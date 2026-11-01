"""ML on the event log: predict from case-start attributes and rank the drivers.

Every task follows the same recipe:

- features: case_features(log), one row per case with the attributes known at
  case start (see features.py). start_time only orders the split.
- split: chronological. The last 20% of cases by start time test. Training
  uses the first 80%, minus the cases that were still running when the first
  test case started: their outcome lies in the test period, so training on
  them would let the model learn from the future. A random split would too.
- models: a reference baseline, a linear model and gradient boosting
  (scikit-learn's HistGradientBoosting). Label attributes are one-hot encoded,
  numbers go in as they are.
- drivers: SHAP values of the gradient boosting model on the test cases. A
  label attribute becomes several one-hot columns; their SHAP values are added
  per case (SHAP values are additive), so each driver is one attribute.

Task A, cycle time, is cycle_time_task. Task B, rework, is rework_tasks: one
classifier per rework gateway. ml_section wraps tasks into the `ml` section of
the results file.
"""

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd
import shap
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import f1_score, mean_absolute_error, r2_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from bpmopt.analysis import cycle_times, rework_flags
from bpmopt.bpmn import ProcessModel
from bpmopt.features import case_features, chronological_split

TRAIN_SHARE = 0.8

# Shallow trees, a small learning rate and big leaves. With a few hundred
# training cases and noisy targets, scikit-learn's defaults overfit: on test
# logs they scored worse than predicting the mean and gave noise attributes
# real SHAP weight. Fixed values, so there's no random validation split.
GRADIENT_BOOSTING = {"max_depth": 3, "learning_rate": 0.05, "min_samples_leaf": 50}


def ml_section(tasks: list[dict]) -> dict:
    """The `ml` section of the results file, for tasks built by cycle_time_task (and rework tasks)."""
    return {"split": {"method": "chronological", "train_share": TRAIN_SHARE}, "tasks": tasks}


def cycle_time_task(log: pd.DataFrame, *, seed: int) -> dict:
    """Task A: predict each case's cycle time from its attributes at case start.

    Reports MAE and R² on the test cases for the reference (training mean),
    linear regression and gradient boosting, and the drivers ranked by mean |SHAP|
    of the gradient boosting model, in working days.
    """
    data = training_data(log, cycle_times(log))
    models = {
        "reference": DummyRegressor(strategy="mean"),
        "linear": Pipeline([("encode", encoder(data.x_train)), ("model", LinearRegression())]),
        "gradient_boosting": Pipeline(
            [("encode", encoder(data.x_train)), ("model", HistGradientBoostingRegressor(**GRADIENT_BOOSTING, random_state=seed))]
        ),
    }
    return {"id": "cycle_time", "kind": "regression", **_fit_and_score(models, data, _regression_metrics)}


def rework_tasks(log: pd.DataFrame, model: ProcessModel, *, seed: int) -> list[dict]:
    """Task B: per rework gateway, predict whether a case loops back at least once.

    One classification task per rework gateway of the model, in model order, with
    id `rework_<gateway_id>`. Only cases that reached the gateway are used.
    Reports ROC-AUC and F1 on the test cases for the reference (majority class),
    logistic regression and gradient boosting, and the drivers ranked by mean
    |SHAP| of the gradient boosting model, in log-odds.

    Class imbalance: rework is usually the minority class. Both real models use
    class_weight="balanced", so each class weighs the same in training. Without
    it, a gateway where no group of cases reworks more often than not gets a model
    that never predicts rework, and F1 0 at the default 0.5 threshold. ROC-AUC
    doesn't depend on the threshold. The reference stays unweighted on purpose:
    it shows what always guessing the majority class scores.

    A gateway where the training or the test cases all went the same way (e.g.
    a loop that never sends work back) can't be fitted or scored. Its task has
    no models or drivers, only `skipped` with the reason, so one such gateway
    doesn't stop the run.
    """
    tasks = []
    for gateway_id, target in rework_flags(log, model).items():
        data = training_data(log, target)
        reason = _single_class_reason(data)
        if reason:
            tasks.append({"id": f"rework_{gateway_id}", "kind": "classification", "gateway_id": gateway_id, "skipped": reason})
            continue
        models = {
            "reference": DummyClassifier(strategy="most_frequent"),
            "linear": Pipeline(
                [("encode", encoder(data.x_train)), ("model", LogisticRegression(class_weight="balanced", max_iter=1_000))]
            ),
            "gradient_boosting": Pipeline(
                [
                    ("encode", encoder(data.x_train)),
                    ("model", HistGradientBoostingClassifier(**GRADIENT_BOOSTING, class_weight="balanced", random_state=seed)),
                ]
            ),
        }
        tasks.append(
            {
                "id": f"rework_{gateway_id}",
                "kind": "classification",
                "gateway_id": gateway_id,
                **_fit_and_score(models, data, _classification_metrics),
            }
        )
    return tasks


def _fit_and_score(models: dict[str, Pipeline], data: "TrainingData", metrics: Callable) -> dict:
    """Fit each model on the training cases and score it on the test cases.

    Returns the task's `models` (in the order given) and the SHAP `drivers` of
    the gradient boosting model.
    """
    reported = []
    for model_id, model in models.items():
        model.fit(data.x_train, data.y_train)
        reported.append({"id": model_id, "metrics": metrics(model, data.x_test, data.y_test)})
    return {"models": reported, "drivers": shap_drivers(models["gradient_boosting"], data.x_test)}


def _regression_metrics(model, x: pd.DataFrame, y: pd.Series) -> dict[str, float]:
    predicted = model.predict(x)
    return {"mae": float(mean_absolute_error(y, predicted)), "r2": float(r2_score(y, predicted))}


def _classification_metrics(model, x: pd.DataFrame, y: pd.Series) -> dict[str, float]:
    return {
        "roc_auc": float(roc_auc_score(y, model.predict_proba(x)[:, 1])),
        "f1": float(f1_score(y, model.predict(x), zero_division=0)),
    }


def _single_class_reason(data: "TrainingData") -> str | None:
    """Why a classifier can't be fitted or scored, or None when both splits hold both classes."""
    parts = []
    for name, y in (("training", data.y_train), ("test", data.y_test)):
        if y.empty:
            parts.append(f"no {name} case reached the gateway")
        elif y.nunique() < 2:
            went = "looped back" if bool(y.iloc[0]) else "didn't loop back"
            parts.append(f"all {len(y)} {name} cases {went}")
    if not parts:
        return None
    return f"Not fitted: {' and '.join(parts)}, so there is nothing to tell apart."


@dataclass(frozen=True)
class TrainingData:
    """Case-start attributes (x) and a per-case target (y), split chronologically."""

    x_train: pd.DataFrame
    x_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series


def training_data(log: pd.DataFrame, target: pd.Series) -> TrainingData:
    """Join a per-case target (indexed by case_id) to the case features and split by start time.

    Cases missing from the target (e.g. ones that never reached a gateway) are
    left out before the split. After it, a training case must have ended before
    the first test case started, so no training outcome comes from the test period.
    """
    features = case_features(log)
    if features.columns.size == 1:
        raise ValueError("the log has no case attributes to learn from; add [attributes.*] to the parameter file")
    features = features[features.index.isin(target.index)]
    train, test = chronological_split(features, TRAIN_SHARE)
    if not test.empty:
        case_end = log.groupby("case_id").end_time.max()
        train = train[case_end.loc[train.index] < test.start_time.min()]
    return TrainingData(
        x_train=train.drop(columns="start_time"),
        x_test=test.drop(columns="start_time"),
        y_train=target.loc[train.index],
        y_test=target.loc[test.index],
    )


def encoder(x: pd.DataFrame) -> ColumnTransformer:
    """One-hot for label attributes, numbers passed through. Labels unseen in training encode as all zeros."""
    labels = [column for column in x.columns if not pd.api.types.is_numeric_dtype(x[column])]
    numbers = [column for column in x.columns if column not in labels]
    return ColumnTransformer(
        [
            ("numbers", "passthrough", numbers),
            ("labels", OneHotEncoder(handle_unknown="ignore", sparse_output=False), labels),
        ]
    )


def shap_drivers(pipeline: Pipeline, x: pd.DataFrame) -> list[dict]:
    """Attributes ranked by mean |SHAP| over the cases in x, largest first.

    pipeline is an encoder step followed by a tree model. The one-hot columns of
    a label attribute are summed per case before taking the absolute value.
    """
    encode, model = pipeline[:-1], pipeline[-1]
    values = np.asarray(shap.TreeExplainer(model).shap_values(encode.transform(x)))
    per_attribute = pd.DataFrame(values, columns=_source_attributes(encode[-1])).T.groupby(level=0).sum().T
    ranked = per_attribute.abs().mean().sort_values(ascending=False, kind="stable")
    return [{"feature": str(name), "mean_abs_shap": float(value)} for name, value in ranked.items()]


def _source_attributes(encoder: ColumnTransformer) -> list[str]:
    """The attribute behind each output column of a fitted encoder, in column order."""
    sources = []
    for name, transformer, columns in encoder.transformers_:
        if name == "numbers":
            sources += columns
        elif name == "labels":
            sources += [column for column, categories in zip(columns, transformer.categories_) for _ in categories]
    return sources

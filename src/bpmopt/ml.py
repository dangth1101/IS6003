"""ML on the event log: predict from case-start attributes and rank the drivers (tickets 11, 12).

Every task follows the same recipe:

- features: case_features(log), one row per case with the attributes known at
  case start (see features.py). start_time only orders the split.
- split: chronological, the first 80% of cases by start time train, the last
  20% test. A random split would let the model learn from later cases.
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

from bpmopt.analysis import cycle_times
from bpmopt.bpmn import ProcessModel
from bpmopt.features import case_features, chronological_split
from bpmopt.flow_analysis import loop_back_flows

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
    reported = []
    for model_id, model in models.items():
        model.fit(data.x_train, data.y_train)
        predicted = model.predict(data.x_test)
        metrics = {"mae": float(mean_absolute_error(data.y_test, predicted)), "r2": float(r2_score(data.y_test, predicted))}
        reported.append({"id": model_id, "metrics": metrics})
    return {
        "id": "cycle_time",
        "kind": "regression",
        "models": reported,
        "drivers": shap_drivers(models["gradient_boosting"], data.x_test),
    }


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
    """
    tasks = []
    for gateway_id, target in rework_targets(log, model).items():
        data = training_data(log, target)
        if data.y_train.nunique() < 2 or data.y_test.nunique() < 2:
            raise ValueError(
                f"{gateway_id}: the training and the test cases both need cases that loop back and cases that don't"
            )
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
        reported = []
        for model_id, classifier in models.items():
            classifier.fit(data.x_train, data.y_train)
            metrics = {
                "roc_auc": float(roc_auc_score(data.y_test, classifier.predict_proba(data.x_test)[:, 1])),
                "f1": float(f1_score(data.y_test, classifier.predict(data.x_test), zero_division=0)),
            }
            reported.append({"id": model_id, "metrics": metrics})
        tasks.append(
            {
                "id": f"rework_{gateway_id}",
                "kind": "classification",
                "gateway_id": gateway_id,
                "models": reported,
                "drivers": shap_drivers(models["gradient_boosting"], data.x_test),
            }
        )
    return tasks


def rework_targets(log: pd.DataFrame, model: ProcessModel) -> dict[str, pd.Series]:
    """Per rework gateway: True for each case that reached it and looped back at least once.

    Indexed by case_id, with only the cases that have a decision row at the
    gateway. Same reading of the log as analysis.rework_rates.
    """
    decisions = log[log.element_type == "exclusiveGateway"]
    targets = {}
    for gateway_id, back_flow in loop_back_flows(model).items():
        at_gateway = decisions[decisions.activity_id == gateway_id]
        targets[gateway_id] = (at_gateway.flow_id == back_flow).groupby(at_gateway.case_id).any()
    return targets


@dataclass(frozen=True)
class TrainingData:
    """Case-start attributes (x) and a per-case target (y), split chronologically."""

    x_train: pd.DataFrame
    x_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series


def training_data(log: pd.DataFrame, target: pd.Series) -> TrainingData:
    """Join a per-case target (indexed by case_id) to the case features and split by start time.

    Cases missing from the target (e.g. ones that never reached a gateway) are left out before the split.
    """
    features = case_features(log)
    if features.columns.size == 1:
        raise ValueError("the log has no case attributes to learn from; add [attributes.*] to the parameter file")
    features = features[features.index.isin(target.index)]
    train, test = chronological_split(features, TRAIN_SHARE)
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

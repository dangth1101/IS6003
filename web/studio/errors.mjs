// Errors in the studio are a code and its data, never a message to show. Python's refusals
// (bpmopt.studio.errors.StudioError) arrive from the worker as { code, data }; the page and the
// worker make their own with studioError(code, data). The text comes from the [errors] table of
// the studio content file, so a translation never touches code.
//
//   throw studioError("fetch_failed", { file, status });
//   const errorText = createErrorText(TEXT.errors);   errorText(e) -> the sentence to show
//
// Anything else that is thrown (a bug, a network failure in a library) shows the text of
// "internal" and goes to the console with its details.

export function studioError(code, data = {}, detail = "") {
  return Object.assign(new Error(detail || code), { code, data, detail });
}

/** The studioError for anything thrown: a studio error as it is, anything else as "internal". */
export function asStudioError(thrown) {
  if (thrown?.code && thrown?.data) return thrown;
  return studioError("internal", {}, String(thrown?.stack ?? thrown?.message ?? thrown));
}

export function createErrorText(errors) {
  const value = (v) => (Array.isArray(v) ? v.join(", ") : v);
  return function errorText(thrown) {
    const error = asStudioError(thrown);
    const code = error.code in errors ? error.code : "internal";
    if (code === "internal") console.error("studio:", error.detail || error);
    return errors[code].replace(/\{(\w+)\}/g, (m, name) => (name in error.data ? value(error.data[name]) : m));
  };
}

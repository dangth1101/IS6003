// Small helpers the studio's UI modules share: building DOM nodes, number formats, and the
// names of parameter entries ("tasks.<id>", "arrivals"), as bpmopt.parameters.entry_key makes them.

/**
 * el(tag, props, ...children): a new element. props: on<event> adds a listener, dataset and
 * style (CSS text) are set as a whole, a DOM property (className, type, disabled, open, ...) is
 * assigned, anything else (aria-*, ...) becomes an attribute. A prop that is null, undefined or
 * false is left out, so { disabled: false } leaves the element enabled. Children may be nested
 * arrays, nodes or strings; null, undefined and false are skipped.
 */
export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "dataset") Object.assign(node.dataset, value);
    else if (key === "style") node.style.cssText = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (key in node) node[key] = value;
    else node.setAttribute(key, value);
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : String(child));
  }
  return node;
}

/** Number formats for the page's language, each Intl.NumberFormat made once. */
export function formatters(lang) {
  const made = new Map();
  const format = (options) => {
    const key = JSON.stringify(options);
    if (!made.has(key)) made.set(key, new Intl.NumberFormat(lang, options));
    return made.get(key);
  };
  return {
    /** Exactly `digits` decimals, e.g. a cycle time in days. */
    fixed: (value, digits = 1) => format({ minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value),
    /** Up to `digits` decimals, e.g. a parameter value as typed. */
    upTo: (value, digits = 3) => format({ maximumFractionDigits: digits }).format(value),
    /** A whole number with grouping, e.g. 1,000 cases. */
    whole: (value) => format({ maximumFractionDigits: 0 }).format(value),
    /** A share as a percentage with exactly `digits` decimals. */
    percent: (value, digits = 0) => format({ style: "percent", minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value),
    /** A share as a percentage with up to `digits` decimals. */
    percentUpTo: (value, digits = 1) => format({ style: "percent", maximumFractionDigits: digits }).format(value),
  };
}

/** The name of a parameter entry: entryKey("tasks", "Task_X") is "tasks.Task_X", entryKey("arrivals") "arrivals". */
export function entryKey(section, id = null) {
  return id === null ? section : `${section}.${id}`;
}

/** [section, id] of an entry name; id is null for a single entry such as "arrivals". */
export function splitEntry(key) {
  const dot = key.indexOf(".");
  return dot < 0 ? [key, null] : [key.slice(0, dot), key.slice(dot + 1)];
}

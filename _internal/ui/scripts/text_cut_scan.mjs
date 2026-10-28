import { parseSync } from "rolldown/utils";
import postcss from "postcss";

export function scanTextCuts(file, source) {
  const findings = [];
  const add = (index, why) => findings.push({ file, line: source.slice(0, index).split("\n").length, why });
  const nowrap = value => /(?:^|[\s:!])whitespace-nowrap\b|\[white-space:nowrap\]/.test(value);
  const clips = value => /(?:^|[\s:!])overflow(?:-[xy])?-(?:hidden|clip)\b|\[overflow(?:-[xy])?:(?:hidden|clip)\]/.test(value);
  const classes = (value, index) => {
    for (const token of value.split(/\s+/)) {
      if (/(?:^|:)!?truncate!?$|(?:^|:)!?line-clamp-/.test(token)) add(index, `text-cut utility: ${token}`);
      if (/\[(?:text-overflow:ellipsis|(?:-webkit-)?line-clamp:)/.test(token)) add(index, `text-cut utility: ${token}`);
    }
    if (nowrap(value) && clips(value)) add(index, "nowrap + hidden/clip overflow");
  };
  if (file.endsWith(".css")) {
    const selectors = new Map();
    postcss.parse(source, { from: file }).walkDecls(decl => {
      if ((decl.prop === "text-overflow" && decl.value === "ellipsis") || /^(?:-webkit-)?line-clamp$/.test(decl.prop)) add(decl.source.start.offset, `${decl.prop}: ${decl.value}`);
      const selector = decl.parent.toString().split("{")[0].trim();
      const previous = selectors.get(selector) ?? { declarations: "", index: decl.source.start.offset };
      previous.declarations += `${decl.prop}: ${decl.value};`;
      selectors.set(selector, previous);
    });
    for (const { declarations, index } of selectors.values()) {
      if (/white-space\s*:\s*nowrap\b/.test(declarations) && /overflow(?:-[xy])?\s*:\s*(?:hidden|clip)\b/.test(declarations)) add(index, "nowrap + hidden/clip overflow");
    }
  } else {
    // Use the parser already installed with Vite; comments, regex literals and
    // template expressions must not confuse the scan or hide real JSX classes.
    const parsed = parseSync(file, source);
    if (parsed.errors.length) throw new Error(`${file}: ${JSON.stringify(parsed.errors)}`);
    const children = node => Object.values(node).flatMap(v => Array.isArray(v) ? v.filter(x => x?.type) : v?.type ? [v] : []);
    const strings = node => !node ? [] : node.type === "Literal" && typeof node.value === "string" ? [node.value] : node.type === "TemplateElement" ? [node.value.raw] : children(node).flatMap(strings);
    const styleProperties = node => new Map((node?.properties ?? []).filter(p => p.type === "Property").map(p => [p.key.name ?? p.key.value, p.value.value]));
    const visit = node => {
      if (node.type === "Literal" && typeof node.value === "string") classes(node.value, node.start);
      if (node.type === "TemplateElement") classes(node.value.raw, node.start);
      if (node.type === "ObjectExpression") {
        const properties = styleProperties(node);
        if (properties.get("textOverflow") === "ellipsis") add(node.start, "textOverflow: ellipsis");
        if (["WebkitLineClamp", "webkitLineClamp", "lineClamp"].some(p => properties.has(p))) add(node.start, "inline line clamp");
        if (properties.get("whiteSpace") === "nowrap" && ["overflow", "overflowX", "overflowY"].some(p => /^(hidden|clip)$/.test(properties.get(p)))) add(node.start, "inline nowrap + hidden/clip overflow");
      }
      if (node.type === "JSXAttribute" && node.name.name === "className") {
        const value = strings(node.value).join(" ");
        if (nowrap(value) && clips(value)) add(node.start, "className nowrap + hidden/clip overflow");
      }
      if (node.type === "CallExpression" && /^(cn|clsx|classNames|cva)$/.test(node.callee.name)) {
        const value = node.arguments.flatMap(strings).join(" ");
        if (nowrap(value) && clips(value)) add(node.start, "shared classes nowrap + hidden/clip overflow");
      }
      if (node.type === "JSXOpeningElement") {
        const attributes = node.attributes.filter(a => a.type === "JSXAttribute");
        const value = strings(attributes.find(a => a.name.name === "className")?.value).join(" ");
        const style = styleProperties(attributes.find(a => a.name.name === "style")?.value?.expression);
        if ((nowrap(value) && ["overflow", "overflowX", "overflowY"].some(p => /^(hidden|clip)$/.test(style.get(p)))) ||
          (clips(value) && style.get("whiteSpace") === "nowrap")) add(node.start, "mixed class/style nowrap + hidden/clip overflow");
      }
      children(node).forEach(visit);
    };
    visit(parsed.program);
  }
  return findings;
}

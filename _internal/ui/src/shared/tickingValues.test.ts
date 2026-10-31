// @vitest-environment node
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseSync } from "rolldown/utils";
import { describe, expect, it } from "vitest";

const root = fileURLToPath(new URL("..", import.meta.url));
// Display formatters: include new time/progress/size/count formatters here.
const formatters = new Set([
  "formatTime", "formatClock", "formatLength", "formatLengthUp", "formatEta", "etaOf",
  "formatPercent", "percentOf", "formatSize", "formatNumber", "formatRelative", "formatWhen",
  "sleepLabel", "sleepButtonLabel", "bookProgressText", "bookStatusText", "progressNote",
  "vieneuLabel", "vieneuPercent", "moduleLabel", "modulePercent", "preciseLabel",
  "progressText", "progressView", "findStatus", "expiryClock",
]);
const motion = /^(?:MotionRegion|AnimatedContent|Crossfade|RollingLabel|MovingTextAction|motion\.)/;
const live = new Set(["TickingValue", "LiveText", "ExportProgressText"]);
const motionClass = /(?:^|[\s"'`])(?:transition(?:-(?:all|opacity|transform|\[[^\]]*(?:opacity|transform)[^\]]*\]))?|animate-\S+)(?=[\s"'`]|$)/;

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap(entry => statSync(join(dir, entry)).isDirectory()
    ? sources(join(dir, entry)) : /\.tsx$/.test(entry) && !/\.test\.tsx$/.test(entry) ? [join(dir, entry)] : []);
}

/** Parse TSX, so nested tags, multiline props, aliases and comments are handled structurally. */
function violations(source: string): string[] {
  // Vite's parser handles TypeScript 7 sources without depending on the removed TS compiler JS API.
  type Node = { type: string; start: number; end: number; [key: string]: unknown };
  const isNode = (value: unknown): value is Node => Boolean(value && typeof value === "object" && "type" in value && "start" in value);
  const field = (node: Node, key: string) => isNode(node[key]) ? node[key] as Node : undefined;
  const children = (node: Node): Node[] => Object.values(node).flatMap(value => Array.isArray(value) ? value.filter(isNode) : isNode(value) ? [value] : []);
  const text = (node?: Node) => node ? source.slice(node.start, node.end) : "";
  const parsed = parseSync("source.tsx", source);
  expect(parsed.errors).toEqual([]);
  const file = parsed.program as unknown as Node;
  const parents = new WeakMap<Node, Node>();
  const definitions: Node[] = [];
  const gather = (node: Node) => {
    if (node.type === "VariableDeclarator") definitions.push(node);
    for (const child of children(node)) { parents.set(child, node); gather(child); }
  };
  gather(file);
  function scope(node: Node): Node {
    for (let p = parents.get(node); p; p = parents.get(p)) if (["BlockStatement", "Program"].includes(p.type)) return p;
    return file;
  }
  function visible(declaration: Node, use: Node) {
    const owner = scope(declaration);
    for (let p: Node | undefined = use; p; p = parents.get(p)) if (p === owner) return true;
    return false;
  }
  function ticking(node: Node, seen = new Set<Node>(), key = false): boolean {
    if (seen.has(node)) return false;
    seen.add(node);
    if (["JSXElement", "JSXFragment", "ArrowFunctionExpression", "FunctionExpression"].includes(node.type)) return false;
    // This helper selects a user action/chapter title; its heard count is only a condition.
    if (node.type === "CallExpression" && text(field(node, "callee")) === "primaryListenLabel") return false;
    // A ticking condition selecting a fixed label is a phase change, not ticking text.
    if (node.type === "ConditionalExpression") return [field(node, "consequent"), field(node, "alternate")].some(branch => branch && ticking(branch, seen, key));
    if (node.type === "LogicalExpression" && node.operator === "&&") {
      const right = field(node, "right");
      return right ? ticking(right, seen, key) : false;
    }
    if (node.type === "CallExpression" && formatters.has(text(field(node, "callee")))) {
      const name = text(field(node, "callee"));
      const args = (node.arguments as Node[]).map(argument => text(argument)).join(",");
      // Fixed metadata and user-selected counts/sizes aren't ticking. All formatters remain forbidden in motion keys.
      const metadata = /^(?:chapter\.(?:duration|seconds|words|chars)|item\.(?:duration|at)|cue\.|scene\.|track\.duration|marker\.seconds|person\.|cast\.|file\.|choice\.|status\.outdatedBytes|voice\.fastBytes|module\.(?:total|outdatedBytes)|precise\.bytes)/.test(args)
        || /(?:expiresAt|scene\.start|scene\.end|scan!\.totals\.audioSeconds)/.test(args);
      const selectedCount = name === "formatNumber" && !/(?:progress\.|book\.segments|pending|counted|aligned)/.test(args);
      const selectedSize = name === "formatSize" && !/(?:progress\.|\.done|sizes\.current|download)/i.test(args);
      if (key || (!metadata && !selectedCount && !selectedSize)) return true;
      return false;
    }
    if (node.type === "MemberExpression") {
      if (/^(percent|secondsLeft|elapsed|heardSeconds|scanned)$/.test(text(field(node, "property")))) return true;
      const object = field(node, "object");
      return object ? ticking(object, seen, key) : false;
    }
    if (node.type === "Identifier") {
      const definition = definitions.filter(d => text(field(d, "id")) === text(node) && field(d, "init") && d.start < node.start && visible(d, node)).at(-1);
      const init = definition && field(definition, "init");
      if (init && ticking(init, seen, key)) return true;
    }
    return children(node).some(child => ticking(child, seen, key));
  }
  function opening(node: Node) {
    return node.type === "JSXElement" ? field(node, "openingElement") : undefined;
  }
  function attr(node: Node, name: string) {
    const attributes = opening(node)?.attributes;
    return Array.isArray(attributes) ? attributes.filter(isNode).find(p => p.type === "JSXAttribute" && text(field(p, "name")) === name) : undefined;
  }
  const errors: string[] = [];
  function renderedTicking(node: Node): boolean {
    if (node.type === "ConditionalExpression") return [field(node, "consequent"), field(node, "alternate")].some(branch => branch && renderedTicking(branch));
    if (node.type === "LogicalExpression" && node.operator === "&&") {
      const right = field(node, "right");
      return right ? renderedTicking(right) : false;
    }
    return ticking(node);
  }
  const report = (node: Node, reason: string) => errors.push(`${source.slice(0, node.start).split("\n").length}: ${reason}`);
  const visit = (node: Node) => {
    const open = opening(node);
    const tag = open && text(field(open, "name"));
    if (tag) {
      for (const name of ["motionKey", "triggerKey", "key", "targetState"]) {
        const attribute = attr(node, name);
        const value = attribute && field(attribute, "value");
        if (value && ticking(value, new Set(), true)) report(value, `${tag} ${name} depends on ticking text`);
      }
    }
    const expression = field(node, "expression");
    if (node.type === "JSXExpressionContainer" && expression && parents.get(node)?.type !== "JSXAttribute" && renderedTicking(expression)) {
      let parent = parents.get(node);
      let protectedValue = false;
      while (parent && parent.type !== "Program") {
        const open = opening(parent);
        const tag = open && text(field(open, "name"));
        if (tag) {
          const role = attr(parent, "role");
          if (live.has(tag) || attr(parent, "data-motion-live") || /["'](?:timer|progressbar)["']/.test(text(role && field(role, "value")))) protectedValue = true;
          const className = attr(parent, "className");
          const classes = text(className && field(className, "value"));
          // Hover/focus opacity is user motion; a plain value transition remains forbidden.
          if (motionClass.test(classes) && !/(?:hover:|focus)/.test(classes)) report(node, `${tag} transitions ticking text`);
          if (motion.test(tag)) {
            // Stable phase/book/user-choice keys are legitimate open/close or user motion.
            if (!protectedValue && !attr(parent, "motionKey")) report(node, `${tag} wraps ticking text without a live boundary`);
            break;
          }
        }
        parent = parents.get(parent);
      }
    }
    children(node).forEach(visit);
  };
  visit(file);
  return [...new Set(errors)];
}

describe("ticking numbers stay in place", () => {
  it("scans all main TSX, including phone-web, desktop and Studio", () => {
    const errors = sources(root).flatMap(path => violations(readFileSync(path, "utf8")).map(error => `${path.slice(root.length)}:${error}`));
    expect(errors).toEqual([]);
  });
  it("detects nested/multiline motion, aliases, numeric keys and transition classes", () => {
    expect(violations(`const elapsed = formatClock(time); const label = elapsed;
      <MotionRegion><strong><span>{label}</span></strong></MotionRegion>`)).not.toEqual([]);
    expect(violations(`<MotionRegion motionKey={formatPercent(progress)}><TickingValue>{formatPercent(progress)}</TickingValue></MotionRegion>`)).not.toEqual([]);
    expect(violations(`<span className="transition-opacity">{formatClock(time)}</span>`)).not.toEqual([]);
    expect(violations(`<div className="transition-transform"><strong><span>{formatClock(time)}</span></strong></div>`)).not.toEqual([]);
    expect(violations(`<MotionRegion><TickingValue>{formatClock(time)}</TickingValue></MotionRegion>`)).toEqual([]);
    expect(violations(`<MotionRegion motionKey={chapter.title}>{chapter.title}</MotionRegion>`)).toEqual([]);
    expect(violations(`<MotionRegion motionKey={speed}>{speed}</MotionRegion>`)).toEqual([]);
  });
  it("live-value CSS uses tabular digits, including the real fallback font, without value transitions", () => {
    const css = readFileSync(join(root, "styles.css"), "utf8");
    for (const selector of [".tabular", ".tabular-nums", ".ticking-value", "[data-motion-live]"]) {
      const rule = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].find(match => match[1].split(",").map(s => s.trim()).includes(selector));
      expect(rule, selector).toBeDefined();
      expect(rule![2]).toMatch(/font-variant-numeric:\s*tabular-nums/);
      expect(rule![2]).toContain('"Be Vietnam Pro Digits"');
      expect(rule![2]).not.toMatch(/(?:transition|animation)\s*:/);
    }
  });
});

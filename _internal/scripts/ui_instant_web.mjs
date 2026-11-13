// L7 web classifier (see ui_instant.py). Every `cond && <Element>` is a site. Rules stop at
// render/function boundaries: a parent's MotionRegion cannot observe state owned by a child component.
import fs from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(new URL('../ui/package.json', import.meta.url));
const { parseAst } = require('rolldown/parseAst');

const MOTION_COMPONENTS = new Set(['MotionPresence', 'Collapse', 'MotionRegion', 'Popover.Close']);
const FUNCTIONS = new Set(['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression']);
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const result = [];
const unwrap = node => { while (node?.type === 'ParenthesizedExpression') node = node.expression; return node; };
const tagName = name => !name ? '' : name.type === 'JSXIdentifier' ? name.name
  : name.type === 'JSXMemberExpression' ? `${tagName(name.object)}.${name.property.name}` : '';
const attr = (element, name) => element.openingElement.attributes.find(p => p.name?.name === name);

function identifiers(node, out = new Set()) {
  if (!node || typeof node !== 'object') return out;
  if (node.type === 'Identifier') out.add(node.name);
  for (const [key, value] of Object.entries(node)) {
    if (key === 'property' && node.type === 'MemberExpression' && !node.computed) continue;
    for (const child of Array.isArray(value) ? value : [value]) if (child && typeof child === 'object' && typeof child.type === 'string') identifiers(child, out);
  }
  return out;
}

/** Value paths read by an expression: `count`, `item.id` (a.b.c chains, not their parts). */
function paths(node, out = new Set()) {
  if (!node || typeof node !== 'object') return out;
  if (node.type === 'MemberExpression' && !node.computed) {
    const chain = [];
    let at = node;
    while (at?.type === 'MemberExpression' && !at.computed) { chain.unshift(at.property.name); at = at.object; }
    if (at?.type === 'Identifier') { out.add([at.name, ...chain].join('.')); return out; }
  }
  if (node.type === 'Identifier') { if (node.name !== 'undefined') out.add(node.name); return out; }
  for (const value of Object.values(node)) for (const child of Array.isArray(value) ? value : [value]) if (child && typeof child === 'object' && typeof child.type === 'string') paths(child, out);
  return out;
}

/** Names bound to useMediaQuery(...) in the nearest enclosing function body. */
function mediaNames(fn) {
  const names = new Set();
  (function walk(node) {
    if (!node || typeof node !== 'object') return;
    if (node !== fn && FUNCTIONS.has(node.type)) return;
    if (node.type === 'VariableDeclarator' && node.id.type === 'Identifier') {
      const init = unwrap(node.init);
      if (init?.type === 'CallExpression' && init.callee.name === 'useMediaQuery') names.add(node.id.name);
    }
    for (const value of Object.values(node)) for (const child of Array.isArray(value) ? value : [value]) if (child && typeof child === 'object' && typeof child.type === 'string') walk(child);
  })(fn.body ?? fn);
  return names;
}

function reason(node, element, ancestors) {
  const tag = tagName(element.openingElement.name);
  if (MOTION_COMPONENTS.has(tag)) return ['b-motion-component', `${tag} animates its own presence`];
  if (['data-state', 'onAnimationEnd'].some(n => attr(element, n))) return ['b-own-presence', 'the element runs its own enter/exit animation (usePresence)'];
  if (EMPTY.has(tag)) return ['b-not-visible', `${tag} renders nothing on screen`];
  const cls = attr(element, 'className')?.value;
  if (cls?.type === 'Literal' && /(^|\s)sr-only(\s|$)/.test(cls.value)) return ['b-not-visible', 'screen-reader-only text: never painted'];
  for (const owner of ancestors.toReversed()) {
    if (FUNCTIONS.has(owner.type)) {
      const media = mediaNames(owner);
      const names = [...identifiers(node.left)];
      if (names.length && names.every(n => media.has(n))) return ['b-responsive', 'layout follows the window size (useMediaQuery)'];
      break;
    }
    if (owner.type !== 'JSXElement') continue;
    if (tagName(owner.openingElement.name) === 'Presence') {
      const children = owner.children.filter(child => child.type !== 'JSXText' || child.value.trim());
      if (children.length === 1 && children[0].type === 'JSXExpressionContainer' && unwrap(children[0].expression) === node)
        return ['b-retained-presence', 'Presence directly owns this conditional value and retains its last tree through exit'];
    }
    if (tagName(owner.openingElement.name) !== 'MotionRegion') continue;
    // A keyed region deliberately ignores children outside its key - unless the key is the very value the condition reads.
    const key = attr(owner, 'motionKey')?.value?.expression;
    if (!key && !attr(owner, 'data-motion-live')) return ['b-parent-motion', 'a MotionRegion animates this expression in the same render'];
    const keyed = paths(key), names = [...paths(node.left)];
    if (key && names.length && names.every(n => keyed.has(n))) return ['b-parent-motion', 'a MotionRegion keyed on the same value animates it'];
    break;
  }
  return ['a-hard', 'direct conditional with no transition'];
}

/** Components whose every own `return` gives null: effect hosts that never paint. */
const EMPTY = new Set();
const trees = input.map(({ path, source }) => parseAst(source, { lang: 'tsx', astType: 'ts' }, path));
for (const tree of trees) {
  (function walk(node) {
    let name = '', fn = null;
    if (node.type === 'FunctionDeclaration' && /^[A-Z]/.test(node.id?.name ?? '')) [name, fn] = [node.id.name, node];
    if (node.type === 'VariableDeclarator' && /^[A-Z]/.test(node.id?.name ?? '') && FUNCTIONS.has(unwrap(node.init)?.type)) [name, fn] = [node.id.name, unwrap(node.init)];
    if (fn && fn.body?.type === 'BlockStatement') {
      const returns = [];
      (function own(n) {
        if (!n || typeof n !== 'object') return;
        if (n !== fn && FUNCTIONS.has(n.type)) return;
        if (n.type === 'ReturnStatement') returns.push(n.argument);
        for (const v of Object.values(n)) for (const c of Array.isArray(v) ? v : [v]) if (c && typeof c === 'object' && typeof c.type === 'string') own(c);
      })(fn.body);
      if (returns.length && returns.every(r => !r || (r.type === 'Literal' && r.value === null) || (r.type === 'Identifier' && r.name === 'undefined'))) EMPTY.add(name);
    }
    for (const v of Object.values(node)) for (const c of Array.isArray(v) ? v : [v]) if (c && typeof c === 'object' && typeof c.type === 'string') walk(c);
  })(tree);
}

for (const [index, { path, source }] of input.entries()) {
  const tree = trees[index];
  const lineOf = offset => source.slice(0, offset).split('\n').length;
  (function visit(node, ancestors) {
    if (node.type === 'LogicalExpression' && node.operator === '&&') {
      const right = unwrap(node.right);
      if (right.type === 'JSXElement') {
        const [category, why] = reason(node, right, ancestors);
        const line = lineOf(node.start);
        result.push({ path, line, text: source.split('\n')[line - 1].trim().slice(0, 90), platform: 'web',
          object: tagName(right.openingElement.name), category, reason: why });
      }
    }
    for (const value of Object.values(node)) {
      for (const child of Array.isArray(value) ? value : [value]) {
        if (child && typeof child === 'object' && typeof child.type === 'string') visit(child, [...ancestors, node]);
      }
    }
  })(tree, []);
}
process.stdout.write(JSON.stringify(result));

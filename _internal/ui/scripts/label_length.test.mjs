// @vitest-environment node
// DESIGN.md §1.7 "Chữ ngắn": nhãn nút / mục menu / lựa chọn 1-4 chữ. Máy đếm trên mã nguồn (soát 26-10 thấy 15 nhãn 5-8 chữ:
// "Bỏ qua gợi ý - giữ sách như cũ", "Mở cài đặt để cho phép"...): giải thích thuộc về dòng mô tả cạnh nút, không nằm trong nút.
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { parseAst } from "rolldown/parseAst";
import { expect, it } from "vitest";

const src = path.resolve(import.meta.dirname, "../src");
function files(dir) { return readdirSync(dir, { withFileTypes: true }).flatMap(entry => entry.isDirectory() ? files(path.join(dir, entry.name)) : [path.join(dir, entry.name)]); }

// Thẻ mà chữ con là nhãn nhìn thấy được.
const CONTROL = /^(button|Button|a|Link|NavLink|option|MenuItem|.*\.Item|.*\.Trigger|.*RadioItem|.*CheckboxItem|.*Choice|.*Option)$/;
// `label` của các thẻ này là tên cho trình đọc màn hình / chú thích nổi, không phải chữ in trên nút: được nói đủ ý.
const SPOKEN = /^(IconButton|Tooltip|Switch|ChoiceRow|NumberBox|Progress|Slider|MenuShell)$/;
const LABEL_PROP = /^(label|action|actionLabel|confirmLabel|cancelLabel)$/;
const name = n => n.type === "JSXIdentifier" ? n.name : n.type === "JSXMemberExpression" ? `${name(n.object)}.${name(n.property)}` : "";
// Chuỗi có thể hiện ra từ một biểu thức: hằng, hai nhánh của ?:, vế phải của &&; phần ${...} (số đếm, tên) không tính là chữ.
// Tên hằng chuỗi khai báo trong cùng file (`const SCENE_LABEL = "..."`) được đổi ra chuỗi của nó.
const strings = (e, consts = new Map()) => !e ? [] : e.type === "Literal" && typeof e.value === "string" ? [e.value]
  : e.type === "TemplateLiteral" ? [e.quasis.map(q => q.value.cooked).join(" ")]
  : e.type === "Identifier" ? consts.get(e.name) ?? []
  : e.type === "ConditionalExpression" ? [...strings(e.consequent, consts), ...strings(e.alternate, consts)]
  : e.type === "LogicalExpression" ? strings(e.right, consts) : [];
const words = text => text.split(/\s+/).filter(word => /\p{L}/u.test(word)).length;

function longLabels(where, code, lang = "tsx") {
  const found = [];
  const report = (at, text) => { const t = text.replace(/\s+/g, " ").trim(); if (words(t) > 4) found.push(`${where}:${code.slice(0, at).split("\n").length} ${t}`); };
  const ast = parseAst(code, { lang });
  const consts = new Map();
  for (const stmt of ast.body) {
    const decl = stmt.type === "ExportNamedDeclaration" ? stmt.declaration : stmt;
    if (decl?.type === "VariableDeclaration" && decl.kind === "const") for (const d of decl.declarations)
      if (d.id.type === "Identifier" && (d.init?.type === "Literal" || d.init?.type === "TemplateLiteral")) consts.set(d.id.name, strings(d.init));
  }
  // Chữ của điều khiển nằm cả trong thẻ con (`<button><span>Nhãn</span></button>`): mỗi đoạn chữ là một nhãn, trừ dòng mô tả nhạt cạnh nhãn.
  const hint = el => /(^|\s)(text-fg-2|text-fg-3|text-xs|sr-only)(\s|$)/.test(el.openingElement.attributes.find(a => a.type === "JSXAttribute" && a.name.name === "className")?.value?.value ?? "");
  const texts = (el, inner = false) => inner && hint(el) ? [] : el.children.flatMap(c => c.type === "JSXText" ? [[c.start, c.value]]
    : c.type === "JSXExpressionContainer" ? strings(c.expression, consts).map(s => [c.start, s])
    : c.type === "JSXElement" && !CONTROL.test(name(c.openingElement.name)) ? texts(c, true) : []);
  const visit = node => {
    if (!node || typeof node !== "object") return;
    if (Array.isArray(node)) return node.forEach(visit);
    if (node.type === "Property" && LABEL_PROP.test(node.key?.name ?? node.key?.value ?? "")) for (const s of strings(node.value, consts)) report(node.start, s);
    if (node.type === "JSXElement") {
      const tag = name(node.openingElement.name);
      if (CONTROL.test(tag)) {
        report(node.start, node.children.filter(c => c.type === "JSXText").map(c => c.value).join(" "));
        for (const c of node.children) if (c.type === "JSXExpressionContainer") for (const s of strings(c.expression, consts)) report(c.start, s);
        for (const c of node.children) if (c.type === "JSXElement" && !CONTROL.test(name(c.openingElement.name))) for (const [at, s] of texts(c, true)) report(at, s);
      }
      if (!SPOKEN.test(tag)) for (const a of node.openingElement.attributes)
        if (a.type === "JSXAttribute" && a.value && LABEL_PROP.test(a.name.name ?? "")) for (const s of strings(a.value.type === "JSXExpressionContainer" ? a.value.expression : a.value, consts)) report(a.start, s);
    }
    for (const key in node) if (key !== "start" && key !== "end") visit(node[key]);
  };
  visit(ast);
  return found;
}

it("nhãn nút, mục menu và lựa chọn không quá 4 chữ", () => {
  const offenders = files(src)
    .filter(file => /\.tsx?$/.test(file) && !file.endsWith(".d.ts") && !file.includes(".test.") && !file.includes(`${path.sep}gallery${path.sep}`))
    .flatMap(file => longLabels(path.relative(src, file), readFileSync(file, "utf8"), file.endsWith(".tsx") ? "tsx" : "ts"));
  expect(offenders).toEqual([]);
});

it("máy đếm bắt được nhãn dài ở chữ con, nhánh ?: và thuộc tính label; bỏ qua tên đọc cho trình đọc màn hình", () => {
  const code = `const a = <Button>Bỏ qua gợi ý - giữ sách như cũ</Button>;
const b = <button>{busy ? "Đang lưu" : "Lưu lại toàn bộ thay đổi này"}</button>;
const c = <Choice label="Đọc lời chú ở cuối chương" />;
const d = [{ id: "mp3", label: "MP3 - mỗi chương một file" }];
const e = <button>{\`Làm trước \${n} chương tới\`}</button>;
const f = <IconButton label="Thêm tuỳ chọn cho đoạn này" />;
const g = <Button>Nghe tiếp</Button>;`;
  expect(longLabels("probe", code)).toEqual([
    "probe:1 Bỏ qua gợi ý - giữ sách như cũ",
    "probe:2 Lưu lại toàn bộ thay đổi này",
    "probe:3 Đọc lời chú ở cuối chương",
    "probe:4 MP3 - mỗi chương một file",
  ]);
});

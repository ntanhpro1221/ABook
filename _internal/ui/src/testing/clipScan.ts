// Máy dò chỗ cắt chữ trên cây JSX thật (rolldown parseAst), không phải regex trên mã: bắt cả chữ nằm trong thẻ con lồng nhau, chữ đứng sau icon,
// lớp trong cn("a", { b: c }, "truncate") / mẫu chuỗi / điều kiện, và line-clamp-[3] (soát leftfix mục 4: máy dò regex cũ sót cả năm dạng ấy).
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { parseAst } from "rolldown/parseAst";

/** Lớp cắt chữ của Tailwind: "…" một dòng hoặc cắt sau N dòng. */
export const CLIP_CLASS = /(?:^|[\s:])(truncate|text-ellipsis|line-clamp-(?:\d+|\[[^\]]+\]))(?=\s|$)/;

export interface ClipHit {
  /** "listen/PlayerViews.tsx" - đường dẫn tính từ src/. */
  file: string;
  line: number;
  /** Lớp cắt tìm thấy ("truncate", "line-clamp-2"...). */
  clip: string;
  /** Toàn bộ lớp (mọi nhánh) của thẻ cắt. */
  classes: string;
  /** Mọi biểu thức `{...}` trong thẻ cắt và MỌI thẻ con của nó, theo thứ tự xuất hiện (mã nguồn nguyên văn, khoảng trắng gộp). */
  exprs: string[];
  /** 600 ký tự mã đứng trước thẻ: chỗ giữ có chủ ý khoá theo ngữ cảnh này (nút, data-*), không theo cả file. */
  before: string;
}

type Node = { type: string; start: number; end: number; [key: string]: unknown };

/** Mọi chuỗi lớp có thể có của một biểu thức className: chuỗi, mẫu chuỗi, điều kiện, &&/||, cn(...) / clsx(...), mảng, khoá của object. */
export function classStrings(node: Node | null | undefined): string[] {
  if (!node) return [];
  switch (node.type) {
    case "Literal": return typeof node.value === "string" ? [node.value] : [];
    case "TemplateLiteral": return [...(node.quasis as { value: { cooked: string } }[]).map((q) => q.value.cooked), ...(node.expressions as Node[]).flatMap(classStrings)];
    case "ConditionalExpression": return [...classStrings(node.consequent as Node), ...classStrings(node.alternate as Node)];
    case "LogicalExpression": return [...classStrings(node.left as Node), ...classStrings(node.right as Node)];
    case "CallExpression": return (node.arguments as Node[]).flatMap(classStrings);
    case "ArrayExpression": return (node.elements as Node[]).flatMap(classStrings);
    case "ObjectExpression": return (node.properties as Node[]).flatMap((p) => {
      if (p.type !== "Property") return [];
      const key = p.key as Node;
      return key.type === "Identifier" ? [String(key.name)] : key.type === "Literal" ? [String(key.value)] : classStrings(key);
    });
    case "TSAsExpression": case "TSSatisfiesExpression": case "ParenthesizedExpression": return classStrings(node.expression as Node);
    default: return [];
  }
}

/** Quét một file mã (chuỗi) - dùng cho cả cây mã thật và các mẫu đối chứng trong test. */
export function scanClips(file: string, code: string): ClipHit[] {
  const ast = parseAst(code, { lang: file.endsWith(".ts") ? "ts" : "tsx" }) as unknown as Node;
  const hits: ClipHit[] = [];
  const text = (node: Node) => code.slice(node.start, node.end).replace(/\s+/g, " ").trim();
  const exprs = (el: Node): string[] => (el.children as Node[]).flatMap((child) => {
    if (child.type === "JSXExpressionContainer") {
      const expression = child.expression as Node;
      return expression.type === "JSXEmptyExpression" ? [] : [`{${text(expression)}}`];
    }
    return child.type === "JSXElement" || child.type === "JSXFragment" ? exprs(child) : [];
  });
  const visit = (node: unknown): void => {
    if (!node || typeof node !== "object") return;
    if (Array.isArray(node)) { node.forEach(visit); return; }
    const n = node as Node;
    if (n.type === "JSXElement") {
      const attrs = (n.openingElement as { attributes: Node[] }).attributes;
      const cls = attrs.find((a) => a.type === "JSXAttribute" && (a.name as Node & { name: string }).name === "className");
      const value = cls?.value as Node | undefined;
      const values = !value ? [] : value.type === "Literal" ? [String(value.value)] : classStrings(value.expression as Node);
      const clip = values.map((v) => CLIP_CLASS.exec(v)?.[1]).find(Boolean);
      if (clip) hits.push({ file, line: code.slice(0, n.start).split("\n").length, clip, classes: values.join(" "), exprs: exprs(n), before: code.slice(Math.max(0, n.start - 600), n.start) });
    }
    for (const key in n) if (key !== "start" && key !== "end" && key !== "type") visit(n[key]);
  };
  visit(ast);
  return hits;
}

const root = path.resolve(import.meta.dirname, "..");
function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    return statSync(full).isDirectory() ? sourceFiles(full) : [full];
  });
}

let cache: ClipHit[] | undefined;
/** Mọi chỗ cắt chữ trong mã giao diện (src/, trừ test, gallery và mã kiểm). */
export function clipHits(): ClipHit[] {
  cache ??= sourceFiles(root)
    .filter((full) => full.endsWith(".tsx") && !full.includes(".test.") && !/[\\/](gallery|testing)[\\/]/.test(full))
    .flatMap((full) => scanClips(full.slice(root.length + 1).replaceAll("\\", "/"), readFileSync(full, "utf8")));
  return cache;
}

/** Lớp chiều cao cố định (h-9, h-[2.75em]...) - không phải min-h / max-h / h-auto / h-full / h-fit. */
export const FIXED_HEIGHT = /(?:^|[\s:])h-(?!auto\b|full\b|fit\b|min\b|max\b|screen\b|dvh\b|svh\b)[\w.[\]()%-]+(?=\s|$)/;

export interface FitFrameHit { file: string; line: number; classes: string }

/** Thẻ cha TRỰC TIẾP của <OneLineFit> mang chiều cao cố định: tên xuống dòng thì tràn dọc đè lên hàng dưới (soát leftfix T1 - nút chọn chương h-9). */
export function scanFitFrames(file: string, code: string): FitFrameHit[] {
  const ast = parseAst(code, { lang: "tsx" }) as unknown as Node;
  const hits: FitFrameHit[] = [];
  const tag = (el: Node) => { const name = (el.openingElement as { name: Node }).name; return name.type === "JSXIdentifier" ? String(name.name) : ""; };
  const visit = (node: unknown): void => {
    if (!node || typeof node !== "object") return;
    if (Array.isArray(node)) { node.forEach(visit); return; }
    const n = node as Node;
    if (n.type === "JSXElement" && (n.children as Node[]).some((child) => child.type === "JSXElement" && tag(child) === "OneLineFit")) {
      const attrs = (n.openingElement as { attributes: Node[] }).attributes;
      const cls = attrs.find((a) => a.type === "JSXAttribute" && (a.name as Node & { name: string }).name === "className");
      const value = cls?.value as Node | undefined;
      const values = !value ? [] : value.type === "Literal" ? [String(value.value)] : classStrings(value.expression as Node);
      // Nút dùng chung (Button) tự nới h-auto khi chữ xuống dòng (has-[[data-fit=wrap]]), nên chỉ xét thẻ HTML thường.
      if (/^[a-z]/.test(tag(n)) && values.some((v) => FIXED_HEIGHT.test(v))) hits.push({ file, line: code.slice(0, n.start).split("\n").length, classes: values.join(" ") });
    }
    for (const key in n) if (key !== "start" && key !== "end" && key !== "type") visit(n[key]);
  };
  visit(ast);
  return hits;
}

/** Mọi khung cao cố định bọc OneLineFit trong mã giao diện. */
export function fitFrameHits(): FitFrameHit[] {
  return sourceFiles(root)
    .filter((full) => full.endsWith(".tsx") && !full.includes(".test.") && !/[\/](gallery|testing)[\/]/.test(full))
    .flatMap((full) => scanFitFrames(full.slice(root.length + 1).replaceAll("\\", "/"), readFileSync(full, "utf8")));
}

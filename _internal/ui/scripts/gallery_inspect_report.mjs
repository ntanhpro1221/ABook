import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";

export function sourceIndex(root) {
  const files = [];
  function walk(dir) {
    for (const e of readdirSync(dir, { withFileTypes: true })) {
      if (e.isDirectory()) { if (!["gallery", "__tests__"].includes(e.name)) walk(path.join(dir, e.name)); }
      else if (/\.tsx$/.test(e.name) && !/\.test\./.test(e.name)) {
        const absolute = path.join(dir, e.name);
        files.push({ file: path.relative(root, absolute).replaceAll("\\", "/"), content: readFileSync(absolute, "utf8") });
      }
    }
  }
  walk(root); return files;
}

export function inferSource(f, files) {
  for (const c of f.context ?? []) for (const [key, value] of Object.entries(c.data ?? {})) {
    if (/source|file/.test(key) && /\.tsx?(?::\d+)?$/.test(value)) return { file: value, evidence: key, confidence: "attribute" };
  }
  // SVG text is uncommon and identifies its renderer more reliably than utility classes
  // inherited from a generic button wrapper.
  if (f.context?.[0]?.tag === "text") {
    const renderers = files.filter((s) => /<text\b/.test(s.content));
    if (renderers.length === 1) {
      const s = renderers[0];
      return { file: s.file, line: s.content.slice(0, s.content.indexOf("<text")).split("\n").length, evidence: "unique SVG text renderer in source", confidence: "likely" };
    }
  }
  const tokens = [...new Set((f.context ?? []).slice(0, 4).flatMap((c) => c.classes ?? []))];
  const scores = files.map((s) => ({ ...s, score: 0, evidence: [] }));
  if (f.rule === "TOUCH TARGET") {
    const own = f.context?.[0]?.classes ?? [];
    for (let length = own.length; length >= 6; length--) {
      const sequence = own.slice(0, length).join(" ");
      const matches = scores.filter((s) => s.content.includes(sequence));
      if (matches.length === 1) { matches[0].score += 20; matches[0].evidence.push(`class sequence:${sequence}`); break; }
      if (matches.length > 1 && matches.length <= 4) {
        for (const match of matches) { match.score += 12 / matches.length; match.evidence.push(`class sequence:${sequence}`); }
        break;
      }
    }
    for (const c of (f.context ?? []).slice(1, 4)) {
      if ((c.classes?.length ?? 0) < 6) continue;
      const sequence = c.classes.join(" "), matches = scores.filter((s) => s.content.includes(sequence));
      if (matches.length && matches.length <= 4) for (const match of matches) { match.score += 6 / matches.length; match.evidence.push(`ancestor class sequence:${sequence}`); }
    }
  }
  for (const token of tokens) {
    const matches = scores.filter((s) => s.content.includes(token));
    if (!matches.length || matches.length > 12) continue;
    for (const s of matches) { s.score += 4 / matches.length; s.evidence.push(`class:${token}`); }
  }
  if (f.text.length >= 4) for (const s of scores) {
    if (s.content.includes(f.text)) { s.score += 12; s.evidence.push("literal label"); }
  }
  scores.sort((a, b) => b.score - a.score);
  const best = scores[0];
  if (!best || best.score < 2) return { file: null, evidence: "No unique source attribute/class/label", confidence: "unknown" };
  const token = best.evidence.find((e) => e.startsWith("class sequence:"))?.slice(15) ?? best.evidence.find((e) => e.startsWith("class:"))?.slice(6);
  const index = best.content.indexOf(best.evidence.includes("literal label") ? f.text : token);
  return { file: best.file, line: best.content.slice(0, index).split("\n").length, confidence: "likely", evidence: best.evidence.join(", "), alternatives: scores.slice(1, 3).filter((s) => s.score >= best.score * 0.85).map((s) => s.file) };
}

export function componentPattern(f) {
  const context = f.context ?? [];
  const opacity = context.find((c) => c.classes?.some((t) => /^opacity-\d/.test(t)));
  if (f.rule === "CONTRAST" && opacity) return `.${opacity.classes.find((t) => /^opacity-\d/.test(t))} :text`;
  const glyph = context.find((c) => c.classes?.some((t) => /^glyph(?:-20)?$/.test(t)));
  if (glyph && context[0]?.tag === "text") return ".glyph* > text";
  if (f.metric === "icon-text-overlap") return `${context[0]?.tag}.${context[0]?.classes?.find((c) => c === "vu") ?? "icon"} + label`;
  if (f.rule === "TOUCH TARGET" && context.length) return `${context[0].tag}${context[0].classes.map((t) => `.${t}`).join("")}`;
  if (context.length) return context.slice(0, 2).reverse().map((c) => `${c.tag}${(c.classes ?? []).map((t) => `.${t}`).join("")}`).join(" > ");
  return f.selector.replace(/:nth-of-type\(\d+\)/g, "").replace(/#_r_[\w]+_/g, "#react-id");
}

export function deduplicate(findings, files = []) {
  const groups = new Map();
  for (const f of findings) {
    const source = inferSource(f, files), pattern = componentPattern(f);
    const key = JSON.stringify([f.rule, pattern, source.file]);
    if (!groups.has(key)) groups.set(key, { rule: f.rule, component: source.file?.replace(/.*\//, "").replace(/\.tsx?$/, "") ?? "Unknown", pattern, source, severity: f.rule === "TEXT-OVER-TEXT" || f.rule === "CLIPPED TEXT" ? "CAO" : f.rule === "ICON SIZE MISMATCH" || f.rule === "OPTICAL SIZE CONSISTENCY" ? "THẤP" : "VỪA", count: 0, frames: new Set(), themes: new Set(), examples: [], findingIds: [] });
    const g = groups.get(key); g.count++; g.frames.add(f.story); g.themes.add(f.theme); g.findingIds.push(f.id);
    if (g.examples.length < 3) g.examples.push(f);
  }
  const order = { CAO: 0, "VỪA": 1, "THẤP": 2 };
  return [...groups.values()].sort((a, b) => order[a.severity] - order[b.severity] || b.frames.size - a.frames.size || b.count - a.count).map((g, i) => ({ ...g, id: `D${String(i + 1).padStart(3, "0")}`, frames: [...g.frames], themes: [...g.themes] }));
}

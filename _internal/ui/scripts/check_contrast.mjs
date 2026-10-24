#!/usr/bin/env node
// Kiểm độ tương phản WCAG AA của mọi token màu trong src/styles.css, cả hai giao diện và cả ba mặt đọc (Giấy / Ngà / Đêm + Tự động).
// Đọc thẳng CSS (không giữ bản sao giá trị): đổi một token là chạy lại script này (npm run contrast). Thoát khác 0 nếu có cặp trượt.
//   4,5:1  chữ thường (mực, mực phụ, chữ nhấn, chữ trạng thái, chữ trên nút)
//   3:1    icon / chữ lớn (--fg-3) và ranh giới điều khiển (viền ô nhập, rãnh công tắc tắt, vòng tiêu điểm, núm công tắc)
// Màu có alpha được chồng lên nền thật (sRGB, như trình duyệt) trước khi đo; color-mix(in oklab) tính đúng theo oklab.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const raw = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
export const css = raw.replace(/\/\*[\s\S]*?\*\//g, "");

// ---- đọc token ------------------------------------------------------------------------------------------------

export function declarations(body) {
  return Object.fromEntries([...body.matchAll(/(?:^|[;{\s])--([\w-]+)\s*:\s*([^;]+);/g)].map(([, name, value]) => [name, value.trim()]));
}
/** Gộp mọi khối CẤP CAO NHẤT (không thụt lề, không lồng trong @media) có đúng bộ chọn `selector`. */
export function blockTokens(selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`^${escaped}\\s*\\{([^}]*)\\}`, "gm");
  return Object.assign({}, ...[...css.matchAll(pattern)].map((match) => declarations(match[1])));
}

export function themeTokens(theme) {
  const light = blockTokens(":root");
  return theme === "dark" ? { ...light, ...blockTokens('[data-theme="dark"]') } : light;
}

export const SURFACES = ["auto", "paper", "ivory", "night"];
/** Token trong vùng `.reading-surface` của một giao diện + một mặt đọc ("auto" = mặt mặc định của giao diện). */
export function readerTokens(theme, surface) {
  const scoped = { ...themeTokens(theme), ...(surface === "auto" ? {} : blockTokens(`:root[data-surface="${surface}"]`)) };
  const overrides = blockTokens(".reading-surface");
  return { ...scoped, ...overrides };
}

// ---- màu --------------------------------------------------------------------------------------------------------

/** Cắt `text` theo `sep` ở cấp ngoài cùng (bỏ qua dấu trong ngoặc). */
function splitTop(text, sep) {
  const parts = [];
  let depth = 0, start = 0;
  for (let i = 0; i < text.length; i++) {
    if (text[i] === "(") depth++;
    else if (text[i] === ")") depth--;
    else if (text[i] === sep && depth === 0) { parts.push(text.slice(start, i).trim()); start = i + 1; }
  }
  parts.push(text.slice(start).trim());
  return parts;
}

const toLinear = (v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
const fromLinear = (v) => (v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055);
export function toOklab([r, g, b]) {
  const [lr, lg, lb] = [r, g, b].map((c) => toLinear(c / 255));
  const l = Math.cbrt(0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb);
  const m = Math.cbrt(0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb);
  const s = Math.cbrt(0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb);
  return [0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s, 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s, 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s];
}
export function fromOklab([L, a, b]) {
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
  const linear = [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s, -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s];
  return linear.map((v) => Math.min(255, Math.max(0, fromLinear(Math.min(1, Math.max(0, v))) * 255)));
}
/** oklch(L C H) -> sRGB, cắt ra ngoài gam (trình duyệt thu nhỏ chroma; chênh lệch nhỏ với màu đã trong gam). */
export function oklch(L, C, hue) {
  const h = (hue * Math.PI) / 180;
  return [...fromOklab([L, C * Math.cos(h), C * Math.sin(h)]), 1];
}

/** Giá trị CSS -> [r, g, b, alpha] (r,g,b 0..255). `tokens` để giải var(--x). */
export function rgba(value, tokens, seen = new Set()) {
  value = value.trim();
  const variable = value.match(/^var\(--([\w-]+)\)$/);
  if (variable) {
    const name = variable[1];
    if (seen.has(name)) throw new Error(`Vòng lặp token: ${name}`);
    if (tokens[name] === undefined) throw new Error(`Không có token --${name}`);
    return rgba(tokens[name], tokens, new Set(seen).add(name));
  }
  if (value === "transparent") return [0, 0, 0, 0];
  if (/^#[\da-f]{6}$/i.test(value)) return [...value.slice(1).match(/../g).map((v) => parseInt(v, 16)), 1];
  const rgb = value.match(/^rgb\(([^)]+)\)$/);
  if (rgb) {
    const [channels, alpha = "1"] = rgb[1].split("/");
    return [...channels.trim().split(/\s+/).map(Number), Number(alpha)];
  }
  const mix = value.match(/^color-mix\(in oklab,(.+)\)$/s);
  if (mix) {
    const parts = splitTop(mix[1], ",").map((part) => {
      const weight = part.match(/^(.*\S)\s+([\d.]+)%$/);
      return weight ? { color: rgba(weight[1], tokens, seen), weight: Number(weight[2]) / 100 } : { color: rgba(part, tokens, seen), weight: null };
    });
    const known = parts.reduce((sum, part) => sum + (part.weight ?? 0), 0);
    for (const part of parts) part.weight ??= 1 - known;
    // Nội suy có nhân alpha (premultiplied), như CSS Color 4.
    const alpha = parts.reduce((sum, part) => sum + part.weight * part.color[3], 0);
    if (alpha === 0) return [0, 0, 0, 0];
    const lab = [0, 1, 2].map((i) => parts.reduce((sum, part) => sum + part.weight * part.color[3] * toOklab(part.color)[i], 0) / alpha);
    return [...fromOklab(lab), alpha];
  }
  throw new Error(`Không đọc được màu: ${value}`);
}

/** Màu `front` (có alpha) chồng lên `back`; trả về màu có alpha gộp. */
export function over(front, back) {
  const a = front[3] + back[3] * (1 - front[3]);
  if (a === 0) return [0, 0, 0, 0];
  return [...front.slice(0, 3).map((c, i) => (c * front[3] + back[i] * back[3] * (1 - front[3])) / a), a];
}
function luminance(rgb) {
  return rgb.slice(0, 3).map((v) => toLinear(v / 255)).reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0);
}
/** Tỉ lệ tương phản WCAG của `front` (chồng lên `back` nếu có alpha) với `back`; `back` phải đặc. */
export function ratio(front, back) {
  const a = luminance(over(front, back)), b = luminance(back);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

/** Tỉ lệ % bìa pha vào --bg của .now-playing-tint, đọc từ CSS. */
export function tintWeight(theme) {
  const selector = theme === "dark" ? String.raw`\[data-theme="dark"\] \.now-playing-tint` : String.raw`^\.now-playing-tint`;
  const mix = String.raw`color-mix\(in oklab, var\(--cover-tint, var\(--bg\)\) (\d+)%`;
  const match = css.match(new RegExp(selector + String.raw`\s*\{[^}]*` + mix, "m"));
  if (!match) throw new Error("Không thấy .now-playing-tint (" + theme + ")");
  return Number(match[1]);
}

// ---- các cặp cần đạt --------------------------------------------------------------------------------------------

const BASES = ["bg", "panel", "panel-2", "bg-sunken", "hover", "nav-active"];
// Lớp *-soft nằm trên nền trang hay thẻ (không nằm trên nền hover / nav-active: trạng thái ấy thay hẳn nền, không chồng).
const TINT_HOSTS = ["bg", "panel", "bg-sunken"];
const SOFT = ["accent-soft", "success-soft", "danger-soft", "warning-soft", "info-soft"];
const TEXT_AA = 4.5, GRAPHIC = 3;

export function checkContrast() {
  const rows = [];
  /** `pairs`: [[tên, mực [r,g,b,a], nền đặc]]. `advisory`: chỉ báo, không làm trượt. */
  const addPairs = (theme, label, pairs, min, { advisory = false } = {}) => {
    const values = pairs.map(([name, fg, bg]) => [name, ratio(fg, bg)]);
    rows.push({ theme, label, values, min, advisory, pass: advisory || values.every(([, r]) => r >= min) });
  };
  /** Một mực trên nhiều nền: `backgrounds` là [[tên, màu đặc]]. */
  const add = (theme, label, fg, backgrounds, min, options) => addPairs(theme, label, backgrounds.map(([name, bg]) => [name, fg, bg]), min, options);

  for (const theme of ["light", "dark"]) {
    const t = themeTokens(theme), color = (name, tokens = t) => rgba(`var(--${name})`, tokens);
    const solid = BASES.map((name) => [name, over(color(name), over(color("bg"), [255, 255, 255, 1]))]);
    // Lớp trạng thái trong suốt (tối) hay nhạt (sáng) nằm trên mọi nền thật.
    const tinted = (soft) => solid.filter(([base]) => TINT_HOSTS.includes(base)).map(([base, bg]) => [`${soft}/${base}`, over(color(soft), bg)]);
    const allTinted = SOFT.flatMap(tinted);

    // Chữ thường.
    for (const name of ["text", "text-2", "text-3"]) add(theme, name, color(name), [...solid, ...allTinted], TEXT_AA);
    add(theme, "accent-text", color("accent-text"), [...solid, ...tinted("accent-soft")], TEXT_AA);
    for (const tone of ["success", "danger", "warning", "info"]) add(theme, tone, color(tone), [...solid, ...tinted(`${tone}-soft`)], TEXT_AA);
    // Mực trên các nút / mảng tô đặc.
    add(theme, "accent-ink trên accent", color("accent-ink"), [["accent", color("accent")], ["accent-hover", color("accent-hover")]], TEXT_AA);
    add(theme, "success-ink trên success", color("success-ink"), [["success", color("success")]], TEXT_AA);
    add(theme, "danger-ink trên danger", color("danger-ink"), [["danger", color("danger")]], TEXT_AA);
    add(theme, "bg trên text (tooltip, nút phát gọn)", color("bg"), [["text", color("text")]], TEXT_AA);

    // Icon phụ và chữ lớn.
    add(theme, "fg-3 (icon, chữ >= 18px)", color("fg-3"), solid, GRAPHIC);
    // Ranh giới điều khiển.
    const hostBases = solid.filter(([name]) => name !== "nav-active");
    add(theme, "control-line (viền nút, ô nhập)", color("control-line"), hostBases, GRAPHIC);
    add(theme, "control-line-strong", color("control-line-strong"), hostBases, GRAPHIC);
    add(theme, "switch-off (rãnh công tắc tắt)", color("switch-off"), hostBases.filter(([name]) => ["bg", "panel", "panel-2"].includes(name)), GRAPHIC);
    add(theme, "switch-on (rãnh công tắc bật)", color("switch-on"), hostBases.filter(([name]) => ["bg", "panel", "panel-2"].includes(name)), GRAPHIC);
    add(theme, "switch-thumb trên rãnh", color("switch-thumb"), [["switch-off", color("switch-off")], ["switch-on", color("switch-on")]], GRAPHIC);
    add(theme, "focus (vòng tiêu điểm, viền đang chọn)", color("focus"), [...hostBases, ...tinted("accent-soft")], GRAPHIC);
    // Thanh tiến độ: phần tô --accent trên rãnh --line là cặp cố định theo DESIGN (--accent giữ nguyên) nên chỉ báo, không làm trượt.
    add(theme, "tiến độ: accent trên rãnh line (chỉ báo)", color("accent"), [["line", over(color("line"), color("panel"))], ["bg-sunken", color("bg-sunken")]], GRAPHIC, { advisory: true });

    // Ảnh bìa có thể là màu bất kỳ: chữ / icon trắng nằm trên lớp phủ --cover-overlay đè lên bìa trắng thì xấu nhất.
    const white = [255, 255, 255, 1];
    add(theme, "cover-ink trên cover-overlay (bìa trắng)", color("cover-ink"), [["bìa trắng", over(color("cover-overlay"), white)]], TEXT_AA);

    // Mặt đọc: mỗi giao diện x (Tự động, Giấy, Ngà, Đêm), đo trong vùng .reading-surface.
    for (const surface of SURFACES) {
      const r = readerTokens(theme, surface), c = (name) => rgba(`var(--${name})`, r);
      const bg = c("read-bg"), sentence = over(c("read-along"), bg), word = over(c("read-along-word"), sentence);
      const still = [["nền", bg], ["hover", over(c("hover"), bg)], ["accent-soft", over(c("accent-soft"), bg)]];
      const label = `đọc ${surface}`;
      // Câu / chữ đang đọc luôn đặt color: var(--text) (styles.css), nên chỉ mực chính nằm trên lớp tô; mực phụ và chữ nhấn chỉ ở nền tĩnh.
      add(theme, `${label}: text`, c("text"), [...still, ["câu đang đọc", sentence], ["chữ đang đọc", word]], TEXT_AA);
      add(theme, `${label}: text-2`, c("text-2"), still, TEXT_AA);
      add(theme, `${label}: text-3`, c("text-3"), still, TEXT_AA);
      add(theme, `${label}: accent-text`, c("accent-text"), still, TEXT_AA);
      add(theme, `${label}: focus`, c("focus"), [...still, ["câu đang đọc", sentence]], GRAPHIC);
    }

    // Màn "Đang nghe": nền = bìa pha 10 % (sáng) / 16 % (tối) vào --bg; bìa là màu sRGB bất kỳ -> quét lưới 6x6x6.
    const weight = tintWeight(theme), steps = [0, 51, 102, 153, 204, 255];
    const player = steps.flatMap((red) => steps.flatMap((green) => steps.map((blue) => {
      const tint = rgba(`color-mix(in oklab, rgb(${red} ${green} ${blue}) ${weight}%, var(--bg))`, t);
      return [`bìa ${red},${green},${blue}`, tint];
    })));
    for (const name of ["text", "text-2", "text-3", "accent-text"]) add(theme, `trình phát: ${name}`, color(name), player, TEXT_AA);
    add(theme, "trình phát: focus", color("focus"), player, GRAPHIC);

    // Chữ cái đầu nhân vật: cùng độ sáng, quét mọi sắc.
    const hues = Array.from({ length: 72 }, (_, i) => i * 5);
    const avatarBg = Number(t["avatar-bg-l"]), avatarFg = Number(t["avatar-fg-l"]);
    addPairs(theme, "avatar: chữ trên nền (mọi sắc)", hues.map((hue) => [`sắc ${hue}`, oklch(avatarFg, 0.13, hue), oklch(avatarBg, 0.05, hue)]), TEXT_AA);
  }
  return rows;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const rows = checkContrast();
  const compact = process.argv.includes("--compact");
  console.log("Nền: bg · panel · panel-2 · bg-sunken · hover · nav-active; lớp *-soft chồng lên từng nền; mặt đọc đo trong .reading-surface; bìa quét lưới màu.");
  console.log("Ngưỡng: 4,5:1 chữ thường · 3:1 icon / chữ lớn / ranh giới điều khiển. 'chỉ báo' = cặp cố định theo DESIGN, không làm trượt.\n");
  console.log("| Chủ đề | Mực / ranh giới | Thấp nhất | Nền thấp nhất | Ngưỡng | Kết quả |");
  console.log("|---|---|---:|---|---:|---|");
  for (const row of rows) {
    const [bg, value] = row.values.reduce((a, b) => (a[1] < b[1] ? a : b));
    const verdict = row.advisory ? (value >= row.min ? "Đạt (chỉ báo)" : "Dưới ngưỡng (chỉ báo)") : row.pass ? "Đạt" : "KHÔNG ĐẠT";
    console.log(`| ${row.theme} | ${row.label} | ${value.toFixed(2)} | ${bg} | ${row.min.toFixed(1)} | ${verdict} |`);
    if (!compact && row.values.length <= 40) console.log(`|  |  ↳ ${row.values.map(([name, r]) => `${name} ${r.toFixed(2)}${r >= row.min ? "" : " ✗"}`).join(" · ")} |  |  |  |`);
  }
  const pairs = rows.reduce((sum, row) => sum + row.values.length, 0), failed = rows.filter((row) => !row.pass);
  console.log(`\n${rows.length} nhóm, ${pairs} cặp; ${failed.length} nhóm không đạt.`);
  for (const row of failed) {
    const bad = row.values.filter(([, r]) => r < row.min).map(([name, r]) => `${name} ${r.toFixed(2)}`);
    console.log(`  KHÔNG ĐẠT ${row.theme} · ${row.label} (cần ${row.min}): ${bad.slice(0, 8).join(", ")}${bad.length > 8 ? ` … +${bad.length - 8}` : ""}`);
  }
  if (failed.length) process.exitCode = 1;
}

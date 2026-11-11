import { formatDecimal } from "./number";
import { S } from "./strings.generated";

// Bộ chọn giá trị số - phần tính toán. MỘT hợp đồng cho ba nền (tests/fixtures/value_picker/cases.json): Android ValuePickerLogic.kt,
// Qt ValuePickerLogic.js. Luật DESIGN mục 6 "Chọn giá trị": mọi giá trị số = chip tiêu biểu + chọn tự do (kéo thước, -/+ một bước, gõ số).

/** Miền của một giá trị: biên, bước, các giá trị tiêu biểu (chip một chạm, nấc hút khi kéo) và thang của thước (mốc [vị trí 0..1, giá trị]). */
export interface ValueSpec {
  min: number;
  max: number;
  step: number;
  typical: readonly number[];
  scale?: readonly (readonly [number, number])[];
}

/** Nấc hút: giá trị tiêu biểu "rộng" thêm chừng này bước khi kéo - đủ để dừng đúng nấc mà không nuốt bước kề. */
export const SNAP_STEPS = 0.75;
/** PageUp / PageDown đổi chừng này bước. */
export const PAGE_STEPS = 10;

export const VALUE_SPECS = {
  sleepMinutes: { min: 1, max: 240, step: 1, typical: [5, 15, 30, 45, 60, 90] },
  sleepChapters: { min: 1, max: 10, step: 1, typical: [1, 2, 3] },
  speed: { min: 0.5, max: 3, step: 0.05, typical: [0.8, 1, 1.25, 1.5, 2], scale: [[0, 0.5], [0.12, 0.8], [0.3, 1], [0.48, 1.25], [0.66, 1.5], [0.84, 2], [1, 3]] },
  readSize: { min: 12, max: 40, step: 1, typical: [16, 18, 20, 22, 24] },
  readLeading: { min: 1.2, max: 2.4, step: 0.05, typical: [1.5, 1.7, 1.9] },
  sleepFadeSeconds: { min: 5, max: 120, step: 5, typical: [10, 30, 60] },
  sleepExtendMinutes: { min: 1, max: 60, step: 1, typical: [5, 10, 15, 30] },
  scheduleMinutes: { min: 5, max: 240, step: 5, typical: [15, 30, 45, 60, 90] },
  voice: { min: 0, max: 200, step: 5, typical: [50, 100, 150, 200] },
  pitch: { min: -6, max: 6, step: 0.5, typical: [-2, 0, 2] },
  balance: { min: -100, max: 100, step: 1, typical: [-50, 0, 50] },
  silenceDb: { min: -80, max: -45, step: 1, typical: [-70, -60, -50] },
  silenceSeconds: { min: 2, max: 10, step: 0.5, typical: [3, 5] },
  keepSeconds: { min: 1.5, max: 3, step: 0.1, typical: [1.5, 2] },
} as const satisfies Record<string, ValueSpec>;

export function decimalsOf(step: number): number {
  const text = String(step);
  const dot = text.indexOf(".");
  return dot < 0 ? 0 : text.length - dot - 1;
}

function roundTo(value: number, decimals: number): number {
  const factor = 10 ** decimals;
  const result = Math.round(value * factor) / factor;
  return Object.is(result, -0) ? 0 : result;
}

/** Kẹp vào biên rồi về lưới min + n*step. */
export function quantize(spec: ValueSpec, value: number): number {
  const decimals = Math.max(decimalsOf(spec.step), decimalsOf(spec.min));
  const clamped = Math.min(spec.max, Math.max(spec.min, value));
  let result = roundTo(spec.min + Math.round((clamped - spec.min) / spec.step) * spec.step, decimals);
  if (result > spec.max) result = roundTo(result - spec.step, decimals);
  return result;
}

export function clampValue(spec: ValueSpec, value: number): { value: number; clamped: boolean } {
  return { value: quantize(spec, value), clamped: value < spec.min || value > spec.max };
}

export function stepValue(spec: ValueSpec, value: number, steps: number): number {
  return quantize(spec, quantize(spec, value) + steps * spec.step);
}

function scaleOf(spec: ValueSpec): readonly (readonly [number, number])[] {
  const crowded = spec.typical.some((v, i) => i > 0 && (v - spec.typical[i - 1]) / (spec.max - spec.min) < 0.12);
  if (!spec.scale && (spec.min > 0 && spec.max / spec.min >= 8 || crowded) && spec.typical.length > 1) {
    const inner = spec.typical.filter(v => v > spec.min && v < spec.max);
    const first = spec.typical[0] === spec.min ? 0.9 / inner.length : 0.1;
    return [[0, spec.min], ...inner.map((v, i): [number, number] => [first + (0.9 - first) * i / Math.max(1, inner.length - 1), v]), [1, spec.max]];
  }
  return spec.scale ?? [[0, spec.min], [1, spec.max]];
}

/** Balance consecutive rows instead of leaving an orphan at the end. */
export function chipRows(widths: readonly number[], available: number, gap: number): number[][] {
  for (let rows = 1; rows <= widths.length; rows++) {
    let start = 0;
    const groups = Array.from({length: rows}, (_, row) => Array.from({length: Math.floor(widths.length / rows) + (row < widths.length % rows ? 1 : 0)}, () => start++));
    if (groups.every(group => group.reduce((sum, i) => sum + widths[i], 0) + gap * (group.length - 1) <= available)) return groups;
  }
  return widths.map((_, i) => [i]);
}

/** Where the ruler's track starts (px from each end) and whether the labels sit under their detents. */
export type TickLabels = { inset: number; aligned: boolean };

/**
 * Labels under the ruler are captions of its detents: label i is centred on detent i, so the track inset grows until
 * every label stays inside the ruler (never under the -/+ buttons). `aligned` false = the labels cannot sit under their
 * detents without touching (`gap`) - then the ruler draws no detents and the labels fall back to rows.
 */
export function tickLabels(fractions: readonly number[], widths: readonly number[], total: number, minInset: number, gap: number): TickLabels {
  const EPSILON = 1e-6;
  let inset = minInset;
  fractions.forEach((f, i) => {
    const half = widths[i] / 2;
    if (f < 0.5) inset = Math.max(inset, (half - f * total) / (1 - 2 * f));
    if (f > 0.5) inset = Math.max(inset, (half - (1 - f) * total) / (2 * f - 1));
  });
  const width = total - 2 * inset;
  const centres = fractions.map(f => inset + f * width);
  const inside = centres.every((c, i) => c - widths[i] / 2 >= -EPSILON && c + widths[i] / 2 <= total + EPSILON);
  const apart = centres.every((c, i) => i === 0 || c - centres[i - 1] + EPSILON >= (widths[i] + widths[i - 1]) / 2 + gap);
  return { inset, aligned: width > 0 && inside && apart };
}

/** Giá trị thô (chưa về lưới) ở vị trí `fraction` của thước. */
export function rawAt(spec: ValueSpec, fraction: number): number {
  const scale = scaleOf(spec);
  const f = Math.min(1, Math.max(0, fraction));
  for (let i = 1; i < scale.length; i++) {
    const [f0, v0] = scale[i - 1];
    const [f1, v1] = scale[i];
    if (f <= f1 || i === scale.length - 1) return v0 + ((f - f0) / (f1 - f0)) * (v1 - v0);
  }
  return spec.max;
}

/** Giá trị khi kéo tới `fraction`: hút về giá trị tiêu biểu gần (nấc), không thì về lưới. */
export function fromFraction(spec: ValueSpec, fraction: number): number {
  const raw = rawAt(spec, fraction);
  let nearest: number | null = null;
  for (const typical of spec.typical) if (nearest === null || Math.abs(typical - raw) < Math.abs(nearest - raw)) nearest = typical;
  if (nearest !== null && Math.abs(nearest - raw) <= SNAP_STEPS * spec.step) return nearest;
  return quantize(spec, raw);
}

/** Vị trí 0..1 của `value` trên thước. */
export function toFraction(spec: ValueSpec, value: number): number {
  const scale = scaleOf(spec);
  const v = Math.min(spec.max, Math.max(spec.min, value));
  for (let i = 1; i < scale.length; i++) {
    const [f0, v0] = scale[i - 1];
    const [f1, v1] = scale[i];
    if (v <= v1 || i === scale.length - 1) return f0 + ((v - v0) / (v1 - v0)) * (f1 - f0);
  }
  return 1;
}

/** Chữ người gõ: null khi không ra số (giữ giá trị cũ). */
export function parseValue(spec: ValueSpec, text: string): { value: number; clamped: boolean } | null {
  const cleaned = text.replace(/[^0-9,.-]/g, "").replace(/,/g, ".");
  if (!cleaned) return null;
  const parsed = Number(cleaned);
  if (!Number.isFinite(parsed)) return null;
  return clampValue(spec, parsed);
}

export function chipIndex(spec: ValueSpec, value: number): number {
  return spec.typical.findIndex((typical) => Math.abs(typical - value) < spec.step / 2);
}

/** Rung / tiếng nấc: vừa tới một giá trị tiêu biểu. */
export function isDetent(spec: ValueSpec, previous: number, next: number): boolean {
  return next !== previous && chipIndex(spec, next) >= 0;
}

/** Số kiểu Việt: "1,35", "1,5", "1". */
export function formatNumber(spec: ValueSpec, value: number): string {
  return formatDecimal(roundTo(value, decimalsOf(spec.step)), decimalsOf(spec.step));
}

/** Số giây kiểu người đọc: "45 giây", tròn phút thì "1 phút", "2 phút". */
export function secondsLabel(seconds: number): string {
  return seconds >= 60 && seconds % 60 === 0 ? S.s_0_phut_2596d212(seconds / 60) : S.s_0_giay_daac30d3(seconds);
}

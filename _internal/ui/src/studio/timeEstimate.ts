import { formatLength } from "@/shared/format";
import type { StudioGpu } from "./studioFit";

/**
 * Thời gian làm sách ước từ số đo của MỘT máy (soát a92 T2): hai lô gần nhất của cuốn 2 (26-09, mức Chất lượng cao) trên máy dev - lô 18
 * có 113 nghìn chữ, phân tích ~4 giờ, thu âm 4,6-7,1 giờ. Chưa có số đo nào của máy đang dùng (app không lưu tốc độ các lô trước), nên
 * chỉ khi card và model phân tích khớp máy đã đo mới nói số ấy; máy khác chỉ cho khoảng rộng, nhãn luôn nói đó là số tham khảo.
 * Hai mức Nhanh / Cân bằng chưa đo ở đâu cả nên không đoán con số.
 */
export const MEASURED_ON = "RTX 5060 Laptop 8 GB";
const MEASURED = { analysisPerKiloword: 2.1 * 60, synthesisPerKiloword: [2.5 * 60, 3.8 * 60] as const };
// Máy khác nhanh hay chậm hơn bao nhiêu thì chưa ai đo: khoảng rộng là phán đoán (card yếu hơn mất gấp vài lần, card mạnh hơn bớt đáng kể), không phải số đo.
const WIDER = { low: 0.6, high: 3 };

/** Card của máy cùng loại card đã đo, và đang dùng model phân tích mặc định (số đo là của model ấy). */
export function matchesMeasured(gpu: StudioGpu | null, analysisModel: string): boolean {
  return !analysisModel && Boolean(gpu && /RTX\s*5060/i.test(gpu.name));
}

export function estimate(words: number, chapters: number, exact: boolean) {
  const kilo = words / 1000;
  const analysis = kilo * MEASURED.analysisPerKiloword;
  const [low, high] = MEASURED.synthesisPerKiloword.map((seconds) => kilo * seconds);
  const scale = exact ? { low: 1, high: 1 } : WIDER;
  return {
    analysis,
    analysisLow: analysis * scale.low,
    analysisHigh: analysis * scale.high,
    totalLow: (analysis + low) * scale.low,
    totalHigh: (analysis + high) * scale.high,
    firstChapter: (analysis + high / Math.max(1, chapters)) * scale.high,
  };
}

/** Nói số này từ đâu ra - đứng cạnh mọi con số thời gian. */
export function timeBasis(exact: boolean): string {
  return exact
    ? `Số tham khảo, đo trên máy cùng card ${MEASURED_ON}`
    : `Số tham khảo, đo trên máy ${MEASURED_ON}; máy của bạn có thể nhanh hơn hay chậm hơn nên đây là khoảng rộng`;
}

export function lengthRange(low: number, high: number): string {
  const a = formatLength(low);
  const b = formatLength(high);
  return a === b ? `khoảng ${a}` : `${a} - ${b}`;
}

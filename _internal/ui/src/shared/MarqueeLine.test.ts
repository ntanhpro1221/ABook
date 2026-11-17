import { expect, it } from "vitest";
import { marqueeFit, marqueeLoop } from "./MarqueeLine";
import { ONE_LINE_MIN_SCALE, TIMING } from "./widthClass.generated";

// Chữ rộng tỉ lệ với cỡ: 10 px chữ mỗi 1 px cỡ
const measure = (size: number) => size * 10;

it("vừa ở cỡ gốc thì giữ cỡ gốc; không vừa thì thu cỡ; thu tới đáy vẫn không vừa thì chạy chữ ở cỡ đáy", () => {
  expect(marqueeFit(200, 16, measure)).toEqual({ fit: "one", size: 16 });
  expect(marqueeFit(140, 16, measure)).toEqual({ fit: "shrunk", size: 14 });
  expect(marqueeFit(100, 16, measure)).toEqual({ fit: "scroll", size: 16 * ONE_LINE_MIN_SCALE });
  expect(marqueeFit(0, 16, measure).fit).toBe("unmeasured");
});

it("measures the exact floor between half-pixel steps", () => {
  const base = 15.6;
  const min = base * ONE_LINE_MIN_SCALE;
  const width = (size: number) => size <= min ? 117 : 118;
  expect(marqueeFit(117, base, width)).toEqual({ fit: "shrunk", size: min });
  expect(marqueeFit(116, base, width)).toEqual({ fit: "scroll", size: min });
});

it("chạy chữ đứng ở đầu một nhịp rồi trượt đều hết một chu kỳ (bản chép thứ hai về chỗ bản đầu)", () => {
  const cycle = 300;
  const { keyframes, duration } = marqueeLoop(cycle);
  expect(duration).toBe(TIMING.marqueeDelayMs + (cycle / TIMING.marqueeSpeed) * 1000);
  expect(keyframes.map((frame) => frame.transform)).toEqual(["translateX(0)", "translateX(0)", "translateX(-300px)"]);
  expect(keyframes[1].offset).toBeCloseTo(TIMING.marqueeDelayMs / duration);
});

import { expect, it } from "vitest";
import { toastBaseBounds } from "./toastClearance";

it("keeps the same clearance target across recorded frames of a half-pixel toast", () => {
  // Native 400px add-book-3 trace: the stationary menu ends at 760px.
  // Serialized translate and raster bounds straddle the 750.5px layout origin.
  const frames = [
    [776.1537475585938, 829.6537475585938, 25.6538],
    [776.1806030273438, 829.6806030273438, 25.6806],
    [775.709228515625, 829.209228515625, 25.2093],
    [776.1533203125, 829.6533203125, 25.6533],
    [776.10107421875, 829.60107421875, 25.6011],
  ];
  for (const [top, bottom, translate] of frames) {
    const base = toastBaseBounds(top, bottom, translate);
    expect(base).toEqual({ top: 750.5, bottom: 804 });
    expect(Math.round(760 + 16 - base.top)).toBe(26);
  }
});

it("retains layout subpixels rather than rounding the toast height to whole pixels", () => {
  expect(toastBaseBounds(100.015625, 153.53125, 0)).toEqual({ top: 100.015625, bottom: 153.53125 });
});

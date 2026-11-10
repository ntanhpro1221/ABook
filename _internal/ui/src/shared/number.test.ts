import { expect, it } from "vitest";
import { formatBalance, formatDecimal } from "./number";

it("renders Vietnamese decimals and directional balance", () => {
  expect([0, -0, 0.5, -2.5, 1.35].map(v => formatDecimal(v))).toEqual(["0", "0", "0,5", "-2,5", "1,35"]);
  expect([-30, 0, 30].map(formatBalance)).toEqual(["Trái 30 %", "Giữa", "Phải 30 %"]);
  expect(formatDecimal(1, 1, true)).toBe("1,0");
});

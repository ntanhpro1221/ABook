import { S } from "./strings.generated";

/** The single decimal formatter for visible Vietnamese numbers. */
export function formatDecimal(value: number, digits = 2, fixed = false): string {
  let text = (Object.is(value, -0) ? 0 : value).toFixed(digits);
  if (Number(text) === 0) text = (0).toFixed(digits);
  if (!fixed && text.includes(".")) text = text.replace(/0+$/, "").replace(/\.$/, "");
  return text.replace(".", ",");
}

export function formatBalance(percent: number): string {
  return percent === 0 ? S.s_value_middle : percent < 0 ? S.s_value_left(formatDecimal(-percent, 0)) : S.s_value_right(formatDecimal(percent, 0));
}

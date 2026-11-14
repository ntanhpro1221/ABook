import { renderToString } from "react-dom/server";
import { afterEach, expect, it } from "vitest";
import { FoldRows } from "./FoldRows";

afterEach(() => { delete (globalThis as unknown as Record<string, unknown>).IntersectionObserver; });

it.each([40, 200])("bounds initial disclosure work for %i children", (count) => {
  (globalThis as unknown as Record<string, unknown>).IntersectionObserver = class {};
  let built = 0;
  const html = renderToString(<FoldRows items={Array.from({ length: count }, (_, i) => i)} keyOf={String}>
    {(item) => { built++; return <p data-person={item}>Person {item}</p>; }}
  </FoldRows>);
  expect(built).toBe(6);
  expect(html).toContain('data-person="0"');
  expect(html).not.toContain('data-person="39"');
  expect(html).toContain('data-block="1"');
});

it("keeps a complete accessible list when observation is unavailable", () => {
  let built = 0;
  renderToString(<FoldRows items={Array.from({ length: 40 }, (_, i) => i)} keyOf={String}>
    {(item) => { built++; return <p>{item}</p>; }}
  </FoldRows>);
  expect(built).toBe(40);
});

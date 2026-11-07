// @vitest-environment happy-dom
import { afterEach, expect, it, vi } from "vitest";
import { morphPlayerMode } from "./playerModeMorph";

afterEach(() => { document.body.replaceChildren(); vi.restoreAllMocks(); });

it.each([false, true])("mode switch moves the cover and titles without animating transport (reading=%s)", reading => {
  vi.spyOn(window, "matchMedia").mockReturnValue({ matches: false } as MediaQueryList);
  const animate = vi.spyOn(HTMLElement.prototype, "animate").mockReturnValue({} as Animation);
  document.body.innerHTML = '<section><div data-np-stage><div data-np="cover"></div><div data-np="chapter"></div><div data-np="book"></div></div><div data-transport></div></section>';
  const screen = document.body.firstElementChild as HTMLElement;
  let changed = false;
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    const small = changed === !reading;
    const size = small ? 48 : 240, x = small ? 20 : 60, y = small ? 40 : 160;
    return { left: x, top: y, x, y, width: size, height: size, right: x + size, bottom: y + size, toJSON() {} };
  });
  morphPlayerMode(screen, () => { changed = true; });
  expect(changed).toBe(true);
  expect(animate).toHaveBeenCalledTimes(3);
  for (const [i, args] of animate.mock.calls.entries()) {
    expect((args[0] as Keyframe[])[0].transform).not.toBe("none");
    expect((args[0] as Keyframe[]).at(-1)?.transform).toBe("none");
    expect(animate.mock.instances[i]).not.toBe(screen.querySelector("[data-transport]"));
  }
});

it("reduced motion applies the state without creating geometry", () => {
  vi.spyOn(window, "matchMedia").mockReturnValue({ matches: true } as MediaQueryList);
  const animate = vi.spyOn(HTMLElement.prototype, "animate");
  document.body.innerHTML = '<section><div data-np-stage></div></section>';
  const update = vi.fn(); morphPlayerMode(document.body.firstElementChild as HTMLElement, update);
  expect(update).toHaveBeenCalledOnce(); expect(animate).not.toHaveBeenCalled();
});

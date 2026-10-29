// @vitest-environment happy-dom
import { renderToString } from "react-dom/server";
import { afterEach, expect, it, vi } from "vitest";

const h = vi.hoisted(() => ({ phones: [] as any[], effects: [] as (() => (() => void) | undefined)[] }));
vi.mock("react", async original => ({ ...await original<typeof import("react")>(), useLayoutEffect: (run: () => (() => void) | undefined) => h.effects.push(run) }));
vi.mock("@tanstack/react-query", async original => ({ ...await original<typeof import("@tanstack/react-query")>(),
  useQuery: () => ({ data: { phones: h.phones, receivedAt: 0 } }), useQueryClient: () => ({}) }));
import { RemoteBars } from "./RemotePhone";

function mount(bars: number) {
  h.phones = Array.from({ length: bars }, (_, device) => ({ device: String(device), bookId: "sách", chapterId: 1 }));
  h.effects = [];
  function Probe() { RemoteBars(); return null; }
  renderToString(<Probe />);
  expect(h.effects).toHaveLength(1);
  return h.effects[0]();
}
afterEach(() => { document.body.replaceChildren(); vi.restoreAllMocks(); });
it("số thanh đổi thì thông báo lên đúng mép, hết thanh / rời màn thì trả vị trí mặc định", async () => {
  document.body.innerHTML = '<ol data-sonner-toaster></ol>';
  const el = document.querySelector<HTMLElement>("[data-sonner-toaster]")!, root = vi.spyOn(document.documentElement.style, "setProperty");
  let cleanup = mount(2); expect(el.style.getPropertyValue("--toast-bottom")).toBe("210px"); cleanup?.();
  cleanup = mount(1); expect(el.style.getPropertyValue("--toast-bottom")).toBe("153px");
  const late = el.cloneNode() as HTMLElement; late.style.removeProperty("--toast-bottom"); document.body.append(late);
  await new Promise(resolve => setTimeout(resolve, 0)); expect(late.style.getPropertyValue("--toast-bottom")).toBe("153px");
  cleanup?.(); expect(el.style.getPropertyValue("--toast-bottom")).toBe(""); expect(late.style.getPropertyValue("--toast-bottom")).toBe("");
  cleanup = mount(0); expect(cleanup).toBeUndefined(); expect(el.style.getPropertyValue("--toast-bottom")).toBe("");
  expect(root).not.toHaveBeenCalled();
});

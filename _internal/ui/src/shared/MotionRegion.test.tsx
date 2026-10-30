import { afterEach, expect, it, vi } from "vitest";
import { MotionRegion, contentSignature } from "./MotionRegion";
import { captureMotionSnapshot } from "./motion";
import { TickingValue } from "./TickingValue";
import { LiveText } from "./ui";

vi.mock("./motion", async (original) => ({
  ...await original<typeof import("./motion")>(),
  captureMotionSnapshot: vi.fn(() => ({ remove: vi.fn() })),
  viewTransitionRunning: () => false,
  prefersReducedMotion: () => false,
}));
afterEach(() => vi.clearAllMocks());

it("live units and countdown words do not trigger snapshots, even after component minification", () => {
  const originalName = TickingValue.name;
  Object.defineProperty(TickingValue, "name", { value: "a", configurable: true });
  try {
    const before = { children: <TickingValue>1 giờ</TickingValue> };
    const after = { children: <TickingValue>59 phút</TickingValue> };
    expect(contentSignature(before.children)).toBe(contentSignature(after.children));
    const region = new MotionRegion(after);
    region.box.current = { ownerDocument: { activeElement: null } } as unknown as HTMLElement;
    expect(region.getSnapshotBeforeUpdate(before)).toBeNull();
    expect(captureMotionSnapshot).not.toHaveBeenCalled();
    expect(contentSignature(<LiveText shown="Đã tải 1 MB" spoken="một phần" />))
      .toBe(contentSignature(<LiveText shown="Đã tải 2 GB" spoken="nửa phần" />));
  } finally {
    Object.defineProperty(TickingValue, "name", { value: originalName, configurable: true });
  }
});

it("đồng hồ, phần trăm, giá trị nhập và callback mới không đổi dấu nội dung", () => {
  const before = <div><span>01:02 · 12%</span><input value="a" onChange={() => {}} /></div>;
  const after = <div><span>01:03 · 13%</span><input value="ab" onChange={() => {}} /></div>;
  expect(contentSignature(before)).toBe(contentSignature(after));
});

it("pha, icon, hàng theo key và bước xác nhận vẫn đổi dấu; vùng con tự chuyển cảnh", () => {
  expect(contentSignature(<p>Đang tải</p>)).not.toBe(contentSignature(<p>Đã tải</p>));
  expect(contentSignature(<li key="A">Câu</li>)).not.toBe(contentSignature(<li key="B">Câu</li>));
  expect(contentSignature(<MotionRegion><p>Đang tải</p></MotionRegion>)).toBe(contentSignature(<MotionRegion><p>Đã tải</p></MotionRegion>));
});

it("poll không đổi nội dung thì không clone DOM; đổi pha chụp trước commit và huỷ khi unmount", () => {
  const before = { children: <span>Đang tải · 12%</span> };
  const region = new MotionRegion({ children: <span>Đang tải · 13%</span> });
  const box = { ownerDocument: { activeElement: null }, contains: () => false, closest: () => null, getBoundingClientRect: () => ({ height: 40 }), animate: vi.fn(), matches: () => false, hasAttribute: () => false, getAttribute: () => null, tagName: "DIV", childNodes: [], children: [], textContent: "Đã tải" };
  region.box.current = box as unknown as HTMLElement;
  expect(region.getSnapshotBeforeUpdate(before)).toBeNull();
  expect(captureMotionSnapshot).not.toHaveBeenCalled();
  const changed = new MotionRegion({ children: <span>Đã tải</span> });
  changed.box.current = box as unknown as HTMLElement;
  const snapshot = changed.getSnapshotBeforeUpdate(before);
  expect(captureMotionSnapshot).toHaveBeenCalledOnce();
  // Nội dung mới đã commit, ảnh cũ được giữ đủ một fade rồi cleanup.
  changed.componentDidUpdate(before, null, { ...snapshot!, signature: "old" });
  expect(box.animate).toHaveBeenCalledOnce();
  changed.componentWillUnmount();
  expect(snapshot?.clone?.remove).toHaveBeenCalled();
});

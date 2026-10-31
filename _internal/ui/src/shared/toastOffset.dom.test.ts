// @vitest-environment happy-dom
import { afterEach, expect, it, vi } from "vitest";
import { toastOffset } from "./toast";

afterEach(() => { document.body.replaceChildren(); vi.restoreAllMocks(); });
const region = () => { const el = document.createElement("ol"); el.dataset.sonnerToaster = ""; document.body.append(el); return el; };
const mutations = () => new Promise(resolve => setTimeout(resolve, 0));

it("hai mép chỉ đổi vùng thông báo và dọn độc lập", () => {
  const el = region(), root = vi.spyOn(document.documentElement.style, "setProperty");
  const top = toastOffset("top"), bottom = toastOffset("bottom");
  top.set("64px"); bottom.set("210px");
  expect(el.style.getPropertyValue("--toast-top")).toBe("64px");
  expect(el.style.getPropertyValue("--toast-bottom")).toBe("210px");
  expect(root).not.toHaveBeenCalled();
  top.dispose(); expect(el.style.getPropertyValue("--toast-top")).toBe("");
  expect(el.style.getPropertyValue("--toast-bottom")).toBe("210px");
  bottom.dispose(); expect(el.style.getPropertyValue("--toast-bottom")).toBe("");
});
it("vùng thêm muộn, vùng thay thế và vùng lồng đều nhận vị trí mới nhất", async () => {
  const offset = toastOffset("bottom"); offset.set("153px");
  const old = region(); await mutations(); expect(old.style.getPropertyValue("--toast-bottom")).toBe("153px");
  old.remove(); offset.set("210px");
  const wrapper = document.createElement("section"); wrapper.innerHTML = '<ol data-sonner-toaster></ol>'; document.body.append(wrapper);
  await mutations(); const el = wrapper.firstElementChild as HTMLElement;
  expect(el.style.getPropertyValue("--toast-bottom")).toBe("210px");
  offset.dispose(); expect(old.style.getPropertyValue("--toast-bottom")).toBe(""); expect(el.style.getPropertyValue("--toast-bottom")).toBe("");
  const late = region(); await mutations(); expect(late.style.getPropertyValue("--toast-bottom")).toBe("");
});
it("vị trí không đổi không ghi lại style", () => {
  const el = region(), write = vi.spyOn(el.style, "setProperty"), offset = toastOffset("top");
  offset.set("64px"); offset.set("64px"); offset.set("72px");
  expect(write).toHaveBeenCalledTimes(2); offset.dispose();
});

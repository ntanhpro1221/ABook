// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it } from "vitest";
import { installKeepDots } from "./DotJoin";

// Dấu "·" giữa hai khoảng trắng không được đứng đầu hay cuối dòng (LINE BREAK): installKeepDots đổi hai khoảng trắng ấy thành khoảng
// không ngắt ở mọi nút chữ, kể cả chữ React đổi sau và chữ trong cổng (hộp thoại, thông báo), trừ chữ của sách ở mặt đọc.

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));
let uninstall = () => {};
afterEach(() => { uninstall(); document.body.innerHTML = ""; });

it("glues the spaces around a middle dot in text already on the page and in text added later", async () => {
  document.body.innerHTML = `<p id="old">Thành Phố Sương Mù · Tập 2</p>`;
  uninstall = installKeepDots();
  expect(document.getElementById("old")!.textContent).toBe("Thành Phố Sương Mù\u00a0·\u00a0Tập 2");
  const portal = document.createElement("div");
  portal.innerHTML = `<span>Tác giả\u00a0· 12 chương</span>`;
  document.body.append(portal);
  await flush();
  expect(portal.textContent).toBe("Tác giả\u00a0·\u00a012 chương");
});

it("follows React when it rewrites the text of a node it already rendered", async () => {
  uninstall = installKeepDots();
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  await act(async () => root.render(<span>{"Chương 1"}</span>));
  await act(async () => root.render(<span>{"Chương 2 · Đồi gió"}</span>));
  await flush();
  expect(host.textContent).toBe("Chương 2\u00a0·\u00a0Đồi gió");
  await act(async () => root.render(<span>{"Chương 3 · Mưa"}</span>));
  await flush();
  expect(host.textContent).toBe("Chương 3\u00a0·\u00a0Mưa");
  act(() => root.unmount());
});

it("leaves the book text on the reading surface, form fields and dots that are not separators alone", async () => {
  uninstall = installKeepDots();
  const html = `<div class="reading-surface"><p>Anh ấy nói · rồi đi</p></div><textarea>A · B</textarea><p id="word">A·B · · ·</p>`;
  document.body.insertAdjacentHTML("beforeend", html);
  await flush();
  expect(document.querySelector(".reading-surface")!.textContent).toBe("Anh ấy nói · rồi đi");
  expect(document.querySelector("textarea")!.value).toBe("A · B");
  expect(document.getElementById("word")!.textContent).toBe("A·B\u00a0·\u00a0·\u00a0·");
});

it("stops after uninstall", async () => {
  uninstall = installKeepDots();
  uninstall();
  const late = document.createElement("p");
  late.textContent = "A · B";
  document.body.append(late);
  await flush();
  expect(late.textContent).toBe("A · B");
});

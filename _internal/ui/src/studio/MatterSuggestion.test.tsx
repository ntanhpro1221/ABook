import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import type { ScannedFile } from "./api";
import { MatterSuggestion } from "./MatterSuggestion";

// Soát a98 F1: Studio cho bạn bỏ / giữ thật các trang phụ của file sách (bìa, bản quyền, mục lục) - không tích sẵn.

const row = (path: string, matter?: string): ScannedFile =>
  ({ path, name: path, title: path, firstLine: `Dòng đầu ${path}`, words: 5, audioSeconds: 1, chars: 20, bytes: 30, ...(matter ? { matter } : {}) }) as ScannedFile;

it("shows nothing for a book with no front matter", () => {
  expect(renderToStaticMarkup(<MatterSuggestion files={[row("1.txt"), row("2.txt")]} keep={[]} onKeep={() => undefined} />)).toBe("");
});

it("lists each front-matter page with its reason and a checkbox that is off until ticked", () => {
  const files = [row("0001.txt", "Trang bìa"), row("0002.txt", "Mục lục"), row("0003.txt")];
  const html = renderToStaticMarkup(<MatterSuggestion files={files} keep={["0002.txt"]} onKeep={() => undefined} />);
  expect(html).toContain("2 trang phụ chưa chọn");
  expect(html).toContain("Trang bìa");
  expect(html).toContain("Mục lục");
  expect(html).not.toContain("0003.txt");
  const boxes = [...html.matchAll(/<input[^>]*type="checkbox"[^>]*>/g)].map((match) => /checked=""/.test(match[0]));
  expect(boxes).toEqual([false, true]);
});

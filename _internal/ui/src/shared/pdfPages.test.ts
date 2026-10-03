// @vitest-environment node
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import { describe, expect, it } from "vitest";
import { pdfPages, words } from "@/shared/pdfPages";

// Bộ ví dụ DÙNG CHUNG với pytest (tests/import_fixtures.py) và test JVM (BookImportTest.kt): pdf.js phải ra đúng các dòng mà pypdf
// ra, vì lớp luật phía sau (Python, Kotlin) đọc các dòng ấy.
const FIXTURES = new URL("../../../tests/fixtures/import/", import.meta.url);
const workerSrc = pathToFileURL(createRequire(import.meta.url).resolve("pdfjs-dist/legacy/build/pdf.worker.min.mjs")).href;
const read = (name: string) => readFileSync(new URL(name, FIXTURES));

describe("pdfPages", () => {
  it("reads the same lines per page as pypdf on the shared sample", async () => {
    const expected = JSON.parse(read("pages/story.pages.json").toString("utf-8")) as { title: string; author: string; pages: string[][] };
    const result = await pdfPages(read("story.pdf"), workerSrc);
    expect(result.pages).toEqual(expected.pages);
    expect(result.title).toBe(expected.title);
    expect(result.author).toBe(expected.author);
  });

  it("finds no text in a scanned PDF (the Kotlin and Python rules then say it needs OCR)", async () => {
    const result = await pdfPages(read("scan.pdf"), workerSrc);
    expect(result.pages).toHaveLength(3);
    expect(result.pages.flat()).toEqual([]);
  });

  it("rejects a file that is not a PDF", async () => {
    await expect(pdfPages(new TextEncoder().encode("not a pdf"), workerSrc)).rejects.toThrow("PDF");
  });

  it("collapses whitespace like Python str.split", () => {
    expect(words("  a  b\t　c  ")).toBe("a b c");
    expect(words("x­y")).toBe("x­y");
  });
});

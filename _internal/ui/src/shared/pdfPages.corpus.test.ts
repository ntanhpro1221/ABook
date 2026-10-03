// @vitest-environment node
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { basename, delimiter, join } from "node:path";
import { pathToFileURL } from "node:url";
import { describe, expect, it } from "vitest";
import { pdfPages } from "@/shared/pdfPages";

// Chỉ chạy trên máy có file PDF thật (không bao giờ có trong repo): ghi các dòng pdf.js lấy được của từng file ra
// `ABOOK_IMPORT_DUMP/<tên file>.pages.json` để so với pypdf (`importers.pdf_pages`) trên cùng file. `ABOOK_PDF_CORPUS` = các file PDF
// cách nhau bằng dấu phân cách đường dẫn của máy; thiếu thì bỏ qua.
const corpus = (process.env.ABOOK_PDF_CORPUS ?? "").split(delimiter).filter(Boolean);
const out = process.env.ABOOK_IMPORT_DUMP ?? "";
const workerSrc = pathToFileURL(createRequire(import.meta.url).resolve("pdfjs-dist/legacy/build/pdf.worker.min.mjs")).href;

describe("pdfPages on local PDFs", () => {
  it.skipIf(!corpus.length || !out)("dumps the lines of every PDF for the pypdf diff", async () => {
    mkdirSync(out, { recursive: true });
    for (const file of corpus) {
      const result = await pdfPages(readFileSync(file), workerSrc);
      writeFileSync(join(out, `${basename(file)}.pages.json`), JSON.stringify(result, null, 1));
      expect(result.pages.length).toBeGreaterThan(0);
    }
  }, 600_000);
});

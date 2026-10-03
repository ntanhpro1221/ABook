import { beforeEach, describe, expect, it, vi } from "vitest";

// Cầu WebView → Kotlin của "Thêm sách từ file…" (android/textImport.ts): PDF được pdf.js lấy chữ từng trang trong WebView rồi đưa sang
// Kotlin; mọi định dạng khác Kotlin đọc thẳng. Plugin native và pdf.js được thay bằng bản giả - phần Kotlin có test JVM riêng (TextImportsTest).
const library = vi.hoisted(() => ({
  pickSource: vi.fn(),
  previewImport: vi.fn(),
  createImport: vi.fn(),
  discardImport: vi.fn(),
}));
const pdf = vi.hoisted(() => ({ readPdfPages: vi.fn() }));
vi.mock("./plugins", () => ({ EbookLibrary: library }));
vi.mock("./importPdf", () => pdf);
vi.mock("@capacitor/core", () => ({ Capacitor: { convertFileSrc: (path: string) => `https://localhost/_capacitor_file_${path}` } }));

import { phoneTextImport } from "./textImport";

const PREVIEW = { title: "Sách", author: null, chapters: [], notes: [], hasCover: false, totals: { chapters: 0, words: 0 } };

beforeEach(() => {
  vi.resetAllMocks();
  library.previewImport.mockResolvedValue(PREVIEW);
});

describe("choose", () => {
  it("asks the system picker for a file or a folder and keeps the copy's reference", async () => {
    library.pickSource.mockResolvedValue({ picked: true, ref: "i1", name: "truyen.epub" });
    expect(await phoneTextImport.choose!("file")).toEqual({ ref: "i1", name: "truyen.epub" });
    expect(library.pickSource).toHaveBeenCalledWith({ kind: "file" });
    library.pickSource.mockResolvedValue({ picked: true, ref: "i2", name: "Truyện" });
    await phoneTextImport.choose!("folder");
    expect(library.pickSource).toHaveBeenLastCalledWith({ kind: "folder" });
  });

  it("returns nothing when the user backs out", async () => {
    library.pickSource.mockResolvedValue({ picked: false });
    expect(await phoneTextImport.choose!("file")).toBeNull();
  });

  it("remembers where the PDF copy is, so the WebView can read it", async () => {
    library.pickSource.mockResolvedValue({ picked: true, ref: "i3", name: "sach.pdf", pdf: "/data/library/imports/i3/sach.pdf" });
    expect(await phoneTextImport.choose!("file")).toMatchObject({ ref: "i3", pdf: "/data/library/imports/i3/sach.pdf" });
  });
});

describe("preview", () => {
  it("lets Kotlin read anything that is not a PDF", async () => {
    expect(await phoneTextImport.preview({ ref: "i1", name: "truyen.epub" })).toBe(PREVIEW);
    expect(library.previewImport).toHaveBeenCalledWith({ ref: "i1" });
    expect(pdf.readPdfPages).not.toHaveBeenCalled();
  });

  it("reads a PDF's lines with pdf.js and hands them to Kotlin, which applies the chapter rules", async () => {
    const bytes = new Uint8Array([37, 80, 68, 70]).buffer;
    const fetched = vi.fn().mockResolvedValue({ arrayBuffer: async () => bytes });
    vi.stubGlobal("fetch", fetched);
    pdf.readPdfPages.mockResolvedValue({ title: "Tên PDF", author: "Tác giả", pages: [["Chương 1", "Nội dung."], []] });
    const choice = { ref: "i3", name: "sach.pdf", pdf: "/data/library/imports/i3/sach.pdf" };
    expect(await phoneTextImport.preview(choice)).toBe(PREVIEW);
    expect(fetched).toHaveBeenCalledWith("https://localhost/_capacitor_file_/data/library/imports/i3/sach.pdf");
    expect(pdf.readPdfPages).toHaveBeenCalledWith(bytes);
    expect(library.previewImport).toHaveBeenCalledWith({
      ref: "i3",
      pages: [["Chương 1", "Nội dung."], []],
      title: "Tên PDF",
      author: "Tác giả",
    });
    vi.unstubAllGlobals();
  });

  it("says plainly when pdf.js cannot open the file", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ arrayBuffer: async () => new ArrayBuffer(0) }));
    pdf.readPdfPages.mockRejectedValue(new Error("PDF này có mật khẩu - ABook chưa mở được"));
    await expect(phoneTextImport.preview({ ref: "i3", name: "a.pdf", pdf: "/x/a.pdf" } as never)).rejects.toThrow(
      "Không đọc được PDF này: PDF này có mật khẩu - ABook chưa mở được",
    );
    expect(library.previewImport).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it("passes Kotlin's own refusal (e.g. a scanned PDF) through unchanged", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ arrayBuffer: async () => new ArrayBuffer(0) }));
    pdf.readPdfPages.mockResolvedValue({ title: "", author: "", pages: [[], [], []] });
    library.previewImport.mockRejectedValue(new Error("PDF scan, cần OCR: file chỉ có ảnh của trang"));
    await expect(phoneTextImport.preview({ ref: "i4", name: "scan.pdf", pdf: "/x/scan.pdf" } as never)).rejects.toThrow("PDF scan, cần OCR");
    vi.unstubAllGlobals();
  });
});

describe("add and discard", () => {
  it("adds with the title the user typed and drops the temporary copy on request", async () => {
    library.createImport.mockResolvedValue({ id: "f-abc", how: "new", chapters: 3 });
    expect(await phoneTextImport.add({ ref: "i1", name: "x" }, "Tên tôi đặt")).toEqual({ id: "f-abc", how: "new", chapters: 3 });
    expect(library.createImport).toHaveBeenCalledWith({ ref: "i1", title: "Tên tôi đặt" });
    library.discardImport.mockResolvedValue(undefined);
    await phoneTextImport.discard!({ ref: "i1", name: "x" });
    expect(library.discardImport).toHaveBeenCalledWith({ ref: "i1" });
  });
});

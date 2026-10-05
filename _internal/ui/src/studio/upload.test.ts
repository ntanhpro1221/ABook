import { describe, expect, it } from "vitest";
import { UPLOAD_LIMIT, batchName, planNotice, planUpload, progressLabel, type Picked } from "./upload";

const file = (path: string, size = 10): Picked => ({ name: path.split("/").pop()!, size, path: path.includes("/") ? path : "" });
const names = (files: Picked[]) => files.map((item) => item.name);

describe("planUpload", () => {
  it("sends loose files into the batch folder in file-name order (2 before 10)", () => {
    const plan = planUpload([file("10.txt"), file("2.txt"), file("1.txt")], "B");
    expect(plan.groups).toHaveLength(1);
    expect(plan.groups[0].folder).toBe("B");
    expect(plan.groups[0].loose).toBe(true);
    expect(names(plan.groups[0].files)).toEqual(["1.txt", "2.txt", "10.txt"]);
    expect(plan.bytes).toBe(30);
  });

  it("keeps a picked folder's name and takes only the files right inside it, like a pasted path", () => {
    const plan = planUpload(
      [file("Truyện/Chương 10.txt"), file("Truyện/Chương 9.txt"), file("Truyện/ghi chú/x.txt"), file("Truyện/bia.jpg")],
      "B",
    );
    expect(plan.groups.map((group) => group.folder)).toEqual(["B/Truyện"]);
    expect(plan.groups[0].loose).toBe(false);
    expect(names(plan.groups[0].files)).toEqual(["Chương 9.txt", "Chương 10.txt"]);
    expect(plan.ignored).toBe(2);
    expect(plan.rejected).toEqual([]);
  });

  it("turns a folder of volume folders into one upload per volume, in name order", () => {
    const plan = planUpload([file("Bộ/Tập 10/1.txt"), file("Bộ/Tập 2/1.txt"), file("Bộ/Tập 2/2.txt"), file("Bộ/Tập 2/sâu/3.txt")], "B");
    expect(plan.groups.map((group) => group.folder)).toEqual(["B/Bộ/Tập 2", "B/Bộ/Tập 10"]);
    expect(plan.ignored).toBe(1);
  });

  it("names the files it will not send: other types and files over the computer's limit", () => {
    const plan = planUpload([file("anh.jpg"), file("sach.mobi"), file("to.epub", UPLOAD_LIMIT + 1), file("1.txt")], "B");
    expect(plan.rejected).toEqual(["anh.jpg", "sach.mobi"]);
    expect(plan.tooBig).toEqual(["to.epub"]);
    expect(names(plan.groups[0].files)).toEqual(["1.txt"]);
    expect(planNotice(plan)).toBe(
      "“anh.jpg”, “sach.mobi” không phải file truyện - chỉ nhận .txt, .epub, .docx, .pdf. “to.epub” lớn hơn 8 MB - máy tính chỉ nhận file tới 8 MB.",
    );
    expect(planNotice(planUpload([file("1.txt")], "B"))).toBeNull();
  });

  it("accepts the book types the creator imports, in any letter case", () => {
    const plan = planUpload([file("A.EPUB"), file("b.Docx"), file("c.pdf")], "B");
    expect(names(plan.groups[0].files)).toEqual(["A.EPUB", "b.Docx", "c.pdf"]);
  });
});

describe("labels", () => {
  it("names each upload by its date and a tag", () => {
    expect(batchName(new Date(2026, 9, 5, 8, 7), "ab12")).toBe("Tải lên 05-10-2026 08h07 ab12");
  });
  it("shows files and size sent so far", () => {
    expect(progressLabel({ files: 3, totalFiles: 12, bytes: 1.2 * 1024 * 1024, totalBytes: 4.5 * 1024 * 1024 })).toBe(
      "Đang gửi 3/12 file · 1,2 MB / 4,5 MB",
    );
  });
});

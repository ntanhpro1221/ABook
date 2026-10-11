import { describe, expect, it } from "vitest";
import type { ListenBook } from "./model";
import { bookStatusText, remoteUnfinishedLine, upcomingStatus } from "./LibraryScreen";

// Thẻ sách chỉ có chữ ở Thư viện: dòng phụ nói tác giả (nếu có), không nói giọng nào đọc ("Hoài My (Edge)").

const book = (extra: Partial<ListenBook>) => ({ id: "x", stage: "text", chaptersTotal: 3, ...extra }) as unknown as ListenBook;

describe("bookStatusText - sách chỉ có chữ", () => {
  it("nói tác giả khi có", () => {
    expect(bookStatusText(book({ author: "Nguyễn Nhật Ánh" }), true)).toBe("Nguyễn Nhật Ánh · 3 chương");
  });
  it("không có tác giả: chỉ số chương, không nói tên giọng", () => {
    expect(bookStatusText(book({}), true)).toBe("3 chương");
    expect(bookStatusText(book({ author: "  " }), true)).toBe("3 chương");
  });
  it("máy chưa có giọng đọc: Chỉ có chữ", () => {
    expect(bookStatusText(book({}), false)).toBe("Chỉ có chữ · 3 chương");
  });
});

// Soát a27 lỗi 6: cuốn "sắp có" của máy khác nói việc đang ở máy nào, không mời "bấm để làm tiếp" (Studio ở đây không có dự án ấy).
describe("upcomingStatus - cuốn sắp có", () => {
  const upcoming = (extra: Partial<ListenBook>) => ({ id: "x", stage: "analysis", chaptersAvailable: 0, ...extra }) as unknown as ListenBook;
  it("cuốn của máy khác: tên máy, không mời làm tiếp", () => {
    expect(upcomingStatus(upcoming({ remote: { computer: "Máy A" }, producing: true } as Partial<ListenBook>), false)).toBe("Đang làm trên Máy A");
    expect(upcomingStatus(upcoming({ remote: { computer: "Máy A" } } as Partial<ListenBook>), false)).toBe("Chưa có chương nghe được · làm trên Máy A");
    expect(upcomingStatus(upcoming({ remote: true } as Partial<ListenBook>), false)).toBe("Chưa có chương nghe được · làm trên máy tính");
  });
  it("cuốn của máy này: mời làm tiếp khi mở được", () => {
    expect(upcomingStatus(upcoming({}), true)).toBe("Chưa có chương nghe được · bấm để làm tiếp");
  });
});

// Soát a27 lỗi 7: cuốn nghe thẳng chưa xong nói máy kia còn làm, không bảo "mở bản mới hơn".
describe("remoteUnfinishedLine", () => {
  it("nói tên máy đang làm", () => {
    expect(remoteUnfinishedLine({ remote: { computer: "Máy A" } } as unknown as ListenBook)).toBe("Máy A còn đang làm, chương mới hiện ở đây khi xong");
    expect(remoteUnfinishedLine({ remote: true } as unknown as ListenBook)).toBe("Máy tính còn đang làm, chương mới hiện ở đây khi xong");
  });
});

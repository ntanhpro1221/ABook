import { describe, expect, it } from "vitest";
import { ApiError, api, setApiTransport } from "@/studio/api";
import { localStudioTransport } from "./localStudio";

describe("đường truyền sửa sách trên điện thoại", () => {
  it("gửi đúng phương thức, đường dẫn và thân tới lõi native, trả đúng JSON", async () => {
    const calls: unknown[] = [];
    setApiTransport(
      localStudioTransport(async (options) => {
        calls.push(options);
        return { status: 200, body: { title: "Tên mới" } };
      }),
    );
    try {
      const reply = await api<{ title: string }>("/api/books/abc/title", { method: "PUT", body: { title: "Tên mới" } });
      expect(reply).toEqual({ title: "Tên mới" });
      expect(calls).toEqual([{ method: "PUT", path: "/api/books/abc/title", body: { title: "Tên mới" } }]);
      await api("/api/books/abc/music");
      expect(calls[1]).toEqual({ method: "GET", path: "/api/books/abc/music", body: undefined });
      // Lõi native không đọc `?...`: tham số của lệnh GET đi trong body (tìm bìa trên mạng), đã giải mã.
      await api("/api/books/abc/cover/search?q=" + encodeURIComponent("Tắt đèn & Co"));
      expect(calls[2]).toEqual({ method: "GET", path: "/api/books/abc/cover/search", body: { q: "Tắt đèn & Co" } });
      await api("/api/books/abc/music?x=1", { method: "PUT", body: { enabled: false } });
      expect(calls[3]).toEqual({ method: "PUT", path: "/api/books/abc/music", body: { enabled: false } });
    } finally {
      setApiTransport(null);
    }
  });

  it("mã lỗi thành ApiError mang câu của lõi native, như fetch thật", async () => {
    setApiTransport(localStudioTransport(async () => ({ status: 409, body: { error: "Sách này lấy từ máy tính khác" } })));
    try {
      const error = await api("/api/books/abc/title", { method: "PUT", body: { title: "x" } }).catch((caught: unknown) => caught);
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).status).toBe(409);
      expect((error as ApiError).message).toBe("Sách này lấy từ máy tính khác");
    } finally {
      setApiTransport(null);
    }
  });

  it("lời đáp không phải đối tượng vẫn có câu lỗi mặc định", async () => {
    setApiTransport(localStudioTransport(async () => ({ status: 500, body: null })));
    try {
      await expect(api("/api/books/abc/edits")).rejects.toMatchObject({ status: 500, message: "Lỗi 500" });
    } finally {
      setApiTransport(null);
    }
  });
});

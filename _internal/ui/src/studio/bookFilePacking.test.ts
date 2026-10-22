import { beforeEach, expect, it, vi } from "vitest";
import { api } from "./api";
import { packBookFile } from "./bookFilePacking";

vi.mock("./api", () => ({ api: vi.fn() }));
beforeEach(() => vi.mocked(api).mockReset());

it.each([true, false])("cả bộ single=%s có mã job ngay và theo kết quả sau khi phản hồi bắt đầu đã xong", async (single) => {
  vi.mocked(api).mockResolvedValue({ state: "running", id: "j1" });
  const result = { folder: "out", parts: [1, 2, 3] };
  const follow = vi.fn(async () => result);
  expect(await packBookFile("b1", { target: "out", series: true, single }, follow)).toEqual(result);
  expect(api).toHaveBeenCalledWith("/api/books/b1/bookfile-job", { method: "POST", body: { target: "out", series: true, single } });
  expect(follow).toHaveBeenCalledOnce();
});

it("nối lại chỉ theo job hiện có, không xuất thêm bản nữa", async () => {
  const follow = vi.fn(async () => ({ file: "old.abook" }));
  expect(await packBookFile("b1", { target: "", series: true }, follow, true)).toEqual({ file: "old.abook" });
  expect(api).not.toHaveBeenCalled();
});

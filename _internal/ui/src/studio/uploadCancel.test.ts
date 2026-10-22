import { beforeEach, describe, expect, it, vi } from "vitest";

// Soát a92 V4: gửi nguồn từ trình duyệt/điện thoại huỷ được; file đã gửi được giữ, và nói rõ đã gửi bao nhiêu.

const sent = vi.hoisted(() => ({ calls: [] as { folder: string; name: string; signal?: AbortSignal }[], hook: null as null | ((n: number) => void) }));
vi.mock("@/studio/api", () => ({
  api: vi.fn(async (_path: string, init: { body: { folder: string; name: string }; signal?: AbortSignal }) => {
    if (init.signal?.aborted) throw new DOMException("Aborted", "AbortError");
    sent.calls.push({ folder: init.body.folder, name: init.body.name, signal: init.signal });
    sent.hook?.(sent.calls.length);
    return { folder: `/srv/${init.body.folder}`, path: `/srv/${init.body.folder}/${init.body.name}` };
  }),
}));
import { planUpload, sendPlan, sendSummary, type Picked } from "./upload";

const pick = (path: string): Picked & { file: File } => {
  const name = path.split("/").pop()!;
  return { name, size: 4, path: path.includes("/") ? path : "", file: new File(["abcd"], name) };
};
const loose = () => planUpload([pick("1.txt"), pick("2.txt"), pick("3.txt")], "B");

beforeEach(() => {
  sent.calls = [];
  sent.hook = null;
});

describe("sendPlan cancel", () => {
  it("sends everything and reports it when nobody cancels", async () => {
    const result = await sendPlan(loose(), () => undefined);
    expect(result).toMatchObject({ sent: 3, total: 3, cancelled: false, paths: ["/srv/B/1.txt", "/srv/B/2.txt", "/srv/B/3.txt"] });
    expect(result.error).toBeUndefined();
  });

  it("hands the signal to every request and checks the flag between files", async () => {
    const controller = new AbortController();
    sent.hook = (n) => n === 1 && controller.abort();
    const result = await sendPlan(loose(), () => undefined, controller.signal);
    expect(sent.calls.map((call) => call.name)).toEqual(["1.txt"]);
    expect(sent.calls[0].signal).toBe(controller.signal);
    expect(result.cancelled).toBe(true);
    expect(result.error).toBeUndefined();
  });

  it("keeps the files already sent and says how many", async () => {
    const controller = new AbortController();
    sent.hook = (n) => n === 2 && controller.abort();
    const result = await sendPlan(loose(), () => undefined, controller.signal);
    expect(result).toMatchObject({ sent: 2, total: 3, cancelled: true, paths: ["/srv/B/1.txt", "/srv/B/2.txt"] });
    expect(sendSummary(result)).toBe("Đã gửi 2/3 file, giữ lại; 1 file chưa gửi.");
  });

  it("an abort that cuts a request in flight stops quietly and does not count that file", async () => {
    const { api } = await import("@/studio/api");
    vi.mocked(api).mockImplementationOnce(async () => ({ folder: "/srv/B", path: "/srv/B/1.txt" })).mockRejectedValueOnce(new DOMException("Aborted", "AbortError"));
    const result = await sendPlan(loose(), () => undefined, new AbortController().signal);
    expect(result).toMatchObject({ sent: 1, cancelled: true, paths: ["/srv/B/1.txt"] });
    expect(result.error).toBeUndefined();
  });

  it("an abort before the first file sends nothing", async () => {
    const controller = new AbortController();
    controller.abort();
    const result = await sendPlan(loose(), () => undefined, controller.signal);
    expect(sent.calls).toEqual([]);
    expect(result).toMatchObject({ sent: 0, total: 3, cancelled: true, paths: [] });
    expect(sendSummary(result)).toBe("Chưa gửi file nào.");
  });

  it("a folder cancelled part-way still points at what reached the computer", async () => {
    const controller = new AbortController();
    sent.hook = (n) => n === 2 && controller.abort();
    const plan = planUpload([pick("Truyện/1.txt"), pick("Truyện/2.txt"), pick("Truyện/3.txt")], "B");
    const result = await sendPlan(plan, () => undefined, controller.signal);
    expect(result.paths).toEqual(["/srv/B/Truyện"]);
    expect(result.sent).toBe(2);
    const none = await sendPlan(plan, () => undefined, controller.signal);
    expect(none.paths).toEqual([]);
  });

  it("a real failure also keeps what was sent before it", async () => {
    const { api } = await import("@/studio/api");
    vi.mocked(api).mockImplementationOnce(async () => ({ folder: "/srv/B", path: "/srv/B/1.txt" })).mockRejectedValueOnce(new Error("Mạng đứt"));
    const result = await sendPlan(loose(), () => undefined);
    expect(result).toMatchObject({ sent: 1, total: 3, cancelled: false, paths: ["/srv/B/1.txt"] });
    expect(result.error?.message).toBe("Mạng đứt");
  });
});

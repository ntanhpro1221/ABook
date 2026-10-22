import { beforeEach, describe, expect, it, vi } from "vitest";

const calls: { url: string; body: Record<string, unknown> }[] = [];
let failSpeaker = false;
vi.mock("./api", async (original) => ({
  ...(await original<typeof import("./api")>()),
  api: vi.fn(async (url: string, options?: { body?: Record<string, unknown> }) => {
    calls.push({ url, body: options?.body ?? {} });
    if (url.endsWith("/speaker")) {
      if (failSpeaker) throw new Error("Trong sách đã có người tên “Lan”");
      return { requestedAt: 222 };
    }
    return { requestedAt: 111 };
  }),
}));

const ref = { stableId: "c1s1", textSha256: "sha" };

beforeEach(() => {
  calls.length = 0;
  failSpeaker = false;
});

describe("sửa cách đọc một câu kèm người nói", () => {
  it("người có sẵn trong sách đi một bước, kèm người nói", async () => {
    const { postLineFix } = await import("./ScriptTab");
    const answer = await postLineFix("b1", ref, { kind: "dialogue", speaker: "NATASHA" }, null);
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe("/api/books/b1/line");
    expect(calls[0].body).toMatchObject({ stableId: "c1s1", kind: "dialogue", speaker: "NATASHA" });
    expect(answer.speakerAt).toBeUndefined();
  });

  it("người MỚI: cách đọc câu trước (không mang người nói), người mới sau; Hoàn tác biết cả hai mốc", async () => {
    const { postLineFix } = await import("./ScriptTab");
    const answer = await postLineFix("b1", ref, { kind: "dialogue", speaker: "Maria", newGender: "female" }, null);
    expect(calls.map((call) => call.url)).toEqual(["/api/books/b1/line", "/api/books/b1/speaker"]);
    expect(calls[0].body).not.toHaveProperty("speaker");
    expect(calls[0].body).not.toHaveProperty("newGender");
    expect(calls[1].body).toMatchObject({ lines: [ref], speaker: "Maria", newGender: "female" });
    expect(answer).toMatchObject({ requestedAt: 111, speakerAt: 222 });
  });

  it("bước người mới hỏng thì rút luôn bước cách đọc câu và báo lỗi", async () => {
    const { postLineFix } = await import("./ScriptTab");
    failSpeaker = true;
    await expect(postLineFix("b1", ref, { kind: "dialogue", speaker: "Lan", newGender: "female" }, null)).rejects.toThrow("đã có người tên");
    expect(calls.at(-1)).toMatchObject({ url: "/api/books/b1/line", body: { stableId: "c1s1", withdraw: true, requestedAt: 111 } });
  });
});

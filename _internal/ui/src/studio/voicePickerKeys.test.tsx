import { renderToString } from "react-dom/server";
import { beforeEach, expect, it, vi } from "vitest";
import { api } from "./api";
import { VoicePicker } from "./VoicePicker";

// Hộp "Đổi giọng" hiện NHÃN ("Bảo Trang") nhưng máy chủ chỉ nhận KHOÁ ("baotrang"): chọn, nghe thử bằng câu của sách và nghe mẫu
// đều phải gửi khoá (soát a94 F1).
const captured = vi.hoisted(() => ({
  mutations: [] as { mutationFn: (variables: unknown) => Promise<unknown> }[],
  tries: [] as { request: Record<string, unknown>; name: string; fallbackUrl?: string }[],
}));
const choices = {
  character: { value: "NOAH", label: "Noah", gender: "male", lines: 4, chapters: 1 },
  current: "Thiện Minh",
  pending: null,
  voices: [
    voice("Thiện Minh", "Thiện Minh", "vieneu"),
    voice("giahuy", "Gia Huy", "zerotts"),
    voice("M4", "Supertonic M4", "supertonic"),
  ],
  tryLine: { segmentId: 1, text: "Mình cứ đi chậm thôi." },
  modules: {},
};
function voice(key: string, name: string, engine: string) {
  return { key, name, engine, engineLabel: engine, installed: true, oneStep: engine !== "vieneu", description: "", gender: "male",
    genderLabel: "Nam", region: "", style: "", preview: true, current: false, pending: false, suggested: false, sharedWith: [], otherUsers: 0 };
}
vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn(), setQueryData: vi.fn() }),
  useQuery: () => ({ data: choices, isLoading: false, error: null }),
  useMutation: (options: { mutationFn: (variables: unknown) => Promise<unknown> }) => {
    captured.mutations.push(options);
    return { mutate: vi.fn(), isPending: false };
  },
}));
vi.mock("@/listen/clip", () => ({ useClip: () => ({ current: null, stop: vi.fn(), toggle: vi.fn(), loading: false }) }));
vi.mock("@/shared/ui", async (original) => ({
  ...(await original<typeof import("@/shared/ui")>()),
  Dialog: ({ children }: { children: React.ReactNode }) => <div>{children}</div>, // Dialog thật vẽ vào cổng, không có khi vẽ chuỗi
}));
vi.mock("./data", () => ({ useAppInfo: () => ({ data: { remote: false } }) }));
vi.mock("./decisions", () => ({ refreshAfterDecision: vi.fn(), UNDO_MS: 1, undoAction: vi.fn(), useWhenApplied: () => "" }));
vi.mock("./VoiceTry", () => ({
  useVoiceTry: () => ({
    note: null,
    button: (request: Record<string, unknown>, name: string, options?: { fallbackUrl?: string }) => {
      captured.tries.push({ request, name, fallbackUrl: options?.fallbackUrl });
      return null;
    },
  }),
}));
vi.mock("./api", async (original) => ({ ...(await original<typeof import("./api")>()), api: vi.fn(async () => ({ requestedAt: 1 })) }));
beforeEach(() => {
  captured.mutations.length = 0;
  captured.tries.length = 0;
  vi.mocked(api).mockClear();
});

it("gửi khoá giọng khi chọn và khi nghe thử bằng câu của sách, nhãn chỉ để hiện", async () => {
  const html = renderToString(<VoicePicker bookId="b1" person={{ name: "NOAH", displayName: "Noah" }} onClose={() => undefined} />);
  expect(html).toContain("Gia Huy");
  expect(html).toContain("Supertonic M4");
  expect(captured.tries.map((item) => item.request.preset)).toEqual(["Thiện Minh", "giahuy", "M4"]);
  expect(captured.tries.map((item) => item.name)).toEqual(["Thiện Minh", "Gia Huy", "Supertonic M4"]);
  expect(captured.tries.map((item) => item.fallbackUrl)).toEqual([
    "/media/voices/Thi%E1%BB%87n%20Minh", "/media/voices/giahuy", "/media/voices/M4"].map((path) => expect.stringContaining(path)));

  const save = captured.mutations[0];
  await save.mutationFn({ voice: choices.voices[1], withGender: false });
  await save.mutationFn({ voice: choices.voices[2], withGender: true });
  const bodies = vi.mocked(api).mock.calls.map((call) => (call[1] as { body: Record<string, unknown> }).body);
  expect(bodies.map((body) => body.preset)).toEqual(["giahuy", "M4"]);
  expect(bodies[1].gender).toBe("male");
});

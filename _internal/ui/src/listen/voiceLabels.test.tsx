import { renderToString } from "react-dom/server";
import { expect, it, vi } from "vitest";
import { TooltipProvider } from "@/shared/ui";
import { PersonRow } from "./BookScreen";
import { voiceName, type CastMember } from "./model";

// Người nghe thấy nhãn giọng ("Bảo Trang"), không thấy khoá ("baotrang") - soát a94. `preset` vẫn là khoá.
vi.mock("./source", async (original) => ({ ...(await original<typeof import("./source")>()), useSource: () => ({ voiceUrl: () => "" }) }));
vi.mock("./clip", () => ({ useClip: () => ({ current: null, stop: vi.fn(), toggle: vi.fn(), loading: false }) }));

const person = (over: Partial<CastMember> = {}): CastMember => ({
  name: "NOAH", displayName: "Noah", gender: "Nam", age: "", lines: 4, seconds: 10,
  voice: { key: "zerotts_baotrang_f100_p+00", preset: "baotrang", label: "Bảo Trang", tone: "" },
  sampleId: null, firstChapter: "", ...over,
}) as CastMember;

it("dòng nhân vật hiện nhãn giọng và nhãn của giọng đang chờ, không hiện khoá", () => {
  const html = renderToString(
    <TooltipProvider>
      <PersonRow bookId="b1" person={person({ pendingVoice: { preset: "F1", label: "Supertonic F1", gender: "" } })} onPickVoice={() => undefined} />
    </TooltipProvider>,
  );
  expect(html).toContain("Bảo Trang");
  expect(html).toContain("giọng Supertonic F1");
  expect(html).not.toContain("baotrang");
  expect(html).not.toContain("giọng F1");
});

it("máy chủ cũ hay sách chưa có nhãn: rơi về khoá (giọng VieNeu: khoá cũng là tên)", () => {
  expect(voiceName({ preset: "Thiện Minh" })).toBe("Thiện Minh");
  expect(voiceName({ preset: "baotrang", label: "" })).toBe("baotrang");
  expect(voiceName(null)).toBe("");
});

import { expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { api } from "@/studio/api";
import { desktopVoicePick, VoicePickCard, type VoicePickBackend } from "./VoicePickCard";
import type { VoicePickStatus } from "./voicePick";

vi.mock("@/studio/api", async (original) => ({ ...(await original<typeof import("@/studio/api")>()), api: vi.fn(async () => ({})) }));

const STATUS: VoicePickStatus = {
  state: "ready", auto: "supertonic", override: "", chosen: "supertonic", asr: "whisper", natural: "utmosv2", liveRtf: 0.8,
  engines: [
    { engine: "supertonic", voice: "supertonic:F1", measured: true, verdict: "", rtf: 0.2, ramMb: 530, peakRamMb: 830, loadMs: 900, cer: 0.02, natural: 3.2, error: "" },
    { engine: "vieneu:turbo", voice: "vieneu:turbo/Adam bựa", measured: true, verdict: "slow", rtf: 1.1, ramMb: 620, loadMs: 2700, cer: 0.01, natural: 2.8, error: "" },
  ],
};

it("shows each engine's numbers, marks the measured pick and offers the others", () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(["readaloud", "voice-pick"], STATUS);
  const action = async () => STATUS;
  const backend: VoicePickBackend = { status: action, measure: action, choose: action };
  const html = renderToStaticMarkup(<QueryClientProvider client={client}><VoicePickCard backend={backend} /></QueryClientProvider>);
  expect(html).toContain("Giọng theo máy");
  expect(html).toContain("Máy chọn");
  expect(html).toContain("Rõ 98% · Tự nhiên 3,2/5 · Nhanh gấp 5,0 lần · RAM đỉnh 830 MB");
  expect(html).toContain("Chậm");
  expect(html.match(/Dùng giọng này/g)).toHaveLength(1); // bộ đang làm mặc định không có nút
  expect(html).toContain("Thử lại");
  client.clear();
});

it("talks to the local server", async () => {
  await desktopVoicePick.measure();
  await desktopVoicePick.choose("vieneu:nano");
  expect(vi.mocked(api).mock.calls.map(([path, init]) => [path, (init as { body: unknown }).body])).toEqual([
    ["/api/readaloud/voice-pick/measure", {}],
    ["/api/readaloud/voice-pick/choose", { engine: "vieneu:nano" }],
  ]);
});

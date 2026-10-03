import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button, Progress } from "@/shared/ui";
import { cn } from "@/shared/cn";
import { api } from "@/studio/api";
import { formatSize } from "@/studio/musicLocal";
import { forgetVoices, switchVoices } from "./readAloudVoice";
import type { ReadAloudVoice } from "./readAloud";
import {
  benchmarkLabel,
  initialChoices,
  meteredNotice,
  selectionBytes,
  suggestionText,
  lowerFirst,
  tierVoicePrefix,
  VIENEU_COPY,
  vieneuLabel,
  vieneuPercent,
  SUPERTONIC_COPY,
  type ModuleCopy,
  type VieneuChoiceId,
  type VieneuStatus,
} from "./vieneuModule";

const ONLINE_VOICE = "edge:vi-VN-HoaiMyNeural";

/** Nơi mô-đun sống: máy tính hỏi máy chủ cục bộ (`desktopVieneu`, `desktopSupertonic`), điện thoại hỏi plugin ReadAloud (android/SettingsScreen.tsx).
 *  Cùng hình trạng thái. `remove` có trên điện thoại và với giọng Supertonic (gỡ một giọng để lấy lại chỗ). `start()` không kèm lựa chọn = cập nhật
 *  phần đã cũ. */
export interface VieneuBackend {
  status(): Promise<VieneuStatus>;
  start(choices?: VieneuChoiceId[]): Promise<VieneuStatus>;
  measure(): Promise<VieneuStatus>;
  remove?(choice: VieneuChoiceId): Promise<VieneuStatus>;
  voices(): Promise<ReadAloudVoice[]>;
}

export const desktopVieneu: VieneuBackend = {
  status: () => api<VieneuStatus>("/api/readaloud/vieneu"),
  start: (choices) => api<VieneuStatus>("/api/readaloud/vieneu", { method: "POST", body: choices ? { choices } : {} }),
  measure: () => api<VieneuStatus>("/api/readaloud/vieneu/measure", { method: "POST", body: {} }),
  voices: () => api<ReadAloudVoice[]>("/api/readaloud/voices"),
};

export const desktopSupertonic: VieneuBackend = {
  ...desktopVieneu,
  status: () => api<VieneuStatus>("/api/readaloud/supertonic"),
  start: (choices) => api<VieneuStatus>("/api/readaloud/supertonic", { method: "POST", body: choices ? { choices } : {} }),
  measure: () => api<VieneuStatus>("/api/readaloud/supertonic/measure", { method: "POST", body: {} }),
  remove: (choice) => api<VieneuStatus>("/api/readaloud/supertonic/remove", { method: "POST", body: { choice } }),
};

/** Thẻ của mô-đun giọng Supertonic: cùng thẻ, lời riêng (máy tính). */
export function SupertonicModuleCard({ onChanged }: { onChanged?: () => void }) {
  return <VieneuModuleCard backend={desktopSupertonic} copy={SUPERTONIC_COPY} onChanged={onChanged} />;
}

/** Thẻ của mô-đun "Giọng VieNeu" trong Cài đặt: chọn giọng muốn tải (có "Khuyên dùng" theo máy), thấy đúng dung lượng máy còn thiếu,
 *  bấm mới tải; tải xong máy tự thử vài giây và nói giọng có kịp người nghe không - không kịp thì đề nghị đổi, người dùng bấm mới đổi. */
export function VieneuModuleCard({
  onChanged,
  backend = desktopVieneu,
  copy = VIENEU_COPY,
}: { onChanged?: () => void; backend?: VieneuBackend; copy?: ModuleCopy } = {}) {
  const client = useQueryClient();
  const lowerName = lowerFirst(copy.name);
  const { data: status } = useQuery({ queryKey: ["readaloud", copy.key], queryFn: () => backend.status() });
  const [chosen, setChosen] = useState<VieneuChoiceId[] | null>(null);
  const [busy, setBusy] = useState(false);
  const working = status?.state === "downloading" || Boolean(status?.benchmarking);
  const wasWorking = useRef(false);
  // Trong lúc tải: % không bao giờ lùi (một lần nối lại mà máy chủ tải lại từ đầu file làm số nhảy lùi) và cỡ mỗi lựa chọn đứng yên ở cỡ lúc bấm tải
  // (số "còn thiếu" của lựa chọn co lại mỗi khi một phần dùng chung tải xong: 313 -> 297 MB giữa chừng).
  const peak = useRef(0);
  const sizes = useRef<Record<string, number>>({});
  useEffect(() => {
    if (!working) return;
    const timer = setInterval(() => void client.invalidateQueries({ queryKey: ["readaloud", copy.key] }), 1000);
    return () => clearInterval(timer);
  }, [working, client, copy.key]);
  useEffect(() => {
    // Vừa tải / đo xong: danh sách giọng của trình phát hỏi lại để giọng mới hiện ngay.
    if (wasWorking.current && !working) {
      forgetVoices();
      void client.invalidateQueries({ queryKey: ["readaloud", "voices"] });
      onChanged?.();
    }
    wasWorking.current = working;
  }, [working, client, onChanged]);
  if (!status) return null;
  const downloading = status.state === "downloading";
  peak.current = downloading ? Math.max(peak.current, status.done) : 0;
  if (!downloading) sizes.current = Object.fromEntries(status.choices.map((choice) => [choice.id, choice.bytes]));
  const shown: VieneuStatus = downloading ? { ...status, done: peak.current } : status;
  const picked = chosen ?? initialChoices(status);
  const missing = picked.filter((id) => !status.choices.find((choice) => choice.id === id)?.installed);
  const bytes = selectionBytes(status, missing);
  const run = async (action: () => Promise<VieneuStatus>, failure = `Chưa tải được ${lowerName}`) => {
    setBusy(true);
    try {
      client.setQueryData(["readaloud", copy.key], await action());
    } catch (error) {
      toast.error(failure, { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  const remove = async (id: VieneuChoiceId) => {
    if (!backend.remove) return;
    await run(() => backend.remove!(id), `Chưa gỡ được ${lowerName}`);
    forgetVoices();
    void client.invalidateQueries({ queryKey: ["readaloud", "voices"] });
    onChanged?.();
  };
  const switchTo = async () => {
    const suggestion = status.suggestion;
    if (!suggestion) return;
    if (suggestion.switchTo === "nano" && !suggestion.installed) return void run(() => backend.start(["nano"]));
    let target = ONLINE_VOICE;
    if (suggestion.switchTo === "nano") {
      const voices = await backend.voices();
      target = voices.find((voice) => voice.id.startsWith("vieneu:nano/"))?.id ?? ONLINE_VOICE;
    }
    switchVoices(tierVoicePrefix(suggestion.tier), target);
    toast.success(suggestion.switchTo === "nano" ? "Đã chuyển sang giọng VieNeu Nano" : "Đã chuyển sang giọng trực tuyến");
  };
  const toggle = (id: VieneuChoiceId, on: boolean) => setChosen(on ? [...new Set([...picked, id])] : picked.filter((item) => item !== id));
  const failed = status.state === "error";
  const canPick = !working && status.state !== "unsupported";
  const suggestion = status.suggestion && !working ? suggestionText(status.suggestion) : null;
  const metered = canPick && missing.length > 0 ? meteredNotice(status, bytes) : null;
  return (
    <div className="max-w-xl space-y-3">
      <h3 className="text-sm font-semibold">{copy.title}</h3>
      <p role="status" className={cn("text-sm text-pretty", failed ? "text-danger" : "text-fg-2")}>{vieneuLabel(shown, copy)}</p>
      {status.state === "downloading" && <Progress value={vieneuPercent(shown) / 100} size="sm" running label={`Đang tải ${lowerName}`} />}
      <ul className="divide-y divide-line rounded-xl border border-line">
        {status.choices.map((choice) => {
          const on = picked.includes(choice.id);
          return (
            <li key={choice.id}>
              <label className={cn("flex items-start gap-3 px-3 py-2.5", canPick && !choice.installed ? "cursor-pointer" : "cursor-default")}>
                <input
                  type="checkbox"
                  className="mt-1 size-4 accent-[var(--accent)]"
                  checked={choice.installed || on}
                  disabled={!canPick || choice.installed}
                  onChange={(event) => toggle(choice.id, event.target.checked)}
                />
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-x-2 text-sm font-medium">
                    {choice.label}
                    {choice.recommended && !choice.installed && (
                      <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-semibold text-accent-text">Khuyên dùng</span>
                    )}
                  </span>
                  <span className="mt-0.5 block text-[13px] text-fg-2 text-pretty">{choice.detail}</span>
                </span>
                <span className="shrink-0 pt-0.5 text-xs text-fg-2">
                  {choice.installed ? "Đã có" : (downloading ? (sizes.current[choice.id] ?? choice.bytes) : choice.bytes) > 0 ? formatSize(downloading ? (sizes.current[choice.id] ?? choice.bytes) : choice.bytes) : "Đã có sẵn"}
                </span>
                {choice.installed && choice.removable && backend.remove && canPick && (
                  <Button size="sm" variant="ghost" className="-my-1 shrink-0" loading={busy} onClick={(event) => { event.preventDefault(); void remove(choice.id); }}>
                    Gỡ
                  </Button>
                )}
              </label>
            </li>
          );
        })}
      </ul>
      {copy.tiers.map((tier) =>
        status.benchmark[tier] ? (
          <p key={tier} className="text-[13px] text-fg-2 text-pretty">{benchmarkLabel(tier, status.benchmark[tier]!, status.slowRtf)}</p>
        ) : null,
      )}
      {metered && <p className="text-[13px] text-fg-2 text-pretty">{metered}</p>}
      {suggestion && (
        <div className="rounded-xl border border-warning/40 bg-warning-soft px-3 py-2.5 text-[13px] text-pretty">
          <p>{suggestion.message}</p>
          <Button size="sm" variant="secondary" className="mt-2" loading={busy} onClick={() => void switchTo()}>
            {suggestion.action}
          </Button>
        </div>
      )}
      {canPick && !status.restart && (
        <div className="flex flex-wrap items-center gap-2">
          {status.state === "outdated" && (
            <Button size="sm" variant="secondary" loading={busy} onClick={() => void run(() => backend.start())}>
              {`Cập nhật (${formatSize(status.outdatedBytes)})`}
            </Button>
          )}
          {missing.length > 0 && (
            <Button size="sm" variant={status.state === "missing" ? "primary" : "secondary"} loading={busy} onClick={() => void run(() => backend.start(missing))}>
              {failed ? "Thử lại" : bytes > 0 ? `Tải (${formatSize(bytes)})` : "Dùng"}
            </Button>
          )}
          {Object.keys(status.benchmark).length > 0 && (
            <Button size="sm" variant="ghost" loading={busy} onClick={() => void run(() => backend.measure())}>
              Thử lại tốc độ
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

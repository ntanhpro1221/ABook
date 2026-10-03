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
  selectionBytes,
  suggestionText,
  vieneuLabel,
  vieneuPercent,
  type VieneuChoiceId,
  type VieneuStatus,
} from "./vieneuModule";

const KEY = ["readaloud", "vieneu"] as const;
const ONLINE_VOICE = "edge:vi-VN-HoaiMyNeural";

/** Thẻ của mô-đun "Giọng VieNeu" trong Cài đặt (máy tính): chọn giọng muốn tải (có "Khuyên dùng" theo máy), thấy đúng dung lượng máy còn thiếu,
 *  bấm mới tải; tải xong máy tự thử vài giây và nói giọng có kịp người nghe không - không kịp thì đề nghị đổi, người dùng bấm mới đổi. */
export function VieneuModuleCard() {
  const client = useQueryClient();
  const { data: status } = useQuery({ queryKey: KEY, queryFn: () => api<VieneuStatus>("/api/readaloud/vieneu") });
  const [chosen, setChosen] = useState<VieneuChoiceId[] | null>(null);
  const [busy, setBusy] = useState(false);
  const working = status?.state === "downloading" || Boolean(status?.benchmarking);
  const wasWorking = useRef(false);
  useEffect(() => {
    if (!working) return;
    const timer = setInterval(() => void client.invalidateQueries({ queryKey: KEY }), 1000);
    return () => clearInterval(timer);
  }, [working, client]);
  useEffect(() => {
    // Vừa tải / đo xong: danh sách giọng của trình phát hỏi lại để giọng mới hiện ngay.
    if (wasWorking.current && !working) {
      forgetVoices();
      void client.invalidateQueries({ queryKey: ["readaloud", "voices"] });
    }
    wasWorking.current = working;
  }, [working, client]);
  if (!status) return null;
  const picked = chosen ?? initialChoices(status);
  const missing = picked.filter((id) => !status.choices.find((choice) => choice.id === id)?.installed);
  const bytes = selectionBytes(status, missing);
  const post = async (body: { choices?: VieneuChoiceId[] }, path = "/api/readaloud/vieneu") => {
    setBusy(true);
    try {
      client.setQueryData(KEY, await api<VieneuStatus>(path, { method: "POST", body }));
    } catch (error) {
      toast.error("Chưa tải được giọng VieNeu", { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  const switchTo = async () => {
    const suggestion = status.suggestion;
    if (!suggestion) return;
    if (suggestion.switchTo === "nano" && !suggestion.installed) return void post({ choices: ["nano"] });
    let target = ONLINE_VOICE;
    if (suggestion.switchTo === "nano") {
      const voices = await api<ReadAloudVoice[]>("/api/readaloud/voices");
      target = voices.find((voice) => voice.id.startsWith("vieneu:nano/"))?.id ?? ONLINE_VOICE;
    }
    switchVoices(`vieneu:${suggestion.tier}/`, target);
    toast.success(suggestion.switchTo === "nano" ? "Đã chuyển sang giọng VieNeu Nano" : "Đã chuyển sang giọng trực tuyến");
  };
  const toggle = (id: VieneuChoiceId, on: boolean) => setChosen(on ? [...new Set([...picked, id])] : picked.filter((item) => item !== id));
  const failed = status.state === "error";
  const canPick = !working && status.state !== "unsupported";
  const suggestion = status.suggestion && !working ? suggestionText(status.suggestion) : null;
  return (
    <div className="max-w-xl space-y-3">
      <p role="status" className={cn("text-sm text-pretty", failed ? "text-danger" : "text-fg-2")}>{vieneuLabel(status)}</p>
      {status.state === "downloading" && <Progress value={vieneuPercent(status) / 100} size="sm" running label="Đang tải giọng VieNeu" />}
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
                  {choice.installed ? "Đã có" : choice.bytes > 0 ? formatSize(choice.bytes) : "Đã có sẵn"}
                </span>
              </label>
            </li>
          );
        })}
      </ul>
      {(["turbo", "nano"] as const).map((tier) =>
        status.benchmark[tier] ? (
          <p key={tier} className="text-[13px] text-fg-2 text-pretty">{benchmarkLabel(tier, status.benchmark[tier]!, status.slowRtf)}</p>
        ) : null,
      )}
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
            <Button size="sm" variant="secondary" loading={busy} onClick={() => void post({})}>
              {`Cập nhật (${formatSize(status.outdatedBytes)})`}
            </Button>
          )}
          {missing.length > 0 && (
            <Button size="sm" variant={status.state === "missing" ? "primary" : "secondary"} loading={busy} onClick={() => void post({ choices: missing })}>
              {failed ? "Thử lại" : bytes > 0 ? `Tải (${formatSize(bytes)})` : "Dùng"}
            </Button>
          )}
          {Object.keys(status.benchmark).length > 0 && (
            <Button size="sm" variant="ghost" loading={busy} onClick={() => void post({}, "/api/readaloud/vieneu/measure")}>
              Thử lại tốc độ
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

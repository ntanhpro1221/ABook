import { S } from "../shared/strings.generated";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { MotionRegion } from "@/shared/MotionRegion";
import { toast } from "@/shared/toast";
import { Button, Progress } from "@/shared/ui";
import { api } from "@/studio/api";
import { forgetVoices, watchVoiceModule } from "./readAloudVoice";
import { engineName, pickHeadline, pickMethod, rowBadge, rowNumbers, type VoicePickStatus } from "./voicePick";

import { Reveal } from "../shared/MotionPresence";
/** Máy tính dùng HTTP; điện thoại có thẻ native cùng luật trong ui/voice/VoicePickCard.kt. */
export interface VoicePickBackend {
  status(): Promise<VoicePickStatus>;
  measure(): Promise<VoicePickStatus>;
  /** "" = theo số đo. */
  choose(engine: string): Promise<VoicePickStatus>;
}

export const desktopVoicePick: VoicePickBackend = {
  status: () => api<VoicePickStatus>("/api/readaloud/voice-pick"),
  measure: () => api<VoicePickStatus>("/api/readaloud/voice-pick/measure", { method: "POST", body: {} }),
  choose: (engine) => api<VoicePickStatus>("/api/readaloud/voice-pick/choose", { method: "POST", body: { engine } }),
};

const KEY = ["readaloud", "voice-pick"] as const;

/** Thẻ "Giọng theo máy" của Cài đặt: số đo từng bộ giọng đã tải trên chính máy này, bộ làm mặc định cho sách chưa chọn giọng (máy chọn theo số đo,
 *  người dùng chọn tay được). `modulesBusy`: một thẻ tải giọng đang tải / tự thử - xong thì hỏi lại (máy tự thử lại các giọng khi có giọng mới). */
export function VoicePickCard({ backend = desktopVoicePick, modulesBusy = false }: { backend?: VoicePickBackend; modulesBusy?: boolean }) {
  const client = useQueryClient();
  const { data: status } = useQuery({ queryKey: KEY, queryFn: () => backend.status() });
  const [busy, setBusy] = useState(false);
  const measuring = status?.state === "measuring";
  useEffect(() => {
    if (!modulesBusy) void client.invalidateQueries({ queryKey: KEY });
  }, [modulesBusy, client]);
  useEffect(() => {
    if (!measuring) return;
    // Thử xong thì giọng mặc định của sách chưa chọn giọng có thể đã đổi: danh sách giọng của trình phát hỏi lại.
    watchVoiceModule(
      KEY.join("/"),
      async () => {
        const next = await backend.status();
        client.setQueryData(KEY, next);
        return next.state === "measuring";
      },
      () => void client.invalidateQueries({ queryKey: ["readaloud", "voices"] }),
    );
  }, [measuring, client, backend]);
  if (!status || status.state === "unsupported") return <MotionRegion />;
  const run = async (action: () => Promise<VoicePickStatus>) => {
    setBusy(true);
    try {
      client.setQueryData(KEY, await action());
      forgetVoices();
      void client.invalidateQueries({ queryKey: ["readaloud", "voices"] });
    } catch (error) {
      toast.error(S.s_chua_doi_duoc_a6c67cde, { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  const measured = status.engines.some((row) => row.measured);
  return (
    <MotionRegion className="space-y-3">
      <h3 className="text-sm font-medium">{S.s_giong_theo_may_bc8b9fff}</h3>
      <p role="status" className="text-sm text-fg-2 text-pretty">{pickHeadline(status)}</p>
      {measuring && <Progress value={(status.done ?? 0) / Math.max(1, status.total ?? 1)} indeterminate={!status.total} size="sm" running label={S.s_dang_thu_cac_giong_872881f6} />}
      {status.engines.length > 0 && (
        <ul className="divide-y divide-line">
          {status.engines.map((row) => {
            const badge = rowBadge(row, status);
            const isChosen = status.chosen === row.engine;
            return (
              <li key={row.engine} className="flex items-center gap-3 py-3">
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-x-2 text-sm font-medium">
                    {engineName(row.engine)}
                    <Reveal when={badge}><span className={isChosen ? "rounded-full bg-accent-soft px-2 py-1 text-caption font-medium text-accent-text" : "text-caption font-medium text-fg-3"}>
                        {badge}
                      </span></Reveal>
                  </span>
                  <span data-motion-live className="mt-1 block text-body-small text-fg-2 text-pretty">{rowNumbers(row, status.liveRtf)}</span>
                </span>
                <Reveal when={!isChosen && !measuring}><Button size="sm" variant="ghost" className="settings-edge-action -my-1 shrink-0" loading={busy} onClick={() => void run(() => backend.choose(row.engine))}>{S.s_dung_giong_nay_903b57aa}</Button></Reveal>
              </li>
            );
          })}
        </ul>
      )}
      {measured && <p className="text-body-small text-fg-3 text-pretty">{pickMethod(status)}</p>}
      {status.engines.length > 0 && !measuring && (
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant={measured ? "ghost" : "primary"} loading={busy} onClick={() => void run(() => backend.measure())}>
            {measured ? S.s_thu_lai_c58d068c : S.s_thu_77e1c0d9}
          </Button>
          {status.override && (
            <Button size="sm" variant="ghost" loading={busy} onClick={() => void run(() => backend.choose(""))}>{S.s_theo_so_do_f3663b51}</Button>
          )}
        </div>
      )}
    </MotionRegion>
  );
}

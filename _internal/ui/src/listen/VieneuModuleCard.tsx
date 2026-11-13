import { S } from "../shared/strings.generated";
import { MotionRegion } from "@/shared/MotionRegion";
import { Fold } from "@/shared/Collapse";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState } from "react";
import { toast } from "@/shared/toast";
import { DialogActions, Button, Dialog, LiveText, Progress, useFocusFollows } from "@/shared/ui";
import { cn } from "@/shared/cn";
import { ErrorDetails } from "@/shared/ErrorDetails";
import { api } from "@/studio/api";
import { formatSize } from "@/shared/format";
import { forgetVoices, switchVoices, watchVoiceModule } from "./readAloudVoice";
import type { ReadAloudVoice } from "./readAloud";
import { desktopVoicePick, VoicePickCard, type VoicePickBackend } from "./VoicePickCard";
import {
  acceleratedNote,
  fastUnsupportedNote,
  benchmarkLabel,
  initialChoices,
  meteredNotice,
  selectionBytes,
  suggestionText,
  toggleChoice,
  lowerFirst,
  moduleAdvice,
  refreshModuleSizes,
  removeAsk,
  tierVoicePrefix,
  VIENEU_COPY,
  vieneuLabel,
  vieneuPercent,
  vieneuSpoken,
  SUPERTONIC_COPY,
  type ModuleCopy,
  type VieneuChoiceId,
  type VieneuStatus,
  type VoiceUse,
} from "./vieneuModule";

import { Reveal } from "../shared/MotionPresence";
const ONLINE_VOICE = "edge:vi-VN-HoaiMyNeural";

/** Nơi mô-đun sống: máy tính hỏi máy chủ cục bộ (`desktopVieneu`, `desktopSupertonic`), điện thoại hỏi plugin ReadAloud (android/SettingsScreen.tsx).
 *  Cùng hình trạng thái. `remove` có trên điện thoại và với cả hai giọng của máy tính (gỡ một giọng để lấy lại chỗ; VieNeu: Turbo, Nano, bản tăng tốc - bộ căn chữ dùng chung
 *  nên ở lại). `start()` không kèm lựa chọn = cập nhật phần đã cũ. */
export interface VieneuBackend {
  status(): Promise<VieneuStatus>;
  start(choices?: VieneuChoiceId[]): Promise<VieneuStatus>;
  measure(): Promise<VieneuStatus>;
  /** Công tắc "Dùng bản tăng tốc" (máy tính). */
  accelerate?(on: boolean): Promise<VieneuStatus>;
  remove?(choice: VieneuChoiceId): Promise<VieneuStatus>;
  /** Huỷ lần tải đang chạy: phần đã tải giữ để lần sau làm tiếp. */
  cancel?(): Promise<VieneuStatus>;
  /** Cuốn nào trong thư viện máy này đang dùng giọng của mô-đun: nút "Gỡ" nói ra trước khi hỏi. Không có (điện thoại: không có sách dùng giọng này) thì chỉ hỏi ngắn. */
  use?(): Promise<VoiceUse>;
  voices(): Promise<ReadAloudVoice[]>;
}

export const desktopVieneu: VieneuBackend = {
  status: () => api<VieneuStatus>("/api/readaloud/vieneu"),
  start: (choices) => api<VieneuStatus>("/api/readaloud/vieneu", { method: "POST", body: choices ? { choices } : {} }),
  measure: () => api<VieneuStatus>("/api/readaloud/vieneu/measure", { method: "POST", body: {} }),
  cancel: () => api<VieneuStatus>("/api/readaloud/vieneu/cancel", { method: "POST", body: {} }),
  accelerate: (on) => api<VieneuStatus>("/api/readaloud/vieneu/accelerate", { method: "POST", body: { on } }),
  remove: (choice) => api<VieneuStatus>("/api/readaloud/vieneu/remove", { method: "POST", body: { choice } }),
  voices: () => api<ReadAloudVoice[]>("/api/readaloud/voices"),
};

export const desktopSupertonic: VieneuBackend = {
  ...desktopVieneu,
  status: () => api<VieneuStatus>("/api/readaloud/supertonic"),
  start: (choices) => api<VieneuStatus>("/api/readaloud/supertonic", { method: "POST", body: choices ? { choices } : {} }),
  measure: () => api<VieneuStatus>("/api/readaloud/supertonic/measure", { method: "POST", body: {} }),
  remove: (choice) => api<VieneuStatus>("/api/readaloud/supertonic/remove", { method: "POST", body: { choice } }),
  cancel: () => api<VieneuStatus>("/api/readaloud/supertonic/cancel", { method: "POST", body: {} }),
  use: () => api<VoiceUse>("/api/studio/supertonic/use"),
};

/** Hai thẻ giọng trên máy của Cài đặt (máy tính và điện thoại) + một dòng khuyên tải cái nào (moduleAdvice): chỉ thẻ được khuyên đánh dấu sẵn.
 *  `vieneuSlot`: mã để nút "Tải giọng VieNeu" ở khối báo mất mạng của trình phát cuộn tới đúng thẻ VieNeu (PlayerViews.PlayerAlert).
 *  `pick`: thẻ "Giọng theo máy" (máy đo các giọng đã tải, chọn giọng mặc định). */
export function LocalVoiceModules({
  vieneu = desktopVieneu,
  supertonic = desktopSupertonic,
  pick = desktopVoicePick,
  onChanged,
}: { vieneu?: VieneuBackend; supertonic?: VieneuBackend; pick?: VoicePickBackend; onChanged?: () => void }) {
  // Cùng khoá truy vấn với thẻ (useModuleStatus): không hỏi thêm lần nào.
  const { data: vieneuStatus } = useQuery({ queryKey: ["readaloud", VIENEU_COPY.key], queryFn: () => vieneu.status() });
  const { data: supertonicStatus } = useQuery({ queryKey: ["readaloud", SUPERTONIC_COPY.key], queryFn: () => supertonic.status() });
  const { advice, preselectSupertonic } = moduleAdvice(vieneuStatus, supertonicStatus);
  return (
    <Fold storageKey="voice.modules" title={S.s_bo_giong_75b79178} summary={moduleActivity(vieneuStatus, supertonicStatus)} bodyClassName="space-y-5 pb-3">
      <Reveal when={advice}><p className="max-w-xl text-body-small text-fg-2 text-pretty">{advice}</p></Reveal>
      <div id="vieneu-module" className="scroll-mt-4">
        <VieneuModuleCard backend={vieneu} onChanged={onChanged} />
      </div>
      <VieneuModuleCard backend={supertonic} copy={SUPERTONIC_COPY} onChanged={onChanged} preselect={preselectSupertonic} />
      <VoicePickCard backend={pick} modulesBusy={moduleActivity(vieneuStatus, supertonicStatus) !== MODULES_IDLE} />
    </Fold>
  );
}

export function moduleActivity(vieneu?: VieneuStatus, supertonic?: VieneuStatus): string {
  const active = [[S.s_vieneu_338b8a9f, vieneu], [S.s_supertonic_b426cb32, supertonic]] as const;
  return active.flatMap(([name, status]) => status?.state === "downloading" ? [`${name} · ${vieneuPercent(status)}%`] : status?.benchmarking ? [S.s_0_dang_do_3db7e929(name)] : []).join(" · ") || MODULES_IDLE;
}

const MODULES_IDLE = S.s_tai_do_va_quan_ly_5d6c8c8d;

/** Trạng thái mô-đun giọng + nhịp hỏi lại khi đang tải / đo (mỗi giây); tải / đo xong thì danh sách giọng của trình phát hỏi lại để giọng mới hiện ngay.
 *  Thẻ trong Cài đặt và khối lỗi của trình phát (VieneuDownload) dùng chung - cùng khoá truy vấn nên hai nơi thấy cùng một lần tải. */
export function useModuleStatus(backend: VieneuBackend, copy: ModuleCopy, onChanged?: () => void) {
  const client = useQueryClient();
  const { data: status } = useQuery({ queryKey: ["readaloud", copy.key], queryFn: () => backend.status() });
  const working = status?.state === "downloading" || Boolean(status?.benchmarking);
  const wasWorking = useRef(false);
  useEffect(() => {
    if (!working) return;
    // Nhịp hỏi lại sống cả phiên (watchVoiceModule), không theo thẻ: tải xong lúc đã rời Cài đặt thì danh sách giọng của trình phát vẫn làm mới.
    watchVoiceModule(
      copy.key,
      async () => {
        const next = await backend.status();
        client.setQueryData(["readaloud", copy.key], next);
        return next.state === "downloading" || Boolean(next.benchmarking);
      },
      () => {
        void client.invalidateQueries({ queryKey: ["readaloud", "voices"] });
        refreshModuleSizes(client);
      },
    );
  }, [working, client, copy.key, backend]);
  useEffect(() => {
    // Mạng đổi (Wi-Fi về, sang dữ liệu di động, mất hẳn): hỏi lại ngay để dòng "đang dùng dữ liệu di động" đúng với mạng lúc này (soát a66).
    const refresh = () => void client.invalidateQueries({ queryKey: ["readaloud", copy.key] });
    window.addEventListener("online", refresh);
    window.addEventListener("offline", refresh);
    return () => {
      window.removeEventListener("online", refresh);
      window.removeEventListener("offline", refresh);
    };
  }, [client, copy.key]);
  useEffect(() => {
    // Vừa tải / đo xong: danh sách giọng + cỡ thẻ kia đã làm mới (watchVoiceModule); báo người dùng thẻ.
    if (wasWorking.current && !working) onChanged?.();
    wasWorking.current = working;
  }, [working, client, onChanged]);
  return { status, working };
}

/** Thẻ của mô-đun "Giọng VieNeu" trong Cài đặt: chọn giọng muốn tải (có "Khuyên dùng" theo máy), thấy đúng dung lượng máy còn thiếu,
 *  bấm mới tải; tải xong máy tự thử vài giây và nói giọng có kịp người nghe không - không kịp thì đề nghị đổi, người dùng bấm mới đổi. */
export function VieneuModuleCard({
  onChanged,
  backend = desktopVieneu,
  copy = VIENEU_COPY,
  preselect = true,
}: { onChanged?: () => void; backend?: VieneuBackend; copy?: ModuleCopy; preselect?: boolean } = {}) {
  const client = useQueryClient();
  const lowerName = lowerFirst(copy.name);
  const { status, working } = useModuleStatus(backend, copy, onChanged);
  const [chosen, setChosen] = useState<VieneuChoiceId[] | null>(null);
  const [busy, setBusy] = useState(false);
  // "Gỡ" một giọng đã tải hỏi trước (soát a94 F2): `use` = cuốn đang dùng nó (undefined: đang hỏi máy chủ; null: không biết).
  const [asking, setAsking] = useState<{ id: VieneuChoiceId; label: string; use: VoiceUse | null | undefined } | null>(null);
  // Trong lúc tải: % không bao giờ lùi (một lần nối lại mà máy chủ tải lại từ đầu file làm số nhảy lùi) và cỡ mỗi lựa chọn đứng yên ở cỡ lúc bấm tải
  // (số "còn thiếu" của lựa chọn co lại mỗi khi một phần dùng chung tải xong: 313 -> 297 MB giữa chừng).
  const peak = useRef(0);
  const sizes = useRef<Record<string, number>>({});
  // Ô chọn giọng: tên = tên giọng + cỡ tải; đoạn giới thiệu dài đọc riêng là mô tả (soát a31: tên ô 300+ chữ).
  const ids = useId();
  // Tải <-> Huỷ thay chỗ nhau: tiêu điểm theo sang nút vừa hiện (soát a67).
  const { ref: followRef, ...follow } = useFocusFollows(status?.state);
  if (!status) return <MotionRegion />;
  const downloading = status.state === "downloading";
  peak.current = downloading ? Math.max(peak.current, status.done) : 0;
  if (!downloading) sizes.current = Object.fromEntries(status.choices.map((choice) => [choice.id, choice.bytes]));
  const shown: VieneuStatus = downloading ? { ...status, done: peak.current } : status;
  const picked = chosen ?? initialChoices(status, preselect);
  const missing = picked.filter((id) => !status.choices.find((choice) => choice.id === id)?.installed);
  const bytes = selectionBytes(status, missing);
  const run = async (action: () => Promise<VieneuStatus>, failure = S.s_chua_tai_duoc_0_0cb3de66(lowerName)) => {
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
    await run(() => backend.remove!(id), S.s_chua_go_duoc_0_f7e62539(lowerName));
    refreshModuleSizes(client); // gỡ giọng cuối dùng phần chung thì phần ấy đi theo: thẻ kia lại phải tải nó
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
    toast.success(suggestion.switchTo === "nano" ? S.s_da_chuyen_sang_giong_vieneu_nano_78fd20a4 : S.s_da_chuyen_sang_giong_truc_tuyen_f1c06742);
  };
  // Bản tăng tốc chỉ là bản chạy nhanh hơn của cùng giọng: sách không cần nó, nên không hỏi cuốn nào.
  const ask = (id: VieneuChoiceId, label: string) => {
    const holdsVoices = id !== "fast" && id !== "supertonic_fast" && backend.use !== undefined;
    setAsking({ id, label, use: holdsVoices ? undefined : null });
    if (holdsVoices) {
      backend.use!().then(
        (use) => setAsking((now) => (now?.id === id ? { ...now, use } : now)),
        () => setAsking((now) => (now?.id === id ? { ...now, use: null } : now)),
      );
    }
  };
  const toggle = (id: VieneuChoiceId, on: boolean) => setChosen(toggleChoice(status, picked, id, on));
  const failed = status.state === "error";
  const canPick = !working && status.state !== "unsupported";
  const suggestion = status.suggestion && !working ? suggestionText(status.suggestion) : null;
  const metered = canPick && missing.length > 0 ? meteredNotice(status, bytes) : null;
  const spoken = vieneuSpoken(shown, copy);
  return (
    <MotionRegion as="div" {...follow} elementRef={followRef} className="space-y-3">
      <h3 tabIndex={-1} data-focus-fallback className="text-sm font-medium">{copy.title}</h3>
      {/* Lỗi tải: không ở đầu thẻ mà ngay trên nút Thử lại, nơi người dùng đang nhìn (soát a66) - xem dưới cùng. */}
      {!failed && (
        <p className="text-sm text-fg-2 text-pretty">
          {/* Đang tải: % đổi liên tục - trình đọc màn hình chỉ đọc mốc 25 % (soát a31 A6), kể cả lúc mạng chập chờn đang thử lại; vừa huỷ thì chỉ đọc
              "Đã huỷ…", không đọc lại cả đoạn giới thiệu (soát a67). */}
          <span role="status">{downloading ? <LiveText shown={vieneuLabel(shown, copy)} spoken={spoken.live} /> : spoken.live}</span>
          {spoken.rest && ` ${spoken.rest}`}
        </p>
      )}
      {status.state === "downloading" && (
        <div className="flex items-center gap-3">
          <Progress value={vieneuPercent(shown) / 100} indeterminate={shown.total <= 0} size="sm" running label={S.s_dang_tai_0_03db34d6(lowerName)} className="flex-1" />
          {backend.cancel && (
            <Button size="sm" variant="ghost" data-focus-next loading={busy} onClick={() => void run(() => backend.cancel!(), S.s_chua_huy_duoc_viec_tai_0_d8afe625(lowerName))}>{S.s_huy_96732485}</Button>
          )}
        </div>
      )}
      <ul className="divide-y divide-line">
        {status.choices.map((choice, index) => {
          const on = picked.includes(choice.id);
          const id = `${ids}-${index}`;
          return (
            <li key={choice.id}>
              <label className={cn("flex items-center gap-3 py-3", canPick && !choice.installed ? "cursor-pointer" : "cursor-default")}>
                <input
                  type="checkbox"
                  className="size-4 shrink-0 accent-[var(--accent)]"
                  checked={choice.installed || on}
                  disabled={!canPick || choice.installed}
                  onChange={(event) => toggle(choice.id, event.target.checked)}
                  aria-labelledby={`${id}-name ${id}-size`}
                  aria-describedby={`${id}-detail`}
                />
                <span className="min-w-0 flex-1">
                  <span id={`${id}-name`} className="flex flex-wrap items-center gap-x-2 text-sm font-medium">
                    {choice.label}
                    <Reveal when={choice.recommended && !choice.installed}><span className="rounded-full bg-accent-soft px-2 py-1 text-caption font-medium text-accent-text">{S.s_khuyen_dung_b1d3dec8}</span></Reveal>
                  </span>
                  <span id={`${id}-detail`} className="mt-1 block text-body-small text-fg-2 text-pretty">{choice.detail}</span>
                </span>
                <span data-motion-live id={`${id}-size`} className="shrink-0 text-xs text-fg-2">
                  {choice.installed ? S.s_da_co_7610f1dd : (downloading ? (sizes.current[choice.id] ?? choice.bytes) : choice.bytes) > 0 ? formatSize(downloading ? (sizes.current[choice.id] ?? choice.bytes) : choice.bytes) : S.s_da_co_san_90ac4add}
                </span>
                <Reveal when={choice.removable && backend.remove && canPick}><Button size="sm" variant="ghost" className="settings-edge-action -my-1 shrink-0" loading={busy} onClick={(event) => { event.preventDefault(); if (choice.installed) ask(choice.id, choice.label); else void remove(choice.id); }}>
                    {choice.installed ? S.s_go_giong_2f8014a9 : S.s_xoa_phan_da_tai_9f9ae26f}
                  </Button></Reveal>
              </label>
            </li>
          );
        })}
      </ul>
      {status.accelerated && backend.accelerate && (
        <div className="space-y-1">
          <label className={cn("flex items-center gap-2 text-sm", canPick ? "cursor-pointer" : "cursor-default")}>
            <input
              type="checkbox"
              className="size-4 accent-[var(--accent)]"
              checked={status.accelerated.on}
              disabled={!canPick || busy}
              onChange={(event) => void run(() => backend.accelerate!(event.target.checked), S.s_chua_doi_duoc_cach_doc_5077e18b)}
              aria-describedby={`${ids}-fast`}
            />{S.s_dung_ban_tang_toc_40b7f3dd}</label>
          <p id={`${ids}-fast`} className="text-body-small text-fg-2 text-pretty">{acceleratedNote(status.accelerated)}</p>
        </div>
      )}
      {fastUnsupportedNote(status) && <p className="text-body-small text-fg-3 text-pretty">{fastUnsupportedNote(status)}</p>}
      {copy.tiers.map((tier) =>
        status.benchmark[tier] ? (
          <p key={tier} className="text-body-small text-fg-2 text-pretty">{benchmarkLabel(tier, status.benchmark[tier]!, status.slowRtf)}</p>
        ) : null,
      )}
      {metered && <p className="text-body-small text-fg-2 text-pretty">{metered}</p>}
      {suggestion && (
        <div className="py-3 text-body-small text-pretty">
          <p>{suggestion.message}</p>
          <Button size="sm" variant="ghost" className="mt-2" loading={busy} onClick={() => void switchTo()}>
            {suggestion.action}
          </Button>
        </div>
      )}
      {failed && (
        <div role="alert" className="text-sm text-danger text-pretty">
          <p data-motion-live>{vieneuLabel(shown, copy)}</p>
          <ErrorDetails technical={status.errorDetail} />
        </div>
      )}
      {canPick && !status.restart && (
        <div className="flex flex-wrap items-center gap-2">
          {status.state === "outdated" && (
            <Button size="sm" variant="ghost" loading={busy} onClick={() => void run(() => backend.start())}>
              {S.s_cap_nhat_0_618a3fa3(formatSize(status.outdatedBytes))}
            </Button>
          )}
          {missing.length > 0 && (
            <Button size="sm" variant={status.state === "missing" ? "primary" : "ghost"} data-focus-next loading={busy} onClick={() => void run(() => backend.start(missing))}>
              {failed ? S.s_thu_lai_c58d068c : bytes > 0 ? S.s_tai_0_3463a4d8(formatSize(bytes)) : S.s_dung_7927ca4e}
            </Button>
          )}
          {(Object.keys(status.benchmark).length > 0 || Boolean(status.accelerated?.problem)) && (
            <Button size="sm" variant="ghost" loading={busy} onClick={() => void run(() => backend.measure())}>{S.s_thu_lai_toc_do_a69ef56d}</Button>
          )}
        </div>
      )}
      <Dialog footer={<DialogActions>
          <Button variant="ghost" onClick={() => setAsking(null)}>{S.s_giu_lai_3c3ba2db}</Button>
          <Button
            variant="danger"
            disabled={asking?.use === undefined}
            onClick={() => {
              const id = asking!.id;
              setAsking(null);
              void remove(id);
            }}
          >{S.s_go_giong_2f8014a9}</Button>
        </DialogActions>}
        open={asking !== null}
        onOpenChange={(open) => !open && setAsking(null)}
        title={S.s_go_0_khoi_may_nay_be8d523b(asking?.label ?? "")}
        description={asking?.use === undefined ? S.s_dang_xem_cuon_nao_con_dung_giong_nay_1a2d4fa1 : removeAsk(asking?.use ?? null)}
      >

      </Dialog>
    </MotionRegion>
  );
}

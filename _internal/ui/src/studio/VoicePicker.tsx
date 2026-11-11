import { S } from "../shared/strings.generated";
import { MoreInfo } from "@/shared/SettingsNav";
import { MotionRegion } from "@/shared/MotionRegion";
import { Fold } from "@/shared/Collapse";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useBackLayer } from "@/shared/backStack";
import { toast } from "@/shared/toast";
import { useClip } from "@/listen/clip";
import { cn } from "@/shared/cn";
import { formatNumber } from "@/shared/format";
import { SelectionMark, Button, Dialog, Progress, ChoiceRow, Skeleton, Vu, InlineError } from "@/shared/ui";
import { OnComputerOnly } from "@/shared/OnComputerOnly";
import { api, urls } from "./api";
import { useAppInfo } from "./data";
import { refreshAfterDecision, UNDO_MS, undoAction } from "./decisions";
import { voiceWas, warnElsewhere } from "./elsewhere";
import { modulePercent } from "./musicLocal";
import { groupByEngine, moduleNote, plainGroupLabels, sharedText, takenText, type EngineModuleStatus, type EngineVoice } from "./voiceEngines";
import { useVoiceTry } from "./VoiceTry";
import { byGender, rerecordText, type GenderFilter, type Rerecord } from "./voiceTryText";
import { useFadeScroller } from "@/shared/scrollFade";

// "Đổi giọng" một nhân vật (webui/voice_picker.py): mọi giọng dùng được cho nhân vật, nghe thử từng giọng, giọng đang dùng,
// giọng máy gợi ý cho từng giới, và ai đang dùng giọng ấy cùng mấy chương. Chọn xong đi đúng đường của thẻ "Nam hay nữ"
// (POST /voice): dây chuyền áp ở ranh giới chương kế tiếp; hai người chung preset nghe cùng giọng,
// câu đã thu của người ấy được thu lại. Không phải dừng sách. Giọng nhóm theo máy đọc: VieNeu (mọi giọng phân vai
// tự động) rồi máy khác chỉ chọn tay (ZeroTTS, Supertonic - tải thêm một lần, nút tải ngay trong hộp). Soát UX Studio mục 13:
// mỗi giọng nghe được cả câu mẫu chung (▶) lẫn một câu của chính nhân vật đọc bằng giọng ấy (VoiceTry.tsx), lọc Nam / Nữ / Tất
// cả, và hộp nói trước đổi giọng sẽ thu lại bao nhiêu câu, hết chừng bao lâu. Người kể dùng chính hộp này (soát UX a23, B21:
// voice_picker.narrator_choices) - giọng kể chuyện của danh mục, giọng nhân vật đang giữ thì không chọn được, không hỏi giới.

type Gender = "male" | "female";
const GENDER_WORD: Record<Gender, string> = { male: "nam", female: S.s_nu_316c30fd };
/** Nút cuối hàng cùng một bề ngang ("Chọn" hay "Người kể dùng"): cột tên giọng của mọi hàng cùng mép phải (soát 25-10: lệch 12 px). */
const ACTION_WIDTH = "h-9 min-h-9 w-[7.5rem] shrink-0";

interface VoiceOption extends EngineVoice {
  /** Khoá giọng - cái duy nhất máy chủ nhận (POST /voice, /voice/preview, /media/voices); `name` chỉ để hiện cho người nghe. */
  key: string;
  gender: Gender;
  genderLabel: string;
  region: string;
  style: string;
  preview: boolean;
  current: boolean;
  /** Giọng người nghe đã chọn mà chưa vào sách. */
  pending: boolean;
  suggested: boolean;
  /** Chất giọng của giọng máy khác ("Nữ · Trưởng thành · Rõ ràng"); rỗng với VieNeu (đã có miền + phong cách). */
  description: string;
  /** Hộp người kể: nhân vật đang giữ (hay đã chọn) giọng này - không chọn được. Hộp nhân vật: người kể đã chọn nó. */
  takenBy?: string[];
  /** Lời giải thích khi `takenBy` không phải "nhân vật đang giữ" (hộp nhân vật: giọng người kể đang chờ đổi sang). */
  takenNote?: string;
}

interface VoiceChoices {
  character: { value: string; label: string; gender: string; lines: number; chapters: number };
  current: string;
  /** Lựa chọn chưa vào sách (tên giọng nó sẽ thành; "" khi chưa biết) - bỏ được bằng `requestedAt` như "Hoàn tác". */
  pending: { name: string; requestedAt: number } | null;
  voices: VoiceOption[];
  /** Mô-đun tải thêm của máy đọc khác, theo tên máy. */
  modules?: Record<string, EngineModuleStatus>;
  /** Câu "Nghe thử bằng câu của sách" sẽ đọc; null: người này chưa có câu nào - chỉ có câu mẫu chung. */
  tryLine?: { segmentId: number; text: string } | null;
  /** Đổi giọng là thu lại mọi câu đã thu của người này. */
  rerecord?: Rerecord;
}

/** `withGender`: lọc "Tất cả" - giọng nam và nữ chung một danh sách, nên nói giới ra. */
function voiceMeta(voice: VoiceOption, withGender = false): string {
  const parts = voice.description ? [voice.description] : [voice.region ? S.s_mien_0_ea8d625b(voice.region) : "", voice.style];
  // Chất giọng của máy khác đã mở đầu bằng giới ("Nữ · Trưởng thành"): không nói hai lần.
  const about = [withGender && !voice.description ? voice.genderLabel : "", ...parts].filter(Boolean).join(" · ");
  // Giọng đang dùng không ai dùng chung: nút "Đang dùng" bên phải đã nói, dòng phụ không nhắc lại "đang đọc cho người này".
  const alone = voice.current && !voice.sharedWith.length && !voice.otherUsers;
  const use = voice.takenNote ?? (voice.takenBy?.length ? takenText(voice.takenBy) : alone ? "" : sharedText(voice, voice.current));
  return [about, use].filter(Boolean).join(" · ");
}

/** Tên nhóm của một máy đọc, và - khi máy chưa có giọng ấy - lời nhắn + nút tải (tiến độ hỏi lại mỗi giây). */
function EngineHeader({ engine, label, status, onReady }: { engine: string; label: string; status?: EngineModuleStatus; onReady: () => void }) {
  const client = useQueryClient();
  // Studio từ xa: tải giọng là việc của máy tính (GET / POST /api/studio/... không qua) - chỉ nói tải ở đâu, không nút, không hỏi tiến độ.
  const remote = Boolean(useAppInfo().data?.remote);
  const { data } = useQuery({
    queryKey: ["engine-module", engine],
    queryFn: () => api<EngineModuleStatus>(`/api/studio/${engine}`),
    initialData: status,
    enabled: status !== undefined && !remote,
    refetchInterval: (query) => (query.state.data?.state === "downloading" ? 1000 : false),
  });
  const current = data ?? status;
  useEffect(() => {
    if (status && status.state !== "ready" && current?.state === "ready") onReady();
  }, [current?.state, status, onReady]);
  const start = useMutation({
    mutationFn: () => api<EngineModuleStatus>(`/api/studio/${engine}`, { method: "POST", body: {} }),
    onSuccess: (next) => client.setQueryData(["engine-module", engine], next),
    onError: (failure: Error) => toast.error(S.s_chua_tai_duoc_giong_728a140d, { description: failure.message }),
  });
  const cancel = useMutation({
    mutationFn: () => api<EngineModuleStatus>(`/api/studio/${engine}/cancel`, { method: "POST", body: {} }),
    onSuccess: (next) => client.setQueryData(["engine-module", engine], next),
    onError: (failure: Error) => toast.error(S.s_chua_huy_duoc_viec_tai_giong_636cbb4a, { description: failure.message }),
  });
  const note = moduleNote(current);
  return (
    <MotionRegion as="div" className="sticky top-0 z-10 bg-panel pb-1 pt-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-semibold tracking-wide text-fg-3">{label}</span>
        {current && ["missing", "error", "outdated"].includes(current.state) &&
          (remote ? (
            <OnComputerOnly verb={S.s_tai_giong_d6f57d0b} />
          ) : (
            <Button size="sm" variant="ghost" loading={start.isPending} onClick={() => start.mutate()}>
              {current.state === "error" ? S.s_thu_lai_c58d068c : current.damaged ? S.s_sua_giong_df27f611 : S.s_tai_giong_d6f57d0b}
            </Button>
          ))}
      </div>
      {note && <p className={cn("mt-0.5 text-xs", current?.state === "error" ? "text-danger" : "text-fg-2")}>{note}</p>}
      {current?.state === "downloading" && (
        <div className="mt-1 flex items-center gap-3">
          <Progress size="xs" running value={modulePercent(current) / 100} indeterminate={current.total <= 0} label={note ?? ""} className="flex-1" />
          {current.cancellable && !remote && (
            <Button size="sm" variant="ghost" loading={cancel.isPending} onClick={() => cancel.mutate()}>{S.s_huy_96732485}</Button>
          )}
        </div>
      )}
    </MotionRegion>
  );
}

export function PreviewButton({ voice }: { voice: VoiceOption }) {
  const clip = useClip();
  const id = `voice-${voice.name}`;
  const active = clip.current === id;
  if (!voice.preview) return <span className="size-9 shrink-0" aria-hidden />;
  return (
    <button
      type="button"
      onClick={() => clip.toggle(id, urls.voice(voice.key))}
      aria-label={active ? S.s_dung_nghe_thu_41a2925b : S.s_nghe_thu_giong_0_d16e376e(voice.name)}
      className={cn(
        "grid size-9 shrink-0 place-items-center rounded-full transition-colors",
        active ? "text-accent-text" : "text-fg-2 hover:bg-hover hover:text-fg ",
      )}
    >
      <MotionRegion as="span" className="grid size-4 place-items-center">{active && clip.loading ? <Loader2 className="size-4 animate-spin" /> : active ? <Vu className="h-3" /> : <Play className="size-3.5 translate-x-[1px]" fill="currentColor" strokeWidth={0} />}</MotionRegion>
    </button>
  );
}

export function VoicePicker({
  bookId,
  person,
  onClose,
}: {
  bookId: string;
  person: { name: string; displayName: string } | null;
  onClose: () => void;
}) {
  const scrollFade = useFadeScroller<HTMLDivElement>();
  const client = useQueryClient();
  const clip = useClip();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["voice-choices", bookId, person?.name],
    queryFn: () => api<VoiceChoices>(`/api/books/${bookId}/voices?character=${encodeURIComponent(person!.name)}`),
    enabled: person !== null,
  });
  const [gender, setGender] = useState<GenderFilter | null>(null);
  useEffect(() => setGender(null), [person?.name]);
  const currentGender = data?.voices.find((voice) => voice.current)?.gender;
  const shown: GenderFilter = gender ?? currentGender ?? (data?.character.gender === "female" ? "female" : "male");
  const tryVoice = useVoiceTry(bookId);
  const close = () => {
    clip.stop();
    onClose();
  };
  // Tên như tiêu đề hộp ("Oliver"), không phải khoá sổ in hoa ("OLIVER") - soát UX 30-09.
  const name = person?.displayName || data?.character.label || "";
  const narrator = data?.character.value === "NARRATOR";
  // Giọng khác giới với nhân vật: hỏi ngay trong hộp trước khi ghi (soát UX a13 #4) - đổi giọng khác giới là đổi luôn giới của người ấy.
  const [crossing, setCrossing] = useState<VoiceOption | null>(null);
  const crossingBox = useRef<HTMLDivElement>(null);
  const crossingButton = useRef<HTMLElement | null>(null);
  useBackLayer(person !== null && crossing !== null, () => setCrossing(null), crossingBox, crossingButton);
  useEffect(() => setCrossing(null), [person?.name]);
  const save = useMutation({
    mutationFn: ({ voice, withGender }: { voice: VoiceOption; withGender: boolean }) =>
      api<{ requestedAt: number; elsewhere?: { voice: string; gender: string } }>(`/api/books/${bookId}/voice`, {
        method: "POST",
        // Có `gender` thì giới ghi cùng giọng (cùng đường overrides `voices`): dòng "chờ áp dụng" ở tab Nhân vật hiện giới mới.
        // `seen`: mốc của lựa chọn đang chờ hộp này thấy (0 = không có) - máy/cửa sổ khác vừa chọn khác thì được hỏi (uxfix28 A).
        body: { character: data!.character.value, preset: voice.key, ...(withGender ? { gender: voice.gender } : {}), seen: data!.pending?.requestedAt ?? 0 },
      }),
    onSuccess: ({ requestedAt, elsewhere }, { voice, withGender }) => {
      // Dòng nhân vật hiện "Chờ áp dụng" ngay (store.pending_voices), không đợi lần làm mới sau 60 giây.
      refreshAfterDecision(client, bookId);
      const character = data!.character;
      const undo = undoAction(
        client,
        bookId,
        "voice",
        [{ character: character.value, requestedAt, keep: false }],
        // Không nói tên giọng cũ: người ấy có thể đang có một giọng chờ áp khác, và hoàn tác trả về đúng giọng chờ ấy.
        S.s_giong_0_cua_1_tro_lai_nhu_truoc_khi_doi_333ca8fe(withGender ? S.s_va_gioi_c20b236e : "", name),
      );
      // Không chặn: "Lấy của máy kia" là hoàn tác lần ghi này - lựa chọn của máy kia (yêu cầu nó thay) trở lại.
      if (elsewhere) warnElsewhere(1, voiceWas(elsewhere), undo.onClick);
      // Chọn nhầm giọng trong danh sách dài: "Hoàn tác" như thẻ giọng trong hộp việc (studio/decisions.ts).
      toast.success(S.s_da_ghi_0_doc_bang_giong_1_2_27a9c30c(name, voice.name, withGender ? S.s_va_la_0_3ac4fdbc(GENDER_WORD[voice.gender]) : ""), {
        action: undo,
        duration: UNDO_MS,
      });
      close();
    },
    onError: (failure: Error) => toast.error(S.s_chua_doi_duoc_giong_5b5ed91f, { description: failure.message }),
  });
  // Bỏ lựa chọn chưa vào sách - cùng đường "Hoàn tác" (POST /voice withdraw), dùng được bất cứ lúc nào trước khi máy áp.
  const keep = useMutation({
    mutationFn: (pending: { name: string; requestedAt: number }) =>
      api<{ undone: number }>(`/api/books/${bookId}/voice`, {
        method: "POST",
        body: { character: data!.character.value, withdraw: true, requestedAt: pending.requestedAt },
      }),
    onSuccess: (_answer, pending) => {
      refreshAfterDecision(client, bookId);
      toast.success(pending.name ? S.s_da_bo_lua_chon_0_55b306ea(pending.name) : S.s_da_bo_lua_chon_giong_1aff3c76);
      close();
    },
    onError: (failure: Error) => toast.error(S.s_chua_bo_duoc_lua_chon_c0844396, { description: failure.message }),
  });
  // Chọn một giọng: cùng giới (hay chưa biết giới) ghi luôn; khác giới thì hỏi trước. Người kể không có giới để đổi.
  const choose = (voice: VoiceOption) => {
    const known = data?.character.gender;
    if (!narrator && (known === "male" || known === "female") && known !== voice.gender) {
      crossingButton.current = document.activeElement as HTMLElement;
      setCrossing(voice);
    }
    else save.mutate({ voice, withGender: false });
  };
  const voices = byGender(data?.voices ?? [], shown);
  const groups = groupByEngine(voices);
  const groupLabels = plainGroupLabels(groups);
  const reload = () => client.invalidateQueries({ queryKey: ["voice-choices", bookId, person?.name] });
  return (
    <Dialog
      open={person !== null}
      onOpenChange={(open) => {
        if (!open) close();
      }}
      title={S.s_giong_cua_0_96e5ead4(person?.displayName ?? "")}
      description={
        data
          ? S.s_0_cau_o_1_chuong_dang_doc_bang_2_51f984c1(formatNumber(data.character.lines), data.character.chapters, data.current || S.s_chua_co_giong_93574f94)
          : undefined
      }
      width="max-w-[560px]"
    ><MotionRegion>
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }, (_, index) => (
            <Skeleton key={index} className="h-12 rounded-cover" />
          ))}
        </div>
      ) : error || !data ? (
        <InlineError message={S.s_ban_hay_kiem_tra_ket_noi_roi_tai_lai_danh_a542de69} onRetry={() => void refetch()} />
      ) : (
        <>
          {data.pending && (
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
              <span className="text-pretty">{S.s_cho_ap_dung_doi_sang_d280f3e4}<span className="font-medium">{data.pending.name || S.s_giong_khac_95c40f55}</span>
              </span>
              <Button size="sm" variant="ghost" loading={keep.isPending} disabled={save.isPending} onClick={() => keep.mutate(data.pending!)}>{S.s_giu_d3777f80}{data.current || S.s_giong_dang_dung_4e5460a7}
              </Button>
            </div>
          )}
          {data.rerecord && <p className="mb-2 text-sm text-pretty text-fg-2">{rerecordText(name, data.rerecord)}</p>}
          {crossing && (
            <div ref={crossingBox} role="alert" className="mb-3 py-2 text-sm">
              <p className="text-pretty">
                {name}{S.s_dang_la_8bd58298}{GENDER_WORD[data.character.gender as Gender]}{S.s_giong_b5e0ec31}{crossing.name}{S.s_la_giong_a07d5815}{GENDER_WORD[crossing.gender]}{S.s_doi_ca_gioi_cua_a6dfa69e}{name}{S.s_thanh_3acad264}{GENDER_WORD[crossing.gender]}?
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <Button size="sm" variant="primary" loading={save.isPending} onClick={() => save.mutate({ voice: crossing, withGender: true })}>{S.s_doi_giong_va_gioi_21985f64}</Button>
                <Button size="sm" variant="ghost" disabled={save.isPending} onClick={() => setCrossing(null)}>{S.s_giu_nhu_cu_4fecf996}</Button>
              </div>
            </div>
          )}
          <ChoiceRow<GenderFilter>
            label={S.s_loc_giong_theo_gioi_93d59ab4}
            value={shown}
            onChange={setGender}
            options={[
              { value: "male", label: S.s_nam_22dd59c8 },
              { value: "female", label: S.s_nu_e15bc11c },
              { value: "all", label: S.s_tat_ca_49c73a31 },
            ]}
          />
          <div className="mt-2 space-y-0.5">
            <p className="text-xs text-pretty text-fg-3">
              {data.tryLine
                ? S.s_nut_sach_doc_cau_cua_0_doc_mau_chung_54b8a732(name)
                : S.s_0_chua_co_cau_nao_de_doc_thu_nut_la_cau_ma_8646f98e(name)}
            </p>
            {tryVoice.note}
          </div>
          <div ref={scrollFade.ref} style={scrollFade.style} className="focus-scroll voice-picker-scroll -mr-1 mt-3 max-h-[min(60vh,460px)] overflow-y-auto pr-1">
            {groups.map((group, index) => (
              <Fold key={group.engine} storageKey={`voice-picker.${group.engine}`} title={groupLabels[index]} summary={S.s_0_giong_7be1af23(group.voices.length)} defaultOpen={groups.length === 1} bodyClassName="px-2 pb-2">
                {groups.length > 1 || group.engine !== "vieneu" ? (
                  <EngineHeader engine={group.engine} label={groupLabels[index]} status={data.modules?.[group.engine]} onReady={reload} />
                ) : null}
                <ul className="space-y-1">
            {group.voices.map((voice) => (
              <li key={voice.key} className={cn("flex items-center gap-3 rounded-cover px-2 py-2", voice.current ? "text-accent-text" : "hover:bg-hover")}>
                <PreviewButton voice={voice} />
                {data.tryLine &&
                  tryVoice.button({ character: data.character.value, preset: voice.key }, voice.name, {
                    fallbackUrl: voice.preview ? urls.voice(voice.key) : undefined,
                    compact: true,
                    disabled: !voice.installed,
                  })}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <SelectionMark selected={voice.current} /><span className={cn("font-medium", voice.current ? "text-accent-text" : voice.takenBy?.length && "text-fg-2")}>{voice.name}</span>
                    {/* Viên "Đang dùng" chỉ khi nút bên phải là "Giữ giọng này"; còn lại nút đã nói đúng chữ ấy (soát 25-10: nói hai lần một hàng). */}
                    {voice.current && data.pending && <span className="rounded-full bg-panel px-2 py-px text-[0.6875rem] font-medium text-accent-text">{S.s_dang_dung_275ca289}</span>}
                    {voice.pending && !voice.current && (
                      <span className="rounded-full bg-warning-soft px-2 py-px text-[0.6875rem] font-medium text-warning">{S.s_cho_ap_dung_77a52853}</span>
                    )}
                    {voice.suggested && !voice.current && !voice.pending && (
                      <span className="rounded-full bg-info-soft px-2 py-px text-[0.6875rem] font-medium text-info">{S.s_may_goi_y_1e7f4cfa}</span>
                    )}
                  </div>
                  <div className={cn("mt-0.5 text-xs", voice.sharedWith.length && !voice.takenBy?.length ? "text-warning" : "text-fg-2")}>
                    {voiceMeta(voice, shown === "all")}
                  </div>
                </div>
                {voice.current && data.pending ? (
                  // Đã chọn giọng khác mà chưa vào sách: giọng đang dùng chọn lại được - là bỏ lựa chọn kia.
                  <Button size="sm" variant="ghost" className={ACTION_WIDTH} loading={keep.isPending} disabled={save.isPending} onClick={() => keep.mutate(data.pending!)}>{S.s_giu_giong_nay_2bc52cde}</Button>
                ) : (
                  <Button
                    size="sm"
                    className={ACTION_WIDTH}
                    variant={voice.suggested && !voice.current && !voice.pending ? "primary" : "ghost"}
                    disabled={voice.current || voice.pending || !voice.installed || Boolean(voice.takenBy?.length) || save.isPending || keep.isPending}
                    onClick={() => choose(voice)}
                  >
                    {voice.current ? S.s_dang_dung_275ca289 : voice.pending ? S.s_da_chon_7f7e38b3 : voice.takenNote ? S.s_nguoi_ke_dung_e9ddd95f : voice.takenBy?.length ? S.s_nhan_vat_dung_0b0df351 : S.s_chon_1171ca97}
                  </Button>
                )}
              </li>
            ))}
                </ul>
              </Fold>
            ))}
          </div>
          {narrator ? (
            <div className="mt-3 text-xs text-fg-3">
              <p>{S.s_doi_giong_se_thu_lai_loi_ke_3d190924}</p>
              <MoreInfo>{S.s_nguoi_ke_can_giong_rieng_nen_khong_chon_gi_c145ea51}</MoreInfo>
            </div>
          ) : (
            <div className="mt-3 text-xs text-fg-3">
              <p>{S.s_nghe_thu_truoc_khi_doi_giong_9d5e986a}</p>
              <MoreInfo label={S.s_dung_chung_giong_ccea62a1}>{S.s_giong_them_co_the_khien_hai_nhan_vat_nghe_ec79eba6}</MoreInfo>
            </div>
          )}
        </>
      )}
    </MotionRegion></Dialog>
  );
}

import { S } from "../shared/strings.generated";
import { MotionRegion } from "@/shared/MotionRegion";
import { AnimatedRows, MotionPresence } from "@/shared/MotionPresence";
import { Collapse } from "@/shared/Collapse";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AudioLines, Check, Pause, Play, RotateCcw, Search, UserPlus } from "lucide-react";
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { toast } from "@/shared/toast";
import { useClip } from "@/listen/clip";
import { cn } from "@/shared/cn";
import { formatNumber } from "@/shared/format";
import { DialogActions, DecisionButton, Button, ContentSkeleton, Dialog, EmptyState, FilterRow, InlineError, Kbd, ChoiceRow, Tooltip } from "@/shared/ui";
import { api, suggestionOf, urls, type BookSummary } from "./api";
import { ReadingProblem } from "./ReadingProblem";
import { retryUnlessGone } from "./polling";
import { useTryReading } from "./TryReading";
import { isOpenWork } from "./precast";
import { applyWhen, PENDING_NOTE, refreshAfterDecision, UNDO_MS, undoAction } from "./decisions";
import { seenFor, warnElsewhere } from "./elsewhere";
import { examplesPage, keepRequests, moreText, pickedLines, pickNote, toggleLine, type LineRef, type SpeakerRequest } from "./minorGroups";
import { decidedTitle, inboxLead, markNames, midSentence, narratorButtons, sentence } from "./workText";
import { useProducingRefetch } from "./liveRefresh";
import { useCardFocus, type CardFocusEnds } from "./useCardFocus";
import type { WorkLists } from "./workFocus";
import { workKeyHandler } from "./workKeys";

// "Việc cần duyệt" (docs/STUDIO_REVIEW.md, webui/work_items.py): chỗ máy nghi ngờ, xếp theo lợi trên mỗi lần bấm. Máy đã tự
// quyết và dây chuyền KHÔNG chờ ai - đây là nơi người sửa ít nhất mà được nhiều nhất. Cách đọc tên sửa được ngay trên thẻ
// (bước 2): mong muốn ghi vào overrides.json, dây chuyền áp ở ranh giới chương và thu lại những câu có tên ấy.

export type WorkKind = "speaker" | "caller" | "turn" | "gender" | "vocative" | "alias" | "bracket" | "shared-voice" | "pronunciation" | "unnamed" | "audio" | "narrator" | "voice-wish" | "snap" | "teller-voice" | "teller-thought" | "refused";

interface WorkExample {
  segmentId: number;
  chapterId: number;
  chapterTitle: string;
  seq: number;
  text: string;
  speaker: string;
  /** Câu đã có bản thu (nghe được); câu chưa thu chỉ là ví dụ ngữ cảnh. */
  hasAudio: boolean;
  /** Câu mà lựa chọn trên thẻ sẽ đổi người nói (thẻ lượt đối đáp: các câu xen kẽ). */
  changes?: boolean;
  /** Thẻ vai phụ cả cuốn: mã câu, để bỏ chọn từng câu. */
  stableId?: string;
  /** Thẻ “Ai nói câu này”: câu liền trước và liền sau (mọi người nói) làm ngữ cảnh để quyết ai nói. */
  before?: string;
  after?: string;
  /** Thẻ “Người này có phải X?”: câu lời kể quanh câu được hỏi (không ai “nói” nó), và tên ứng viên để tô trong câu. */
  narration?: boolean;
  names?: string[];
}

export interface WorkItem {
  kind: WorkKind;
  key: string;
  title: string;
  problem: string;
  affected: number;
  doubt: number;
  score: number;
  options: string[];
  current: string;
  examples: WorkExample[];
  /** Việc cách đọc tên: chữ gốc trong sách, và cách đọc người nghe đã ghi mà dây chuyền chưa áp (nếu có). */
  surface?: string;
  requested?: string | null;
  /** Đã quyết mà chỉ áp khi làm lại sách (thẻ người kể của đoạn đã phân tích xong): không tính vào "chờ áp dụng", xếp cuối. */
  redoOnly?: boolean;
  /** Việc gán người nói ("Ai nói câu này", người gọi, vai phụ không tên): các câu (mã ổn định + băm chữ, để yêu cầu
   *  không áp nhầm câu đã đổi) và các lựa chọn bấm được. */
  lines?: { stableId: string; textSha256: string }[];
  /** Thẻ chuỗi lượt đối đáp: mọi câu của chuỗi - phạm vi "Cả chuỗi" thay cho các câu xen kẽ trong `lines`. Thẻ 『』: mọi
   *  câu 『』 của dự án - phạm vi "Cả cuốn", và quy ước đi theo các phần sau. */
  allLines?: { stableId: string; textSha256: string }[];
  /** Nhãn hai phạm vi khi khác "Câu xen kẽ / Cả chuỗi" (thẻ 『』: "Chương này / Cả cuốn"). */
  scopeLabels?: [string, string];
  /** `name`: tên người khi nhãn nút không phải là tên ("Gộp vào Kati"). `sampleId`: một câu đã thu của người ấy - nghe giọng
   *  ngay cạnh nút trước khi chọn (như tab Nhân vật). */
  choices?: { label: string; value: string; name?: string; sampleId?: number; samplePreset?: string }[];
  currentValue?: string;
  /** Người đang được ghi cho từng câu khi thẻ được dựng ("" = chưa ai quyết): gửi lại làm `seen` (soát a27 lỗi 4). */
  seen?: Record<string, string>;
  /** Nhãn nút giữ nguyên khi "Giữ <người đang nói>" không đúng nghĩa (bí danh: "Hai người khác nhau"). */
  keepLabel?: string;
  /** `false`: máy không đề xuất ai (thẻ theo độ tin logprob chỉ nói máy chưa chắc) - chip đầu không tô như gợi ý của máy. */
  suggested?: boolean;
  /** Thẻ bí danh: tên được hỏi, để hiển thị ("“Thiên Biến Vạn Hóa” là Krai") - `current` là nhãn lựa chọn, không phải tên. */
  subject?: string;
  /** Việc giọng/giới của nhân vật ("Nam hay nữ", "Chung giọng"): mỗi lựa chọn là một yêu cầu POST /voice; giữ nguyên thì
   *  ghi yêu cầu rỗng cho từng người trong `keepCharacters` (thẻ thôi hỏi). */
  voiceChoices?: VoiceChoice[];
  keepCharacters?: string[];
  /** Thẻ "Yêu cầu chưa được": yêu cầu của bạn máy đã xét mà không làm được - phần, khoá và mốc để bỏ đúng yêu cầu ấy. */
  refused?: { section: string; key: string; requestedAt: number };
  /** Thẻ "Giọng chưa đổi được": người có giọng đã chọn mà không áp được - nút "Chọn giọng khác…" mở hộp "Đổi giọng" của họ. */
  pickVoice?: { name: string; displayName: string };
  /** Chương của các câu thẻ sẽ đổi (hay của câu ví dụ) - "Duyệt trước khi thu" hỏi trước thẻ ở chương sắp thu. */
  chapters?: number[];
  /** Thẻ vai phụ không tên cả cuốn: `examples` là các câu của nhóm, người nghe bỏ chọn câu không phải trước khi chọn người. */
  pick?: boolean;
  /** Thẻ `pick` có nhóm lớn: máy chỉ gửi vài câu đầu trong `examples`, đây là tổng số câu - "Xem thêm" lấy tiếp theo trang
   *  (GET /work/examples). Không có (bản chụp trong file dự án, nhóm nhỏ): `examples` đã đủ. */
  examplesTotal?: number;
  /** Giữ nguyên thẻ nhóm: mỗi vai giữ người của nó - một yêu cầu cho mỗi vai. */
  keepGroups?: SpeakerRequest[];
  /** Thẻ vai phụ cả cuốn: tên đề nghị cho "là một người mới tên “…”" (cả nhóm thành MỘT người có giọng riêng). */
  newPerson?: string;
  suggestedName?: string;
  /** Chữ của nút người mới khi thẻ hỏi theo kiểu có / không ("Không, là người khác" - thẻ hai cách viết một tên). */
  newPersonLabel?: string;
  /** Thẻ đã quyết: cách rút đúng lần bấm ấy (`POST /{endpoint}` với `withdraw`) - nút "Hoàn tác" của mục "Đã quyết". */
  undo?: { endpoint: string; decisions: Record<string, unknown>[] };
  /** Thẻ người kể của đoạn (webui/narrator_cards.py): đoạn nào, người kể của sách, ứng viên, và điều cần biết trước khi bấm
   *  (đoạn đã phân tích xong thì chỉ áp khi làm lại sách). */
  narratorSection?: {
    chapterIndex: number;
    fromSeq: number;
    toSeq: number;
    narrator: string;
    appliesNote: string;
    choices: { label: string; value: string }[];
    /** Đoạn mở bằng dòng tiêu đề góc nhìn ("Góc nhìn của Mai"): dòng ấy và người kể nó gọi ("" = ngôi thứ ba). */
    heading?: { line: string; narrator: string; label: string };
  };
}

interface VoiceChoice {
  label: string;
  character: string;
  gender?: string;
  preset?: string;
  avoid?: string;
  /** Cái giá của lựa chọn: "giữ giọng đang đọc", "đổi giọng, thu lại 12 câu". */
  note?: string;
  /** Câu báo khi đã ghi: "Noah là nữ", "đổi giọng Rhine". */
  done?: string;
  /** Máy khuyên lựa chọn này (tách hai người chung giọng: đổi người ít câu hơn). Thẻ giới không khuyên gì. */
  recommended?: boolean;
}

export interface WorkView {
  items: WorkItem[];
  counts: Partial<Record<WorkKind, number>>;
}

const KIND_LABEL: Record<WorkKind, string> = {
  speaker: S.s_ai_noi_cau_nay_0e00a5c7,
  caller: S.s_nguoi_goi_ngoai_khung_03677986,
  turn: S.s_luot_doi_dap_a2c055e0,
  pronunciation: S.s_cach_doc_ten_1c46e75d,
  gender: S.s_nam_hay_nu_0167dbc6,
  vocative: S.s_goi_hay_noi_305521d7,
  alias: S.s_mot_nguoi_hai_ten_9293d8ab,
  bracket: S.s_loi_trong_c682376b,
  "shared-voice": S.s_chung_giong_a58df5cc,
  unnamed: S.s_vai_phu_khong_ten_6395f0d2,
  audio: S.s_ban_thu_loi_753aaed5,
  narrator: S.s_nguoi_ke_cua_doan_b218398e,
  "voice-wish": S.s_giong_chua_doi_duoc_2617419d,
  snap: S.s_ten_viet_khac_f05542f3,
  "teller-voice": S.s_giong_loi_dan_f8f4ea1e,
  "teller-thought": S.s_noi_tam_nguoi_ke_0c360f80,
  refused: S.s_yeu_cau_chua_duoc_3c62dd70,
};

const PAGE = 40;

export function useWork(bookId: string, enabled = true) {
  const refetchInterval = useProducingRefetch(bookId); // sách đang chạy: việc mới sinh ra theo chương, hộp tự thấy (soát a90 V4)
  return useQuery({
    queryKey: ["work", bookId],
    queryFn: () => api<WorkView>(`/api/books/${bookId}/work`),
    enabled: Boolean(bookId) && enabled,
    refetchInterval,
    staleTime: 60_000,
    retry: retryUnlessGone,
    retryOnMount: false, // sổ lỗi: mỗi chỗ gắn thêm một người quan sát không được kéo thêm một lượt hỏi
  });
}

// Việc còn chờ người duyệt: một phép đếm cho hộp việc, màn duyệt trước khi thu và con số điện thoại nhận (precast.isOpenWork).
export { isOpenWork };

/** Số việc cần làm cho nhãn của tab. `fromList`: danh sách đầy đủ đang được tải/mở (tab Việc cần duyệt, màn Duyệt trước khi thu) thì đếm
 *  từ chính nó; không thì chỉ hỏi con số (`?count=1`) - trang dự án 400 chương từng tải 9,5 MB danh sách chỉ để hiện một con số, và tải
 *  lại sau MỖI quyết định. Khoá nằm dưới ["work", sách] nên mọi chỗ làm mới danh sách cũng làm mới con số. `enabled: false`: hoãn hỏi
 *  (tab đang mở cần máy chủ trước). */
export function useWorkCount(bookId: string, fromList = false, enabled = true) {
  const { data: list } = useWork(bookId, fromList && enabled);
  const refetchInterval = useProducingRefetch(bookId);
  const { data: counted } = useQuery({
    queryKey: ["work", bookId, "count"],
    queryFn: () => api<{ count: number }>(`/api/books/${bookId}/work?count=1`),
    enabled: Boolean(bookId) && !fromList && enabled,
    refetchInterval,
    staleTime: 60_000,
    retry: retryUnlessGone,
    retryOnMount: false,
  });
  // Việc đã quyết (đang chờ áp dụng) không còn là việc cần làm - soát UX 29-09: số không giảm sau khi quyết.
  if (fromList && list) return list.items.filter(isOpenWork).length;
  return counted?.count ?? 0;
}

/** Việc đã quyết chờ gì: sách đang dở thì tự áp khi chạy tiếp; sách ĐÃ XONG không tự chạy lại - phải bấm "Áp dụng thay
 *  đổi" (soát UX 29-09: thẻ từng nói "chờ … chạy tiếp" cả ở sách đã xong). */
const PendingHint = createContext<string>(S.s_cho_ap_dung_khi_sach_chay_tiep_6f0a3bc6);

function Example({ bookId, example, picked, onPick }: { bookId: string; example: WorkExample; picked?: boolean; onPick?: () => void }) {
  const clip = useClip();
  const id = `work-${example.segmentId}`;
  const playing = clip.current === id;
  return (
    <li className={cn("flex items-start gap-2 text-sm transition-opacity duration-motion-fast", onPick && !picked && "opacity-60")}>
      {onPick && (
        // Ô 14 px: nhãn bọc nới vùng bấm ra 24 px (màn hẹp/cảm ứng cao 40 px) mà ô vẫn đứng đúng chỗ cũ (soát a31, 2.5.8).
        <label className="touch-reach -mx-[5.25px] grid size-[24.5px] shrink-0 cursor-pointer place-items-center">
          <input
            type="checkbox"
            checked={picked}
            onChange={onPick}
            aria-label={S.s_gom_cau_nay_0_544f2a6f(example.text)}
            className="size-4 accent-[var(--accent)]"
          />
        </label>
      )}
      {example.hasAudio ? (
        <button
          type="button"
          onClick={() => clip.toggle(id, urls.sample(bookId, example.segmentId))}
          aria-label={playing ? S.s_dung_11554138 : S.s_nghe_cau_0_4329fb13(example.text)}
          className="mt-0.5 grid size-[32px] shrink-0 place-items-center rounded-full bg-hover text-fg-2 hover:text-fg"
        >
          <MotionRegion as="span" className="grid size-3.5 place-items-center">{playing ? <Pause className="size-3.5" fill="currentColor" strokeWidth={0} /> : <Play className="size-3.5 translate-x-[1px]" fill="currentColor" strokeWidth={0} />}</MotionRegion>
        </button>
      ) : (
        <span className="mt-0.5 size-[32px] shrink-0" aria-hidden />
      )}
      <div className="min-w-0">
        {example.before && <p className="line-clamp-2 text-fg-3"><span className="sr-only">{S.s_cau_lien_truoc_3fdc0989}</span>{example.before}</p>}
        {/* Nhãn đứng NGAY TRÊN câu được hỏi (không phải trên câu trước mờ - dễ đọc nhầm là nhãn của câu ấy); vạch bên trái đánh dấu đúng câu đang hỏi
            khi có câu trước/sau làm ngữ cảnh. */}
        <div className={cn((example.before || example.after) && "border-l-2 border-accent pl-2")}>
          <div className="text-xs text-fg-3">
            {example.chapterTitle} · {example.seq === 0 ? S.s_tieu_de_chuong_4f8f59f4 : S.s_cau_0_7b7d4092(example.seq)}
            {example.speaker && S.s_may_gan_0_e3b67580(example.speaker)}
            {example.narration && S.s_loi_ke_d511b7eb}
            {example.changes && <span className="font-semibold text-accent-text">{S.s_se_doi_b8b363f7}</span>}
            {!example.hasAudio && S.s_chua_thu_240643ef}
          </div>
          <p className={example.narration ? "text-fg-2" : "text-fg"}>
            {example.names?.length
              ? markNames(example.text, example.names).map((part, index) =>
                  part.mark ? (
                    <mark key={index} className="rounded-control bg-accent-soft px-0.5 font-semibold text-accent-text">
                      {part.text}
                    </mark>
                  ) : (
                    part.text
                  ),
                )
              : example.text}
          </p>
        </div>
        {example.after && <p className="line-clamp-2 text-fg-3"><span className="sr-only">{S.s_cau_lien_sau_e9238b3e}</span>{example.after}</p>}
      </div>
    </li>
  );
}

/** Nghe giọng một người được đề xuất (một câu đã thu của họ, như tab Nhân vật) - ngay cạnh nút chọn người ấy. */
function VoiceSample({ bookId, sampleId, samplePreset, name }: { bookId: string; sampleId?: number; samplePreset?: string; name: string }) {
  const clip = useClip();
  const id = `work-voice-${sampleId ?? samplePreset}`;
  const playing = clip.current === id;
  return (
    <Tooltip label={playing ? S.s_dung_11554138 : S.s_nghe_0_noi_e9307f6f(name)}>
      <button
        type="button"
        onClick={() => clip.toggle(id, sampleId ? urls.sample(bookId, sampleId) : urls.voice(samplePreset!))}
        aria-label={playing ? S.s_dung_nghe_thu_41a2925b : S.s_nghe_0_noi_e9307f6f(name)}
        className="touch-hit grid size-[32px] shrink-0 place-items-center rounded-full text-fg-2 transition-colors hover:bg-hover hover:text-fg"
      >
        <MotionRegion as="span" className="grid size-3.5 place-items-center">{playing ? <Pause className="size-3.5" fill="currentColor" strokeWidth={0} /> : <Play className="size-3.5 translate-x-[1px]" fill="currentColor" strokeWidth={0} />}</MotionRegion>
      </button>
    </Tooltip>
  );
}

/** Tên hiện của một người nói từ mã của họ, theo các lựa chọn của thẻ (báo "trước đó đang là …"). */
function personOf(item: WorkItem, value: string): string {
  if (value === item.currentValue) return item.current;
  const choice = item.choices?.find((option) => option.value === value);
  return choice?.name ?? choice?.label ?? value;
}

// Sửa cách đọc một tên ngay trên thẻ. Không chờ gì: ghi xong là xong phần người; dây chuyền áp ở ranh giới chương kế
// tiếp (hoặc lần chạy tới) và thu lại đúng những câu có tên ấy - kể cả sách đã xong.
function PronunciationFix({ bookId, item, onOpenNames }: { bookId: string; item: WorkItem; onOpenNames?: (name: string) => void }) {
  const client = useQueryClient();
  const pending = useContext(PendingHint);
  const [value, setValue] = useState(item.requested ?? item.current);
  // Lỗi nằm ngay dưới ô nhập, không chỉ trong toast 4 giây (soát UX 29-09: "Hên-kơ" bị từ chối mà không biết sửa chỗ nào).
  const [problem, setProblem] = useState("");
  const [suggestion, setSuggestion] = useState("");
  const save = useMutation({
    mutationFn: (spokenForm: string) =>
      api<{ surface: string; spokenForm: string; requestedAt: number; elsewhere?: { spokenForm?: string } }>(`/api/books/${bookId}/pronunciation`, {
        method: "POST",
        // `seen`: cách đọc thẻ này đang thấy đã ghi - máy/cửa sổ khác vừa ghi khác thì được báo (soát a27 lỗi 4).
        body: { surface: item.surface, spokenForm, seen: item.requested ?? "" },
      }),
    onSuccess: ({ spokenForm, requestedAt, elsewhere }) => {
      refreshAfterDecision(client, bookId);
      const keep = spokenForm === item.current;
      // `previous`: cách máy đọc lúc bấm - máy chủ xin lại cách ấy nếu cách mới đã vào sách.
      const action = undoAction(
        client,
        bookId,
        "pronunciation",
        [{ surface: item.surface, requestedAt, previous: item.current, keep }],
        item.requested
          ? S.s_tro_lai_quyet_dinh_truoc_0_doc_la_1_0fd271bc(item.surface, item.requested)
          : S.s_0_lai_doc_la_1_734123f6(item.surface, item.current),
      );
      if (elsewhere?.spokenForm !== undefined) warnElsewhere(1, elsewhere.spokenForm ? `“${elsewhere.spokenForm}”` : "", action.onClick);
      // Giữ đúng cách máy đang đọc thì không có gì để thu lại - soát UX 29-09: báo "sẽ thu lại" làm người nghe hoảng.
      if (keep) {
        toast.success(S.s_giu_cach_doc_0_ad3b6d08(spokenForm), { action, duration: UNDO_MS });
        return;
      }
      toast.success(S.s_da_ghi_0_doc_la_1_2c14f196(item.surface, spokenForm), {
        action,
        duration: UNDO_MS,
      });
    },
    // Lỗi chỉ nằm dưới ô nhập - thêm toast là báo một lỗi hai lần (soát UX 29-09).
    onError: (error: Error) => {
      setProblem(error.message);
      setSuggestion(suggestionOf(error));
    },
  });
  const typed = value.trim();
  const inputId = `spoken-${item.key}`;
  const use = (spoken: string) => {
    setValue(spoken);
    setProblem("");
    setSuggestion("");
    save.mutate(spoken);
  };
  // "Nghe thử" cách đang gõ trước khi lưu: máy chê cách đọc thì hiện đúng chỗ lỗi của "Đọc thế này".
  const tryIt = useTryReading({
    bookId,
    surface: item.surface ?? "",
    spoken: typed,
    disabled: Boolean(problem),
    onRejected: (message, suggestionText) => {
      setProblem(message);
      setSuggestion(suggestionText);
    },
  });
  return (
    <div className="mt-3">
      {item.requested && (
        <p className="mb-2 flex items-center gap-1.5 text-xs text-fg-2">
          <Check className="size-3.5 text-success" />
          {/* "Giữ" cách máy đang đọc không đổi gì trong sách - không bảo bấm "Áp dụng thay đổi" (soát UX 29-09). */}
          {item.requested === item.current ? S.s_giu_0_khong_can_ap_dung_90d56536(item.requested) : S.s_da_ghi_0_1_ff5ca65e(item.requested, pending)}
        </p>
      )}
      <form
        className="flex flex-wrap items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (typed) save.mutate(typed);
        }}
      >
        <DecisionButton data-choice size="sm" variant="ghost" disabled={save.isPending} onClick={() => save.mutate(item.current)}>{S.s_dung_roi_giu_b3493ad3}{item.current}”
        </DecisionButton>
        <label htmlFor={inputId} className="text-xs text-fg-2">{S.s_hoac_doc_la_376990a8}</label>
        <input
          id={inputId}
          aria-label={S.s_cach_doc_moi_cho_0_d68a75c3(item.surface)}
          placeholder={S.s_vd_0_85e20173(item.current)}
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            setProblem("");
            setSuggestion("");
          }}
          spellCheck={false}
          autoComplete="off"
          aria-invalid={problem ? true : undefined}
          aria-describedby={problem ? `${inputId}-problem` : undefined}
          className={cn(
            "h-8 w-40 rounded-control border bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-focus focus-visible:ring-2 focus-visible:ring-focus",
            problem ? "border-danger" : "border-line",
          )}
        />
        {tryIt.button}
        <Button
          size="sm"
          variant="primary"
          type="submit"
          loading={save.isPending}
          disabled={!typed || typed === item.current || typed === item.requested}
        >{S.s_doc_the_nay_b9d202fe}</Button>
        {/* Thẻ chỉ hỏi tên máy kém chắc; mọi tên khác (kể cả tên đã chọn) sửa ở tab Nhân vật, mục "Cách đọc tên". */}
        {onOpenNames && (
          <Button size="sm" variant="ghost" type="button" className="text-fg-2 hover:text-fg" onClick={() => onOpenNames(item.surface ?? "")}>{S.s_moi_cach_doc_ten_5d01fa0c}</Button>
        )}
      </form>
      {tryIt.note}
      <ReadingProblem id={`${inputId}-problem`} problem={problem} suggestion={suggestion} onUse={use} />
    </div>
  );
}

// Gán người nói - một câu ("Ai nói câu này", người gọi) hay mọi câu của một vai phụ: mỗi ứng viên một nút, người máy nghi
// nhất đứng đầu. Không chờ gì - ghi xong là xong phần người; dây chuyền gán câu cho người ấy (mượn đúng giọng sẵn có của
// họ) ở ranh giới chương, câu đã thu thì thu lại.
type Scope = "alternate" | "all";

function SpeakerFix({
  bookId,
  item,
  onOpenScript,
  scope = "alternate",
  onScope,
  picked,
}: {
  bookId: string;
  item: WorkItem;
  onOpenScript?: OpenScript;
  scope?: Scope;
  onScope?: (scope: Scope) => void;
  /** Thẻ vai phụ cả cuốn: những câu người nghe còn chọn. */
  picked?: LineRef[];
}) {
  const client = useQueryClient();
  const lines = picked ?? (scope === "all" && item.allLines ? item.allLines : item.lines);
  const pending = useContext(PendingHint);
  // "Người khác…": người nói chưa có trong lựa chọn - kể cả người máy CHƯA TỪNG gán câu nào (linh thể nói trong 『』):
  // gõ tên + chọn giới, dây chuyền tạo người ấy và cấp giọng riêng như bước phân vai.
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState(item.suggestedName ?? "");
  // Mở “Người khác…” để gõ tên thì con trỏ vào ô luôn (bàn phím không phải Tab qua cả hàng nút để tìm nó).
  const nameInput = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (creating) nameInput.current?.focus();
  }, [creating]);
  const save = useMutation({
    mutationFn: ({ speaker, newGender }: { speaker: string; newGender?: string }) =>
      api<{ lines: number; speaker: string; alias?: boolean; requestedAt: number; elsewhere?: Record<string, string> }>(`/api/books/${bookId}/speaker`, {
        method: "POST",
        body: {
          lines,
          speaker,
          newGender: newGender ?? "",
          seen: seenFor(lines ?? [], item.seen),
          // "Một người hai tên": gộp là quyết cả ở cấp tên - phần sau của cuốn ("Làm tiếp cuốn này") tự hiểu.
          ...(item.kind === "alias" && speaker !== item.currentValue ? { alias: item.currentValue } : {}),
          // Thẻ 『』 phạm vi "Cả cuốn": quy ước của cả cuốn, các phần sau tự áp.
          ...(item.kind === "bracket" && scope === "all" ? { bracketRule: true } : {}),
        },
      }),
    onSuccess: ({ lines: recorded, speaker, alias, requestedAt, elsewhere }) => {
      refreshAfterDecision(client, bookId);
      const which = recorded > 1 ? S.s_0_cau_nay_eeb40df6(recorded) : S.s_cau_nay_c70feb8f;
      const keep = speaker === item.currentValue;
      // Thẻ "hai tên một người": máy chủ rút luôn bí danh ghi cùng mốc (server._withdraw) nên hoàn tác được. Quy ước 『』 cả cuốn còn ghi ở
      // cấp cuốn cho các phần sau - hoàn tác chỉ lùi được phần câu, nên không mời.
      const back = item.requested
        ? S.s_tro_lai_quyet_dinh_truoc_0_cua_1_1a135e00(which, midSentence(item.requested))
        : item.pick
          ? S.s_0_tro_lai_cho_duyet_d4777925(sentence(which))
          : S.s_0_lai_la_cua_1_1de883c6(sentence(which), midSentence(item.current));
      const undo = alias && item.kind === "bracket" ? {} : { action: undoAction(client, bookId, "speaker", [{ lines, requestedAt, keep }], back), duration: UNDO_MS };
      const replaced = Object.values(elsewhere ?? {});
      if (replaced.length) warnElsewhere(replaced.length, replaced[0] ? personOf(item, replaced[0]) : "", undo.action?.onClick);
      if (keep) {
        toast.success(item.keepLabel ? S.s_da_ghi_0_5450366f(item.keepLabel) : S.s_giu_nguyen_0_cua_1_f0574c99(which, midSentence(item.current)), {
          ...undo,
        });
        return;
      }
      const choice = item.choices?.find((option) => option.value === speaker);
      const label = choice?.name ?? choice?.label ?? speaker;
      toast.success(S.s_da_ghi_0_cua_1_36d6075b(which, midSentence(label)), {
        ...undo,
      });
    },
    onError: (error: Error) => toast.error(S.s_chua_ghi_duoc_nguoi_noi_5ef0be83, { description: error.message }),
  });
  // Thẻ nhóm giữ nguyên: mỗi vai giữ người của nó - vài yêu cầu, một nút hoàn tác cho cả nhóm.
  const keepAll = useMutation({
    mutationFn: async (requests: SpeakerRequest[]) => {
      const made: Record<string, unknown>[] = [];
      const replaced: string[] = [];
      for (const request of requests) {
        const answer = await api<{ requestedAt: number; elsewhere?: Record<string, string> }>(`/api/books/${bookId}/speaker`, {
          method: "POST",
          body: { ...request, seen: seenFor(request.lines, item.seen) },
        });
        replaced.push(...Object.values(answer.elsewhere ?? {}));
        made.push({ lines: request.lines, requestedAt: answer.requestedAt, keep: true });
      }
      return { made, replaced };
    },
    onSuccess: ({ made, replaced }) => {
      refreshAfterDecision(client, bookId);
      const action = undoAction(client, bookId, "speaker", made, S.s_the_hoi_lai_nhu_truoc_khi_bam_7ad3829e);
      if (replaced.length) warnElsewhere(replaced.length, replaced[0] ? personOf(item, replaced[0]) : "", action.onClick);
      toast.success(S.s_da_ghi_0_5450366f(item.keepLabel ?? S.s_giu_nguyen_1b550a12), {
        action,
        duration: UNDO_MS,
      });
    },
    onError: (error: Error) => {
      refreshAfterDecision(client, bookId);
      toast.error(S.s_chua_ghi_duoc_9fa87a7d, { description: error.message });
    },
  });
  const busy = save.isPending || keepAll.isPending;
  const none = !lines?.length;
  // Quá nhiều chip (thẻ 『』 có thể 12 người): chừa MAX_CHIPS đầu (và lựa chọn đã ghi), phần còn lại nằm trong “Người khác…”.
  const everyChoice = item.choices ?? [];
  const isAnswer = (choice: { label: string; name?: string }) => Boolean(item.requested) && [choice.name, choice.label].includes(item.requested!);
  const shownChoices = everyChoice.filter((choice, index) => index < MAX_CHIPS || isAnswer(choice) || GENERIC_PEOPLE.has(choice.label));
  const moreChoices = everyChoice.filter((choice) => !shownChoices.includes(choice));
  // Gợi ý tên bằng chính tên trong sách, không phải tên truyện nào đó (soát UX a13 #6).
  const sample = everyChoice.map((choice) => choice.name ?? choice.label).find((text) => text && !GENERIC_PEOPLE.has(text) && !/^(Tất cả là|Giữ) /.test(text));
  return (
    <div className="mt-3">
      {item.requested && (
        <p className="mb-2 flex items-center gap-1.5 text-xs text-fg-2">
          <Check className="size-3.5 text-success" />
          {/* Gộp tên là ở cấp TÊN cho cả cuốn và các phần sau, không phải "câu này của X" (soát UX 29-09). */}
          {item.kind === "alias"
            ? S.s_da_ghi_0_la_1_ca_cuon_va_cac_phan_sau_a67585e2(item.subject ?? item.current, midSentence(item.requested))
            : S.s_da_ghi_0_cua_1_2_efc7efdc((item.lines?.length ?? 1) > 1 ? S.s_0_cau_nay_eeb40df6(item.lines?.length) : S.s_cau_nay_c70feb8f, midSentence(item.requested), pending)}
        </p>
      )}
      {item.allLines && item.lines && onScope && (
        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-fg-2">
          <span>{S.s_doi_nguoi_noi_cho_214fb622}</span>
          <ChoiceRow<Scope>
            label={S.s_doi_nguoi_noi_cho_nhung_cau_nao_88602af5}
            value={scope}
            onChange={onScope}
            options={[
              { value: "alternate", label: `${item.scopeLabels?.[0] ?? S.s_cau_xen_ke_a9442401} · ${item.lines.length}` },
              { value: "all", label: `${item.scopeLabels?.[1] ?? S.s_ca_chuoi_2a2c3bbf} · ${item.allLines.length}` },
            ]}
          />
        </div>
      )}
      {item.allLines && item.lines && onScope && (
        <p className="mb-2 text-xs text-fg-3">
          {item.scopeLabels
            ? S.s_0_theo_chuong_1_theo_ca_sach_va_cac_phan_s_1dd980b1(item.scopeLabels[0], item.scopeLabels[1])
            : S.s_cau_xen_ke_chi_doi_cau_danh_dau_ca_chuoi_d_8b814b90}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label={`${KIND_LABEL[item.kind]}: ${decidedTitle(item) ?? item.title}`}>
        {shownChoices.map((choice, index) => (
          <span key={choice.value} className="inline-flex items-center">
            <DecisionButton data-choice
              size="sm"
              // Gạch chân lựa chọn, để nút thực hiện vẫn là điểm nhấn duy nhất.
              variant="ghost"
              className={cn("border-b-2 rounded-none transition-colors", index === 0 && "edge-start-action", (item.requested ? [choice.name, choice.label].includes(item.requested) : index === 0 && item.kind !== "unnamed" && item.suggested !== false) ? "border-accent" : "border-transparent")}
              aria-pressed={item.requested ? [choice.name, choice.label].includes(item.requested) : undefined}
              disabled={busy || none}
              onClick={() => save.mutate({ speaker: choice.value })}
            >
              {choice.label}
            </DecisionButton>
            {choice.sampleId || choice.samplePreset ? <VoiceSample bookId={bookId} sampleId={choice.sampleId} samplePreset={choice.samplePreset} name={choice.name ?? choice.label} /> : null}
          </span>
        ))}
        {item.currentValue && (
          <DecisionButton data-choice size="sm" variant="ghost" disabled={busy} onClick={() => save.mutate({ speaker: item.currentValue! })}>
            {item.keepLabel ?? (item.kind === "unnamed" ? S.s_dung_la_vai_phu_7f821afe : S.s_giu_0_b8c06ffa(item.current))}
          </DecisionButton>
        )}
        {/* Vai phụ ngôi ba (lính gác) không phải ai trong danh sách - cả nhóm có thể là MỘT người mới, có giọng riêng. */}
        {item.newPerson && (
          <DecisionButton data-choice size="sm" variant="ghost" disabled={busy || none} onClick={() => save.mutate({ speaker: item.newPerson!, newGender: "unknown" })}>
            {item.newPersonLabel ?? S.s_tao_nhan_vat_18e9a09a}
          </DecisionButton>
        )}
        {item.keepGroups && item.keepGroups.length > 0 && (
          <DecisionButton data-choice size="sm" variant="ghost" disabled={busy} onClick={() => keepAll.mutate(keepRequests(item))}>
            {item.keepLabel ?? S.s_giu_nguyen_1b550a12}
          </DecisionButton>
        )}
        {/* Thẻ "một người hai tên" hỏi hai tên có phải một người - chọn người thứ ba lạc chủ đề (soát UX 29-09). */}
        {item.kind !== "alias" && (
          <Button size="sm" variant="ghost" icon={item.suggestedName || item.kind === "caller" ? undefined : UserPlus} aria-expanded={creating} className="text-fg-2 hover:text-fg" onClick={() => setCreating((value) => !value)}>
            {item.suggestedName ? S.s_dat_ten_519d84a1 : S.s_nguoi_khac_36be042b}
          </Button>
        )}
        {/* Thẻ chỉ gợi vài người; tab Kịch bản tìm được mọi nhân vật trong sách - mở đúng câu này ở đó (soát UX 29-09). */}
        {onOpenScript && item.lines?.length === 1 && item.examples?.[0] && (
          <Button size="sm" variant="ghost" icon={Search} className="text-fg-2 hover:text-fg" onClick={() => onOpenScript(item.examples![0].chapterId, item.lines![0].stableId)}>{S.s_tim_nguoi_khac_ce406b45}</Button>
        )}
        {/* Thẻ nhóm chỉ in vài câu làm ví dụ ("Hai người chung một tên" có thể 16 câu): đọc đủ ngữ cảnh ở tab Kịch bản trước khi
            quyết, mở đúng chương, tại câu đầu của nhóm. */}
        {onOpenScript && (item.lines?.length ?? 0) > (item.examples?.length ?? 0) && item.examples?.[0] && (
          <Button size="sm" variant="ghost" icon={Search} className="text-fg-2 hover:text-fg" onClick={() => onOpenScript(item.examples![0].chapterId, item.lines![0].stableId, false)}>{S.s_xem_e7ed16f8}{item.lines!.length}{S.s_cau_b07e1008}</Button>
        )}
      </div>
      <Collapse open={creating}>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {moreChoices.length > 0 && (
            <div className="flex w-full flex-wrap items-center gap-1.5" role="group" aria-label={S.s_nhung_nguoi_khac_trong_sach_43124252}>
              {moreChoices.map((choice) => (
                <Button key={choice.value} size="sm" variant="ghost" disabled={busy || none} onClick={() => save.mutate({ speaker: choice.value })}>
                  {choice.label}
                </Button>
              ))}
              <span className="text-xs text-fg-3">{S.s_hay_dat_ten_mot_nguoi_moi_10597c08}</span>
            </div>
          )}
          <input
            ref={nameInput}
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder={sample ? S.s_ten_nguoi_noi_vd_0_b7a0ff62(sample) : S.s_ten_nguoi_noi_d3caf277}
            aria-label={S.s_ten_nguoi_noi_moi_9be83401}
            maxLength={80}
            className="h-8 min-w-0 flex-1 rounded-control border border-line bg-panel px-2.5 text-sm outline-none focus-visible:border-focus focus-visible:ring-2 focus-visible:ring-focus"
          />
          <span className="text-xs text-fg-2">{S.s_gioi_bam_de_luu_e314c934}</span>
          {(
            [
              ["male", S.s_nam_22dd59c8],
              ["female", S.s_nu_e15bc11c],
              ["unknown", S.s_khong_ro_8af7da78],
            ] as const
          ).map(([gender, label]) => (
            <Button
              key={gender}
              size="sm"
              variant="ghost"
              disabled={!name.trim() || busy || none}
              aria-label={S.s_luu_nguoi_noi_moi_gioi_0_f39ab58a(label.toLowerCase())}
              onClick={() => save.mutate({ speaker: name.trim(), newGender: gender })}
            >
              {label}
            </Button>
          ))}
        </div>
      </Collapse>
    </div>
  );
}

// Người kể của một ĐOẠN khác người kể "tôi" của sách: ba lựa chọn - đúng (đoạn không do người ấy kể; đoạn mở bằng dòng tiêu đề góc
// nhìn thì: do người dòng ấy gọi kể), không (giữ nguyên), hay chọn người khác. Lô phân tích chưa chạy sẽ theo lựa chọn; đoạn đã
// phân tích xong thì chỉ áp khi làm lại sách (thẻ nói rõ).
function NarratorFix({ bookId, item }: { bookId: string; item: WorkItem }) {
  const client = useQueryClient();
  const section = item.narratorSection!;
  const [choosing, setChoosing] = useState(false);
  const [name, setName] = useState("");
  const nameInput = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (choosing) nameInput.current?.focus();
  }, [choosing]);
  const where = { chapterIndex: section.chapterIndex, fromSeq: section.fromSeq, toSeq: section.toSeq };
  const buttons = narratorButtons(section.narrator, section.heading);
  const save = useMutation({
    mutationFn: (body: { action: "accept" | "choose" | "keep"; narrator?: string }) =>
      api<{ action: string; narrator: string }>(`/api/books/${bookId}/narrator-section`, { method: "POST", body: { ...where, ...body } }),
    onSuccess: ({ action, narrator }) => {
      refreshAfterDecision(client, bookId);
      const back = item.requested ? S.s_tro_lai_quyet_dinh_truoc_0_2d7ed059(item.requested) : S.s_the_hoi_lai_nhu_truoc_khi_bam_7ad3829e;
      toast.success(
        action === "keep"
          ? item.current ? S.s_giu_nguyen_doan_nay_van_do_0_ke_dffb3797(item.current) : S.s_giu_nguyen_doan_nay_van_ke_o_ngoi_thu_ba_f0be91ed
          : narrator
            ? S.s_da_ghi_doan_nay_do_0_ke_99b4e3f7(section.heading?.narrator === narrator ? section.heading.label : narrator)
            : S.s_da_ghi_doan_nay_khong_phai_0_ke_71722738(item.current),
        {
          action: undoAction(client, bookId, "narrator-section", [where], back),
          duration: UNDO_MS,
        },
      );
    },
    onError: (error: Error) => toast.error(S.s_chua_ghi_duoc_nguoi_ke_ce503d25, { description: error.message }),
  });
  const typed = name.trim();
  return (
    <div className="mt-3">
      {section.appliesNote && !(item.requested && item.redoOnly) && <p className="mb-2 text-xs text-fg-2">{section.appliesNote}</p>}
      {item.requested && (
        <p className="mb-2 flex items-center gap-1.5 text-xs text-fg-2">
          <Check className="size-3.5 text-success" />
          {item.redoOnly ? S.s_da_ghi_ap_khi_lam_lai_phan_tich_tu_dau_4ed021d7 : S.s_da_ghi_0_036988b1(item.requested)}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label={`${KIND_LABEL[item.kind]}: ${decidedTitle(item) ?? item.title}`}>
        <DecisionButton data-choice size="sm" variant="ghost" className={cn("border-b-2 rounded-none transition-colors", item.requested === buttons.accepted ? "border-accent" : "border-transparent")} disabled={save.isPending} onClick={() => save.mutate({ action: "accept" })}>
          {buttons.accept}
        </DecisionButton>
        <DecisionButton data-choice size="sm" variant="ghost" className={cn("border-b-2 rounded-none transition-colors", item.requested === S.s_giu_nguyen_1b550a12 ? "border-accent" : "border-transparent")} disabled={save.isPending} onClick={() => save.mutate({ action: "keep" })}>
          {buttons.keep}
        </DecisionButton>
        <Button size="sm" variant="ghost" icon={UserPlus} aria-expanded={choosing} className="text-fg-2 hover:text-fg" onClick={() => setChoosing((value) => !value)}>{S.s_nguoi_ke_khac_7291e079}</Button>
      </div>
      <Collapse open={choosing}>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {section.choices.map((choice) => (
            <Button key={choice.value} size="sm" variant="ghost" disabled={save.isPending} onClick={() => save.mutate({ action: "choose", narrator: choice.value })}>
              {choice.label}
            </Button>
          ))}
          <input
            ref={nameInput}
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder={S.s_ten_nguoi_ke_d492ccfb}
            aria-label={S.s_ten_nguoi_ke_cua_doan_94204731}
            maxLength={80}
            className="h-8 min-w-0 flex-1 rounded-control border border-line bg-panel px-2.5 text-sm outline-none focus-visible:border-focus focus-visible:ring-2 focus-visible:ring-focus"
          />
          <Button size="sm" variant="primary" disabled={!typed || save.isPending} onClick={() => save.mutate({ action: "choose", narrator: typed })}>{S.s_dat_nguoi_ke_d4ae9aa6}</Button>
        </div>
      </Collapse>
    </div>
  );
}

// Yêu cầu máy đã xét và từ chối (soát a89 V8): bạn không phải đoán vì sao nó không được làm - thẻ nói lý do (`problem`) và cho bỏ yêu cầu ấy;
// sửa lại thì làm ở tab tương ứng (Kịch bản, Nhân vật, Cách đọc tên). Bỏ hay gửi yêu cầu khác cho cùng mục thì thẻ tự rơi.
function RefusedFix({ bookId, item }: { bookId: string; item: WorkItem }) {
  const client = useQueryClient();
  const drop = useMutation({
    mutationFn: () =>
      api(`/api/books/${bookId}/pending-changes/withdraw`, {
        method: "POST",
        body: { section: item.refused!.section, key: item.refused!.key, requestedAt: item.refused!.requestedAt },
      }),
    onSuccess: () => {
      refreshAfterDecision(client, bookId);
      toast.success(S.s_da_bo_yeu_cau_nay_5eec8a27);
    },
    onError: (error: Error) => toast.error(S.s_chua_bo_duoc_638141d7, { description: error.message }),
  });
  return (
    <Button size="sm" variant="ghost" className="mt-3" loading={drop.isPending} onClick={() => drop.mutate()}>{S.s_bo_yeu_cau_nay_670ce121}</Button>
  );
}

// Giọng / giới của một nhân vật: một lần bấm. Dây chuyền chọn giọng mới như bước phân vai (mọi người khác giữ giọng) và
// chỉ thu lại khi giọng thật sự đổi - ghi chú dưới mỗi nút nói trước cái giá ấy.
function VoiceFix({ bookId, item }: { bookId: string; item: WorkItem }) {
  const client = useQueryClient();
  const pending = useContext(PendingHint);
  const save = useMutation({
    mutationFn: async ({ requests }: { requests: Omit<VoiceChoice, "label" | "note" | "done" | "recommended">[]; label: string; keep: boolean; note?: string }) => {
      const made: { character: string; requestedAt: number }[] = [];
      for (const request of requests) {
        const { requestedAt } = await api<{ requestedAt: number }>(`/api/books/${bookId}/voice`, { method: "POST", body: request });
        made.push({ character: request.character, requestedAt });
      }
      return made;
    },
    onSuccess: (made, { label, keep }) => {
      refreshAfterDecision(client, bookId);
      // Nói cụ thể điều gì trở lại, như thẻ cách đọc và thẻ người nói (soát UX 30-09: "Thẻ hỏi lại như trước khi bấm").
      const heard = item.current === S.s_giong_nam_4ab78f43 || item.current === S.s_giong_nu_cd860480 ? item.current.toLowerCase() : S.s_giong_dang_co_3b2ea3dd;
      const back =
        item.kind === "gender" && item.subject
          ? item.requested
            ? S.s_tro_lai_quyet_dinh_truoc_0_la_1_68f9b1ee(item.subject, item.requested.toLowerCase())
            : S.s_0_lai_de_may_quyet_van_doc_bang_1_d02a4952(item.subject, heard)
          : item.requested
            ? S.s_tro_lai_quyet_dinh_truoc_0_2d7ed059(item.requested)
            : item.kind === "shared-voice"
              ? S.s_hai_nguoi_lai_dung_chung_giong_nhu_truoc_7486498c
              : S.s_the_hoi_lai_nhu_truoc_khi_bam_7ad3829e;
      const undo = { action: undoAction(client, bookId, "voice", made.map((decision) => ({ ...decision, keep })), back), duration: UNDO_MS };
      if (keep) {
        toast.success(S.s_da_ghi_0_5450366f(label), { ...undo });
        return;
      }
      // Lựa chọn nói trước cái giá ("giữ giọng đang đọc" / "đổi giọng, thu lại N câu") - thông báo nói đúng cái giá ấy, không
      // rào "nếu giọng phải đổi" khi giọng giữ nguyên (soát UX 29-09).
      toast.success(S.s_da_ghi_0_5450366f(label), {
        ...undo,
      });
    },
    onError: (error: Error) => toast.error(S.s_chua_ghi_duoc_9fa87a7d, { description: error.message }),
  });
  return (
    <div className="mt-3">
      {item.requested && (
        <p className="mb-2 flex items-center gap-1.5 text-xs text-fg-2">
          <Check className="size-3.5 text-success" />{S.s_da_ghi_85094402}{item.requested} - {pending}.
        </p>
      )}
      <div className="flex flex-wrap items-start gap-2" role="group" aria-label={S.s_chon_1171ca97}>
        {(item.voiceChoices ?? []).map((choice) => (
          <div key={`${choice.character}-${choice.label}`} className="flex flex-col items-start gap-0.5">
            <DecisionButton data-choice
              size="sm"
              variant="ghost"
              className={cn("border-b-2 rounded-none transition-colors", (item.requested ? [choice.done, choice.label].includes(item.requested) : choice.recommended) ? "border-accent" : "border-transparent")}
              disabled={save.isPending}
              onClick={() =>
                save.mutate({
                  requests: [{ character: choice.character, gender: choice.gender, preset: choice.preset, avoid: choice.avoid }],
                  label: choice.done ?? choice.label,
                  keep: false,
                  note: choice.note,
                })
              }
            >
              {choice.label}
            </DecisionButton>
            {choice.note && <span className="px-0.5 text-[0.6875rem] text-fg-3">{choice.note}</span>}
          </div>
        ))}
        {item.keepCharacters && item.keepCharacters.length > 0 && (
          <DecisionButton data-choice
            size="sm"
            variant="ghost"
            disabled={save.isPending}
            onClick={() =>
              save.mutate({
                requests: item.keepCharacters!.map((character) => ({ character })),
                label: item.keepLabel ?? S.s_giu_nguyen_1b550a12,
                keep: true,
              })
            }
          >
            {item.keepLabel ?? S.s_giu_nguyen_1b550a12}
          </DecisionButton>
        )}
      </div>
    </div>
  );
}

/** Mở câu `stableId` của chương `chapterId` trong tab Kịch bản, ô chọn người nói mở sẵn. */
/** `pick`: mở sẵn ô chọn người nói ở câu ấy (mặc định) - thẻ nhóm mở để ĐỌC thì không, ô ấy che chữ. */
/** `card`: thẻ đang mở lối nhảy - trang dự án ghi nó vào địa chỉ để Back trở lại đúng thẻ ấy. */
type OpenScript = (chapterId: number, stableId: string, pick?: boolean, card?: string) => void;
type OpenNames = (name: string, card?: string) => void;
type OpenReview = (card?: string) => void;
type PickVoice = (person: { name: string; displayName: string }) => void;

// "Hoàn tác" bền của một mục đã quyết: toast chỉ sống vài giây, mà người duyệt thường nhận ra bấm nhầm khi đã xem sang thẻ khác.
// Đi đúng đường hoàn tác của toast (decisions.undoAction): máy chủ bỏ yêu cầu của đúng lần bấm ấy, hay nói thật khi dây chuyền
// đã đưa nó vào sách.
function UndoDecision({ bookId, item }: { bookId: string; item: WorkItem }) {
  const client = useQueryClient();
  const [asked, setAsked] = useState(false);
  const resetTimer = useRef<ReturnType<typeof window.setTimeout> | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(resetTimer.current), []);
  const undo = item.undo!;
  return (
    <Button
      size="sm"
      variant="ghost"
      icon={RotateCcw}
      className="ml-auto"
      disabled={asked}
      aria-label={S.s_hoan_tac_0_d8c7233a(decidedTitle(item) ?? item.title)}
      onClick={() => {
        setAsked(true);
        undoAction(client, bookId, undo.endpoint, undo.decisions, S.s_viec_nay_tro_lai_cho_ban_duyet_76cf7987).onClick();
        // Không hoàn tác được (đã vào sách) thì thẻ còn đó - mở nút lại để thử khi đổi ý.
        window.clearTimeout(resetTimer.current);
        resetTimer.current = window.setTimeout(() => setAsked(false), 2500);
      }}
    >{S.s_hoan_tac_e72ff675}</Button>
  );
}

function Card({ bookId, item, onOpenReview, onOpenScript, onOpenNames, onPickVoice, active = false, exiting = false, as: Tag = "li" }: { as?: "li" | "div"; bookId: string; item: WorkItem; onOpenReview: OpenReview; onOpenScript?: OpenScript; onOpenNames?: OpenNames; onPickVoice?: PickVoice; active?: boolean; exiting?: boolean }) {
  // Thẻ chuỗi lượt đối đáp: đổi các câu xen kẽ (mặc định) hay cả chuỗi - câu "sẽ đổi" theo phạm vi đang chọn.
  const [scope, setScope] = useState<Scope>("alternate");
  // Thẻ vai phụ cả cuốn: câu người nghe bỏ chọn (mã câu), và mở cả danh sách hay chỉ vài câu đầu.
  const [left, setLeft] = useState<ReadonlySet<string>>(new Set());
  const [all, setAll] = useState(false);
  // Câu tải thêm theo trang (thẻ nhóm lớn chỉ mang vài câu đầu - `examplesTotal`).
  const [more, setMore] = useState<WorkExample[]>([]);
  const [loadingMore, setLoadingMore] = useState(false);
  // Gán một phần rồi thì thẻ còn đúng những câu đã bỏ chọn - chúng phải hiện là đang chọn, không phải vẫn bỏ.
  const groupLines = item.pick ? (item.lines ?? []).map((line) => line.stableId).join(" ") : "";
  useEffect(() => {
    setLeft(new Set());
    setMore([]);
  }, [groupLines]);
  const picked = item.pick && item.lines ? pickedLines(item.lines, left) : undefined;
  const { loaded, total, next } = examplesPage(bookId, item.key, item.examples, more, item.examplesTotal, PICK_PAGE);
  const loadMore = () => {
    if (!next) return;
    setLoadingMore(true);
    api<{ examples: WorkExample[]; total: number }>(next)
      .then((page) => setMore((current) => [...current, ...page.examples]))
      .catch((error: Error) => toast.error(S.s_chua_tai_them_duoc_cau_35372122, { description: error.message }))
      .finally(() => setLoadingMore(false));
  };
  const shownExamples = item.pick && !all ? loaded.slice(0, PICK_PREVIEW) : loaded;
  const openScript: OpenScript | undefined =
    onOpenScript && ((chapterId, stableId, pick) => onOpenScript(chapterId, stableId, pick, item.key));
  const openNames: OpenNames | undefined = onOpenNames && ((name) => onOpenNames(name, item.key));
  return (
    // tabIndex -1: J / K và "quyết xong thì sang thẻ kế" đặt tiêu điểm thật vào thẻ - trình đọc màn hình đọc thẻ đang chọn (soát a31 K4/K5).
    <Tag
      id={exiting ? undefined : `work-${item.key}`}
      data-work-key={exiting ? undefined : item.key}
      tabIndex={-1}
      // Thẻ đứng riêng (div) cần vai trò thì tên của nó mới được đọc; trong danh sách thì là listitem.
      role={Tag === "div" ? "group" : undefined}
      aria-labelledby={exiting ? undefined : `work-${item.key}-title`}
      aria-current={active ? "true" : undefined}
      // Việc đang duyệt nổi ở tên; không thêm mặt thẻ cho từng hàng.
      className={cn("scroll-mt-24 px-3 py-4 transition-colors duration-motion-fast", active && "[&_h3]:text-accent-text")}
    >
      <MotionRegion>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="rounded-full bg-hover px-2 py-0.5 text-[0.6875rem] font-medium text-fg-2">{KIND_LABEL[item.kind]}</span>
        <h3 id={exiting ? undefined : `work-${item.key}-title`} className="text-[0.9375rem] font-semibold">{decidedTitle(item) ?? item.title}</h3>
        {item.requested && item.undo && <UndoDecision bookId={bookId} item={item} />}
      </div>
      <p className="mt-1.5 text-sm text-fg-2">{item.problem}</p>
      <MotionRegion motionKey={scope} className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-fg-2">
        <span>{S.s_anh_huong_f9ba35dd}<span className="font-semibold text-fg">{formatNumber(item.allLines && scope === "all" ? item.allLines.length : item.affected)}</span>{S.s_cau_b07e1008}</span>
        <span>
          {item.kind === "audio" ? S.s_trang_thai_cb31de81 : item.kind === "narrator" ? S.s_may_coi_nguoi_ke_la_f1309939 : S.s_may_dang_dung_d9ef0879}:{" "}
          <span className="font-medium text-fg">{item.kind === "narrator" && !item.current ? S.s_khong_ai_chuong_ke_o_ngoi_thu_ba_209ef4df : item.current}</span>
        </span>
      </MotionRegion>
      {item.kind === "audio" ? (
        <Button size="sm" variant="ghost" icon={AudioLines} className="mt-3" onClick={() => onOpenReview(item.key)}>{S.s_nghe_lai_2ac2936f}</Button>
      ) : item.kind === "pronunciation" && item.surface ? (
        <PronunciationFix bookId={bookId} item={item} onOpenNames={openNames} />
      ) : item.kind === "narrator" && item.narratorSection ? (
        <NarratorFix bookId={bookId} item={item} />
      ) : item.kind === "refused" && item.refused ? (
        <RefusedFix bookId={bookId} item={item} />
      ) : item.kind === "voice-wish" ? (
        <div className="flex flex-wrap items-end gap-2">
          {item.pickVoice && onPickVoice && (
            <Button size="sm" variant="ghost" className="mt-3" onClick={() => onPickVoice(item.pickVoice!)}>{S.s_chon_giong_khac_d31cfe89}</Button>
          )}
          <VoiceFix bookId={bookId} item={item} />
        </div>
      ) : item.voiceChoices && item.voiceChoices.length > 0 ? (
        <VoiceFix bookId={bookId} item={item} />
      ) : item.lines && item.choices ? (
        <>
          <SpeakerFix bookId={bookId} item={item} onOpenScript={openScript} scope={scope} onScope={setScope} picked={picked} />
          {item.kind === "unnamed" && item.pickVoice && onPickVoice && (
            <Button size="sm" variant="ghost" className="edge-start-action mt-2" onClick={() => onPickVoice(item.pickVoice!)}>{S.s_gioi_giong_a5c7c7b7}</Button>
          )}
        </>
      ) : (
        <div role="group" className="mt-3 flex flex-wrap gap-1.5" aria-label={S.s_lua_chon_499eda35}>
          {item.options.map((option) => (
            <span key={option} className="rounded-control border border-line px-2.5 py-1 text-xs text-fg-2">
              {option}
            </span>
          ))}
        </div>
      )}
      {item.examples.length > 0 && (
        <MotionRegion motionKey={[scope, shownExamples.map(example => example.segmentId)]}><ul className="mt-3 space-y-2 border-t border-line pt-3">
          {picked && item.lines && (
            <li className="text-xs text-fg-2">{pickNote(picked.length, item.lines.length)}{S.s_bo_chon_cau_khong_phai_cua_nguoi_ay_c8d4e374}</li>
          )}
          {shownExamples.map((example) => (
            <Example
              key={example.segmentId}
              bookId={bookId}
              example={item.allLines && scope === "all" ? { ...example, changes: true } : example}
              {...(picked && example.stableId
                ? { picked: !left.has(example.stableId), onPick: () => setLeft(toggleLine(left, example.stableId!)) }
                : {})}
            />
          ))}
        </ul></MotionRegion>
      )}
      {item.pick && total > PICK_PREVIEW && (
        <div className="mt-2 flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="ghost"
            aria-expanded={all}
            onClick={() => {
              if (!all && next && more.length === 0) loadMore();
              setAll((value) => !value);
            }}
          >
            {all ? S.s_thu_gon_1f6bf2c3 : S.s_xem_ca_0_cau_444f6616(formatNumber(total))}
          </Button>
          {all && next && (
            <Button size="sm" variant="ghost" disabled={loadingMore} onClick={loadMore}>
              {loadingMore ? S.s_dang_tai_465b1987 : moreText(loaded.length, total, formatNumber)}
            </Button>
          )}
        </div>
      )}
      </MotionRegion>
    </Tag>
  );
}

/** Nhiều hơn ngần này lựa chọn thì phần còn lại gom vào “Người khác…”. */
const MAX_CHIPS = 6;
const GENERIC_PEOPLE = new Set<string>([S.s_nguoi_ke_fd36cd15, S.s_nguoi_ke_doc_tat_ca_97e4f69d, S.s_vai_phu_khong_ten_6395f0d2]);

/** Thẻ vai phụ cả cuốn hiện ngần này câu đầu; "Xem cả N câu" mở hết để bỏ chọn - nhóm lớn thì từng trang PICK_PAGE câu. */
const PICK_PREVIEW = 3;
const PICK_PAGE = 100;

// "Giữ như máy đang làm" cho cả loại thẻ đang lọc (soát UX a6 01-10, D2): sau khi soát vài thẻ thấy máy đúng gần hết, người
// làm sách bấm "giữ" từng thẻ một trong cả trăm thẻ. Một lần bấm (có hỏi lại) ghi đúng quyết định "giữ" mà từng thẻ ghi -
// không câu nào phải thu lại, máy thôi hỏi - và hoàn tác được cả nhóm.
const BULK_KINDS: WorkKind[] = ["pronunciation", "speaker", "caller", "turn", "vocative", "unnamed"];

function BulkKeep({ bookId, kind, items }: { bookId: string; kind: WorkKind; items: WorkItem[] }) {
  const client = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const pronunciation = kind === "pronunciation";
  const keepable = items.filter((item) => (pronunciation ? Boolean(item.surface) : keepRequests(item).length > 0));
  if (!BULK_KINDS.includes(kind) || keepable.length < 2) return null;
  const run = async () => {
    setBusy(true);
    const decisions: Record<string, unknown>[] = [];
    const replaced: string[] = [];
    let done = 0;
    try {
      for (const item of keepable) {
        if (pronunciation) {
          const { requestedAt, elsewhere } = await api<{ requestedAt: number; elsewhere?: { spokenForm?: string } }>(`/api/books/${bookId}/pronunciation`, {
            method: "POST",
            body: { surface: item.surface, spokenForm: item.current, seen: item.requested ?? "" },
          });
          if (elsewhere?.spokenForm !== undefined) replaced.push(elsewhere.spokenForm ? `“${elsewhere.spokenForm}”` : "");
          decisions.push({ surface: item.surface, requestedAt, previous: item.current, keep: true });
        } else {
          // Thẻ vai phụ cả cuốn giữ người của từng vai: một yêu cầu cho mỗi vai.
          for (const request of keepRequests(item)) {
            const answer = await api<{ requestedAt: number; elsewhere?: Record<string, string> }>(`/api/books/${bookId}/speaker`, {
              method: "POST",
              body: { ...request, seen: seenFor(request.lines, item.seen) },
            });
            replaced.push(...Object.values(answer.elsewhere ?? {}).map((value) => (value ? personOf(item, value) : "")));
            decisions.push({ lines: request.lines, requestedAt: answer.requestedAt, keep: true });
          }
        }
        done += 1;
      }
      const action = undoAction(client, bookId, pronunciation ? "pronunciation" : "speaker", decisions, S.s_0_the_tro_lai_cho_duyet_bff909d5(done));
      if (replaced.length) warnElsewhere(replaced.length, replaced[0], action.onClick);
      toast.success(S.s_da_giu_nhu_may_dang_lam_cho_0_the_8f7492cc(done), {
        action,
        duration: UNDO_MS,
      });
    } catch (error) {
      toast.error(S.s_moi_giu_duoc_0_1_the_58b9cdf5(done, keepable.length), { description: (error as Error).message });
    } finally {
      setBusy(false);
      setConfirm(false);
      refreshAfterDecision(client, bookId);
    }
  };
  return (
    <>
      <Button size="sm" variant="ghost" icon={Check} className="mt-3" onClick={() => setConfirm(true)}>{S.s_giu_d3777f80}{keepable.length}{S.s_the_5d800d1c}</Button>
      <Dialog footer={<DialogActions>
          <Button variant="ghost" onClick={() => setConfirm(false)}>{S.s_thoi_e68f9e88}</Button>
          <Button variant="primary" icon={Check} loading={busy} onClick={() => void run()}>{S.s_giu_ca_4b7c5467}{keepable.length}{S.s_the_5d800d1c}</Button>
        </DialogActions>}
        open={confirm}
        onOpenChange={setConfirm}
        title={S.s_giu_ca_0_the_1_33bc5807(keepable.length, KIND_LABEL[kind])}
        description={
          pronunciation
            ? S.s_giu_cach_doc_ten_khong_thu_lai_co_the_hoan_175ec7d0
            : S.s_giu_nguoi_noi_khong_thu_lai_co_the_hoan_ta_602c8451
        }
      >

      </Dialog>
    </>
  );
}

interface InboxProps {
  book: BookSummary;
  onOpenReview: OpenReview;
  onOpenScript?: OpenScript;
  onOpenNames?: OpenNames;
  onPickVoice?: PickVoice;
  /** Bộ lọc loại việc và thẻ cần cuộn tới, nằm trong địa chỉ trang - Back từ Kịch bản trở lại đúng chỗ đang duyệt. */
  kind?: string | null;
  focus?: string | null;
  onKind?: (kind: WorkKind | "all") => void;
  /** Thẻ đang nằm ở màn "Duyệt trước khi thu": không hiện lại ở đây, chỉ nói còn bao nhiêu và đường mở màn ấy. */
  inPrecast?: Set<string>;
  onOpenPrecast?: () => void;
}

/** Hộp "Việc cần duyệt": hết thẻ thì tiêu điểm về dòng báo cuối danh sách, không có thì lời mở đầu. */
const INBOX_ENDS: CardFocusEnds = { end: "work-end", lead: "work-lead" };

/** Một nhóm thẻ việc chọn sẵn (màn "Duyệt trước khi thu"): đúng thẻ của hộp việc, sửa ngay trên thẻ như ở đó. */
export function WorkCards({ book, items, onOpenReview, onOpenScript, onOpenNames, onPickVoice }: {
  book: BookSummary;
  items: WorkItem[];
  onOpenReview: OpenReview;
  onOpenScript?: OpenScript;
  onOpenNames?: OpenNames;
  onPickVoice?: PickVoice;
}) {
  return (
    <PendingHint.Provider value={PENDING_NOTE[applyWhen(book)]}>
      {/* Mỗi lựa chọn là một thẻ rời danh sách: khép tại chỗ như hộp việc chính (WorkInboxBody), không mất cứng. data-motion-live: vùng của
          bước duyệt bên ngoài không mờ lại cả trang theo từng thẻ. */}
      <div data-motion-live="">
      <AnimatedRows as="ol" className="rows-inset -mx-3 mt-3 [--rows-inset:calc(var(--spacing)*3)]" items={items} keyOf={(item) => item.key}>
        {(item, _index, state) => (
          <Card as="div" bookId={book.id} item={item} exiting={state === "exit"} onOpenReview={onOpenReview} onOpenScript={onOpenScript} onOpenNames={onOpenNames} onPickVoice={onPickVoice} />
        )}
      </AnimatedRows>
      </div>
    </PendingHint.Provider>
  );
}

export function WorkInbox(props: InboxProps) {
  // Sách đang chạy áp ở ranh giới chương kế tiếp, không "chờ chạy tiếp" (studio/decisions.ts).
  const hint = PENDING_NOTE[applyWhen(props.book)];
  return (
    <PendingHint.Provider value={hint}>
      <WorkInboxBody {...props} />
    </PendingHint.Provider>
  );
}

/** Số thay đổi đang chờ áp dụng trong các thẻ đã quyết: hai thẻ cùng quyết một câu (“Ai nói câu này” + “Gọi hay nói”) là MỘT thay đổi -
 *  khớp số trên nút “Áp dụng N thay đổi”. “Giữ” cách đang đọc là đã quyết mà không có gì chờ áp dụng. */
export function waitingChanges(decided: WorkItem[]): number {
  const changes = new Set<string>();
  for (const item of decided) {
    if (item.requested === item.current) continue;
    const lines = item.lines?.map((line) => line.stableId).sort();
    changes.add(lines?.length ? `lines:${lines.join(",")}` : `key:${item.key}`);
  }
  return changes.size;
}

function WorkInboxBody({ book, onOpenReview, onOpenScript, onOpenNames, onPickVoice, kind: kindParam, focus, onKind, inPrecast, onOpenPrecast }: InboxProps) {
  const bookId = book.id;
  const hint = useContext(PendingHint);
  const [kind, setKindState] = useState<WorkKind | "all">(
    kindParam && kindParam in KIND_LABEL ? (kindParam as WorkKind) : "all",
  );
  const setKind = (value: WorkKind | "all") => {
    setKindState(value);
    onKind?.(value);
  };
  const [shown, setShown] = useState(PAGE);
  // Phím tắt (soát UX a6 01-10, D1): J / K chọn thẻ, 1-9 bấm lựa chọn thứ N của thẻ ấy - duyệt cả trăm thẻ không cần chuột.
  // Quyết xong thì thẻ rời danh sách, nên thẻ kế tự đứng vào đúng chỗ đang chọn.
  const [cursor, setCursorState] = useState<number | null>(null);
  const cursorRef = useRef<number | null>(null);
  const setCursor = (value: number | null) => {
    cursorRef.current = value;
    setCursorState(value);
  };
  const keys = useRef<{ items: WorkItem[] }>({ items: [] });
  useEffect(() => {
    const onKey = workKeyHandler(() => keys.current.items, () => cursorRef.current, setCursor, INBOX_ENDS);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // setCursor chỉ ghi ref + state - không cần gắn lại.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  // Quyết / hoàn tác làm thẻ đang giữ tiêu điểm rời danh sách: tiêu điểm sang thẻ kế thay vì rơi về BODY (useCardFocus.ts).
  const lists = useRef<WorkLists | null>(null);
  useCardFocus(lists, INBOX_ENDS);
  const refetchInterval = useProducingRefetch(bookId);
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["work", bookId],
    queryFn: () => api<WorkView>(`/api/books/${bookId}/work`),
    refetchInterval,
  });
  // Trở lại từ Kịch bản (Back hay "Về Việc cần duyệt"): cuộn tới đúng thẻ vừa rời, mở đủ trang để thấy nó - một lần.
  const focused = useRef(false);
  useEffect(() => {
    if (focused.current || !focus || !data) return;
    focused.current = true;
    const index = data.items.filter((item) => isOpenWork(item) && (kind === "all" || item.kind === kind)).findIndex((item) => item.key === focus);
    if (index >= PAGE) setShown(Math.ceil((index + 1) / PAGE) * PAGE);
    window.setTimeout(() => document.getElementById(`work-${focus}`)?.scrollIntoView({ block: "center" }), 0);
  }, [focus, data, kind]);
  // Quyết xong việc cuối của loại đang lọc: về “Tất cả” cả trong địa chỉ trang, không thì tải lại (hay quay lại) vẫn lọc loại đã hết thẻ (soát UX a11).
  useEffect(() => {
    if (!data || kind === "all") return;
    if (!data.items.some((item) => isOpenWork(item) && item.kind === kind && !inPrecast?.has(item.key))) setKind("all");
    // setKind chỉ ghi state + gọi onKind - không cần gắn lại.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, kind, inPrecast]);
  if (error && !data) return <MotionRegion fadeThrough><InlineError className="mt-6" message={S.s_ban_hay_kiem_tra_ket_noi_roi_tai_lai_viec_718b2054} onRetry={() => void refetch()} /></MotionRegion>;
  if (isLoading || !data) return <MotionRegion fadeThrough><ContentSkeleton shape="cards" className="mt-6" label={S.s_dang_tai_viec_duyet_f68f3839} /></MotionRegion>;
  if (!data.items.length) {
    return (
      <MotionRegion><EmptyState icon={AudioLines} title={S.s_khong_con_viec_duyet_21f808a7} className="py-10">{S.s_may_chac_chan_ve_moi_thu_da_lam_toi_gio_15f0b56b}</EmptyState></MotionRegion>
    );
  }
  // Việc đã quyết (chờ áp dụng) xuống mục thu gọn cuối trang và không tính vào số đếm.
  const undecided = data.items.filter(isOpenWork);
  // Chưa quyết mà chỉ áp khi làm lại phân tích: nhóm riêng cuối trang, không đếm, không đứng chung với việc áp ngay.
  const later = data.items.filter((item) => !item.requested && item.redoOnly);
  const open = inPrecast ? undecided.filter((item) => !inPrecast.has(item.key)) : undecided;
  const atReview = undecided.length - open.length;
  const answered = data.items.filter((item) => item.requested);
  // Đã ghi mà chỉ áp khi làm lại sách (đoạn người kể đã phân tích xong): nhóm riêng, không có nút "Áp dụng thay đổi" nào cho nó.
  const redo = answered.filter((item) => item.redoOnly);
  const decided = answered.filter((item) => !item.redoOnly);
  // "Giữ" cách đang đọc là đã quyết mà không có gì chờ áp dụng - không đếm vào "chờ áp dụng" (soát UX 29-09).
  const waiting = waitingChanges(decided);
  const counts: Partial<Record<WorkKind, number>> = {};
  for (const item of open) counts[item.kind] = (counts[item.kind] ?? 0) + 1;
  const kinds = (Object.keys(KIND_LABEL) as WorkKind[]).filter((value) => counts[value]);
  // Quyết xong việc cuối của loại đang lọc thì loại ấy biến khỏi thanh lọc - về "Tất cả", đừng để danh sách trống không lời.
  const active = kind !== "all" && !counts[kind] ? "all" : kind;
  const items = open.filter((item) => active === "all" || item.kind === active);
  keys.current.items = items.slice(0, shown);
  lists.current = { open: keys.current.items.map((item) => item.key), decided: decided.map((item) => item.key) };
  const at = cursor === null ? null : Math.min(cursor, Math.max(items.slice(0, shown).length - 1, 0));
  return (
    <MotionRegion as="div" className="motion-reveal mt-5">
      {/* Lời mở đầu theo trạng thái sách - soát UX 29-09: "đang chạy tiếp" hiện cả khi sách đã xong hay đang dừng. */}
      <p id="work-lead" tabIndex={-1} className="max-w-3xl text-sm text-fg-2">
        {inboxLead(book)}
      </p>
      {atReview > 0 && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
          <span className="min-w-0 text-pretty">
            {atReview}{S.s_viec_cua_cac_chuong_dau_dang_cho_o_duyet_t_ffc8b06a}</span>
          {onOpenPrecast && (
            <Button size="sm" variant="ghost" onClick={onOpenPrecast}>{S.s_mo_man_duyet_5d7f194c}</Button>
          )}
        </div>
      )}
      <div className="mt-4">
        <FilterRow<WorkKind | "all">
          label={S.s_loai_viec_19d758cd}
          value={active}
          onChange={(value) => {
            setKind(value);
            setShown(PAGE);
          }}
          options={[
            { value: "all", label: S.s_tat_ca_0_bc914efb(open.length) },
            ...kinds.map((value) => ({ value, label: `${KIND_LABEL[value]} · ${counts[value]}` })),
          ]}
        />
      </div>
      {active !== "all" && <BulkKeep bookId={bookId} kind={active} items={items} />}
      <p className="mt-2 hidden flex-wrap items-center gap-1.5 text-xs text-fg-3 md:flex">
        <Kbd>{S.s_j_6da43b94}</Kbd> <Kbd>{S.s_k_86be9a55}</Kbd>{S.s_chon_the_d4ce1760}<Kbd>1–9</Kbd>{S.s_chon_dap_an_4ef796c6}<Kbd>{S.s_esc_52f878ed}</Kbd>{S.s_bo_chon_647a1871}</p>
      {/* Đổi loại việc: cả danh sách trượt theo hướng mục vừa chọn; danh sách mới dựng lại từ đầu, không lẫn thẻ cũ đang mờ ra. */}
      <MotionRegion motionKey={active} slideIndex={active === "all" ? 0 : kinds.indexOf(active) + 1}>
      <AnimatedRows key={active} as="ol" className="rows-inset -mx-3 mt-3 [--rows-inset:calc(var(--spacing)*3)]" items={items.slice(0, shown)} keyOf={(item) => item.key}>
        {(item, _index, state) => (
          <Card as="div" key={item.key} bookId={bookId} item={item} exiting={state === "exit"} active={state !== "exit" && item.key === keys.current.items[at ?? -1]?.key} onOpenReview={onOpenReview} onOpenScript={onOpenScript} onOpenNames={onOpenNames} onPickVoice={onPickVoice} />
        )}
      </AnimatedRows>
      </MotionRegion>
      <MotionPresence open={items.length > shown}>
        <Button variant="ghost" size="sm" className="mt-4" onClick={() => setShown(shown + PAGE)}>{S.s_xem_them_58c3f515}{Math.min(PAGE, items.length - shown)}{S.s_viec_1c50ca93}</Button>
      </MotionPresence>
      <MotionPresence open={!open.length && atReview === 0}>
        <p id="work-end" tabIndex={-1} className="mt-4 text-sm text-fg-2">
          {later.length > 0
            ? S.s_het_viec_sua_duoc_ngay_nhung_viec_ben_duoi_2b4551c3
            : S.s_moi_viec_da_co_quyet_dinh_0_b683c4dd(decided.length > 0 ? ` - ${hint}` : "")}
        </p>
      </MotionPresence>
      {/* Ba nhóm phụ: thẻ vào / ra (Hoàn tác, quyết thêm) khép / mở tại chỗ. data-motion-live: vùng cả hộp không mờ lại theo từng thẻ. */}
      <MotionPresence open={decided.length > 0}>
        <details className="mt-6 border-t border-line">
          <summary className="touch-reach cursor-pointer text-sm font-medium text-fg-2">
            {waiting === decided.length ? S.s_da_quyet_cho_ap_dung_0_viec_87d1149b(decided.length) : S.s_da_quyet_0_viec_1_thay_doi_cho_ap_dung_9f6d58ae(decided.length, waiting)}
          </summary>
          <div data-motion-live="">
          <AnimatedRows as="ol" className="rows-inset -mx-3 mt-3 [--rows-inset:calc(var(--spacing)*3)]" items={decided} keyOf={(item) => item.key}>
            {(item, _index, state) => <Card as="div" bookId={bookId} item={item} exiting={state === "exit"} onOpenReview={onOpenReview} onOpenNames={onOpenNames} onPickVoice={onPickVoice} />}
          </AnimatedRows>
          </div>
        </details>
      </MotionPresence>
      <MotionPresence open={later.length > 0}>
        <details className="mt-4 border-t border-line">
          <summary className="touch-reach cursor-pointer text-sm font-medium text-fg-2">{S.s_cho_phan_tich_lai_8038a2ac}</summary>
          <p className="mt-2 max-w-3xl text-pretty text-xs text-fg-2">{S.s_chi_ap_khi_phan_tich_lai_khong_chan_sach_c_56e246b0}</p>
          <div data-motion-live="">
          <AnimatedRows as="ol" className="rows-inset -mx-3 mt-3 [--rows-inset:calc(var(--spacing)*3)]" items={later} keyOf={(item) => item.key}>
            {(item, _index, state) => <Card as="div" bookId={bookId} item={item} exiting={state === "exit"} onOpenReview={onOpenReview} onOpenScript={onOpenScript} onOpenNames={onOpenNames} onPickVoice={onPickVoice} />}
          </AnimatedRows>
          </div>
        </details>
      </MotionPresence>
      <MotionPresence open={redo.length > 0}>
        <details className="mt-4 border-t border-line">
          <summary className="touch-reach cursor-pointer text-sm font-medium text-fg-2">{S.s_da_ghi_6fd13e0b}</summary>
          <div data-motion-live="">
          <AnimatedRows as="ol" className="rows-inset -mx-3 mt-3 [--rows-inset:calc(var(--spacing)*3)]" items={redo} keyOf={(item) => item.key}>
            {(item, _index, state) => <Card as="div" bookId={bookId} item={item} exiting={state === "exit"} onOpenReview={onOpenReview} onOpenNames={onOpenNames} onPickVoice={onPickVoice} />}
          </AnimatedRows>
          </div>
        </details>
      </MotionPresence>
    </MotionRegion>
  );
}

import { S } from "../shared/strings.generated";
import { MotionRegion } from "@/shared/MotionRegion";
import { SectionHeading } from "@/shared/SectionHeading";
import { DisclosureRow } from "@/shared/DisclosureRow";
import { MotionPresence } from "@/shared/MotionPresence";
import { useListPresence, type PresentRow } from "@/shared/motion";
import { Collapse, Fold, useFold } from "@/shared/Collapse";
import { MoreInfo } from "@/shared/SettingsNav";
import {
  AlertTriangle,
  Check,
  FileText,
  Folder,
  FolderInput,
  Gauge,
  Info,
  Layers,
  Loader2,
  Mic,
  Play,
  Scissors,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  Upload,
  Wand2,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router";
import { toast, toastDone } from "@/shared/toast";
import { Switch } from "@/desktop/Switch";
import { useClip } from "@/listen/clip";
import { useSource } from "@/listen/source";
import { cn } from "@/shared/cn";
import { ScreenHeader } from "@/shared/ScreenHeader";
import { usePageTitle } from "@/shared/title";
import { useScrollFadeOn } from "@/shared/scrollFade";
import { formatLength, formatNumber } from "@/shared/format";
import { spokenProgress } from "@/shared/progressSpeech";
import { Button, LiveText, ChoiceRow, Vu, radioGroupKeys, radioTabIndex } from "@/shared/ui";
import type { ContinuationPlan, FirstPersonHint, ScannedFile, ScanResult, Voice } from "@/studio/api";
import {
  pickFiles,
  pickFolder,
  usePreferences,
  useAppInfo,
  useContinuation,
  useRedo,
  useCreateBook,
  useFirstPersonHint,
  useScan,
  useStudioMissing,
  useVoices,
} from "@/studio/data";
import { api } from "@/studio/api";
import { chapterNumberIssues } from "@/studio/chapterNumbers";
import { narratorIsAuto, recommendedFor, type TellerGender } from "@/studio/narratorChoice";
import { TELLER_TITLE, tellerHint } from "@/studio/tellerMode";
import { creditKind, creditLine, creditRows, creditSummary, creditWhere, droppedLines, KEEP_CREDITS, type CreditDrop, type Credits } from "@/studio/credits";
import { samePath } from "@/studio/samePath";
import { watchAppDropPaths } from "@/studio/appDrops";
import { MatterSuggestion } from "@/studio/MatterSuggestion";
import { allExcluded, approx, keepMatter } from "@/studio/scanView";
import { createGate, scanIsCurrent, sourcesKey, type ScannedSources } from "@/studio/scanState";
import { isSourceRef, sourceName } from "@/studio/sourceRef";
import { splitOutcome } from "@/studio/splitOffer";
import {
  UPLOAD_ACCEPT,
  batchName,
  canPickFolder,
  pickedFromDrop,
  pickedFromInput,
  planNotice,
  planUpload,
  progressLabel,
  sendPlan,
  sendSummary,
  UPLOAD_LIMIT,
  type Picked,
  type UploadProgress,
} from "@/studio/upload";
import { AnalysisModelPicker, analysisChoiceLabel, useAnalysisModels, useAvailableModelNames } from "@/studio/AnalysisModelPicker";
import { DEFAULT_LABEL, applyTemplate, changedChoices, templateChoices, type BookTemplate, type Profile } from "@/studio/bookTemplates";
import { NoStudioHere, StudioInstallNotice, useStudioFit, useStudioGpu } from "@/studio/StudioSetup";
import { estimate, lengthRange, matchesMeasured, timeBasis } from "@/studio/timeEstimate";
import type { StudioFit } from "@/studio/studioFit";
import { TemplateBar } from "@/studio/TemplateBar";
import { VolumeSplit } from "@/studio/VolumeSplit";
import { inOrder, ranges, startNumbers, volumeTitles } from "@/studio/volumes";

const PROFILES: { value: Profile; title: string; pace: string; summary: string; points: string[] }[] = [
  {
    value: "fast",
    title: S.s_nhanh_c2385879,
    pace: S.s_nhanh_nhat_3e80ad74,
    summary: S.s_nghe_thu_mot_truyen_moi_hoac_can_gap_7595a3d8,
    points: [S.s_may_hieu_truyen_theo_tung_doan_dai_mot_lan_e6cda2fb, S.s_soat_co_ban_sau_khi_doc_2e51d472, S.s_doc_lai_toi_da_1_lan_neu_cau_bi_doc_sai_82e58722],
  },
  {
    value: "balanced",
    title: S.s_can_bang_8b88211d,
    pace: S.s_vua_phai_8c671657,
    summary: S.s_nghe_hang_ngay_chap_nhan_vai_cau_chua_hoan_2bc0c77a,
    points: [S.s_phan_tich_truyen_day_du_7d2d439e, S.s_soat_co_ban_sau_khi_doc_2e51d472, S.s_doc_lai_toi_da_2_lan_neu_cau_bi_doc_sai_4d15b713],
  },
  {
    value: "high_quality",
    title: S.s_chat_luong_cao_dc7017a7,
    pace: S.s_cham_nhat_ky_nhat_ff0d4141,
    summary: S.s_sach_nghe_lai_nhieu_lan_hoac_de_chia_se_c35352d9,
    points: [S.s_ra_lai_cam_xuc_tung_cau_mot_lan_nua_5d40fd1d, S.s_nghe_lai_moi_cau_soat_ky_tung_chu_88b14719, S.s_doc_lai_toi_5_lan_neu_cau_bi_doc_sai_df336644],
  },
];
const PROFILE_VALUES = PROFILES.map((option) => option.value);
// Chọn nhanh số chương cho một đợt - chỉ hiện khi nguồn có nhiều hơn mức nhỏ nhất.
const CHAPTER_LIMITS = [20, 50, 100];

// ---- Nháp: rời trang rồi quay lại không mất gì ----------------------------------------------------------------

interface Draft {
  paths: string[];
  excluded: string[];
  /** Trang phụ của file sách (bìa, bản quyền, mục lục...) mà người dùng đã TÍCH lại: mặc định chúng chưa vào sách, như Nghe ngay. */
  keepMatter?: string[];
  title: string;
  titleEdited: boolean;
  narrator: string;
  /** Người dùng đã tự chọn giọng kể (bấm một giọng, hay áp mẫu có ghi giọng): không thì máy chọn giọng dẫn cùng giới người kể "tôi". */
  narratorPicked?: boolean;
  /** Người xưng "tôi" ở truyện kể ngôi thứ nhất ("" = ngôi thứ ba). */
  firstPerson: string;
  /** Giới của người kể "tôi" (người dùng nói; không có = chưa rõ, máy tự đoán sau khi đọc truyện). */
  firstPersonGender?: TellerGender;
  /** B (tuỳ chọn, mặc định tắt): người kể "tôi" tự kể chuyện - lời kể của đoạn họ kể cũng đọc bằng giọng của họ (abook/teller_voice.py). */
  tellerMode?: boolean;
  /** Chương đổi góc kể (gợi ý của máy) mà người dùng bỏ chọn - số chương trong sách. */
  povOff?: number[];
  /** "Sửa thiết lập": chương đổi người kể đã chọn lúc tạo - đổi thành `povOff` ngay khi máy đọc xong gợi ý đổi góc kể của truyện. */
  povKept?: Record<string, string>;
  profile: Profile;
  startNow: boolean;
  /** "Duyệt trước khi thu" (webui/precast.py): phân tích xong thì sách tạm dừng chờ người duyệt. Mặc định tắt. */
  precastWait?: boolean;
  /** "Làm tiếp cuốn này": phần trước để gieo từ (continuation.py), hay không có khi là sách mới. */
  seed?: Seed;
  /** Chip "Đợt này làm N chương đầu": N chương đầu trong số chương CHƯA bị bỏ tay (null/không có = tất cả). Tách khỏi
   *  `excluded` - trước đây chip ghi đè danh sách bỏ tay, chương vừa bỏ tự quay lại (soát UX 29-09). */
  limit?: number | null;
  /** "Chia thành nhiều tập" (B7): đường dẫn chương đầu mỗi tập người dùng đã đồng ý chia; null/không có = một sách. */
  volumeStarts?: string[] | null;
  /** Người dùng ĐỒNG Ý bỏ dòng ghi công (đầu chương) / xin ủng hộ (cuối chương) khỏi phần đọc - chọn riêng. Mặc định không: app
   *  không tự sửa nội dung truyện. */
  dropCredits?: CreditDrop;
  /** Model đọc hiểu truyện chỉ cho cuốn này ("" hay không có = mặc định của app). */
  analysisModel?: string;
  /** Tên mẫu thiết lập đang theo (studio/bookTemplates.ts); không có = mặc định của app. Mẫu bị xoá/đổi tên thì coi như không có. */
  template?: string;
  /** "Sửa thiết lập" (?redo=<id>): cuốn chưa bắt đầu sẽ được thay bằng cuốn này; phần trước của nó nếu là phần nối tiếp. */
  replaces?: { id: string; title: string; seedFrom?: string; restart?: boolean };
}

interface Seed {
  id: string;
  title: string;
  part: number;
  analyzed: boolean;
  /** Thư mục truyện chưa có chương nào sau chương cuối của phần trước lúc mở trình tạo. */
  empty: boolean;
  carries: ContinuationPlan["carries"];
  /** Giọng kể của phần trước (nháp cũ không có). */
  narrator?: string;
  /** Thư mục truyện + file chương cuối đã làm - khung "chưa có chương mới" nói rõ chỗ. */
  folder?: string;
  lastChapter?: string;
  /** Mở từ một phần cũ hơn phần mới nhất (tên phần ấy). */
  clickedTitle?: string;
  latestTitle?: string;
  /** Model đọc hiểu phần trước dùng (khác mặc định), hay model ấy đã không còn trong Ollama. */
  analysisModel?: string;
  analysisModelMissing?: string;
}

const DRAFT_KEY = "abook-new-book-draft";
const EMPTY_DRAFT: Draft = {
  paths: [], excluded: [], title: "", titleEdited: false, narrator: "", firstPerson: "", profile: "high_quality", startNow: true,
};

function loadDraft(): Draft {
  try {
    return { ...EMPTY_DRAFT, ...JSON.parse(sessionStorage.getItem(DRAFT_KEY) ?? "{}") };
  } catch {
    return EMPTY_DRAFT;
  }
}

function saveDraft(draft: Draft | null): void {
  try {
    if (draft) sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    else sessionStorage.removeItem(DRAFT_KEY);
  } catch {
    /* không lưu được nháp thì thôi */
  }
}

/** Giọng kể mặc định cho sách mới (Cài đặt > Studio): giọng người dùng đặt nếu còn trong danh sách giọng, không thì giọng máy đề xuất. */
function defaultNarrator(voices: Voice[], preferred?: string): string {
  const chosen = preferred ? voices.find((voice) => voice.name === preferred) : undefined;
  return chosen ? chosen.name : (voices.find((voice) => voice.recommended)?.name ?? voices[0].name);
}

function cleanPath(value: string): string {
  return value.trim().replace(/^["']+|["']+$/g, "").trim();
}

// ---- Nguồn -----------------------------------------------------------------------------------------------------

export function SourceStep({
  scan,
  title,
  onTitle,
  scanning,
  onPaths,
  onAddFiles,
  onRemove,
  total,
  limit,
  later,
  onLimit,
  problem,
  dropCredits,
  onDropCredits,
  onSplit,
  previousLast,
  replaces,
  volumeSplit,
  splitting,
  volumeStarts,
  matter,
  onKeepMatter,
}: {
  /** Trang phụ của file sách (EPUB / DOCX) trong lần quét: chưa tích sẵn; `keep` là những trang người dùng đã tích lại. */
  matter: { files: ScannedFile[]; keep: string[] };
  onKeepMatter: (path: string, on: boolean) => void;
  /** Số chương đầu mỗi tập khi đang chia: số chương soát riêng từng tập (mỗi tập đánh số lại từ 1). */
  volumeStarts?: number[];
  /** "Chia thành nhiều tập": khung đề xuất / danh sách tập (VolumeSplit) và đang chia hay không (chia rồi thì "N chương đầu" vô nghĩa). */
  volumeSplit?: ReactNode;
  splitting?: boolean;
  /** "Sửa thiết lập": cuốn đang được làm lại - không nhắc "đã có dự án" về chính nó. */
  replaces?: { id: string; title: string; restart?: boolean };
  scan: ScanResult | null;
  title: string;
  onTitle: (title: string) => void;
  scanning: boolean;
  onPaths: (paths: string[]) => void;
  onAddFiles: (paths: string[]) => void;
  onRemove: (path: string) => void;
  /** Số chương đọc được trong nguồn, trước khi bỏ chương nào. */
  total: number;
  /** Giới hạn đang chọn (null = tất cả) và số chương để dành cho đợt sau. */
  limit: number | null;
  later: number;
  /** Chỉ làm `count` chương đầu (theo thứ tự tên file, sau các chương bỏ tay), hay tất cả khi null. */
  onLimit: (count: number | null) => void;
  problem: { text: string; subfolders: string[] } | null;
  dropCredits: CreditDrop;
  onDropCredits: (value: CreditDrop) => void;
  /** Tách một file cả truyện thành các chương (máy ghi thư mục mới), rồi quét thư mục ấy thay cho file. */
  onSplit: (path: string) => Promise<void>;
  /** "Làm tiếp": file chương cuối của phần trước - phần này phải bắt đầu ngay sau nó. */
  previousLast?: string;
}) {
  const { data: info } = useAppInfo();
  const [chapterList, setChapterList] = useState<HTMLDivElement | null>(null);
  const chapterFade = useScrollFadeOn(chapterList);
  const [typed, setTyped] = useState("");
  // Studio trong trình duyệt (từ xa, hay ngay trên máy tính mà không có hộp chọn file của app): máy đang xem không có đường
  // dẫn nào trên máy tính để gõ - nó gửi các chương đi (studio/upload.ts). Ô dán đường dẫn lui vào "Nâng cao".
  const browser = Boolean(info) && !info?.dialogs;
  const filesInput = useRef<HTMLInputElement | null>(null);
  const folderInput = useRef<HTMLInputElement | null>(null);
  const appending = useRef(false);
  const folderPick = useMemo(canPickFolder, []);
  const [uploading, setUploading] = useState<UploadProgress | null>(null);
  // Huỷ gửi (soát a92 V4): tín hiệu đi xuyên đọc + gửi từng file; rời trang thì dừng luôn, khỏi gửi nốt vào "Nguồn tải lên" khi không ai theo dõi.
  const sending = useRef<AbortController | null>(null);
  const [stopping, setStopping] = useState(false);
  useEffect(() => () => sending.current?.abort(), []);
  const cancelUpload = () => {
    setStopping(true);
    sending.current?.abort();
  };
  const [dragging, setDragging] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const upload = async (picked: (Picked & { file: File })[], append: boolean) => {
    if (!picked.length || uploading) return;
    const plan = planUpload(picked, batchName(new Date(), Math.random().toString(36).slice(2, 6)));
    const notice = planNotice(plan);
    if (!plan.groups.length) {
      toast.error(S.s_khong_co_file_truyen_nao_de_gui_d7431246, {
        description: notice ?? S.s_chon_cac_file_txt_moi_file_mot_chuong_hay_ab6662ed,
      });
      return;
    }
    if (notice) toast.warning(S.s_co_file_khong_gui_2d8a5d11, { description: notice });
    const controller = new AbortController();
    sending.current = controller;
    try {
      const result = await sendPlan(plan, setUploading, controller.signal);
      // File đã tới máy tính thì giữ (huỷ hay hỏng giữa chừng cũng vậy): người dùng làm tiếp được, và nói rõ đã gửi bao nhiêu.
      if (result.paths.length) (append ? onAddFiles : onPaths)(result.paths);
      if (result.error) toast.error(S.s_khong_gui_het_cac_chuong_eda12b69, { description: `${result.error.message} ${sendSummary(result)}` });
      else if (result.cancelled) toast(result.sent ? S.s_da_dung_gui_0_f0b1325f(sendSummary(result)) : S.s_da_huy_gui_d2e596a4);
    } finally {
      sending.current = null;
      setStopping(false);
      setUploading(null);
    }
  };
  const browse = (input: HTMLInputElement | null, append: boolean) => {
    appending.current = append;
    input?.click();
  };
  const percent = uploading?.totalBytes ? Math.round((uploading.bytes / uploading.totalBytes) * 100) : 0;
  const chooseFolder = async () => {
    const path = await pickFolder(S.s_chon_thu_muc_chua_cac_chuong_txt_d3c22d58).catch((error: Error) => {
      toast.error(error.message);
      return null;
    });
    if (path) onPaths([path]);
  };
  const chooseFiles = async (append: boolean) => {
    const chosen = await pickFiles(S.s_chon_cac_chuong_txt_hay_mot_file_sach_epub_cd4fd0b8).catch((error: Error) => {
      toast.error(error.message);
      return [];
    });
    if (chosen.length) (append ? onAddFiles : onPaths)(chosen);
  };
  const files = scan?.files ?? [];
  // DESIGN.md §2 L10 (Studio -> Dự án mới -> chọn file -> Bắt đầu, ≤ 3 chạm): tới từ nút "Dự án mới" thì mở luôn hộp chọn file của app - thư
  // mục, dán đường dẫn, kéo thả vẫn nằm ngay trang này khi bạn huỷ. Một lần: xoá dấu khỏi lịch sử để Back / tải lại không mở lại hộp.
  const location = useLocation();
  const navigate = useNavigate();
  const pickOnOpen = (location.state as { pick?: boolean } | null)?.pick === true;
  const pickedOnOpen = useRef(false);
  useEffect(() => {
    if (!pickOnOpen || !info || pickedOnOpen.current) return;
    pickedOnOpen.current = true;
    navigate(`${location.pathname}${location.search}`, { replace: true, state: null });
    if (info.dialogs && !files.length) void chooseFiles(false);
  }, [pickOnOpen, info]); // eslint-disable-line react-hooks/exhaustive-deps
  // Cửa sổ app: vỏ Tauri nuốt sự kiện thả của HTML5 và phát `abook-drag` kèm đường dẫn thật (như Thư viện) - nghe nó để khung nét đứt nhận file.
  const dropTarget = useRef({ files: files.length, onPaths, onAddFiles });
  dropTarget.current = { files: files.length, onPaths, onAddFiles };
  const appWindow = Boolean(info?.dialogs);
  useEffect(() => {
    if (!appWindow) return undefined;
    return watchAppDropPaths({
      hover: setDragging,
      drop: (paths) => {
        const target = dropTarget.current;
        if (paths.length) (target.files ? target.onAddFiles : target.onPaths)(paths);
      },
    });
  }, [appWindow]);
  const onPicked = (event: { target: HTMLInputElement }) => {
    if (event.target.files) void upload(pickedFromInput(event.target.files), appending.current);
    event.target.value = "";
  };
  return (
    <MotionRegion as="div">
      {browser && (
        <>
          <input
            ref={filesInput}
            type="file"
            multiple
            accept={UPLOAD_ACCEPT}
            className="sr-only"
            tabIndex={-1}
            aria-hidden
            onChange={onPicked}
          />
          <input
            // Chọn cả thư mục: thuộc tính chưa có trong kiểu của React, gắn thẳng vào thẻ.
            ref={(node) => {
              folderInput.current = node;
              node?.setAttribute("webkitdirectory", "");
            }}
            type="file"
            multiple
            className="sr-only"
            tabIndex={-1}
            aria-hidden
            onChange={onPicked}
          />
        </>
      )}
      <SectionHeading>{S.s_nguon_truyen_ddecd9bb}</SectionHeading>
      <p className="mt-1 text-sm text-fg-2">{S.s_chon_txt_epub_word_hoac_pdf_co_chu_5e38434f}</p>
      <Fold storageKey="new-project.formats" title={S.s_dinh_dang_36b746b6} className="mt-3" heading="h3"><ul className="list-disc space-y-1 pl-5 text-sm text-fg-2">
        <li>{S.s_moi_file_txt_la_mot_chuong_xep_theo_ten_fi_50c79061}</li>
        <li>{S.s_epub_word_pdf_co_chu_chon_thang_may_tu_tac_6fe43d31}</li>
        <li>{S.s_ca_truyen_nam_trong_mot_file_txt_thi_may_g_67a7c9cb}</li>
      </ul></Fold>
      {!files.length ? (
        <div
          className={cn(
            "mt-6 rounded-cover border-2 border-dashed bg-panel px-8 py-10 text-center transition-colors max-sm:px-4",
            dragging ? "border-accent bg-accent-soft" : "border-line-strong",
          )}
          // Kéo thả file hay cả thư mục truyện vào khung (trình duyệt; cửa sổ app có hộp chọn của Windows).
          onDragOver={(event) => {
            if (!browser || uploading || !event.dataTransfer.types.includes("Files")) return;
            event.preventDefault();
            event.dataTransfer.dropEffect = "copy";
            setDragging(true);
          }}
          onDragLeave={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false);
          }}
          onDrop={(event) => {
            if (!browser || uploading) return;
            event.preventDefault();
            setDragging(false);
            pickedFromDrop(event.dataTransfer).then(
              (picked) => upload(picked, false),
              (error: Error) => toast.error(S.s_chua_doc_duoc_cac_file_vua_tha_a0eba75e, { description: error.message }),
            );
          }}
        >
          <div className="mx-auto grid size-14 place-items-center rounded-cover bg-accent-soft text-accent-text">
            <MotionRegion as="span" className="inline-grid place-items-center">{scanning || uploading ? <Loader2 className="size-7 animate-spin" /> : <FolderInput className="size-7" strokeWidth={1.75} />}</MotionRegion>
          </div>
          <p className="mt-4 font-medium">
            {scanning
              ? S.s_dang_doc_cac_chuong_ec75d38e
              : browser
                ? folderPick
                  ? S.s_chon_hay_keo_tha_vao_day_cac_chuong_cua_tr_77883a5f
                  : S.s_gui_cac_chuong_tu_may_nay_ac7786f4
                : S.s_chon_hay_keo_tha_vao_day_thu_muc_truyen_ha_978b59fe}
          </p>
          <p className="mt-1 text-sm text-fg-2 text-pretty">
            {browser
              ? S.s_cac_file_txt_0_hoac_mot_file_epub_docx_pdf_3bd70a5b(folderPick ? S.s_hay_ca_thu_muc_b71bcc1b : "", UPLOAD_LIMIT / 2 ** 20)
              : S.s_chi_lay_file_nam_ngay_trong_thu_muc_khong_29e37f3e}
          </p>
          {browser && (
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              <Button variant="primary" icon={Upload} disabled={Boolean(uploading)} onClick={() => browse(filesInput.current, false)}>{S.s_chon_file_f43fd47b}</Button>
              {folderPick && (
                <Button icon={Folder} disabled={Boolean(uploading)} onClick={() => browse(folderInput.current, false)}>{S.s_chon_thu_muc_1fe47e38}</Button>
              )}
            </div>
          )}
          {uploading && (
            <div className="mx-auto mt-4 max-w-xs" role="status">
              <div
                role="progressbar"
                aria-label={S.s_dang_gui_cac_chuong_d7b47553}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={percent}
                className="h-1.5 overflow-hidden rounded-full bg-hover"
              >
                <div className="motion-progress h-full rounded-full bg-accent" style={{ transform: `scaleX(${percent / 100})` }} />
              </div>
              <p className="mt-1.5 text-xs text-fg-2">
                <LiveText shown={progressLabel(uploading)} spoken={spokenProgress(S.s_dang_gui_cac_chuong_d7b47553, uploading.totalBytes ? uploading.bytes / uploading.totalBytes : null)} />
              </p>
              <Button className="mt-2" size="sm" variant="ghost" disabled={stopping} onClick={cancelUpload}>
                {stopping ? S.s_dang_dung_9b35aeb5 : S.s_huy_gui_4d53a582}
              </Button>
            </div>
          )}
          {info?.dialogs && (
            <div className="mt-6 flex justify-center gap-2">
              <Button variant="primary" icon={Folder} onClick={() => void chooseFolder()}>{S.s_chon_thu_muc_1fe47e38}</Button>
              <Button icon={FileText} onClick={() => void chooseFiles(false)}>{S.s_chon_tung_file_c6f96077}</Button>
            </div>
          )}
          {info?.remote ? null : browser && !advanced ? (
            // Studio từ xa: đường dẫn trên máy tính chỉ máy tính có - thiết bị gửi chương lên (hay "Làm lại" / "Làm tiếp" dùng chương của chính cuốn ấy).
            // Đường dẫn trên máy tính chỉ người rành máy mới cần (thư mục đã có sẵn trên máy tính, file quá lớn để gửi).
            <button
              type="button"
              aria-expanded={false}
              onClick={() => setAdvanced(true)}
              className="mt-5 text-[0.8125rem] text-fg-2 underline-offset-2 hover:text-fg hover:underline"
            >{S.s_dan_duong_dan_2ae49bc1}</button>
          ) : (
            <>
              <form
                className="mx-auto mt-5 flex max-w-lg gap-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  const path = cleanPath(typed);
                  if (path) onPaths([path]);
                }}
              >
                <input
                  value={typed}
                  onChange={(event) => setTyped(event.target.value)}
                  aria-label={S.s_duong_dan_thu_muc_d8f9678b}
                  aria-invalid={Boolean(problem)}
                  aria-describedby={problem ? "source-problem" : undefined}
                  placeholder={info?.dialogs ? S.s_hoac_dan_duong_dan_bb4837f7 : S.s_dan_duong_dan_thu_muc_hay_file_40ebc3a2}
                  className={cn(
                    "h-10 min-w-0 flex-1 rounded-control border bg-bg px-3 text-sm outline-none placeholder:text-fg-3 focus:border-focus",
                    problem ? "border-danger" : "border-line",
                  )}
                />
                <Button type="submit" className="h-10 min-h-10" disabled={!cleanPath(typed) || scanning}>{S.s_lay_chuong_8869b554}</Button>
              </form>
              {!info?.dialogs && <p className="mx-auto mt-1.5 max-w-lg break-all text-left text-xs text-fg-3">{S.s_vi_du_d_truyen_ten_truyen_d4c4a6e8}</p>}
            </>
          )}
          {problem && (
            <div id="source-problem" role="alert" className="mx-auto mt-3 max-w-lg text-left text-sm text-danger">
              {problem.text}
              {problem.subfolders.length > 0 && (
                <div className="mt-2 space-y-1">
                  <div className="text-fg-2">{S.s_co_le_nen_chon_thu_muc_con_b36394ab}</div>
                  {problem.subfolders.length > 1 && (
                    // Light novel ra từng tập, mỗi tập một thư mục: chọn cả bộ một lần; bước sau ĐỀ XUẤT chia tập, người dùng bấm mới chia.
                    <button
                      type="button"
                      onClick={() => onPaths(problem.subfolders)}
                      className="flex min-h-10 w-full items-center gap-2 py-2 text-left font-medium text-accent-text hover:bg-hover"
                    >
                      <Layers className="size-4 shrink-0 text-accent-text" />
                      <span className="min-w-0">{S.s_chon_345d435d}{problem.subfolders.length}{S.s_tap_269b0b3d}</span>
                    </button>
                  )}
                  {problem.subfolders.slice(0, 8).map((folder) => (
                    <button
                      key={folder}
                      type="button"
                      title={isSourceRef(folder) ? sourceName(folder) : folder}
                      onClick={() => onPaths([folder])}
                      className="flex min-h-10 w-full items-center gap-2 truncate py-2 text-left text-accent-text hover:bg-hover"
                    >
                      <Folder className="size-4 shrink-0 text-fg-2" />
                      {/* Tên thư mục đứng trước: hai thư mục "Tập 1", "Tập 2" cùng một đường dẫn dài thì đuôi bị cắt nhìn y hệt nhau. */}
                      <span className="shrink-0 font-medium">{sourceName(folder)}</span>
                      {/* Tham chiếu của máy tính (Studio từ xa) không phải thứ để đọc: chỉ có tên. */}
                      {!isSourceRef(folder) && <span className="min-w-0 truncate text-xs text-fg-3">{folder}</span>}
                    </button>
                  ))}
                  {problem.subfolders.length > 8 && (
                    <div className="text-fg-2">{S.s_va_6e638075}{problem.subfolders.length - 8}{S.s_thu_muc_nua_deu_nam_trong_dung_ca_o_tren_ea2063d1}</div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <>
          <label className="mt-6 block">
            <span className="text-sm font-medium">{S.s_ten_sach_d54846eb}</span>
            <input
              value={title}
              onChange={(event) => onTitle(event.target.value)}
              aria-invalid={!title.trim()}
              aria-describedby={!title.trim() ? "title-problem" : undefined}
              className={cn(
                "mt-1.5 h-11 w-full rounded-cover border bg-panel px-3.5 text-[0.9375rem] font-medium outline-none focus:border-focus",
                title.trim() ? "border-line" : "border-danger",
              )}
              placeholder={S.s_ten_hien_thi_trong_thu_vien_c48c7ac6}
            />
            {!title.trim() && (
              <span id="title-problem" role="alert" className="mt-1 block text-[0.8125rem] text-danger">{S.s_sach_can_co_ten_de_hien_trong_thu_vien_49495e92}</span>
            )}
          </label>
          {replaces && (
            <div className="mt-4 flex gap-3 py-4 text-sm">
              <Info className="mt-line-icon size-4 shrink-0 text-info" />
              <p className="min-w-0 text-pretty">
                {replaces.restart ? S.s_dang_lam_lai_phan_tich_cua_a4a97a79 : S.s_dang_sua_thiet_lap_cua_e2a5f0e6}
                <span className="font-semibold">“{replaces.title}”</span>{S.s_da_dien_thiet_lap_cu_tao_xong_se_dua_ban_c_1adb5eb8}</p>
            </div>
          )}
          {scan?.existing && scan.existing.some((project) => project.id !== replaces?.id) && (
            <div className="mt-4 flex gap-3 py-4 text-sm">
              <Info className="mt-line-icon size-4 shrink-0 text-info" />
              <div className="min-w-0">
                <p className="font-semibold">{S.s_truyen_nay_da_co_du_an_07223685}</p>
                <ul className="mt-1 space-y-1">
                  {scan.existing.filter((project) => project.id !== replaces?.id).map((project) => (
                    <li key={project.id} className="flex flex-wrap items-baseline gap-x-2">
                      <span className="min-w-0 break-words">
                        “{project.title}” · {project.shared === project.chapters ? S.s_ca_0_chuong_f8291b8f(project.chapters) : S.s_trung_0_1_chuong_25d29e17(project.shared, project.chapters)} · {project.statusLabel}
                      </span>
                      <Link to={`/studio/${project.id}`} className="touch-reach font-medium text-accent-text hover:underline">{S.s_mo_du_an_f990c9d8}</Link>
                    </li>
                  ))}
                </ul>
                <p className="mt-1 text-fg-2">{S.s_van_tao_duoc_du_an_moi_vi_du_de_thu_mot_gi_b8eda300}</p>
              </div>
            </div>
          )}
          {files.filter((file) => file.split).map((file) => (
            <SplitSuggestion key={file.path} file={file} title={title} onSplit={onSplit} />
          ))}
          <MatterSuggestion files={matter.files} keep={matter.keep} onKeep={onKeepMatter} />
          {/* Gợi ý chia phần đứng TRƯỚC lời nhắc số chương: truyện nhiều tập đánh số lại từ 1 ở mỗi tập, lời nhắc "trùng số" chỉ là
              hệ quả của việc chưa chia. */}
          {volumeSplit}
          <ChapterNumberWarning
            issues={
              splitting && volumeStarts
                ? ranges(volumeStarts, files.length).flatMap((part, index) =>
                    chapterNumberIssues(files.slice(part.start - 1, part.end), index === 0 ? previousLast : undefined).map(
                      (issue) => S.s_phan_0_1_07722a78(index + 1, issue),
                    ),
                  )
                : chapterNumberIssues(files, previousLast)
            }
            suggestsSplit={!splitting && Boolean(scan?.volumes)}
          />
          <CreditSuggestion files={files} drop={dropCredits} onChange={onDropCredits} />
          <div className="mt-5 flex flex-wrap items-center justify-between gap-2">
            <div className="text-sm text-fg-2">
              <span className="font-semibold text-fg">{files.length}{S.s_chuong_9e6a01dc}</span> · {approx(scan!.totals.words, scan!.totals.estimated)}{S.s_chu_khoang_7a1a54c6}{" "}
              {formatLength(scan!.totals.audioSeconds)}{S.s_audio_7024c69b}</div>
            <div className="flex gap-1">
              {info?.dialogs && (
                <Button size="sm" variant="ghost" icon={FileText} onClick={() => void chooseFiles(true)}>{S.s_them_file_834b1f33}</Button>
              )}
              {browser && (
                <Button size="sm" variant="ghost" icon={Upload} loading={Boolean(uploading)} onClick={() => browse(filesInput.current, true)}>
                  {uploading ? progressLabel(uploading) : S.s_them_file_834b1f33}
                </Button>
              )}
              {browser && uploading && (
                <Button size="sm" variant="ghost" disabled={stopping} onClick={cancelUpload}>
                  {stopping ? S.s_dang_dung_9b35aeb5 : S.s_huy_gui_4d53a582}
                </Button>
              )}
              <Button size="sm" variant="ghost" onClick={() => onPaths([])}>{S.s_chon_lai_834274af}</Button>
            </div>
          </div>
          {/* Truyện dài (còn ra tiếp, hay làm từng đợt bằng "Làm tiếp cuốn này"): bỏ từng chương một thì không xuể - chọn
              nhanh làm N chương đầu, phần còn lại để đợt sau. */}
          {total > CHAPTER_LIMITS[0] && !splitting && (
            <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-fg-2">
              <span>{S.s_dot_nay_lam_34f9f26c}</span>
              <ChoiceRow<string>
                label={S.s_dot_nay_lam_bao_nhieu_chuong_fb0c6a1b}
                wrap
                value={limit ? String(limit) : "all"}
                onChange={(value) => onLimit(value === "all" ? null : Number(value))}
                options={[
                  ...CHAPTER_LIMITS.filter((count) => count < total).map((count) => ({ value: String(count), label: S.s_0_chuong_dau_1edc0ecb(count) })),
                  { value: "all", label: S.s_ca_0_chuong_65f6a487(formatNumber(total)) },
                ]}
              />
              {limit !== null && later > 0 && <span>{S.s_con_b3181893}{formatNumber(later)}{S.s_chuong_cho_dot_sau_50fbbbf5}</span>}
            </div>
          )}
          {/* Danh sách thật cho trình đọc màn hình ("danh sách 12 mục", soát a31 A4); vạch "Phần N" chỉ để nhìn - lời của nó đọc ở đầu mục. */}
          <Fold storageKey="new-project.chapters" title={S.s_danh_sach_chuong_7fa755f9} summary={S.s_0_chuong_04093412(files.length)} defaultOpen={files.length <= 4} className="mt-3" heading="h3">
          <div className="overflow-hidden">
          {/* data-motion-live: vùng cả bước không mờ lại khi bỏ / thêm chương - hàng tự khép / mở tại chỗ (useListPresence), thanh cuộn đứng yên. */}
          <div ref={setChapterList} style={chapterFade} role="list" aria-label={S.s_cac_chuong_se_lam_5a07f064} data-motion-live="" className="max-h-[340px] overflow-y-auto overscroll-contain">
            <ChapterRows files={files}>
            {({ key, item: file, state, ref }) => {
              const index = files.findIndex((item) => item.path === key);
              // Chia phần: một vạch "Phần N bắt đầu" trước chương đầu mỗi phần - khỏi phải đối số chương với ô "từ chương" ở trên.
              const part = splitting && volumeStarts && volumeStarts.length > 1 && index >= 0 ? volumeStarts.indexOf(index + 1) : -1;
              return (
                <div key={key} ref={ref} role="listitem" className="motion-row border-b border-line last:border-b-0" data-state={state} inert={state === "exit"}>
                  <div>
                  <MotionPresence open={part >= 0}>
                    <div aria-hidden className="flex items-center gap-2 border-b border-accent/30 px-3 py-1.5 text-xs font-semibold text-accent-text">
                      <Layers className="size-3.5 shrink-0" />
                      <span className="min-w-0 truncate">{S.s_phan_a17569d5}{part + 1}{S.s_bat_dau_76545e3c}</span>
                    </div>
                  </MotionPresence>
                  <div
                    className="group grid grid-cols-[auto_minmax(0,1fr)_90px_36px] items-center gap-2 px-3 py-2 [contain-intrinsic-size:auto_48px] [content-visibility:auto]"
                  >
                    <span className="tabular-cell text-right text-xs text-fg-2" style={{ width: `${String(files.length).length}ch` }}>
                      {part >= 0 && <span className="sr-only">{S.s_phan_a17569d5}{part + 1}{S.s_bat_dau_85cad92e}</span>}
                      {index >= 0 ? index + 1 : ""}
                    </span>
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">{file.firstLine || file.title}</div>
                      <div className="truncate text-xs text-fg-2">{file.name}</div>
                    </div>
                    <div className="tabular-cell text-right text-xs text-fg-2">
                      <div>{approx(file.words, file.estimated)}{S.s_chu_6117d040}</div>
                      {file.chars > 0 && <div className="text-fg-3">{approx(file.chars, file.estimated)}{S.s_ky_tu_c7cc4ddf}</div>}
                    </div>
                    <button
                      type="button"
                      aria-label={S.s_bo_chuong_0_bc591be5(file.name)}
                      title={S.s_bo_chuong_nay_dfcadfcd}
                      onClick={() => onRemove(file.path)}
                      className="touch-hit grid size-8 place-items-center rounded-control text-fg-2 opacity-0 transition-[opacity,color,background-color] duration-motion-fast hover:bg-hover hover:text-danger group-hover:opacity-100 focus-visible:opacity-100 max-md:opacity-100"
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </div>
                  </div>
                </div>
              );
            }}
            </ChapterRows>
          </div>
          </div>
          </Fold>
          {scan!.skipped.length > 0 && <p className="mt-2 text-xs text-fg-2">{S.s_bo_qua_0e8d852d}{scan!.skipped.length}{S.s_file_khong_phai_txt_674f8d1a}</p>}
          {/* File sách hỏng / PDF scan nằm cạnh file tốt, thư mục có cả TXT lẫn EPUB, trang chỉ có ảnh bị bỏ, gợi ý dòng ghi công: không chặn, nhưng nói ra (soát UX 01-10: bị bỏ âm thầm). */}
          {[...(scan!.errors ?? []).map((error) => S.s_bo_qua_0_a2975d42(error)), ...(scan!.notes ?? [])].map((line) => (
            <p key={line} className="mt-2 text-xs text-warning">
              {line}
            </p>
          ))}
        </>
      )}
    </MotionRegion>
  );
}

/** Hàng chương ở bước Nguồn: bỏ chương / "N chương đầu" / Hoàn tác khép / mở hàng tại chỗ (DESIGN 5.2). */
function ChapterRows({ files, children }: { files: ScannedFile[]; children: (row: PresentRow<ScannedFile> & { ref?: (element: HTMLElement | null) => void }) => ReactNode }) {
  const rows = useListPresence(files, (file) => file.path);
  return <>{rows.map(children)}</>;
}

/** "Chương 768" từ dòng đầu file ("Chương 768 - Mô hình…"), không thì tên file - cho dải chương ở bước xác nhận. */
function chapterLabel(file: ScannedFile): string {
  const head = file.firstLine.split(/\s[-–—:]\s|[:：]/)[0].trim();
  return head && head.length <= 40 ? head : file.name;
}

// ---- Nối tiếp phần trước ---------------------------------------------------------------------------------------

function carriedText(carries: Seed["carries"]): string {
  const parts = [
    carries.voices ? S.s_giong_0_nhan_vat_acc51e04(formatNumber(carries.voices)) : "",
    carries.pronunciations ? S.s_0_cach_doc_ten_740fd23f(formatNumber(carries.pronunciations)) : "",
    carries.pins ? S.s_gioi_tuoi_da_sua_tay_cua_0_nhan_vat_f4f6e10d(formatNumber(carries.pins)) : "",
    carries.aliases ? S.s_0_bi_danh_a35a01a7(formatNumber(carries.aliases)) : "",
    carries.names ? S.s_0_ten_nhan_vat_da_doi_3aa798e4(formatNumber(carries.names)) : "",
    carries.bracket ? S.s_quy_uoc_loi_trong_b4f1c558 : "",
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : S.s_nhung_gi_phan_truoc_da_co_84eb2fe7;
}

// Phát hiện được thì ĐỀ XUẤT, không tự làm (chủ sách 29-09: app không bao giờ tự sửa nội dung truyện). Dòng ghi công người
// dịch ở đầu chương ("TL : NicK", "*Edit: Lắc") bị đọc như một câu kể; chỉ khi bấm "Bỏ khỏi phần đọc" sách mới bỏ chúng,
// không bấm thì sách giữ nguyên như file truyện. Phải chọn lúc tạo sách: đổi cách tách câu sau khi đã làm là đổi cả quyển.
// Dòng xin ủng hộ / quảng cáo ở cuối chương (soát UX a23) nằm chung một gợi ý, ghi "(cuối chương)" (studio/credits).
function CreditSuggestion({ files, drop, onChange }: { files: ScannedFile[]; drop: CreditDrop; onChange: (value: CreditDrop) => void }) {
  // Soát UX a24, A9: xem hết mọi dòng (theo chương) trước khi bỏ, và bỏ riêng dòng đầu chương / cuối chương - hai cài đặt riêng của sách.
  const [all, setAll] = useState(false);
  const [list, setList] = useState<HTMLUListElement | null>(null);
  const fade = useScrollFadeOn(list);
  const credits = creditSummary(files);
  if (!credits.lines) return <MotionRegion />;
  const quoted = credits.examples.join(", ");
  const dropped = droppedLines(credits, drop);
  const both = credits.head > 0 && credits.tail > 0;
  return (
    <MotionRegion as="div" className="mt-4 flex gap-3 py-4 text-sm">
      <Sparkles className="mt-line-icon size-4 shrink-0 text-accent-text" />
      <div className="min-w-0 flex-1">
        {dropped ? (
          <>
            <p className="font-semibold">{S.s_se_bo_976be2fb}{formatNumber(dropped)} {creditKind({ ...credits, head: drop.head ? credits.head : 0, tail: drop.tail ? credits.tail : 0 })}{S.s_khoi_phan_doc_a9d1c125}</p>
            <p className="mt-1 break-words text-fg-2">{S.s_chi_bo_khoi_phan_doc_giu_nguyen_file_truye_94c7dd67}</p>
          </>
        ) : (
          <>
            <p className="font-semibold">{S.s_goi_y_dddb8282}{formatNumber(credits.chapters)}{S.s_chuong_co_51021419}{creditWhere(credits)}
            </p>
            <p className="mt-1 break-words text-fg-2">
              {quoted}
              {credits.lines > credits.examples.length ? "…" : ""}{S.s_chon_bo_neu_khong_muon_doc_5abe810e}</p>
          </>
        )}
        {all && (
          <div className="mt-2 overflow-hidden">
          <ul ref={setList} style={fade} className="max-h-64 space-y-1 overflow-y-auto overscroll-contain p-2 text-xs text-fg-2" aria-label={S.s_moi_dong_goi_y_theo_chuong_af83ec00}>
            {creditRows(files, chapterLabel).map((row, index) => (
              <li key={`${index}-${row.chapter}`} className="break-words">
                <span className="font-medium text-fg">{row.chapter}:</span>{" "}
                {[...row.head.map((line) => creditLine(line, "head", drop)), ...row.tail.map((line) => creditLine(line, "tail", drop))].map((line, at) => (
                  <span key={at}>
                    {at > 0 && " · "}
                    <span className={line.dropped ? "text-fg-3 line-through" : undefined}>{line.text}</span>
                  </span>
                ))}
              </li>
            ))}
          </ul>
          </div>
        )}
        <div className="mt-2.5 flex flex-wrap gap-2">
          {both ? (
            <>
              <Button size="sm" variant="ghost" aria-pressed={drop.head} onClick={() => onChange({ ...drop, head: !drop.head })}>
                {drop.head ? S.s_giu_dong_dau_d250460c : S.s_bo_0_dong_f647322c(formatNumber(credits.head))}
              </Button>
              <Button size="sm" variant="ghost" aria-pressed={drop.tail} onClick={() => onChange({ ...drop, tail: !drop.tail })}>
                {drop.tail ? S.s_giu_dong_cuoi_d9387556 : S.s_bo_0_dong_f647322c(formatNumber(credits.tail))}
              </Button>
            </>
          ) : dropped ? (
            <Button size="sm" variant="ghost" onClick={() => onChange(KEEP_CREDITS)}>{S.s_giu_nguyen_chu_02c81916}</Button>
          ) : (
            <Button size="sm" variant="ghost" onClick={() => onChange({ head: credits.head > 0, tail: credits.tail > 0 })}>{S.s_bo_khoi_phan_doc_6726e734}</Button>
          )}
          <Button size="sm" variant="ghost" aria-expanded={all} onClick={() => setAll((value) => !value)}>
            {all ? S.s_thu_gon_1f6bf2c3 : S.s_xem_het_0_dong_064e8d87(formatNumber(credits.lines))}
          </Button>
        </div>
      </div>
    </MotionRegion>
  );
}

// Soát UX a5 01-10: truyện tải trên mạng phần lớn là MỘT file TXT - trình tạo sách đọc ra một chương dài vài tiếng, không
// một lời nhắc. Thấy nhiều dòng "Chương N" trong một file thì ĐỀ XUẤT tách; không bấm thì giữ nguyên như file (chủ sách
// 29-09: không bao giờ tự sửa nguồn). Tách là ghi các chương ra một thư mục mới trong thư viện - file gốc không đổi.
function ChapterNumberWarning({ issues, suggestsSplit }: { issues: string[]; suggestsSplit?: boolean }) {
  if (!issues.length) return null;
  return (
    <div className="mt-4 flex gap-3 py-4 text-sm">
      <AlertTriangle className="mt-line-icon size-4 shrink-0 text-warning" />
      <div className="min-w-0">
        <p className="font-semibold">{S.s_so_chuong_co_cho_la_xem_lai_truoc_khi_tao_cbf84a1f}</p>
        <ul className="mt-1 list-disc space-y-0.5 pl-4 text-fg-2">
          {issues.map((issue) => (
            <li key={issue} className="break-words">{issue}</li>
          ))}
        </ul>
        <p className="mt-1 text-fg-2">
          {suggestsSplit
            ? S.s_nhieu_tap_danh_so_lai_tu_1_chia_thanh_nhie_50bbb0ff
            : ""}{S.s_van_tao_duoc_nhu_the_may_chi_nhac_khong_bo_08ad11a0}</p>
      </div>
    </div>
  );
}

function SplitSuggestion({ file, title, onSplit }: { file: ScannedFile; title: string; onSplit: (path: string) => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const plan = file.split!;
  const quoted = plan.titles.map((title) => `“${title}”`).join(", ");
  // Chữ dẫn chỉ là một dòng tên truyện: trùng Tên sách thì nó là tên sách (không thành chương "Mở đầu" 4 chữ); khác thì chữ vẫn ở lại.
  const outcome = splitOutcome(plan, title);
  return (
    <div className="mt-4 flex gap-3 py-4 text-sm">
      <Sparkles className="mt-line-icon size-4 shrink-0 text-accent-text" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{S.s_goi_y_80f3b4ba}{file.name}{S.s_co_ve_chua_ca_f34d3ea9}{formatNumber(outcome.chapters)}{S.s_chuong_9e6a01dc}</p>
        <p className="mt-1 break-words text-fg-2">{S.s_tach_theo_5f3e6530}{quoted}{plan.chapters > plan.titles.length ? "…" : ""}{S.s_giu_file_goc_4cf6140f}{plan.preamble ? S.s_va_chu_mo_dau_a047c58f : ""}.
        </p>
        <div className="mt-2.5">
          <Button
            size="sm"
            variant="ghost"
            icon={busy ? Loader2 : Scissors}
            disabled={busy}
            onClick={() => {
              setBusy(true);
              void onSplit(file.path).finally(() => setBusy(false));
            }}
          >{S.s_tach_thanh_a08e8a2c}{formatNumber(outcome.chapters)}{S.s_chuong_9e6a01dc}</Button>
        </div>
      </div>
    </div>
  );
}

function SeedBanner({ seed, hasFiles, onDrop }: { seed: Seed; hasFiles: boolean; onDrop: () => void }) {
  return (
    // Điện thoại: nút bỏ nối tiếp xuống dưới đoạn chữ - đứng bên phải thì ép chữ thành cột ~180 px, dài 11 dòng (soát UX 29-09).
    <MotionRegion as="div" className="mt-5 flex flex-wrap gap-3 py-4 text-sm sm:flex-nowrap">
      <Layers className="mt-line-icon size-4 shrink-0 text-accent-text" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{S.s_phan_a17569d5}{seed.part}{S.s_cua_285bec9f}{seed.title}”
        </p>
        {seed.clickedTitle && (
          <p className="mt-0.5 text-fg-2">{S.s_noi_sau_26bf063a}{seed.latestTitle ?? seed.title}{S.s_giu_c0878737}{carriedText(seed.carries)}.
          </p>
        )}
        {!seed.clickedTitle && <p className="mt-0.5 text-fg-2">{S.s_giu_d3777f80}{carriedText(seed.carries)}{S.s_giong_va_cach_doc_ten_995cc280}</p>}
        {/* Khung "chưa có chương mới" tắt ngay khi đã chọn / thêm được file (soát UX a6 01-10, B5: vẫn hiện sau khi đã có). */}
        {seed.empty && !hasFiles && (
          <p className="mt-1 text-fg-2">
            {seed.folder ? (
              <>{S.s_chon_file_moi_sau_5b6856da}{seed.lastChapter || S.s_chuong_cuoi_phan_truoc_7e3d0c5b}{S.s_o_duoi_a9e009c8}</>
            ) : (
              S.s_chon_file_chuong_moi_o_duoi_0af6839c
            )}
          </p>
        )}
        {seed.analysisModelMissing && (
          <p className="mt-1 text-warning">{S.s_thieu_bo_phan_tich_cua_phan_truoc_doi_bo_c_9b47e7fe}</p>
        )}
        {!seed.analyzed && (
          <p className="mt-1 text-warning">{S.s_phan_truoc_chua_phan_tich_xong_chi_mang_du_6719c096}</p>
        )}
      </div>
      <button
        type="button"
        onClick={onDrop}
        className="self-start whitespace-nowrap text-[0.8125rem] text-fg-2 underline-offset-2 hover:text-fg hover:underline max-sm:basis-full max-sm:pl-7 max-sm:text-left"
      >{S.s_bo_noi_tiep_2b7945ba}</button>
    </MotionRegion>
  );
}

// ---- Giọng -----------------------------------------------------------------------------------------------------

export function VoiceCard({
  voice,
  selected,
  focusable,
  onSelect,
}: {
  voice: Voice;
  selected: boolean;
  focusable: boolean;
  onSelect: () => void;
}) {
  const clip = useClip();
  const source = useSource();
  const id = `voice-${voice.name}`;
  const playing = clip.current === id;
  return (
    <div
      className={cn(
        "relative flex items-center gap-3 border-b border-line py-3.5 transition-colors",
        selected ? "text-accent-text" : "text-fg",
      )}
    >
      <button
        type="button"
        tabIndex={-1}
        aria-label={playing ? S.s_dung_nghe_0_11a2fef9(voice.name) : S.s_nghe_thu_giong_0_d16e376e(voice.name)}
        onClick={() => clip.toggle(id, source.voiceUrl(voice.name))}
        // Trên lớp phủ bấm-để-chọn của thẻ (after:inset-0): nghe thử không đổi giọng đang chọn (soát UX a5 01-10).
        className={cn(
          "relative z-10 grid size-10 shrink-0 place-items-center rounded-full transition-colors",
          playing ? "text-accent-text" : "text-fg-2 hover:bg-hover",
        )}
      >
        <MotionRegion as="span" className="grid size-4 place-items-center">{playing ? <Vu className="h-3" /> : <Play className="size-4 translate-x-[1px]" fill="currentColor" strokeWidth={0} />}</MotionRegion>
      </button>
      <button
        type="button"
        role="radio"
        aria-checked={selected}
        tabIndex={focusable ? 0 : -1}
        data-voice={voice.name}
        onClick={onSelect}
        className="min-w-0 flex-1 text-left outline-none after:absolute after:inset-0 after:rounded-cover focus-visible:after:outline-2 focus-visible:after:outline-offset-2 focus-visible:after:outline-focus"
      >
        <span className="block font-semibold leading-snug">{voice.name}</span>
        <span className="mt-0.5 block text-xs text-fg-2">
          {voice.gender}{S.s_mien_8dcd7dbe}{voice.region} · {voice.style}
        </span>
        {voice.recommended && (
          <span className="mt-1.5 inline-block rounded-control bg-accent-soft px-1.5 py-px text-[0.6875rem] font-semibold uppercase tracking-wide text-accent-text">{S.s_de_xuat_3a11f911}</span>
        )}
      </button>
      <MotionRegion as="span" className="grid size-6 shrink-0 place-items-center" aria-hidden>
        {selected ? <span className="grid size-6 place-items-center text-accent-text"><Check className="size-3.5" strokeWidth={3} /></span> : <span />}
      </MotionRegion>
    </div>
  );
}

/**
 * "'Tôi' là ai?" - truyện kể ngôi thứ nhất không bao giờ gọi tên người kể trong lời kể, nên máy không biết câu thoại
 * của nhân vật chính là của ai: đo 27-09, model gán 22 câu của người kể cho chính người đang nói chuyện với anh ta và
 * chỉ đúng 34% người nói; biết tên người kể thì 89%. Máy đoán được TRUYỆN NÀO kể ngôi thứ nhất, còn tên chỉ gợi ý.
 */
/** Chương đổi góc kể được giữ: gợi ý của máy, trừ chương mà tên ấy chính là người kể cả cuốn và chương người dùng bỏ chọn. */
function chosenPovChapters(hint: FirstPersonHint | undefined, narrator: string, off: number[]): Record<string, string> {
  const book = narrator.trim().toUpperCase();
  return Object.fromEntries(
    (hint?.chapters ?? [])
      .filter((chapter) => chapter.name !== book && !off.includes(chapter.chapter))
      .map((chapter) => [String(chapter.chapter), chapter.name]),
  );
}

/**
 * Light novel hay có chương đổi góc kể ("Chương 11: Yuuko Hayase" kể bằng "tôi" của Hayase trong cuốn Kakeru kể): máy
 * gợi ý khi tên chương là một nhân vật chính và chương kể bằng "tôi" (first_person.pov_chapters). Giữ chọn thì chương
 * ấy phân tích với đúng người kể của nó (`voices.first_person_chapters`).
 */
function PovChapters({ hint, narrator, off, onOffChange }: {
  hint: FirstPersonHint | undefined;
  narrator: string;
  off: number[];
  onOffChange: (off: number[]) => void;
}) {
  const book = narrator.trim().toUpperCase();
  const chapters = (hint?.chapters ?? []).filter((chapter) => chapter.name !== book);
  if (!chapters.length) return null;
  return (
    <fieldset className="mt-4 border-t border-line pt-3">
      <legend className="sr-only">{S.s_chuong_doi_nguoi_ke_88865076}</legend>
      <p className="text-sm font-semibold">{S.s_chuong_doi_nguoi_ke_88865076}</p>
      <p className="mt-0.5 text-sm text-fg-2 text-pretty">{S.s_ke_bang_toi_bo_chon_neu_may_doan_sai_306c44c1}</p>
      <ul className="mt-2 space-y-1.5">
        {chapters.map((chapter) => {
          const on = !off.includes(chapter.chapter);
          return (
            <li key={chapter.chapter}>
              <label className="flex items-start gap-2.5 text-sm">
                <input
                  id={`pov-chapter-${chapter.chapter}`}
                  type="checkbox"
                  checked={on}
                  onChange={() => onOffChange(on ? [...off, chapter.chapter] : off.filter((value) => value !== chapter.chapter))}
                  className="mt-0.5 size-4 accent-[var(--accent)]"
                />
                <span>
                  {chapter.title}{S.s_toi_la_90e4c35d}<b>{chapter.name}</b>
                </span>
              </label>
            </li>
          );
        })}
      </ul>
    </fieldset>
  );
}

function FirstPersonQuestion({ paths, seedFrom, value, onChange, gender, onGender, tellerMode, onTellerMode, povOff, setPovOff }: {
  paths: string[];
  seedFrom?: string;
  value: string;
  onChange: (name: string) => void;
  gender?: TellerGender;
  onGender: (gender: TellerGender | undefined) => void;
  tellerMode?: boolean;
  onTellerMode: (on: boolean) => void;
  povOff: number[];
  setPovOff: (off: number[]) => void;
}) {
  const { data: hint, isLoading } = useFirstPersonHint(paths, seedFrom);
  const [opened, setOpened] = useState(false);
  if (!hint?.firstPerson && !value && !opened && !hint?.chapters?.length) {
    return (
      <MotionRegion as="button"
        type="button"
        onClick={() => setOpened(true)}
        className="mt-3 text-sm font-medium text-accent-text underline underline-offset-2 disabled:opacity-60"
        disabled={isLoading}
      >{S.s_ke_bang_toi_521f80f7}</MotionRegion>
    );
  }
  return (
    <MotionRegion as="section" aria-labelledby="first-person-title" className="mt-5 max-w-2xl py-4 sm:py-5">
      <h3 id="first-person-title" className="font-semibold">{S.s_toi_la_ai_efbf5a65}</h3>
      <p className="mt-1 text-sm text-fg-2 text-pretty">{S.s_ten_nguoi_ke_giup_phan_vai_dung_loi_thoai_ded89111}</p>
      <MoreInfo label={S.s_may_doan_0f0472f0}>{hint?.firstPerson
        ? hint.chaptersSampled && hint.chaptersWithI
          ? S.s_0_1_chuong_dau_co_loi_ke_xung_toi_6b41741b(hint.chaptersWithI, hint.chaptersSampled)
          : S.s_0_doan_loi_ke_co_toi_b16efe53(Math.round(hint.rate * 100))
        : S.s_chon_nhan_vat_xung_toi_trong_loi_ke_d47a6c20}{S.s_ban_co_the_sua_goi_y_nay_ffd074da}</MoreInfo>
      {Boolean(hint?.suggestions.length) && (
        <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label={S.s_goi_y_ten_nguoi_ke_7b50873d}>
          {hint!.suggestions.map((name) => (
            <button
              key={name}
              type="button"
              aria-pressed={value === name}
              onClick={() => onChange(value === name ? "" : name)}
              className={cn(
                "rounded-control px-3 py-1.5 text-sm font-medium transition-colors duration-motion-medium",
                value === name ? "text-accent-text underline underline-offset-4" : "text-fg-2 hover:bg-hover",
              )}
            >
              {name}
            </button>
          ))}
        </div>
      )}
      <label className="mt-3 block text-sm text-fg-2">{S.s_ten_nguoi_ke_d492ccfb}<input
          id="first-person-name"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={S.s_ten_nhan_vat_xung_toi_de_trong_neu_ke_ngoi_67659017}
          className="mt-1.5 h-11 w-full rounded-cover border border-line bg-panel px-3.5 text-[0.9375rem] font-medium text-fg outline-none focus:border-focus focus-visible:ring-2 focus-visible:ring-focus"
        />
      </label>
      {value.trim() && (
        <div className="mt-3">
          <ChoiceRow
            label={S.s_nguoi_ke_la_379f9c45}
            value={gender ?? "unknown"}
            onChange={(next) => onGender(next === "male" || next === "female" ? next : undefined)}
            options={[
              { value: "unknown", label: S.s_chua_ro_be464a5a },
              { value: "male", label: S.s_nam_22dd59c8 },
              { value: "female", label: S.s_nu_e15bc11c },
            ]}
          />
          <p className="mt-1.5 text-[0.8125rem] text-fg-2 text-pretty">{S.s_chua_ro_thi_may_doan_loi_dan_dung_giong_cu_243f284d}</p>
          <label className="mt-3 flex items-start gap-3 py-4" htmlFor="teller-mode">
            <Switch id="teller-mode" labelledBy="teller-mode-name" describedBy="teller-mode-hint" checked={Boolean(tellerMode)} onCheckedChange={onTellerMode} />
            <span>
              <span id="teller-mode-name" className="block text-sm font-medium">{TELLER_TITLE}</span>
              <span id="teller-mode-hint" className="mt-0.5 block text-[0.8125rem] leading-relaxed text-fg-2">{tellerHint(Boolean(tellerMode))}</span>
            </span>
          </label>
        </div>
      )}
      <PovChapters hint={hint} narrator={value} off={povOff} onOffChange={setPovOff} />
    </MotionRegion>
  );
}

export function VoiceStep({
  narrator,
  setNarrator,
  paths,
  seedFrom,
  previousNarrator,
  firstPerson,
  setFirstPerson,
  firstPersonGender,
  setFirstPersonGender,
  tellerMode,
  setTellerMode,
  narratorAuto,
  povOff,
  setPovOff,
}: {
  narrator: string;
  setNarrator: (name: string) => void;
  paths: string[];
  seedFrom?: string;
  previousNarrator?: string;
  firstPerson: string;
  setFirstPerson: (name: string) => void;
  firstPersonGender?: TellerGender;
  setFirstPersonGender: (gender: TellerGender | undefined) => void;
  tellerMode?: boolean;
  setTellerMode: (on: boolean) => void;
  /** Giọng kể đang do máy chọn (người dùng chưa bấm giọng nào): đổi theo giới người kể "tôi". */
  narratorAuto: boolean;
  povOff: number[];
  setPovOff: (off: number[]) => void;
}) {
  const { data: voices } = useVoices();
  const [gender, setGender] = useState("all");
  const [region, setRegion] = useState("all");
  const group = useRef<HTMLDivElement | null>(null);
  // Làm tiếp một cuốn: giọng kể của phần trước đứng ĐẦU lưới - trước đây nó là thẻ thứ 21, dưới hai giọng "Đề xuất", dễ
  // đổi nhầm giọng kể giữa bộ (soát UX 29-09).
  const shown = (voices ?? [])
    .filter((voice) => (gender === "all" || voice.gender === gender) && (region === "all" || voice.region === region))
    .sort((a, b) => Number(b.name === previousNarrator) - Number(a.name === previousNarrator));
  const hiddenSelection = Boolean(narrator) && !shown.some((voice) => voice.name === narrator);
  const focusName = shown.some((voice) => voice.name === narrator) ? narrator : shown[0]?.name;
  // Một điểm dừng Tab cho cả nhóm; mũi tên chuyển giọng (chuẩn radiogroup).
  const onKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const keys: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
    const step = keys[event.key];
    if (!step || !shown.length) return;
    event.preventDefault();
    const index = shown.findIndex((voice) => voice.name === focusName);
    const next = shown[(index + step + shown.length) % shown.length];
    setNarrator(next.name);
    window.requestAnimationFrame(() => group.current?.querySelector<HTMLElement>(`[data-voice="${CSS.escape(next.name)}"]`)?.focus());
  };
  return (
    <MotionRegion as="div">
      <SectionHeading>{S.s_giong_ke_b209f686}</SectionHeading>
      <p className="mt-1 max-w-2xl text-sm text-fg-2 text-pretty">{S.s_giong_doc_loi_dan_nhan_vat_duoc_trao_giong_6dd30d7a}</p>
      <FirstPersonQuestion
        paths={paths}
        seedFrom={seedFrom}
        value={firstPerson}
        onChange={setFirstPerson}
        gender={firstPersonGender}
        onGender={setFirstPersonGender}
        tellerMode={tellerMode}
        onTellerMode={setTellerMode}
        povOff={povOff}
        setPovOff={setPovOff}
      />
      {narratorAuto && (
        <p className="mt-4 max-w-2xl text-sm text-fg-2 text-pretty">{S.s_may_chon_cung_gioi_nguoi_ke_chon_giong_de_48aef3e1}</p>
      )}
      {previousNarrator && (
        <p className="mt-4 text-sm text-fg-2">{S.s_giong_ke_phan_truoc_9750613e}<span className="font-semibold text-fg">{previousNarrator}</span>
          {narrator && narrator !== previousNarrator && (
            <>
              {S.s_dang_chon_giong_khac_hai_phan_se_doc_loi_d_bd6d927d}
              <button type="button" className="font-medium text-accent-text underline underline-offset-2" onClick={() => setNarrator(previousNarrator)}>{S.s_dung_lai_267968d0}{previousNarrator}
              </button>
            </>
          )}
        </p>
      )}
      <Fold storageKey="new-project.voices" title={S.s_doi_giong_94b6b371} summary={narrator || S.s_chon_mot_giong_749f92a2} defaultOpen={!narrator} className="mt-4" heading="h3">
      <div className="flex flex-wrap items-center gap-3">
        <ChoiceRow label={S.s_gioi_tinh_46eb9a2c} value={gender} onChange={setGender} options={[
          { value: "all", label: S.s_moi_giong_b0243b7c },
          { value: S.s_nam_22dd59c8, label: S.s_giong_nam_4ab78f43 },
          { value: S.s_nu_e15bc11c, label: S.s_giong_nu_cd860480 },
        ]} />
        <ChoiceRow label={S.s_mien_498584a9} value={region} onChange={setRegion} options={[
          { value: "all", label: S.s_moi_mien_58ed42fb },
          { value: S.s_bac_b8cc98f1, label: S.s_mien_bac_67b1bf3b },
          { value: S.s_nam_22dd59c8, label: S.s_mien_nam_81505299 },
          { value: S.s_trung_83080cf9, label: S.s_mien_trung_f313e576 },
        ]} />
      </div>
      {hiddenSelection && (
        <p className="mt-3 text-sm text-fg-2">{S.s_dang_chon_7789a2de}<span className="font-semibold text-fg">{narrator}</span>{S.s_bo_loc_dang_an_giong_nay_90f64c87}{" "}
          <button type="button" className="font-medium text-accent-text underline underline-offset-2" onClick={() => { setGender("all"); setRegion("all"); }}>{S.s_bo_loc_74de0064}</button>
        </p>
      )}
      <div ref={group} role="radiogroup" aria-label={S.s_giong_ke_chuyen_4a4e32b1} onKeyDown={onKeyDown} className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 2xl:grid-cols-3">
        {shown.map((voice) => (
          <VoiceCard
            key={voice.name}
            voice={voice}
            selected={voice.name === narrator}
            focusable={voice.name === focusName}
            onSelect={() => setNarrator(voice.name)}
          />
        ))}
      </div>
      </Fold>
    </MotionRegion>
  );
}

// ---- Chất lượng -----------------------------------------------------------------------------------------------

export function QualityStep({
  profile,
  setProfile,
  words,
  chapters,
  analysisModel,
  setAnalysisModel,
  noStudio,
}: {
  profile: Profile;
  setProfile: (profile: Profile) => void;
  words: number;
  chapters: number;
  analysisModel: string;
  setAnalysisModel: (model: string) => void;
  /** Máy chưa có Studio: số đo thời gian không nói gì về máy này - không hiện. */
  noStudio?: boolean;
}) {
  // Số đo là của MỘT máy: máy khác / model phân tích khác chỉ được khoảng rộng, có nhãn tham khảo (timeEstimate.ts).
  const exact = matchesMeasured(useStudioGpu(), analysisModel);
  const guess = estimate(words, chapters, exact);
  const chosen = PROFILES.find((option) => option.value === profile)!;
  return (
    <div>
      <SectionHeading>{S.s_chat_luong_a12ed26c}</SectionHeading>
      <p className="mt-1 text-sm text-fg-2 text-pretty">{S.s_co_dinh_sau_khi_tao_de_moi_chuong_doc_gion_165eeae2}</p>
      <div
        role="radiogroup"
        aria-label={S.s_chat_luong_a12ed26c}
        onKeyDown={radioGroupKeys(PROFILE_VALUES, profile, setProfile)}
        className="mt-6 grid divide-y divide-line"
      >
        {PROFILES.map((option, index) => {
          const selected = option.value === profile;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={selected}
              tabIndex={radioTabIndex(PROFILE_VALUES, profile, index)}
              onClick={() => setProfile(option.value)}
              className={cn(
                "relative flex flex-col border-b border-line py-4 text-left transition-colors",
                selected ? "text-accent-text" : "text-fg",
              )}
            >
              {option.value === "high_quality" && (
                <span className="mb-2 inline-flex items-center gap-1 text-xs font-medium text-fg-2">
                  <Sparkles className="size-3" />{S.s_nen_dung_6d30e4cd}</span>
              )}
              <div className="flex items-center justify-between">
                <span className="text-base font-semibold">{option.title}</span>
                <MotionRegion as="span" className="grid size-6 place-items-center" aria-hidden>{selected ? <span className="grid size-6 place-items-center text-accent-text"><Check className="size-3.5" strokeWidth={3} /></span> : <span />}</MotionRegion>
              </div>
              <div className="mt-1 flex items-center gap-1.5 text-xs font-medium text-fg-2">
                <Gauge className="size-3.5" /> {option.pace}
              </div>
              <p className="mt-3 text-sm text-fg-2">{option.summary}</p>
            </button>
          );
        })}
      </div>
      <Fold storageKey="new-project.quality" title={S.s_chi_tiet_e762d926} summary={chosen.title} className="mt-4" heading="h3">
        <MotionRegion>
          <ul className="space-y-2 text-sm">{chosen.points.map((point) => <li key={point} className="flex gap-2"><Check className="mt-0.5 size-3.5 shrink-0 text-success" aria-hidden /><span>{point}</span></li>)}</ul>
          <p className="mt-3 text-sm text-fg-2">{noStudio ? S.s_cai_studio_de_uoc_tinh_thoi_gian_0ac5ef9b : profile === "high_quality" ? <>{S.s_tham_khao_e9bde754}{lengthRange(guess.totalLow, guess.totalHigh)}{S.s_cho_0f86da9d}{chapters}{S.s_chuong_2721c3eb}{timeBasis(exact)}.</> : S.s_nhanh_hon_chat_luong_cao_chua_co_so_do_d80ead73}</p>
        </MotionRegion>
      </Fold>
      <AnalysisModelPicker value={analysisModel} onChange={setAnalysisModel} />
    </div>
  );
}

// ---- Khi tạo ---------------------------------------------------------------------------------------------------

function ConfirmStep({
  title,
  scan,
  narrator,
  narratorAuto,
  firstPerson,
  firstPersonGender,
  tellerMode,
  povChapters,
  profile,
  seed,
  volumes,
  startNow,
  setStartNow,
  precastWait,
  setPrecastWait,
  dropCredits,
  credits,
  analysisModel,
  noStudio,
  unfit,
}: {
  /** "Chia thành nhiều tập": các tập sẽ tạo (số chương mỗi tập), hay không có khi là một sách. */
  volumes?: { chapters: number }[];
  title: string;
  scan: ScanResult;
  narrator: string;
  narratorAuto: boolean;
  firstPerson: string;
  firstPersonGender?: TellerGender;
  tellerMode?: boolean;
  povChapters: Record<string, string>;
  profile: Profile;
  seed?: Seed;
  startNow: boolean;
  setStartNow: (value: boolean) => void;
  precastWait: boolean;
  setPrecastWait: (value: boolean) => void;
  /** Người dùng đã đồng ý bỏ dòng ghi công khỏi phần đọc (đầu / cuối chương riêng). */
  dropCredits: CreditDrop;
  /** Dòng ghi công / ủng hộ phát hiện ở các chương đã chọn (gợi ý chưa áp nếu `dropCredits` tắt). */
  credits: Credits;
  analysisModel: string;
  /** Máy chưa có Studio: tạo được nhưng không chạy được - không ước thời gian, không "bắt đầu ngay". */
  noStudio?: boolean;
  /** Máy chưa có Studio và không đủ để làm sách nói (studioFit.ts): không tạo được ở đây - nói thật, mời tạo ở máy đã ghép. */
  unfit?: StudioFit;
}) {
  const models = useAnalysisModels().data;
  const option = PROFILES.find((item) => item.value === profile)!;
  const exact = matchesMeasured(useStudioGpu(), analysisModel);
  const guess = estimate(scan.totals.words, scan.files.length, exact);
  const measured = profile === "high_quality" && !noStudio;
  const rows: [string, string][] = [
    [S.s_chuong_2d157977, S.s_0_chuong_1_chu_7d350bc3(scan.files.length, approx(scan.totals.words, scan.totals.estimated))],
    // Tập 1 là sách thường, tập sau nối tiếp nó (continuation.py): nói rõ tên từng sách và việc "tự chạy khi tập trước xong".
    ...(volumes
      ? ([
          [S.s_chia_thanh_b0af0247, S.s_0_phan_1_e33b2de5(volumes.length, volumeTitles(title, volumes.length).map((name, index) => S.s_0_1_chuong_e82e8596(name, formatNumber(volumes[index].chapters))).join(", "))],
          [S.s_cac_phan_sau_c2deb368, startNow ? S.s_tu_chay_sau_phan_truoc_giu_giong_va_cach_d_3418c1f0 : S.s_xep_hang_sau_phan_1_giu_giong_va_cach_doc_a149ce8b],
        ] as [string, string][])
      : []),
    ...(droppedLines(credits, dropCredits)
      ? ([[
          creditKind({ ...credits, head: dropCredits.head ? credits.head : 0, tail: dropCredits.tail ? credits.tail : 0 }).replace(/^d/, "D"),
          S.s_bo_0_dong_khoi_phan_doc_6c4cc4ad(formatNumber(droppedLines(credits, dropCredits))),
        ]] as [string, string][])
      : []),
    [S.s_do_dai_audio_cc51e366, S.s_khoang_0_22035be1(formatLength(scan.totals.audioSeconds))],
    [S.s_giong_ke_b209f686, narratorAuto ? S.s_may_chon_cung_gioi_voi_nguoi_ke_toi_dang_l_13824b7a(narrator) : narrator],
    ...(firstPerson
      ? ([[S.s_nguoi_ke_toi_e2ce42b1, firstPersonGender ? `${firstPerson} (${firstPersonGender === "female" ? S.s_nu_316c30fd : "nam"})` : firstPerson]] as [string, string][])
      : []),
    ...(tellerMode ? ([[S.s_loi_ke_eba0761e, S.s_doc_bang_giong_cua_nguoi_ke_toi_e1d42efd]] as [string, string][]) : []),
    ...(Object.keys(povChapters).length
      ? ([[S.s_chuong_doi_nguoi_ke_88865076, Object.entries(povChapters).map(([chapter, name]) => S.s_chuong_0_1_e933721c(chapter, name)).join(", ")]] as [string, string][])
      : []),
    // "Nối tiếp: phần 2 của …" đọc như nối SAU phần 2 hay LÀ phần 2 đều được - nói thẳng là phần mấy, sau phần nào, và dải
    // chương (soát UX 29-09).
    ...(seed
      ? ([[
          S.s_la_9d0892e6,
          S.s_phan_0_cua_1_noi_sau_phan_2_48e60119(seed.part, seed.title, seed.part - 1) +
            (scan.files.length ? ` · ${chapterLabel(scan.files[0])} → ${chapterLabel(scan.files[scan.files.length - 1])}` : ""),
        ]] as [string, string][])
      : []),
    [S.s_nhan_vat_d4940c17, seed ? S.s_giu_0_nguoi_moi_duoc_phan_vai_sau_khi_phan_41927c80(carriedText(seed.carries)) : S.s_tu_dong_phan_vai_sau_khi_phan_tich_6530ecf1],
    [S.s_chat_luong_a12ed26c, option.title],
    // Luôn nói bộ phân tích nào sẽ đọc hiểu truyện - cả khi là mặc định - vì phân tích là bước dài nhất và không ngắt được.
    ...(analysisModel || models?.default
      ? ([[S.s_bo_phan_tich_truyen_9a52f60b, analysisChoiceLabel(analysisModel, seed?.analysisModel)]] as [string, string][])
      : []),
    ...(unfit
      ? ([[S.s_thoi_gian_lam_ba044b40, S.s_may_nay_khong_lam_sach_noi_duoc_a627fd2a]] as [string, string][])
      : noStudio
      ? ([[S.s_thoi_gian_lam_ba044b40, S.s_tinh_duoc_khi_studio_da_cai_du_an_cho_toi_4387d301]] as [string, string][])
      : measured
        ? ([
            [S.s_thoi_gian_lam_tham_khao_95d55912, lengthRange(guess.totalLow, guess.totalHigh)],
            [S.s_chuong_dau_nghe_duoc_sau_tham_khao_2d0bf61e, `${exact ? S.s_khoang_18209c07 : S.s_toi_da_khoang_1532dcc6} ${formatLength(guess.firstChapter)}`],
            [S.s_so_tham_khao_tu_dau_afcc409b, timeBasis(exact)],
          ] as [string, string][])
        : // "Nhanh" chưa có số đo trên máy này - vẫn nói được trần trên thay vì im lặng (soát UX a5 01-10).
          ([[S.s_thoi_gian_lam_ba044b40, S.s_chua_do_cho_che_do_nay_ngan_hon_chat_luong_eb953340(formatLength(guess.totalHigh))]] as [string, string][])),
  ];
  return (
    <MotionRegion as="div">
      <h3 className="text-base font-semibold">{S.s_khi_tao_07d6f63b}</h3>
      <div className="mt-2 divide-y divide-line">
        <label className="flex items-start gap-3 py-3" htmlFor="start-now">
          <Switch
            id="start-now"
            labelledBy="start-now-name"
            describedBy="start-now-hint"
            checked={startNow && !noStudio}
            disabled={noStudio}
            onCheckedChange={setStartNow}
          />
          <span>
            <span id="start-now-name" className="block text-sm font-medium">{S.s_bat_dau_tao_ngay_58ad17d7}</span>
            <MotionRegion as="span" id="start-now-hint" className="mt-0.5 block text-[0.8125rem] leading-relaxed text-fg-2">
              {unfit
                ? S.s_tat_vi_may_nay_khong_lam_sach_noi_duoc_ly_7f659322
                : noStudio
                ? S.s_chua_co_studio_sach_duoc_tao_va_cho_cai_xo_5e5d9ecf
                : startNow
                ? S.s_chay_nen_nghe_duoc_ngay_tung_chuong_da_xon_5872a97a
                : S.s_tao_nhung_chua_chay_bat_dau_o_trang_du_an_3c708f92}
            </MotionRegion>
          </span>
        </label>
        <label className="flex items-start gap-3 py-3" htmlFor="precast-wait">
          <Switch id="precast-wait" labelledBy="precast-wait-name" describedBy="precast-wait-hint" checked={precastWait} onCheckedChange={setPrecastWait} />
          <span>
            <span id="precast-wait-name" className="block text-sm font-medium">{S.s_duyet_truoc_khi_thu_74c121d0}</span>
            <MotionRegion as="span" id="precast-wait-hint" className="mt-0.5 block text-[0.8125rem] leading-relaxed text-fg-2">
              {precastWait
                ? S.s_dung_sau_phan_tich_de_ban_duyet_roi_bam_th_0ca451d3
                : S.s_phan_tich_xong_thi_thu_luon_duyet_luc_nao_1f91e9f9}
            </MotionRegion>
          </span>
        </label>
      </div>
      {/* Mọi lựa chọn sẽ gửi đi, kể cả thời gian tham khảo - một danh sách phẳng. */}
      <h3 className="mt-8 text-base font-semibold">{S.s_tom_tat_b4bb3064}</h3>
      <dl className="mt-2 divide-y divide-line text-sm">
        {rows.map(([label, value]) => (
          // Điện thoại: nhãn trên, giá trị dưới - cột nhãn cố định từng ép giá trị thành 5-6 dòng ở 390 px.
          <div key={label} className="grid gap-0.5 py-2 sm:grid-cols-[200px_minmax(0,1fr)] sm:gap-4">
            <dt className="text-fg-2">{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </MotionRegion>
  );
}

/** Nhắc ngay trên nút tạo, luôn thấy (không nằm trong "Tuỳ chọn"): phân tích không nên bị ngắt (AGENTS.md), làm lại thì bản dở vào
 *  Thùng rác, máy không đủ thì nói vì sao. */
function StartNotes({ restart, noStudio, unfit, analysis }: { restart?: { title: string }; noStudio: boolean; unfit?: StudioFit; analysis?: string }) {
  return (
    <MotionRegion as="div" className="mt-8 space-y-2 text-sm text-fg-2">
      {unfit && <NoStudioHere fit={unfit} />}
      {restart && (
        <p className="flex gap-2 text-pretty">
          <Info className="mt-line-icon size-4 shrink-0 text-info" />
          <span>{S.s_tao_cuon_moi_tu_dau_giu_bia_va_file_goc_ba_690baff8}{restart.title}{S.s_vao_thung_rac_76efc06d}</span>
        </p>
      )}
      <div className="flex gap-2 text-pretty">
        <AlertTriangle className="mt-line-icon size-4 shrink-0 text-warning" />
        <div>{S.s_dang_phan_tich_ma_can_nghi_hay_dung_tam_du_ddbf5b3d}{" "}
          <MoreInfo label={S.s_vi_sao_3f6469f9}>{S.s_dung_tat_may_cho_may_ngu_hoac_bam_dung_tro_98270a3d}{!noStudio && analysis && S.s_thoi_gian_tham_khao_0_b2b41058(analysis)}
          </MoreInfo>
        </div>
      </div>
    </MotionRegion>
  );
}

// ---- Trang ------------------------------------------------------------------------------------------------------

export function NewProjectScreen() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const continueId = params.get("continue") ?? undefined;
  const { data: plan, error: planError } = useContinuation(continueId);
  const redoId = params.get("redo") ?? undefined;
  const { data: redo, error: redoError } = useRedo(redoId);
  const scanMutation = useScan();
  const create = useCreateBook();
  const { data: voices } = useVoices();
  const { data: preferences } = usePreferences();
  const modelNames = useAvailableModelNames();
  const [draft, setDraft] = useState<Draft>(loadDraft);
  // Kết quả quét gắn với đúng danh sách nguồn đã quét (soát a92 V1): nguồn đổi thì kết quả cũ chỉ còn để xem / chỉnh, không dùng để tạo sách.
  const [scanned, setScanned] = useState<ScannedSources | null>(null);
  const rawScan = scanned?.result ?? null;
  const latestSources = useRef("");
  const [problem, setProblem] = useState<{ text: string; subfolders: string[] } | null>(null);
  const submitting = useRef(false);
  const noStudio = useStudioMissing().missing;
  // Máy không đủ để làm sách nói: dự án tạo ở đây sẽ không bao giờ chạy - không cho tạo, lý do ở bước đầu và bước cuối (soát a64).
  const fit = useStudioFit();
  const unfit = noStudio && fit?.level === "no" ? fit : undefined;
  const remote = Boolean(useAppInfo().data?.remote);
  const update = (changes: Partial<Draft>) => setDraft((current) => ({ ...current, ...changes }));

  useEffect(() => saveDraft(draft), [draft]);
  // Chất lượng mặc định cho sách mới (Cài đặt > Studio) - chỉ khi trình tạo còn trống, không đè lựa chọn đang dở.
  const profileApplied = useRef(false);
  useEffect(() => {
    if (profileApplied.current || !preferences) return;
    profileApplied.current = true;
    const wanted = preferences.newBookProfile;
    if (!draft.paths.length && !draft.seed && wanted && (PROFILE_VALUES as string[]).includes(wanted) && wanted !== draft.profile) {
      update({ profile: wanted as Profile });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preferences]);
  usePageTitle(draft.seed ? S.s_lam_tiep_cuon_nay_18bbf3cc : draft.replaces ? S.s_sua_thiet_lap_0_feb34d5a(draft.replaces.title) : undefined);

  // "Sửa thiết lập" (?redo=<id>): điền lại đúng lựa chọn lúc tạo của cuốn chưa bắt đầu, một lần, rồi bỏ tham số.
  useEffect(() => {
    if (!redoId || !redo) return;
    if (redo.started) {
      toast.error(S.s_sach_da_bat_dau_chay_d8b50089, { description: S.s_khong_the_lam_lai_voi_thiet_lap_khac_nua_b3eef0b6 });
      navigate(`/studio/${redoId}`, { replace: true });
      return;
    }
    setDraft({
      ...EMPTY_DRAFT,
      paths: redo.paths,
      title: redo.title,
      titleEdited: true,
      narrator: redo.narrator,
      // Giọng do máy chọn lúc tạo thì vẫn là máy chọn, không thành lựa chọn tay (soát UX a32, #8).
      narratorPicked: !redo.narratorAuto,
      firstPerson: redo.firstPerson,
      ...(redo.firstPersonGender ? { firstPersonGender: redo.firstPersonGender } : {}),
      ...(redo.tellerMode ? { tellerMode: true } : {}),
      ...(Object.keys(redo.firstPersonChapters ?? {}).length ? { povKept: redo.firstPersonChapters } : {}),
      ...(redo.analysisModel ? { analysisModel: redo.analysisModel } : {}),
      profile: (PROFILE_VALUES as string[]).includes(redo.profile) ? (redo.profile as Profile) : "high_quality",
      dropCredits: { head: Boolean(redo.dropCreditLines), tail: Boolean(redo.dropTailCreditLines) },
      replaces: {
        id: redoId,
        title: redo.title,
        ...(redo.seedFrom ? { seedFrom: redo.seedFrom } : {}),
        ...(redo.analysisInterrupted ? { restart: true } : {}),
      },
    });
    setParams({}, { replace: true });
  }, [redoId, redo, setParams, navigate]);
  useEffect(() => {
    if (redoError) toast.error(S.s_chua_doc_duoc_thiet_lap_cua_sach_d7efab34, { description: (redoError as Error).message });
  }, [redoError]);

  // "Làm tiếp cuốn này" (?continue=<id>): điền sẵn một lần từ phần trước rồi bỏ tham số, để quay lại trang không điền đè
  // những gì người dùng đã sửa.
  useEffect(() => {
    if (!continueId || !plan) return;
    setDraft({
      ...EMPTY_DRAFT,
      paths: plan.paths,
      title: plan.title,
      titleEdited: true,
      narrator: plan.narrator,
      firstPerson: plan.firstPerson,
      ...(plan.analysisModel ? { analysisModel: plan.analysisModel } : {}),
      profile: (PROFILE_VALUES as string[]).includes(plan.profile) ? (plan.profile as Profile) : "high_quality",
      seed: {
        id: plan.sourceId || continueId,
        title: plan.sourceTitle,
        clickedTitle: plan.clickedTitle,
        latestTitle: plan.latestTitle,
        analysisModel: plan.analysisModel,
        analysisModelMissing: plan.analysisModelMissing,
        part: plan.part,
        analyzed: plan.analyzed,
        empty: plan.paths.length === 0,
        carries: plan.carries,
        narrator: plan.narrator,
        folder: plan.folder,
        lastChapter: plan.lastChapter,
      },
    });
    setParams({}, { replace: true });
  }, [continueId, plan, setParams]);

  useEffect(() => {
    if (planError) toast.error(S.s_chua_mo_duoc_phan_truoc_52e838aa, { description: planError.message });
  }, [planError]);

  useEffect(() => {
    if (!draft.narrator && voices?.length) update({ narrator: defaultNarrator(voices, preferences?.newBookNarrator) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voices, draft.narrator, preferences?.newBookNarrator]);

  // Chọn một mẫu thiết lập (hay "Mặc định" = null): chỉ giọng kể, chất lượng, model, "bắt đầu ngay" của nháp đổi theo.
  const pickTemplate = (template: BookTemplate | null) => {
    const fallback: BookTemplate = {
      name: DEFAULT_LABEL,
      narrator: voices?.length ? defaultNarrator(voices, preferences?.newBookNarrator) : "",
      profile: (PROFILE_VALUES as string[]).includes(preferences?.newBookProfile ?? "") ? (preferences?.newBookProfile as Profile) : "high_quality",
      analysisModel: "",
      startNow: true,
      precastWait: false,
    };
    // Mẫu có ghi giọng kể là lựa chọn của người dùng; "Mặc định" và mẫu không ghi giọng thì máy vẫn chọn giọng dẫn theo giới người kể "tôi".
    const apply = (current: Draft): Draft =>
      template
        ? {
            ...applyTemplate(current, template, voices?.map((voice) => voice.name), modelNames, fallback.narrator),
            narratorPicked: Boolean(template.narrator),
          }
        : { ...applyTemplate(current, fallback), template: undefined, narratorPicked: false };
    const before = templateChoices(draft);
    const changed = changedChoices(before, templateChoices(apply(draft)));
    setDraft(apply);
    // Áp mẫu ghi đè giọng / chất lượng / chờ duyệt bạn vừa chọn: nói đã đổi gì và cho trả lại (soát UX a32).
    if (changed.length) {
      toast.success(S.s_da_ap_0_doi_1_cf6466d9(template ? S.s_mau_0_184a389f(template.name) : S.s_lua_chon_mac_dinh_2b7a4461, changed.join(", ")), {
        action: { label: S.s_hoan_tac_e72ff675, onClick: () => setDraft((current) => ({ ...current, ...before })) },
        duration: 8000,
      });
    }
  };

  // Quét lại chỉ khi danh sách nguồn đổi; bỏ một chương là lọc ngay ở đây, không đọc lại cả thư mục.
  useEffect(() => {
    if (!draft.paths.length) {
      latestSources.current = "";
      setScanned(null);
      setProblem(null);
      return;
    }
    const key = sourcesKey(draft.paths);
    latestSources.current = key;
    scanMutation.mutate({ paths: draft.paths, seedFrom: draft.seed?.id }, {
      onSuccess: (result) => {
        // Lượt quét của danh sách nguồn đã bị thay thì bỏ, đừng để nó đè lên kết quả của danh sách hiện tại.
        if (latestSources.current !== key) return;
        setScanned({ key, result });
        if (!result.files.length) {
          setProblem(
            result.errors?.length
              ? { text: S.s_chua_mo_duoc_0_849699f5(result.errors[0]), subfolders: [] }
              : result.missing.length
              ? { text: isSourceRef(result.missing[0]) ? S.s_khong_tim_thay_0_tren_may_tinh_gui_lai_roi_1e682119(sourceName(result.missing[0])) : S.s_khong_tim_thay_0_kiem_tra_lai_duong_dan_9c467c16(result.missing[0]), subfolders: [] }
              : { text: S.s_thu_muc_nay_khong_co_file_txt_hay_epub_doc_9c5a2dff, subfolders: result.subfolders },
          );
          return;
        }
        setProblem(null);
        setDraft((current) => (current.titleEdited || !result.suggestedTitle ? current : { ...current, title: result.suggestedTitle }));
      },
      onError: (error: Error) => {
        if (latestSources.current !== key) return;
        setScanned({ key, result: null });
        setProblem({ text: S.s_chua_doc_duoc_0_3adbe047(error.message), subfolders: [] });
      },
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft.paths.join("\n")]);

  // Chia nhiều tập: các chương theo thứ tự của đề xuất (mỗi thư mục / EPUB liền nhau - quét theo tên file thì chương các tập
  // xen nhau), và "N chương đầu" không áp (nó cắt một sách, không phải một bộ).
  const splitting = draft.volumeStarts != null;
  // Trang phụ của file sách chưa tích lại cũng là chương không vào sách (cùng luật chọn mặc định với Nghe ngay).
  const excludedPaths = useMemo(() => allExcluded(rawScan?.files ?? [], draft.excluded, draft.keepMatter ?? []), [rawScan, draft.excluded, draft.keepMatter]);
  const ordered = useMemo(
    () => (rawScan ? (splitting ? inOrder(rawScan.files, rawScan.volumes?.order) : rawScan.files) : []),
    [rawScan, splitting],
  );
  const scan = useMemo<ScanResult | null>(() => {
    if (!rawScan) return null;
    const excluded = new Set(excludedPaths);
    const kept = ordered.filter((file) => !excluded.has(file.path));
    const files = draft.limit && !splitting ? kept.slice(0, draft.limit) : kept;
    const words = files.reduce((sum, file) => sum + file.words, 0);
    const audioSeconds = files.reduce((sum, file) => sum + (file.audioSeconds ?? 0), 0); // ước của máy chủ, cùng cách hộp Xuất sách nói
    const estimated = files.some((file) => file.estimated);
    return { ...rawScan, files, totals: { chapters: files.length, words, audioSeconds, ...(estimated ? { estimated } : {}) } };
  }, [rawScan, ordered, excludedPaths, draft.limit, splitting]);
  const volumeStarts = useMemo(
    () => (splitting && scan ? startNumbers(ordered, draft.volumeStarts, new Set(excludedPaths)) : [1]),
    [splitting, scan, ordered, draft.volumeStarts, excludedPaths],
  );

  // Cùng khoá truy vấn với bước "Tôi là ai?": lấy từ bộ nhớ đệm, không đọc lại sách.
  const { data: firstPersonHint } = useFirstPersonHint(scan?.files.map((file) => file.path) ?? [], draft.seed?.id);
  // "Sửa thiết lập": chương nào của gợi ý mà lúc tạo bạn không giữ thì tắt đi; chương giữ thì vẫn bật.
  useEffect(() => {
    if (!draft.povKept || !firstPersonHint) return;
    const kept = draft.povKept;
    const book = draft.firstPerson.trim().toUpperCase();
    const off = (firstPersonHint.chapters ?? []).filter((chapter) => chapter.name !== book && !(String(chapter.chapter) in kept)).map((chapter) => chapter.chapter);
    setDraft((current) => ({ ...current, povKept: undefined, povOff: off }));
  }, [draft.povKept, draft.firstPerson, firstPersonHint]);
  const povChapters = chosenPovChapters(firstPersonHint, draft.firstPerson, draft.povOff ?? []);
  const autoNarrator = narratorIsAuto(draft, preferences?.newBookNarrator, voices);

  const title = draft.title;
  const reading = !scanIsCurrent(scanned, draft.paths);
  // Một trang, không bước (DESIGN.md L10: Studio -> "Dự án mới" -> chọn file -> "Bắt đầu"): giọng, chất lượng, model, "bắt đầu ngay"
  // đã chọn sẵn theo mặc định tốt và gập dưới "Tuỳ chọn"; mở rồi thì lần sau vẫn mở.
  const [optionsOpen, setOptionsOpen] = useFold("new-project.options", false);
  const ready = Boolean(scan?.files.length);
  const exact = matchesMeasured(useStudioGpu(), draft.analysisModel ?? "");
  const guess = scan ? estimate(scan.totals.words, scan.files.length, exact) : null;
  const analysisTime = guess && draft.profile === "high_quality" ? (exact ? formatLength(guess.analysis) : lengthRange(guess.analysisLow, guess.analysisHigh)) : undefined;
  const optionsSummary = [
    autoNarrator ? S.s_giong_ke_may_chon_bcf6a534 : S.s_giong_ke_0_958dd853(draft.narrator),
    PROFILES.find((option) => option.value === draft.profile)?.title,
    draft.startNow && !noStudio ? S.s_bat_dau_ngay_83137873 : S.s_chua_chay_713224b6,
  ].filter(Boolean).join(" · ");

  const gate = createGate({ title, reading, unfit: Boolean(unfit) });
  const submit = () => {
    // Đang đọc lại nguồn (vừa thêm / bớt file): `scan` còn là của danh sách cũ - đợi, đừng tạo sách thiếu chương vừa chọn.
    if (reading) return;
    if (!scan?.files.length || !title.trim() || submitting.current) return;
    submitting.current = true;
    create.mutate(
      {
        paths: scan.files.map((file) => file.path),
        ...(volumeStarts.length > 1 ? { volumeStarts } : {}),
        title: title.trim(),
        profile: draft.profile,
        // Máy chọn giọng dẫn: gửi rỗng - máy chủ đặt giọng cùng giới người kể "tôi" và ghi nhớ đó là lựa chọn của máy.
        narrator: autoNarrator ? "" : draft.narrator,
        firstPerson: draft.firstPerson.trim(),
        ...(draft.firstPerson.trim() && draft.firstPersonGender ? { firstPersonGender: draft.firstPersonGender } : {}),
        ...(draft.firstPerson.trim() && draft.tellerMode ? { tellerMode: true } : {}),
        ...(Object.keys(povChapters).length ? { firstPersonChapters: povChapters } : {}),
        ...(draft.seed ? { seedFrom: draft.seed.id } : draft.replaces?.seedFrom ? { seedFrom: draft.replaces.seedFrom } : {}),
        // Studio từ xa không nói tên đường dẫn nào: chương nguồn là `ref:...` của cuốn cũ, máy tính tự đổi ra file và tự thay cuốn cũ.
        ...(draft.replaces ? (remote ? { redoOf: draft.replaces.id } : { replaces: draft.replaces.id }) : {}),
        ...(draft.analysisModel ? { analysisModel: draft.analysisModel } : {}),
        // Chỉ khi người dùng đã đồng ý đề xuất - không gửi gì thì sách giữ nguyên nội dung.
        ...(draft.dropCredits?.head && creditSummary(scan.files).head ? { dropCreditLines: true } : {}),
        ...(draft.dropCredits?.tail && creditSummary(scan.files).tail ? { dropTailCreditLines: true } : {}),
        start: draft.startNow && !noStudio,
        ...(draft.precastWait ? { precastWait: true } : {}),
      },
      {
        onSuccess: (result) => {
          saveDraft(null);
          const volumes = result.parts?.length ?? 0;
          // MỘT dòng: trang dự án (mở ngay sau đây) nói tiến trình; chỉ hàng chờ nằm trong câu, và việc Studio chưa cài xong là cảnh báo cùng dòng.
          const queued = draft.startNow && !noStudio && result.queued ? S.s_vao_hang_cho_thu_0_76b18f6c(result.queued) : "";
          toastDone(
            (result.unchanged
              ? S.s_khong_co_thiet_lap_nao_thay_doi_giu_nguyen_929846eb
              : volumes > 1
                ? S.s_da_tao_0_phan_dd256b57(volumes)
                : draft.replaces?.restart
                  ? S.s_da_lam_lai_sach_tu_dau_6e51eb4c
                  : draft.replaces
                    ? S.s_da_tao_lai_sach_voi_thiet_lap_moi_cd546877
                    : S.s_da_tao_sach_15431889) + queued,
            noStudio ? S.s_du_an_cho_toi_khi_studio_cai_xong_roi_bam_9937b79b : undefined,
          );
          if (result.replaceError) toast.warning(S.s_ban_cu_van_con_trong_du_an_19473cdb, { description: result.replaceError });
          navigate(`/studio/${result.id}`, { replace: true });
        },
        onError: (error: Error) => toast.error(S.s_chua_tao_duoc_sach_2d0ce411, { description: error.message }),
        onSettled: () => {
          submitting.current = false;
        },
      },
    );
  };

  return (
    <div className="page-x mx-auto max-w-[920px] pb-16">
      <ScreenHeader back={{ label: S.s_ve_studio_349a48c4, onClick: () => navigate("/studio") }} title={<MotionRegion as="span">{draft.seed ? S.s_lam_tiep_cuon_nay_18bbf3cc : S.s_tao_sach_noi_ab873c7a}</MotionRegion>} />
      <MotionPresence open={Boolean(draft.seed)}>{draft.seed && (
        <SeedBanner
          seed={draft.seed}
          hasFiles={(rawScan?.files.length ?? 0) > 0}
          onDrop={() => {
            // Bỏ nối tiếp = phân vai lại từ đầu, giọng lệch phần trước: một cú bấm lỡ tay phải lấy lại được (soát UX 29-09).
            const previous = draft.seed;
            update({ seed: undefined });
            toast(S.s_da_bo_noi_tiep_sach_se_phan_vai_lai_tu_dau_fa1cf109, {
              duration: 10000,
              action: { label: S.s_hoan_tac_e72ff675, onClick: () => update({ seed: previous }) },
            });
          }}
        />
      )}</MotionPresence>
      <div className="mt-8">
          <StudioInstallNotice className="mb-6" />
          <SourceStep
            scan={scan}
            title={title}
            onTitle={(value) => update({ title: value, titleEdited: true })}
            scanning={scanMutation.isPending}
            onPaths={(paths) => update({ paths, excluded: [], keepMatter: [], limit: null, volumeStarts: null, titleEdited: paths.length ? draft.titleEdited : false })}
            matter={{ files: rawScan?.files ?? [], keep: draft.keepMatter ?? [] }}
            onKeepMatter={(path, on) => setDraft((current) => ({ ...current, ...keepMatter(current, path, on) }))}
            onAddFiles={(paths) => setDraft((current) => ({ ...current, paths: [...current.paths, ...paths], volumeStarts: null }))}
            splitting={splitting}
            volumeStarts={volumeStarts}
            volumeSplit={
              <VolumeSplit
                ordered={ordered}
                excluded={excludedPaths}
                files={scan?.files ?? []}
                proposal={rawScan?.volumes}
                title={title.trim()}
                value={draft.volumeStarts ?? null}
                onChange={(volumeStarts) => update({ volumeStarts })}
              />
            }
            total={rawScan?.files.length ?? 0}
            limit={draft.limit ?? null}
            later={(rawScan?.files.filter((file) => !excludedPaths.includes(file.path)).length ?? 0) - (scan?.files.length ?? 0)}
            onLimit={(count) => update({ limit: count })}
            onRemove={(path) => {
              update({ excluded: [...draft.excluded, path] });
              const name = sourceName(path);
              toast(S.s_da_bo_0_d38fac95(name), {
                id: `removed-${path}`,
                action: {
                  label: S.s_hoan_tac_e72ff675,
                  onClick: () => setDraft((current) => ({ ...current, excluded: current.excluded.filter((item) => item !== path) })),
                },
              });
            }}
            problem={problem}
            dropCredits={draft.dropCredits ?? KEEP_CREDITS}
            onDropCredits={(value) => update({ dropCredits: value })}
            previousLast={draft.seed?.lastChapter}
            replaces={draft.replaces}
            onSplit={async (path) => {
              try {
                // Tên sách đang điền đi kèm: dòng tên truyện đầu file trùng nó thì không thành chương "Mở đầu" (txt_split.split).
                const { folder } = await api<{ folder: string }>("/api/sources/split", { method: "POST", body: { path, title: draft.title.trim() } });
                // File đã chọn thẳng: thư mục chương thay chỗ nó. File nằm trong một thư mục đã chọn: thêm thư mục chương,
                // bỏ file cả truyện khỏi danh sách (vẫn hoàn tác được như mọi chương bỏ tay).
                // Đường người dùng gõ ("D:/Truyện/a.txt") khác dạng đường máy quét ("D:\Truyện\a.txt"): so bằng samePath.
                const replaced = draft.paths.some((item) => samePath(item, path));
                // Tên sách người dùng đã có / đã gõ ở lại: thư mục chương mang tên FILE ("ngon_den_cuoi_cung"), không được đè lên nó khi quét lại.
                const keepTitle = draft.title.trim() ? { titleEdited: true } : {};
                update(
                  replaced
                    ? { paths: draft.paths.map((item) => (samePath(item, path) ? folder : item)), excluded: [], keepMatter: [], limit: null, volumeStarts: null, ...keepTitle }
                    : { paths: [...draft.paths, folder], excluded: [...draft.excluded, path], limit: null, volumeStarts: null, ...keepTitle },
                );
                const plan = scan?.files.find((file) => samePath(file.path, path))?.split;
                const chapters = plan ? splitOutcome(plan, draft.title).chapters : undefined;
                toast.success(chapters ? S.s_da_tach_thanh_0_chuong_fa082fb5(formatNumber(chapters)) : S.s_da_tach_thanh_cac_chuong_1e1bb231);
              } catch (error) {
                toast.error(S.s_chua_tach_duoc_7d64588d, { description: (error as Error).message });
              }
            }}
          />
          {/* "Tuỳ chọn": một dòng tóm tắt lựa chọn đang dùng; bấm thì mở giọng kể, chất lượng, model và cách bắt đầu. Hiện khi đã có
              chương - trước đó chưa có gì để chọn. */}
          <MotionPresence open={ready}>
            <section className="mt-8 border-t border-line">
              <h2><DisclosureRow section title={S.s_tuy_chon_dc06ba8f} summary={optionsSummary} icon={<SlidersHorizontal className="size-4" />} expanded={optionsOpen} controls="new-project-options" onClick={() => setOptionsOpen(!optionsOpen)} /></h2>
              <Collapse open={optionsOpen} id="new-project-options">
                <div className="space-y-12 pb-4 pt-4">
                  {/* Mẫu thiết lập chỉ cho sách mới: "Làm tiếp cuốn này" theo phần trước. */}
                  {/* "Bỏ nối tiếp" / "Hoàn tác": thanh mẫu mở / khép tại chỗ; khoảng cách 48 px nằm trong phần khép (không nhảy khi gỡ). */}
                  <MotionPresence open={!draft.seed} className="mb-0!" bodyClassName="pb-12"><TemplateBar draft={draft} onPick={pickTemplate} narratorAuto={autoNarrator} /></MotionPresence>
                  <VoiceStep
                    narrator={draft.narrator}
                    setNarrator={(narrator) => update({ narrator, narratorPicked: true })}
                    paths={scan?.files.map((file) => file.path) ?? []}
                    seedFrom={draft.seed?.id}
                    previousNarrator={draft.seed?.narrator}
                    firstPerson={draft.firstPerson}
                    setFirstPerson={(firstPerson) => update({ firstPerson, ...(firstPerson.trim() ? {} : { firstPersonGender: undefined, tellerMode: false }) })}
                    firstPersonGender={draft.firstPersonGender}
                    setFirstPersonGender={(firstPersonGender) => {
                      // Máy chọn giọng dẫn thì giọng hiện trong lưới theo giới vừa chọn (máy chủ đặt đúng giọng ấy lúc tạo).
                      const suggested = autoNarrator ? recommendedFor(voices, firstPersonGender) : undefined;
                      update({ firstPersonGender, ...(suggested ? { narrator: suggested } : {}) });
                    }}
                    tellerMode={draft.tellerMode}
                    setTellerMode={(tellerMode) => update({ tellerMode })}
                    narratorAuto={autoNarrator}
                    povOff={draft.povOff ?? []}
                    setPovOff={(povOff) => update({ povOff })}
                  />
                  {scan && (
                    <QualityStep profile={draft.profile} setProfile={(profile) => update({ profile })} words={scan.totals.words} chapters={scan.files.length}
                      analysisModel={draft.analysisModel ?? ""} setAnalysisModel={(analysisModel) => update({ analysisModel })} noStudio={noStudio} />
                  )}
                  {scan && (
                    <ConfirmStep
                      title={title.trim()}
                      scan={scan}
                      narrator={draft.narrator}
                      narratorAuto={autoNarrator}
                      firstPerson={draft.firstPerson.trim()}
                      firstPersonGender={draft.firstPerson.trim() ? draft.firstPersonGender : undefined}
                      tellerMode={draft.firstPerson.trim() ? draft.tellerMode : false}
                      povChapters={povChapters}
                      profile={draft.profile}
                      seed={draft.seed}
                      volumes={volumeStarts.length > 1 ? ranges(volumeStarts, scan.files.length) : undefined}
                      startNow={draft.startNow}
                      setStartNow={(startNow) => update({ startNow })}
                      precastWait={Boolean(draft.precastWait)}
                      setPrecastWait={(precastWait) => update({ precastWait })}
                      dropCredits={draft.dropCredits ?? KEEP_CREDITS}
                      credits={creditSummary(scan.files)}
                      analysisModel={draft.analysisModel ?? ""}
                      noStudio={noStudio}
                      unfit={unfit}
                    />
                  )}
                </div>
              </Collapse>
            </section>
          </MotionPresence>
          <MotionPresence open={ready}>
            <StartNotes restart={draft.replaces?.restart ? { title: draft.replaces.title } : undefined} noStudio={noStudio} unfit={unfit} analysis={analysisTime} />
          </MotionPresence>
          {/* Ghim ở đáy vùng cuộn: bước xác nhận dài (thêm dòng "Dòng ghi công"...) đẩy nút tạo xuống dưới nếp màn hình - soát
              UX 29-09. */}
          {/* Ghim ở đáy vùng cuộn: "Tuỳ chọn" mở ra dài thì nút tạo vẫn luôn thấy (DESIGN.md mục 6). Hiện khi đã đọc được chương - trước
              đó việc chính là chọn nguồn, mỗi lúc một nút chính. */}
          <MotionPresence open={ready} className="sticky bottom-0 z-10 mt-8 bg-bg">
            <div className="flex items-center justify-between gap-3 border-t border-line py-4">
              <Button
                variant="ghost"
                onClick={() => {
                  saveDraft(null);
                  setDraft(EMPTY_DRAFT);
                  latestSources.current = "";
                  setScanned(null);
                }}
              >{S.s_bat_dau_lai_a3fe79c8}</Button>
              <span className="flex min-w-0 items-center gap-3">
                <MotionPresence open={Boolean(unfit)}><span className="min-w-0 text-right text-[0.8125rem] text-fg-2 text-pretty">{S.s_may_thieu_cau_hinh_df5ae9ef}</span></MotionPresence>
                <Button variant="primary" size="lg" icon={draft.startNow && !noStudio ? Wand2 : Mic} loading={create.isPending || gate.reading} disabled={gate.disabled} onClick={submit}>
                  {gate.label ?? (draft.startNow && !noStudio ? S.s_bat_dau_b3cacc46 : S.s_tao_sach_af3aeee3)}
                </Button>
              </span>
            </div>
          </MotionPresence>
      </div>
    </div>
  );
}

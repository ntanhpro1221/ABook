import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Check,
  Clock3,
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
  Sparkles,
  Trash2,
  Upload,
  Wand2,
} from "lucide-react";
import { Fragment, useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { Switch } from "@/desktop/PhoneSync";
import { useClip } from "@/listen/clip";
import { useSource } from "@/listen/source";
import { BookCover } from "@/shared/BookCover";
import { cn } from "@/shared/cn";
import { usePageTitle } from "@/shared/title";
import { formatLength, formatNumber } from "@/shared/format";
import { Button, Segmented, Vu, radioGroupKeys, radioTabIndex } from "@/shared/ui";
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
  useVoices,
} from "@/studio/data";
import { api } from "@/studio/api";
import { chapterNumberIssues } from "@/studio/chapterNumbers";
import { samePath } from "@/studio/samePath";
import { uploadChapters } from "@/studio/upload";
import { AnalysisModelPicker, modelLabel, useAnalysisModels } from "@/studio/AnalysisModelPicker";
import { DEFAULT_LABEL, applyTemplate, type BookTemplate, type Profile } from "@/studio/bookTemplates";
import { TemplateBar } from "@/studio/TemplateBar";
import { VolumeSplit } from "@/studio/VolumeSplit";
import { inOrder, ranges, startNumbers, volumeTitles } from "@/studio/volumes";

const STEPS = [
  { title: "Nội dung", hint: "TXT, EPUB, DOCX hay PDF" },
  { title: "Giọng kể", hint: "Người dẫn truyện" },
  { title: "Chất lượng", hint: "Nhanh hay kỹ" },
  { title: "Xác nhận", hint: "Xem lại và tạo" },
];

const PROFILES: { value: Profile; title: string; pace: string; summary: string; points: string[] }[] = [
  {
    value: "fast",
    title: "Nhanh",
    pace: "Nhanh nhất",
    summary: "Nghe thử một truyện mới, hoặc cần gấp.",
    points: ["Phân tích truyện từng đoạn dài một lượt", "Soát cơ bản sau khi đọc", "Đọc lại tối đa 1 lần nếu câu bị đọc sai"],
  },
  {
    value: "balanced",
    title: "Cân bằng",
    pace: "Vừa phải",
    summary: "Nghe hằng ngày, chấp nhận vài câu chưa hoàn hảo.",
    points: ["Phân tích truyện đầy đủ", "Soát cơ bản sau khi đọc", "Đọc lại tối đa 2 lần nếu câu bị đọc sai"],
  },
  {
    value: "high_quality",
    title: "Chất lượng cao",
    pace: "Chậm nhất, kỹ nhất",
    summary: "Sách nghe lại nhiều lần hoặc để chia sẻ.",
    points: ["Rà lại cảm xúc từng câu một lần nữa", "Nghe lại mọi câu, soát kỹ từng chữ", "Đọc lại tới 5 lần nếu câu bị đọc sai"],
  },
];
const PROFILE_VALUES = PROFILES.map((option) => option.value);
// Chọn nhanh số chương cho một đợt - chỉ hiện khi nguồn có nhiều hơn mức nhỏ nhất.
const CHAPTER_LIMITS = [20, 50, 100];

// Ước lượng thời gian làm trên máy này, đo từ hai lô gần nhất của cuốn 2 (26-09, mức Chất lượng cao): lô 18 có
// 113 nghìn chữ, phân tích ~4 giờ, thu âm 4,6-7,1 giờ. Hai mức kia chưa đo trên máy này nên không đoán con số.
const MEASURED = { analysisPerKiloword: 2.1 * 60, synthesisPerKiloword: [2.5 * 60, 3.8 * 60] as const };

function estimate(words: number, chapters: number) {
  const kilo = words / 1000;
  const analysis = kilo * MEASURED.analysisPerKiloword;
  const [low, high] = MEASURED.synthesisPerKiloword.map((seconds) => kilo * seconds);
  return {
    analysis,
    totalLow: analysis + low,
    totalHigh: analysis + high,
    firstChapter: analysis + high / Math.max(1, chapters),
  };
}

function lengthRange(low: number, high: number): string {
  const a = formatLength(low);
  const b = formatLength(high);
  return a === b ? `khoảng ${a}` : `${a} - ${b}`;
}

// ---- Nháp: rời trang rồi quay lại không mất gì ----------------------------------------------------------------

interface Draft {
  paths: string[];
  excluded: string[];
  title: string;
  titleEdited: boolean;
  narrator: string;
  /** Người xưng "tôi" ở truyện kể ngôi thứ nhất ("" = ngôi thứ ba). */
  firstPerson: string;
  /** Chương đổi góc kể (gợi ý của máy) mà người dùng bỏ chọn - số chương trong sách. */
  povOff?: number[];
  profile: Profile;
  startNow: boolean;
  /** "Chờ tôi duyệt trước khi thu" (webui/precast.py): phân tích xong thì sách tạm dừng chờ người duyệt. Mặc định tắt. */
  precastWait?: boolean;
  /** "Làm tiếp cuốn này": phần trước để gieo từ (continuation.py), hay không có khi là sách mới. */
  seed?: Seed;
  /** Chip "Đợt này làm N chương đầu": N chương đầu trong số chương CHƯA bị bỏ tay (null/không có = tất cả). Tách khỏi
   *  `excluded` - trước đây chip ghi đè danh sách bỏ tay, chương vừa bỏ tự quay lại (soát UX 29-09). */
  limit?: number | null;
  /** "Chia thành nhiều tập" (B7): đường dẫn chương đầu mỗi tập người dùng đã đồng ý chia; null/không có = một sách. */
  volumeStarts?: string[] | null;
  /** Người dùng ĐỒNG Ý bỏ dòng ghi công người dịch khỏi phần đọc. Mặc định không: app không tự sửa nội dung truyện. */
  dropCredits?: boolean;
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

// ---- Thanh bước --------------------------------------------------------------------------------------------------

function StepRail({ step, allowed, onGo }: { step: number; allowed: number; onGo: (index: number) => void }) {
  return (
    // Dưới lg (điện thoại, cửa sổ hẹp): bốn bước một hàng ngang, bỏ dòng gợi ý - xếp dọc thì chiếm ~250 px trước khi tới
    // nội dung của bước (soát UX 29-09).
    <ol className="grid grid-cols-4 gap-1 lg:block lg:space-y-1">
      {STEPS.map((item, index) => {
        const done = index < step;
        const current = index === step;
        const enabled = index <= allowed;
        return (
          <li key={item.title}>
            <button
              type="button"
              disabled={!enabled}
              aria-current={current ? "step" : undefined}
              onClick={() => onGo(index)}
              className={cn(
                "flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-colors disabled:cursor-not-allowed max-lg:flex-col max-lg:gap-1 max-lg:px-1 max-lg:text-center",
                current ? "bg-hover" : enabled && "hover:bg-hover",
              )}
            >
              <span
                className={cn(
                  "grid size-7 shrink-0 place-items-center rounded-full text-xs font-bold",
                  done ? "bg-success text-white" : current ? "bg-accent text-accent-ink" : "bg-hover text-fg-2",
                )}
              >
                {done ? <Check className="size-4" strokeWidth={3} /> : index + 1}
              </span>
              <span>
                <span className={cn("block text-sm font-medium max-lg:text-xs", !current && !done && "text-fg-2")}>{item.title}</span>
                <span className="block text-xs text-fg-2 max-lg:hidden">{item.hint}</span>
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

// ---- Bước 1 ---------------------------------------------------------------------------------------------------

function SourceStep({
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
}: {
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
  dropCredits: boolean;
  onDropCredits: (value: boolean) => void;
  /** Tách một file cả truyện thành các chương (máy ghi thư mục mới), rồi quét thư mục ấy thay cho file. */
  onSplit: (path: string) => Promise<void>;
  /** "Làm tiếp": file chương cuối của phần trước - phần này phải bắt đầu ngay sau nó. */
  previousLast?: string;
}) {
  const { data: info } = useAppInfo();
  const [typed, setTyped] = useState("");
  // Studio từ xa: máy đang xem không có đường dẫn nào trên máy tính - nó gửi các chương đi (studio/upload.ts).
  const uploadInput = useRef<HTMLInputElement | null>(null);
  const [uploading, setUploading] = useState<{ done: number; total: number } | null>(null);
  const upload = async (list: FileList | null) => {
    if (!list?.length) return;
    setUploading({ done: 0, total: list.length });
    try {
      onPaths([await uploadChapters([...list], (done, total) => setUploading({ done, total }))]);
    } catch (error) {
      toast.error("Không gửi được các chương", { description: (error as Error).message });
    } finally {
      setUploading(null);
    }
  };
  const chooseFolder = async () => {
    const path = await pickFolder("Chọn thư mục chứa các chương TXT").catch((error: Error) => {
      toast.error(error.message);
      return null;
    });
    if (path) onPaths([path]);
  };
  const chooseFiles = async (append: boolean) => {
    const chosen = await pickFiles("Chọn các chương TXT hay một file sách (EPUB, DOCX, PDF)").catch((error: Error) => {
      toast.error(error.message);
      return [];
    });
    if (chosen.length) (append ? onAddFiles : onPaths)(chosen);
  };
  const files = scan?.files ?? [];
  return (
    <div>
      <h2 className="text-xl font-semibold">Chọn các chương của truyện</h2>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-fg-2">
        <li>Mỗi file TXT là một chương, xếp theo tên file (2 đứng trước 10).</li>
        <li>Có file EPUB, Word hay PDF thì chọn thẳng nó - máy tách chương, bạn xem lại danh sách trước khi tạo. PDF phải có chữ.</li>
        <li>Cả truyện nằm trong một file TXT thì máy gợi ý tách theo các dòng “Chương N”.</li>
      </ul>
      {!files.length ? (
        <div className="mt-6 rounded-2xl border-2 border-dashed border-line-strong bg-panel px-8 py-10 text-center">
          <div className="mx-auto grid size-14 place-items-center rounded-2xl bg-accent-soft text-accent-text">
            {scanning ? <Loader2 className="size-7 animate-spin" /> : <FolderInput className="size-7" strokeWidth={1.75} />}
          </div>
          <p className="mt-4 font-medium">
            {scanning ? "Đang đọc các chương…" : info?.remote ? "Gửi các chương từ máy này" : "Chọn thư mục truyện hay một file EPUB, DOCX, PDF"}
          </p>
          <p className="mt-1 text-sm text-fg-2">
            {info?.remote
              ? "Chọn cùng lúc mọi file .txt của truyện, hay một file .epub / .docx / .pdf. Máy tính giữ chúng trong mục “Nguồn tải lên”."
              : "Chỉ lấy file nằm ngay trong thư mục, không quét thư mục con."}
          </p>
          {info?.remote && (
            <div className="mt-6 flex justify-center">
              <input
                ref={uploadInput}
                type="file"
                multiple
                accept=".txt,.epub,.docx,.pdf,text/plain,application/epub+zip,application/pdf"
                className="sr-only"
                tabIndex={-1}
                aria-hidden
                onChange={(event) => {
                  void upload(event.target.files);
                  event.target.value = "";
                }}
              />
              <Button variant="primary" icon={Upload} loading={Boolean(uploading)} onClick={() => uploadInput.current?.click()}>
                {uploading ? `Đang gửi ${uploading.done}/${uploading.total} chương` : "Chọn các file TXT"}
              </Button>
            </div>
          )}
          {info?.dialogs && (
            <div className="mt-6 flex justify-center gap-2">
              <Button variant="primary" icon={Folder} onClick={() => void chooseFolder()}>
                Chọn thư mục
              </Button>
              <Button icon={FileText} onClick={() => void chooseFiles(false)}>
                Chọn từng file
              </Button>
            </div>
          )}
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
              aria-label="Đường dẫn thư mục"
              aria-invalid={Boolean(problem)}
              aria-describedby={problem ? "source-problem" : undefined}
              placeholder={info?.dialogs ? "…hoặc dán đường dẫn" : "Dán đường dẫn thư mục hay file"}
              className={cn(
                "h-10 min-w-0 flex-1 rounded-lg border bg-bg px-3 text-sm outline-none placeholder:text-fg-3 focus:border-accent",
                problem ? "border-danger" : "border-line",
              )}
            />
            <Button type="submit" disabled={!cleanPath(typed) || scanning}>
              Lấy chương
            </Button>
          </form>
          {!info?.dialogs && <p className="mx-auto mt-1.5 max-w-lg break-all text-left text-xs text-fg-3">Ví dụ: D:\Truyện\Tên truyện</p>}
          {problem && (
            <div id="source-problem" role="alert" className="mx-auto mt-3 max-w-lg text-left text-sm text-danger">
              {problem.text}
              {problem.subfolders.length > 0 && (
                <div className="mt-2 space-y-1">
                  <div className="text-fg-2">Có lẽ nên chọn thư mục con:</div>
                  {problem.subfolders.length > 1 && (
                    // Light novel ra từng tập, mỗi tập một thư mục: chọn cả bộ một lần; bước sau ĐỀ XUẤT chia tập, người dùng bấm mới chia.
                    <button
                      type="button"
                      onClick={() => onPaths(problem.subfolders)}
                      className="flex w-full items-center gap-2 rounded-lg border border-accent/50 bg-panel px-3 py-2 text-left font-medium text-fg hover:border-accent"
                    >
                      <Layers className="size-4 shrink-0 text-accent-text" />
                      <span className="min-w-0">Dùng cả {problem.subfolders.length} thư mục - mỗi thư mục một tập</span>
                    </button>
                  )}
                  {problem.subfolders.slice(0, 8).map((folder) => (
                    <button
                      key={folder}
                      type="button"
                      title={folder}
                      onClick={() => onPaths([folder])}
                      className="flex w-full items-center gap-2 truncate rounded-lg border border-line bg-panel px-3 py-2 text-left text-fg hover:border-accent"
                    >
                      <Folder className="size-4 shrink-0 text-fg-2" />
                      {/* Tên thư mục đứng trước: hai thư mục "Tập 1", "Tập 2" cùng một đường dẫn dài thì đuôi bị cắt nhìn y hệt nhau. */}
                      <span className="shrink-0 font-medium">{folder.split(/[\\/]/).filter(Boolean).pop() ?? folder}</span>
                      <span className="min-w-0 truncate text-xs text-fg-3">{folder}</span>
                    </button>
                  ))}
                  {problem.subfolders.length > 8 && (
                    <div className="text-fg-2">…và {problem.subfolders.length - 8} thư mục nữa (đều nằm trong “Dùng cả” ở trên).</div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <>
          <label className="mt-6 block">
            <span className="text-sm font-medium">Tên sách</span>
            <input
              value={title}
              onChange={(event) => onTitle(event.target.value)}
              aria-invalid={!title.trim()}
              aria-describedby={!title.trim() ? "title-problem" : undefined}
              className={cn(
                "mt-1.5 h-11 w-full rounded-xl border bg-panel px-3.5 text-[15px] font-medium outline-none focus:border-accent",
                title.trim() ? "border-line" : "border-danger",
              )}
              placeholder="Tên hiển thị trong thư viện"
            />
            {!title.trim() && (
              <span id="title-problem" role="alert" className="mt-1 block text-[13px] text-danger">
                Sách cần có tên để hiện trong thư viện.
              </span>
            )}
          </label>
          {replaces && (
            <div className="mt-4 flex gap-3 rounded-xl border border-info/40 bg-info-soft p-4 text-sm">
              <Info className="mt-0.5 size-4 shrink-0 text-info" />
              <p className="min-w-0 text-pretty">
                {replaces.restart ? "Đang làm lại phân tích của " : "Đang sửa thiết lập của "}
                <span className="font-semibold">“{replaces.title}”</span>: mọi lựa chọn cũ đã điền sẵn, đổi gì cũng được. Tạo xong,
                bản cũ vào Thùng rác (bìa đi theo).
              </p>
            </div>
          )}
          {scan?.existing && scan.existing.some((project) => project.id !== replaces?.id) && (
            <div className="mt-4 flex gap-3 rounded-xl border border-info/40 bg-info-soft p-4 text-sm">
              <Info className="mt-0.5 size-4 shrink-0 text-info" />
              <div className="min-w-0">
                <p className="font-semibold">Truyện này đã có dự án</p>
                <ul className="mt-1 space-y-1">
                  {scan.existing.filter((project) => project.id !== replaces?.id).map((project) => (
                    <li key={project.id} className="flex flex-wrap items-baseline gap-x-2">
                      <span className="min-w-0 break-words">
                        “{project.title}” · {project.shared === project.chapters ? `cả ${project.chapters} chương` : `trùng ${project.shared}/${project.chapters} chương`} · {project.statusLabel}
                      </span>
                      <Link to={`/studio/${project.id}`} className="font-medium text-accent-text hover:underline">
                        Mở dự án
                      </Link>
                    </li>
                  ))}
                </ul>
                <p className="mt-1 text-fg-2">Vẫn tạo được dự án mới - ví dụ để thử một giọng kể khác.</p>
              </div>
            </div>
          )}
          {files.filter((file) => file.split).map((file) => (
            <SplitSuggestion key={file.path} file={file} onSplit={onSplit} />
          ))}
          {/* Gợi ý chia phần đứng TRƯỚC lời nhắc số chương: truyện nhiều tập đánh số lại từ 1 ở mỗi tập, lời nhắc "trùng số" chỉ là
              hệ quả của việc chưa chia. */}
          {volumeSplit}
          <ChapterNumberWarning
            issues={
              splitting && volumeStarts
                ? ranges(volumeStarts, files.length).flatMap((part, index) =>
                    chapterNumberIssues(files.slice(part.start - 1, part.end), index === 0 ? previousLast : undefined).map(
                      (issue) => `Phần ${index + 1}: ${issue}`,
                    ),
                  )
                : chapterNumberIssues(files, previousLast)
            }
            suggestsSplit={!splitting && Boolean(scan?.volumes)}
          />
          <CreditSuggestion credits={creditSummary(files)} accepted={dropCredits} onChange={onDropCredits} />
          <div className="mt-5 flex flex-wrap items-center justify-between gap-2">
            <div className="tabular text-sm text-fg-2">
              <span className="font-semibold text-fg">{files.length} chương</span> · {formatNumber(scan!.totals.words)} chữ · khoảng{" "}
              {formatLength(scan!.totals.audioSeconds)} audio
            </div>
            <div className="flex gap-1">
              {info?.dialogs && (
                <Button size="sm" variant="ghost" icon={FileText} onClick={() => void chooseFiles(true)}>
                  Thêm file
                </Button>
              )}
              <Button size="sm" variant="ghost" onClick={() => onPaths([])}>
                Chọn lại
              </Button>
            </div>
          </div>
          {/* Truyện dài (còn ra tiếp, hay làm từng đợt bằng "Làm tiếp cuốn này"): bỏ từng chương một thì không xuể - chọn
              nhanh làm N chương đầu, phần còn lại để đợt sau. */}
          {total > CHAPTER_LIMITS[0] && !splitting && (
            <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-fg-2">
              <span>Đợt này làm</span>
              <Segmented<string>
                label="Đợt này làm bao nhiêu chương"
                wrap
                value={limit ? String(limit) : "all"}
                onChange={(value) => onLimit(value === "all" ? null : Number(value))}
                options={[
                  ...CHAPTER_LIMITS.filter((count) => count < total).map((count) => ({ value: String(count), label: `${count} chương đầu` })),
                  { value: "all", label: `Cả ${formatNumber(total)} chương` },
                ]}
              />
              {limit !== null && later > 0 && <span>· còn {formatNumber(later)} chương cho đợt sau</span>}
            </div>
          )}
          <div className="mt-3 max-h-[340px] overflow-y-auto rounded-xl border border-line bg-panel">
            {files.map((file, index) => {
              // Chia phần: một vạch "Phần N bắt đầu" trước chương đầu mỗi phần - khỏi phải đối số chương với ô "từ chương" ở trên.
              const part = splitting && volumeStarts && volumeStarts.length > 1 ? volumeStarts.indexOf(index + 1) : -1;
              return (
                <Fragment key={file.path}>
                  {part >= 0 && (
                    <div className="flex items-center gap-2 border-b border-accent/30 bg-accent-soft px-3 py-1.5 text-xs font-semibold text-accent-text">
                      <Layers className="size-3.5 shrink-0" />
                      <span className="min-w-0 truncate">Phần {part + 1} bắt đầu</span>
                    </div>
                  )}
                  <div className="group grid grid-cols-[40px_minmax(0,1fr)_90px_36px] items-center gap-2 border-b border-line px-3 py-2 [contain-intrinsic-size:auto_48px] [content-visibility:auto] last:border-b-0">
                    <span className="tabular text-xs text-fg-2">{index + 1}</span>
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">{file.firstLine || file.title}</div>
                      <div className="truncate text-xs text-fg-2">{file.name}</div>
                    </div>
                    <div className="tabular text-right text-xs text-fg-2">
                      <div>{formatNumber(file.words)} chữ</div>
                      {file.chars > 0 && <div className="text-fg-3">{formatNumber(file.chars)} ký tự</div>}
                    </div>
                    <button
                      type="button"
                      aria-label={`Bỏ chương ${file.name}`}
                      title="Bỏ chương này"
                      onClick={() => onRemove(file.path)}
                      className="grid size-8 place-items-center rounded-md text-fg-2 opacity-0 hover:bg-hover hover:text-danger group-hover:opacity-100 focus-visible:opacity-100 max-md:opacity-100"
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </div>
                </Fragment>
              );
            })}
          </div>
          {scan!.skipped.length > 0 && <p className="mt-2 text-xs text-fg-2">Bỏ qua {scan!.skipped.length} file không phải .txt.</p>}
          {/* File sách hỏng / PDF scan nằm cạnh file tốt, thư mục có cả TXT lẫn EPUB, trang chỉ có ảnh bị bỏ, gợi ý dòng ghi công: không chặn, nhưng nói ra (soát UX 01-10: bị bỏ âm thầm). */}
          {[...(scan!.errors ?? []).map((error) => `Bỏ qua ${error}`), ...(scan!.notes ?? [])].map((line) => (
            <p key={line} className="mt-2 text-xs text-warning">
              {line}
            </p>
          ))}
        </>
      )}
    </div>
  );
}

/** "Chương 768" từ dòng đầu file ("Chương 768 - Mô hình…"), không thì tên file - cho dải chương ở bước xác nhận. */
function chapterLabel(file: ScannedFile): string {
  const head = file.firstLine.split(/\s[-–—:]\s|[:：]/)[0].trim();
  return head && head.length <= 40 ? head : file.name;
}

// ---- Nối tiếp phần trước ---------------------------------------------------------------------------------------

function carriedText(carries: Seed["carries"]): string {
  const parts = [
    carries.voices ? `giọng ${formatNumber(carries.voices)} nhân vật` : "",
    carries.pronunciations ? `${formatNumber(carries.pronunciations)} cách đọc tên` : "",
    carries.pins ? `giới / tuổi đã sửa tay của ${formatNumber(carries.pins)} nhân vật` : "",
    carries.aliases ? `${formatNumber(carries.aliases)} bí danh` : "",
    carries.names ? `${formatNumber(carries.names)} tên nhân vật đã đổi` : "",
    carries.bracket ? "quy ước lời trong 『』" : "",
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "những gì phần trước đã có";
}

interface Credits {
  lines: number;
  chapters: number;
  examples: string[];
}

/** Dòng ghi công người dịch ở đầu các chương ĐANG CHỌN (bỏ chương hay giới hạn số chương thì đếm lại). */
function creditSummary(files: ScannedFile[]): Credits {
  const examples: string[] = [];
  let lines = 0;
  let chapters = 0;
  for (const file of files) {
    const found = file.credits ?? [];
    if (!found.length) continue;
    lines += found.length;
    chapters += 1;
    for (const line of found) if (examples.length < 3 && !examples.includes(line)) examples.push(line);
  }
  return { lines, chapters, examples };
}

// Phát hiện được thì ĐỀ XUẤT, không tự làm (chủ sách 29-09: app không bao giờ tự sửa nội dung truyện). Dòng ghi công người
// dịch ở đầu chương ("TL : NicK", "*Edit: Lắc") bị đọc như một câu kể; chỉ khi bấm "Bỏ khỏi phần đọc" sách mới bỏ chúng,
// không bấm thì sách giữ nguyên như file truyện. Phải chọn lúc tạo sách: đổi cách tách câu sau khi đã làm là đổi cả quyển.
function CreditSuggestion({ credits, accepted, onChange }: { credits: Credits; accepted: boolean; onChange: (value: boolean) => void }) {
  if (!credits.lines) return null;
  const quoted = credits.examples.map((line) => `“${line}”`).join(", ");
  return (
    <div className="mt-4 flex gap-3 rounded-xl border border-line bg-panel p-4 text-sm">
      <Sparkles className="mt-0.5 size-4 shrink-0 text-accent-text" />
      <div className="min-w-0 flex-1">
        {accepted ? (
          <>
            <p className="font-semibold">Sẽ bỏ {formatNumber(credits.lines)} dòng ghi công khỏi phần đọc</p>
            <p className="mt-1 break-words text-fg-2">
              Những dòng như {quoted} không được đọc và không hiện khi đọc theo. File truyện giữ nguyên.
            </p>
          </>
        ) : (
          <>
            <p className="font-semibold">Gợi ý: {formatNumber(credits.chapters)} chương có dòng ghi công người dịch ở đầu chương</p>
            <p className="mt-1 break-words text-fg-2">
              {quoted}
              {credits.lines > credits.examples.length ? " và các dòng khác" : ""}. Hiện máy vẫn đọc chúng như lời kể - file truyện
              không bị sửa. Bỏ chúng khỏi phần đọc?
            </p>
          </>
        )}
        <div className="mt-2.5">
          {accepted ? (
            <Button size="sm" variant="ghost" onClick={() => onChange(false)}>
              Thôi, cứ đọc như file truyện
            </Button>
          ) : (
            <Button size="sm" variant="secondary" onClick={() => onChange(true)}>
              Bỏ khỏi phần đọc
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

// Soát UX a5 01-10: truyện tải trên mạng phần lớn là MỘT file TXT - trình tạo sách đọc ra một chương dài vài tiếng, không
// một lời nhắc. Thấy nhiều dòng "Chương N" trong một file thì ĐỀ XUẤT tách; không bấm thì giữ nguyên như file (chủ sách
// 29-09: không bao giờ tự sửa nguồn). Tách là ghi các chương ra một thư mục mới trong thư viện - file gốc không đổi.
function ChapterNumberWarning({ issues, suggestsSplit }: { issues: string[]; suggestsSplit?: boolean }) {
  if (!issues.length) return null;
  return (
    <div className="mt-4 flex gap-3 rounded-xl border border-warning/40 bg-warning-soft p-4 text-sm">
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
      <div className="min-w-0">
        <p className="font-semibold">Số chương có chỗ lạ - xem lại trước khi tạo</p>
        <ul className="mt-1 list-disc space-y-0.5 pl-4 text-fg-2">
          {issues.map((issue) => (
            <li key={issue} className="break-words">{issue}</li>
          ))}
        </ul>
        <p className="mt-1 text-fg-2">
          {suggestsSplit
            ? "Nếu đây là nhiều tập (mỗi tập đánh số chương lại từ 1) thì chia thành nhiều phần ở trên - mỗi phần được soát số chương riêng. "
            : ""}
          Vẫn tạo được như thế - máy chỉ nhắc, không bỏ file nào.
        </p>
      </div>
    </div>
  );
}

function SplitSuggestion({ file, onSplit }: { file: ScannedFile; onSplit: (path: string) => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const plan = file.split!;
  const quoted = plan.titles.map((title) => `“${title}”`).join(", ");
  return (
    <div className="mt-4 flex gap-3 rounded-xl border border-line bg-panel p-4 text-sm">
      <Sparkles className="mt-0.5 size-4 shrink-0 text-accent-text" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">Gợi ý: “{file.name}” có vẻ chứa cả {formatNumber(plan.chapters)} chương</p>
        <p className="mt-1 break-words text-fg-2">
          Máy thấy các tiêu đề {quoted}
          {plan.chapters > plan.titles.length + (plan.preamble ? 1 : 0) ? "…" : ""}. Hiện cả file được làm thành MỘT chương - một file
          audio dài, không chuyển chương được. Tách theo các tiêu đề ấy?
          {plan.preamble ? " Phần chữ trước tiêu đề đầu tiên thành chương “Mở đầu”." : ""} File gốc giữ nguyên.
        </p>
        <div className="mt-2.5">
          <Button
            size="sm"
            variant="secondary"
            icon={busy ? Loader2 : Scissors}
            disabled={busy}
            onClick={() => {
              setBusy(true);
              void onSplit(file.path).finally(() => setBusy(false));
            }}
          >
            Tách thành {formatNumber(plan.chapters)} chương
          </Button>
        </div>
      </div>
    </div>
  );
}

function SeedBanner({ seed, hasFiles, onDrop }: { seed: Seed; hasFiles: boolean; onDrop: () => void }) {
  return (
    // Điện thoại: nút bỏ nối tiếp xuống dưới đoạn chữ - đứng bên phải thì ép chữ thành cột ~180 px, dài 11 dòng (soát UX 29-09).
    <div className="mt-5 flex flex-wrap gap-3 rounded-xl border border-accent/30 bg-accent-soft p-4 text-sm sm:flex-nowrap">
      <Layers className="mt-0.5 size-4 shrink-0 text-accent-text" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">
          Phần {seed.part} của “{seed.title}”
        </p>
        {seed.clickedTitle && (
          <p className="mt-0.5 text-fg-2">
            Mở từ “{seed.clickedTitle}”, nhưng cuốn đã có tới “{seed.latestTitle ?? seed.title}” - phần mới nối sau phần ấy,
            không làm lại chương đã có.
          </p>
        )}
        <p className="mt-0.5 text-fg-2">
          Mang theo {carriedText(seed.carries)}: nhân vật đã gặp giữ nguyên giọng, tên đọc như phần trước.
        </p>
        {/* Khung "chưa có chương mới" tắt ngay khi đã chọn / thêm được file (soát UX a6 01-10, B5: vẫn hiện sau khi đã có). */}
        {seed.empty && !hasFiles && (
          <p className="mt-1 text-fg-2">
            {seed.folder ? (
              <>
                Thư mục <span className="break-all font-medium text-fg">{seed.folder}</span> chưa có file chương nào sau{" "}
                {seed.lastChapter || "chương cuối của phần trước"} - thêm file chương mới vào đó rồi mở lại “Làm tiếp”, hoặc
                chọn các file chương mới ở dưới.
              </>
            ) : (
              "Thư mục truyện chưa có chương nào sau chương cuối của phần trước - thêm file chương mới vào đó, hoặc chọn các file chương mới ở dưới."
            )}
          </p>
        )}
        {seed.analysisModelMissing && (
          <p className="mt-1 text-warning">
            Phần trước đọc bằng model “{modelLabel(seed.analysisModelMissing)}”, máy này lúc này không thấy model ấy - phần mới sẽ
            dùng model mặc định (đổi được ở bước Chất lượng). Đổi model giữa hai phần có thể làm vài người nói được gán khác đi.
          </p>
        )}
        {!seed.analyzed && (
          <p className="mt-1 text-warning">Phần trước chưa phân tích xong - chỉ mang được những gì đã có tới lúc này.</p>
        )}
      </div>
      <button
        type="button"
        onClick={onDrop}
        className="self-start whitespace-nowrap text-[13px] text-fg-2 underline-offset-2 hover:text-fg hover:underline max-sm:basis-full max-sm:pl-7 max-sm:text-left"
      >
        Bỏ nối tiếp
      </button>
    </div>
  );
}

// ---- Bước 2 ---------------------------------------------------------------------------------------------------

function VoiceCard({
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
        "relative flex items-center gap-3 rounded-xl border bg-panel p-3.5 transition-colors",
        selected ? "border-accent ring-1 ring-accent" : "border-line hover:border-line-strong",
      )}
    >
      <button
        type="button"
        tabIndex={-1}
        aria-label={playing ? `Dừng nghe ${voice.name}` : `Nghe thử giọng ${voice.name}`}
        onClick={() => clip.toggle(id, source.voiceUrl(voice.name))}
        // Trên lớp phủ bấm-để-chọn của thẻ (after:inset-0): nghe thử không đổi giọng đang chọn (soát UX a5 01-10).
        className={cn(
          "relative z-10 grid size-10 shrink-0 place-items-center rounded-full transition-colors",
          playing ? "bg-accent text-accent-ink" : "bg-hover text-fg hover:bg-line",
        )}
      >
        {playing ? <Vu className="h-3" /> : <Play className="size-4 translate-x-[1px]" fill="currentColor" strokeWidth={0} />}
      </button>
      <button
        type="button"
        role="radio"
        aria-checked={selected}
        tabIndex={focusable ? 0 : -1}
        data-voice={voice.name}
        onClick={onSelect}
        className="min-w-0 flex-1 text-left outline-none after:absolute after:inset-0 after:rounded-xl focus-visible:after:outline-2 focus-visible:after:outline-offset-2 focus-visible:after:outline-accent"
      >
        <span className="block font-semibold leading-snug">{voice.name}</span>
        <span className="mt-0.5 block text-xs text-fg-2">
          {voice.gender} · Miền {voice.region} · {voice.style}
        </span>
        {voice.recommended && (
          <span className="mt-1.5 inline-block rounded-md bg-accent-soft px-1.5 py-px text-[11px] font-semibold uppercase tracking-wide text-accent-text">
            Đề xuất
          </span>
        )}
      </button>
      {selected && (
        <span className="grid size-6 shrink-0 place-items-center rounded-full bg-accent text-accent-ink" aria-hidden>
          <Check className="size-3.5" strokeWidth={3} />
        </span>
      )}
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
      <legend className="sr-only">Chương đổi người kể</legend>
      <p className="text-sm font-semibold">Chương đổi người kể</p>
      <p className="mt-0.5 text-sm text-fg-2 text-pretty">
        Tên các chương này là tên một nhân vật và chương kể bằng “tôi” - thường là “tôi” của chính người ấy. Bỏ chọn nếu không
        phải.
      </p>
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
                  {chapter.title} - “tôi” là <b>{chapter.name}</b>
                </span>
              </label>
            </li>
          );
        })}
      </ul>
    </fieldset>
  );
}

function FirstPersonQuestion({ paths, seedFrom, value, onChange, povOff, setPovOff }: {
  paths: string[];
  seedFrom?: string;
  value: string;
  onChange: (name: string) => void;
  povOff: number[];
  setPovOff: (off: number[]) => void;
}) {
  const { data: hint, isLoading } = useFirstPersonHint(paths, seedFrom);
  const [opened, setOpened] = useState(false);
  if (!hint?.firstPerson && !value && !opened && !hint?.chapters?.length) {
    return (
      <button
        type="button"
        onClick={() => setOpened(true)}
        className="mt-3 text-sm font-medium text-accent-text underline underline-offset-2 disabled:opacity-60"
        disabled={isLoading}
      >
        Truyện kể ở ngôi thứ nhất (người kể xưng “tôi”)?
      </button>
    );
  }
  return (
    <section aria-labelledby="first-person-title" className="mt-5 max-w-2xl rounded-2xl border border-line bg-panel p-4 sm:p-5">
      <h3 id="first-person-title" className="font-semibold">“Tôi” là ai?</h3>
      <p className="mt-1 text-sm text-fg-2 text-pretty">
        {hint?.firstPerson
          ? hint.chaptersSampled && hint.chaptersWithI
            ? `Truyện có vẻ kể ở ngôi thứ nhất: ${hint.chaptersWithI}/${hint.chaptersSampled} chương đầu có nhiều lời kể xưng “tôi”. `
            : `Truyện có vẻ kể ở ngôi thứ nhất: ${Math.round(hint.rate * 100)}% đoạn lời kể có “tôi”. `
          : "Nếu người kể chuyện xưng “tôi”, cho biết đó là nhân vật nào. "}
        Biết tên người kể thì lời thoại của nhân vật chính được đọc bằng đúng giọng của họ - không thì dễ bị gán cho người
        đang nói chuyện với họ.
      </p>
      {Boolean(hint?.suggestions.length) && (
        <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="Gợi ý tên người kể">
          {hint!.suggestions.map((name) => (
            <button
              key={name}
              type="button"
              aria-pressed={value === name}
              onClick={() => onChange(value === name ? "" : name)}
              className={cn(
                "rounded-full border px-3 py-1.5 text-sm font-medium",
                value === name ? "border-accent bg-accent/10 text-accent-text" : "border-line text-fg hover:border-fg-3",
              )}
            >
              {name}
            </button>
          ))}
        </div>
      )}
      <label className="mt-3 block text-sm text-fg-2">
        Tên người kể
        <input
          id="first-person-name"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Tên nhân vật xưng “tôi” (để trống nếu kể ngôi thứ ba)"
          className="mt-1.5 h-11 w-full rounded-xl border border-line bg-panel px-3.5 text-[15px] font-medium text-fg outline-none focus:border-accent"
        />
      </label>
      <PovChapters hint={hint} narrator={value} off={povOff} onOffChange={setPovOff} />
    </section>
  );
}

function VoiceStep({
  narrator,
  setNarrator,
  paths,
  seedFrom,
  previousNarrator,
  firstPerson,
  setFirstPerson,
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
    <div>
      <h2 className="text-xl font-semibold">Chọn giọng kể chuyện</h2>
      <p className="mt-1 max-w-2xl text-sm text-fg-2 text-pretty">
        Giọng này đọc toàn bộ lời dẫn truyện. Mỗi nhân vật sẽ được tự động trao một giọng riêng sau bước phân tích - không cần
        chọn trước.
      </p>
      <FirstPersonQuestion
        paths={paths}
        seedFrom={seedFrom}
        value={firstPerson}
        onChange={setFirstPerson}
        povOff={povOff}
        setPovOff={setPovOff}
      />
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Segmented label="Giới tính" value={gender} onChange={setGender} options={[
          { value: "all", label: "Mọi giọng" },
          { value: "Nam", label: "Giọng nam" },
          { value: "Nữ", label: "Giọng nữ" },
        ]} />
        <Segmented label="Miền" value={region} onChange={setRegion} options={[
          { value: "all", label: "Mọi miền" },
          { value: "Bắc", label: "Miền Bắc" },
          { value: "Nam", label: "Miền Nam" },
          { value: "Trung", label: "Miền Trung" },
        ]} />
      </div>
      {previousNarrator && (
        <p className="mt-4 text-sm text-fg-2">
          Giọng kể phần trước: <span className="font-semibold text-fg">{previousNarrator}</span>
          {narrator && narrator !== previousNarrator && (
            <>
              {" - đang chọn giọng khác, hai phần sẽ đọc lời dẫn khác nhau. "}
              <button type="button" className="font-medium text-accent-text underline underline-offset-2" onClick={() => setNarrator(previousNarrator)}>
                Dùng lại {previousNarrator}
              </button>
            </>
          )}
        </p>
      )}
      {hiddenSelection && (
        <p className="mt-3 text-sm text-fg-2">
          Đang chọn: <span className="font-semibold text-fg">{narrator}</span> (bộ lọc đang ẩn giọng này).{" "}
          <button type="button" className="font-medium text-accent-text underline underline-offset-2" onClick={() => { setGender("all"); setRegion("all"); }}>
            Bỏ lọc
          </button>
        </p>
      )}
      <div ref={group} role="radiogroup" aria-label="Giọng kể chuyện" onKeyDown={onKeyDown} className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 2xl:grid-cols-3">
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
    </div>
  );
}

// ---- Bước 3 ---------------------------------------------------------------------------------------------------

function QualityStep({
  profile,
  setProfile,
  words,
  chapters,
  analysisModel,
  setAnalysisModel,
}: {
  profile: Profile;
  setProfile: (profile: Profile) => void;
  words: number;
  chapters: number;
  analysisModel: string;
  setAnalysisModel: (model: string) => void;
}) {
  const guess = estimate(words, chapters);
  return (
    <div>
      <h2 className="text-xl font-semibold">Chọn mức chất lượng</h2>
      <p className="mt-1 text-sm text-fg-2 text-pretty">
        Mức này đi cùng sách tới chương cuối, để mọi chương đọc giống nhau - không đổi được sau khi tạo.
      </p>
      <div
        role="radiogroup"
        aria-label="Chất lượng"
        onKeyDown={radioGroupKeys(PROFILE_VALUES, profile, setProfile)}
        className="mt-6 grid gap-4 lg:grid-cols-3"
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
                "relative flex flex-col rounded-2xl border bg-panel p-5 text-left transition-colors",
                selected ? "border-accent ring-1 ring-accent" : "border-line hover:border-line-strong",
              )}
            >
              {option.value === "high_quality" && (
                <span className="absolute -top-2.5 left-4 inline-flex items-center gap-1 rounded-full bg-accent px-2 py-0.5 text-[11px] font-semibold text-accent-ink">
                  <Sparkles className="size-3" /> Nên dùng
                </span>
              )}
              <div className="flex items-center justify-between">
                <span className="text-base font-semibold">{option.title}</span>
                {selected && (
                  <span className="grid size-6 place-items-center rounded-full bg-accent text-accent-ink">
                    <Check className="size-3.5" strokeWidth={3} />
                  </span>
                )}
              </div>
              <div className="mt-1 flex items-center gap-1.5 text-xs font-medium text-fg-2">
                <Gauge className="size-3.5" /> {option.pace}
              </div>
              <p className="mt-3 text-sm text-fg-2">{option.summary}</p>
              <ul className="mt-4 space-y-2 text-[13px]">
                {option.points.map((point) => (
                  <li key={point} className="flex gap-2">
                    <Check className="mt-0.5 size-3.5 shrink-0 text-success" strokeWidth={3} />
                    <span>{point}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-4 flex items-start gap-1.5 border-t border-line pt-3 text-[13px] text-fg-2">
                <Clock3 className="mt-0.5 size-3.5 shrink-0" />
                {option.value === "high_quality" ? (
                  <span>
                    Trên máy này: <span className="font-semibold text-fg">{lengthRange(guess.totalLow, guess.totalHigh)}</span> cho{" "}
                    {chapters} chương
                  </span>
                ) : (
                  <span>Nhanh hơn Chất lượng cao; chưa đo trên máy này.</span>
                )}
              </div>
            </button>
          );
        })}
      </div>
      <AnalysisModelPicker value={analysisModel} onChange={setAnalysisModel} />
    </div>
  );
}

// ---- Bước 4 ---------------------------------------------------------------------------------------------------

function ConfirmStep({
  title,
  scan,
  narrator,
  firstPerson,
  povChapters,
  profile,
  seed,
  volumes,
  startNow,
  setStartNow,
  precastWait,
  setPrecastWait,
  dropCredits,
  creditLines,
  analysisModel,
  restart,
  onReview,
}: {
  /** "Chia thành nhiều tập": các tập sẽ tạo (số chương mỗi tập), hay không có khi là một sách. */
  volumes?: { chapters: number }[];
  title: string;
  scan: ScanResult;
  narrator: string;
  firstPerson: string;
  povChapters: Record<string, string>;
  profile: Profile;
  seed?: Seed;
  startNow: boolean;
  setStartNow: (value: boolean) => void;
  precastWait: boolean;
  setPrecastWait: (value: boolean) => void;
  /** Người dùng đã đồng ý bỏ dòng ghi công khỏi phần đọc. */
  dropCredits: boolean;
  /** Số dòng ghi công người dịch phát hiện ở các chương đã chọn (gợi ý chưa áp nếu `dropCredits` tắt). */
  creditLines: number;
  analysisModel: string;
  /** "Làm lại phân tích": bản dở của cuốn này vào Thùng rác khi cuốn mới tạo xong. */
  restart?: { title: string };
  /** Quay lại bước đầu (chọn file, gợi ý dòng ghi công). */
  onReview: () => void;
}) {
  const models = useAnalysisModels().data;
  const option = PROFILES.find((item) => item.value === profile)!;
  const guess = estimate(scan.totals.words, scan.files.length);
  const measured = profile === "high_quality";
  const rows: [string, string][] = [
    ["Chương", `${scan.files.length} chương · ${formatNumber(scan.totals.words)} chữ`],
    // Tập 1 là sách thường, tập sau nối tiếp nó (continuation.py): nói rõ tên từng sách và việc "tự chạy khi tập trước xong".
    ...(volumes
      ? ([
          ["Chia thành", `${volumes.length} phần: ${volumeTitles(title, volumes.length).map((name, index) => `“${name}” (${formatNumber(volumes[index].chapters)} chương)`).join(", ")}`],
          ["Các phần sau", startNow ? "Xếp hàng sau phần trước, tự bắt đầu khi phần trước xong; mang giọng nhân vật và cách đọc tên từ phần trước" : "Bấm bắt đầu phần 1 thì các phần sau tự xếp hàng; mang giọng nhân vật và cách đọc tên từ phần trước"],
        ] as [string, string][])
      : []),
    ...(dropCredits
      ? ([["Dòng ghi công", `bỏ ${formatNumber(creditSummary(scan.files).lines)} dòng khỏi phần đọc`]] as [string, string][])
      : []),
    ["Độ dài audio", `khoảng ${formatLength(scan.totals.audioSeconds)}`],
    ["Giọng kể", narrator],
    ...(firstPerson ? ([["Người kể “tôi”", firstPerson]] as [string, string][]) : []),
    ...(Object.keys(povChapters).length
      ? ([["Chương đổi người kể", Object.entries(povChapters).map(([chapter, name]) => `chương ${chapter}: ${name}`).join(", ")]] as [string, string][])
      : []),
    // "Nối tiếp: phần 2 của …" đọc như nối SAU phần 2 hay LÀ phần 2 đều được - nói thẳng là phần mấy, sau phần nào, và dải
    // chương (soát UX 29-09).
    ...(seed
      ? ([[
          "Là",
          `phần ${seed.part} của “${seed.title}”, nối sau phần ${seed.part - 1}` +
            (scan.files.length ? ` · ${chapterLabel(scan.files[0])} → ${chapterLabel(scan.files[scan.files.length - 1])}` : ""),
        ]] as [string, string][])
      : []),
    ["Nhân vật", seed ? `Giữ ${carriedText(seed.carries)}; người mới được phân vai sau khi phân tích` : "Tự động phân vai sau khi phân tích"],
    ["Chất lượng", option.title],
    // Luôn nói model nào sẽ đọc hiểu truyện - cả khi là mặc định - vì phân tích là bước dài nhất và không ngắt được.
    ...(analysisModel
      ? ([["Model đọc hiểu", `${modelLabel(analysisModel)} (${seed?.analysisModel === analysisModel ? "như phần trước" : "chỉ cuốn này"})`]] as [string, string][])
      : models?.default
        ? ([["Model đọc hiểu", `${modelLabel(models.default)} (mặc định)`]] as [string, string][])
        : []),
    ...(measured
      ? ([
          ["Thời gian làm", lengthRange(guess.totalLow, guess.totalHigh)],
          ["Chương đầu nghe được sau", `khoảng ${formatLength(guess.firstChapter)}`],
        ] as [string, string][])
      : // "Nhanh" chưa có số đo trên máy này - vẫn nói được trần trên thay vì im lặng (soát UX a5 01-10).
        ([["Thời gian làm", `chưa đo cho chế độ này - ngắn hơn “Chất lượng cao” (dưới ${formatLength(guess.totalHigh)})`]] as [string, string][])),
  ];
  return (
    <div>
      <h2 className="text-xl font-semibold">Xem lại trước khi tạo</h2>
      <div className="mt-6 flex flex-col gap-6 rounded-2xl border border-line bg-panel p-6 sm:flex-row">
        <BookCover title={title} size="lg" className="w-40 max-sm:mx-auto" />
        <div className="min-w-0 flex-1">
          <h3 className="text-lg font-semibold text-balance">{title}</h3>
          <dl className="mt-3 divide-y divide-line text-sm">
            {rows.map(([label, value]) => (
              // Điện thoại: nhãn trên, giá trị dưới - cột nhãn 170 px cố định từng ép giá trị thành 5-6 dòng ở 390 px.
              <div key={label} className="grid gap-0.5 py-2 sm:grid-cols-[170px_minmax(0,1fr)] sm:gap-4">
                <dt className="text-fg-2">{label}</dt>
                <dd className="font-medium">{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
      <div className="mt-5 flex gap-3 rounded-xl border border-warning/40 bg-warning-soft p-4 text-sm">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
        <p className="text-pretty">
          <span className="font-semibold">Giai đoạn đầu là phân tích cả truyện</span>
          {measured ? ` (khoảng ${formatLength(guess.analysis)})` : " (truyện dài có thể mất nhiều giờ)"}: trong lúc đó đừng tắt máy, đừng cho máy ngủ và đừng bấm
          Dừng. Dừng giữa chừng rồi chạy tiếp sẽ ra cách phân vai khác với chạy liền một mạch - cần máy rảnh một lúc thì bấm{" "}
          <span className="font-semibold">Tạm dừng</span>, an toàn mọi lúc. Qua giai đoạn này thì dừng lúc nào cũng được.
        </p>
      </div>
      {restart && (
        <div className="mt-3 flex gap-3 rounded-xl border border-info/40 bg-info-soft p-4 text-sm">
          <Info className="mt-0.5 size-4 shrink-0 text-info" />
          <p className="text-pretty">
            Phân tích làm lại từ đầu, như một cuốn mới. Bản dở “{restart.title}” vào Thùng rác khi cuốn mới tạo xong (bìa đi
            theo); file truyện gốc không bị đụng.
          </p>
        </div>
      )}
      {creditLines > 0 && !dropCredits && (
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border border-line bg-panel p-4 text-sm">
          <Sparkles className="size-4 shrink-0 text-accent-text" />
          <p className="min-w-0 flex-1 text-pretty">
            Còn một gợi ý chưa áp: {formatNumber(creditLines)} dòng ghi công người dịch ở đầu chương sẽ vẫn được đọc như lời kể.
            Đổi sau khi đã phân tích là đổi cả quyển, nên chọn ngay bây giờ.
          </p>
          <Button variant="secondary" size="sm" onClick={onReview}>
            Xem gợi ý
          </Button>
        </div>
      )}
      <label className="mt-4 flex items-start gap-3 rounded-xl border border-line bg-panel p-4" htmlFor="start-now">
        <Switch id="start-now" checked={startNow} onCheckedChange={setStartNow} />
        <span>
          <span className="block text-sm font-medium">Bắt đầu tạo ngay</span>
          <span className="mt-0.5 block text-[13px] leading-relaxed text-fg-2">
            {startNow
              ? "Sách chạy nền: đóng cửa sổ vẫn tiếp tục, Windows báo khi xong. Chương nào xong là nghe được chương đó, không phải chờ cả cuốn."
              : "Sách được tạo nhưng chưa chạy - bấm “Bắt đầu tạo sách nói” ở trang dự án khi sẵn sàng (vd sửa trước cách đọc tên)."}
          </span>
        </span>
      </label>
      <label className="mt-3 flex items-start gap-3 rounded-xl border border-line bg-panel p-4" htmlFor="precast-wait">
        <Switch id="precast-wait" checked={precastWait} onCheckedChange={setPrecastWait} />
        <span>
          <span className="block text-sm font-medium">Chờ tôi duyệt trước khi thu</span>
          <span className="mt-0.5 block text-[13px] leading-relaxed text-fg-2">
            {precastWait
              ? "Phân tích xong, sách tạm dừng để bạn xem giọng, cách đọc tên và người nói - bấm “Thu âm” để thu tiếp."
              : "Phân tích xong thì thu luôn. Vẫn duyệt được bất cứ lúc nào; sửa ở chương chưa thu thì không phải thu lại."}
          </span>
        </span>
      </label>
    </div>
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
  const [draft, setDraft] = useState<Draft>(loadDraft);
  const [rawScan, setRawScan] = useState<ScanResult | null>(null);
  const [problem, setProblem] = useState<{ text: string; subfolders: string[] } | null>(null);
  const submitting = useRef(false);
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
  usePageTitle(draft.seed ? "Làm tiếp cuốn này" : draft.replaces ? `Sửa thiết lập · ${draft.replaces.title}` : undefined);

  // "Sửa thiết lập" (?redo=<id>): điền lại đúng lựa chọn lúc tạo của cuốn chưa bắt đầu, một lần, rồi bỏ tham số.
  useEffect(() => {
    if (!redoId || !redo) return;
    if (redo.started) {
      toast.error("Sách đã bắt đầu chạy", { description: "Không làm lại với thiết lập khác được nữa." });
      navigate(`/studio/${redoId}`, { replace: true });
      return;
    }
    setDraft({
      ...EMPTY_DRAFT,
      paths: redo.paths,
      title: redo.title,
      titleEdited: true,
      narrator: redo.narrator,
      firstPerson: redo.firstPerson,
      ...(redo.analysisModel ? { analysisModel: redo.analysisModel } : {}),
      profile: (PROFILE_VALUES as string[]).includes(redo.profile) ? (redo.profile as Profile) : "high_quality",
      dropCredits: redo.dropCreditLines,
      replaces: {
        id: redoId,
        title: redo.title,
        ...(redo.seedFrom ? { seedFrom: redo.seedFrom } : {}),
        ...(redo.analysisInterrupted ? { restart: true } : {}),
      },
    });
    // Làm lại phân tích: không có gì để chọn lại - thẳng bước Xác nhận (lựa chọn cũ đã điền sẵn, vẫn đổi được ở các bước trước).
    setParams(redo.analysisInterrupted ? { step: "3" } : {}, { replace: true });
  }, [redoId, redo, setParams, navigate]);
  useEffect(() => {
    if (redoError) toast.error("Không đọc được thiết lập của sách", { description: (redoError as Error).message });
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
    if (planError) toast.error("Không mở được phần trước", { description: planError.message });
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
    };
    setDraft((current) => (template ? applyTemplate(current, template, voices?.map((voice) => voice.name)) : { ...applyTemplate(current, fallback), template: undefined }));
  };

  // Quét lại chỉ khi danh sách nguồn đổi; bỏ một chương là lọc ngay ở đây, không đọc lại cả thư mục.
  useEffect(() => {
    if (!draft.paths.length) {
      setRawScan(null);
      setProblem(null);
      return;
    }
    scanMutation.mutate({ paths: draft.paths, seedFrom: draft.seed?.id }, {
      onSuccess: (result) => {
        setRawScan(result);
        if (!result.files.length) {
          setProblem(
            result.errors?.length
              ? { text: `Không mở được ${result.errors[0]}`, subfolders: [] }
              : result.missing.length
              ? { text: `Không tìm thấy “${result.missing[0]}”. Kiểm tra lại đường dẫn.`, subfolders: [] }
              : { text: "Thư mục này không có file .txt (hay .epub, .docx, .pdf) nằm ngay bên trong.", subfolders: result.subfolders },
          );
          return;
        }
        setProblem(null);
        setDraft((current) => (current.titleEdited || !result.suggestedTitle ? current : { ...current, title: result.suggestedTitle }));
      },
      onError: (error: Error) => setProblem({ text: `Không đọc được: ${error.message}`, subfolders: [] }),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft.paths.join("\n")]);

  // Chia nhiều tập: các chương theo thứ tự của đề xuất (mỗi thư mục / EPUB liền nhau - quét theo tên file thì chương các tập
  // xen nhau), và "N chương đầu" không áp (nó cắt một sách, không phải một bộ).
  const splitting = draft.volumeStarts != null;
  const ordered = useMemo(
    () => (rawScan ? (splitting ? inOrder(rawScan.files, rawScan.volumes?.order) : rawScan.files) : []),
    [rawScan, splitting],
  );
  const scan = useMemo<ScanResult | null>(() => {
    if (!rawScan) return null;
    const excluded = new Set(draft.excluded);
    const kept = ordered.filter((file) => !excluded.has(file.path));
    const files = draft.limit && !splitting ? kept.slice(0, draft.limit) : kept;
    const words = files.reduce((sum, file) => sum + file.words, 0);
    return { ...rawScan, files, totals: { chapters: files.length, words, audioSeconds: Math.round(words / 4.3) } };
  }, [rawScan, ordered, draft.excluded, draft.limit, splitting]);
  const volumeStarts = useMemo(
    () => (splitting && scan ? startNumbers(ordered, draft.volumeStarts, new Set(draft.excluded)) : [1]),
    [splitting, scan, ordered, draft.volumeStarts, draft.excluded],
  );

  // Cùng khoá truy vấn với bước "Tôi là ai?": lấy từ bộ nhớ đệm, không đọc lại sách.
  const { data: firstPersonHint } = useFirstPersonHint(scan?.files.map((file) => file.path) ?? [], draft.seed?.id);
  const povChapters = chosenPovChapters(firstPersonHint, draft.firstPerson, draft.povOff ?? []);

  const title = draft.title;
  const allowed = !scan?.files.length || !title.trim() ? 0 : !draft.narrator ? 1 : STEPS.length - 1;
  const requested = Number(params.get("step") ?? 0);
  const step = Number.isInteger(requested) ? Math.max(0, Math.min(requested, allowed)) : 0;
  useEffect(() => {
    document.querySelector("main")?.scrollTo({ top: 0 });
  }, [step]);
  // URL đòi bước chưa được phép (tên vừa bị xoá trống...): kéo URL về đúng bước đang hiện, để lúc điều kiện thoả
  // lại, trình tạo KHÔNG tự nhảy tới bước cũ trong URL.
  // Nhưng KHÔNG trong lúc nháp đang quét lại file (tải lại trang ở bước 4): lúc ấy chưa có chương nên mọi bước sau đều
  // "chưa được phép" - kéo URL về bước 1 thì quét xong người dùng mất chỗ (soát UX 29-09).
  const scanning = draft.paths.length > 0 && !rawScan;
  useEffect(() => {
    if (scanning) return;
    if (params.get("step") && requested !== step) setParams(step ? { step: String(step) } : {}, { replace: true });
  }, [params, requested, scanning, setParams, step]);

  // Bước nằm trong URL: nút Back của trình duyệt/chuột lùi đúng một bước.
  const go = (index: number) => {
    const target = Math.max(0, Math.min(index, allowed));
    setParams(target ? { step: String(target) } : {});
  };

  const submit = () => {
    if (!scan?.files.length || !title.trim() || submitting.current) {
      if (!title.trim()) go(0);
      return;
    }
    submitting.current = true;
    create.mutate(
      {
        paths: scan.files.map((file) => file.path),
        ...(volumeStarts.length > 1 ? { volumeStarts } : {}),
        title: title.trim(),
        profile: draft.profile,
        narrator: draft.narrator,
        firstPerson: draft.firstPerson.trim(),
        ...(Object.keys(povChapters).length ? { firstPersonChapters: povChapters } : {}),
        ...(draft.seed ? { seedFrom: draft.seed.id } : draft.replaces?.seedFrom ? { seedFrom: draft.replaces.seedFrom } : {}),
        ...(draft.replaces ? { replaces: draft.replaces.id } : {}),
        ...(draft.analysisModel ? { analysisModel: draft.analysisModel } : {}),
        // Chỉ khi người dùng đã đồng ý đề xuất - không gửi gì thì sách giữ nguyên nội dung.
        ...(draft.dropCredits && creditSummary(scan.files).lines ? { dropCreditLines: true } : {}),
        start: draft.startNow,
        ...(draft.precastWait ? { precastWait: true } : {}),
      },
      {
        onSuccess: (result) => {
          saveDraft(null);
          const shared = result.sharedReadings ?? [];
          const readings = shared.length
            ? `Dùng ${shared.length} cách đọc chung (${shared.slice(0, 3).join(", ")}${shared.length > 3 ? ", …" : ""}).`
            : "";
          const starting = !draft.startNow
            ? ""
            : result.queued
              ? `Đang có cuốn khác chạy - sách này vào hàng chờ (thứ ${result.queued}), tự bắt đầu khi cuốn ấy xong.`
              : "Đang khởi động - theo dõi tiến trình ngay trên trang sách.";
          const volumes = result.parts?.length ?? 0;
          toast.success(
            result.unchanged
              ? "Không có thiết lập nào thay đổi"
              : volumes > 1
                ? `Đã tạo ${volumes} phần`
                : draft.replaces?.restart
                  ? "Đã làm lại sách từ đầu"
                  : draft.replaces
                    ? "Đã tạo lại sách với thiết lập mới"
                    : "Đã tạo sách",
            {
              description:
                [
                  result.unchanged ? "Giữ nguyên sách cũ." : "",
                  starting,
                  volumes > 1 && draft.startNow ? "Phần sau tự bắt đầu khi phần trước xong, mang giọng và cách đọc tên sang." : "",
                  volumes > 1 && !draft.startNow ? "Bấm bắt đầu phần 1 thì các phần sau tự xếp hàng; mỗi phần chạy được khi phần trước đã phân tích xong." : "",
                  readings,
                  draft.replaces && !result.unchanged && !result.replaceError ? "Bản cũ đã vào Thùng rác." : "",
                ]
                  .filter(Boolean)
                  .join(" ") || undefined,
            },
          );
          if (result.replaceError) toast.warning("Bản cũ vẫn còn trong Dự án", { description: result.replaceError });
          navigate(`/studio/${result.id}`, { replace: true });
        },
        onError: (error: Error) => toast.error("Không tạo được sách", { description: error.message }),
        onSettled: () => {
          submitting.current = false;
        },
      },
    );
  };

  return (
    <div className="mx-auto max-w-[1180px] px-4 pb-16 pt-6 sm:px-10 sm:pt-9">
      <button type="button" onClick={() => navigate("/studio")} className="inline-flex items-center gap-1.5 text-sm text-fg-2 hover:text-fg">
        <ArrowLeft className="size-4" /> Studio
      </button>
      <h1 className="mt-4 text-2xl font-bold tracking-tight sm:text-[28px]">{draft.seed ? "Làm tiếp cuốn này" : "Tạo sách nói"}</h1>
      {draft.seed && (
        <SeedBanner
          seed={draft.seed}
          hasFiles={(rawScan?.files.length ?? 0) > 0}
          onDrop={() => {
            // Bỏ nối tiếp = phân vai lại từ đầu, giọng lệch phần trước: một cú bấm lỡ tay phải lấy lại được (soát UX 29-09).
            const previous = draft.seed;
            update({ seed: undefined });
            toast("Đã bỏ nối tiếp", {
              description: "Sách này sẽ phân vai lại từ đầu - nhân vật có thể mang giọng khác phần trước.",
              duration: 10000,
              action: { label: "Hoàn tác", onClick: () => update({ seed: previous }) },
            });
          }}
        />
      )}
      <div className="mt-6 flex flex-col gap-8 lg:flex-row lg:gap-10">
        <aside className="shrink-0 lg:w-56">
          <StepRail step={step} allowed={allowed} onGo={go} />
          {(draft.paths.length > 0 || draft.title) && (
            <button
              type="button"
              onClick={() => {
                saveDraft(null);
                setDraft(EMPTY_DRAFT);
                setRawScan(null);
                go(0);
              }}
              className="mt-4 px-2.5 text-[13px] text-fg-2 hover:text-fg"
            >
              Bắt đầu lại từ đầu
            </button>
          )}
        </aside>
        <section className="min-w-0 flex-1">
          {/* Mẫu thiết lập chỉ cho sách mới: "Làm tiếp cuốn này" theo phần trước. */}
          {step > 0 && !draft.seed && <TemplateBar draft={draft} onPick={pickTemplate} />}
          {step === 0 && (
            <SourceStep
              scan={scan}
              title={title}
              onTitle={(value) => update({ title: value, titleEdited: true })}
              scanning={scanMutation.isPending}
              onPaths={(paths) => update({ paths, excluded: [], limit: null, volumeStarts: null, titleEdited: paths.length ? draft.titleEdited : false })}
              onAddFiles={(paths) => update({ paths: [...draft.paths, ...paths], volumeStarts: null })}
              splitting={splitting}
              volumeStarts={volumeStarts}
              volumeSplit={
                <VolumeSplit
                  ordered={ordered}
                  excluded={draft.excluded}
                  files={scan?.files ?? []}
                  proposal={rawScan?.volumes}
                  title={title.trim()}
                  value={draft.volumeStarts ?? null}
                  onChange={(volumeStarts) => update({ volumeStarts })}
                />
              }
              total={rawScan?.files.length ?? 0}
              limit={draft.limit ?? null}
              later={(rawScan?.files.filter((file) => !draft.excluded.includes(file.path)).length ?? 0) - (scan?.files.length ?? 0)}
              onLimit={(count) => update({ limit: count })}
              onRemove={(path) => {
                update({ excluded: [...draft.excluded, path] });
                const name = path.split(/[\\/]/).pop();
                toast(`Đã bỏ ${name}`, {
                  id: `removed-${path}`,
                  action: {
                    label: "Hoàn tác",
                    onClick: () => setDraft((current) => ({ ...current, excluded: current.excluded.filter((item) => item !== path) })),
                  },
                });
              }}
              problem={problem}
              dropCredits={Boolean(draft.dropCredits)}
              onDropCredits={(value) => update({ dropCredits: value })}
              previousLast={draft.seed?.lastChapter}
              replaces={draft.replaces}
              onSplit={async (path) => {
                try {
                  const { folder } = await api<{ folder: string }>("/api/sources/split", { method: "POST", body: { path } });
                  // File đã chọn thẳng: thư mục chương thay chỗ nó. File nằm trong một thư mục đã chọn: thêm thư mục chương,
                  // bỏ file cả truyện khỏi danh sách (vẫn hoàn tác được như mọi chương bỏ tay).
                  // Đường người dùng gõ ("D:/Truyện/a.txt") khác dạng đường máy quét ("D:\Truyện\a.txt"): so bằng samePath.
                  const replaced = draft.paths.some((item) => samePath(item, path));
                  update(
                    replaced
                      ? { paths: draft.paths.map((item) => (samePath(item, path) ? folder : item)), excluded: [], limit: null, volumeStarts: null }
                      : { paths: [...draft.paths, folder], excluded: [...draft.excluded, path], limit: null, volumeStarts: null },
                  );
                  const chapters = scan?.files.find((file) => samePath(file.path, path))?.split?.chapters;
                  toast.success(chapters ? `Đã tách thành ${formatNumber(chapters)} chương` : "Đã tách thành các chương", {
                    description: "File gốc vẫn giữ nguyên.",
                  });
                } catch (error) {
                  toast.error("Không tách được", { description: (error as Error).message });
                }
              }}
            />
          )}
          {step === 1 && (
            <VoiceStep
              narrator={draft.narrator}
              setNarrator={(narrator) => update({ narrator })}
              paths={scan?.files.map((file) => file.path) ?? []}
              seedFrom={draft.seed?.id}
              previousNarrator={draft.seed?.narrator}
              firstPerson={draft.firstPerson}
              setFirstPerson={(firstPerson) => update({ firstPerson })}
              povOff={draft.povOff ?? []}
              setPovOff={(povOff) => update({ povOff })}
            />
          )}
          {step === 2 && scan && (
            <QualityStep profile={draft.profile} setProfile={(profile) => update({ profile })} words={scan.totals.words} chapters={scan.files.length}
              analysisModel={draft.analysisModel ?? ""} setAnalysisModel={(analysisModel) => update({ analysisModel })} />
          )}
          {step === 3 && scan && (
            <ConfirmStep
              title={title.trim()}
              scan={scan}
              narrator={draft.narrator}
              firstPerson={draft.firstPerson.trim()}
              povChapters={povChapters}
              profile={draft.profile}
              seed={draft.seed}
              volumes={volumeStarts.length > 1 ? ranges(volumeStarts, scan.files.length) : undefined}
              startNow={draft.startNow}
              setStartNow={(startNow) => update({ startNow })}
              precastWait={Boolean(draft.precastWait)}
              setPrecastWait={(precastWait) => update({ precastWait })}
              dropCredits={Boolean(draft.dropCredits)}
              creditLines={creditSummary(scan.files).lines}
              analysisModel={draft.analysisModel ?? ""}
              restart={draft.replaces?.restart ? { title: draft.replaces.title } : undefined}
              onReview={() => go(0)}
            />
          )}
          {/* Ghim ở đáy vùng cuộn: bước xác nhận dài (thêm dòng "Dòng ghi công"...) đẩy nút tạo xuống dưới nếp màn hình - soát
              UX 29-09. */}
          <div className="sticky bottom-0 z-10 mt-8 flex items-center justify-between border-t border-line bg-bg py-4">
            <Button variant="ghost" icon={ArrowLeft} disabled={step === 0} onClick={() => go(step - 1)}>
              Quay lại
            </Button>
            {step < STEPS.length - 1 ? (
              <Button variant="primary" disabled={step >= allowed} onClick={() => go(step + 1)}>
                Tiếp tục <ArrowRight className="size-4" />
              </Button>
            ) : (
              <Button variant="primary" icon={draft.startNow ? Wand2 : Mic} loading={create.isPending} disabled={!title.trim()} onClick={submit}>
                {draft.startNow ? "Tạo và bắt đầu" : "Tạo sách"}
              </Button>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

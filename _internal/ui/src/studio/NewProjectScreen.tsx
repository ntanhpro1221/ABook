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
  Sparkles,
  Trash2,
  Upload,
  Wand2,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
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
  useAppInfo,
  useContinuation,
  useCreateBook,
  useFirstPersonHint,
  useScan,
  useVoices,
} from "@/studio/data";
import { uploadChapters } from "@/studio/upload";

type Profile = "fast" | "balanced" | "high_quality";

const STEPS = [
  { title: "Nội dung", hint: "Các chương TXT" },
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
  /** "Làm tiếp cuốn này": phần trước để gieo từ (continuation.py), hay không có khi là sách mới. */
  seed?: Seed;
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
}

const DRAFT_KEY = "ebook-reader-new-book-draft";
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
  onLimit,
  problem,
}: {
  scan: ScanResult | null;
  title: string;
  onTitle: (title: string) => void;
  scanning: boolean;
  onPaths: (paths: string[]) => void;
  onAddFiles: (paths: string[]) => void;
  onRemove: (path: string) => void;
  /** Số chương đọc được trong nguồn, trước khi bỏ chương nào. */
  total: number;
  /** Chỉ làm `count` chương đầu (theo thứ tự tên file), hay tất cả khi null. */
  onLimit: (count: number | null) => void;
  problem: { text: string; subfolders: string[] } | null;
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
    const chosen = await pickFiles("Chọn các chương TXT").catch((error: Error) => {
      toast.error(error.message);
      return [];
    });
    if (chosen.length) (append ? onAddFiles : onPaths)(chosen);
  };
  const files = scan?.files ?? [];
  return (
    <div>
      <h2 className="text-xl font-semibold">Chọn các chương của truyện</h2>
      <p className="mt-1 text-sm text-fg-2 text-pretty">
        Mỗi file TXT là một chương. Chương được xếp theo tên file như người đọc mong đợi: 2 đứng trước 10.
      </p>
      {!files.length ? (
        <div className="mt-6 rounded-2xl border-2 border-dashed border-line-strong bg-panel px-8 py-10 text-center">
          <div className="mx-auto grid size-14 place-items-center rounded-2xl bg-accent-soft text-accent-text">
            {scanning ? <Loader2 className="size-7 animate-spin" /> : <FolderInput className="size-7" strokeWidth={1.75} />}
          </div>
          <p className="mt-4 font-medium">
            {scanning ? "Đang đọc các chương…" : info?.remote ? "Gửi các chương từ máy này" : "Chọn thư mục chứa truyện"}
          </p>
          <p className="mt-1 text-sm text-fg-2">
            {info?.remote
              ? "Chọn cùng lúc mọi file .txt của truyện. Máy tính giữ chúng trong thư viện, mục “Nguồn tải lên”."
              : "Chỉ lấy file .txt nằm ngay trong thư mục, không quét thư mục con."}
          </p>
          {info?.remote && (
            <div className="mt-6 flex justify-center">
              <input
                ref={uploadInput}
                type="file"
                multiple
                accept=".txt,text/plain"
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
              placeholder={info?.dialogs ? "…hoặc dán đường dẫn thư mục" : "Dán đường dẫn thư mục, ví dụ D:\\Truyện\\Tên truyện"}
              className={cn(
                "h-10 flex-1 rounded-lg border bg-bg px-3 text-sm outline-none placeholder:text-fg-3 focus:border-accent",
                problem ? "border-danger" : "border-line",
              )}
            />
            <Button type="submit" disabled={!cleanPath(typed) || scanning}>
              Mở
            </Button>
          </form>
          {problem && (
            <div id="source-problem" role="alert" className="mx-auto mt-3 max-w-lg text-left text-sm text-danger">
              {problem.text}
              {problem.subfolders.length > 0 && (
                <div className="mt-2 space-y-1">
                  <div className="text-fg-2">Có lẽ nên chọn thư mục con:</div>
                  {problem.subfolders.map((folder) => (
                    <button
                      key={folder}
                      type="button"
                      onClick={() => onPaths([folder])}
                      className="flex w-full items-center gap-2 truncate rounded-lg border border-line bg-panel px-3 py-2 text-left text-fg hover:border-accent"
                    >
                      <Folder className="size-4 shrink-0 text-fg-2" />
                      <span className="truncate">{folder}</span>
                    </button>
                  ))}
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
          {scan?.existing && scan.existing.length > 0 && (
            <div className="mt-4 flex gap-3 rounded-xl border border-info/40 bg-info-soft p-4 text-sm">
              <Info className="mt-0.5 size-4 shrink-0 text-info" />
              <div className="min-w-0">
                <p className="font-semibold">Truyện này đã có dự án</p>
                <ul className="mt-1 space-y-1">
                  {scan.existing.map((project) => (
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
          {total > CHAPTER_LIMITS[0] && (
            <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-fg-2">
              <span>Đợt này làm</span>
              <Segmented<string>
                label="Đợt này làm bao nhiêu chương"
                wrap
                value={files.length === total ? "all" : String(files.length)}
                onChange={(value) => onLimit(value === "all" ? null : Number(value))}
                options={[
                  ...CHAPTER_LIMITS.filter((count) => count < total).map((count) => ({ value: String(count), label: `${count} chương đầu` })),
                  { value: "all", label: `Cả ${formatNumber(total)} chương` },
                ]}
              />
            </div>
          )}
          <div className="mt-3 max-h-[340px] overflow-y-auto rounded-xl border border-line bg-panel">
            {files.map((file, index) => (
              <div
                key={file.path}
                className="group grid grid-cols-[40px_minmax(0,1fr)_90px_36px] items-center gap-2 border-b border-line px-3 py-2 [contain-intrinsic-size:auto_48px] [content-visibility:auto] last:border-b-0"
              >
                <span className="tabular text-xs text-fg-2">{index + 1}</span>
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">{file.firstLine || file.title}</div>
                  <div className="truncate text-xs text-fg-2">{file.name}</div>
                </div>
                <span className="tabular text-right text-xs text-fg-2">{formatNumber(file.words)} chữ</span>
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
            ))}
          </div>
          {scan!.skipped.length > 0 && <p className="mt-2 text-xs text-fg-2">Bỏ qua {scan!.skipped.length} file không phải .txt.</p>}
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
    carries.pins ? `${formatNumber(carries.pins)} ghim giới/tuổi` : "",
    carries.aliases ? `${formatNumber(carries.aliases)} bí danh` : "",
    carries.bracket ? "quy ước lời trong 『』" : "",
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "những gì phần trước đã có";
}

function SeedBanner({ seed, onDrop }: { seed: Seed; onDrop: () => void }) {
  return (
    // Điện thoại: nút bỏ nối tiếp xuống dưới đoạn chữ - đứng bên phải thì ép chữ thành cột ~180 px, dài 11 dòng (soát UX 29-09).
    <div className="mt-5 flex flex-wrap gap-3 rounded-xl border border-accent/30 bg-accent-soft p-4 text-sm sm:flex-nowrap">
      <Layers className="mt-0.5 size-4 shrink-0 text-accent-text" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">
          Phần {seed.part} của “{seed.title}”
        </p>
        <p className="mt-0.5 text-fg-2">
          Mang theo {carriedText(seed.carries)}: nhân vật đã gặp giữ nguyên giọng, tên đọc như phần trước.
        </p>
        {seed.empty && (
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
        {!seed.analyzed && (
          <p className="mt-1 text-warning">Phần trước chưa phân tích xong - chỉ mang được những gì đã có tới lúc này.</p>
        )}
      </div>
      <button
        type="button"
        onClick={onDrop}
        className="self-start whitespace-nowrap text-[13px] text-fg-2 underline-offset-2 hover:text-fg hover:underline max-sm:basis-full max-sm:pl-7 max-sm:text-left"
      >
        Bỏ nối tiếp…
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
        className={cn(
          "grid size-10 shrink-0 place-items-center rounded-full transition-colors",
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

function QualityStep({ profile, setProfile, words, chapters }: { profile: Profile; setProfile: (profile: Profile) => void; words: number; chapters: number }) {
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
  startNow,
  setStartNow,
}: {
  title: string;
  scan: ScanResult;
  narrator: string;
  firstPerson: string;
  povChapters: Record<string, string>;
  profile: Profile;
  seed?: Seed;
  startNow: boolean;
  setStartNow: (value: boolean) => void;
}) {
  const option = PROFILES.find((item) => item.value === profile)!;
  const guess = estimate(scan.totals.words, scan.files.length);
  const measured = profile === "high_quality";
  const rows: [string, string][] = [
    ["Chương", `${scan.files.length} chương · ${formatNumber(scan.totals.words)} chữ`],
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
    ...(measured
      ? ([
          ["Thời gian làm", lengthRange(guess.totalLow, guess.totalHigh)],
          ["Chương đầu nghe được sau", `khoảng ${formatLength(guess.firstChapter)}`],
        ] as [string, string][])
      : []),
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
          {measured ? ` (khoảng ${formatLength(guess.analysis)})` : ""}: trong lúc đó đừng tắt máy, đừng cho máy ngủ và đừng bấm
          Dừng. Dừng giữa chừng rồi chạy tiếp sẽ ra cách phân vai khác với chạy liền một mạch. Qua giai đoạn này thì dừng lúc nào
          cũng được.
        </p>
      </div>
      <label className="mt-4 flex items-start gap-3 rounded-xl border border-line bg-panel p-4" htmlFor="start-now">
        <Switch id="start-now" checked={startNow} onCheckedChange={setStartNow} />
        <span>
          <span className="block text-sm font-medium">Bắt đầu tạo ngay</span>
          <span className="mt-0.5 block text-[13px] leading-relaxed text-fg-2">
            Sách chạy nền: đóng cửa sổ vẫn tiếp tục, Windows báo khi xong. Chương nào xong là nghe được chương đó, không phải chờ
            cả cuốn.
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
  const scanMutation = useScan();
  const create = useCreateBook();
  const { data: voices } = useVoices();
  const [draft, setDraft] = useState<Draft>(loadDraft);
  const [rawScan, setRawScan] = useState<ScanResult | null>(null);
  const [problem, setProblem] = useState<{ text: string; subfolders: string[] } | null>(null);
  const submitting = useRef(false);
  const update = (changes: Partial<Draft>) => setDraft((current) => ({ ...current, ...changes }));

  useEffect(() => saveDraft(draft), [draft]);
  usePageTitle(draft.seed ? "Làm tiếp cuốn này" : undefined);

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
      profile: (PROFILE_VALUES as string[]).includes(plan.profile) ? (plan.profile as Profile) : "high_quality",
      seed: {
        id: plan.sourceId || continueId,
        title: plan.sourceTitle,
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
    if (!draft.narrator && voices?.length) update({ narrator: voices.find((voice) => voice.recommended)?.name ?? voices[0].name });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voices, draft.narrator]);

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
            result.missing.length
              ? { text: `Không tìm thấy thư mục “${result.missing[0]}”. Kiểm tra lại đường dẫn.`, subfolders: [] }
              : { text: "Thư mục này không có file .txt nằm ngay bên trong.", subfolders: result.subfolders },
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

  const scan = useMemo<ScanResult | null>(() => {
    if (!rawScan) return null;
    const excluded = new Set(draft.excluded);
    const files = rawScan.files.filter((file) => !excluded.has(file.path));
    const words = files.reduce((sum, file) => sum + file.words, 0);
    return { ...rawScan, files, totals: { chapters: files.length, words, audioSeconds: Math.round(words / 4.3) } };
  }, [rawScan, draft.excluded]);

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
  useEffect(() => {
    if (params.get("step") && requested !== step) setParams(step ? { step: String(step) } : {}, { replace: true });
  }, [params, requested, setParams, step]);

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
        title: title.trim(),
        profile: draft.profile,
        narrator: draft.narrator,
        firstPerson: draft.firstPerson.trim(),
        ...(Object.keys(povChapters).length ? { firstPersonChapters: povChapters } : {}),
        ...(draft.seed ? { seedFrom: draft.seed.id } : {}),
        start: draft.startNow,
      },
      {
        onSuccess: (result) => {
          saveDraft(null);
          toast.success("Đã tạo sách", { description: draft.startNow ? "Đang khởi động - theo dõi tiến trình ngay trên trang sách." : undefined });
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
          {step === 0 && (
            <SourceStep
              scan={scan}
              title={title}
              onTitle={(value) => update({ title: value, titleEdited: true })}
              scanning={scanMutation.isPending}
              onPaths={(paths) => update({ paths, excluded: [], titleEdited: paths.length ? draft.titleEdited : false })}
              onAddFiles={(paths) => update({ paths: [...draft.paths, ...paths] })}
              total={rawScan?.files.length ?? 0}
              onLimit={(count) =>
                update({ excluded: count === null ? [] : (rawScan?.files ?? []).slice(count).map((file) => file.path) })
              }
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
            <QualityStep profile={draft.profile} setProfile={(profile) => update({ profile })} words={scan.totals.words} chapters={scan.files.length} />
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
              startNow={draft.startNow}
              setStartNow={(startNow) => update({ startNow })}
            />
          )}
          <div className="mt-8 flex items-center justify-between border-t border-line pt-5">
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

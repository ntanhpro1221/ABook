import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { FileDown, ImagePlus, Loader2, Music2, Pencil, Shuffle, Trash2, Volume2, VolumeX, Wrench } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { BookCover } from "@/shared/BookCover";
import { cn } from "@/shared/cn";
import { canEditLayer, editBlockedNote, studioNeed, syncsToComputer } from "@/shared/capabilities";
import { formatClock } from "@/shared/format";
import { levelOptions } from "@/shared/musicLevels";
import { Button, Dialog, Segmented } from "@/shared/ui";
import { api } from "@/studio/api";
import { MUSIC_CHANGED_EVENT } from "./musicBed";
import { MyMusicSection, SwapTrack } from "./MyMusic";
import type { ListenBook, ListenChapter } from "./model";
import { useSource } from "./source";

// Sửa sách "áp ngay" ngay trên trang nghe (docs/EDITING.md): tên sách, bìa, tên nhân vật, tên chương, nhạc nền. Cùng một bộ
// màn hình cho máy tính và điện thoại - lệnh đi tới `/api/books/<mã>/...`; máy tính là server Python, điện thoại là lõi native
// (android/localStudio.ts) trả cùng JSON. Cuốn có xưởng (dự án) ghi vào các file riêng của dự án, cuốn nhập từ file ghi vào
// lớp sửa cạnh sách - người dùng không phải biết khác biệt ấy.

const MENU_ITEM = "flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[highlighted]:bg-hover";

/** Làm mới mọi chỗ hiện thứ vừa sửa: thư viện, trang sách, dàn nhân vật, chữ đọc theo, và trình phát nạp lại mốc nhạc. */
export function refreshAfterEdit(client: QueryClient, bookId: string): void {
  void client.invalidateQueries({ queryKey: ["listen"] });
  void client.invalidateQueries({ queryKey: ["library"] });
  void client.invalidateQueries({ queryKey: ["book", bookId] });
  void client.invalidateQueries({ queryKey: ["cast", bookId] });
}

/** Cuốn này sửa được ngay trên trang nghe không (cuốn của máy này, có xưởng hay không). */
export function canEditBook(book: Pick<ListenBook, "capabilities"> | undefined): boolean {
  return canEditLayer(book?.capabilities);
}

const MAX_SIDE = 1600;

/** Ảnh bìa người dùng chọn -> data URL JPEG đã thu nhỏ (cạnh dài <= 1600): ảnh chụp 12 MB không phải đi qua cầu nối của
 *  điện thoại. Máy chủ / lõi native vẫn chuẩn hoá lại; không thu nhỏ được (trình duyệt lạ) thì gửi nguyên ảnh. */
async function imageToDataUrl(file: Blob): Promise<string> {
  const raw = () =>
    new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(reader.error ?? new Error("Không đọc được file ảnh"));
      reader.readAsDataURL(file);
    });
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    if (scale === 1 && file.type === "image/jpeg") return await raw();
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const context = canvas.getContext("2d");
    if (!context) return await raw();
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    return canvas.toDataURL("image/jpeg", 0.9);
  } catch {
    return raw();
  }
}

interface MusicEditView {
  hasMusic: boolean;
  enabled: boolean;
  levelDb: number;
  defaultLevelDb: number;
  cues: {
    key: string;
    chapterId: number;
    chapter: string;
    start: number;
    end: number;
    title: string;
    creator: string;
    silenced: boolean;
    /** Người nghe đã đổi đoạn này sang một bài trong "Nhạc của tôi". */
    pinned?: boolean;
  }[];
}

/** Nhạc nền của cuốn nhập từ file: người làm sách đã gắn sẵn - người nghe bật/tắt, chỉnh mức, cho im lặng từng đoạn, và đổi một đoạn
 *  sang bài trong "Nhạc của tôi" (bài ấy đi cùng file sách khi lưu). */
function MusicSection({ book }: { book: ListenBook }) {
  const client = useQueryClient();
  const key = ["listen", "edit-music", book.id];
  const [swapping, setSwapping] = useState<string | null>(null); // khoá đoạn đang mở "Đổi bài"
  const { data, isLoading } = useQuery({ queryKey: key, queryFn: () => api<MusicEditView>(`/api/books/${book.id}/music`) });
  const change = useMutation({
    mutationFn: (body: { enabled?: boolean; levelDb?: number; silence?: Record<string, boolean>; pins?: Record<string, string | null> }) =>
      api<MusicEditView>(`/api/books/${book.id}/music`, { method: "PUT", body }),
    onSuccess: (view) => {
      client.setQueryData(key, view);
      setSwapping(null);
      refreshAfterEdit(client, book.id);
      window.dispatchEvent(new CustomEvent(MUSIC_CHANGED_EVENT, { detail: book.id }));
    },
    onError: (error: Error) => toast.error("Chưa chỉnh được nhạc nền", { description: error.message }),
  });
  if (isLoading || !data) return <p className="text-sm text-fg-2">Đang đọc nhạc nền…</p>;
  if (!data.hasMusic) {
    return <p className="text-sm text-fg-2">Người làm sách không gắn nhạc nền cho cuốn này.</p>;
  }
  const choosing = change.isPending ? (Object.values(change.variables?.pins ?? {}).find((link): link is string => !!link) ?? null) : null;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <Button
          variant={data.enabled ? "primary" : "secondary"}
          icon={data.enabled ? Volume2 : VolumeX}
          loading={change.isPending}
          aria-pressed={data.enabled}
          onClick={() => change.mutate({ enabled: !data.enabled })}
        >
          {data.enabled ? "Nhạc nền đang bật" : "Nhạc nền đang tắt"}
        </Button>
        <label className="text-sm">
          <span className="block text-fg-2">Mức nhạc dưới giọng đọc</span>
          <select
            value={String(data.levelDb)}
            onChange={(event) => change.mutate({ levelDb: Number(event.target.value) })}
            className="mt-1 h-9 rounded-lg border border-line bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-accent"
          >
            {levelOptions(data.levelDb).map(([value, label]) => (
              <option key={value} value={String(value)}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <ul className={cn("max-h-72 divide-y divide-line overflow-y-auto rounded-xl border border-line", !data.enabled && "opacity-50")}>
        {data.cues.map((cue) => (
          <li key={cue.key}>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
              <div className="min-w-[9rem] flex-1">
                <div className={cn("truncate text-sm", cue.silenced && "text-fg-3 line-through")}>{cue.title || "Nhạc nền"}</div>
                <div className="tabular truncate text-xs text-fg-2">
                  {cue.chapter} · {formatClock(cue.start)} – {formatClock(cue.end)}
                  {cue.creator ? ` · ${cue.creator}` : ""}
                  {cue.pinned ? " · bài của bạn" : ""}
                </div>
              </div>
              <span className="flex shrink-0 gap-1">
                {cue.pinned && (
                  <Button size="sm" variant="ghost" disabled={change.isPending} onClick={() => change.mutate({ pins: { [cue.key]: null } })}>
                    Về bài gốc
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="ghost"
                  icon={Shuffle}
                  aria-expanded={swapping === cue.key}
                  disabled={change.isPending}
                  onClick={() => setSwapping(swapping === cue.key ? null : cue.key)}
                >
                  Đổi bài
                </Button>
                <Button size="sm" variant="ghost" disabled={change.isPending} onClick={() => change.mutate({ silence: { [cue.key]: !cue.silenced } })}>
                  {cue.silenced ? "Có nhạc" : "Im lặng"}
                </Button>
              </span>
            </div>
            {swapping === cue.key && (
              <SwapTrack
                bookId={book.id}
                cueKey={cue.key}
                busy={change.isPending}
                choosing={choosing}
                onChoose={(link) => change.mutate({ pins: { [cue.key]: link }, ...(cue.silenced ? { silence: { [cue.key]: false } } : {}) })}
              />
            )}
          </li>
        ))}
      </ul>
      <MyMusicSection />
    </div>
  );
}

function Section({ title, hint, children }: { title: string; hint?: string; children?: ReactNode }) {
  return (
    <section className="border-t border-line pt-4 first:border-t-0 first:pt-0">
      <h3 className="text-sm font-semibold">{title}</h3>
      {hint && <p className="mb-2 text-xs text-fg-2">{hint}</p>}
      {children && <div className={hint ? undefined : "mt-2"}>{children}</div>}
    </section>
  );
}

/** Hộp "Sửa sách": tên, bìa, nhạc nền, bỏ mọi thay đổi. Tên nhân vật và tên chương sửa ngay ở tab Nhân vật / dòng chương. */
export function EditBookDialog({
  book,
  open,
  onOpenChange,
  onOpenStudio,
}: {
  book: ListenBook;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Máy tính, cuốn có xưởng: nhạc nền chỉnh đầy đủ ở tab Nhạc nền của Studio. */
  onOpenStudio?: () => void;
}) {
  const client = useQueryClient();
  const [title, setTitle] = useState(book.title);
  const file = useRef<HTMLInputElement | null>(null);
  const [confirmRevert, setConfirmRevert] = useState(false);
  useEffect(() => {
    if (open) {
      setTitle(book.title);
      setConfirmRevert(false);
    }
  }, [open, book.title]);
  const workshop = Boolean(book.capabilities?.workshop);
  const done = (message: string) => {
    refreshAfterEdit(client, book.id);
    toast.success(message);
  };
  const rename = useMutation({
    mutationFn: (next: string) => api(`/api/books/${book.id}/title`, { method: "PUT", body: { title: next } }),
    onSuccess: () => done("Đã đổi tên sách"),
    onError: (error: Error) => toast.error("Chưa đổi được tên sách", { description: error.message }),
  });
  const setCover = useMutation({
    mutationFn: async (picked: Blob) => api(`/api/books/${book.id}/cover`, { method: "PUT", body: { image: await imageToDataUrl(picked) } }),
    onSuccess: () => done("Đã đặt ảnh bìa"),
    onError: (error: Error) => toast.error("Chưa đặt được ảnh bìa", { description: error.message }),
  });
  const removeCover = useMutation({
    mutationFn: () => api(`/api/books/${book.id}/cover`, { method: "DELETE" }),
    onSuccess: () => done("Đã bỏ ảnh bìa - sách dùng bìa vẽ từ tên"),
    onError: (error: Error) => toast.error("Chưa bỏ được ảnh bìa", { description: error.message }),
  });
  const revert = useMutation({
    mutationFn: () => api(`/api/books/${book.id}/edits`, { method: "DELETE" }),
    onSuccess: () => {
      setConfirmRevert(false);
      done("Đã bỏ mọi thay đổi - sách như người làm sách đã đóng gói");
      window.dispatchEvent(new CustomEvent(MUSIC_CHANGED_EVENT, { detail: book.id }));
    },
    onError: (error: Error) => toast.error("Chưa bỏ được thay đổi", { description: error.message }),
  });
  const busy = rename.isPending || setCover.isPending || removeCover.isPending;
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      width="max-w-xl"
      title="Sửa sách"
      description="Đổi có hiệu lực ngay và chỉ trên máy này - audio và chữ của người làm sách giữ nguyên."
    >
      <div className="max-h-[68vh] space-y-4 overflow-y-auto pr-1">
        <Section title="Tên sách">
          <form
            className="flex gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              if (title.trim() && title.trim() !== book.title) rename.mutate(title);
            }}
          >
            <input
              data-autofocus
              value={title}
              maxLength={160}
              aria-label="Tên sách"
              onChange={(event) => setTitle(event.target.value)}
              className="h-10 min-w-0 flex-1 rounded-lg border border-line bg-bg px-3 text-sm outline-none focus:border-accent"
            />
            <Button type="submit" variant="primary" loading={rename.isPending} disabled={!title.trim() || title.trim() === book.title}>
              Lưu tên
            </Button>
          </form>
        </Section>
        <Section title="Ảnh bìa">
          <div className="flex items-start gap-4">
            <BookCover title={book.title} part={book.series?.part} size="lg" image={book.cover} className="w-28 shrink-0" />
            <div className="flex flex-col items-start gap-1">
              <Button variant="outline" icon={ImagePlus} disabled={busy} onClick={() => file.current?.click()}>
                {book.cover ? "Đổi ảnh bìa…" : "Chọn ảnh bìa…"}
              </Button>
              {book.cover && (
                <Button variant="ghost" icon={Trash2} disabled={busy} onClick={() => removeCover.mutate()}>
                  Bỏ ảnh bìa
                </Button>
              )}
              {setCover.isPending && (
                <span className="inline-flex items-center gap-1.5 text-xs text-fg-2">
                  <Loader2 className="size-3.5 animate-spin" /> Đang đặt ảnh…
                </span>
              )}
            </div>
            <input
              ref={file}
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif,image/bmp"
              className="hidden"
              onChange={(event) => {
                const picked = event.target.files?.[0];
                event.target.value = "";
                if (picked) setCover.mutate(picked);
              }}
            />
          </div>
        </Section>
        <Section title="Nhạc nền">
          {workshop ? (
            <div className="flex flex-wrap items-center gap-3 text-sm text-fg-2">
              <span>Cuốn này có xưởng - nhạc nền chỉnh đầy đủ (chọn bài, im lặng từng đoạn) ở Studio.</span>
              {onOpenStudio && (
                <Button size="sm" variant="outline" icon={Music2} onClick={onOpenStudio}>
                  Mở tab Nhạc nền
                </Button>
              )}
            </div>
          ) : (
            <MusicSection book={book} />
          )}
        </Section>
        <Section title="Tên chương và tên nhân vật" hint="Bấm “…” ở dòng chương để đổi tên chương, “…” ở tab Nhân vật để đổi tên người." />
        {!workshop && (book.edits ?? 0) > 0 && (
          <Section title={`Bỏ mọi thay đổi (${book.edits})`} hint="Sách trở về đúng như người làm sách đã đóng gói.">
            {confirmRevert ? (
              <div className="flex gap-2">
                <Button variant="danger" loading={revert.isPending} onClick={() => revert.mutate()}>
                  Bỏ hết thay đổi
                </Button>
                <Button variant="ghost" onClick={() => setConfirmRevert(false)}>
                  Thôi
                </Button>
              </div>
            ) : (
              <Button variant="outline" onClick={() => setConfirmRevert(true)}>
                Bỏ mọi thay đổi…
              </Button>
            )}
          </Section>
        )}
      </div>
    </Dialog>
  );
}

/** Đổi tên một chương: nhãn ("Chương 12") và tên ("Hồi kết"); "Về tên gốc" trả lại tên của người làm sách. */
export function RenameChapterDialog({ book, chapter, onClose }: { book: ListenBook; chapter: ListenChapter | null; onClose: () => void }) {
  const client = useQueryClient();
  const [label, setLabel] = useState("");
  const [name, setName] = useState("");
  useEffect(() => {
    setLabel(chapter?.title ?? "");
    setName(chapter?.subtitle ?? "");
  }, [chapter]);
  const save = useMutation({
    mutationFn: (body: { title?: string; subtitle?: string; revert?: boolean }) =>
      api<{ fullTitle: string }>(`/api/books/${book.id}/chapters/${chapter?.id}/title`, { method: "PUT", body }),
    onSuccess: (answer) => {
      refreshAfterEdit(client, book.id);
      toast.success(`Đã đổi tên chương: ${answer.fullTitle}`);
      onClose();
    },
    onError: (error: Error) => toast.error("Chưa đổi được tên chương", { description: error.message }),
  });
  return (
    <Dialog
      open={chapter !== null}
      onOpenChange={(open) => !open && onClose()}
      width="max-w-md"
      title="Đổi tên chương"
      description="Chỉ đổi cái tên hiện trên màn hình - audio không đổi."
    >
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          if (label.trim()) save.mutate({ title: label, subtitle: name });
        }}
      >
        <label className="block text-sm">
          <span className="text-fg-2">Số chương hay nhãn</span>
          <input
            data-autofocus
            value={label}
            maxLength={160}
            onChange={(event) => setLabel(event.target.value)}
            className="mt-1 h-9 w-full rounded-lg border border-line bg-bg px-2.5 text-sm outline-none focus-visible:border-accent"
          />
        </label>
        <label className="block text-sm">
          <span className="text-fg-2">Tên chương (có thể để trống)</span>
          <input
            value={name}
            maxLength={160}
            onChange={(event) => setName(event.target.value)}
            className="mt-1 h-9 w-full rounded-lg border border-line bg-bg px-2.5 text-sm outline-none focus-visible:border-accent"
          />
        </label>
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" disabled={save.isPending} onClick={() => save.mutate({ revert: true })}>
            Về tên gốc
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>
            Thôi
          </Button>
          <Button type="submit" variant="primary" loading={save.isPending} disabled={!label.trim()}>
            Lưu
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

/** "Lưu": đóng cuốn (kèm thay đổi của người nghe) thành file mới, GIỮ loại file cuốn đã đến (`.abookproj` mang theo xưởng của nó,
 *  `.abook` thì không). Máy tính ghi vào thư mục xuất (hay thư mục đã chọn), điện thoại hỏi chỗ lưu. Trả hàm lưu và trạng thái bận. */
export function useSaveBook(book: ListenBook) {
  const source = useSource();
  const [busy, setBusy] = useState(false);
  const save = async (options?: { folder?: string; as?: "abook" | "abookproj" }) => {
    if (!source.saveBook) return;
    setBusy(true);
    try {
      const result = await source.saveBook(book.id, options);
      if (!result.saved) return;
      const edits = result.edits ? `${result.edits} thay đổi của bạn nằm trong file.` : "Chưa có thay đổi nào - file giống bản gốc.";
      const folder = result.folder;
      toast.success("Đã lưu file sách", {
        description: `${result.file ?? ""}${result.file ? " - " : ""}${edits}`,
        duration: 8000,
        action: folder
          ? { label: "Mở thư mục", onClick: () => void api("/api/reveal-export", { method: "POST", body: { folder } }).catch(() => undefined) }
          : undefined,
      });
    } catch (error) {
      toast.error("Chưa lưu được file sách", { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  return { save, busy, available: Boolean(source.saveBook) };
}

type SaveKind = "abook" | "abookproj";

/** "Lưu thành…": chọn loại file. `.abookproj` mang cả xưởng nếu cuốn đến từ một file dự án; không thì là file "chờ dựng xưởng"
 *  (chỉ phần nghe + thay đổi của bạn, máy có Studio mời dựng xưởng khi mở). */
export function SaveAsDialog({
  book,
  open,
  onOpenChange,
  pickFolder,
}: {
  book: ListenBook;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Máy tính trong cửa sổ app: chọn thư mục lưu (hộp thoại của Windows). */
  pickFolder?: () => Promise<string | null>;
}) {
  const { save, busy } = useSaveBook(book);
  const [kind, setKind] = useState<SaveKind>(book.projectFile ? "abookproj" : "abook");
  const [folder, setFolder] = useState<string | null>(null);
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      width="max-w-md"
      title="Lưu thành…"
      description="Lưu cuốn này kèm những thay đổi của bạn thành một file mới. File gốc không bị đụng tới."
    >
      <Segmented<SaveKind>
        value={kind}
        onChange={setKind}
        label="Loại file"
        options={[
          { value: "abook", label: "Sách nghe (.abook)" },
          { value: "abookproj", label: "Dự án (.abookproj)" },
        ]}
      />
      {kind === "abookproj" ? (
        <p className="mt-3 text-sm text-fg-2">
          {book.projectFile?.workshop === "present"
            ? "Dự án (.abookproj) giữ nguyên cả xưởng làm sách của cuốn này, kèm những thay đổi của bạn. Mở bằng Studio, ABook hỏi có áp thay đổi vào dự án không."
            : "Cuốn này chưa có xưởng: file chỉ mang phần nghe và thay đổi của bạn. Máy có Studio mở file sẽ mời “Dựng xưởng” - tạo dự án mới từ chữ và giọng trong sách, làm lại toàn bộ audio."}
        </p>
      ) : (
        <p className="mt-3 text-sm text-fg-2">
          Sách nghe mở được bằng ABook trên máy tính và điện thoại, mang theo tên, bìa, tên nhân vật, tên chương, nhạc bạn đã sửa
          {book.wishes ? `, cùng ${book.wishes} việc đang chờ Studio (chưa làm gì trong giọng đọc)` : ""}.
        </p>
      )}
      {pickFolder && (
        <div className="mt-3 flex items-center gap-2 text-sm">
          <Button variant="outline" size="sm" onClick={() => void pickFolder().then((picked) => picked && setFolder(picked))}>
            Chọn thư mục…
          </Button>
          <span className="min-w-0 truncate text-fg-2">{folder ?? "Mặc định: thư mục Đã xuất"}</span>
        </div>
      )}
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" onClick={() => onOpenChange(false)}>
          Thôi
        </Button>
        <Button
          variant="primary"
          icon={FileDown}
          loading={busy}
          onClick={() => void save({ ...(folder ? { folder } : {}), as: kind }).then(() => onOpenChange(false))}
        >
          Lưu
        </Button>
      </div>
    </Dialog>
  );
}

/** Việc cần Studio vẫn hiện trong menu, mờ đi, nói rõ thiếu gì - không giấu (docs/EDITING.md: "explain, never hide"). */
export function StudioOnlyItem({ book }: { book: ListenBook }) {
  const need = studioNeed(book.capabilities);
  if (!need) return null;
  const syncs = syncsToComputer(book.capabilities);
  return (
    <DropdownMenu.Item disabled className={cn(MENU_ITEM, "h-auto items-start py-1.5 data-[disabled]:opacity-60")}>
      <Wrench className="mt-0.5 size-4 shrink-0" />
      <span className="min-w-0">
        <span className="block">Đổi giọng, sửa lời đọc, thu lại chương</span>
        <span className="block text-xs text-fg-3">
          {syncs
            ? "Làm ở Studio trên máy tính - đổi giới tính, gộp người, cách đọc ghi được ở đây rồi gửi về máy tính chờ duyệt"
            : `${need} - đổi giới tính, gộp người ghi được ở tab Nhân vật, chờ Studio làm`}
        </span>
      </span>
    </DropdownMenu.Item>
  );
}

/** Cuốn nghe thẳng từ máy khác: mục sửa vẫn hiện, mờ đi, nói vì sao không sửa được ở đây - không giấu. */
export function EditBlockedItem({ book }: { book: ListenBook }) {
  const note = editBlockedNote(book.capabilities);
  if (!note) return null;
  return (
    <DropdownMenu.Item disabled className={cn(MENU_ITEM, "h-auto items-start py-1.5 data-[disabled]:opacity-60")}>
      <Pencil className="mt-0.5 size-4 shrink-0" />
      <span className="min-w-0">
        <span className="block">Sửa tên, bìa, nhạc nền…</span>
        <span className="block text-xs text-fg-3">{note}</span>
      </span>
    </DropdownMenu.Item>
  );
}

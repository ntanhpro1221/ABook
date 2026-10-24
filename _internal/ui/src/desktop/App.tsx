import { MotionRegion } from "@/shared/MotionRegion";
import { MotionPresence } from "@/shared/MotionPresence";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { Clapperboard, Compass, FileAudio, Headphones, Laptop, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Route, Routes, useNavigate } from "react-router";
import { Toaster } from "sonner";
import { toast } from "@/shared/toast";
import { BookScreen } from "@/listen/BookScreen";
import { ClipProvider } from "@/listen/clip";
import { WebAudioEngine } from "@/listen/engine";
import { RoutedEngine } from "@/listen/readAloud";
import { onDefaultVoiceChosen, restoreDefaultVoice } from "@/listen/readAloudVoice";
import { AddBookButton } from "@/listen/AddBook";
import type { ReadSession } from "@/listen/importQueue";
import { DropToAdd } from "@/listen/DropToAdd";
import { LibraryScreen } from "@/listen/LibraryScreen";
import { MorningRecap } from "@/listen/MorningRecap";
import { ReaderScreen } from "@/listen/ReaderScreen";
import { readerEditing } from "./readerEditing";
import { PlayerProvider, usePlayer } from "@/listen/player";
import { SourceProvider, useSource } from "@/listen/source";
import { Button, Dialog, EmptyState, TooltipProvider, useFocusClearOfToasts } from "@/shared/ui";
import { useMediaQuery, useModalOpen } from "@/shared/media";
import type { ListenBook } from "@/listen/model";
import { brokenMusicNote, keptEditsTitle, otherTitleNote, workshopMergeNote } from "@/shared/editsKept";
import { MissingLibrary } from "@/shared/MissingLibrary";
import { MotionHashRouter } from "@/shared/MotionRouter";
import { withViewTransition } from "@/shared/motion";
import { setLetterShortcuts } from "@/shared/letterShortcuts";
import { setExternalOpener } from "@/shared/openExternal";
import { toastRemoved } from "@/shared/trashUndo";
import { homePage, LISTEN_ONLY_EVENT, listenOnlyLine, listenOnlyOwner, peerPage } from "@/shared/peerStudio";
import { watchUntilBack } from "@/listen/peerBack";
import { api, ApiError, currentPeer, type AppInfo } from "@/studio/api";
import { pickFolder, useAppInfo, useLibrary, usePreferences } from "@/studio/data";
import { LibraryMoveRecovery } from "./LibraryMoveRecovery";
import { NewProjectScreen } from "@/studio/NewProjectScreen";
import { ProjectScreen } from "@/studio/ProjectScreen";
import { ProjectsScreen } from "@/studio/ProjectsScreen";
import { desktopTextImport, httpSource } from "./httpSource";
import { AudiobookDialogHost } from "./AudiobookDialog";
import { AudiobookMenuItem, BookFileMenuItem, ExportJobHost, M4bMenuItem, Mp3MenuItem } from "./ExportBookFileJob";
import { RemoteDownloadMenuItem, RemoteDownloadStatus } from "./RemoteDownload";
import { SettingsScreen } from "./SettingsScreen";
import { OpenedInbox } from "./openedInbox";
import { Shell } from "./Shell";

function useTheme(theme: string | undefined) {
  // Lần đầu đặt thẳng; đổi sau đó (người dùng chọn, Windows tự chuyển sáng/tối) thì cả cửa sổ mờ chéo sang giao diện mới.
  const applied = useRef(false);
  useEffect(() => {
    const root = document.documentElement;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const next = theme === "dark" || (theme !== "light" && media.matches) ? "dark" : "light";
      if (!applied.current || root.dataset.theme === next) root.dataset.theme = next;
      else withViewTransition(() => (root.dataset.theme = next), "none", undefined, (run) => run());
      applied.current = theme !== undefined;
    };
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [theme]);
}

function ClipBridge({ children }: { children: ReactNode }) {
  const player = usePlayer();
  return <ClipProvider onStart={() => player.playing && player.toggle()}>{children}</ClipProvider>;
}

const shownNotices = new Set<string>();

/** File trạng thái hỏng đã được giữ lại lúc mở app (máy chủ: notices.keep_broken): báo mỗi dòng một lần - cái gì, đã giữ bản cũ ở đâu
 *  (soát a28 lỗi 1). Không báo thì người dùng chỉ thấy chỗ nghe / cài đặt "tự mất". */
function StartupNotices({ notices }: { notices?: { id: string; text: string }[] }) {
  useEffect(() => {
    for (const notice of notices ?? []) {
      if (shownNotices.has(notice.id)) continue;
      shownNotices.add(notice.id);
      toast.warning(notice.text, { duration: 30000 });
    }
  }, [notices]);
  return null;
}

function EmptyLibrary() {
  const navigate = useNavigate();
  const library = useLibrary({ live: false }).data;
  // Người mới mở app thường có sẵn một file truyện: nghe ngay là việc chính, làm sách nói (Studio) là việc kế. Máy điều khiển từ xa không
  // thêm file được thì Studio vẫn là nút chính.
  const canAdd = Boolean(useSource().textImport);
  const openBookPath = useOpenBookPath();
  if (library?.rootMissing) return <MotionRegion><MissingLibrary root={library.root} className="mt-12 rounded-2xl border border-dashed border-line" /></MotionRegion>;
  return (
    <MotionRegion><EmptyState
      icon={Headphones}
      title="Chưa có sách"
      className="mt-12 rounded-2xl border border-dashed border-line"
      action={
        <div className="flex flex-wrap justify-center gap-2">
          <AddBookButton variant="primary" size="lg" onBookFile={openBookPath} />
          <Button variant={canAdd ? "secondary" : "primary"} size={canAdd ? "md" : "lg"} icon={Clapperboard} onClick={() => navigate("/studio/new")}>
            Tạo sách nói
          </Button>
          <OpenBookFileButton variant="ghost" />
        </div>
      }
    >
      Thêm truyện hoặc tạo sách nói.
    </EmptyState></MotionRegion>
  );
}

function StudioMenuItem({ id }: { id: string }) {
  const navigate = useNavigate();
  return (
    <DropdownMenu.Item
      onSelect={() => navigate(`/studio/${id}`)}
      className="flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[highlighted]:bg-hover"
    >
      <Clapperboard className="size-4" /> Mở trong Studio
    </DropdownMenu.Item>
  );
}

/** Cuốn nhập từ file `.abook`: bỏ khỏi thư viện (thư mục giải nén vào Thùng rác). Hộp xác nhận nằm ngoài menu
 *  (RemoveImportedHost) - menu đóng lại ngay khi chọn, hộp trong menu sẽ biến mất theo. */
function RemoveImportedMenuItem({ book }: { book: ListenBook }) {
  return (
    <DropdownMenu.Item
      onSelect={() => window.dispatchEvent(new CustomEvent<ListenBook>("abook-remove-imported", { detail: book }))}
      className="flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm text-danger outline-none data-[highlighted]:bg-hover"
    >
      <Trash2 className="size-4" /> Xoá khỏi thư viện…
    </DropdownMenu.Item>
  );
}

/** Sách chỉ có chữ (EPUB / TXT / DOCX / PDF) và sách đóng gói .abook bỏ khỏi thư viện thì khác nhau ở điều người dùng cần biết sau đó: file gốc thế nào, lấy lại cách nào. */
function removedNote(book: ListenBook): string {
  return book.stage === "text" ? "File gốc của bạn không bị đụng." : "Mở lại file .abook là nhập lại.";
}

function removeAsk(book: ListenBook): string {
  return book.stage === "text"
    ? "Sách vào Thùng rác, khôi phục được. File gốc giữ nguyên."
    : "Sách vào Thùng rác, khôi phục được. File .abook gốc giữ nguyên.";
}

function RemoveImportedHost() {
  const [book, setBook] = useState<ListenBook | null>(null);
  const [busy, setBusy] = useState(false);
  const client = useQueryClient();
  const navigate = useNavigate();
  const player = usePlayer();
  useEffect(() => {
    const listener = (event: Event) => setBook((event as CustomEvent<ListenBook>).detail);
    window.addEventListener("abook-remove-imported", listener);
    return () => window.removeEventListener("abook-remove-imported", listener);
  }, []);
  const remove = async () => {
    if (!book) return;
    setBusy(true);
    // Cuốn đang nghe giữ file chương mở - đóng trình phát trước (nó lưu chỗ nghe lúc sách còn đó).
    if (player.track?.bookId === book.id) player.close();
    try {
      const result = await api<{ ok: boolean; undo?: string }>(`/api/listen/books/${book.id}`, { method: "DELETE" });
      setBook(null);
      navigate("/", { replace: true });
      void client.invalidateQueries({ queryKey: ["listen"] });
      // "Hoàn tác" (trash_pending.py): thư mục nằm chờ vài chục giây trước khi vào Thùng rác.
      toastRemoved({
        message: `Đã bỏ “${book.title}” khỏi thư viện`,
        title: book.title,
        undo: result.undo,
        note: removedNote(book),
        onRestored: () => void client.invalidateQueries({ queryKey: ["listen"] }),
      });
    } catch (error) {
      toast.error("Chưa xoá được", { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog
      open={book !== null}
      onOpenChange={(open) => !open && setBook(null)}
      title={`Bỏ “${book?.title ?? ""}” khỏi thư viện?`}
      description={book ? removeAsk(book) : ""}
    >
      <div className="dialog-actions">
        <Button variant="ghost" onClick={() => setBook(null)}>
          Để sau
        </Button>
        <Button variant="danger" icon={Trash2} loading={busy} onClick={() => void remove()}>
          Xoá khỏi thư viện
        </Button>
      </div>
    </Dialog>
  );
}

/** Kết quả mở một file sách (`POST /api/listen/open-book-file`, hay cửa sổ app khi bấm đúp file .abook - desktop.py). */
interface OpenedBook {
  eventId?: string;
  id: string | null;
  how?: "new" | "existing" | "updated" | "repaired" | "project" | "studio" | "older" | "conflict";
  source?: string;
  /** File `.abookproj`: số file nguồn chương không có trong gói (đã bị dời hay xoá ở máy gói). */
  missingSources?: number;
  /** File `.abook` phiên bản 4 mang thay đổi của người nghe (lớp sửa - docs/EDITING.md): số thay đổi. Cuốn là dự án của
   *  máy này (`how` "project") thì chúng đang chờ người dùng đồng ý áp vào dự án. */
  edits?: number;
  /** Cuốn đã nhập sẵn trên máy: phần sửa trong file được hợp vào, thay đổi của máy này thắng khi trùng. */
  merge?: { adopted: number; kept: number; conflicts: number };
  /** File `.abookproj` của dự án máy này: sửa trong xưởng của file đã gộp vào dự án (bản mới hơn thắng). */
  workshop?: { merged: number; kept: number };
  /** File `.abook` có bài nhạc nền hỏng: đã bỏ bài ấy (đoạn ấy im lặng), sách vẫn mở. */
  brokenMusic?: number;
  /** Cuốn đã có (`how` "existing") mang tên khác tên trong file: tên trong file không được lấy. */
  otherTitle?: string;
  error?: string;
  file?: string;
}

const OPENED_SAID: Record<NonNullable<OpenedBook["how"]>, [string, string | undefined]> = {
  new: ["Đã thêm sách", "Sách đã chép vào thư viện - xoá file gốc cũng không sao."],
  existing: ["Sách đã có", undefined],
  updated: ["Đã cập nhật", "Chỗ đang nghe, dấu trang và chỉnh sửa của bạn vẫn giữ nguyên."],
  older: ["Bản sách cũ hơn", "Bạn muốn thay bản đang có bằng file này?"],
  conflict: ["Bản thu khác", "Chưa rõ bản mới hơn; thay bản đang có bằng file này?"],
  repaired: ["Đã khôi phục file", "Chỗ đang nghe, dấu trang vẫn giữ nguyên."],
  project: ["Sách của Studio", "Mở đúng cuốn ấy, không chép thêm bản nào."],
  studio: ["Đã mở dự án", "Dự án đã chép vào thư viện Studio - xoá file gốc cũng không sao."],
};

/** Thư viện mà một file sách vừa mở làm đổi: thư viện Studio (dự án) hay thư viện nghe. */
const openedLibrary = (result: OpenedBook) => ({ queryKey: [result.how === "studio" ? "library" : "listen"] });

function useOpenedBook() {
  const navigate = useNavigate();
  const client = useQueryClient();
  return useCallback(
    (result: OpenedBook): boolean => {
      if (result.error) {
        toast.error("Không mở được file sách", { description: result.file ? `${result.file}: ${result.error}` : result.error });
        return false;
      }
      if (!result.id) return false;
      if (result.how === "older" || result.how === "conflict") {
        const [title, description] = OPENED_SAID[result.how];
        toast.warning(title, { description, duration: Infinity,
          action: { label: "Thay bằng file này", onClick: () => {
            void api<OpenedBook>("/api/listen/open-book-file", { method: "POST", body: { path: result.source, allowOlder: true } })
              .then((next) => { void client.invalidateQueries({ queryKey: ["listen"] }); navigate(`/book/${next.id}`); toast.success("Đã thay bản sách, giữ chỉnh sửa và chỗ nghe của bạn"); })
              .catch((error: Error) => toast.error("Chưa thay được sách", { description: error.message }));
          } }, cancel: { label: "Giữ bản đang có", onClick: () => undefined } });
        return true;
      }
      if (result.how === "studio") {
        void client.invalidateQueries(openedLibrary(result));
        navigate(`/studio/${result.id}`);
        if (result.edits) offerFold(client, result.id, result.edits); // file dự án đã được sửa ở máy khác (điện thoại)
        const lost = result.missingSources ?? 0;
        toast.success(OPENED_SAID.studio[0], {
          description: lost
            ? `Thiếu ${lost} file nguồn chương (đã bị dời ở máy gói) - nghe, xem, xuất vẫn được; thu lại chương ấy thì cần chép nguồn vào.`
            : OPENED_SAID.studio[1],
        });
        return true;
      }
      void client.invalidateQueries(openedLibrary(result));
      navigate(`/book/${result.id}`);
      const [said, description] = OPENED_SAID[result.how ?? "new"];
      const note = workshopMergeNote(result.workshop) ?? mergeNote(result) ?? otherTitleNote(result.otherTitle) ?? description;
      toast.success(keptEditsTitle(result.merge?.kept) ?? said, { description: [note, brokenMusicNote(result.brokenMusic)].filter(Boolean).join(" ") || undefined });
      if (result.how === "project" && result.edits) offerFold(client, result.id, result.edits);
      return true;
    },
    [client, navigate],
  );
}

/** File đã sửa mở vào cuốn có sẵn trên máy: nói thay đổi nào được lấy từ file và chỗ nào hai bên khác nhau (phần "giữ nguyên N
 *  chỉnh sửa của bạn" đã nằm ở tiêu đề - keptEditsTitle). Không nói gì khi file không mang thay đổi. */
function mergeNote(result: OpenedBook): string | undefined {
  const merge = result.merge;
  if (!merge || (!merge.adopted && !merge.conflicts)) return undefined;
  const taken = merge.adopted ? `Đã lấy ${merge.adopted} thay đổi từ file.` : "";
  const conflict = merge.conflicts ? ` Chỗ hai bên khác nhau thì theo máy này (${merge.conflicts}).` : "";
  return `${taken}${conflict}`.trim();
}

/** File `.abook` mang thay đổi của người nghe, mở ra đúng dự án của máy này: hỏi có áp vào dự án không - thông báo có nút,
 *  không phải hộp chọn chế độ. Chưa áp gì cho tới khi bấm; "Bỏ qua" xoá phần chờ. */
function offerFold(client: QueryClient, id: string, edits: number) {
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ["library"] });
    void client.invalidateQueries({ queryKey: ["book", id] });
    void client.invalidateQueries({ queryKey: ["listen"] });
  };
  toast(`${edits} thay đổi trong file - áp vào dự án?`, {
    description: "Sửa tên, bìa, nhạc nền và việc ghi cho Studio. Chưa áp gì khi bạn chưa đồng ý.",
    duration: 30000,
    action: {
      label: "Áp vào dự án",
      onClick: () =>
        void api<{ applied: number; skipped: number; requests?: number }>(`/api/books/${id}/edits/fold`, { method: "POST", body: {} })
          .then((report) => {
            refresh();
            const asked = report.requests ? `${report.requests} việc đã vào danh sách chờ áp dụng của dự án. ` : "";
            const lost = report.skipped ? `${report.skipped} thay đổi không còn chỗ trong dự án nên bỏ qua.` : "";
            toast.success(`Đã áp ${report.applied} thay đổi vào dự án`, { description: `${asked}${lost}`.trim() || undefined });
          })
          .catch((error: Error) => toast.error("Chưa áp được thay đổi", { description: error.message })),
    },
    cancel: {
      label: "Bỏ qua",
      onClick: () => void api(`/api/books/${id}/edits`, { method: "DELETE" }).then(refresh).catch(() => undefined),
    },
  });
}

/** Cửa sổ app mở một file sách (bấm đúp .abook trong Explorer, kể cả khi app đang mở): desktop.py báo qua sự kiện. */
/** Âm lượng nhớ qua các lần mở app (soát UX 29-09: đặt 15% rồi mở lại thành 90% - app nghe trước khi ngủ mà lần sau phát
 *  to đột ngột). Lưu vào tuỳ chọn sau khi thôi kéo; mức 0 của nút tắt tiếng thì không lưu - lần mở sau về mức nghe được gần
 *  nhất, không im lặng khó hiểu. */
function VolumeSaver() {
  const { volume } = usePlayer();
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    if (volume <= 0) return;
    const timer = window.setTimeout(() => {
      void api("/api/preferences", { method: "PUT", body: { volume } }).catch(() => undefined);
    }, 800);
    return () => window.clearTimeout(timer);
  }, [volume]);
  return null;
}

function OpenedBookListener({ local = true }: { local?: boolean }) {
  const opened = useOpenedBook();
  useEffect(() => {
    const inbox = new OpenedInbox<OpenedBook>(opened, (eventId) => api("/api/host/opened/ack", { method: "POST", body: { eventId } }));
    let stopped = false, polling = false;
    const receive = (event: OpenedBook) => inbox.receive(event).catch(() => undefined);
    const listener = (event: Event) => { void receive((event as CustomEvent<OpenedBook>).detail); };
    window.addEventListener("abook-opened", listener);
    // Listener đã gắn mới báo sẵn sàng. GET không lấy mất sự kiện: reload trước ACK vẫn nhận lại.
    const replay = async () => {
      if (polling || stopped) return;
      polling = true;
      try {
        const events = await api<OpenedBook[]>("/api/host/opened");
        for (const event of events) { if (stopped) break; await receive(event); }
      } catch { /* Host đang bận / trang vừa nạp lại: nhịp sau thử tiếp. */ }
      finally { polling = false; }
    };
    if (local) void replay();
    const timer = local ? window.setInterval(() => void replay(), 1000) : undefined;
    return () => { stopped = true; window.clearInterval(timer); window.removeEventListener("abook-opened", listener); };
  }, [local, opened]);
  return null;
}

/** Quyền sửa bị thu hồi giữa phiên (Studio từ xa, hay Studio của máy khác): hỏi lại /api/app để bỏ các nút Studio (api.ts phát sự kiện khi gặp 403 `listenOnly`). */
function ListenOnlyListener() {
  const client = useQueryClient();
  useEffect(() => {
    const refresh = () => void client.invalidateQueries({ queryKey: ["app"] });
    window.addEventListener(LISTEN_ONLY_EVENT, refresh);
    return () => window.removeEventListener(LISTEN_ONLY_EVENT, refresh);
  }, [client]);
  return null;
}

/** App Windows đóng gói: vỏ tìm thấy bản mới sau khi trang đã mở - đọc lại thông tin app để hiện nút "Cập nhật";
 *  tải bản mới hỏng (mất mạng, chữ ký sai) thì nói rõ, bấm lại được. */
function UpdateListener() {
  const client = useQueryClient();
  useEffect(() => {
    const found = () => void client.invalidateQueries({ queryKey: ["app"] });
    // Lời của vỏ đã viết sẵn cho người nghe (không lộ chuỗi lỗi của thư viện) và đã nói bước tiếp theo.
    const failed = (event: Event) => toast.error("Chưa tải được bản mới", { description: (event as CustomEvent<string>).detail });
    window.addEventListener("abook-update", found);
    window.addEventListener("abook-update-failed", failed);
    return () => {
      window.removeEventListener("abook-update", found);
      window.removeEventListener("abook-update-failed", failed);
    };
  }, [client]);
  return null;
}

/** Hộp "Thêm sách từ file…" nhận được .abook / .abookproj (dán đường dẫn, kể cả từ trình duyệt): mở như "Mở file sách". */
export function useOpenBookPath() {
  const opened = useOpenedBook();
  const client = useQueryClient();
  return useCallback(
    async (path: string, session?: ReadSession) => {
      const book = await api<OpenedBook>("/api/listen/open-book-file", { method: "POST", body: { path } });
      try {
        session?.still();
      } catch (cancelled) {
        // Hộp đã đóng: không chuyển trang, nhưng máy đã nhập xong cuốn này - thư viện vẫn phải thấy nó.
        if (book.id && !book.error) void client.invalidateQueries(openedLibrary(book));
        throw cancelled;
      }
      return opened(book);
    },
    [client, opened],
  );
}

/** "Mở file sách": hộp chọn file của Windows (chỉ có trong cửa sổ app), nhập vào thư viện, mở trang sách. */
function OpenBookFileButton({ variant = "secondary" }: { variant?: "secondary" | "ghost" }) {
  const { data: info } = useAppInfo();
  const opened = useOpenedBook();
  const [busy, setBusy] = useState(false);
  if (!info?.dialogs) return null;
  const run = async () => {
    setBusy(true);
    try {
      opened(await api<OpenedBook>("/api/listen/open-book-file", { method: "POST", body: {} }));
    } catch (error) {
      toast.error("Không mở được file sách", { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Button variant={variant} icon={FileAudio} className="touch-row" disabled={busy} onClick={() => void run()}>
      {busy ? "Đang mở…" : "Mở file sách"}
    </Button>
  );
}

function StudioChipLink({ id }: { id: string }) {
  const navigate = useNavigate();
  return (
    <button type="button" onClick={() => navigate(`/studio/${id}`)} className="font-semibold underline underline-offset-2 hover:no-underline">
      Mở Studio
    </button>
  );
}

/** Cuốn đang làm trên máy tính đã ghép: mở Studio của máy ấy ngay tại cuốn này, trong app máy này (webui/peer_studio.py). */
function PeerStudioChipLink({ device, book }: { device: string; book: string }) {
  return (
    <button
      type="button"
      onClick={() => window.location.assign(peerPage(window.location.search, device, `/studio/${book}`))}
      className="font-semibold underline underline-offset-2 hover:no-underline"
    >
      Mở Studio
    </button>
  );
}

/** Cuốn của máy khác mở Studio được ở máy ấy: máy tính đã ghép (không phải điện thoại), biết mã cuốn ở máy ấy. */
function peerStudioOf(book: ListenBook): { device: string; book: string } | null {
  const remote = typeof book.remote === "object" ? book.remote : null;
  return remote?.device && remote.book && remote.kind === "computer" ? { device: remote.device, book: remote.book } : null;
}

/** Trang mở Studio của máy khác mà chưa vào được: máy ấy không trả lời (tự nối lại khi nó trả lời), hay hai máy khác phiên bản. */
function PeerTrouble({ error, retry }: { error: unknown; retry: () => void }) {
  const silent = error instanceof ApiError && error.detail.unreachable === true;
  useEffect(() => (silent ? watchUntilBack(() => api<AppInfo>("/api/app").then(() => true), retry) : undefined), [silent, retry]);
  return (
    <EmptyState
      icon={Laptop}
      title={(error as Error).message || "Máy kia không trả lời"}
      className="mt-24"
      action={<Button onClick={() => window.location.assign(homePage(window.location.search))}>Về máy này</Button>}
    >
      <MotionRegion as="span">{silent ? "Studio tự mở khi máy ấy trả lời lại." : null}</MotionRegion>
    </EmptyState>
  );
}

function LibraryRoute() {
  const navigate = useNavigate();
  const { data: info } = useAppInfo();
  const openBookPath = useOpenBookPath();
  return (
    <>
      <LibraryScreen
        empty={<EmptyLibrary />}
        header={
          <div className="flex flex-wrap justify-end gap-2">
            <AddBookButton onBookFile={openBookPath} />
            <OpenBookFileButton />
          </div>
        }
        recap={<MorningRecap className="mt-6" />}
        onOpenUpcoming={info?.listenOnly ? undefined : (book) => navigate(`/studio/${book.id}`)}
      />
      <DropToAdd onBookFile={openBookPath} />
    </>
  );
}

/** Trang Studio khi thiết bị chỉ được nghe (Studio từ xa, remote_studio.py): nói vì sao và bật ở đâu. */
function StudioClosed({ children }: { children: ReactNode }) {
  const { data: info } = useAppInfo();
  const navigate = useNavigate();
  if (!info?.listenOnly) return <MotionRegion motionKey="open">{children}</MotionRegion>;
  // Cùng một câu ở mọi nơi mở Studio của máy khác: app máy tính (`peer`), trình duyệt và app điện thoại (`machine`).
  return (
    <MotionRegion motionKey="closed"><EmptyState
      icon={Clapperboard}
      title={listenOnlyLine(listenOnlyOwner(info))}
      className="mt-24"
      action={<Button onClick={() => navigate("/")}>Về Thư viện</Button>}
    >
      Sách của máy ấy vẫn nghe được ở Thư viện.
    </EmptyState></MotionRegion>
  );
}

function NotFound() {
  const navigate = useNavigate();
  return (
    <EmptyState
      icon={Compass}
      title="Không có trang này"
      className="mt-24"
      action={<Button onClick={() => navigate("/")}>Về Thư viện</Button>}
    >
      Đường dẫn có thể đã cũ hoặc gõ nhầm.
    </EmptyState>
  );
}

export function App() {
  const { data: info, error, refetch } = useAppInfo();
  const retry = useCallback(() => void refetch(), [refetch]);
  const { data: preferences, error: preferencesError, refetch: reloadPreferences } = usePreferences();
  const [voiceReady, setVoiceReady] = useState(false);
  useEffect(() => {
    if (!preferences || info?.remote) return;
    restoreDefaultVoice(preferences.readAloudVoice ?? "");
    setVoiceReady(true);
    return onDefaultVoiceChosen((voice) => {
      void api("/api/preferences", { method: "PUT", body: { readAloudVoice: voice } })
        .catch(() => toast.error("Chưa lưu được giọng mặc định. Bạn hãy chọn lại để thử lại."));
    });
  }, [info?.remote, preferences?.readAloudVoice]);
  useTheme(preferences?.theme ?? info?.theme);
  // Cài đặt › Phím tắt: bộ bắt phím của trình phát, Việc cần duyệt, Cần nghe lại đọc cờ này lúc có phím.
  useEffect(() => setLetterShortcuts(preferences?.letterShortcuts !== false), [preferences?.letterShortcuts]);
  // Chương có audio phát bằng <audio>; chương chỉ-có-chữ ("Nghe ngay") đi qua bộ máy đọc to (listen/readAloud.ts).
  const engine = useMemo(() => new RoutedEngine(new WebAudioEngine()), []);
  // Màn hẹp (Studio từ xa trên điện thoại): thông báo ở đầu màn như app Android - ở đáy nó đè trình phát nhỏ và thanh
  // điều hướng suốt 8 giây của nút "Hoàn tác" (soát UX 30-09).
  const narrow = useMediaQuery("(max-width: 639px)");
  // Trên điện thoại, hộp thoại đổi khoảng cách đáy; CSS tween offset để toast không nhảy.
  const modalOpen = useModalOpen();
  useFocusClearOfToasts();
  // Cửa sổ app Windows không mở được liên kết ngoài tự thân: nhờ máy chủ mở bằng trình duyệt mặc định (chỉ ở app đóng gói có hộp thoại).
  useEffect(() => {
    setExternalOpener(info?.dialogs ? (url) => api("/api/open-url", { method: "POST", body: { url } }).then(() => undefined) : null);
  }, [info?.dialogs]);
  // "Thêm sách từ file…" đọc file bằng đường dẫn trên máy này: thiết bị điều khiển từ xa (Studio từ xa) không có.
  // Giọng đọc của máy là việc của máy tính (/api/readaloud/* không mở cho thiết bị ở xa): không hỏi, khỏi một lời 403 ở mỗi trang sách.
  const source = useMemo(
    () => (info?.remote ? { ...httpSource, readAloudVoices: undefined } : { ...httpSource, textImport: desktopTextImport(Boolean(info?.dialogs)) }),
    [info?.remote, info?.dialogs],
  );
  if (!info && error && currentPeer()) return <MotionRegion motionKey="peer-error"><PeerTrouble error={error} retry={retry} /></MotionRegion>;
  if (info && !info.remote && !voiceReady && preferencesError) return <MotionRegion motionKey="preferences-error"><EmptyState icon={Laptop} title="Chưa đọc cài đặt" action={<Button onClick={() => void reloadPreferences()}>Thử lại</Button>}>Bạn hãy thử lại để nạp giọng mặc định trước khi nghe.</EmptyState></MotionRegion>;
  if (!info || (!info.remote && !voiceReady)) return <MotionRegion motionKey="loading" className="grid h-full place-items-center text-fg-3">Đang mở ABook…</MotionRegion>;
  return (
    <MotionRegion motionKey="ready" className="h-full" fadeThrough><TooltipProvider delayDuration={350} skipDelayDuration={150}>
      <SourceProvider source={source}>
        <PlayerProvider
          engine={engine}
          defaultRate={info.playbackRate}
          defaultVolume={info.volume}
          fadeSeconds={preferences?.sleepFadeSeconds ?? info.sleepFadeSeconds}
          extendMinutes={preferences?.sleepExtendMinutes ?? info.sleepExtendMinutes}
          safetyStopHours={preferences?.safetyStopHours ?? info.safetyStopHours}
          sleepSchedule={preferences ? preferences.sleepSchedule : info.sleepSchedule}
          autoRewind={preferences?.autoRewind !== false}
        >
          <ClipBridge>
            <MotionHashRouter>
              <OpenedBookListener local={!info.remote} />
              <UpdateListener />
              <ListenOnlyListener />
              {!info.remote && <StartupNotices notices={info.notices} />}
              {!info.remote && <VolumeSaver />}
              {!info.remote && <RemoveImportedHost />}
              <ExportJobHost kind="bookfile" />
              <ExportJobHost kind="m4b" />
              <ExportJobHost kind="mp3" />
              {!info.remote && <ExportJobHost kind="audiobook" />}
              {!info.remote && <ExportJobHost kind="projectfile" />}
              {!info.remote && <AudiobookDialogHost />}
              <Shell>
                <MotionPresence open={Boolean(!info.remote && info.libraryMoveRecovery)}>{info.libraryMoveRecovery && <LibraryMoveRecovery recovery={info.libraryMoveRecovery} />}</MotionPresence>
                <Routes>
                  <Route path="/" element={<LibraryRoute />} />
                  <Route
                    path="/book/:id"
                    element={
                      <BookScreen
                        extraActions={(book) =>
                          book.imported ? (
                            // Sách của máy khác (remote) thôi hiện khi gỡ máy ấy - không có gì để xoá ở đây; tải về máy được.
                            info.remote ? null : book.remote ? (
                              <RemoteDownloadMenuItem book={book} />
                            ) : (
                              <>
                                {/* Sách chỉ có chữ (EPUB / TXT) thành sách nói: giọng của máy đọc cả cuốn rồi ghép file. */}
                                {book.stage === "text" && <AudiobookMenuItem book={book} />}
                                {/* Sách nhận từ file `.abook` có audio: mang sang trình phát khác như trên điện thoại (soát a99 V4). */}
                                {book.stage !== "text" && (
                                  <>
                                    <Mp3MenuItem book={book} />
                                    <M4bMenuItem book={book} />
                                  </>
                                )}
                                <RemoveImportedMenuItem book={book} />
                              </>
                            )
                          ) : (
                            // Thiết bị chỉ được nghe (remote_studio.LISTEN_ROUTES): xuất file và Studio đều chỉ kết thúc bằng 403 - không hiện.
                            info.listenOnly ? null : (
                              <>
                                <BookFileMenuItem book={book} />
                                <Mp3MenuItem book={book} />
                                <M4bMenuItem book={book} />
                                <StudioMenuItem id={book.id} />
                              </>
                            )
                          )
                        }
                        studioLink={(book) => {
                          const peer = info.remote ? null : peerStudioOf(book);
                          return peer ? <PeerStudioChipLink {...peer} /> : book.imported || info.listenOnly ? null : <StudioChipLink id={book.id} />;
                        }}
                        notice={(book) => (book.remote && !info.remote ? <RemoteDownloadStatus book={book} /> : null)}
                        editing={
                          // Studio từ xa: đổi tên sách / tác giả / bìa / nhạc nền / tên chương / tên nhân vật chạy trên máy tính (ALLOWED); thiết bị
                          // chỉ được nghe thì không sửa gì.
                          info.listenOnly
                            ? false
                            : info.remote
                              ? { remote: listenOnlyOwner(info) }
                              : {
                                  pickFolder: info.dialogs ? () => pickFolder("Chọn nơi lưu file sách", "").catch(() => null) : undefined,
                                  onOpenStudio: (book) => window.location.assign(`#/studio/${book.id}?tab=music`),
                                }
                        }
                      />
                    }
                  />
                  <Route
                    path="/book/:id/read/:chapterId?"
                    element={
                      <ReaderScreen {...readerEditing(info)} />
                    }
                  />
                  <Route path="/studio" element={<StudioClosed><ProjectsScreen /></StudioClosed>} />
                  <Route path="/studio/new" element={<StudioClosed><NewProjectScreen /></StudioClosed>} />
                  <Route path="/studio/:id" element={<StudioClosed><ProjectScreen /></StudioClosed>} />
                  <Route path="/settings/:group?" element={<SettingsScreen />} />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </Shell>
            </MotionHashRouter>
          </ClipBridge>
        </PlayerProvider>
      </SourceProvider>
      <Toaster
        // Giữ góc khi mở hộp; màn hẹp đặt trên thanh phát và thanh điều hướng.
        position={narrow ? "bottom-center" : "top-right"}
        offset={{ top: "var(--toast-top, 16px)", right: 16, left: narrow ? 16 : 96, bottom: modalOpen && narrow ? 16 : "var(--toast-bottom, 96px)" }}
        // Dưới 600 px sonner bỏ `offset` mà dùng `mobileOffset` (mặc định 16 px) - thông báo từng đè lên thanh tab dưới ở 390 px.
        mobileOffset={{ top: "var(--toast-top, 16px)", right: 16, left: 16, bottom: modalOpen ? 16 : "var(--toast-bottom, 96px)" }}
        visibleToasts={2}
        // Thông báo vài giây che chữ thẻ bên dưới (soát UX a13 #17): nút ✕ để đọc xong là gạt đi ngay, không phải chờ hết hạn.
        closeButton
        // Nhãn trọn (mặc định sonner nối "alt+T" thô): phím tắt nói bằng chữ của app.
        customAriaLabel="Thông báo (Alt+T)"
        // Radix tắt chuột của mọi thứ ngoài hộp thoại đang mở: không có dòng này nút trong thông báo không bấm được.
        className="pointer-events-auto"
        toastOptions={{
          closeButtonAriaLabel: "Đóng thông báo",
          classNames: {
            toast: "!bg-panel !border !border-line !text-fg !shadow-float !rounded-xl",
            description: "!text-fg-2",
            // Nút trong thông báo ("Hoàn tác", "Ở lại đây") theo màu của app - mặc định của sonner là chữ tối trên nền
            // tối ở giao diện tối (soát UX 29-09).
            actionButton: "!bg-accent !text-accent-ink !font-semibold !rounded-lg",
            cancelButton: "!bg-hover !text-fg !rounded-lg",
            closeButton: "!bg-panel !border-line !text-fg-2",
          },
        }}
      />
    </TooltipProvider></MotionRegion>
  );
}

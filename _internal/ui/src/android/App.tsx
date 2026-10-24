import { App as CapacitorApp } from "@capacitor/app";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Clapperboard, Download, Headphones, Library, Link2, Settings, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { NavLink, Route, Routes, useLocation, useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { toast } from "@/shared/toast";
import type { ListenBook } from "@/listen/model";
import { EbookLibrary } from "./plugins";
import { BookScreen } from "@/listen/BookScreen";
import { ClipProvider } from "@/listen/clip";
import { AddBookButton, AddBookDialog } from "@/listen/AddBook";
import type { ImportChoice } from "@/listen/textImport";
import { LibraryScreen, useRestoreLastListening } from "@/listen/LibraryScreen";
import { ReaderScreen } from "@/listen/ReaderScreen";
import { NowPlaying, PlayerBar } from "@/listen/PlayerViews";
import { PlayerProvider, useNowPlaying, usePlayer } from "@/listen/player";
import { SourceProvider } from "@/listen/source";
import { pageFocusKey, usePageEnter, usePageFocus } from "@/shared/motion";
import { watchDownloads, watchEditsSync } from "./downloads";
import { watchReadAloud } from "./readAloud";
import { watchImports } from "./imports";
import { cn } from "@/shared/cn";
import { UNDO_SECONDS, toastRemoved } from "@/shared/trashUndo";
import { Button, Dialog, EmptyState, TooltipProvider, useFocusClearOfToasts } from "@/shared/ui";
import { androidSource } from "./androidSource";
import { LibraryDownloads } from "./LibraryDownloads";
import { StudioScreen } from "./StudioScreen";
import { AudiobookPhoneDialogHost, ExportAudiobookMenuItem, watchAudiobookExports } from "./ExportAudiobook";
import { ExportM4bMenuItem, M4bMusicDialogHost, watchM4bExports } from "./ExportM4b";
import { ExportMp3MenuItem, Mp3MusicDialogHost, watchMp3Exports } from "./ExportMp3";
import { ExportRevisionNotice } from "./ExportRevisions";
import { PhoneHandOffButton, RemotePlayerBars } from "./RemotePlayers";
import { MorningRecap } from "@/listen/MorningRecap";
import { NativeAudioEngine } from "./nativeEngine";
import { SettingsScreen } from "./SettingsScreen";
import { useOldSaveNotice } from "./oldSaveList";
import { StudioChipHost } from "./StudioOpen";
import { UpdateNotice } from "./UpdateNotice";
import { applySenses, applyTheme, loadSettings, syncSettings } from "./settings";
import { backStep, dismissTopLayer, historyIndex } from "./backLayers";
import { useBookBytes, type RemovableFromPhone } from "./storage";
import { formatSize } from "@/shared/format";
import { MotionHashRouter } from "@/shared/MotionRouter";

// Vỏ Android: cùng các màn hình Nghe với máy tính, bố cục một tay - điều hướng dưới đáy, trình phát thu nhỏ ngay
// trên thanh điều hướng, nút Back của máy đóng menu / hộp thoại đang mở, rồi màn hình đang nghe, rồi mới lùi trang.

/** Theo dõi mọi lượt tải từ lúc app mở, không phụ thuộc màn đang xem (android/downloads.ts). */
function DownloadWatcher() {
  const client = useQueryClient();
  useEffect(() => watchDownloads(client), [client]);
  useEffect(() => watchEditsSync(client), [client]);
  useEffect(() => watchMp3Exports(), []);
  useEffect(() => watchM4bExports(), []);
  useEffect(() => watchAudiobookExports(), []);
  // Chương chỉ-có-chữ đang được lõi đọc to: mốc câu / chữ lõi báo đi vào kịch bản chữ của màn đọc (android/readAloud.ts).
  useEffect(() => watchReadAloud(client), [client]);
  return null;
}

/** Mở file từ ngoài app (android/imports.ts): file sách .abook báo "Đã thêm sách" kèm nút mở trang sách; file EPUB / DOCX / PDF / TXT mở
 *  hộp "Thêm sách từ file" ở bước xem trước. */
function ImportWatcher() {
  const client = useQueryClient();
  const navigate = useNavigate();
  const [incoming, setIncoming] = useState<ImportChoice | null>(null);
  useEffect(() => watchImports(client, (bookId) => navigate(`/book/${bookId}`), setIncoming), [client, navigate]);
  return <AddBookDialog open={incoming !== null} initial={incoming} onOpenChange={(open) => !open && setIncoming(null)} />;
}

function BackButton() {
  const navigate = useNavigate();
  const location = useLocation();
  // Đăng ký MỘT lần, đọc trang hiện tại qua ref: trước đây mỗi lần đổi trang lại gỡ / gắn listener (bất đồng bộ), Back bấm đúng lúc ấy rơi vào khoảng trống.
  const now = useRef({ navigate, pathname: location.pathname });
  now.current = { navigate, pathname: location.pathname };
  useEffect(() => {
    const handle = CapacitorApp.addListener("backButton", () => {
      // Lớp trên cùng trước (android/backLayers.ts): hộp / menu Radix, lớp tự đăng ký (màn Đang nghe, panel, bước con…), thông báo có nút.
    if (dismissTopLayer()) return;
      const step = backStep(now.current.pathname, historyIndex());
      if (step.kind === "history") now.current.navigate(-1);
      else if (step.kind === "replace") now.current.navigate(step.to, { replace: true });
      else void CapacitorApp.minimizeApp();
    });
    return () => void handle.then((listener) => listener.remove());
  }, []);
  return null;
}

/** `also`: đường không nằm dưới `to` nhưng vẫn thuộc tab này - trang sách và trang đọc mở từ Thư viện nên tô Thư viện
 *  (soát 24-10 T16: ở trang sách thanh đáy không tô mục nào). */
function Tab({ to, icon: Icon, label, also }: { to: string; icon: typeof Library; label: string; also?: string }) {
  const { pathname } = useLocation();
  const within = also !== undefined && pathname.startsWith(also);
  return (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        cn(
          "flex flex-1 flex-col items-center justify-center gap-1 text-[0.6875rem] font-medium transition-colors duration-(--motion-medium) ease-standard",
          isActive || within ? "text-accent-text" : "text-fg-2",
        )
      }
    >
      {({ isActive }) => (
        <>
          {/* Tab vừa chọn: biểu tượng nhún nhẹ lên, màu chuyển dần (trang đổi bằng "fade through" - MotionHashRouter). */}
          <Icon className={cn("motion-tab-icon glyph-22 transition-transform duration-(--motion-medium) ease-decelerate", (isActive || within) && "-translate-y-px scale-110")} strokeWidth={1.9} />
          {label}
        </>
      )}
    </NavLink>
  );
}

function MobileShell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const { expanded, setExpanded } = useNowPlaying();
  useRestoreLastListening();
  const expandedNow = useRef(expanded);
  expandedNow.current = expanded;
  useEffect(() => {
    if (expandedNow.current) setExpanded(false);
  }, [pathname, setExpanded]);
  const main = useRef<HTMLElement | null>(null);
  // Điện thoại giữ chỗ cuộn: thư viện -> sách -> quay lại không mất chỗ đang xem.
  usePageEnter(main, pathname, { resetScroll: false });
  usePageFocus(main, pageFocusKey(pathname));
  return (
    <div className="relative flex h-full flex-col" style={{ paddingTop: "env(safe-area-inset-top)" }}>
      {/* Màn "Đang nghe" phủ kín: mọi thứ nằm dưới nó cũng ra khỏi cây trợ năng và Tab (inert), không chỉ khuất mắt. */}
      <main ref={main} inert={expanded} className="page-motion min-h-0 flex-1 overflow-y-auto overscroll-contain">{children}</main>
      <div className="contents" inert={expanded}>
        <RemotePlayerBars localBar={<PlayerBar compact />} />
      </div>
      <nav
        inert={expanded}
        className="flex h-16 shrink-0 border-t border-line bg-bg"
        style={{ paddingBottom: "env(safe-area-inset-bottom)", boxSizing: "content-box" }}
        aria-label="Điều hướng"
      >
        <Tab to="/" icon={Library} label="Thư viện" also="/book/" />
        <Tab to="/studio" icon={Clapperboard} label="Studio" />
        <Tab to="/settings" icon={Settings} label="Cài đặt" />
      </nav>
      <NowPlaying mobile actions={<PhoneHandOffButton />} />
    </div>
  );
}

function EmptyLibrary() {
  const navigate = useNavigate();
  return (
    <EmptyState
      icon={Headphones} // như máy tính: biểu tượng nói "nghe", không phải "tải xuống" (việc ở đây là thêm file - soát 24-10 T05)
      title="Chưa có sách trên máy"
      className="mt-10"
      action={
        <div className="flex flex-col items-center gap-2">
          {/* Người mới thường có sẵn một file truyện mà chưa có ABook trên máy tính: nghe ngay là việc chính (soát UX a7, như máy tính). */}
          <AddBookButton variant="primary" size="lg" />
          <Button variant="ghost" icon={Link2} onClick={() => navigate("/settings/devices")}>
            Nối máy
          </Button>
        </div>
      }
    >
      Thêm sách của bạn để bắt đầu nghe.
    </EmptyState>
  );
}

function LibraryPage() {
  useOldSaveNotice();
  return <LibraryDownloads>{(bookExtras, additionalBooks) => <LibraryScreen bookExtras={bookExtras} additionalBooks={additionalBooks} empty={<EmptyLibrary />} header={<AddBookButton />} recap={<MorningRecap className="mt-5" />} />}</LibraryDownloads>;
}

/** Sách đang nghe thẳng từ máy tính: tải hẳn về để nghe cả khi không có mạng (tiến độ hiện trên bìa ở Thư viện). */
function DownloadMenuItem({ book }: { book: ListenBook }) {
  return (
    <DropdownMenu.Item
      onSelect={() => {
        toast("Đang tải về máy", { description: "Xem tiến độ trên bìa ở Thư viện" });
        void EbookLibrary.download({ bookId: book.id }).catch((error: Error) => toast.error("Không tải được", { description: error.message }));
      }}
      className="flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[highlighted]:bg-hover"
    >
      <Download className="size-4" /> Tải về máy
    </DropdownMenu.Item>
  );
}

/** Sách đã nằm trên điện thoại: xoá bản ấy để lấy lại chỗ trống (soát UX 29-09: EbookLibrary.deleteBook có sẵn mà không
 *  nút nào gọi - sách tải về chỉ có thêm, không bớt được). Hộp xác nhận ở RemoveFromPhoneHost, ngoài menu. */
function RemoveFromPhoneMenuItem({ book }: { book: ListenBook }) {
  const bytes = useBookBytes(book.id);
  return (
    <DropdownMenu.Item
      onSelect={() => window.dispatchEvent(new CustomEvent<RemovableFromPhone>("abook-remove-from-phone", { detail: { id: book.id, title: book.title } }))}
      className="flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm text-danger outline-none data-[highlighted]:bg-hover"
    >
      <Trash2 className="size-4" /> Xoá khỏi điện thoại…
      {bytes !== undefined && <span className="ml-auto text-xs text-fg-2">Chiếm {formatSize(bytes)}</span>}
    </DropdownMenu.Item>
  );
}

function RemoveFromPhoneHost() {
  const [book, setBook] = useState<RemovableFromPhone | null>(null);
  const [busy, setBusy] = useState(false);
  const client = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const player = usePlayer();
  const bytes = useBookBytes(book?.id ?? "");
  useEffect(() => {
    const listener = (event: Event) => setBook((event as CustomEvent<RemovableFromPhone>).detail);
    window.addEventListener("abook-remove-from-phone", listener);
    return () => window.removeEventListener("abook-remove-from-phone", listener);
  }, []);
  const remove = async () => {
    if (!book) return;
    setBusy(true);
    if (player.track?.bookId === book.id) player.close();
    try {
      const { undo } = await EbookLibrary.deleteBook({ id: book.id });
      setBook(null);
      // Xoá từ danh sách dung lượng ở Cài đặt › Thiết bị thì ở lại đó; chỉ rời trang của chính cuốn vừa xoá.
      if (location.pathname.startsWith(`/book/${book.id}`)) navigate("/", { replace: true });
      void client.invalidateQueries();
      // "Hoàn tác" (TrashPending.kt): cuốn nằm chờ vài chục giây rồi mới xoá hẳn - điện thoại không có Thùng rác.
      toastRemoved({
        message: book.partial ? `Đã xoá phần đã tải của “${book.title}”` : `Đã xoá “${book.title}” khỏi điện thoại`,
        title: book.title,
        undo: undo ?? undefined,
        note: "",
        to: "gone",
        restore: (token) => EbookLibrary.undoDelete({ token }),
        onRestored: () => void client.invalidateQueries(),
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
      title={book?.partial ? `Xoá phần đã tải của “${book.title}”?` : `Xoá “${book?.title ?? ""}” khỏi điện thoại?`}
      description={
        book?.partial
          ? `${bytes !== undefined ? `Lấy lại ${formatSize(bytes)}. ` : ""}Phần tải dở; lần sau tải lại từ đầu, sách vẫn ở máy tính. Hoàn tác được trong ${UNDO_SECONDS} giây.`
          : `${bytes !== undefined ? `Lấy lại ${formatSize(bytes)}. ` : ""}Xoá hẳn khỏi điện thoại; Hoàn tác được trong ${UNDO_SECONDS} giây. Sách từ máy đã ghép thì tải lại được.`
      }
    >
      <div className="dialog-actions">
        <Button variant="ghost" onClick={() => setBook(null)}>
          Để sau
        </Button>
        <Button variant="danger" icon={Trash2} loading={busy} onClick={() => void remove()}>
          {book?.partial ? "Xoá phần đã tải" : "Xoá khỏi điện thoại"}
        </Button>
      </div>
    </Dialog>
  );
}

function ClipBridge({ children }: { children: ReactNode }) {
  const player = usePlayer();
  return <ClipProvider onStart={() => player.playing && player.toggle()}>{children}</ClipProvider>;
}

export function AndroidApp() {
  const engine = useMemo(() => new NativeAudioEngine(), []);
  useFocusClearOfToasts();
  // Lần đồng bộ tuỳ chọn với native xong (mới hơn bản WebView thì lấy của native): hiện lại các màn đọc tuỳ chọn lúc dựng (soát a100 T3).
  const [synced, setSynced] = useState(0);
  useEffect(() => {
    applyTheme(loadSettings().theme);
    applySenses(loadSettings());
    void syncSettings().then((settings) => {
      applyTheme(settings.theme);
      applySenses(settings);
      setSynced((count) => count + 1);
    });
  }, []);
  // "Theo hệ thống" phải theo cả khi đang mở app: Activity khai uiMode trong configChanges nên KHÔNG dựng lại khi
  // điện thoại chuyển sáng/tối (vd tự tối lúc chiều) - trước đây app giữ nguyên giao diện cũ tới lần mở sau.
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const follow = () => {
      if (loadSettings().theme === "system") applyTheme("system", true);
    };
    media.addEventListener("change", follow);
    return () => media.removeEventListener("change", follow);
  }, []);
  return (
    <TooltipProvider delayDuration={500}>
      <SourceProvider source={androidSource}>
        <PlayerProvider engine={engine} keyboard={false} fadeSeconds={loadSettings().sleepFadeSeconds} extendMinutes={loadSettings().sleepExtendMinutes}>
          <ClipBridge>
            <MotionHashRouter>
              <BackButton />
              <DownloadWatcher />
              <UpdateNotice />
              <ImportWatcher />
              <RemoveFromPhoneHost />
              <AudiobookPhoneDialogHost />
              <M4bMusicDialogHost />
              <Mp3MusicDialogHost />
              <MobileShell>
                <Routes>
                  <Route path="/" element={<LibraryPage />} />
                  <Route
                    path="/book/:id"
                    element={
                      <BookScreen
                        studioLink={(book) => <StudioChipHost book={book} />}
                        notice={(book) => <ExportRevisionNotice book={book} />}
                        extraActions={(book) =>
                          book.remote ? (
                            <DownloadMenuItem book={book} />
                          ) : (
                            <>
                              <ExportAudiobookMenuItem book={book} />
                              <ExportMp3MenuItem book={book} />
                              <ExportM4bMenuItem book={book} />
                              <RemoveFromPhoneMenuItem book={book} />
                            </>
                          )
                        }
                      />
                    }
                  />
                  <Route path="/book/:id/read/:chapterId?" element={<ReaderScreen />} />
                  <Route path="/studio" element={<StudioScreen />} />
                  <Route path="/settings/:group?" element={<SettingsScreen key={synced} />} />
                </Routes>
              </MobileShell>
            </MotionHashRouter>
          </ClipBridge>
        </PlayerProvider>
      </SourceProvider>
      <Toaster
        position="top-center"
        // Màn đọc: thông báo nằm dưới thanh đầu (ReaderScreen đặt --toast-top) - không che nút "Nghe từ đây" (soát a70).
        mobileOffset={{ top: "var(--toast-top, 16px)", right: 16, left: 16, bottom: 16 }}
        offset={{ top: "var(--toast-top, 24px)" }}
        // Nhãn trọn của vùng thông báo: mặc định sonner nối thêm phím tắt "alt+T" - vô nghĩa trên điện thoại (TalkBack đọc ra, soát a66).
        customAriaLabel="Thông báo"
        // Radix tắt chuột của mọi thứ ngoài hộp thoại đang mở: không có dòng này nút trong thông báo không bấm được.
        className="pointer-events-auto"
        toastOptions={{
          closeButtonAriaLabel: "Đóng thông báo",
          classNames: {
            toast: "!bg-panel !border !border-line !text-fg !rounded-xl",
            description: "!text-fg-2",
            actionButton: "!bg-accent !text-accent-ink !font-semibold !rounded-lg",
            cancelButton: "!bg-hover !text-fg !rounded-lg",
          },
        }}
      />
    </TooltipProvider>
  );
}

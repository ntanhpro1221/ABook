import { App as CapacitorApp } from "@capacitor/app";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Download, FileAudio, Library, Settings } from "lucide-react";
import { useEffect, useMemo, useRef, type ReactNode } from "react";
import { HashRouter, NavLink, Route, Routes, useLocation, useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Toaster, toast } from "sonner";
import type { ListenBook } from "@/listen/model";
import { EbookLibrary } from "./plugins";
import { BookScreen } from "@/listen/BookScreen";
import { ClipProvider } from "@/listen/clip";
import { LibraryScreen, useRestoreLastListening } from "@/listen/LibraryScreen";
import { ReaderScreen } from "@/listen/ReaderScreen";
import { NowPlaying, PlayerBar } from "@/listen/PlayerViews";
import { PlayerProvider, useNowPlaying, usePlayer } from "@/listen/player";
import { SourceProvider } from "@/listen/source";
import { usePageEnter } from "@/shared/motion";
import { watchDownloads } from "./downloads";
import { pickBookFile, watchImports } from "./imports";
import { cn } from "@/shared/cn";
import { Button, EmptyState, TooltipProvider } from "@/shared/ui";
import { androidSource } from "./androidSource";
import { DevicesScreen } from "./DevicesScreen";
import { MorningRecap } from "@/listen/MorningRecap";
import { NativeAudioEngine } from "./nativeEngine";
import { SettingsScreen } from "./SettingsScreen";
import { applyTheme, loadSettings, pushSettings } from "./settings";

// Vỏ Android: cùng các màn hình Nghe với máy tính, bố cục một tay - điều hướng dưới đáy, trình phát thu nhỏ ngay
// trên thanh điều hướng, nút Back của máy đóng màn hình đang nghe trước rồi mới lùi trang.

/** Theo dõi mọi lượt tải từ lúc app mở, không phụ thuộc màn đang xem (android/downloads.ts). */
function DownloadWatcher() {
  const client = useQueryClient();
  useEffect(() => watchDownloads(client), [client]);
  return null;
}

/** Mở file sách .abook từ ngoài app (android/imports.ts): báo "Đã thêm sách", nút mở trang sách. */
function ImportWatcher() {
  const client = useQueryClient();
  const navigate = useNavigate();
  useEffect(() => watchImports(client, (bookId) => navigate(`/book/${bookId}`)), [client, navigate]);
  return null;
}

function BackButton() {
  const navigate = useNavigate();
  const location = useLocation();
  const { expanded, setExpanded } = useNowPlaying();
  useEffect(() => {
    const handle = CapacitorApp.addListener("backButton", () => {
      if (expanded) setExpanded(false);
      else if (location.pathname !== "/") navigate(-1);
      else void CapacitorApp.minimizeApp();
    });
    return () => void handle.then((listener) => listener.remove());
  }, [navigate, location.pathname, expanded, setExpanded]);
  return null;
}

function Tab({ to, icon: Icon, label }: { to: string; icon: typeof Library; label: string }) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        cn("flex flex-1 flex-col items-center justify-center gap-1 text-[11px] font-medium", isActive ? "text-accent-text" : "text-fg-3")
      }
    >
      <Icon className="size-[22px]" strokeWidth={1.9} />
      {label}
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
  usePageEnter(main, pathname);
  return (
    <div className="relative flex h-full flex-col" style={{ paddingTop: "env(safe-area-inset-top)" }}>
      <main ref={main} className="min-h-0 flex-1 overflow-y-auto overscroll-contain">{children}</main>
      <PlayerBar compact />
      <nav
        className="flex h-16 shrink-0 border-t border-line bg-panel"
        style={{ paddingBottom: "env(safe-area-inset-bottom)", boxSizing: "content-box" }}
        aria-label="Điều hướng"
      >
        <Tab to="/" icon={Library} label="Thư viện" />
        <Tab to="/devices" icon={Download} label="Tải sách" />
        <Tab to="/settings" icon={Settings} label="Cài đặt" />
      </nav>
      <NowPlaying mobile />
    </div>
  );
}

function EmptyLibrary() {
  const navigate = useNavigate();
  return (
    <EmptyState
      icon={Download}
      title="Chưa có sách trên máy"
      className="mt-10"
      action={
        <div className="flex flex-col items-center gap-2">
          <Button variant="primary" size="lg" icon={Download} onClick={() => navigate("/devices")}>
            Tải sách từ máy tính
          </Button>
          <Button variant="ghost" icon={FileAudio} onClick={() => void pickBookFile()}>
            Mở file sách (.abook)
          </Button>
        </div>
      }
    >
      Kết nối với Ebook Reader trên máy tính qua Wi-Fi rồi tải sách về - nghe được cả khi không có mạng. Có file sách
      .abook (bạn bè gửi, tải về)? Mở nó bằng app là sách vào Thư viện.
    </EmptyState>
  );
}

function LibraryPage() {
  return <LibraryScreen empty={<EmptyLibrary />} recap={<MorningRecap className="mt-5" />} />;
}

/** Sách đang nghe thẳng từ máy tính: tải hẳn về để nghe cả khi không có mạng (tiến độ hiện ở tab Tải sách). */
function DownloadMenuItem({ book }: { book: ListenBook }) {
  return (
    <DropdownMenu.Item
      onSelect={() => {
        toast("Đang tải về máy", { description: "Xem tiến độ ở tab Tải sách" });
        void EbookLibrary.download({ bookId: book.id }).catch((error: Error) => toast.error("Không tải được", { description: error.message }));
      }}
      className="flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[highlighted]:bg-hover"
    >
      <Download className="size-4" /> Tải về máy
    </DropdownMenu.Item>
  );
}

function ClipBridge({ children }: { children: ReactNode }) {
  const player = usePlayer();
  return <ClipProvider onStart={() => player.playing && player.toggle()}>{children}</ClipProvider>;
}

export function AndroidApp() {
  const engine = useMemo(() => new NativeAudioEngine(), []);
  useEffect(() => {
    const settings = loadSettings();
    applyTheme(settings.theme);
    void pushSettings(settings);
  }, []);
  // "Theo hệ thống" phải theo cả khi đang mở app: Activity khai uiMode trong configChanges nên KHÔNG dựng lại khi
  // điện thoại chuyển sáng/tối (vd tự tối lúc chiều) - trước đây app giữ nguyên giao diện cũ tới lần mở sau.
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const follow = () => {
      if (loadSettings().theme === "system") applyTheme("system");
    };
    media.addEventListener("change", follow);
    return () => media.removeEventListener("change", follow);
  }, []);
  return (
    <TooltipProvider delayDuration={500}>
      <SourceProvider source={androidSource}>
        <PlayerProvider engine={engine} keyboard={false} fadeSeconds={loadSettings().sleepFadeSeconds} extendMinutes={loadSettings().sleepExtendMinutes}>
          <ClipBridge>
            <HashRouter>
              <BackButton />
              <DownloadWatcher />
              <ImportWatcher />
              <MobileShell>
                <Routes>
                  <Route path="/" element={<LibraryPage />} />
                  <Route path="/book/:id" element={<BookScreen extraActions={(book) => (book.remote ? <DownloadMenuItem book={book} /> : null)} />} />
                  <Route path="/book/:id/read/:chapterId?" element={<ReaderScreen />} />
                  <Route path="/devices" element={<DevicesScreen />} />
                  <Route path="/settings" element={<SettingsScreen />} />
                </Routes>
              </MobileShell>
            </HashRouter>
          </ClipBridge>
        </PlayerProvider>
      </SourceProvider>
      <Toaster position="top-center" containerAriaLabel="Thông báo" toastOptions={{ classNames: { toast: "!bg-panel !border !border-line !text-fg !rounded-xl", description: "!text-fg-2" } }} />
    </TooltipProvider>
  );
}

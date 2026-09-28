import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useQueryClient } from "@tanstack/react-query";
import { BookPlus, Clapperboard, Compass, FileAudio, FolderDown, Headphones } from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { HashRouter, Route, Routes, useNavigate } from "react-router";
import { Toaster, toast } from "sonner";
import { BookScreen } from "@/listen/BookScreen";
import { ClipProvider } from "@/listen/clip";
import { WebAudioEngine } from "@/listen/engine";
import { LibraryScreen } from "@/listen/LibraryScreen";
import { MorningRecap } from "@/listen/MorningRecap";
import { ReaderScreen } from "@/listen/ReaderScreen";
import { PlayerProvider, usePlayer } from "@/listen/player";
import { SourceProvider } from "@/listen/source";
import { Button, EmptyState, TooltipProvider } from "@/shared/ui";
import type { ListenBook } from "@/listen/model";
import { coverArtwork } from "@/shared/cover";
import { api } from "@/studio/api";
import { pickFolder, useAppInfo, usePreferences } from "@/studio/data";
import { NewProjectScreen } from "@/studio/NewProjectScreen";
import { ProjectScreen } from "@/studio/ProjectScreen";
import { ProjectsScreen } from "@/studio/ProjectsScreen";
import { httpSource } from "./httpSource";
import { SettingsScreen } from "./SettingsScreen";
import { Shell } from "./Shell";

function useTheme(theme: string | undefined) {
  useEffect(() => {
    const root = document.documentElement;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      root.dataset.theme = theme === "dark" || (theme !== "light" && media.matches) ? "dark" : "light";
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

function EmptyLibrary() {
  const navigate = useNavigate();
  return (
    <EmptyState
      icon={Headphones}
      title="Chưa có sách để nghe"
      className="mt-12 rounded-2xl border border-dashed border-line"
      action={
        <div className="flex flex-wrap justify-center gap-2">
          <Button variant="primary" size="lg" icon={BookPlus} onClick={() => navigate("/studio/new")}>
            Tạo sách nói đầu tiên
          </Button>
          <OpenBookFileButton variant="ghost" />
        </div>
      }
    >
      Sách xuất hiện ở đây ngay khi chương đầu tiên thu xong - không cần chờ cả cuốn. Có file sách (.abook) từ máy khác
      thì mở thẳng.
    </EmptyState>
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

/** Xuất thư mục MP3 có tên sách, tên chương, bìa - nghe được bằng mọi trình phát khác. */
function ExportMenuItem({ book }: { book: ListenBook }) {
  const { data: info } = useAppInfo();
  const run = async () => {
    let target = "";
    if (info?.dialogs) {
      const picked = await pickFolder("Chọn nơi lưu bản xuất", "").catch(() => null);
      if (!picked) return;
      target = picked;
    }
    const pending = toast.loading("Đang xuất sách…", { description: `${book.chaptersAvailable} chương` });
    try {
      const result = await api<{ folder: string; files: number; chaptersTotal: number }>(`/api/books/${book.id}/export`, {
        method: "POST",
        body: { target, cover: coverArtwork(book.title) },
      });
      toast.success(`Đã xuất ${result.files} chương`, {
        id: pending,
        description: result.files < result.chaptersTotal ? "Các chương chưa làm xong sẽ không có trong bản xuất." : result.folder,
        // Studio từ xa: thư mục nằm trên máy tính, không mở được từ máy đang xem.
        action: info?.remote ? undefined : {
          label: "Mở thư mục",
          onClick: () => void api("/api/reveal-export", { method: "POST", body: { folder: result.folder } }),
        },
      });
    } catch (error) {
      toast.error("Không xuất được", { id: pending, description: (error as Error).message });
    }
  };
  return (
    <DropdownMenu.Item
      onSelect={() => void run()}
      className="flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[highlighted]:bg-hover"
    >
      <FolderDown className="size-4" /> Xuất MP3 để nghe ở app khác
    </DropdownMenu.Item>
  );
}

/** Một cuốn trong một file của app (webui/bookfile.py): bìa, chữ có tag, audio, nhân vật - mở bằng app ở máy khác. */
function BookFileMenuItem({ book }: { book: ListenBook }) {
  const { data: info } = useAppInfo();
  const run = async () => {
    let target = "";
    if (info?.dialogs) {
      const picked = await pickFolder("Chọn nơi lưu file sách", "").catch(() => null);
      if (!picked) return;
      target = picked;
    }
    const pending = toast.loading("Đang đóng gói sách…", { description: `${book.chaptersAvailable} chương` });
    try {
      const result = await api<{ file: string; folder: string; size: number }>(`/api/books/${book.id}/bookfile`, {
        method: "POST",
        body: { target },
      });
      toast.success("Đã xuất file sách", {
        id: pending,
        description: `${result.file} · ${Math.round(result.size / 1048576)} MB`,
        action: info?.remote ? undefined : {
          label: "Mở thư mục",
          onClick: () => void api("/api/reveal-export", { method: "POST", body: { folder: result.folder } }),
        },
      });
    } catch (error) {
      toast.error("Không xuất được file sách", { id: pending, description: (error as Error).message });
    }
  };
  return (
    <DropdownMenu.Item
      onSelect={() => void run()}
      className="flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[highlighted]:bg-hover"
    >
      <FileAudio className="size-4" /> Xuất file sách (mở bằng app ở máy khác)
    </DropdownMenu.Item>
  );
}

/** Kết quả mở một file sách (`POST /api/listen/open-book-file`, hay cửa sổ app khi bấm đúp file .abook - desktop.py). */
interface OpenedBook {
  id: string | null;
  how?: "new" | "existing" | "updated" | "project";
  error?: string;
  file?: string;
}

const OPENED_SAID: Record<NonNullable<OpenedBook["how"]>, [string, string | undefined]> = {
  new: ["Đã thêm sách vào thư viện", "Sách đã chép vào thư viện - xoá file gốc cũng không sao."],
  existing: ["Cuốn này đã có trong thư viện", undefined],
  updated: ["Đã cập nhật lên bản nhiều chương hơn", "Chỗ đang nghe, dấu trang vẫn giữ nguyên."],
  project: ["Đây là sách do Studio máy này làm", "Mở đúng cuốn ấy, không chép thêm bản nào."],
};

function useOpenedBook() {
  const navigate = useNavigate();
  const client = useQueryClient();
  return useCallback(
    (result: OpenedBook) => {
      if (result.error) {
        toast.error("Không mở được file sách", { description: result.file ? `${result.file}: ${result.error}` : result.error });
        return;
      }
      if (!result.id) return;
      void client.invalidateQueries({ queryKey: ["listen"] });
      navigate(`/book/${result.id}`);
      const [title, description] = OPENED_SAID[result.how ?? "new"];
      toast.success(title, { description });
    },
    [client, navigate],
  );
}

/** Cửa sổ app mở một file sách (bấm đúp .abook trong Explorer, kể cả khi app đang mở): desktop.py báo qua sự kiện. */
function OpenedBookListener() {
  const opened = useOpenedBook();
  useEffect(() => {
    const listener = (event: Event) => opened((event as CustomEvent<OpenedBook>).detail);
    window.addEventListener("abook-opened", listener);
    return () => window.removeEventListener("abook-opened", listener);
  }, [opened]);
  return null;
}

/** App Windows đóng gói: vỏ tìm thấy bản mới sau khi trang đã mở - đọc lại thông tin app để hiện nút "Cập nhật";
 *  tải bản mới hỏng (mất mạng, chữ ký sai) thì nói rõ, bấm lại được. */
function UpdateListener() {
  const client = useQueryClient();
  useEffect(() => {
    const found = () => void client.invalidateQueries({ queryKey: ["app"] });
    const failed = (event: Event) =>
      toast.error("Chưa tải được bản mới", {
        description: `${(event as CustomEvent<string>).detail} - kiểm tra mạng rồi bấm Cập nhật lần nữa.`,
      });
    window.addEventListener("abook-update", found);
    window.addEventListener("abook-update-failed", failed);
    return () => {
      window.removeEventListener("abook-update", found);
      window.removeEventListener("abook-update-failed", failed);
    };
  }, [client]);
  return null;
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
    <Button variant={variant} icon={FileAudio} disabled={busy} onClick={() => void run()}>
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

function LibraryRoute() {
  const navigate = useNavigate();
  const { data: info } = useAppInfo();
  return (
    <LibraryScreen
      empty={<EmptyLibrary />}
      header={<OpenBookFileButton />}
      recap={<MorningRecap className="mt-6" />}
      onOpenUpcoming={info?.listenOnly ? undefined : (book) => navigate(`/studio/${book.id}`)}
    />
  );
}

/** Trang Studio khi thiết bị chỉ được nghe (Studio từ xa, remote_studio.py): nói vì sao và bật ở đâu. */
function StudioClosed({ children }: { children: ReactNode }) {
  const { data: info } = useAppInfo();
  const navigate = useNavigate();
  if (!info?.listenOnly) return <>{children}</>;
  return (
    <EmptyState
      icon={Clapperboard}
      title="Thiết bị này chỉ nghe sách"
      className="mt-24"
      action={<Button onClick={() => navigate("/")}>Về Thư viện</Button>}
    >
      Muốn làm sách từ đây: trên máy tính, Cài đặt → Điện thoại và thiết bị → bật “Cho phép điều khiển sản xuất từ thiết bị
      đã ghép” và “Điều khiển sản xuất” ở dòng của thiết bị này, rồi tải lại trang.
    </EmptyState>
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
  const { data: info } = useAppInfo();
  const { data: preferences } = usePreferences();
  useTheme(preferences?.theme ?? info?.theme);
  const engine = useMemo(() => new WebAudioEngine(), []);
  if (!info) return <div className="grid h-full place-items-center text-fg-3">Đang mở ABook…</div>;
  return (
    <TooltipProvider delayDuration={350} skipDelayDuration={150}>
      <SourceProvider source={httpSource}>
        <PlayerProvider
          engine={engine}
          defaultRate={info.playbackRate}
          defaultVolume={info.volume}
          fadeSeconds={preferences?.sleepFadeSeconds ?? info.sleepFadeSeconds}
          extendMinutes={preferences?.sleepExtendMinutes ?? info.sleepExtendMinutes}
          safetyStopHours={preferences?.safetyStopHours ?? info.safetyStopHours}
          sleepSchedule={preferences ? preferences.sleepSchedule : info.sleepSchedule}
        >
          <ClipBridge>
            <HashRouter>
              <OpenedBookListener />
              <UpdateListener />
              <Shell>
                <Routes>
                  <Route path="/" element={<LibraryRoute />} />
                  <Route
                    path="/book/:id"
                    element={
                      <BookScreen
                        extraActions={(book) =>
                          book.imported ? null : (
                            <>
                              <BookFileMenuItem book={book} />
                              <ExportMenuItem book={book} />
                              <StudioMenuItem id={book.id} />
                            </>
                          )
                        }
                        studioLink={(book) => (book.imported ? null : <StudioChipLink id={book.id} />)}
                      />
                    }
                  />
                  <Route path="/book/:id/read/:chapterId?" element={<ReaderScreen />} />
                  <Route path="/studio" element={<StudioClosed><ProjectsScreen /></StudioClosed>} />
                  <Route path="/studio/new" element={<StudioClosed><NewProjectScreen /></StudioClosed>} />
                  <Route path="/studio/:id" element={<StudioClosed><ProjectScreen /></StudioClosed>} />
                  <Route path="/settings" element={<SettingsScreen />} />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </Shell>
            </HashRouter>
          </ClipBridge>
        </PlayerProvider>
      </SourceProvider>
      <Toaster
        position="bottom-right"
        // Đáy nâng lên khi có thanh "Đang phát trên điện thoại" (RemotePhone.tsx đặt --toast-bottom).
        offset={{ top: 96, right: 96, left: 96, bottom: "var(--toast-bottom, 96px)" }}
        containerAriaLabel="Thông báo"
        toastOptions={{
          classNames: {
            toast: "!bg-panel !border !border-line !text-fg !shadow-float !rounded-xl",
            description: "!text-fg-2",
          },
        }}
      />
    </TooltipProvider>
  );
}

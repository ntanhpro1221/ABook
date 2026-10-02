import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { BookPlus, Clapperboard, Compass, FileAudio, FolderDown, Headphones, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
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
import { Button, Dialog, EmptyState, TooltipProvider } from "@/shared/ui";
import { useMediaQuery, useModalOpen } from "@/shared/media";
import type { ListenBook } from "@/listen/model";
import { coverArtwork } from "@/shared/cover";
import { keptEditsTitle } from "@/shared/editsKept";
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
      // Chưa có chương nào nghe được thì không có gì để xuất (soát UX 29-09: bấm được rồi nhận lỗi 409).
      disabled={!book.chaptersAvailable}
      onSelect={() => void run()}
      className="flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[disabled]:opacity-40 data-[highlighted]:bg-hover"
    >
      <FolderDown className="size-4" /> Xuất MP3 để nghe ở app khác
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
      await api(`/api/listen/books/${book.id}`, { method: "DELETE" });
      setBook(null);
      navigate("/", { replace: true });
      void client.invalidateQueries({ queryKey: ["listen"] });
      toast.success(`Đã bỏ “${book.title}” khỏi thư viện`, {
        description: "Thư mục sách đã vào Thùng rác. Mở lại file .abook là nhập lại.",
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
      description="Bản đã nhập trên máy này chuyển vào Thùng rác, khôi phục được từ đó. File .abook gốc không bị đụng - mở lại nó là nhập lại."
    >
      <div className="flex justify-end gap-2">
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
      // Chưa có chương nào nghe được thì không có gì để xuất (soát UX 29-09: bấm được rồi nhận lỗi 409).
      disabled={!book.chaptersAvailable}
      onSelect={() => void run()}
      className="flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[disabled]:opacity-40 data-[highlighted]:bg-hover"
    >
      <FileAudio className="size-4" /> Xuất file sách (mở bằng app ở máy khác)
    </DropdownMenu.Item>
  );
}

/** Kết quả mở một file sách (`POST /api/listen/open-book-file`, hay cửa sổ app khi bấm đúp file .abook - desktop.py). */
interface OpenedBook {
  id: string | null;
  how?: "new" | "existing" | "updated" | "project" | "studio";
  /** File `.abookproj`: số file nguồn chương không có trong gói (đã bị dời hay xoá ở máy gói). */
  missingSources?: number;
  /** File `.abook` phiên bản 4 mang thay đổi của người nghe (lớp sửa - docs/EDITING.md): số thay đổi. Cuốn là dự án của
   *  máy này (`how` "project") thì chúng đang chờ người dùng đồng ý áp vào dự án. */
  edits?: number;
  /** Cuốn đã nhập sẵn trên máy: phần sửa trong file được hợp vào, thay đổi của máy này thắng khi trùng. */
  merge?: { adopted: number; kept: number; conflicts: number };
  error?: string;
  file?: string;
}

const OPENED_SAID: Record<NonNullable<OpenedBook["how"]>, [string, string | undefined]> = {
  new: ["Đã thêm sách vào thư viện", "Sách đã chép vào thư viện - xoá file gốc cũng không sao."],
  existing: ["Cuốn này đã có trong thư viện", undefined],
  updated: ["Đã cập nhật lên bản nhiều chương hơn", "Chỗ đang nghe, dấu trang vẫn giữ nguyên."],
  project: ["Đây là sách do Studio máy này làm", "Mở đúng cuốn ấy, không chép thêm bản nào."],
  studio: ["Đã mở dự án vào Studio", "Dự án đã chép vào thư viện Studio - xoá file gốc cũng không sao."],
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
      if (result.how === "studio") {
        void client.invalidateQueries({ queryKey: ["library"] });
        navigate(`/studio/${result.id}`);
        const lost = result.missingSources ?? 0;
        toast.success(OPENED_SAID.studio[0], {
          description: lost
            ? `Thiếu ${lost} file nguồn chương (đã bị dời ở máy gói) - nghe, xem, xuất vẫn được; thu lại chương ấy thì cần chép nguồn vào.`
            : OPENED_SAID.studio[1],
        });
        return;
      }
      void client.invalidateQueries({ queryKey: ["listen"] });
      navigate(`/book/${result.id}`);
      const [said, description] = OPENED_SAID[result.how ?? "new"];
      toast.success(keptEditsTitle(result.merge?.kept) ?? said, { description: mergeNote(result) ?? description });
      if (result.how === "project" && result.edits) offerFold(client, result.id, result.edits);
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
    description: "Tên sách, bìa, tên nhân vật, tên chương, nhạc nền người nghe đã sửa, và những việc họ ghi cho Studio (giọng, giới tính, gộp người, cách đọc, thu lại). Chưa áp gì cho tới khi bạn đồng ý.",
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
  // Màn hẹp (Studio từ xa trên điện thoại): thông báo ở đầu màn như app Android - ở đáy nó đè trình phát nhỏ và thanh
  // điều hướng suốt 8 giây của nút "Hoàn tác" (soát UX 30-09).
  const narrow = useMediaQuery("(max-width: 639px)");
  // Hộp thoại đang mở: thông báo (nhất là cái có nút "Ở lại đây") lên đầu màn, khỏi đè nút chính của hộp ở góc dưới
  // (soát UX 02-10: "Thiết bị khác đã nghe tới chỗ khác" che "Xuất" và "Chọn").
  const modalOpen = useModalOpen();
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
              {!info.remote && <VolumeSaver />}
              {!info.remote && <RemoveImportedHost />}
              <Shell>
                <Routes>
                  <Route path="/" element={<LibraryRoute />} />
                  <Route
                    path="/book/:id"
                    element={
                      <BookScreen
                        extraActions={(book) =>
                          book.imported ? (
                            // Sách của máy khác (remote) thôi hiện khi gỡ máy ấy - không có gì để xoá ở đây.
                            book.remote || info.remote ? null : <RemoveImportedMenuItem book={book} />
                          ) : (
                            <>
                              <BookFileMenuItem book={book} />
                              <ExportMenuItem book={book} />
                              <StudioMenuItem id={book.id} />
                            </>
                          )
                        }
                        studioLink={(book) => (book.imported ? null : <StudioChipLink id={book.id} />)}
                        editing={
                          info.remote
                            ? false
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
                      <ReaderScreen
                        editing={!info.remote}
                        onOpenStudioScript={(bookId, chapterId, stableId) =>
                          window.location.assign(`#/studio/${bookId}?tab=script&chapter=${chapterId}&line=${encodeURIComponent(stableId)}`)
                        }
                      />
                    }
                  />
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
        position={narrow || modalOpen ? "top-center" : "bottom-right"}
        // Đáy nâng lên khi có thanh "Đang phát trên điện thoại" (RemotePhone.tsx đặt --toast-bottom).
        offset={{ top: modalOpen ? 16 : 96, right: 96, left: 96, bottom: "var(--toast-bottom, 96px)" }}
        containerAriaLabel="Thông báo"
        // Radix tắt chuột của mọi thứ ngoài hộp thoại đang mở: không có dòng này nút trong thông báo không bấm được.
        className="pointer-events-auto"
        toastOptions={{
          classNames: {
            toast: "!bg-panel !border !border-line !text-fg !shadow-float !rounded-xl",
            description: "!text-fg-2",
            // Nút trong thông báo ("Hoàn tác", "Ở lại đây") theo màu của app - mặc định của sonner là chữ tối trên nền
            // tối ở giao diện tối (soát UX 29-09).
            actionButton: "!bg-accent !text-accent-ink !font-semibold !rounded-lg",
            cancelButton: "!bg-hover !text-fg !rounded-lg",
          },
        }}
      />
    </TooltipProvider>
  );
}

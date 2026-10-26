import { useQuery } from "@tanstack/react-query";
import { useMemo, type ReactNode } from "react";
import { Link } from "react-router";
import type { ListenBook } from "@/listen/model";
import { MotionPresence } from "@/shared/MotionPresence";
import { MotionRegion } from "@/shared/MotionRegion";
import { Progress } from "@/shared/ui";
import { RemoteRow } from "./DevicesScreen";
import { useDownloadProgress } from "./downloads";
import { isUnpaired, toastNativeError } from "./nativeError";
import { EbookLibrary, type RemoteBook } from "./plugins";

/** Tiến độ ở ngay bìa, kể cả khi cuốn nằm trong một bộ chưa mở. */
function DownloadCover({ books }: { books: ListenBook[] }) {
  const progress = useDownloadProgress();
  const book = books.find(book => progress[book.id] && !progress[book.id].finished && !progress[book.id].cancelled && !progress[book.id].error);
  const event = book && progress[book.id];
  const fraction = event ? event.total ? (event.done ?? 0) / event.total : (event.files ?? 0) / Math.max(1, event.filesTotal ?? 1) : 0;
  return <MotionPresence open={Boolean(event)}>{event && <div className="pointer-events-none absolute bottom-2 left-2 right-[60px] rounded-control bg-panel p-2 text-xs text-fg">
    <span className="block truncate">Tải · {Math.round(fraction * 100)}%</span>
    <Progress size="xs" running value={fraction} label={`Đang tải ${book!.title}`} className="mt-1" />
  </div>}</MotionPresence>;
}

type Extras = {
  actions: (book: ListenBook) => ReactNode;
  cover: (book: ListenBook) => ReactNode;
  seriesCover: (books: ListenBook[]) => ReactNode;
};

/** Dùng đúng thư viện và lệnh tải cũ; cả máy tính chính và thiết bị ghép cùng nằm trong lưới. */
export function LibraryDownloads({ children }: { children: (extras: Extras, books: ListenBook[]) => ReactNode }) {
  const connection = useQuery({ queryKey: ["connection"], queryFn: () => EbookLibrary.connection() });
  const remote = useQuery({ queryKey: ["remote"], enabled: Boolean(connection.data?.paired), queryFn: () => EbookLibrary.remoteLibrary(), retry: 0 });
  const peers = useQuery({ queryKey: ["peer-libraries"], queryFn: () => EbookLibrary.peerLibraries(), retry: 0 });
  const catalog = useMemo(() => new Map<string, RemoteBook & { sourceName: string }>([
    ...(connection.data?.paired && !isUnpaired(remote.error) ? remote.data?.books ?? [] : []).map(book => [book.id, { ...book, sourceName: connection.data?.name || "máy tính" }] as const),
    ...(peers.data?.peers ?? []).filter(peer => !peer.error && !peer.unpaired).flatMap(peer => peer.books.map(book => [book.id, { ...book, source: peer.key, sourceName: peer.name }] as const)),
  ]), [connection.data?.paired, connection.data?.name, remote.data, remote.error, peers.data]);
  // Gói nghe trực tiếp có thể chưa về (mạng chậm/hỏng); danh mục vẫn phải cho bạn tải được cuốn ấy.
  const books = useMemo<ListenBook[]>(() => [...catalog.values()].map(book => ({
    id: book.id, title: book.title, narrator: book.narrator, duration: book.duration,
    chaptersTotal: book.chaptersTotal, chaptersAvailable: book.chaptersAvailable,
    complete: book.complete, producing: Boolean(book.producing), updatedAt: book.updatedAt,
    state: { chapters: {} },
    progress: { heardSeconds: 0, totalSeconds: book.duration, fraction: 0, chaptersDone: 0, finished: false },
    remote: { computer: book.sourceName, downloaded: book.downloaded },
  })), [catalog]);
  const failed = remote.isError || peers.isError || peers.data?.peers.some(peer => peer.error || peer.unpaired);
  const extras: Extras = {
    actions: book => <BookDownload book={catalog.get(book.id)} />,
    cover: book => <DownloadCover books={[book]} />,
    seriesCover: books => <DownloadCover books={books} />,
  };
  return <>
    <MotionPresence open={Boolean(failed)}><div className="flex items-center justify-between gap-3 px-[20px] pt-3 text-xs text-fg-2">
      <span>Chưa nối được máy kia.</span>
      <button type="button" className="min-h-[44px] text-accent-text" onClick={() => { void remote.refetch(); void peers.refetch(); }}>Thử lại</button>
      <Link to="/settings/devices" className="min-h-[44px] content-center text-accent-text">Thiết bị</Link>
    </div></MotionPresence>
    {children(extras, books)}
  </>;
}

function BookDownload({ book }: { book?: RemoteBook }) {
  const progress = useDownloadProgress();
  return <MotionRegion>{book && <RemoteRow compact book={book} progress={progress[book.id]} onDownload={() => {
    void EbookLibrary.download({ bookId: book.id, ...(book.source ? { source: book.source, remoteId: book.remoteId } : {}) })
      .catch(error => toastNativeError("Chưa tải được", error));
  }} />}</MotionRegion>;
}

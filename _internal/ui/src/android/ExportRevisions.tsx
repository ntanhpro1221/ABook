import { MotionRegion } from "@/shared/MotionRegion";
import { useQuery } from "@tanstack/react-query";
import type { ListenBook } from "@/listen/model";
import { Button } from "@/shared/ui";
import { EbookLibrary } from "./plugins";
import { exportMp3 } from "./ExportMp3";
import { chooseM4b } from "./ExportM4b";

export function ExportRevisionNotice({ book }: { book: ListenBook }) {
  const history = useQuery({ queryKey: ["phone-export-history", book.id],
    queryFn: () => EbookLibrary.exportHistory({ bookId: book.id }), refetchInterval: 5000 });
  const stale = (history.data?.exports ?? []).filter((item) => item.changed.length);
  if (!stale.length) return <MotionRegion />;
  return <MotionRegion as="div" className="my-3 space-y-2 py-3 text-sm">
    <p className="font-semibold">Bạn có bản xuất đã cũ sau khi sửa và thu lại.</p>
    {stale.map((item) => <div key={item.target}>
      <p className="break-all">{item.target} · {item.changed.length} chương đã đổi</p>
      {item.kind === "mp3" ? <Button size="sm" variant="ghost" onClick={() => void exportMp3(book, false, item.changed)}>Xuất lại các chương đã đổi</Button>
        : item.kind === "m4b" ? <><p>M4B gộp cả cuốn: bạn cần dựng lại cả file và thay bản đã chép hoặc gửi.</p><Button size="sm" variant="ghost" onClick={() => void chooseM4b(book)}>Xuất lại cả file M4B</Button></>
        : <p>Bạn hãy dùng “Lưu thành…” trong menu sách để xuất lại file và thay bản đã chép hoặc gửi.</p>}
    </div>)}
  </MotionRegion>;
}

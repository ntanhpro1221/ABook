import { useNavigate } from "react-router";
import { useLibraryPreview } from "./preview";
import { TrackSheet } from "./TrackSheet";

/** Sheet "Bài đang phát" (chạm dòng Nhạc nền của trình phát): tên · người sáng tác · cảm xúc (+ "Vì sao bài này" khi đoạn có cảm xúc
 *  máy đọc được) · Lưu / Bỏ lưu · Xem trong kho · Đổi bài (mở Kho nhạc ở chế độ chọn cho đúng đoạn đang phát - cùng đường lưu với "Đổi bài"). */
export function NowPlayingMusic({ link, bookId, scene, onClose }: { link: string | null; bookId: string | null; scene: string | null; onClose: () => void }) {
  const preview = useLibraryPreview();
  const navigate = useNavigate();
  const context = bookId && scene ? { book: bookId, scene } : null;
  return (
    <TrackSheet
      link={link}
      onClose={onClose}
      preview={preview}
      context={context}
      playing={{
        onOpenLibrary: (title) => { onClose(); navigate(`/music?tab=library&q=${encodeURIComponent(title)}`); },
        onSwap: context ? () => { onClose(); navigate(`/music?pick=${encodeURIComponent(context.book)}&scene=${encodeURIComponent(context.scene)}`); } : undefined,
      }}
    />
  );
}

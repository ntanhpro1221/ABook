import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router";
import { toast } from "@/shared/toast";
import type { BookSummary } from "./api";
import { precastInvites } from "./precast";

// Lời mời duyệt trước khi thu, ở mọi trang (thanh bên của máy tính gọi): mô-đun nhỏ riêng, không kéo màn Duyệt trước khi thu (PrecastReview,
// tải lười cùng Studio) vào gói đầu của app (docs/PERF_WEB.md).

const INVITED_KEY = "abook-precast-invited-";

function invited(id: string): string | null {
  try {
    return localStorage.getItem(INVITED_KEY + id);
  } catch {
    return null;
  }
}

/** Lời mời "Phân tích xong - duyệt trước khi thu?" ở mọi trang của Studio, một lần mỗi mốc - cả Studio từ xa trên điện thoại
 *  (cùng giao diện này). Máy tính còn có thông báo Windows của Studio (webui/server.py `_precast_tick`). */
export function usePrecastInvites(books: BookSummary[] | undefined) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  useEffect(() => {
    for (const book of precastInvites(books ?? [], invited)) {
      try {
        localStorage.setItem(INVITED_KEY + book.id, String(book.precast?.announcedAt));
      } catch {
        /* không nhớ được thì lần sau mời lại - vô hại */
      }
      // Đang ở chính trang dự án ấy: dải mời trên trang đã nói, không cần thêm thông báo.
      if (pathname === `/studio/${book.id}`) continue;
      toast(book.precast?.held ? `“${book.title}” đang chờ bạn duyệt` : `“${book.title}” đã phân tích xong`, {
        id: `precast-${book.id}`,
        duration: 30_000,
        action: { label: "Duyệt", onClick: () => navigate(`/studio/${book.id}?tab=precast`) },
      });
    }
  }, [books, navigate, pathname]);
}

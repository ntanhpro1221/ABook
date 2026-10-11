import { FolderX, Settings } from "lucide-react";
import { useNavigate } from "react-router";
import { Button, EmptyState } from "@/shared/ui";

/** Tên thư mục cuối của một đường dẫn (Windows hay POSIX) - không hiện cả đường dẫn (có tên tài khoản Windows). */
export function folderName(path: string): string {
  return path.replace(/[\\/]+$/, "").split(/[\\/]/).pop() || path;
}

/** Thư mục thư viện người dùng chọn không còn (ổ rời rút ra, bị đổi tên / chuyển chỗ khi app đang chạy - soát a28 lỗi 6): nói thẳng thay vì
 *  một thư viện trống im lặng. Chọn lại thư mục (kể cả chỗ mới của chính nó) thì chỗ nghe, dấu trang đi theo sách. */
export function MissingLibrary({ root, className }: { root: string; className?: string }) {
  const navigate = useNavigate();
  return (
    <EmptyState
      icon={FolderX}
      title={`Không thấy thư mục thư viện “${folderName(root)}”`}
      className={className}
      action={
        <Button variant="primary" icon={Settings} onClick={() => navigate("/settings")}>
          Chọn thư mục trong Cài đặt
        </Button>
      }
    >
      Có thể ổ chứa nó chưa được cắm, hoặc thư mục đã bị đổi tên hay chuyển đi. Cắm lại ổ, hoặc chọn chỗ mới của thư mục ấy - chỗ đang nghe và
      dấu trang vẫn được giữ.
    </EmptyState>
  );
}

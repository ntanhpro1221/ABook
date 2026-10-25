import { FolderX, Settings } from "lucide-react";
import { useNavigate } from "react-router";
import { OnComputerOnly } from "@/shared/OnComputerOnly";
import { Button, EmptyState } from "@/shared/ui";
import { useAppInfo } from "@/studio/data";

/** Tên thư mục cuối của một đường dẫn (Windows hay POSIX) - không hiện cả đường dẫn (có tên tài khoản Windows). */
export function folderName(path: string): string {
  return path.replace(/[\\/]+$/, "").split(/[\\/]/).pop() || path;
}

/** Thư mục thư viện người dùng chọn không còn (ổ rời rút ra, bị đổi tên / chuyển chỗ khi app đang chạy - soát a28 lỗi 6): nói thẳng thay vì
 *  một thư viện trống im lặng. Chọn lại thư mục (kể cả chỗ mới của chính nó) thì chỗ nghe đi theo sách. */
export function MissingLibrary({ root, className }: { root: string; className?: string }) {
  const navigate = useNavigate();
  // Studio từ xa: thư mục thư viện là của máy tính (đường dẫn không tới thiết bị này, cài đặt không đổi được từ đây).
  const remote = Boolean(useAppInfo().data?.remote);
  return (
    <EmptyState
      icon={FolderX}
      title={remote || !root ? "Không thấy thư mục thư viện" : `Không thấy thư mục thư viện “${folderName(root)}”`}
      className={className}
      action={
        remote ? (
          <OnComputerOnly verb="Chọn lại thư mục thư viện" />
        ) : (
          <Button variant="primary" icon={Settings} onClick={() => navigate("/settings/advanced")}>
            Chọn thư mục
          </Button>
        )
      }
    >
      Ổ chưa cắm, hay thư mục đã đổi tên. Cắm lại ổ hoặc chọn chỗ mới; chỗ đang nghe vẫn giữ.
    </EmptyState>
  );
}

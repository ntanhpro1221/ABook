import { S } from "./strings.generated";
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
      title={remote || !root ? S.s_khong_thay_thu_muc_thu_vien_8c2af7eb : S.s_khong_thay_thu_muc_thu_vien_0_9b3dbbec(folderName(root))}
      className={className}
      action={
        remote ? (
          <OnComputerOnly verb={S.s_chon_lai_thu_muc_thu_vien_2d290748} />
        ) : (
          <Button variant="primary" icon={Settings} onClick={() => navigate("/settings/advanced")}>{S.s_chon_thu_muc_1fe47e38}</Button>
        )
      }
    >{S.s_o_chua_cam_hay_thu_muc_da_doi_ten_cam_lai_713e694c}</EmptyState>
  );
}

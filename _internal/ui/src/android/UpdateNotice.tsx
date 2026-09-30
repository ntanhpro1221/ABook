import { useEffect } from "react";
import { toast } from "sonner";
import { EbookLibrary } from "./plugins";
import { markTold, toldAbout, useAppUpdate } from "./updates";

/** Mở file APK (hay trang) của bản mới bằng trình duyệt của máy - cài là người dùng bấm. */
export async function openRelease(url: string): Promise<void> {
  try {
    await EbookLibrary.openRelease({ url });
  } catch (error) {
    toast.error("Không mở được trình duyệt", { description: (error as Error).message });
  }
}

/** Nhắc MỘT lần mỗi bản mới lúc mở app; Cài đặt → Cập nhật thì luôn ghi. */
export function UpdateNotice() {
  const { update } = useAppUpdate();
  useEffect(() => {
    if (!update || toldAbout(update.version)) return;
    markTold(update.version);
    toast(`Có ABook ${update.version} cho điện thoại`, {
      description: "Tải file APK rồi mở để cài đè - sách và chỗ đang nghe giữ nguyên.",
      duration: 12000,
      action: { label: "Tải", onClick: () => void openRelease(update.apk ?? update.page) },
    });
  }, [update]);
  return null;
}

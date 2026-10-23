import { MotionRegion } from "@/shared/MotionRegion";
import { BatteryCharging } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "@/shared/toast";
import { Button, LiveText } from "@/shared/ui";
import { backgroundHelp } from "./backgroundHelp";
import { EbookLibrary } from "./plugins";

// Xuất MP3/M4B/sách nói dài trên điện thoại hãng (OPPO ColorOS, Xiaomi...): hệ thống đông app ở nền sau chừng nửa phút kể cả khi có dịch vụ nền
// (đo 17-10 trên ColorOS: OplusHansManager), nên tắt màn hình giữa chừng thì việc xuất có thể đứng. Khi người dùng bật "Cho phép hoạt động dưới
// nền" ABook vào danh sách miễn tối ưu pin. App không tự xin miễn (không có intent công khai nào ổn) - chỉ nhắc và chỉ đường, một ghi chú
// nhỏ trong khung xuất, ẩn hẳn khi đã cho phép hoặc khi không đọc được (máy tính, web, lỗi).

export interface BackgroundStatus {
  manufacturer: string;
  backgroundAllowed: boolean;
}

/** Hỏi máy; không hỏi được (không phải điện thoại, plugin cũ, lỗi) thì undefined - ghi chú không hiện. */
export async function readBackground(): Promise<BackgroundStatus | undefined> {
  try {
    const status = await EbookLibrary.backgroundStatus();
    return typeof status?.backgroundAllowed === "boolean" ? status : undefined;
  } catch {
    return undefined;
  }
}

/**
 * Đọc ngay và đọc lại mỗi lần app trở lại màn hình (người dùng sang Cài đặt bật xong rồi quay về thì ghi chú tự ẩn).
 * Trả hàm huỷ theo dõi; `onStatus` không bị gọi sau khi huỷ.
 */
export function watchBackground(onStatus: (status: BackgroundStatus | undefined) => void): () => void {
  let live = true;
  const check = () => void readBackground().then((status) => live && onStatus(status));
  const follow = () => {
    if (document.visibilityState !== "hidden") check();
  };
  check();
  document.addEventListener("visibilitychange", follow);
  return () => {
    live = false;
    document.removeEventListener("visibilitychange", follow);
  };
}

export function useBackgroundStatus(): BackgroundStatus | undefined {
  const [status, setStatus] = useState<BackgroundStatus | undefined>();
  useEffect(() => watchBackground(setStatus), []);
  return status;
}

/** Mở trang thông tin ứng dụng của ABook trong Cài đặt (nơi bật "Cho phép hoạt động dưới nền"). */
export function openBackgroundSettings() {
  return EbookLibrary.openAppSettings().catch((error: Error) => void toast.error(error.message));
}

/** Lời mặc định của ghi chú trong khung xuất; chỗ khác (chia sẻ thư viện) nói việc của mình bằng `note` / `action`. */
const EXPORT_NOTE = "Xuất sách dài khi tắt màn hình có thể bị máy tạm dừng.";
const EXPORT_ACTION = "Cho ABook chạy nền";

interface NoteWords {
  note?: string;
  action?: string;
}

/** Thuần hiển thị: chỉ hiện khi biết chắc ABook CHƯA được chạy nền. */
export function BackgroundNoteView({ status, onOpen = () => void openBackgroundSettings(), note = EXPORT_NOTE, action = EXPORT_ACTION }: { status: BackgroundStatus | undefined; onOpen?: () => void } & NoteWords) {
  if (!status || status.backgroundAllowed) return <MotionRegion />;
  return (
    <MotionRegion as="div" role="note" className="mt-2 rounded-lg border border-line bg-hover/40 p-2.5">
      <p className="text-xs leading-snug text-fg-2">{note}</p>
      <Button size="sm" variant="ghost" icon={BatteryCharging} className="mt-1 h-auto min-h-8 justify-start whitespace-normal py-1.5 text-left" onClick={onOpen}>
        {action}
      </Button>
      <p className="px-1 text-xs leading-snug text-fg-2">{backgroundHelp(status.manufacturer)}</p>
    </MotionRegion>
  );
}

/** Ghi chú trong khung xuất (hộp chọn xuất, thông báo đang xuất) và ở trang chia sẻ thư viện (DevicesScreen). */
export function BackgroundNote(words: NoteWords) {
  return <BackgroundNoteView status={useBackgroundStatus()} {...words} />;
}

/** Chữ tiến độ của thông báo đang xuất + ghi chú chạy nền (nếu cần). Cùng `shown`/`spoken` với LiveText. */
export function ExportProgressText({ shown, spoken }: { shown: string; spoken: string }) {
  return (
    <>
      <LiveText shown={shown} spoken={spoken} />
      <BackgroundNote />
    </>
  );
}

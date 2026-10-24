import { toast } from "@/shared/toast";

/** Một hàm báo lỗi chỉ gọi `show` ở lần lỗi ĐẦU TIÊN - trình phát lưu chỗ nghe vài giây một lần, đĩa đầy thì đừng dội thông báo. */
export function onceReporter(show: (detail: string) => void): (error: unknown) => void {
  let told = false;
  return (error: unknown) => {
    if (told) return;
    told = true;
    show(error instanceof Error ? error.message : "");
  };
}

/** Lưu chỗ nghe / phiên nghe lỗi (đĩa đầy, thư mục dữ liệu chỉ đọc): trước đây giao diện nuốt lỗi - nghe tiếp cả buổi mà không chỗ nào được
 *  lưu, không ai biết (soát a28 lỗi 11). Báo một lần mỗi phiên. */
export const reportSaveFailure = onceReporter((detail) =>
  toast.error("Chưa lưu được chỗ đang nghe", {
    description: `${detail ? `${detail} ` : ""}Vẫn nghe tiếp được, nhưng lần mở sau có thể không về đúng chỗ này.`.trim(),
    duration: 12000,
  }),
);

// Trạng thái chung của một trang trưng bày: kịch bản của mục đang xem (dữ liệu giả đọc nó), và những gì trang báo ra ngoài cho
// scripts/gallery_shots.mjs và test (`window.__gallery`).

export interface Scenario {
  /** Thư viện: đủ sách, rỗng, đang tải mãi, hay lỗi. */
  library: "full" | "empty" | "loading" | "error";
  /** Điện thoại đã ghép máy tính chưa (Cài đặt › Thiết bị). */
  paired: boolean;
  /** Máy tính cũng có sách của thiết bị ghép trong Thư viện. */
  remoteBooks: boolean;
  /** Có đêm hẹn giờ ngủ để hiện thẻ "Tối qua". */
  night: boolean;
  /** Bấm phát thì phát (false: giữ ở trạng thái tạm dừng). */
  playing: boolean;
  /** Studio: lỗi / rỗng ở danh sách dự án. */
  projects: "full" | "empty" | "loading";
  /** Dự án chờ và lỗi/đang tải của từng vùng, hoàn toàn cục bộ. */
  queued?: boolean;
  /** App Windows đóng gói đã cài Studio (khác bản dev dùng runtime cạnh mã nguồn). */
  installedStudio?: boolean;
  requests?: Record<string, "loading" | "error">;
  /** Hộp chọn file của hệ thống: bạn huỷ - hộp Thêm sách / trình tạo sách hiện bước chọn của nó (thư mục, dán đường dẫn) làm lối khác. */
  pickCancelled?: boolean;
}

export const DEFAULT_SCENARIO: Scenario = { library: "full", paired: true, remoteBooks: false, night: false, playing: true, projects: "full" };

export const galleryState = {
  scenario: { ...DEFAULT_SCENARIO } as Scenario,
  /** Phương thức native / đường API mà dữ liệu giả chưa có - trang vẫn chạy (trả rỗng), danh sách để bổ sung. */
  missing: new Set<string>(),
  /** Lỗi (console.error, lỗi không bắt) trong lúc dựng mục. */
  errors: [] as string[],
  /** Cảnh báo dev đã biết của chính app (run.ts KNOWN_DEV_WARNINGS) - không tính là lỗi. */
  known: new Set<string>(),
  ready: false,
};

/** Lời hứa không bao giờ xong: trạng thái "đang tải" đứng yên để chụp. */
export function never<T>(): Promise<T> {
  return new Promise<T>(() => undefined);
}

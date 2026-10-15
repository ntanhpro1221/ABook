/** Menu "Tuỳ chọn khác" của trang sách có mục nào để hiện không (thiết bị chỉ được nghe: không sửa, không xuất - menu rỗng thì ẩn nút, soát a36). */
export function moreMenuHasItems(parts: {
  /** Mục hồ sơ nghe (nghe lại từ đầu / chuyển chỗ nghe) hiện. */
  records: boolean;
  /** Sách có âm thanh: có "Đánh dấu đã nghe xong". */
  finishedToggle: boolean;
  /** Được sửa sách (nhóm Sửa tên, bìa...). */
  edit: boolean;
  /** Nhóm mục theo nền tảng (chặn sửa, Studio, file dự án, sách chữ) - có thể hiện ở mọi máy cho sửa tại chỗ. */
  platform: boolean;
  /** Mục nền tảng thêm vào (`extraActions`): null / false = không có. */
  extra: unknown;
}): boolean {
  return parts.records || parts.finishedToggle || parts.edit || parts.platform || (parts.extra !== null && parts.extra !== undefined && parts.extra !== false);
}

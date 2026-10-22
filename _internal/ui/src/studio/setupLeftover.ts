/** Lượt cài Studio của lần mở app trước (hay một cửa sổ ABook khác) còn chạy (webui/install_lock.py, `leftover` của /api/studio/setup). */
export interface SetupLeftover {
  pid: number;
  /** Giây epoch lúc lượt ấy bắt đầu. */
  since: number;
  what: string;
  /** Host của lượt ấy đã chết, tiến trình con còn chạy ngầm: dừng được. Sai = một cửa sổ ABook khác đang cài. */
  orphan: boolean;
  childPid: number;
}

const clock = (seconds: number) => {
  if (!seconds) return "trước";
  const date = new Date(seconds * 1000);
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
};

export function leftoverLine(leftover: SetupLeftover): string {
  const when = clock(leftover.since);
  return leftover.orphan
    ? `Lượt cài lúc ${when} (lần mở app trước) vẫn còn chạy ngầm. Bạn chờ nó xong rồi bấm Cài tiếp, hoặc bấm “Dừng lượt cũ” để cài lại từ chỗ dở.`
    : `Một cửa sổ ABook khác đang cài Studio từ ${when}. Bạn đóng nó hoặc chờ nó xong rồi bấm Cài tiếp.`;
}

// Giao diện chọn trong app (Sáng / Tối / Tự động) nhớ ở trình duyệt này, để trang lúc tải (ui/index.html, chạy TRƯỚC khi vẽ) tô đúng nền
// ngay khung đầu - không thì máy để Tối mà app chọn Sáng sẽ loé nền tối tới khi tuỳ chọn về từ máy chủ. Soát tapthru5 S4 (18-11).
// index.html đọc đúng khoá này bằng mã nội tuyến (savedTheme.test.ts giữ hai bên khớp).
export const SAVED_THEME_KEY = "abook.theme";

export type ThemeChoice = "system" | "light" | "dark";

export function saveTheme(theme: string): void {
  if (theme !== "system" && theme !== "light" && theme !== "dark") return;
  try { localStorage.setItem(SAVED_THEME_KEY, theme); } catch { /* trình duyệt chặn lưu: lần sau theo máy như cũ */ }
}

/** "light" / "dark" khi người nghe đã chọn hẳn; null khi theo máy hay chưa lưu. */
export function savedTheme(): "light" | "dark" | null {
  try {
    const value = localStorage.getItem(SAVED_THEME_KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch { return null; }
}

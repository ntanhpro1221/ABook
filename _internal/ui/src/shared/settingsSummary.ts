// Dòng tóm tắt giá trị hiện tại dưới tên nhóm ở trang gốc Cài đặt (shared/SettingsNav.tsx) - hai nền cùng lời.

export function sleepSummary(schedule: { from: string; to: string } | null | undefined, safetyStopHours: number | undefined): string {
  if (schedule) return `Lịch đêm ${schedule.from}–${schedule.to}`;
  if (safetyStopHours) return `Tự tắt sau ${safetyStopHours} giờ`;
  return "Tắt";
}

/** Nhóm Nghe: tự lùi · nhạc nền tự chọn (SettingsSummary.listen bên native). */
export function listenSummary(autoRewind: boolean, autoMusic: boolean): string {
  const rewind = autoRewind ? "Tự lùi" : "Không tự lùi";
  return `${rewind} · ${autoMusic ? "nhạc tự chọn" : "không nhạc nền"}`;
}

/** `system`: tên của "theo hệ thống" trên nền ấy ("Tự động" trên điện thoại, "Theo Windows" trên máy tính). */
export function themeSummary(theme: string | undefined, system: string): string {
  return theme === "light" ? "Sáng" : theme === "dark" ? "Tối" : system;
}

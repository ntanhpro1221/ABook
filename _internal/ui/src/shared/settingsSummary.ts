import { S } from "./strings.generated";
// Dòng tóm tắt giá trị hiện tại dưới tên nhóm ở trang gốc Cài đặt (shared/SettingsNav.tsx) - hai nền cùng lời.

export function sleepSummary(schedule: { from: string; to: string } | null | undefined): string {
  if (schedule) return S.s_lich_dem_0_1_4578d519(schedule.from, schedule.to);
  return S.s_tat_3286064e;
}

/** Listening summary, shared with native settings. */
export function listenSummary(autoMusic: boolean): string {
  return autoMusic ? S.s_nhac_tu_chon_31bdb97d : S.s_khong_nhac_nen_0e54f623;
}

/** `system`: tên của "theo hệ thống" trên nền ấy ("Tự động" trên điện thoại, "Theo Windows" trên máy tính). */
export function themeSummary(theme: string | undefined, system: string): string {
  return theme === "light" ? S.s_sang_8f0c677d : theme === "dark" ? S.s_toi_4ac2d267 : system;
}

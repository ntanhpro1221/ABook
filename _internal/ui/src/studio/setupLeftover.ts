import { S } from "../shared/strings.generated";
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
  if (!seconds) return S.s_truoc_22e6f96e;
  const date = new Date(seconds * 1000);
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
};

export function leftoverLine(leftover: SetupLeftover): string {
  const when = clock(leftover.since);
  return leftover.orphan
    ? S.s_luot_cai_luc_0_lan_mo_app_truoc_van_con_ch_75fe6211(when)
    : S.s_mot_cua_so_abook_khac_dang_cai_studio_tu_0_bd6918c5(when);
}

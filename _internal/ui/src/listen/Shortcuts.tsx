import { S } from "../shared/strings.generated";
import { useEffect, useState, type ReactNode } from "react";
import { letterShortcutsOn, useLetterShortcuts } from "@/shared/letterShortcuts";
import { MotionRegion } from "@/shared/MotionRegion";
import { Dialog, Kbd } from "@/shared/ui";

// Phím tắt của máy tính: MỘT danh sách cho Cài đặt › Phím tắt và cho hộp mở bằng phím "?" (hay nút "Phím tắt" ở màn Đang nghe).

export const SHORTCUTS_EVENT = "abook:shortcuts";

/** Mở hộp phím tắt (nút ở màn Đang nghe và phím "?" cùng đi qua đây). */
export function openShortcuts() {
  window.dispatchEvent(new CustomEvent(SHORTCUTS_EVENT));
}

/** [phím, việc, là phím một chữ cái (tắt được ở Cài đặt › Phím tắt)]. */
const SHORTCUTS: [ReactNode, string, boolean][] = [
  [<Kbd key="space">{S.s_space_20eac5aa}</Kbd>, S.s_phat_tam_dung_563530d1, false],
  [<><Kbd>←</Kbd> <Kbd>→</Kbd></>, S.s_lui_toi_15_giay_5f952fd6, false],
  [<><Kbd>{S.s_shift_2e544a29}</Kbd> + <Kbd>←</Kbd> <Kbd>→</Kbd></>, S.s_chuong_truoc_sau_1f7a3d2b, false],
  [<Kbd key="m">{S.s_m_08f27188}</Kbd>, S.s_tat_bat_tieng_152563ae, true],
  [<><Kbd>[</Kbd> <Kbd>]</Kbd></>, S.s_giam_tang_toc_do_doc_484ba2e5, true],
  [<Kbd key="esc">{S.s_esc_52f878ed}</Kbd>, S.s_thu_nho_man_hinh_dang_nghe_ec2467a0, false],
  [<Kbd key="help">?</Kbd>, S.s_xem_cac_phim_tat_nay_bdc607f4, true],
];

/** Dòng mô tả công tắc "Phím tắt một chữ cái" (Cài đặt › Giao diện). */
export const LETTER_SHORTCUTS_HINT =
  S.s_tat_neu_hay_lo_cham_phim_hay_nhap_bang_gio_03fe0a14;

/** `remote`: thiết bị ở xa (Studio từ xa) không đổi được cài đặt của máy tính - câu cuối không chỉ nó tới một công tắc nó không có.
 *  `inSettings`: danh sách nằm ngay dưới công tắc trong Cài đặt › Giao diện - không trỏ về chính trang ấy (soát 24-10 T18). */
export function ShortcutList({ remote = false, inSettings = false }: { remote?: boolean; inSettings?: boolean }) {
  const letters = useLetterShortcuts();
  // Bật / tắt "Phím tắt chữ" ngay trên danh sách: hậu tố "(đang tắt)", gạch ngang và câu cuối mờ qua (state riêng - vùng cha không thấy).
  return (
    <MotionRegion motionKey={letters}>
      <dl className={inSettings ? "space-y-2.5 text-sm" : "max-w-md space-y-2.5 text-sm"}>
        {SHORTCUTS.map(([keys, label, letter]) => (
          <div key={label} className="flex items-center justify-between gap-4">
            <dt className="text-fg-2">
              {label}
              {letter && !letters && S.s_dang_tat_3aac6b7f}
            </dt>
            <dd className={letter && !letters ? "flex items-center gap-1 text-fg-2 line-through" : "flex items-center gap-1 text-fg-2"}>{keys}</dd>
          </div>
        ))}
      </dl>
      {!(inSettings && letters) && (
      <p className="mt-3 max-w-md text-[0.8125rem] text-fg-2 text-pretty">
        {letters
          ? remote
            ? S.s_phim_mot_chu_cai_m_va_j_k_19_o_r_o_studio_456e9e75
            : S.s_tat_phim_mot_chu_cai_o_cai_dat_giao_dien_dea67281
          : S.s_phim_mot_chu_cai_dang_tat_0_space_mui_ten_7e515535(remote || inSettings ? "" : S.s_bat_o_cai_dat_giao_dien_e4e0ca4b)}
      </p>
      )}
    </MotionRegion>
  );
}

/** Đang gõ chữ (ô nhập, vùng soạn thảo): "?" là một ký tự, không phải lệnh. */
function isTyping(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  return Boolean(element && (element.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(element.tagName)));
}

/** Hộp phím tắt, một chỗ duy nhất của cả app: phím "?" (khi không gõ chữ) hay `openShortcuts()` mở nó. */
export function ShortcutsHost({ remote = false }: { remote?: boolean }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "?" || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || !letterShortcutsOn()) return;
      if (isTyping(event.target) || document.querySelector("[role='dialog']")) return;
      event.preventDefault();
      setOpen(true);
    };
    const onOpen = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener(SHORTCUTS_EVENT, onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener(SHORTCUTS_EVENT, onOpen);
    };
  }, []);
  return (
    <Dialog open={open} onOpenChange={setOpen} title={S.s_phim_tat_7baaed2f} description={S.s_dung_duoc_o_moi_man_hinh_tru_khi_dang_go_c_6452e52d}>
      <ShortcutList remote={remote} />
    </Dialog>
  );
}

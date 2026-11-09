import { S } from "../shared/strings.generated";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "./api";

// Cách đọc cho BẤT KỲ chữ nào ("TP.HCM", "km/h"): trước khi lưu, nói nó chạm tới bao nhiêu câu (webui/name_readings.reading_reach).

export interface Reach {
  surface: string;
  /** Câu có chữ ấy; `reached` là những câu mà cách đọc thật sự dùng được (ký hiệu bị đổi thành quãng nghỉ thì không), `blocked` là phần còn lại. */
  lines: number;
  reached: number;
  recorded: number;
  blocked: number;
  /** Cách đọc này không bao giờ được dùng: mọi câu có chữ ấy bị ký hiệu xé đôi (hay chưa có câu nào mà chính chữ ấy bị xé đôi)
   *  - không cho lưu (webui/name_readings.never_used). */
  never: boolean;
  cost: string;
  chapters: { chapterId: number; title: string; lines: number; recorded: number }[];
  example: { segmentId: number; chapterTitle: string; seq: number; text: string; hasAudio: boolean } | null;
}

/** Gõ xong mới hỏi (mỗi phím một lượt hỏi là phí). */
function useSettled(value: string, ms = 350): string {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
}

export function useReach(bookId: string, surface: string, enabled = true) {
  const asked = useSettled(surface.trim());
  return useQuery({
    queryKey: ["pronunciations", bookId, "reach", asked],
    enabled: enabled && Boolean(asked),
    queryFn: () => api<Reach>(`/api/books/${bookId}/pronunciations/reach?surface=${encodeURIComponent(asked)}`),
    staleTime: 15_000,
  });
}

function where(reach: Reach): string {
  const named = reach.chapters.slice(0, 3).map((chapter) => chapter.title || S.s_chuong_0_55d256d1(chapter.chapterId));
  const more = reach.chapters.length - named.length;
  return named.length ? S.s_o_0_1_dd43afcc(named.join(", "), more > 0 ? S.s_va_0_chuong_nua_128abbd4(more) : "") : "";
}

/** Vì sao không lưu được cách đọc cho chữ có ký hiệu bị xé đôi ("Mở/đóng"), và làm gì thay vào đó. */
export function neverText(surface: string): string {
  return S.s_may_doc_ky_hieu_trong_0_thanh_mot_cho_ngun_41720519(surface);
}

/** Dòng dưới ô khi đang thêm cách đọc: có bao nhiêu câu, bao nhiêu câu đã thu sẽ phải thu lại. `later`: cuốn chờ Studio - thu lại khi nào
 *  (decisions.retakeWhen), để dòng này hứa cùng điều với thông báo sau khi lưu. */
export function reachSummary(reach: Reach, later?: string): string {
  // Lời giải thích đầy đủ (`neverText`) nằm ngay dưới ô sửa, cạnh nút "Lưu" đã tắt.
  if (reach.never) return S.s_0_ay_khong_dung_duoc_cach_doc_cho_chu_co_k_0fe94280(reach.lines ? S.s_co_0_cau_co_chu_nay_nhung_m_d75dd8c1(reach.lines) : "M");
  if (!reach.lines) return S.s_chua_co_cau_nao_co_chu_nay_cach_doc_se_duo_2d730bc4;
  const cost = reach.recorded ? S.s_0_cau_da_thu_se_duoc_thu_lai_1_597e3783(reach.recorded, later ? ` ${later}` : "") : S.s_chua_thu_cau_nao_nen_khong_phai_thu_lai_79ed2712;
  const blocked = reach.blocked ? S.s_0_cau_khac_khong_dung_duoc_vi_ky_hieu_d0715176(reach.blocked) : "";
  return S.s_0_cau_co_chu_nay_1_2_3_8abc27d8(reach.reached, cost, where(reach), blocked);
}

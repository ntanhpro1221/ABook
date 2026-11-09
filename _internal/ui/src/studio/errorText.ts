import { S } from "../shared/strings.generated";
// Lỗi của lần làm sách (`book.lastError`) là dòng đầu của lỗi Python - đúng nguyên văn nhà phát triển, không phải lời cho người nghe.
// Lỗi hay gặp đổi sang câu tiếng Việt kèm việc nên làm; nguyên văn thu vào "Chi tiết" cho ai cần gửi đi hỏi.

export interface FriendlyError {
  /** Câu cho người nghe. */
  summary: string;
  /** Việc nên làm, nếu biết. */
  hint: string;
  /** Nguyên văn lỗi kỹ thuật. */
  detail: string;
}

const KNOWN: { pattern: RegExp; summary: string | ((match: RegExpMatchArray) => string); hint: string; studioHint?: string }[] = [
  {
    pattern: /out of memory|CUBLAS_STATUS_ALLOC_FAILED|CUDA error: .*memory|OutOfMemoryError|bad allocation/i,
    summary: S.s_card_do_hoa_het_bo_nho_3d3fdb50,
    hint: S.s_dong_cac_app_khac_dang_dung_card_do_hoa_tr_12ee0258,
  },
  {
    // Dây chuyền chờ (hay dừng) vì ổ chứa thư viện gần đầy: "disk free 8.0 GB" từ cổng tài nguyên (resource_manager).
    pattern: /disk free (\d+(?:[.,]\d+)?) GB/i,
    summary: (match) => S.s_o_dia_chua_thu_vien_sach_chi_con_0_gb_c664fd95(match[1].replace(",", ".")),
    hint: S.s_giai_phong_them_dung_luong_o_o_do_lam_sach_0ae5c6e8,
  },
  {
    // Model phân tích không dùng được: Ollama có thể chưa chạy HOẶC chưa có model. Nếu Studio biết model đã mất thì
    // `friendlyError` nói thẳng ở dưới (studioLostModel); còn lại không đoán bừa là lỗi kết nối.
    pattern: /model .* không sẵn sàng/i,
    summary: S.s_chua_dung_duoc_model_phan_tich_truyen_olla_8c2ead55,
    hint: S.s_bam_tiep_tuc_de_thu_lai_neu_van_loi_mo_oll_2d24bc66,
    studioHint: S.s_studio_tu_bat_ollama_rieng_cua_no_bam_tiep_cffd211a,
  },
  {
    pattern: /ollama|11434|actively refused|Connection refused|ConnectionError|Max retries exceeded/i,
    summary: S.s_chua_ket_noi_duoc_ollama_phan_chay_mo_hinh_9408ea80,
    hint: S.s_mo_ollama_bieu_tuong_o_khay_he_thong_roi_b_e00df159,
    // App có Studio: Ollama là bản riêng của Studio, tự bật khi làm sách - không có biểu tượng khay để mở (soát UX a20).
    studioHint: S.s_studio_tu_bat_ollama_rieng_cua_no_nen_khon_10d2c374,
  },
  {
    pattern: /No space left|ENOSPC|disk full|database or disk is full|WinError 112|not enough space|disk quota/i,
    summary: S.s_o_dia_het_cho_trong_3b736e41,
    hint: S.s_giai_phong_dung_luong_o_o_chua_thu_vien_sa_f1ab2981,
  },
];

/** Lỗi thô -> câu cho người nghe + việc nên làm + nguyên văn. Lỗi lạ: "Có lỗi khi làm sách" (không đọc nguyên văn lên mặt).
 *  `bundledStudio`: app đóng gói có Studio (Ollama riêng, không có biểu tượng khay) - lời khuyên theo đó.
 *  `redo`: phân tích đã bị ngắt giữa chừng - nút chính của trang là "Làm lại phân tích từ đầu", "Tiếp tục" chỉ là lối phụ có giá
 *  (stopText.asksBeforeResume), nên lời khuyên chỉ nút chính (soát a88 T3).
 *  `studioLostModel`: Studio báo model phân tích đã mất khỏi máy (appInfo.studio.damagedSteps có "llm") - lỗi liên quan model/Ollama
 *  khi ấy là "mất model", không phải "Ollama chưa chạy", và việc cần làm là Sửa Studio (soát a96 V1). */
export function friendlyError(raw: string, bundledStudio = false, redo = false, studioLostModel = false): FriendlyError {
  const detail = raw.trim();
  if (studioLostModel && /ollama|model|qwen/i.test(detail)) {
    return {
      summary: S.s_studio_mat_model_phan_tich_truyen_file_da_e8f0b483,
      hint: redo
        ? S.s_vao_du_an_bam_sua_studio_de_tai_lai_dung_p_a4f2e4e5
        : S.s_vao_du_an_bam_sua_studio_de_tai_lai_dung_p_68884ea1,
      detail,
    };
  }
  const known = KNOWN.find((entry) => entry.pattern.test(detail));
  const advice = (hint: string) => (redo ? hint.replace(/([Bb])ấm Tiếp tục/g, S.s_1am_lam_lai_phan_tich_tu_dau_af1d00bc) : hint);
  const match = known ? detail.match(known.pattern) : null;
  if (known && match) return { summary: typeof known.summary === "function" ? known.summary(match) : known.summary, hint: advice((bundledStudio && known.studioHint) || known.hint), detail };
  return { summary: S.s_co_loi_khi_lam_sach_469057f5, hint: advice(S.s_bam_tiep_tuc_de_thu_lai_neu_van_loi_mo_chi_c47f6ecc), detail };
}

const OFFLINE = /getaddrinfo failed|\[Errno 11001\]|WinError 11001|WinError 10051|WinError 10060|Network is unreachable|Temporary failure in name resolution|Name or service not known|timed out|Connection (?:aborted|reset)|RemoteDisconnected|IncompleteRead/i;

/** Lỗi dừng dở của bước "Cài Studio" (studio_setup `error`): mất mạng giữa chừng nói bằng lời người nghe và chỉ việc làm tiếp;
 *  nguyên văn vẫn trả lại ở `detail` cho "Chi tiết". Lỗi khác: nguyên văn như cũ (đã là tiếng Việt do máy chủ viết). */
export function friendlySetupError(raw: string): { summary: string; detail: string } {
  const detail = raw.trim();
  if (OFFLINE.test(detail)) return { summary: S.s_mat_mang_giua_chung_bam_cai_tiep_de_lam_ti_c7e5dddf, detail };
  return { summary: detail, detail: "" };
}

import { S } from "../shared/strings.generated";
import { MotionRegion } from "@/shared/MotionRegion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Mic2 } from "lucide-react";
import { useState } from "react";
import { toast } from "@/shared/toast";
import { Switch } from "@/desktop/Switch";
import { SettingsRow } from "@/shared/SettingsNav";
import { cn } from "@/shared/cn";
import { DialogActions, Button, Dialog } from "@/shared/ui";
import { api, type BookSummary } from "./api";
import { pollDelay, retryUnlessGone } from "./polling";
import { costText, needsConfirm, TELLER_ELSEWHERE, TELLER_TITLE, tellerHint, type TellerModeView } from "./tellerMode";

/** Sách đang chạy: Tạm dừng chưa đủ (máy vẫn giữ sách), phải “Dừng”. Dừng lúc này an toàn vì công tắc chỉ mở sau khi máy đã đọc hiểu xong truyện. */
const BUSY_NOTE = S.s_dung_sau_phan_tich_de_doi_roi_tiep_tuc_tam_2623587f;

/** Công tắc "Người kể xưng “tôi” tự kể chuyện" của một cuốn (webui/teller_mode.py), dưới hàng "Người kể chuyện" của tab Nhân vật.
 *  Mặc định tắt. Sách đã có bản thu thì bật / tắt hiện trước số câu phải thu lại và chờ bạn xác nhận; sách đang chạy thì phải bấm “Dừng” trước
 *  (Tạm dừng không đủ - máy vẫn đang giữ sách). Công tắc chỉ khoá sau bước phân tích nên Dừng lúc ấy không đổi sách. */
export function TellerModeSwitch({ book, className }: { book: BookSummary; className?: string }) {
  const client = useQueryClient();
  const [asking, setAsking] = useState<"teller" | "narrator" | null>(null);
  const { data } = useQuery({
    queryKey: ["narrator-mode", book.id],
    queryFn: () => api<TellerModeView>(`/api/books/${book.id}/narrator-mode`),
    refetchInterval: (query) => pollDelay(book.running ? 15_000 : false, query.state),
    retry: retryUnlessGone,
  });
  const save = useMutation({
    mutationFn: ({ mode }: { mode: "teller" | "narrator"; recorded: number }) =>
      api<TellerModeView>(`/api/books/${book.id}/narrator-mode`, { method: "PUT", body: { mode } }),
    onSuccess: (view, { recorded }) => {
      client.setQueryData(["narrator-mode", book.id], view);
      for (const key of ["book", "work", "cast", "script"]) void client.invalidateQueries({ queryKey: [key, book.id] });
      void client.invalidateQueries({ queryKey: ["library"] });
      void client.invalidateQueries({ queryKey: ["listen", "cast", book.id] });  // số câu của người kể và nhân vật trong tab Nhân vật
      setAsking(null);
      // Chỉ nhắc thu lại khi có bản thu bị bỏ (số báo trước lúc đổi); chưa thu câu nào thì máy cứ thu theo giọng mới, không có gì "lại".
      if (view.castLocked && view.mode === "teller" && view.applied) {
        toast.success(recorded > 0 ? S.s_da_doi_bam_tiep_tuc_de_thu_lai_nhung_cau_d_273ea241 : S.s_da_doi_nhung_cau_doi_giong_se_duoc_thu_ban_1a29ee0b);
      }
    },
    onError: (error: Error) => {
      setAsking(null);
      toast.error(S.s_chua_doi_duoc_a6c67cde, { description: error.message });
    },
  });
  if (!data?.available) return <MotionRegion />;
  const on = data.mode === "teller";
  const busy = Boolean(data.castLocked && (book.running || book.starting));
  const readOnly = data.editableHere === false;  // điện thoại mở file dự án: xem được, đổi ở máy tính có Studio
  const id = `teller-mode-${book.id}`;
  const change = (value: boolean) => {
    const mode = value ? "teller" : "narrator";
    if (needsConfirm(data)) setAsking(mode);
    else save.mutate({ mode, recorded: data.plan?.recorded ?? 0 });
  };
  return (
    <MotionRegion>
      {/* Một hàng cài đặt như trang Cài đặt: tên và lời giải thích bên trái, công tắc bên phải - không khung bao. */}
      <div className={cn("mt-3 border-t border-line", className)}>
        <SettingsRow
          label={<span id={`${id}-name`}>{TELLER_TITLE}</span>}
          hint={
            <span id={`${id}-hint`}>
              {readOnly ? tellerHint(on) : busy ? BUSY_NOTE : tellerHint(on)}
              {readOnly && ` ${TELLER_ELSEWHERE}`}
            </span>
          }
        >
          <Switch id={id} labelledBy={`${id}-name`} describedBy={`${id}-hint`} checked={on} disabled={save.isPending || busy || readOnly} onCheckedChange={change} />
        </SettingsRow>
      </div>
      <Dialog footer={<DialogActions>
          <Button variant="ghost" onClick={() => setAsking(null)}>{S.s_thoi_e68f9e88}</Button>
          <Button variant="primary" icon={Mic2} loading={save.isPending} onClick={() => asking && save.mutate({ mode: asking, recorded: data.plan?.recorded ?? 0 })}>
            {asking === "teller" ? S.s_bat_va_thu_lai_16adc647 : S.s_tat_va_thu_lai_dc0f8e21}
          </Button>
        </DialogActions>}
        open={asking !== null}
        onOpenChange={(open) => !open && setAsking(null)}
        title={asking === "teller" ? S.s_bat_giong_tu_ke_ef32d59a : S.s_dung_giong_dan_c9aaaec4}
        description={costText(data.plan, asking === "teller")}
      >

      </Dialog>
    </MotionRegion>
  );
}

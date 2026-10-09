import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { cn } from "@/shared/cn";
import { Progress } from "@/shared/ui";
import { CANCELLED_NOTE, formatSize } from "@/studio/musicLocal";
import { useSource } from "./source";
import { desktopVieneu, useModuleStatus } from "./VieneuModuleCard";
import { initialChoices, meteredNotice, selectionBytes, VIENEU_COPY, vieneuLabel, vieneuPercent, type VieneuStatus } from "./vieneuModule";

/** Tải giọng VieNeu NGAY trong khối lỗi của trình phát (mất mạng mà giọng đang chọn cần mạng): cùng API với thẻ trong Cài đặt - máy tính hỏi máy chủ cục bộ,
 *  điện thoại hỏi lõi native (`source.vieneu`) - nên người nghe không rời màn nghe. Tải xong thì danh sách giọng hỏi lại, khối lỗi tự đổi nút sang
 *  “Đọc bằng …”. Chọn gì để tải: đúng phần đánh dấu sẵn của thẻ (initialChoices). */
export function VieneuDownload({ button, onOpenSettings }: { button: string; onOpenSettings: () => void }) {
  const source = useSource();
  const backend = source.vieneu ?? desktopVieneu;
  const client = useQueryClient();
  const { status, working } = useModuleStatus(backend, VIENEU_COPY);
  const [busy, setBusy] = useState(false);
  if (!status) return null;
  const missing = initialChoices(status).filter((id) => !status.choices.find((choice) => choice.id === id)?.installed);
  const bytes = selectionBytes(status, missing);
  const start = async () => {
    setBusy(true);
    try {
      client.setQueryData(["readaloud", VIENEU_COPY.key], await backend.start(missing));
    } catch (error) {
      toast.error("Chưa tải được giọng VieNeu", { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  const cancel = async () => {
    setBusy(true);
    try {
      client.setQueryData(["readaloud", VIENEU_COPY.key], await backend.cancel!());
    } catch (error) {
      toast.error("Chưa huỷ được việc tải giọng VieNeu", { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  const downloading = status.state === "downloading";
  const failed = status.state === "error";
  const metered = !working && missing.length > 0 ? meteredNotice(status, bytes) : null;
  const note = downloading || failed || status.state === "unsupported" ? vieneuLabel(status as VieneuStatus, VIENEU_COPY) : status.cancelled ? CANCELLED_NOTE : null;
  // Chưa có gì để nói (không tải, không ghi chú): hai nút đứng cùng hàng với "Thử lại" của khối lỗi, không tốn thêm hàng ở màn hẹp.
  const idle = !downloading && !note && !metered;
  return (
    <div className={idle ? "contents" : "flex basis-full flex-col gap-2"}>
      {downloading && (
        <div className="flex items-center gap-3">
          <Progress value={vieneuPercent(status) / 100} size="sm" running label="Đang tải giọng VieNeu" className="flex-1" />
          {backend.cancel && (
            <button
              type="button"
              disabled={busy}
              onClick={() => void cancel()}
              onMouseDown={(event) => event.preventDefault()}
              className="min-h-9 shrink-0 rounded-lg px-2 text-xs font-medium text-fg-2 underline underline-offset-2 hover:text-fg disabled:opacity-60 max-sm:min-h-[44px]"
            >
              Huỷ
            </button>
          )}
        </div>
      )}
      {note && <p className={cn("text-[13px] text-pretty", failed ? "text-danger" : "text-fg-2")}>{note}</p>}
      {metered && <p className="text-[13px] text-fg-2 text-pretty">{metered}</p>}
      <div className={idle ? "contents" : "flex flex-wrap items-center gap-2"}>
        {!downloading && status.state !== "unsupported" && missing.length > 0 && (
          <button
            type="button"
            disabled={busy}
            onClick={() => void start()}
            onMouseDown={(event) => event.preventDefault()}
            className="min-h-9 shrink-0 rounded-lg bg-panel px-3 text-xs font-semibold ring-1 ring-line hover:bg-hover disabled:opacity-60 max-sm:min-h-[44px]"
          >
            {failed ? "Tải lại" : bytes > 0 ? `${button} (${formatSize(bytes)})` : button}
          </button>
        )}
        <button
          type="button"
          onClick={onOpenSettings}
          onMouseDown={(event) => event.preventDefault()}
          className="min-h-9 shrink-0 rounded-lg px-2 text-xs font-medium text-fg-2 underline underline-offset-2 hover:text-fg max-sm:min-h-[44px]"
        >
          Xem trong Cài đặt
        </button>
      </div>
    </div>
  );
}

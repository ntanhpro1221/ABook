import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, Laptop, Loader2, Send, Smartphone, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { localEditsNote } from "@/shared/capabilities";
import { cn } from "@/shared/cn";
import { editsSyncNote, holderName, sentToast } from "@/shared/editsSync";
import { endSentence } from "@/shared/format";
import { Button } from "@/shared/ui";
import { refreshAfterEdit } from "./EditBook";
import type { ListenBook } from "./model";
import { useSource } from "./source";

// Cuốn tải từ máy tính (điện thoại): sửa xong thì phần sửa gửi về máy tính - tự động khi tới được máy tính, hoặc bấm "Gửi về máy
// tính" (docs/EDITING.md, P2b). Chữ nói tình trạng ở shared/editsSync.ts.

const MENU_ITEM = "flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[highlighted]:bg-hover";

/** Gửi ngay phần sửa của cuốn về máy tính. `available`: nguồn này có đường gửi (chỉ điện thoại). */
export function useSendEdits(book: ListenBook) {
  const source = useSource();
  const client = useQueryClient();
  const where = holderName(book.remote);
  const send = useMutation({
    mutationFn: async () => {
      if (!source.sendEdits) throw new Error("Máy này không gửi phần sửa về máy tính");
      return source.sendEdits(book.id);
    },
    onSuccess: (state) => {
      refreshAfterEdit(client, book.id);
      const done = sentToast(state, where);
      toast.success(done.title, { description: done.description, duration: 8000 });
    },
    onError: (error: Error) => {
      refreshAfterEdit(client, book.id);
      toast.error(`Chưa gửi được về ${where}`, { description: `${endSentence(error.message)} Phần sửa vẫn nằm trên máy này.`, duration: 10000 });
    },
  });
  return { send: () => send.mutate(), busy: send.isPending, available: Boolean(source.sendEdits), where };
}

/** Mục "Gửi về máy tính" trong menu của sách; mờ đi (kèm lý do) khi không còn gì để gửi - không giấu. */
export function SendEditsItem({ book }: { book: ListenBook }) {
  const { send, busy, available, where } = useSendEdits(book);
  if (!available) return null;
  const pending = book.editsSync?.pending ?? 0;
  return (
    <DropdownMenu.Item
      disabled={pending === 0 || busy}
      onSelect={send}
      className={cn(MENU_ITEM, "h-auto items-start py-1.5 data-[disabled]:opacity-60")}
    >
      {busy ? <Loader2 className="mt-0.5 size-4 shrink-0 animate-spin" /> : <Send className="mt-0.5 size-4 shrink-0" />}
      <span className="min-w-0">
        <span className="block">{busy ? "Đang gửi…" : pending ? `Gửi về ${where} (${pending} thay đổi)` : `Gửi về ${where}`}</span>
        {!busy && !pending && <span className="block text-xs text-fg-3">Chưa có thay đổi nào chờ gửi</span>}
      </span>
    </DropdownMenu.Item>
  );
}

/** Cuốn của điện thoại khác: sửa xong, nói rõ phần sửa chỉ có trên máy này (không có chỗ gửi). Chưa sửa gì thì không hiện. */
export function LocalEditsBanner({ book }: { book: ListenBook }) {
  const note = localEditsNote(book.capabilities);
  if (!note || !book.edits) return null;
  return (
    <div role="status" className="mt-2 max-w-md rounded-xl bg-info-soft px-3 py-2 text-xs text-info max-sm:mx-auto max-sm:text-left">
      <p className="inline-flex items-center gap-1.5 font-medium">
        <Smartphone className="size-3.5 shrink-0" /> {book.edits} thay đổi chỉ có trên điện thoại này
      </p>
      <p className="mt-0.5 text-pretty">{note}</p>
    </div>
  );
}

const SEEN_KEY = "abook.editsSentSeen.";

function seenAt(id: string): number {
  try {
    return Number(window.localStorage.getItem(SEEN_KEY + id)) || 0;
  } catch {
    return 0;
  }
}

/** Dòng tình trạng dưới tên sách: chưa gửi (và vì sao), hay máy kia đã làm gì với lần gửi vừa rồi. Đã gửi mà không có gì đáng kể thì không
 *  hiện (thông báo lúc gửi đã nói rồi); có điều đáng kể (xung đột, việc chờ duyệt) thì hiện cho tới khi người dùng bấm “Đã hiểu”. */
export function EditsSyncBanner({ book }: { book: ListenBook }) {
  const { send, busy, available, where } = useSendEdits(book);
  const [seen, setSeen] = useState(() => seenAt(book.id));
  // Khung “Chưa tải xong về máy” (desktop/RemoteDownload.tsx) cùng nằm dưới tên sách: cả hai cùng đứt vì máy kia không trả lời thì chỉ
  // một khung nói lý do dài, khung này giữ phần riêng của nó (số thay đổi chưa gửi, nút gửi) - không lặp nguyên câu.
  const download = useQuery<{ state: string; retry?: boolean }>({ queryKey: ["listen", "download", book.id], queryFn: skipToken });
  const found = editsSyncNote(book.editsSync, where);
  const unreachable = /Không kết nối được|không trả lời/.test(book.editsSync?.last?.error ?? "");
  const note =
    found && found.tone === "error" && unreachable && download.data?.state === "failed" && download.data.retry
      ? { ...found, lines: [`Tự gửi khi ${where} trả lời lại; bấm “Gửi về ${where}” để gửi ngay.`] }
      : found;
  if (!note) return null;
  const at = book.editsSync?.last?.at ?? 0;
  if (note.tone === "sent" && (note.lines.length === 0 || seen >= at)) return null;
  const dismiss = () => {
    setSeen(at);
    try {
      window.localStorage.setItem(SEEN_KEY + book.id, String(at));
    } catch {
      // không lưu được thì lần mở sau hiện lại - không sao
    }
  };
  const Icon = note.tone === "error" ? CircleAlert : note.tone === "sent" ? Laptop : Send;
  return (
    <div
      role="status"
      className={cn(
        "mt-2 max-w-md rounded-xl px-3 py-2 text-xs max-sm:mx-auto max-sm:text-left",
        note.tone === "error" ? "bg-danger-soft text-danger" : "bg-info-soft text-info",
      )}
    >
      <p className="inline-flex items-center gap-1.5 font-medium">
        <Icon className="size-3.5 shrink-0" /> {note.title}
      </p>
      {note.lines.map((line) => (
        <p key={line} className="mt-0.5 text-pretty">
          {line}
        </p>
      ))}
      {available && book.editsSync && book.editsSync.pending > 0 && (
        <Button size="sm" variant="secondary" className="mt-2" icon={Send} loading={busy} onClick={send}>
          Gửi về {where}
        </Button>
      )}
      {note.tone === "sent" && (
        <Button size="sm" variant="secondary" className="mt-2" icon={X} onClick={dismiss}>
          Đã hiểu
        </Button>
      )}
    </div>
  );
}

import { S } from "../shared/strings.generated";
import { MotionRegion } from "@/shared/MotionRegion";
import * as DropdownMenu from "@/shared/DropdownMenu";
import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, Laptop, Loader2, Send, Smartphone, Undo2, X } from "lucide-react";
import { useState } from "react";
import { toast, toastDone } from "@/shared/toast";
import { BOOK_STORAGE } from "@/shared/bookStorage";
import { localEditsNote } from "@/shared/capabilities";
import { cn } from "@/shared/cn";
import { editsSyncNote, holderName, sentToast } from "@/shared/editsSync";
import { endSentence } from "@/shared/format";
import { Button } from "@/shared/ui";
import { api } from "@/studio/api";
import { refreshAfterEdit } from "./EditBook";
import type { EditsNotice, ListenBook } from "./model";
import { useSource } from "./source";

// Cuốn tải từ máy tính (điện thoại): sửa xong thì phần sửa gửi về máy tính - tự động khi tới được máy tính, hoặc bấm "Gửi về máy
// tính" (docs/EDITING.md, P2b). Chữ nói tình trạng ở shared/editsSync.ts.

/** Câu cuối của lời báo gửi hỏng (cùng chữ với điện thoại, editbook/BookEditor.kt). */
const KEPT_HERE = S.s_phan_sua_van_nam_tren_may_nay_095e7b80;

const MENU_ITEM = "flex h-9 cursor-default items-center gap-2 rounded-control px-2 text-sm outline-none data-[highlighted]:bg-hover";

/** Gửi ngay phần sửa của cuốn về máy tính. `available`: nguồn này có đường gửi (chỉ điện thoại). */
export function useSendEdits(book: ListenBook) {
  const source = useSource();
  const client = useQueryClient();
  const where = holderName(book.remote);
  const send = useMutation({
    mutationFn: async () => {
      if (!source.sendEdits) throw new Error(S.s_may_nay_khong_gui_phan_sua_ve_may_tinh_82e6f13f);
      return source.sendEdits(book.id);
    },
    onSuccess: (state) => {
      refreshAfterEdit(client, book.id);
      const done = sentToast(state, where);
      toastDone(done.title, done.note, { duration: 8000 });
    },
    onError: (error: Error) => {
      refreshAfterEdit(client, book.id);
      toast.error(S.s_chua_gui_duoc_ve_0_cd4df102(where), { description: `${endSentence(error.message)} ${KEPT_HERE}`, duration: 10000 });
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
      className={cn(MENU_ITEM, "h-auto items-start py-2 data-[disabled]:opacity-60")}
    >
      <MotionRegion as="span" className="mt-1 inline-grid shrink-0 place-items-center">{busy ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}</MotionRegion>
      <span className="min-w-0">
        <span className="block">{busy ? S.s_dang_gui_dd6f95be : S.s_gui_ve_0_50e46c2d(where)}</span>
        {!busy && !pending && <span className="block text-xs text-fg-3">{S.s_chua_co_thay_doi_nao_cho_gui_3f3fce11}</span>}
      </span>
    </DropdownMenu.Item>
  );
}

/** Cuốn của điện thoại khác: sửa xong, nói rõ phần sửa chỉ có trên máy này (không có chỗ gửi). Chưa sửa gì thì không hiện. */
export function LocalEditsBanner({ book }: { book: ListenBook }) {
  const note = localEditsNote(book.capabilities);
  if (!note || !book.edits) return <MotionRegion />;
  return (
    <MotionRegion as="div" role="status" className="mt-2 max-w-md py-2 text-xs text-info max-sm:mx-auto max-sm:text-left">
      <p className="inline-flex items-center gap-2 font-medium">
        <Smartphone className="size-3.5 shrink-0" /> {book.edits}{S.s_thay_doi_chi_co_tren_dien_thoai_nay_fb7327ee}</p>
      <p className="mt-1 text-pretty">{note}</p>
    </MotionRegion>
  );
}

/** Cuốn nhập từ file ở máy này: máy đã ghép gửi bản khác thay bản của máy này (bản đến sau thắng) - từng lời báo nói đổi gì từ gì sang gì;
 *  "Đặt lại" dùng lại bản của máy này (thành thay đổi mới nhất), "Đã hiểu" chỉ bỏ lời báo (soát a70). */
export function EditsNoticesBanner({ book }: { book: ListenBook }) {
  const client = useQueryClient();
  const act = useMutation({
    mutationFn: ({ verb, notice }: { verb: "undo" | "dismiss"; notice?: EditsNotice }) =>
      api(`/api/books/${book.id}/edits-notices/${verb}`, { method: "POST", body: { id: notice?.id ?? "" } }),
    onSuccess: (_reply, { verb }) => {
      refreshAfterEdit(client, book.id);
      if (verb === "undo") toast.success(S.s_da_dat_lai_ban_cua_may_nay_e12443cf);
    },
    onError: (error: Error) => toast.error(S.s_chua_lam_duoc_8b442a06, { description: error.message }),
  });
  const items = book.editsNotices ?? [];
  if (!items.length) return <MotionRegion />;
  return (
    <MotionRegion as="div" role="status" className="mt-2 max-w-md py-2 text-xs text-info max-sm:mx-auto max-sm:text-left">
      <p className="inline-flex items-center gap-2 font-medium">
        <Smartphone className="size-3.5 shrink-0" />{S.s_may_da_ghep_vua_doi_phan_ban_da_dat_cc07a562}</p>
      <ul className="mt-1 space-y-2">
        {items.map((notice) => (
          <li key={notice.id} className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="min-w-0 flex-1 text-pretty">{notice.label}</span>
            <Button size="sm" variant="ghost" icon={Undo2} disabled={act.isPending} onClick={() => act.mutate({ verb: "undo", notice })}>{S.s_hoan_tac_e72ff675}</Button>
          </li>
        ))}
      </ul>
      <Button size="sm" variant="ghost" className="mt-2" icon={X} disabled={act.isPending} onClick={() => act.mutate({ verb: "dismiss" })}>{S.s_da_hieu_9bb82968}</Button>
    </MotionRegion>
  );
}

const SEEN_KEY = BOOK_STORAGE.editsSentSeen;

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
  const unreachable = /(?:Không|Chưa) kết nối được|không trả lời/.test(book.editsSync?.last?.error ?? "");
  const note =
    found && found.tone === "error" && unreachable && download.data?.state === "failed" && download.data.retry
      ? { ...found, lines: [S.s_tu_gui_khi_0_tra_loi_lai_bam_gui_ve_1_de_g_47a67376(where, where)] }
      : found;
  if (!note) return <MotionRegion />;
  const at = book.editsSync?.last?.at ?? 0;
  if (note.tone === "sent" && (note.lines.length === 0 || seen >= at)) return <MotionRegion />;
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
    <MotionRegion as="div"
      role="status"
      className={cn(
        "mt-2 max-w-md rounded-cover px-3 py-2 text-xs max-sm:mx-auto max-sm:text-left",
        note.tone === "error" ? "bg-danger-soft text-danger" : "bg-info-soft text-info",
      )}
    >
      <p className="inline-flex items-center gap-2 font-medium">
        <Icon className="size-3.5 shrink-0" /> {note.title}
      </p>
      {note.lines.map((line) => (
        <p key={line} className="mt-1 text-pretty">
          {line}
        </p>
      ))}
      {available && book.editsSync && book.editsSync.pending > 0 && (
        <Button size="sm" variant="ghost" className="mt-2" icon={Send} loading={busy} onClick={send}>
          {S.s_gui_ve_0_50e46c2d(where)}
        </Button>
      )}
      {note.tone === "sent" && (
        <Button size="sm" variant="ghost" className="mt-2" icon={X} onClick={dismiss}>{S.s_da_hieu_9bb82968}</Button>
      )}
    </MotionRegion>
  );
}

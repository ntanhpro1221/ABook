import { Presence } from "../shared/MotionPresence";
import { S } from "../shared/strings.generated";
import { MotionRegion } from "@/shared/MotionRegion";
import { useListPresence } from "@/shared/motion";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AudioLines, BookOpenCheck, Mic2, RefreshCw, UserRound, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { toast } from "@/shared/toast";
import { formatNumber } from "@/shared/format";
import { DialogActions, Button, Dialog, IconButton } from "@/shared/ui";
import { api } from "./api";
import { useVoiceTry } from "./VoiceTry";
import { estimateText, type VoiceRequest } from "./voiceTryText";
import { useFadeScroller } from "@/shared/scrollFade";

import { Reveal } from "../shared/MotionPresence";
// "Áp dụng N thay đổi" mở hộp này thay vì chạy ngay (soát UX a6 01-10: bấm là chạy, không nói sẽ thu lại gì, hết bao lâu; số
// trên nút còn lệch với "chờ áp dụng" ở Việc cần duyệt vì sửa ở Kịch bản / đổi giọng không được liệt kê ở đâu). Máy chủ
// (store.pending_details) liệt kê đủ từng thay đổi bằng lời, số câu ĐÃ THU sẽ thu lại, ở chương nào, và thời gian ước theo
// tốc độ thật của chính cuốn này (chưa đo được thì số ước, nói rõ là ước). Đổi giọng nghe thử được ngay trong hộp, trên một câu
// của chính người ấy (VoiceTry.tsx) - soát UX Studio mục 15: áp là thu lại mà chưa nghe giọng mới lần nào.

export interface PendingItem {
  kind: "pronunciation" | "speaker" | "line" | "voice" | "retake";
  label: string;
  chapter?: string;
  lines: number;
  /** Đủ để bỏ đúng yêu cầu này (POST …/pending-changes/withdraw). */
  section: string;
  key: string;
  /** "Thu lại cả chương": mọi câu của một lần bấm - bỏ thì bỏ cả nhóm. */
  keys?: string[];
  requestedAt: number;
  /** Đổi giọng: đủ để nghe thử đúng giọng sẽ áp (POST …/voice/preview). */
  voice?: VoiceRequest;
  /** Tên giọng đang chờ để hiện ("Bảo Trang"); `voice.preset` là khoá gửi máy chủ. */
  voiceLabel?: string;
  /** Tên máy đã ghép gửi việc này tới (cuốn nhập từ file - book_wishes.note_sources); không có: ghi ở chính máy này. */
  from?: string;
}

export interface PendingDetails {
  items: PendingItem[];
  lines: number;
  chapters: string[];
  seconds: number;
  /** False: cuốn chưa xong chương nào để đo - `seconds` là số ước dư tay. */
  measured?: boolean;
}

export const KIND_ICON = { pronunciation: BookOpenCheck, speaker: UserRound, line: AudioLines, voice: Mic2, retake: RefreshCw } as const;

/** Nút bỏ một dòng nói rõ nó bỏ gì ("Bỏ cách đọc “Lucien”") - mọi nút cùng nhãn "Bỏ thay đổi này" thì trình đọc màn hình (và chú thích khi rê
 *  chuột) không phân biệt được dòng nào (soát a70). */
export function dropLabel(item: Pick<PendingItem, "kind" | "label">): string {
  if (item.kind === "pronunciation") {
    const surface = /^“([^”]+)”/.exec(item.label)?.[1];
    if (surface) return S.s_bo_cach_doc_0_a883978b(surface);
  }
  const verb = { pronunciation: S.s_bo_cach_doc_98ceb6ae, speaker: S.s_bo_doi_nguoi_noi_4787bbf3, line: S.s_bo_sua_cach_doc_cau_2b4e183f, voice: S.s_bo_doi_giong_d165cd63, retake: S.s_bo_thu_lai_ed903b0f }[item.kind] ?? S.s_bo_e07d3f4d;
  return `${verb}: ${item.label}`;
}

/** Danh sách từng thay đổi đang chờ, mỗi dòng có nút bỏ (`dropLabel`) - dùng cho cả hộp "Áp dụng" (dự án) lẫn hộp "Việc đang chờ
 *  Studio" của sách không có xưởng (listen/WishesDialog.tsx). `dropping` = id đang bỏ dở; `showLines`: hiện số câu thu lại;
 *  `extra`: nút thêm của một dòng (nghe thử giọng chờ áp). */
export function PendingList({
  items,
  dropping,
  onDrop,
  showLines = true,
  extra,
}: {
  items: PendingItem[];
  dropping: string | null;
  onDrop: (item: PendingItem) => void;
  showLines?: boolean;
  extra?: (item: PendingItem) => ReactNode;
}) {
  const scrollFade = useFadeScroller<HTMLUListElement>();
  const rows = useListPresence(items, (item) => `${item.section}:${item.key}`);
  return (
    <ul ref={scrollFade.ref} style={scrollFade.style} className="max-h-72 divide-y divide-line overflow-y-auto">
      {rows.map(({ item, key, state, ref }) => {
        const Icon = KIND_ICON[item.kind] ?? RefreshCw;
        return (
          <li key={key} ref={ref} className="motion-row" data-state={state} inert={state === "exit"}><div className="flex items-start gap-3 py-2 text-sm">
            <Icon className="mt-line-icon size-4 shrink-0 text-fg-3" />
            <span className="min-w-0 flex-1 text-pretty">
              {item.label}
              <Reveal when={item.chapter}><span className="text-fg-3"> · {item.chapter}</span></Reveal>
              <Reveal when={item.from}><span className="text-fg-3">{S.s_tu_02926cd1}{item.from}</span></Reveal>
            </span>
            <Reveal when={showLines}><span className="shrink-0 pt-1 text-xs text-fg-3">
                {item.lines ? S.s_0_cau_thu_lai_372ad9c3(formatNumber(item.lines)) : S.s_chua_thu_khong_ton_gi_d0da00cf}
              </span></Reveal>
            {<Presence>{extra && <span className="-my-1 shrink-0">{extra(item)}</span>}</Presence>}
            <IconButton
              size="sm"
              icon={X}
              label={dropLabel(item)}
              className="-my-2 -mr-2"
              disabled={dropping !== null}
              onClick={() => onDrop(item)}
            />
          </div></li>
        );
      })}
    </ul>
  );
}

export function ApplyChangesDialog({
  bookId,
  count,
  open,
  onOpenChange,
  onApply,
  running,
}: {
  bookId: string;
  count: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApply: () => void;
  /** Sách đang chạy: máy tự áp ở ranh giới chương kế nên không có nút "Áp dụng". Bỏ một việc thì bất cứ lúc nào (máy chủ từ chối việc đã áp). */
  running?: "busy" | "checkpoint";
}) {
  const client = useQueryClient();
  const [dropping, setDropping] = useState<string | null>(null);
  const tryVoice = useVoiceTry(bookId);
  // Bỏ một mục ngay tại đây (soát UX a6 01-10: muốn bỏ thì phải đi tìm lại đúng thẻ ở ba tab). Lựa chọn trước đó, nếu có,
  // trở lại; mọi màn đọc lại (số trên nút, Việc cần duyệt, Kịch bản).
  const drop = async (item: PendingItem) => {
    const id = `${item.section}:${item.key}`;
    setDropping(id);
    try {
      await api(`/api/books/${bookId}/pending-changes/withdraw`, {
        method: "POST",
        body: { section: item.section, key: item.key, keys: item.keys, requestedAt: item.requestedAt },
      });
      if (count <= 1) onOpenChange(false);
      await client.invalidateQueries();
    } catch (error) {
      toast.error(S.s_chua_bo_duoc_thay_doi_nay_eccfaf9b, { description: (error as Error).message });
    } finally {
      setDropping(null);
    }
  };
  const { data } = useQuery({
    queryKey: ["pending-changes", bookId, count],
    queryFn: () => api<PendingDetails>(`/api/books/${bookId}/pending-changes`),
    enabled: open,
  });
  const chapters = data?.chapters ?? [];
  const shownChapters = chapters.slice(0, 4).join(", ") + (chapters.length > 4 ? S.s_va_0_chuong_khac_e2145ca8(chapters.length - 4) : "");
  return (
    <Dialog footer={<DialogActions>
        <Button variant="ghost" onClick={() => onOpenChange(false)}>
          {running ? S.s_dong_5d54c2a1 : S.s_de_sau_9be0a7ab}
        </Button>
        <Reveal when={!running}><Button
            variant="primary"
            icon={RefreshCw}
            onClick={() => {
              onOpenChange(false);
              onApply();
            }}
          >{S.s_ap_dung_ff631576}</Button></Reveal>
      </DialogActions>}
      open={open}
      onOpenChange={onOpenChange}
      width="max-w-[560px]"
      title={running ? S.s_0_thay_doi_dang_cho_ap_663ea37f(count) : S.s_ap_dung_0_thay_doi_b7955e0a(count)}
      description={
        running
          ? S.s_tu_ap_o_chuong_ke_tiep_chi_bo_duoc_viec_ch_6f3e60e9
          : S.s_may_chi_thu_lai_nhung_cau_bi_anh_huong_roi_67af5454
      }
    ><MotionRegion>
      {!data ? (
        <p className="text-sm text-fg-2">{S.s_dang_xem_cac_thay_doi_765915d5}</p>
      ) : (
        <>
          <PendingList
            items={data.items}
            dropping={dropping}
            onDrop={(item) => void drop(item)}
            extra={(item) => (item.voice ? tryVoice.button(item.voice, item.voiceLabel || S.s_moi_54e203ba) : null)}
          />
          {tryVoice.note}
          <p className="mt-3 text-sm text-pretty">
            {data.lines ? (
              <>{S.s_thu_lai_bceb80c2}<span className="font-medium">{formatNumber(data.lines)}{S.s_cau_b07e1008}</span>{S.s_o_ce0ade07}{chapters.length}{S.s_chuong_1c106b8b}{shownChapters})
                {data.seconds > 0 && <> - {estimateText(data.seconds, data.measured)}</>}.
              </>
            ) : (
              S.s_chi_ghi_thay_doi_khong_thu_lai_cau_nao_ad9ef853
            )}
          </p>
        </>
      )}

    </MotionRegion></Dialog>
  );
}

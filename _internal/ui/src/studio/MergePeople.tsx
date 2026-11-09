import { S } from "../shared/strings.generated";
import { MotionRegion } from "@/shared/MotionRegion";
import { useQueryClient } from "@tanstack/react-query";
import { GitMerge, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "@/shared/toast";
import { cleanName } from "@/listen/BookScreen";
import { voiceName, type CastMember } from "@/listen/model";
import { cn } from "@/shared/cn";
import { formatNumber } from "@/shared/format";
import { DialogActions, SelectionMark, Button, Dialog } from "@/shared/ui";
import { api } from "./api";
import { nameKey, sameNames } from "./workText";
import { useFadeScroller } from "@/shared/scrollFade";

// Tab Nhân vật: "Gộp vào…" (soát UX a6 01-10: máy tách một người thành hai - tên đầy đủ và tên gọi, có chức danh và không -
// mà Studio chỉ sửa được từng câu). Máy chủ chuyển mọi câu nói của người này sang người kia và ghi bí danh để phần sau
// của cuốn tự hiểu (POST /characters/merge). Không áp ngay: như mọi sửa khác, áp theo trạng thái sách (decisions.ts).

/** Giọng người ấy SẼ đọc: giọng người nghe vừa chọn mà chưa áp, nếu có (soát UX a23 B4: hộp Gộp nói giọng cũ). */
export function voiceToUse(member: Pick<CastMember, "voice" | "pendingVoice">): string {
  return member.pendingVoice?.preset ? voiceName(member.pendingVoice) : voiceName(member.voice);
}

export function MergeDialog({
  bookId,
  person,
  people,
  onClose,
  onSaved,
}: {
  bookId: string;
  person: CastMember | null;
  people: CastMember[];
  onClose: () => void;
  /** Cuốn không có xưởng (file .abook): chỉ ghi ý muốn chờ Studio. */
  /** Làm mới thêm các màn của trang nghe (số thay đổi chưa lưu). */
  onSaved?: () => void;
}) {
  const scrollFade = useFadeScroller<HTMLUListElement>();
  const client = useQueryClient();
  const [query, setQuery] = useState("");
  const [into, setInto] = useState<CastMember | null>(null);
  const [busy, setBusy] = useState(false);
  const others = useMemo(() => {
    const words = query.trim().toLowerCase();
    return people
      .filter((other) => other.name !== person?.name && other.voice)
      .filter((other) => !words || cleanName(other.displayName).toLowerCase().includes(words));
  }, [people, person, query]);
  // Vai phụ trùng tên (ba "Lính gác 1" ở ba chương): dòng ghi thêm chương đầu người ấy lên tiếng (soát UX a23).
  const twins = useMemo(() => sameNames(people), [people]);
  const close = () => {
    setQuery("");
    setInto(null);
    onClose();
  };
  const merge = async () => {
    if (!person || !into) return;
    setBusy(true);
    try {
      const { lines } = await api<{ lines: number }>(`/api/books/${bookId}/characters/merge`, {
        method: "POST",
        body: { from: person.name, into: into.name },
      });
      toast.success(S.s_da_ghi_0_cau_cua_1_la_cua_2_099ed4e5(lines, cleanName(person.displayName), cleanName(into.displayName)));
      void client.invalidateQueries();
      onSaved?.();
      close();
    } catch (error) {
      toast.error(S.s_chua_gop_duoc_3d63128a, { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  const name = person ? cleanName(person.displayName) : "";
  return (
    <Dialog footer={<DialogActions>
        <Button variant="ghost" onClick={close}>{S.s_thoi_e68f9e88}</Button>
        <Button variant="primary" icon={GitMerge} disabled={!into} loading={busy} onClick={() => void merge()}>{S.s_gop_2380bed6}</Button>
      </DialogActions>}
      open={person !== null}
      onOpenChange={(open) => !open && close()}
      width="max-w-lg"
      title={S.s_gop_nhan_vat_37b51bd5}
      description={S.s_moi_cau_cua_0_va_cac_phan_sau_dung_nguoi_b_75a7c03f(name)}
    >
      <label className="relative block">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-fg-3" />
        <input
          id="merge-search"
          value={query}
          autoFocus
          onChange={(event) => setQuery(event.target.value)}
          placeholder={S.s_tim_nguoi_trong_truyen_a1507054}
          className="h-9 w-full rounded-control border border-line bg-bg pl-8 pr-2.5 text-sm outline-none focus-visible:border-focus"
        />
      </label>
      <MotionRegion motionKey={[others.map(other => other.name), !others.length && query]}>
      <ul ref={scrollFade.ref} style={scrollFade.style} className="mt-2 max-h-64 overflow-y-auto" role="listbox" aria-label={S.s_gop_vao_ai_640d3477}>
        {others.length ? (
          others.map((other) => (
            <li key={other.name}>
              <button
                type="button"
                role="option"
                aria-selected={into?.name === other.name}
                onClick={() => setInto(other)}
                className={cn(
                  "flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors duration-motion-fast",
                  into?.name === other.name ? "text-accent-text" : "hover:bg-hover",
                )}
              >
                <SelectionMark selected={into?.name === other.name} /><span className="min-w-0 flex-1 truncate font-medium">{cleanName(other.displayName)}</span>
                <span className="shrink-0 text-xs text-fg-3">
                  {voiceToUse(other)}
                  {other.pendingVoice?.preset ? S.s_cho_ap_dung_31faa52d : ""} · {formatNumber(other.lines)}{S.s_cau_b07e1008}{twins.has(nameKey(other.displayName)) && other.firstChapter ? ` · ${other.firstChapter}` : ""}
                </span>
              </button>
            </li>
          ))
        ) : (
          <li className="px-3 py-3 text-sm text-fg-2">{S.s_khong_co_ai_khop_2213386e}{query}”.</li>
        )}
      </ul>
      </MotionRegion>
      <MotionRegion>
      {person && into && (
        <p className="mt-3 text-sm text-pretty">
          {formatNumber(person.lines)}{S.s_cau_cua_35c4143d}<span className="font-semibold">{name}</span>{S.s_thanh_cua_788f02d8}{" "}
          <span className="font-semibold">{cleanName(into.displayName)}</span>{S.s_doc_bang_giong_0e64b444}{voiceToUse(into)}
          {into.pendingVoice?.preset ? S.s_giong_vua_chon_cho_ap_dung_23afd9d2 : ""}.
        </p>
      )}
      </MotionRegion>

    </Dialog>
  );
}

import { useQueryClient } from "@tanstack/react-query";
import { GitMerge, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { cleanName } from "@/listen/BookScreen";
import type { CastMember } from "@/listen/model";
import { cn } from "@/shared/cn";
import { formatNumber } from "@/shared/format";
import { Button, Dialog } from "@/shared/ui";
import { api } from "./api";
import { WAITING_STUDIO } from "./decisions";

// Tab Nhân vật: "Gộp vào…" (soát UX a6 01-10: máy tách một người thành hai - tên đầy đủ và tên gọi, có chức danh và không -
// mà Studio chỉ sửa được từng câu). Máy chủ chuyển mọi câu nói của người này sang người kia và ghi bí danh để phần sau
// của cuốn tự hiểu (POST /characters/merge). Không áp ngay: như mọi sửa khác, chờ "Áp dụng thay đổi"; bỏ được trong hộp ấy.

export function MergeDialog({
  bookId,
  person,
  people,
  onClose,
  waiting = false,
  onSaved,
}: {
  bookId: string;
  person: CastMember | null;
  people: CastMember[];
  onClose: () => void;
  /** Cuốn không có xưởng (file .abook): chỉ ghi ý muốn chờ Studio. */
  waiting?: boolean;
  /** Làm mới thêm các màn của trang nghe (số thay đổi chưa lưu). */
  onSaved?: () => void;
}) {
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
      toast.success(`Đã ghi: ${lines} câu của ${cleanName(person.displayName)} là của ${cleanName(into.displayName)}`, {
        description: waiting
          ? WAITING_STUDIO
          : "Các phần sau của truyện cũng hiểu hai tên là một người. Bấm “Áp dụng thay đổi” để thu lại; bỏ được trong hộp ấy.",
      });
      void client.invalidateQueries();
      onSaved?.();
      close();
    } catch (error) {
      toast.error("Chưa gộp được", { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  const name = person ? cleanName(person.displayName) : "";
  return (
    <Dialog
      open={person !== null}
      onOpenChange={(open) => !open && close()}
      width="max-w-lg"
      title={`Gộp ${name} vào người khác`}
      description={`Khi máy tách một người thành hai tên. Mọi câu của ${name} sẽ đọc bằng giọng người bạn chọn, và các phần sau của truyện cũng hiểu hai tên là một.`}
    >
      <label className="relative block">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-fg-3" />
        <input
          id="merge-search"
          value={query}
          autoFocus
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Tìm người trong truyện…"
          className="h-9 w-full rounded-lg border border-line bg-bg pl-8 pr-2.5 text-sm outline-none focus-visible:border-accent"
        />
      </label>
      <ul className="mt-2 max-h-64 overflow-y-auto rounded-xl border border-line" role="listbox" aria-label="Gộp vào ai">
        {others.length ? (
          others.map((other) => (
            <li key={other.name}>
              <button
                type="button"
                role="option"
                aria-selected={into?.name === other.name}
                onClick={() => setInto(other)}
                className={cn(
                  "flex w-full items-center gap-2 px-3 py-2 text-left text-sm",
                  into?.name === other.name ? "bg-accent-soft" : "hover:bg-hover",
                )}
              >
                <span className="min-w-0 flex-1 truncate font-medium">{cleanName(other.displayName)}</span>
                <span className="shrink-0 text-xs text-fg-3">
                  {other.voice?.preset} · {formatNumber(other.lines)} câu
                </span>
              </button>
            </li>
          ))
        ) : (
          <li className="px-3 py-3 text-sm text-fg-2">Không có ai khớp “{query}”.</li>
        )}
      </ul>
      {person && into && (
        <p className="mt-3 text-sm text-pretty">
          {formatNumber(person.lines)} câu của <span className="font-semibold">{name}</span> thành của{" "}
          <span className="font-semibold">{cleanName(into.displayName)}</span>, đọc bằng giọng {into.voice?.preset}.
        </p>
      )}
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" onClick={close}>
          Thôi
        </Button>
        <Button variant="primary" icon={GitMerge} disabled={!into} loading={busy} onClick={() => void merge()}>
          Gộp
        </Button>
      </div>
    </Dialog>
  );
}

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { cleanName } from "@/listen/BookScreen";
import type { CastMember } from "@/listen/model";
import { formatNumber } from "@/shared/format";
import { Button, Dialog, Segmented } from "@/shared/ui";
import { api } from "./api";
import { refreshAfterDecision, UNDO_MS, undoAction, useWhenApplied } from "./decisions";

// Tab Nhân vật: "Đổi tên" và "Đổi giới tính" của một người.
// - Đổi tên chỉ là cái tên trên màn hình (POST /characters/rename -> names.json): không đổi giọng hay audio, có hiệu lực ngay.
// - Đổi giới tính đi đúng đường của thẻ "Nam hay nữ" (POST /voice): một thay đổi chờ "Áp dụng thay đổi", hoàn tác được.

export function RenamePersonDialog({
  bookId,
  person,
  onClose,
  onSaved,
}: {
  bookId: string;
  person: CastMember | null;
  onClose: () => void;
  /** Gọi sau khi đổi tên xong - trang nghe làm mới thư viện, chữ đọc theo, dàn nhân vật (listen/EditBook.tsx). */
  onSaved?: () => void;
}) {
  const client = useQueryClient();
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => setValue(person ? cleanName(person.displayName) : ""), [person]);
  const save = async (next: string) => {
    if (!person) return;
    setBusy(true);
    try {
      const answer = await api<{ name: string; renamed: boolean }>(`/api/books/${bookId}/characters/rename`, {
        method: "POST",
        body: { character: person.name, name: next },
      });
      refreshAfterDecision(client, bookId);
      onSaved?.();
      toast.success(answer.renamed ? `Đã đổi tên thành ${cleanName(answer.name)}` : `Đã trở về tên gốc: ${cleanName(answer.name)}`, {
        description: "Chỉ đổi cái tên hiện trên màn hình - giọng đọc và audio giữ nguyên. Các phần sau của truyện cũng dùng tên này.",
      });
      onClose();
    } catch (error) {
      toast.error("Chưa đổi được tên", { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  const name = person ? cleanName(person.displayName) : "";
  return (
    <Dialog
      open={person !== null}
      onOpenChange={(open) => !open && onClose()}
      width="max-w-md"
      title={`Đổi tên ${name}`}
      description="Chỉ đổi cái tên hiện trên màn hình. Giọng đọc và audio không đổi."
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void save(value);
        }}
      >
        <input
          id="rename-person"
          data-autofocus
          value={value}
          maxLength={80}
          onChange={(event) => setValue(event.target.value)}
          aria-label={`Tên mới của ${name}`}
          className="h-9 w-full rounded-lg border border-line bg-bg px-2.5 text-sm outline-none focus-visible:border-accent"
        />
        {person?.originalName && <p className="mt-2 text-xs text-fg-2">Tên gốc: {cleanName(person.originalName)}</p>}
        <div className="mt-5 flex justify-end gap-2">
          {person?.originalName && (
            <Button type="button" variant="ghost" disabled={busy} onClick={() => void save("")}>
              Về tên gốc
            </Button>
          )}
          <Button type="button" variant="ghost" onClick={onClose}>
            Thôi
          </Button>
          <Button type="submit" variant="primary" loading={busy} disabled={!value.trim()}>
            Lưu
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

type Gender = "male" | "female";
const GENDERS: { value: Gender; label: string }[] = [
  { value: "male", label: "Nam" },
  { value: "female", label: "Nữ" },
];

/** Giới người nghe đang thấy ở dòng nhân vật: giới chờ áp dụng nếu có, không thì giới trong sổ. */
function shownGender(person: CastMember | null): Gender | null {
  const label = person?.pendingVoice?.gender || person?.gender;
  return label === "Nam" ? "male" : label === "Nữ" ? "female" : null;
}

export function GenderDialog({ bookId, person, onClose }: { bookId: string; person: CastMember | null; onClose: () => void }) {
  const client = useQueryClient();
  const when = useWhenApplied(bookId);
  const current = shownGender(person);
  const [choice, setChoice] = useState<Gender | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => setChoice(shownGender(person)), [person]);
  const name = person ? cleanName(person.displayName) : "";
  const recorded = person?.recorded ?? 0;
  const save = async () => {
    if (!person || !choice) return;
    setBusy(true);
    try {
      const { requestedAt } = await api<{ requestedAt: number }>(`/api/books/${bookId}/voice`, {
        method: "POST",
        body: { character: person.name, gender: choice },
      });
      refreshAfterDecision(client, bookId);
      const label = choice === "female" ? "nữ" : "nam";
      toast.success(`Đã ghi: ${name} là nhân vật ${label}`, {
        description: `${recorded ? "Nếu giọng đang đọc chưa hợp giới này, các câu đã thu của người ấy sẽ đọc lại bằng giọng mới. " : ""}${when}`,
        action: undoAction(client, bookId, "voice", [{ character: person.name, requestedAt, keep: false }], `${name} trở lại như trước khi đổi giới tính.`),
        duration: UNDO_MS,
      });
      onClose();
    } catch (error) {
      toast.error("Chưa đổi được giới tính", { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog
      open={person !== null}
      onOpenChange={(open) => !open && onClose()}
      width="max-w-md"
      title={`Giới tính của ${name}`}
      description={current ? `Hiện đang là nhân vật ${current === "female" ? "nữ" : "nam"}.` : "Máy chưa xác định được giới của người này."}
    >
      <Segmented<Gender> value={(choice ?? "") as Gender} onChange={setChoice} options={GENDERS} label="Giới tính" />
      {recorded > 0 && (
        <p className="mt-3 text-sm text-pretty">
          {name} đã có {formatNumber(recorded)} câu được thu. Khi bấm “Áp dụng thay đổi”, nếu giọng đang đọc không hợp giới mới,
          mọi câu đã thu của {name} sẽ được thu lại bằng giọng mới; nếu giọng đã hợp, chỉ ghi nhớ giới và không câu nào bị thu lại.
        </p>
      )}
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          Thôi
        </Button>
        <Button variant="primary" loading={busy} disabled={!choice || choice === current} onClick={() => void save()}>
          Ghi lại
        </Button>
      </div>
    </Dialog>
  );
}

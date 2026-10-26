import { MotionRegion } from "@/shared/MotionRegion";
import { useQueryClient } from "@tanstack/react-query";
import { useId, useEffect, useState } from "react";
import { toast } from "@/shared/toast";
import { cleanName } from "@/listen/BookScreen";
import type { CastMember } from "@/listen/model";
import { formatNumber } from "@/shared/format";
import { DialogActions, Button, Dialog, ChoiceRow } from "@/shared/ui";
import { api } from "./api";
import { refreshAfterDecision, UNDO_MS, undoAction } from "./decisions";
import { voiceToUse } from "./MergePeople";

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
  const dialogForm1 = useId();
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
      toast.success(answer.renamed ? `Đã đổi tên thành ${cleanName(answer.name)}` : `Đã trở về tên gốc: ${cleanName(answer.name)}`);
      onClose();
    } catch (error) {
      toast.error("Chưa đổi được tên", { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  const name = person ? cleanName(person.displayName) : "";
  return (
    <Dialog footer={<DialogActions>
          {person?.originalName && (
            <Button type="button" variant="ghost" disabled={busy} onClick={() => void save("")}>
              Về tên gốc
            </Button>
          )}
          <Button type="button" variant="ghost" onClick={onClose}>
            Thôi
          </Button>
          <Button type="submit" form={dialogForm1} variant="primary" loading={busy} disabled={!value.trim()}>
            Lưu
          </Button>
        </DialogActions>}
      open={person !== null}
      onOpenChange={(open) => !open && onClose()}
      width="max-w-md"
      title={`Đổi tên ${name}`}
      description="Chỉ đổi tên hiển thị, giữ giọng và audio."
    >
      <form id={dialogForm1}
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
          className="h-9 w-full rounded-control border border-line bg-bg px-2.5 text-sm outline-none focus-visible:border-focus"
        />
        {person?.originalName && <p className="mt-2 text-xs text-fg-2">Tên gốc: {cleanName(person.originalName)}</p>}

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

/** `waiting`: cuốn không có xưởng (file .abook) - chỉ ghi ý muốn chờ Studio, câu nói và việc làm lại ở trên không đúng nữa.
 *  `onSaved`: làm mới thêm các màn của trang nghe (số thay đổi chưa lưu). */
export function GenderDialog({ bookId, person, onClose, waiting = false, onSaved }: {
  bookId: string;
  person: CastMember | null;
  onClose: () => void;
  waiting?: boolean;
  onSaved?: () => void;
}) {
  const client = useQueryClient();
  const current = shownGender(person);
  const [choice, setChoice] = useState<Gender | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => setChoice(shownGender(person)), [person]);
  const name = person ? cleanName(person.displayName) : "";
  const recorded = waiting ? 0 : (person?.recorded ?? 0);
  const save = async () => {
    if (!person || !choice) return;
    setBusy(true);
    try {
      const { requestedAt } = await api<{ requestedAt: number }>(`/api/books/${bookId}/voice`, {
        method: "POST",
        body: { character: person.name, gender: choice },
      });
      refreshAfterDecision(client, bookId);
      onSaved?.();
      const label = choice === "female" ? "nữ" : "nam";
      toast.success(`Đã ghi: ${name} là nhân vật ${label}`, {
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
    <Dialog footer={<DialogActions>
        <Button variant="ghost" onClick={onClose}>
          Thôi
        </Button>
        <Button variant="primary" loading={busy} disabled={!choice || choice === current} onClick={() => void save()}>
          Ghi lại
        </Button>
      </DialogActions>}
      open={person !== null}
      onOpenChange={(open) => !open && onClose()}
      width="max-w-md"
      title={`Giới tính của ${name}`}
      description={current ? `Hiện đang là nhân vật ${current === "female" ? "nữ" : "nam"}.` : "Máy chưa xác định được giới của người này."}
    >
      <MotionRegion>
      <ChoiceRow<Gender> value={(choice ?? "") as Gender} onChange={setChoice} options={GENDERS} label="Giới tính" />
      {waiting && <p className="mt-3 text-sm text-pretty">Giọng đọc của {name} chưa đổi ngay - Studio sẽ làm khi bạn mở file này ở máy có Studio.</p>}
      {/* Chưa có câu nào được thu: vẫn nói giọng sẽ đổi - đổi giới là đổi giọng (soát UX a23: hộp không nói). */}
      {!waiting && recorded === 0 && person && choice && choice !== current && (
        <p className="mt-3 text-sm text-pretty">
          Nếu giọng {voiceToUse(person) ? `${voiceToUse(person)} ` : ""}đang đọc {name} không hợp giới mới, máy chọn một giọng{" "}
          {choice === "female" ? "nữ" : "nam"} khác cho người ấy khi áp dụng.
        </p>
      )}
      {recorded > 0 && (
        <p className="mt-3 text-sm text-pretty">
          Áp dụng sẽ thu lại {formatNumber(recorded)} câu của {name} nếu giọng chưa hợp giới mới.
        </p>
      )}
      </MotionRegion>

    </Dialog>
  );
}

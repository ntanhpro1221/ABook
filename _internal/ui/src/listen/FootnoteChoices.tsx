import { footnoteSummary, type FootnoteChoice, type FootnoteNotes, type FootnoteOffer } from "./textImport";

// Chú thích trong sách nhập ("Thêm sách từ file…", bước xem trước): máy nói tìm thấy gì và ĐỀ XUẤT; mặc định không tích gì, sách giữ nguyên như file.
// Tích thì danh sách chương và chữ đổi theo (đọc lại file); bỏ tích là về như cũ. Máy tính và điện thoại dùng chung.

function Choice({
  checked,
  disabled,
  onChange,
  label,
  help,
}: {
  checked: boolean;
  disabled: boolean;
  onChange: (on: boolean) => void;
  label: string;
  help: string;
}) {
  return (
    <label className="touch-row flex items-start gap-2.5 text-sm">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-0.5 size-4 shrink-0 accent-[var(--accent)]"
      />
      <span className="min-w-0">
        <span className="block font-medium">{label}</span>
        <span className="block text-xs text-fg-2">{help}</span>
      </span>
    </label>
  );
}

export function FootnoteChoices({
  offer,
  value,
  disabled,
  onChange,
}: {
  offer: FootnoteOffer;
  value: FootnoteChoice;
  disabled: boolean;
  onChange: (next: FootnoteChoice) => void;
}) {
  const { title, example } = footnoteSummary(offer);
  const notes = (on: boolean, kind: Exclude<FootnoteNotes, "">) => onChange({ ...value, notes: on ? kind : "" });
  return (
    <div className="mt-3 rounded-xl border border-line bg-hover p-3" data-testid="footnote-choices">
      <p className="text-xs font-medium">{title} - ABook không tự bỏ hay sửa chữ của truyện</p>
      {example && <p className="mt-0.5 text-xs text-fg-2">{example}</p>}
      <div className="mt-2 space-y-1">
        {offer.marks > 0 && (
          <Choice
            checked={value.hideMarks}
            disabled={disabled}
            onChange={(on) => onChange({ ...value, hideMarks: on })}
            label="Không đọc số chú thích"
            help="Bỏ các con số như ² hay [3] khỏi phần đọc; lời chú không đổi."
          />
        )}
        <Choice
          checked={value.notes === "end"}
          disabled={disabled}
          onChange={(on) => notes(on, "end")}
          label="Đọc lời chú ở cuối chương"
          help="Mỗi lời chú nằm ở cuối chương có số gọi nó, kể cả khi trong sách nó nằm ở chương riêng."
        />
        <Choice
          checked={value.notes === "drop"}
          disabled={disabled}
          onChange={(on) => notes(on, "drop")}
          label="Bỏ lời chú"
          help="Phần đọc không có lời chú nào. Bỏ tích để có lại."
        />
      </div>
      <p className="mt-1 text-xs text-fg-2">Không tích gì thì sách giữ nguyên như trong file.</p>
    </div>
  );
}

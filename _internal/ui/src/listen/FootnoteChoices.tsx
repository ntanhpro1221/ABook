import { ChoiceRow } from "@/shared/ui";
import { footnoteSummary, type FootnoteChoice, type FootnoteNotes, type FootnoteOffer } from "./textImport";

// Chú thích trong sách nhập ("Thêm sách từ file…", bước xem trước): máy nói tìm thấy gì và ĐỀ XUẤT; mặc định giữ nguyên như file.
// Đổi lựa chọn thì danh sách chương và chữ đổi theo (đọc lại file). Cùng chữ, cùng thứ tự với điện thoại (addbook/AddBookScreen.kt): "Bỏ số gọi", rồi
// "Lời chú" chọn một trong Giữ nguyên / Cuối chương / Bỏ lời chú (một giá trị trong lõi, nên là nhóm chọn-một chứ không phải hai ô tích).

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
  return (
    <div className="mt-3 py-3" data-testid="footnote-choices">
      <p className="text-xs font-medium">{title}</p>
      {example && <p className="mt-0.5 text-xs text-fg-2">{example}</p>}
      <div className="mt-2 space-y-3">
        {offer.marks > 0 && (
          <Choice
            checked={value.hideMarks}
            disabled={disabled}
            onChange={(on) => onChange({ ...value, hideMarks: on })}
            label="Bỏ số gọi"
            help={`${offer.marks} số gọi trong chữ. Bỏ các con số như ² hay [3] khỏi phần đọc; lời chú không đổi.`}
          />
        )}
        {/* ChoiceRow không có trạng thái tắt: lúc đang đọc lại file, cả nhóm mờ đi và không nhận chạm / phím (như ô tích bên trên). */}
        <div inert={disabled} className={disabled ? "opacity-60" : undefined}>
          <p className="text-sm font-medium">Lời chú</p>
          <ChoiceRow<FootnoteNotes>
            value={value.notes}
            onChange={(notes) => onChange({ ...value, notes })}
            label="Lời chú"
            options={[
              { value: "", label: "Giữ nguyên" },
              { value: "end", label: "Cuối chương" },
              { value: "drop", label: "Bỏ lời chú" },
            ]}
          />
          <p className="mt-1 text-xs text-fg-2">Bạn chọn Giữ nguyên để giữ lời chú như trong file; Cuối chương đặt mỗi lời chú ở cuối chương có số gọi nó.</p>
        </div>
      </div>
    </div>
  );
}

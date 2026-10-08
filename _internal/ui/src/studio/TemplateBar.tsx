import { BookmarkPlus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button, Segmented } from "@/shared/ui";
import { useAppInfo, usePreferences } from "@/studio/data";
import {
  DEFAULT_LABEL,
  NAME_MAX,
  cleanName,
  findTemplate,
  isFull,
  isModified,
  nameProblem,
  templateFromDraft,
  templatesOf,
  upsertTemplate,
  type BookTemplate,
  type TemplateFields,
} from "@/studio/bookTemplates";

// "Mẫu thiết lập" ở trình tạo sách: chọn một mẫu đã lưu thì giọng kể, chất lượng, model đọc hiểu và "bắt đầu ngay" của nháp
// theo mẫu (nguồn truyện, tên sách... không đụng tới); "Lưu thành mẫu…" chụp các lựa chọn hiện tại. Qua Studio từ xa chỉ chọn
// được - ghi tuỳ chọn là việc của chính máy tính (remote_studio.py không mở PUT /api/preferences), nên nút lưu ẩn đi.
export function TemplateBar({ draft, onPick }: {
  draft: TemplateFields;
  /** null = "Mặc định": các lựa chọn mặc định của app cho sách mới. */
  onPick: (template: BookTemplate | null) => void;
}) {
  const { data: preferences, update, updating } = usePreferences();
  const { data: info } = useAppInfo();
  const remote = Boolean(info?.remote);
  const templates = templatesOf(preferences?.bookTemplates);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [problem, setProblem] = useState("");
  // Lưu / huỷ xong thì ô tên biến mất và tiêu điểm rơi về đầu trang: trả nó về nút "Lưu thành mẫu…" (soát UX 02-10).
  const saveButton = useRef<HTMLButtonElement>(null);
  const wasSaving = useRef(false);
  useEffect(() => {
    if (wasSaving.current && !saving) saveButton.current?.focus();
    wasSaving.current = saving;
  }, [saving]);

  const active = findTemplate(templates, draft.template);
  const modified = active ? isModified(draft, active) : false;
  if (!templates.length && remote) return null;

  const close = () => {
    setSaving(false);
    setConfirming(false);
    setProblem("");
  };
  const submit = () => {
    const existing = findTemplate(templates, name);
    const wrong = nameProblem(templates, name, existing?.name) || (!existing && isFull(templates) ? "Đã có đủ 20 mẫu - xoá bớt một mẫu trong Cài đặt trước" : "");
    if (wrong) {
      setProblem(wrong);
      return;
    }
    if (existing && !confirming) {
      setConfirming(true);
      return;
    }
    const saved = templateFromDraft(draft, name);
    update(
      { bookTemplates: upsertTemplate(templates, saved) },
      {
        onSuccess: () => {
          toast.success(`Đã lưu mẫu “${saved.name}”`);
          onPick(saved);
          close();
        },
        onError: (error) => setProblem(error.message),
      },
    );
  };

  return (
    <div className="mb-6 rounded-xl border border-line bg-panel px-4 py-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="text-sm font-medium">Mẫu thiết lập</span>
        {templates.length > 0 && (
          <Segmented<string>
            label="Mẫu thiết lập"
            wrap
            value={active?.name ?? ""}
            onChange={(value) => onPick(value ? (findTemplate(templates, value) ?? null) : null)}
            options={[
              { value: "", label: DEFAULT_LABEL },
              ...templates.map((item) => ({ value: item.name, label: item.name === active?.name && modified ? `${item.name} (đã sửa)` : item.name })),
            ]}
          />
        )}
        {!remote && !saving && (
          <Button
            ref={saveButton}
            size="sm"
            variant="ghost"
            icon={BookmarkPlus}
            className="ml-auto"
            onClick={() => {
              setName(active?.name ?? "");
              setSaving(true);
            }}
          >
            Lưu thành mẫu…
          </Button>
        )}
      </div>
      {modified && active && (
        <p className="mt-2 text-[13px] text-fg-2">Bạn đã đổi so với mẫu “{active.name}”. Bấm lại tên mẫu để trở về như đã lưu.</p>
      )}
      {!templates.length && !saving && !remote && (
        <p className="mt-2 text-[13px] text-fg-2">Lưu các lựa chọn dưới đây thành mẫu để dùng lại cho những cuốn sau.</p>
      )}
      {saving && (
        <form
          className="mt-3"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <div className="flex flex-wrap items-center gap-2">
            <input
              autoFocus
              value={name}
              maxLength={NAME_MAX}
              aria-label="Tên mẫu"
              aria-invalid={Boolean(problem)}
              placeholder="Tên mẫu, ví dụ Light novel"
              onChange={(event) => {
                setName(event.target.value);
                setConfirming(false);
                setProblem("");
              }}
              onKeyDown={(event) => {
                if (event.key === "Escape") close();
              }}
              className="h-9 min-w-0 flex-1 rounded-lg border border-line bg-bg px-3 text-sm outline-none placeholder:text-fg-3 focus:border-accent sm:max-w-xs"
            />
            {confirming ? (
              <>
                <Button type="submit" size="sm" variant="primary" loading={updating}>
                  Ghi đè
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
                  Đặt tên khác
                </Button>
              </>
            ) : (
              <>
                <Button type="submit" size="sm" variant="primary" loading={updating} disabled={!cleanName(name)}>
                  Lưu
                </Button>
                <Button size="sm" variant="ghost" onClick={close}>
                  Huỷ
                </Button>
              </>
            )}
          </div>
          {confirming && <p className="mt-2 text-[13px] text-fg-2">Đã có mẫu “{findTemplate(templates, name)?.name}”. Ghi đè bằng các lựa chọn hiện tại?</p>}
          {problem && <p role="alert" className="mt-2 text-[13px] text-danger">{problem}</p>}
          <p className="mt-2 text-[13px] text-fg-3">Mẫu nhớ giọng kể, chất lượng, bộ phân tích truyện và chuyện có bắt đầu ngay không. Không nhớ truyện, tên sách hay dòng ghi công.</p>
        </form>
      )}
    </div>
  );
}

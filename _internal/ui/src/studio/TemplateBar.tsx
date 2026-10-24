import { MoreInfo } from "@/shared/SettingsNav";
import { useBackLayer } from "@/shared/backStack";
import { MotionRegion } from "@/shared/MotionRegion";
import { BookmarkPlus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "@/shared/toast";
import { Button, Segmented } from "@/shared/ui";
import { useAvailableModelNames } from "@/studio/AnalysisModelPicker";
import { useBookTemplateOp, usePreferences, useVoices } from "@/studio/data";
import {
  DEFAULT_LABEL,
  NAME_MAX,
  cleanName,
  findTemplate,
  isFull,
  isModified,
  missingModel,
  missingModelNote,
  missingVoice,
  missingVoiceNote,
  nameProblem,
  templateFromDraft,
  templatesOf,
  type BookTemplate,
  type TemplateFields,
} from "@/studio/bookTemplates";

// "Mẫu thiết lập" ở trình tạo sách: chọn một mẫu đã lưu thì giọng kể, chất lượng, model đọc hiểu và "bắt đầu ngay" của nháp
// theo mẫu (nguồn truyện, tên sách... không đụng tới); "Lưu thành mẫu…" chụp các lựa chọn hiện tại. Lưu là MỘT thao tác gửi lên
// máy tính (useBookTemplateOp, POST /api/book-templates) nên Studio từ xa lưu được như trên máy tính; trùng tên thì hỏi ghi đè.
export function TemplateBar({ draft, onPick, narratorAuto = false }: {
  draft: TemplateFields;
  /** Giọng kể đang do máy chọn (bạn chưa bấm giọng nào): mẫu lưu ra ghi "máy chọn", không ghim tên giọng. */
  narratorAuto?: boolean;
  /** null = "Mặc định": các lựa chọn mặc định của app cho sách mới. */
  onPick: (template: BookTemplate | null) => void;
}) {
  const { data: preferences } = usePreferences();
  const { run, running } = useBookTemplateOp();
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
  const modelNames = useAvailableModelNames();
  const modified = active ? isModified(draft, active, modelNames) : false;
  const lostModel = missingModel(active, modelNames);
  const { data: voices } = useVoices();
  const lostVoice = missingVoice(active, voices?.map((voice) => voice.name));

  const close = () => {
    setSaving(false);
    setConfirming(false);
    setProblem("");
  };
  const formBox = useRef<HTMLFormElement>(null);
  useBackLayer(saving, () => confirming ? setConfirming(false) : close(), formBox, saveButton);
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
    const saved = templateFromDraft(draft, name, narratorAuto);
    // Trùng tên: máy tính giữ chỗ cũ của mẫu và chỉ đè khi đã được hỏi ("replace"). Máy khác vừa lưu cùng tên (409): danh sách tải lại, bấm Lưu lần nữa sẽ hỏi ghi đè.
    run(
      { op: "save", template: saved, replace: Boolean(existing) },
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
    <MotionRegion as="div" className="mb-6 rounded-xl border border-line bg-panel px-4 py-3">
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
        {!saving && (
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
        <p className="mt-2 text-[0.8125rem] text-fg-2">Bấm lại mẫu “{active.name}” để khôi phục thiết lập đã lưu.</p>
      )}
      {lostVoice && <p className="mt-2 text-[0.8125rem] text-fg-2">{missingVoiceNote(lostVoice)}</p>}
      {lostModel && <p className="mt-2 text-[0.8125rem] text-fg-2">{missingModelNote(lostModel)}</p>}
      {!templates.length && !saving && (
        <p className="mt-2 text-[0.8125rem] text-fg-2">Lưu các lựa chọn dưới đây thành mẫu để dùng lại cho những cuốn sau.</p>
      )}
      {saving && (
        <form
          ref={formBox}
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
              className="h-9 min-w-0 flex-1 rounded-lg border border-line bg-bg px-3 text-sm outline-none placeholder:text-fg-3 focus:border-focus sm:max-w-xs"
            />
            {confirming ? (
              <>
                <Button type="submit" size="sm" variant="primary" loading={running}>
                  Ghi đè
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
                  Đặt tên khác
                </Button>
              </>
            ) : (
              <>
                <Button type="submit" size="sm" variant="primary" loading={running} disabled={!cleanName(name)}>
                  Lưu
                </Button>
                <Button size="sm" variant="ghost" onClick={close}>
                  Huỷ
                </Button>
              </>
            )}
          </div>
          {confirming && <p className="mt-2 text-[0.8125rem] text-fg-2">Đã có mẫu “{findTemplate(templates, name)?.name}”. Ghi đè bằng các lựa chọn hiện tại?</p>}
          {problem && <p role="alert" className="mt-2 text-[0.8125rem] text-danger">{problem}</p>}
          <p className="mt-2 text-[0.8125rem] text-fg-3">Mẫu lưu giọng, chất lượng và cách tạo sách.</p>
          <MoreInfo>Gồm bộ phân tích, bắt đầu ngay và duyệt trước khi thu. Không lưu truyện, tên sách hay dòng ghi công.</MoreInfo>
        </form>
      )}
    </MotionRegion>
  );
}

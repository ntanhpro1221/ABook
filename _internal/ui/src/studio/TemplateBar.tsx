import { S } from "../shared/strings.generated";
import { MoreInfo } from "@/shared/SettingsNav";
import { useBackLayer } from "@/shared/backStack";
import { MotionRegion } from "@/shared/MotionRegion";
import { BookmarkPlus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "@/shared/toast";
import { Button, ChoiceRow } from "@/shared/ui";
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
    const wrong = nameProblem(templates, name, existing?.name) || (!existing && isFull(templates) ? S.s_da_co_du_20_mau_xoa_bot_mot_mau_trong_cai_c3b1c3a3 : "");
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
          toast.success(S.s_da_luu_mau_0_73392b8c(saved.name));
          onPick(saved);
          close();
        },
        onError: (error) => setProblem(error.message),
      },
    );
  };

  return (
    <MotionRegion as="div" className="mb-6 py-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="text-sm font-medium">{S.s_mau_thiet_lap_be32f35e}</span>
        {templates.length > 0 && (
          <ChoiceRow<string>
            label={S.s_mau_thiet_lap_be32f35e}
            wrap
            value={active?.name ?? ""}
            onChange={(value) => onPick(value ? (findTemplate(templates, value) ?? null) : null)}
            options={[
              { value: "", label: DEFAULT_LABEL },
              ...templates.map((item) => ({ value: item.name, label: item.name === active?.name && modified ? S.s_0_da_sua_d46146e2(item.name) : item.name })),
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
          >{S.s_luu_thanh_mau_3b28bc8b}</Button>
        )}
      </div>
      {modified && active && (
        <p className="mt-2 text-body-small text-fg-2">{S.s_bam_lai_mau_26ea82c5}{active.name}{S.s_de_khoi_phuc_thiet_lap_da_luu_095b8a08}</p>
      )}
      {lostVoice && <p className="mt-2 text-body-small text-fg-2">{missingVoiceNote(lostVoice)}</p>}
      {lostModel && <p className="mt-2 text-body-small text-fg-2">{missingModelNote()}</p>}
      {!templates.length && !saving && (
        <p className="mt-2 text-body-small text-fg-2">{S.s_luu_cac_lua_chon_duoi_day_thanh_mau_de_dun_8513aa2f}</p>
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
              aria-label={S.s_ten_mau_f037fdd2}
              aria-invalid={Boolean(problem)}
              placeholder={S.s_ten_mau_vi_du_light_novel_aae56cfd}
              onChange={(event) => {
                setName(event.target.value);
                setConfirming(false);
                setProblem("");
              }}
              onKeyDown={(event) => {
                if (event.key === "Escape") close();
              }}
              className="h-9 min-w-0 flex-1 rounded-control border border-line bg-bg px-3 text-sm outline-none placeholder:text-fg-3 focus:border-focus sm:max-w-xs"
            />
            {confirming ? (
              <>
                <Button type="submit" size="sm" variant="primary" loading={running}>{S.s_ghi_de_5e4cd1eb}</Button>
                <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>{S.s_dat_ten_khac_78e8f19c}</Button>
              </>
            ) : (
              <>
                <Button type="submit" size="sm" variant="primary" loading={running} disabled={!cleanName(name)}>{S.s_luu_e91f26c0}</Button>
                <Button size="sm" variant="ghost" onClick={close}>{S.s_huy_96732485}</Button>
              </>
            )}
          </div>
          {confirming && <p className="mt-2 text-body-small text-fg-2">{S.s_da_co_mau_8527783b}{findTemplate(templates, name)?.name}{S.s_ghi_de_bang_cac_lua_chon_hien_tai_c2f33cd5}</p>}
          {problem && <p role="alert" className="mt-2 text-body-small text-danger">{problem}</p>}
          <p className="mt-2 text-body-small text-fg-3">{S.s_mau_luu_giong_chat_luong_va_cach_tao_sach_143fa4bf}</p>
          <MoreInfo>{S.s_gom_bo_phan_tich_bat_dau_ngay_va_duyet_tru_7f1b3642}</MoreInfo>
        </form>
      )}
    </MotionRegion>
  );
}

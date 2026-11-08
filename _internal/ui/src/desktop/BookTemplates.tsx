import { S } from "../shared/strings.generated";
import { MotionRegion } from "@/shared/MotionRegion";
import { AnimatedRows, MotionPresence } from "@/shared/MotionPresence";
import { useBackLayer } from "@/shared/backStack";
import { useRef, useState } from "react";
import { toast } from "@/shared/toast";
import { Button } from "@/shared/ui";
import { useBookTemplateOp, usePreferences } from "@/studio/data";
import { NAME_MAX, PROFILE_LABEL, nameProblem, staleTemplateError, templateIndex, templatesOf, type BookTemplate } from "@/studio/bookTemplates";

// Mẫu thiết lập đã lưu từ trình tạo sách (studio/bookTemplates.ts): đổi tên, xoá (có "Hoàn tác"). Lưu mẫu mới làm ở trình tạo. Mỗi việc là
// một thao tác riêng gửi lên máy tính (useBookTemplateOp) nên chạy được cả qua Studio từ xa, và hai thiết bị cùng sửa không đè mất nhau.
export function BookTemplates() {
  const { data: preferences } = usePreferences();
  const { run } = useBookTemplateOp();
  const templates = templatesOf(preferences?.bookTemplates);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [typed, setTyped] = useState("");
  const [problem, setProblem] = useState("");
  const renameBox = useRef<HTMLFormElement>(null);
  useBackLayer(renaming !== null, () => setRenaming(null), renameBox);
  // Mẫu vừa bị thiết bị khác xoá / đặt trùng tên: nói đúng lời máy tính báo (danh sách đã tự tải lại); việc khác hỏng thì nói không lưu được.
  const fail = (error: Error) =>
    staleTemplateError(error) ? toast.error(error.message) : toast.error(S.s_chua_luu_duoc_mau_f9aea903, { description: error.message });
  const finishRename = (from: string) => {
    const wrong = nameProblem(templates, typed, from);
    if (wrong) {
      setProblem(wrong);
      return;
    }
    run(
      { op: "rename", from, to: typed },
      {
        onSuccess: () => setRenaming(null),
        onError: (error) => {
          fail(error);
          // Mẫu đã bị xoá thì không còn gì để đổi tên; trùng tên thì giữ ô nhập để chọn tên khác.
          if ((error as { status?: number }).status === 404) setRenaming(null);
        },
      },
    );
  };
  const remove = (template: BookTemplate) => {
    const index = templateIndex(templates, template.name);
    run(
      { op: "delete", name: template.name },
      {
        onSuccess: () =>
          toast(S.s_da_xoa_mau_0_28991c54(template.name), {
            duration: 10000,
            action: { label: S.s_hoan_tac_e72ff675, onClick: () => run({ op: "restore", template, index }, { onError: fail }) },
          }),
        onError: fail,
      },
    );
  };
  return (
    <MotionRegion as="div" className="mb-4 max-w-xl">
      <div className="text-sm font-medium">{S.s_mau_sach_moi_6e860e3e}</div>
      <p className="mt-0.5 text-[0.8125rem] text-fg-2 text-pretty">{S.s_o_tao_sach_chon_luu_thanh_mau_de_dung_lai_a2505ca9}</p>
      {!templates.length ? (
        <p className="mt-2 text-[0.8125rem] text-fg-3">{S.s_chua_co_mau_nao_55b4683e}</p>
      ) : (
        // Xoá / Hoàn tác một mẫu: hàng khép / mở tại chỗ; đổi tên <-> hàng thường thì hàng tự mờ qua. data-motion-live: cả vùng không mờ theo từng hàng.
        <div data-motion-live="">
        <AnimatedRows className="mt-2 divide-y divide-line" items={templates} keyOf={(template) => template.name}>
          {(template) => (
            <MotionRegion motionKey={renaming === template.name} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 py-2">
              {renaming === template.name ? (
                <form
                  ref={renameBox}
                  className="flex min-w-0 flex-1 flex-wrap items-center gap-2"
                  onSubmit={(event) => {
                    event.preventDefault();
                    finishRename(template.name);
                  }}
                >
                  <input
                    autoFocus
                    value={typed}
                    maxLength={NAME_MAX}
                    aria-label={S.s_ten_moi_cua_mau_0_bb9744ca(template.name)}
                    aria-invalid={Boolean(problem)}
                    onChange={(event) => {
                      setTyped(event.target.value);
                      setProblem("");
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "Escape") setRenaming(null);
                    }}
                    className="h-8 min-w-0 flex-1 rounded-control border border-line bg-bg px-2.5 text-sm outline-none focus:border-focus"
                  />
                  <Button type="submit" size="sm" variant="primary" disabled={!typed.trim()}>{S.s_luu_e91f26c0}</Button>
                  <Button size="sm" variant="ghost" onClick={() => setRenaming(null)}>{S.s_huy_96732485}</Button>
                  <MotionPresence className="basis-full" open={Boolean(problem)}><p role="alert" className="text-[0.8125rem] text-danger">{problem}</p></MotionPresence>
                </form>
              ) : (
                <>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{template.name}</div>
                    <div className="truncate text-[0.8125rem] text-fg-2">
                      {[template.narrator || S.s_giong_may_de_xuat_35389626, PROFILE_LABEL[template.profile], template.startNow ? S.s_bat_dau_ngay_83137873 : S.s_cho_bam_bat_dau_5d760870, ...(template.precastWait ? [S.s_cho_ban_duyet_truoc_khi_thu_35299b41] : [])].join(" · ")}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setRenaming(template.name);
                      setTyped(template.name);
                      setProblem("");
                    }}
                  >{S.s_doi_ten_a2a0dc70}</Button>
                  <Button size="sm" variant="ghost" onClick={() => remove(template)}>{S.s_xoa_777195ab}</Button>
                </>
              )}
            </MotionRegion>
          )}
        </AnimatedRows>
        </div>
      )}
    </MotionRegion>
  );
}

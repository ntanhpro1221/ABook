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
    staleTemplateError(error) ? toast.error(error.message) : toast.error("Không lưu được mẫu", { description: error.message });
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
          toast(`Đã xoá mẫu “${template.name}”`, {
            duration: 10000,
            action: { label: "Hoàn tác", onClick: () => run({ op: "restore", template, index }, { onError: fail }) },
          }),
        onError: fail,
      },
    );
  };
  return (
    <MotionRegion as="div" className="mb-4 max-w-xl">
      <div className="text-sm font-medium">Mẫu sách mới</div>
      <p className="mt-0.5 text-[0.8125rem] text-fg-2 text-pretty">
        Ở Tạo sách, chọn “Lưu thành mẫu…” để dùng lại.
      </p>
      {!templates.length ? (
        <p className="mt-2 text-[0.8125rem] text-fg-3">Chưa có mẫu nào.</p>
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
                    aria-label={`Tên mới của mẫu “${template.name}”`}
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
                  <Button type="submit" size="sm" variant="primary" disabled={!typed.trim()}>
                    Lưu
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setRenaming(null)}>
                    Huỷ
                  </Button>
                  <MotionPresence className="basis-full" open={Boolean(problem)}><p role="alert" className="text-[0.8125rem] text-danger">{problem}</p></MotionPresence>
                </form>
              ) : (
                <>
                  <div className="min-w-0 flex-1">
                    <div className="[overflow-wrap:anywhere] whitespace-normal text-sm font-medium">{template.name}</div>
                    <div className="[overflow-wrap:anywhere] whitespace-normal text-[0.8125rem] text-fg-2">
                      {[template.narrator || "Giọng máy đề xuất", PROFILE_LABEL[template.profile], template.startNow ? "bắt đầu ngay" : "chờ bấm bắt đầu", ...(template.precastWait ? ["chờ bạn duyệt trước khi thu"] : [])].join(" · ")}
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
                  >
                    Đổi tên
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => remove(template)}>
                    Xoá
                  </Button>
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

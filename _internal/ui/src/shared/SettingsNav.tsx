// Khung Cài đặt dùng chung hai nền (chủ app 23-10: "trong setting tôi như lạc vào một cái ma trận"): trang gốc là danh sách ngắn các nhóm
// (biểu tượng + tên + một dòng giá trị hiện tại), mỗi nhóm một màn con `/settings/<nhóm>` - route thật nên Back của điện thoại, vuốt cạnh và
// nút ← cùng về trang gốc. Không có cấp thứ ba. Cây nhóm và lý do: SETTINGS_MAP (a119).
import { AudioLines, ChevronDown, ChevronLeft, ChevronRight, CircleHelp, Clapperboard, Headphones, MonitorSmartphone, MoonStar, Palette, Wrench, type LucideIcon } from "lucide-react";
import { useId, useState, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router";
import { cn } from "./cn";
import { Collapse, useFold } from "./Collapse";

export type SettingsGroupId = "voice" | "listen" | "sleep" | "look" | "devices" | "studio" | "advanced";

/** Thứ tự = tần suất dùng: giọng đọc trước, mục kỹ thuật cuối. */
export const SETTINGS_GROUPS: readonly { id: SettingsGroupId; label: string; icon: LucideIcon }[] = [
  { id: "voice", label: "Giọng đọc", icon: AudioLines },
  { id: "listen", label: "Nghe", icon: Headphones },
  { id: "sleep", label: "Hẹn giờ ngủ", icon: MoonStar },
  { id: "look", label: "Giao diện", icon: Palette },
  { id: "devices", label: "Thiết bị", icon: MonitorSmartphone },
  { id: "studio", label: "Studio", icon: Clapperboard },
  { id: "advanced", label: "Nâng cao", icon: Wrench },
];

export function isSettingsGroup(value: string | undefined): value is SettingsGroupId {
  return SETTINGS_GROUPS.some((group) => group.id === value);
}

export function settingsPath(group?: SettingsGroupId): string {
  return group ? `/settings/${group}` : "/settings";
}

export function groupLabel(id: SettingsGroupId): string {
  return SETTINGS_GROUPS.find((group) => group.id === id)?.label ?? "";
}

/** Một dòng của trang gốc: nhóm nào có mặt trên nền này và giá trị hiện tại của nó. */
export interface GroupRow {
  id: SettingsGroupId;
  summary?: string;
}

/** Danh sách nhóm. `current`: máy tính hai cột - nhóm đang mở bên phải sáng lên, đổi nhóm như đổi tab (không chồng lịch sử). */
export function SettingsList({ rows, current, className }: { rows: readonly GroupRow[]; current?: SettingsGroupId; className?: string }) {
  const location = useLocation();
  const replace = current !== undefined;
  const shown = SETTINGS_GROUPS.filter((group) => rows.some((row) => row.id === group.id));
  return (
    <nav aria-label="Nhóm cài đặt" className={cn("divide-y divide-line overflow-hidden rounded-2xl border border-line bg-panel", className)}>
      {shown.map(({ id, label, icon: Icon }) => {
        const summary = rows.find((row) => row.id === id)?.summary;
        return (
          <NavLink
            key={id}
            to={settingsPath(id)}
            replace={replace}
            state={{ settingsList: !replace || Boolean(location.state?.settingsList) }}
            aria-current={id === current ? "page" : undefined}
            className={cn("flex min-h-[3.5rem] items-center gap-3.5 px-4 py-2.5 transition-colors hover:bg-hover", id === current && "bg-hover")}
          >
            <Icon className="size-5 shrink-0 text-fg-2" strokeWidth={1.9} aria-hidden />
            <span className="min-w-0 flex-1">
              <span className="block text-[0.9375rem] font-medium">{label}</span>
              {summary && <span className="block truncate text-xs text-fg-2">{summary}</span>}
            </span>
            <ChevronRight className="size-4 shrink-0 text-fg-3" aria-hidden />
          </NavLink>
        );
      })}
    </nav>
  );
}

/** Nút ← của màn con: như Back của hệ thống - về trang trước nếu có (vào từ trình phát thì về trình phát), không thì về trang gốc Cài đặt. */
export function useLeaveSettingsGroup(): () => void {
  const navigate = useNavigate();
  const location = useLocation();
  return () => {
    const idx = (typeof window === "undefined" ? null : (window.history.state as { idx?: number } | null))?.idx ?? 0;
    if (location.state?.settingsList || (location.state?.settingsList === undefined && idx > 0)) navigate(-1);
    else navigate(settingsPath(), { replace: true });
  };
}

/** Đầu màn con: nút ← và tên nhóm. `back={false}`: máy tính hai cột, danh sách nhóm đã ở bên trái. */
export function GroupHeader({ id, back = true }: { id: SettingsGroupId; back?: boolean }) {
  const leave = useLeaveSettingsGroup();
  return (
    <div className="flex items-center gap-1">
      {back && (
        <button type="button" onClick={leave} aria-label="Về Cài đặt" className="touch-box -ml-2 grid size-10 place-items-center rounded-lg text-fg-2 hover:bg-hover">
          <ChevronLeft className="size-5" />
        </button>
      )}
      <h1 className="text-2xl font-bold tracking-tight">{groupLabel(id)}</h1>
    </div>
  );
}

/** Khối trong màn con: tiêu đề nhỏ + thẻ. `fold` (khoá nhớ): khối ít dùng trong một nhóm dài gập lại sau tiêu đề bấm được (a120 - chủ app: nhiều
 *  đầu mục thì "foldout chúng lại"); mở rồi thì lần sau vẫn mở. */
export function SettingsBlock({ title, id, children, className, fold }: { title?: string; id?: string; children: ReactNode; className?: string; fold?: string }) {
  if (fold && title) return <FoldedBlock title={title} id={id} storageKey={fold} className={className}>{children}</FoldedBlock>;
  return (
    <section id={id} className={cn("mt-6 first:mt-4", className)}>
      {title && <h2 className="mb-2 px-1 text-xs font-semibold uppercase tracking-wider text-fg-3">{title}</h2>}
      <div className="divide-y divide-line rounded-2xl border border-line bg-panel">{children}</div>
    </section>
  );
}

function FoldedBlock({ title, id, children, className, storageKey }: { title: string; id?: string; children: ReactNode; className?: string; storageKey: string }) {
  const [open, setOpen] = useFold(`settings.${storageKey}`);
  const bodyId = useId();
  return (
    <section id={id} className={cn("mt-6 first:mt-4", className)}>
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-fg-3">
        <button type="button" aria-expanded={open} aria-controls={bodyId} onClick={() => setOpen(!open)} className="touch-row -mx-1 flex w-[calc(100%+0.5rem)] items-center justify-between gap-2 rounded-lg px-2 py-1 text-left uppercase hover:bg-hover">
          {title}
          <ChevronDown className="fold-chevron size-4 shrink-0" aria-hidden />
        </button>
      </h2>
      <Collapse open={open} id={bodyId}>
        <div className="divide-y divide-line rounded-2xl border border-line bg-panel">{children}</div>
      </Collapse>
    </section>
  );
}

/** Một dòng tuỳ chọn: tên (+ một dòng mô tả ngắn khi thật cần) bên trái, điều khiển bên phải; hẹp thì điều khiển xuống hàng. */
export function SettingsRow({ label, hint, children }: { label: ReactNode; hint?: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3">
      <div className="min-w-0 flex-[1_1_12rem]">
        <div className="text-[0.9375rem] font-medium [overflow-wrap:anywhere]">{label}</div>
        {hint && <div className="mt-0.5 text-xs leading-snug text-fg-2 [overflow-wrap:anywhere]">{hint}</div>}
      </div>
      {children !== undefined && <div className="ml-auto max-w-full">{children}</div>}
    </div>
  );
}

/** Giải thích dài mà người dùng cần biết (quyền riêng tư, an toàn dữ liệu) gập sau nút "?" - không chiếm chỗ khi không cần. */
export function MoreInfo({ children, label = "Tìm hiểu thêm", className }: { children: ReactNode; label?: string; className?: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <div className={className}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((now) => !now)}
        className="touch-hit inline-flex items-center gap-1 text-xs font-medium text-accent-text"
      >
        <CircleHelp className="size-3.5" aria-hidden />
        {label}
      </button>
      <Collapse open={open} id={id} className="pt-1 text-xs leading-snug text-fg-2 text-pretty">
        {children}
      </Collapse>
    </div>
  );
}

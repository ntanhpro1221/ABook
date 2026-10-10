import { Check, Download, FolderOpen, Monitor, Moon, Sun } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useMediaQuery } from "@/shared/media";
import { Button, Dialog, Segmented, TimeSelect, radioGroupKeys, radioTabIndex } from "@/shared/ui";
import { ThirdPartyList } from "@/shared/ThirdPartyList";
import { cn } from "@/shared/cn";
import { api } from "@/studio/api";
import { pickFolder, useAppInfo, usePreferences, useVoices } from "@/studio/data";
import { StudioSettings } from "@/studio/StudioSetup";
import {
  NAME_MAX,
  PROFILE_LABEL,
  nameProblem,
  removeTemplate,
  renameTemplate,
  templatesOf,
  type BookTemplate,
} from "@/studio/bookTemplates";
import { SharedReadingsSettings } from "@/studio/sharedReadings";
import { SupertonicModuleCard, VieneuModuleCard } from "@/listen/VieneuModuleCard";
import { EXTEND_GESTURE } from "@/listen/extendGesture";
import { ShortcutList } from "@/listen/Shortcuts";
import { MyMusicSection } from "@/listen/MyMusic";
import { AUTO_MUSIC_HINT, AUTO_MUSIC_LABEL } from "@/listen/playlistBed";
import { VoiceSettings, type KeyCheck, type OnlineProviderInfo, type VoiceSettingsApi } from "@/listen/VoiceSettings";
import { httpSource } from "./httpSource";
import { OtherComputers } from "./OtherComputers";
import { PhoneSync, Switch } from "./PhoneSync";

// Mặc định cho sách MỚI (soát UX a5 01-10: mỗi lần tạo sách lại chọn giọng kể và chất lượng như lần trước). "Làm tiếp cuốn
// này" vẫn theo phần trước.
function NewBookDefaults() {
  const { data: preferences, update } = usePreferences();
  const { data: voices } = useVoices();
  const selectClass = "h-9 w-full rounded-lg border border-line bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-accent";
  return (
    <div className="mb-4 grid max-w-xl gap-3 sm:grid-cols-2">
      <label htmlFor="new-book-narrator" className="block">
        <span className="block text-sm font-medium">Giọng kể cho sách mới</span>
        <select
          id="new-book-narrator"
          className={cn(selectClass, "mt-1")}
          value={preferences?.newBookNarrator ?? ""}
          onChange={(event) => update({ newBookNarrator: event.target.value })}
        >
          <option value="">Giọng máy đề xuất</option>
          {(voices ?? []).map((voice) => (
            <option key={voice.name} value={voice.name}>
              {voice.name} · {voice.gender}, miền {voice.region}
            </option>
          ))}
        </select>
      </label>
      <label htmlFor="new-book-profile" className="block">
        <span className="block text-sm font-medium">Chất lượng cho sách mới</span>
        <select
          id="new-book-profile"
          className={cn(selectClass, "mt-1")}
          value={preferences?.newBookProfile ?? "high_quality"}
          onChange={(event) => update({ newBookProfile: event.target.value })}
        >
          {(Object.keys(PROFILE_LABEL) as (keyof typeof PROFILE_LABEL)[]).map((value) => (
            <option key={value} value={value}>
              {PROFILE_LABEL[value]}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

// Mẫu thiết lập đã lưu từ trình tạo sách (studio/bookTemplates.ts): đổi tên, xoá (có "Hoàn tác"). Lưu mẫu mới làm ở trình tạo.
function BookTemplates() {
  const { data: preferences, update } = usePreferences();
  const templates = templatesOf(preferences?.bookTemplates);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [typed, setTyped] = useState("");
  const [problem, setProblem] = useState("");
  const save = (next: BookTemplate[], onSuccess?: () => void) =>
    update({ bookTemplates: next }, { onSuccess, onError: (error) => toast.error("Không lưu được mẫu", { description: error.message }) });
  const finishRename = (from: string) => {
    const wrong = nameProblem(templates, typed, from);
    if (wrong) {
      setProblem(wrong);
      return;
    }
    save(renameTemplate(templates, from, typed), () => setRenaming(null));
  };
  const remove = (template: BookTemplate) =>
    save(removeTemplate(templates, template.name), () =>
      toast(`Đã xoá mẫu “${template.name}”`, { duration: 10000, action: { label: "Hoàn tác", onClick: () => save(templates) } }),
    );
  return (
    <div className="mb-4 max-w-xl">
      <div className="text-sm font-medium">Mẫu thiết lập cho sách mới</div>
      <p className="mt-0.5 text-[13px] text-fg-2 text-pretty">
        Bộ lựa chọn đặt tên sẵn (giọng kể, chất lượng...) để chọn lại ở trình tạo sách; “Mặc định” ở đó là giọng kể và chất lượng đặt
        ngay phía trên. Muốn lưu mẫu mới: chọn xong ở trình tạo sách rồi bấm “Lưu thành mẫu…”.
      </p>
      {!templates.length ? (
        <p className="mt-2 text-[13px] text-fg-3">Chưa có mẫu nào.</p>
      ) : (
        <ul className="mt-2 divide-y divide-line rounded-lg border border-line">
          {templates.map((template) => (
            <li key={template.name} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 px-3 py-2">
              {renaming === template.name ? (
                <form
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
                    className="h-8 min-w-0 flex-1 rounded-lg border border-line bg-bg px-2.5 text-sm outline-none focus:border-accent"
                  />
                  <Button type="submit" size="sm" variant="primary" disabled={!typed.trim()}>
                    Lưu
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setRenaming(null)}>
                    Huỷ
                  </Button>
                  {problem && <p role="alert" className="basis-full text-[13px] text-danger">{problem}</p>}
                </form>
              ) : (
                <>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{template.name}</div>
                    <div className="truncate text-[13px] text-fg-2">
                      {[template.narrator || "Giọng máy đề xuất", PROFILE_LABEL[template.profile], template.startNow ? "bắt đầu ngay" : "chờ bấm bắt đầu"].join(" · ")}
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
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Giọng đọc của "Nghe ngay" trên máy tính: máy chủ cục bộ (abook/readaloud) đọc, khóa của người dùng gửi trong thân yêu cầu, chỉ nhận lại bản che. */
const desktopVoices: VoiceSettingsApi = {
  voices: () => httpSource.readAloudVoices!(),
  sample: (voice, text) => httpSource.readAloudSample!(voice, text),
  online: () => api<OnlineProviderInfo[]>("/api/readaloud/online"),
  saveKey: (provider, key, region) => api<OnlineProviderInfo>(`/api/readaloud/online/${provider}`, { method: "PUT", body: { key, region } }),
  removeKey: (provider) => api<OnlineProviderInfo>(`/api/readaloud/online/${provider}`, { method: "DELETE" }),
  checkKey: (provider) => api<KeyCheck>(`/api/readaloud/online/${provider}/check`, { method: "POST", body: {} }),
};

function Section({ id, title, description, children }: { id?: string; title: string; description?: string; children: ReactNode }) {
  return (
    <section id={id} className="grid scroll-mt-4 gap-4 border-b border-line py-7 last:border-b-0 lg:grid-cols-[260px_minmax(0,1fr)] lg:gap-8">
      <div>
        <h2 className="text-base font-semibold">{title}</h2>
        {description && <p className="mt-1 text-[13px] leading-relaxed text-fg-2 text-pretty">{description}</p>}
      </div>
      <div className="min-w-0">{children}</div>
    </section>
  );
}

/** Mục lục của trang: đọc thẳng các mục (`<section id>` + tiêu đề) đang có trên trang, nên mục nào ẩn theo máy / chế độ thì tự không có
 *  trong mục lục - không phải giữ một danh sách thứ hai khớp với các điều kiện bên dưới. */
function SectionIndex({ root }: { root: { current: HTMLElement | null } }) {
  const [items, setItems] = useState<{ id: string; title: string }[]>([]);
  useEffect(() => {
    // Chạy sau mỗi lần dựng: thông tin máy / tuỳ chọn tới muộn làm mục xuất hiện hay biến mất; chỉ đặt lại khi danh sách thật sự đổi.
    const found = [...(root.current?.querySelectorAll<HTMLElement>("section[id]") ?? [])].map((section) => ({
      id: section.id,
      title: section.querySelector("h2")?.textContent ?? "",
    }));
    setItems((now) => (now.length === found.length && now.every((item, index) => item.id === found[index].id && item.title === found[index].title) ? now : found));
  });
  if (items.length < 4) return null;
  const jump = (id: string) => {
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    document.getElementById(id)?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  };
  return (
    <nav aria-label="Các mục của Cài đặt" className="mt-4 flex flex-wrap gap-1.5">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => jump(item.id)}
          className="touch-row h-8 rounded-full border border-line bg-panel px-3 text-[13px] font-medium text-fg-2 transition-colors hover:border-line-strong hover:text-fg"
        >
          {item.title}
        </button>
      ))}
    </nav>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 py-2">
      <div className="min-w-0">
        <div className="text-sm font-medium">{label}</div>
        {hint && <div className="mt-0.5 text-[13px] text-fg-2">{hint}</div>}
      </div>
      {children}
    </div>
  );
}

const THEMES = [
  { value: "system", label: "Theo Windows", icon: Monitor },
  { value: "light", label: "Sáng", icon: Sun },
  { value: "dark", label: "Tối", icon: Moon },
] as const;
const THEME_VALUES = THEMES.map((theme) => theme.value);

/** App Windows đóng gói: vỏ đã tìm thấy bản mới (đã ký) - cài chỉ khi người dùng bấm, vì app phải đóng rồi mở lại. */
function UpdateSection({ update, current }: { update: { version: string; notes: string }; current: string }) {
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    // Vỏ tải hỏng (desktop/App.tsx báo lỗi): nút bấm lại được.
    const failed = () => setBusy(false);
    window.addEventListener("abook-update-failed", failed);
    return () => window.removeEventListener("abook-update-failed", failed);
  }, []);
  const install = async () => {
    setBusy(true);
    try {
      await api("/api/app/update", { method: "POST", body: {} });
      toast.success(`Đang tải ABook ${update.version}`, {
        description: "App tự đóng, cài bản mới rồi mở lại. Chỗ đang nghe, dấu trang và sách giữ nguyên.",
        duration: 60_000,
      });
    } catch (error) {
      setBusy(false);
      toast.error("Chưa cập nhật được", { description: (error as Error).message });
    }
  };
  return (
    <Section id="update" title="Cập nhật" description="Bản mới tải từ trang phát hành của ABook, có chữ ký kiểm được.">
      <div className="max-w-xl">
        <p className="text-sm">
          <span className="font-semibold">ABook {update.version}</span> đã có{current ? ` - máy này đang dùng ${current}` : ""}.
        </p>
        {update.notes && <p className="mt-2 whitespace-pre-line text-[13px] leading-relaxed text-fg-2 text-pretty">{update.notes}</p>}
        <Button className="mt-3" icon={Download} disabled={busy} onClick={() => void install()}>
          {busy ? "Đang tải bản mới…" : "Cập nhật và mở lại"}
        </Button>
      </div>
    </Section>
  );
}

/** Danh sách thành phần bên thứ ba (docs/THIRD_PARTY.md, gói lúc build) trong một hộp - trang Cài đặt không dài thêm. */
function ThirdPartyButton() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button className="mt-3" size="sm" variant="secondary" onClick={() => setOpen(true)}>
        Thành phần bên thứ ba
      </Button>
      <Dialog open={open} onOpenChange={setOpen} title="Thành phần bên thứ ba" width="max-w-2xl">
        <div className="mt-3 max-h-[65vh] select-text overflow-y-auto pr-1">{open && <ThirdPartyList />}</div>
      </Dialog>
    </>
  );
}

export function SettingsScreen() {
  const { data: info } = useAppInfo();
  const { data: preferences, update } = usePreferences();
  const client = useQueryClient();
  const changeLibrary = async () => {
    try {
      const path = await pickFolder("Chọn thư mục thư viện", preferences?.libraryRoot ?? "");
      if (path) {
        update({ libraryRoot: path });
        toast.success("Đã đổi thư mục thư viện");
      }
    } catch (error) {
      toast.error((error as Error).message);
    }
  };
  const remote = Boolean(info?.remote);
  const page = useRef<HTMLDivElement | null>(null);
  // Phím tắt vô nghĩa trên màn chỉ có cảm ứng (điện thoại, máy tính bảng không bàn phím): ẩn cả mục.
  const touchOnly = useMediaQuery("(hover: none) and (pointer: coarse)");
  const fade = String(preferences?.sleepFadeSeconds ?? 30) as "10" | "30" | "60";
  const extend = String(preferences?.sleepExtendMinutes ?? 10) as "5" | "10" | "15";
  return (
    <div ref={page} className="mx-auto max-w-[1180px] px-4 pb-16 pt-6 sm:px-10 sm:pt-9">
      <h1 className="text-2xl font-bold tracking-tight sm:text-[28px]">Cài đặt</h1>
      <div className="max-w-[980px]">
        <SectionIndex root={page} />
        {!remote && info?.update && <UpdateSection update={info.update} current={info.version} />}
        {remote && (
          <Section id="remote" title="Điều khiển từ xa" description="Đang dùng ABook của máy tính qua mạng.">
            <p className="max-w-xl text-sm text-fg-2 text-pretty">
              {info?.listenOnly
                ? "Thiết bị này nghe được mọi sách của máy tính. Muốn làm sách từ đây: trên máy tính, Cài đặt → Điện thoại và thiết bị → bật “Cho phép điều khiển sản xuất từ thiết bị đã ghép” và “Điều khiển sản xuất” ở dòng của thiết bị này."
                : "Sách, dự án và việc sản xuất ở đây là của máy tính."}{" "}
              Cài đặt của máy tính - thư mục thư viện, giao diện, hẹn giờ ngủ, thiết bị đã ghép - chỉ đổi được trên chính máy tính.
            </p>
          </Section>
        )}
        {!info?.listenOnly && (
        <Section id="library" title="Thư viện" description="Thư mục chứa sách của bạn. Sách thêm vào hay mới làm đều nằm ở đây.">
          <div className="flex items-center gap-2">
            <div className="flex h-10 min-w-0 flex-1 items-center gap-2 rounded-lg bg-sunken px-3 text-sm text-fg-2">
              <FolderOpen className="size-4 shrink-0" />
              <span className="truncate" title={preferences?.libraryRoot}>{preferences?.libraryRoot}</span>
            </div>
            {info?.dialogs && (
              <Button icon={FolderOpen} className="touch-row" onClick={() => void changeLibrary()}>
                Đổi thư mục
              </Button>
            )}
          </div>
        </Section>
        )}
        {!remote && (
        <>
        <Section id="theme" title="Giao diện" description="Màu sáng hay tối. Theo Windows sẽ tự đổi cùng hệ thống.">
          <div
            role="radiogroup"
            aria-label="Giao diện"
            onKeyDown={radioGroupKeys(THEME_VALUES, preferences?.theme ?? "system", (theme) => update({ theme }))}
            className="grid max-w-md grid-cols-3 gap-2"
          >
            {THEMES.map((theme, index) => {
              const selected = (preferences?.theme ?? "system") === theme.value;
              const Icon = theme.icon;
              return (
                <button
                  key={theme.value}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  tabIndex={radioTabIndex(THEME_VALUES, preferences?.theme ?? "system", index)}
                  onClick={() => update({ theme: theme.value })}
                  className={cn(
                    "flex flex-col items-center gap-2 rounded-xl border bg-panel py-4 text-sm font-medium transition-colors",
                    selected ? "border-accent ring-1 ring-accent" : "border-line hover:border-line-strong",
                  )}
                >
                  <Icon className="size-5" />
                  {theme.label}
                </button>
              );
            })}
          </div>
        </Section>
        <Section
          id="listen"
          title="Nghe"
          description="Trình phát nhớ vị trí và tốc độ của từng cuốn. Hết một chương tự sang chương kế tiếp (nếu đã có audio)."
        >
          <div className="divide-y divide-line">
            <Field label="Nhỏ dần trước khi hẹn giờ tắt" hint="Tiếng giảm êm để không giật mình tỉnh giấc.">
              <Segmented<"10" | "30" | "60">
                label="Độ dài nhỏ dần"
                value={fade}
                onChange={(value) => update({ sleepFadeSeconds: Number(value) })}
                options={[
                  { value: "10", label: "10 giây" },
                  { value: "30", label: "30 giây" },
                  { value: "60", label: "1 phút" },
                ]}
              />
            </Field>
            <Field label="Mỗi lần nghe thêm" hint={`Lúc đang nhỏ dần, ${EXTEND_GESTURE} là được nghe thêm chừng này.`}>
              <Segmented<"5" | "10" | "15">
                label="Số phút nghe thêm"
                value={extend}
                onChange={(value) => update({ sleepExtendMinutes: Number(value) })}
                options={[
                  { value: "5", label: "5 phút" },
                  { value: "10", label: "10 phút" },
                  { value: "15", label: "15 phút" },
                ]}
              />
            </Field>
            <Field
              label="Tự tắt khi ngủ quên"
              hint="Phát liên tục mà không ai chạm máy chừng này thì nhỏ dần rồi dừng, và ghi lại chỗ đang nghe cho thẻ “Tối qua”."
            >
              <Segmented<"0" | "1" | "2" | "3">
                label="Tự tắt khi ngủ quên"
                value={String(preferences?.safetyStopHours ?? 2) as "0" | "1" | "2" | "3"}
                onChange={(value) => update({ safetyStopHours: Number(value) })}
                options={[
                  { value: "0", label: "Không" },
                  { value: "1", label: "1 giờ" },
                  { value: "2", label: "2 giờ" },
                  { value: "3", label: "3 giờ" },
                ]}
              />
            </Field>
            <Field
              label="Lịch đêm"
              hint="Bấm nghe trong khung giờ này thì tự hẹn giờ ngủ - khỏi phải nhớ bấm lúc buồn ngủ."
            >
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <Switch
                  id="sleep-schedule"
                  label="Lịch đêm"
                  checked={Boolean(preferences?.sleepSchedule)}
                  onCheckedChange={(on) => update({ sleepSchedule: on ? { from: "22:00", to: "06:00", minutes: 30 } : null })}
                />
                {preferences?.sleepSchedule && (
                  <>
                    <TimeSelect
                      label="Từ"
                      value={preferences.sleepSchedule.from}
                      onChange={(value) => update({ sleepSchedule: { ...preferences.sleepSchedule!, from: value } })}
                      className="h-9 rounded-lg border border-line bg-panel px-2"
                    />
                    <span className="text-fg-2">đến</span>
                    <TimeSelect
                      label="Đến"
                      value={preferences.sleepSchedule.to}
                      onChange={(value) => update({ sleepSchedule: { ...preferences.sleepSchedule!, to: value } })}
                      className="h-9 rounded-lg border border-line bg-panel px-2"
                    />
                    <span className="text-fg-2">hẹn</span>
                    <select
                      aria-label="Số phút hẹn"
                      value={preferences.sleepSchedule.minutes}
                      onChange={(event) => update({ sleepSchedule: { ...preferences.sleepSchedule!, minutes: Number(event.target.value) } })}
                      className="h-9 rounded-lg border border-line bg-panel px-2"
                    >
                      {[15, 30, 45, 60].map((minutes) => (
                        <option key={minutes} value={minutes}>
                          {minutes} phút
                        </option>
                      ))}
                    </select>
                  </>
                )}
              </div>
            </Field>
            <Field
              label="Tự lùi khi nghe lại"
              hint="Dừng dưới 5 phút: không lùi. Từ 5 phút tới 1 giờ: lùi 10 giây. Lâu hơn (ngủ dậy): lùi 30 giây."
            >
              {/* Thông tin, không phải lựa chọn (soát UX 29-09: chữ "Tự động" trông như một nút mà không bấm được). */}
              <span className="inline-flex items-center gap-1 text-[13px] text-fg-2">
                <Check className="size-3.5 text-success" /> Luôn bật
              </span>
            </Field>
          </div>
        </Section>
        {!remote && (
          <Section
            id="voices"
            title="Giọng đọc"
            description="Giọng mặc định khi nghe sách chưa có audio (“Nghe ngay”). Mỗi cuốn vẫn đổi được giọng riêng ở nút “Giọng đọc” trong trình phát."
          >
            <VoiceSettings
              api={desktopVoices}
              deviceHint="Máy này chưa có giọng tiếng Việt. Cài trong Windows: Cài đặt → Thời gian và ngôn ngữ → Giọng nói → Thêm giọng nói → Tiếng Việt."
              modules={(reload) => (
                <>
                  {/* Mã để nút "Tải giọng VieNeu" ở khối báo mất mạng của trình phát cuộn tới đúng thẻ này (PlayerViews.PlayerAlert). */}
                  <div id="vieneu-module" className="scroll-mt-4">
                    <VieneuModuleCard onChanged={reload} />
                  </div>
                  <SupertonicModuleCard onChanged={reload} />
                </>
              )}
            />
          </Section>
        )}
        {/* "Nhạc của tôi" trước chỉ mở được từ hộp "Sửa sách" của từng cuốn, dù kho nhạc là chung cho mọi cuốn. */}
        <Section
          id="music"
          title="Nhạc nền"
          description="Máy tự chọn nhạc nền cho sách chỉ có chữ (công tắc ngay dưới), và bạn có thể thêm nhạc của riêng mình, dùng chung cho mọi cuốn. Chọn bài cho từng đoạn ở tab “Nhạc nền” của từng dự án trong Studio."
        >
          <div className="mb-5 flex max-w-2xl items-start justify-between gap-6">
            <label htmlFor="auto-music" className="min-w-0 cursor-pointer">
              <span className="block text-sm font-medium">{AUTO_MUSIC_LABEL}</span>
              <span className="mt-0.5 block text-[13px] text-fg-2 text-pretty">{AUTO_MUSIC_HINT}</span>
            </label>
            <Switch
              id="auto-music"
              checked={preferences?.autoMusic !== false}
              onCheckedChange={(value) =>
                update(
                  { autoMusic: value },
                  {
                    onSuccess: () => {
                      void client.invalidateQueries({ queryKey: ["listen"] });
                      toast.success(value ? "Đã bật tự chọn nhạc nền" : "Đã tắt tự chọn nhạc nền", {
                        description: value ? "Sách chỉ có chữ chưa chọn nhạc sẽ có nhạc nhè nhẹ." : "Sách chưa chọn nhạc sẽ im lặng; cuốn đã chọn nhạc vẫn giữ.",
                      });
                    },
                  },
                )
              }
            />
          </div>
          <div className="max-w-2xl">
            <MyMusicSection />
          </div>
        </Section>
        <Section
          id="phone"
          title="Điện thoại và thiết bị"
          description="Nghe tiếp trên điện thoại Android: tải sách về để nghe không cần mạng, chỗ đang nghe và dấu trang tự đồng bộ hai chiều. Nếu cho phép, thiết bị đã ghép còn điều khiển được việc sản xuất của máy này qua trình duyệt."
        >
          <PhoneSync />
        </Section>
        {info?.studio && (
          <Section
            id="studio"
            title="Studio"
            description="Phần làm sách nói (thư viện, model đọc hiểu truyện, giọng đọc) - tải thêm khi cần, nằm riêng một thư mục."
          >
            {/* Trạng thái Studio (đã cài / chưa cài + Gỡ hay Cài) ở đầu mục; chưa cài thì các tuỳ chọn bên dưới chỉ có tác dụng khi đã có Studio: mờ đi nhưng vẫn xem và chỉnh được. */}
            <StudioSettings />
            {!info.studio.installed && <p className="mb-3 text-[13px] text-fg-2">Các tuỳ chọn dưới đây dùng khi đã cài Studio.</p>}
            <div className={cn(!info.studio.installed && "opacity-60")}>
              <div className="mb-4 flex max-w-xl items-start justify-between gap-6">
                <label htmlFor="pause-on-battery" className="min-w-0 cursor-pointer">
                  <span className="block text-sm font-medium">Tạm dừng khi rút sạc</span>
                  <span className="mt-0.5 block text-[13px] text-fg-2 text-pretty">
                    Máy tính xách tay chạy pin thì làm sách rất chậm mà hao pin. Sách đứng yên và tự làm tiếp đúng chỗ khi cắm sạc
                    lại - kể cả giữa lúc phân tích truyện.
                  </span>
                </label>
                <Switch
                  id="pause-on-battery"
                  checked={preferences?.pauseOnBattery !== false}
                  onCheckedChange={(value) => update({ pauseOnBattery: value })}
                />
              </div>
              <NewBookDefaults />
              <BookTemplates />
              <SharedReadingsSettings />
            </div>
          </Section>
        )}
        <Section
          id="computers"
          title="Máy tính khác"
          description="Nghe sách trên máy tính khác cùng mạng (hay cùng mạng riêng ảo) mà không phải chép sang: sách của máy ấy hiện trong Thư viện, chương tải về lần đầu nghe tới."
        >
          <OtherComputers />
        </Section>
        </>
        )}
        {!touchOnly && (
        <Section id="shortcuts" title="Phím tắt" description="Dùng được ở mọi màn hình, trừ khi đang gõ chữ.">
          <ShortcutList />
        </Section>
        )}
        <Section id="about" title="Giới thiệu">
          <p className="text-sm text-fg-2 text-pretty">
            ABook {info?.version} - studio sách nói tiếng Việt chạy hoàn toàn trên máy này: phân tích truyện, phân vai, thu âm và
            kiểm tra từng câu.
          </p>
          {/* Liên kết mở ở cửa sổ mới (target="_blank", như ghi công nhạc ở trình phát), không điều hướng chính cửa sổ app; Android: SOURCE_URL. */}
          <p className="mt-2 select-text text-sm text-fg-2">
            Mã nguồn mở, giấy phép MIT:{" "}
            <a href="https://github.com/ntanhpro1221/ABook/" target="_blank" rel="noopener noreferrer" className="font-medium text-accent-text underline underline-offset-2">
              github.com/ntanhpro1221/ABook
            </a>{" "}
            - bản mới,
            ứng dụng Android và ghi chú từng bản ở mục Releases.
          </p>
          <ThirdPartyButton />
        </Section>
      </div>
    </div>
  );
}

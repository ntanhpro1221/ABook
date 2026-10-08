import * as Switch from "@radix-ui/react-switch";
import { ChevronDown, ChevronRight, Download } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { cn } from "@/shared/cn";
import { Button, Segmented, Sheet, TimeSelect } from "@/shared/ui";
import { ThirdPartyList } from "@/shared/ThirdPartyList";
import { MyMusicSection } from "@/listen/MyMusic";
import { VieneuModuleCard, type VieneuBackend } from "@/listen/VieneuModuleCard";
import { SUPERTONIC_COPY } from "@/listen/vieneuModule";
import { VoiceSettings, type VoiceSettingsApi } from "@/listen/VoiceSettings";
import { androidSource } from "./androidSource";
import { notificationState, openNotificationSettings, type NotificationState } from "./notifications";
import { ReadAloud } from "./plugins";
import { applyTheme, loadSettings, saveSettings, type PlayerSettings } from "./settings";
import { openRelease } from "./UpdateNotice";
import { useAppUpdate } from "./updates";

function Group({ title, id, children }: { title: string; id?: string; children: ReactNode }) {
  return (
    <section id={id} className="mt-7">
      <h2 className="mb-2 px-1 text-xs font-semibold uppercase tracking-wider text-fg-3">{title}</h2>
      <div className="divide-y divide-line rounded-2xl border border-line bg-panel">{children}</div>
    </section>
  );
}

/** Giọng đọc của "Nghe ngay" trên điện thoại: lõi native đọc (plugin ReadAloud); khóa lưu mã hoá bằng Android Keystore (OnlineKeys.kt). */
const phoneVoices: VoiceSettingsApi = {
  voices: async () => (await ReadAloud.voices()).voices,
  sample: (voice, text) => androidSource.readAloudSample!(voice, text),
  online: async () => (await ReadAloud.onlineProviders()).providers,
  saveKey: (provider, key, region) => ReadAloud.setOnlineKey({ provider, key, region }),
  removeKey: (provider) => ReadAloud.removeOnlineKey({ provider }),
  checkKey: (provider) => ReadAloud.checkOnlineKey({ provider }),
};

/** "Giọng VieNeu" trên điện thoại: lõi native tải, đo, gỡ (VieneuModule.kt) - cùng thẻ với máy tính. */
const phoneVieneu: VieneuBackend = {
  status: () => ReadAloud.vieneuStatus(),
  start: (choices) => ReadAloud.vieneuStart(choices ? { choices } : {}),
  measure: () => ReadAloud.vieneuMeasure(),
  remove: (choice) => ReadAloud.vieneuRemove({ choice }),
  voices: async () => (await ReadAloud.voices()).voices,
};

/** "Giọng Supertonic" trên điện thoại (SupertonicModule.kt): cùng thẻ, lời riêng. */
const phoneSupertonic: VieneuBackend = {
  status: () => ReadAloud.supertonicStatus(),
  start: (choices) => ReadAloud.supertonicStart(choices ? { choices } : {}),
  measure: () => ReadAloud.supertonicMeasure(),
  remove: (choice) => ReadAloud.supertonicRemove({ choice }),
  voices: phoneVieneu.voices,
};

function Row({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    // Chữ giữ tối thiểu ~12rem; nút chọn rộng (Không / 1 giờ / 2 giờ / 3 giờ) không đủ chỗ thì xuống hàng dưới, sát phải - chữ hệ thống to
    // từng bóp lời giải thích còn một chữ mỗi dòng (soát UX a9).
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3.5">
      <div className="min-w-0 flex-[1_1_12rem]">
        <div className="text-[15px] font-medium">{label}</div>
        {hint && <div className="mt-0.5 text-xs leading-snug text-fg-2">{hint}</div>}
      </div>
      <div className="ml-auto shrink-0">{children}</div>
    </div>
  );
}

/** Chỉ hiện khi ABook chưa được phép hiện thông báo (người nghe từ chối hay bỏ qua lời mời lúc nghe lần đầu): nói thẳng hậu quả và mở đúng trang cài đặt.
 *  Quay lại từ Cài đặt Android thì hỏi lại - cho phép xong là dòng này biến mất. */
function NotificationRow() {
  const [state, setState] = useState<NotificationState>("granted");
  useEffect(() => {
    const check = () => void notificationState().then(setState);
    check();
    document.addEventListener("visibilitychange", check);
    return () => document.removeEventListener("visibilitychange", check);
  }, []);
  if (state === "granted") return null;
  return (
    <Row label="Thông báo" hint="Khay thông báo và màn khoá chưa có nút tạm dừng, tua vì ABook chưa được phép hiện thông báo.">
      <Button size="sm" onClick={() => void openNotificationSettings().catch(() => undefined)}>
        Mở cài đặt
      </Button>
    </Row>
  );
}

// Dấu "/" cuối: lõi native chỉ mở địa chỉ bắt đầu bằng "https://github.com/ntanhpro1221/ABook/" (LibraryPlugin.openRelease).
const SOURCE_URL = "https://github.com/ntanhpro1221/ABook/";

/** "Giới thiệu": bản đang cài, mã nguồn (MIT), thành phần bên thứ ba (docs/THIRD_PARTY.md gói lúc build) trong tấm trượt. */
export function AboutGroup({ version }: { version: string | null }) {
  const [open, setOpen] = useState(false);
  return (
    <Group title="Giới thiệu" id="about">
      <Row label="Phiên bản">
        <span className="tabular text-sm text-fg-2">{version ?? "…"}</span>
      </Row>
      <Row label="Mã nguồn mở" hint="Giấy phép MIT - github.com/ntanhpro1221/ABook">
        <Button size="sm" onClick={() => void openRelease(SOURCE_URL)}>
          Mở
        </Button>
      </Row>
      <Sheet
        open={open}
        onOpenChange={setOpen}
        title="Thành phần bên thứ ba"
        trigger={
          <button type="button" className="flex w-full items-center justify-between gap-4 px-4 py-3.5 text-left">
            <span className="min-w-0">
              <span className="block text-[15px] font-medium">Thành phần bên thứ ba</span>
              <span className="mt-0.5 block text-xs leading-snug text-fg-2">Thư viện, giọng đọc và nhạc ABook dùng, cùng giấy phép của từng thứ.</span>
            </span>
            <ChevronRight className="size-5 shrink-0 text-fg-3" />
          </button>
        }
      >
        <div className="px-1.5 pt-3">{open && <ThirdPartyList />}</div>
      </Sheet>
    </Group>
  );
}

export function SettingsScreen() {
  const [settings, setSettings] = useState<PlayerSettings>(loadSettings);
  const { current, update } = useAppUpdate();
  const [sleepMore, setSleepMore] = useState(false);
  const change = (patch: Partial<PlayerSettings>) => {
    const next = { ...settings, ...patch };
    setSettings(next);
    saveSettings(next);
    if (patch.theme) applyTheme(patch.theme);
  };
  return (
    <div className="px-4 pb-10 pt-4">
      <h1 className="text-2xl font-bold tracking-tight">Cài đặt</h1>

      {/* Giọng đọc là việc người mới cần trước hết; hẹn giờ ngủ là tuỳ chọn nên xuống sau (soát UX a9). */}
      <Group title="Giọng đọc" id="voices">
        <div className="px-4 py-3.5">
          <p className="mb-3 text-xs leading-snug text-fg-2">
            Giọng mặc định khi nghe sách chưa có audio (“Nghe ngay”). Mỗi cuốn vẫn đổi được giọng riêng ở nút “Giọng đọc” trong trình phát.
          </p>
          <VoiceSettings
            api={phoneVoices}
            deviceHint="Máy chưa có giọng tiếng Việt. Cài trong Cài đặt của điện thoại → Chuyển văn bản thành giọng nói → tải dữ liệu giọng Tiếng Việt."
            modules={(reload) => (
              <>
                {/* Mã để nút "Tải giọng VieNeu" ở khối báo mất mạng của trình phát cuộn tới đúng thẻ này (PlayerViews.PlayerAlert). */}
                <div id="vieneu-module" className="scroll-mt-4">
                  <VieneuModuleCard backend={phoneVieneu} onChanged={reload} />
                </div>
                <VieneuModuleCard backend={phoneSupertonic} copy={SUPERTONIC_COPY} onChanged={reload} />
              </>
            )}
          />
        </div>
      </Group>

      <Group title="Hẹn giờ ngủ">
        <Row label="Lắc máy để nghe thêm" hint="Khi đang hẹn giờ, lắc nhẹ điện thoại hai lần - máy rung báo đã thêm giờ.">
          <Switch.Root
            checked={settings.shakeToExtend}
            onCheckedChange={(value) => change({ shakeToExtend: value })}
            aria-label="Lắc máy để nghe thêm"
            className="relative h-7 w-12 rounded-full bg-switch-off transition-colors data-[state=checked]:bg-accent"
          >
            <Switch.Thumb className="block size-6 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-[22px]" />
          </Switch.Root>
        </Row>
        <Row label="Úp máy để tạm dừng" hint="Úp màn hình xuống (lên bàn, lên nệm) là dừng; lật lên trong 10 phút là nghe tiếp. Cầm máy trên tay thì không tính.">
          <Switch.Root
            checked={settings.flipToPause ?? false}
            onCheckedChange={(value) => change({ flipToPause: value })}
            aria-label="Úp máy để tạm dừng"
            className="relative h-7 w-12 rounded-full bg-switch-off transition-colors data-[state=checked]:bg-accent"
          >
            <Switch.Thumb className="block size-6 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-[22px]" />
          </Switch.Root>
        </Row>
        <Row label="Lịch đêm" hint="Bấm nghe trong khung giờ này thì tự hẹn giờ ngủ - khỏi nhớ bấm lúc buồn ngủ.">
          <Switch.Root
            checked={Boolean(settings.sleepSchedule)}
            onCheckedChange={(value) => change({ sleepSchedule: value ? { from: "22:00", to: "06:00", minutes: 30 } : null })}
            aria-label="Lịch đêm"
            className="relative h-7 w-12 rounded-full bg-switch-off transition-colors data-[state=checked]:bg-accent"
          >
            <Switch.Thumb className="block size-6 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-[22px]" />
          </Switch.Root>
        </Row>
        {settings.sleepSchedule && (
          <div className="flex flex-wrap items-center gap-2 px-4 py-3 text-sm">
            <TimeSelect
              label="Từ"
              value={settings.sleepSchedule.from}
              onChange={(value) => change({ sleepSchedule: { ...settings.sleepSchedule!, from: value } })}
              className="h-10 rounded-lg border border-line bg-bg px-2"
            />
            <span className="text-fg-2">đến</span>
            <TimeSelect
              label="Đến"
              value={settings.sleepSchedule.to}
              onChange={(value) => change({ sleepSchedule: { ...settings.sleepSchedule!, to: value } })}
              className="h-10 rounded-lg border border-line bg-bg px-2"
            />
            <span className="text-fg-2">hẹn</span>
            <select
              aria-label="Số phút hẹn"
              value={settings.sleepSchedule.minutes}
              onChange={(event) => change({ sleepSchedule: { ...settings.sleepSchedule!, minutes: Number(event.target.value) } })}
              className="h-10 rounded-lg border border-line bg-bg px-2"
            >
              {[15, 30, 45, 60].map((minutes) => (
                <option key={minutes} value={minutes}>
                  {minutes} phút
                </option>
              ))}
            </select>
          </div>
        )}
        <Row label="Tự tắt khi ngủ quên" hint="Phát liên tục mà không chạm máy chừng này thì nhỏ dần rồi dừng, và ghi lại chỗ đang nghe cho thẻ “Tối qua”.">
          <Segmented
            label="Tự tắt khi ngủ quên"
            value={String(settings.safetyStopHours)}
            onChange={(value) => change({ safetyStopHours: Number(value) })}
            options={[
              { value: "0", label: "Không" },
              { value: "1", label: "1 giờ" },
              { value: "2", label: "2 giờ" },
              { value: "3", label: "3 giờ" },
            ]}
          />
        </Row>
        {/* Bảy dòng liền một khối khiến nhóm này dài hơn cả phần còn lại của Cài đặt: phần chỉnh tinh (cách lắc, mỗi lần thêm, nhỏ dần) gập lại (soát UX a9). */}
        <button
          type="button"
          aria-expanded={sleepMore}
          onClick={() => setSleepMore((value) => !value)}
          className="flex w-full items-center justify-between gap-4 px-4 py-3.5 text-left"
        >
          <span className="text-[15px] font-medium">Tuỳ chỉnh thêm</span>
          <ChevronDown className={cn("size-5 shrink-0 text-fg-3 transition-transform", sleepMore && "rotate-180")} />
        </button>
        {sleepMore && (
          <>
            {settings.shakeToExtend && (
              <>
                <Row label="Khi lắc" hint="Cộng thêm: mỗi cú lắc thêm vài phút. Đặt lại: hẹn giờ quay về từ đầu (vd lại đủ 30 phút).">
                  <Segmented
                    label="Khi lắc"
                    value={settings.shakeAction ?? "extend"}
                    onChange={(value) => change({ shakeAction: value })}
                    options={[
                      { value: "extend", label: "Cộng thêm" },
                      { value: "reset", label: "Đặt lại" },
                    ]}
                  />
                </Row>
                <Row label="Độ nhạy" hint="Hay bị tính nhầm khi trở mình thì chọn Mạnh tay; lắc mãi không ăn thì chọn Nhẹ tay.">
                  <Segmented
                    label="Độ nhạy lắc"
                    value={settings.shakeSensitivity ?? "normal"}
                    onChange={(value) => change({ shakeSensitivity: value })}
                    options={[
                      { value: "gentle", label: "Nhẹ tay" },
                      { value: "normal", label: "Vừa" },
                      { value: "firm", label: "Mạnh tay" },
                    ]}
                  />
                </Row>
              </>
            )}
            <Row label="Mỗi lần thêm">
              <Segmented
                label="Mỗi lần thêm"
                value={String(settings.sleepExtendMinutes)}
                onChange={(value) => change({ sleepExtendMinutes: Number(value) })}
                options={[5, 10, 15].map((value) => ({ value: String(value), label: `${value}′` }))}
              />
            </Row>
            <Row label="Nhỏ dần trước khi tắt">
              <Segmented
                label="Nhỏ dần trước khi tắt"
                value={String(settings.sleepFadeSeconds)}
                onChange={(value) => change({ sleepFadeSeconds: Number(value) })}
                options={[10, 30, 60].map((value) => ({ value: String(value), label: `${value}s` }))}
              />
            </Row>
          </>
        )}
      </Group>

      <Group title="Nghe">
        <NotificationRow />
        <Row label="Nút tai nghe lùi/tới" hint="Nút Trước/Sau trên tai nghe Bluetooth, đồng hồ, xe hơi: lùi/tới 15 giây thay vì nhảy cả chương.">
          <Switch.Root
            checked={settings.headsetSkips ?? false}
            onCheckedChange={(value) => change({ headsetSkips: value })}
            aria-label="Nút tai nghe lùi/tới"
            className="relative h-7 w-12 rounded-full bg-switch-off transition-colors data-[state=checked]:bg-accent"
          >
            <Switch.Thumb className="block size-6 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-[22px]" />
          </Switch.Root>
        </Row>
        <Row label="Tự lùi khi nghe lại" hint={`Tạm dừng quá ${settings.rewindAfterMinutes} phút rồi nghe tiếp thì lùi lại một chút để bắt mạch truyện.`}>
          <Segmented
            label="Tự lùi"
            value={String(settings.rewindSeconds)}
            onChange={(value) => change({ rewindSeconds: Number(value) })}
            options={[
              { value: "0", label: "Tắt" },
              { value: "5", label: "5s" },
              { value: "15", label: "15s" },
            ]}
          />
        </Row>
      </Group>

      {/* "Nhạc của tôi" trước chỉ mở được từ hộp "Sửa sách" của từng cuốn, dù kho nhạc là chung cho mọi cuốn. */}
      <Group title="Nhạc nền" id="music">
        <div className="px-4 py-3.5">
          <MyMusicSection />
        </div>
      </Group>

      <Group title="Giao diện">
        <Row label="Màu">
          <Segmented
            label="Màu"
            value={settings.theme}
            onChange={(value) => change({ theme: value })}
            options={[
              { value: "system", label: "Tự động" },
              { value: "light", label: "Sáng" },
              { value: "dark", label: "Tối" },
            ]}
          />
        </Row>
      </Group>

      {/* Điện thoại không tự cập nhật như app Windows: báo bản mới trên GitHub, mời tải APK (updates.ts). */}
      {update && (
        <Group title="Cập nhật">
          <Row label={`Có bản mới ${update.version}`} hint="Tải file APK rồi mở để cài đè - sách và chỗ đang nghe giữ nguyên.">
            <Button size="sm" variant="primary" icon={Download} onClick={() => void openRelease(update.apk ?? update.page)}>
              Tải
            </Button>
          </Row>
        </Group>
      )}

      <AboutGroup version={current} />
    </div>
  );
}

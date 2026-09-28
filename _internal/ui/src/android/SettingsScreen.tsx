import * as Switch from "@radix-ui/react-switch";
import { useState, type ReactNode } from "react";
import { Segmented, TimeSelect } from "@/shared/ui";
import { applyTheme, loadSettings, saveSettings, type PlayerSettings } from "./settings";

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-7">
      <h2 className="mb-2 px-1 text-xs font-semibold uppercase tracking-wider text-fg-3">{title}</h2>
      <div className="divide-y divide-line rounded-2xl border border-line bg-panel">{children}</div>
    </section>
  );
}

function Row({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 px-4 py-3.5">
      <div className="min-w-0">
        <div className="text-[15px] font-medium">{label}</div>
        {hint && <div className="mt-0.5 text-xs leading-snug text-fg-2">{hint}</div>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

export function SettingsScreen() {
  const [settings, setSettings] = useState<PlayerSettings>(loadSettings);
  const change = (patch: Partial<PlayerSettings>) => {
    const next = { ...settings, ...patch };
    setSettings(next);
    saveSettings(next);
    if (patch.theme) applyTheme(patch.theme);
  };
  return (
    <div className="px-4 pb-10 pt-4">
      <h1 className="text-2xl font-bold tracking-tight">Cài đặt</h1>

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
        <Row label="Mỗi lần thêm">
          <Segmented
            label="Mỗi lần thêm"
            value={String(settings.sleepExtendMinutes)}
            onChange={(value) => change({ sleepExtendMinutes: Number(value) })}
            options={[5, 10, 15].map((value) => ({ value: String(value), label: `${value}′` }))}
          />
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
        <Row label="Nhỏ dần trước khi tắt">
          <Segmented
            label="Nhỏ dần trước khi tắt"
            value={String(settings.sleepFadeSeconds)}
            onChange={(value) => change({ sleepFadeSeconds: Number(value) })}
            options={[10, 30, 60].map((value) => ({ value: String(value), label: `${value}s` }))}
          />
        </Row>
      </Group>

      <Group title="Nghe">
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

      <p className="mt-10 text-center text-xs text-fg-3">ABook · trình nghe sách nói</p>
    </div>
  );
}

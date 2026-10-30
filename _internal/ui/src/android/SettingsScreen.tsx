import { DisclosureRow } from "@/shared/DisclosureRow";
import { MotionPresence } from "@/shared/MotionPresence";
import * as Switch from "@radix-ui/react-switch";
import { Download, TriangleAlert } from "lucide-react";
import { toast } from "@/shared/toast";
import { useEffect, useState } from "react";
import { useParams } from "react-router";
import { Select, Button, ChoiceRow, Dialog, DialogActions, Sheet, TimeSelect } from "@/shared/ui";
import { GroupHeader, isSettingsGroup, MoreInfo, SettingsBlock, SettingsList, SettingsRow, settingsPath, type GroupRow, type SettingsGroupId } from "@/shared/SettingsNav";
import { ScreenHeader } from "@/shared/ScreenHeader";
import { listenSummary, sleepSummary, themeSummary } from "@/shared/settingsSummary";
import { ThirdPartyList } from "@/shared/ThirdPartyList";
import { MyMusicSection } from "@/listen/MyMusic";
import { AUTO_MUSIC_HINT, AUTO_MUSIC_LABEL } from "@/listen/playlistBed";
import { ReadAloudStorage } from "@/listen/ReadAloudStorage";
import { LocalVoiceModules, type VieneuBackend } from "@/listen/VieneuModuleCard";
import { VoiceSpeedSetting, type VoiceSpeedBackend } from "@/listen/VoiceSpeedSetting";
import { useDefaultVoiceName, VoiceSettings, type VoiceSettingsApi } from "@/listen/VoiceSettings";
import { androidSource, phoneVieneu } from "./androidSource";
import { CLEAR_HINT, CLEAR_QUESTION, DIAGNOSTICS_HINT, DIAGNOSTICS_MORE, DiagnosticsPanel, SEND_HINT, useDiagnostics } from "./Diagnostics";
import { NOTIFICATION_ROW_HINT, notificationState, openNotificationSettings, type NotificationState } from "./notifications";
import { ReadAloud } from "./plugins";
import { applySenses, applyTheme, loadSettings, saveSettings, type PlayerSettings } from "./settings";
import { feedback, TOUCH_SOUNDS_HINT } from "@/shared/feedback";
import { READING_SURFACES } from "@/shared/readingSurface";
import { OldSavesList } from "./OldSaves";
import { useOldSaves } from "./oldSaveList";
import { openRelease } from "./UpdateNotice";
import { useAppUpdate } from "./updates";
import { DevicesScreen } from "./DevicesScreen";

// Cài đặt của điện thoại (chủ app 23-10: "như lạc vào ma trận"): trang gốc là danh sách 6 nhóm, mỗi nhóm một màn con /settings/<nhóm>
// (shared/SettingsNav.tsx). Cùng cây nhóm với máy tính; Thiết bị ở đây, Studio là tab riêng.

/** Giọng đọc của "Nghe ngay" trên điện thoại: lõi native đọc (plugin ReadAloud); khoá lưu mã hoá bằng Android Keystore (OnlineKeys.kt). */
const phoneVoices: VoiceSettingsApi = {
  voices: async () => (await ReadAloud.voices()).voices,
  sample: (voice, text) => androidSource.readAloudSample!(voice, text),
  online: async () => (await ReadAloud.onlineProviders()).providers,
  saveKey: (provider, key, region) => ReadAloud.setOnlineKey({ provider, key, region }),
  removeKey: (provider) => ReadAloud.removeOnlineKey({ provider }),
  checkKey: (provider) => ReadAloud.checkOnlineKey({ provider }),
};

/** "Giọng Supertonic" trên điện thoại (SupertonicModule.kt): cùng thẻ, lời riêng. */
const phoneSupertonic: VieneuBackend = {
  status: () => ReadAloud.supertonicStatus(),
  start: (choices) => ReadAloud.supertonicStart(choices ? { choices } : {}),
  measure: () => ReadAloud.supertonicMeasure(),
  remove: (choice) => ReadAloud.supertonicRemove({ choice }),
  cancel: () => ReadAloud.supertonicCancel(),
  voices: phoneVieneu.voices,
};

/** "Tốc độ giọng trên máy" trên điện thoại (readaloud/VoiceSpeed.kt). */
const phoneVoiceSpeed: VoiceSpeedBackend = {
  status: () => ReadAloud.voiceSpeed(),
  set: (choice) => ReadAloud.setVoiceSpeed({ choice }),
};

/** Nhóm có mặt trên điện thoại, theo thứ tự của SETTINGS_GROUPS. */
export const PHONE_GROUPS: readonly SettingsGroupId[] = ["voice", "listen", "sleep", "look", "devices", "advanced"];

type Change = (patch: Partial<PlayerSettings>) => void;

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <Switch.Root
      checked={checked}
      onCheckedChange={(value) => {
        feedback("toggle");
        onChange(value);
      }}
      aria-label={label}
      className="ui-switch ui-switch-large"
    >
      <Switch.Thumb className="motion-switch-thumb" />
    </Switch.Root>
  );
}

function VoiceGroup() {
  return (
    <SettingsBlock>
      <div className="py-3.5">
        <VoiceSettings
          api={phoneVoices}
          deviceHint="Điện thoại chưa có giọng tiếng Việt. Cài ở Cài đặt điện thoại › Chuyển văn bản thành giọng nói."
          modules={(reload) => (
            <>
              <LocalVoiceModules vieneu={phoneVieneu} supertonic={phoneSupertonic} onChanged={reload} />
              <VoiceSpeedSetting backend={phoneVoiceSpeed} supertonic={phoneSupertonic} />
            </>
          )}
        />
      </div>
    </SettingsBlock>
  );
}

/** Chỉ hiện khi ABook chưa được phép hiện thông báo: nói hậu quả và mở đúng trang cài đặt. Quay lại từ Cài đặt Android thì hỏi lại. */
function NotificationRow() {
  const [state, setState] = useState<NotificationState>("granted");
  useEffect(() => {
    const check = () => void notificationState().then(setState);
    check();
    document.addEventListener("visibilitychange", check);
    return () => document.removeEventListener("visibilitychange", check);
  }, []);
  // Cho phép xong quay lại app (hay vừa bị tắt ở Cài đặt Android): dòng khép / mở tại chỗ, không bật tắt cứng.
  return (
    <MotionPresence open={state !== "granted"}>
      <SettingsRow label="Thông báo" hint={NOTIFICATION_ROW_HINT}>
        <Button size="sm" onClick={() => void openNotificationSettings().catch(() => undefined)}>
          Cho phép
        </Button>
      </SettingsRow>
    </MotionPresence>
  );
}

function ListenGroup({ settings, change }: { settings: PlayerSettings; change: Change }) {
  return (
    <>
      <SettingsBlock>
        <NotificationRow />
        <SettingsRow label="Tự lùi" hint="Nghỉ quá 30 giây thì lùi 5 giây (quá 10 phút: 10 giây).">
          <Toggle label="Tự lùi" checked={settings.autoRewind !== false} onChange={(value) => change({ autoRewind: value })} />
        </SettingsRow>
        <SettingsRow label="Nút tai nghe lùi/tới" hint="Bật: nút Trước/Sau lùi/tới 15 giây. Tắt: chuyển chương.">
          <Toggle label="Nút tai nghe lùi/tới" checked={settings.headsetSkips !== false} onChange={(value) => change({ headsetSkips: value })} />
        </SettingsRow>
      </SettingsBlock>
      {/* "Nhạc của tôi" là kho chung mọi cuốn: ở đây, không chỉ trong hộp "Sửa sách" của từng cuốn. */}
      <SettingsBlock title="Nhạc nền" id="music">
        <SettingsRow label={AUTO_MUSIC_LABEL} hint={AUTO_MUSIC_HINT}>
          <Toggle label={AUTO_MUSIC_LABEL} checked={settings.autoMusic !== false} onChange={(value) => change({ autoMusic: value })} />
        </SettingsRow>
        <div className="py-3.5">
          <MyMusicSection />
        </div>
      </SettingsBlock>
    </>
  );
}

function SleepGroup({ settings, change }: { settings: PlayerSettings; change: Change }) {
  return (
    <>
      <SettingsBlock>
        <SettingsRow label="Tự tắt" hint="Không chạm máy chừng này thì nhỏ dần rồi dừng.">
          <ChoiceRow
            label="Tự tắt"
            value={String(settings.safetyStopHours)}
            onChange={(value) => change({ safetyStopHours: Number(value) })}
            options={[
              { value: "0", label: "Không" },
              ...[1, 2, 3].map((hours) => ({ value: String(hours), label: `${hours} giờ` })),
            ]}
          />
        </SettingsRow>
        <SettingsRow label="Lịch đêm" hint="Nghe trong khung giờ này thì tự hẹn giờ.">
          <Toggle
            label="Lịch đêm"
            checked={Boolean(settings.sleepSchedule)}
            onChange={(value) => change({ sleepSchedule: value ? { from: "22:00", to: "06:00", minutes: 30 } : null })}
          />
        </SettingsRow>
        {/* Ba ô chọn giờ / số phút cao tối thiểu 48 dp như mọi đích chạm khác của Android (soát a100 T2). */}
        <MotionPresence open={Boolean(settings.sleepSchedule)}>
        {settings.sleepSchedule && (
          <div className="flex flex-wrap items-center gap-2 py-3 text-sm">
            <TimeSelect
              label="Từ"
              value={settings.sleepSchedule.from}
              onChange={(value) => change({ sleepSchedule: { ...settings.sleepSchedule!, from: value } })}

            />
            <span className="text-fg-2">đến</span>
            <TimeSelect
              label="Đến"
              value={settings.sleepSchedule.to}
              onChange={(value) => change({ sleepSchedule: { ...settings.sleepSchedule!, to: value } })}

            />
            <span className="text-fg-2">hẹn</span>
            <Select
              inline
              aria-label="Hẹn"
              value={settings.sleepSchedule.minutes}
              onChange={(event) => change({ sleepSchedule: { ...settings.sleepSchedule!, minutes: Number(event.target.value) } })}

            >
              {[15, 30, 45, 60].map((minutes) => (
                <option key={minutes} value={minutes}>
                  {minutes} phút
                </option>
              ))}
            </Select>
          </div>
        )}
        </MotionPresence>
      </SettingsBlock>
      <SettingsBlock title="Cử chỉ" fold="sleep.gestures">
        <SettingsRow label="Lắc để nghe thêm" hint="Đang hẹn giờ, lắc nhẹ hai lần để thêm giờ.">
          <Toggle label="Lắc để nghe thêm" checked={settings.shakeToExtend} onChange={(value) => change({ shakeToExtend: value })} />
        </SettingsRow>
        <MotionPresence open={settings.shakeToExtend}>
        {settings.shakeToExtend && (
          <>
            <SettingsRow label="Khi lắc" hint="Đặt lại: hẹn giờ quay về từ đầu.">
              <ChoiceRow
                label="Khi lắc"
                value={settings.shakeAction ?? "extend"}
                onChange={(value) => change({ shakeAction: value })}
                options={[
                  { value: "extend", label: "Cộng thêm" },
                  { value: "reset", label: "Đặt lại" },
                ]}
              />
            </SettingsRow>
            <SettingsRow label="Độ nhạy">
              <ChoiceRow
                label="Độ nhạy"
                value={settings.shakeSensitivity ?? "normal"}
                onChange={(value) => change({ shakeSensitivity: value })}
                options={[
                  { value: "gentle", label: "Nhẹ tay" },
                  { value: "normal", label: "Vừa" },
                  { value: "firm", label: "Mạnh tay" },
                ]}
              />
            </SettingsRow>
          </>
        )}
        </MotionPresence>
        <SettingsRow label="Úp máy để dừng" hint="Lật lên trong 10 phút là nghe tiếp.">
          <Toggle label="Úp máy để dừng" checked={settings.flipToPause ?? false} onChange={(value) => change({ flipToPause: value })} />
        </SettingsRow>
      </SettingsBlock>
      <SettingsBlock title="Khi sắp tắt" fold="sleep.ending">
        <SettingsRow label="Mỗi lần thêm">
          <ChoiceRow
            label="Mỗi lần thêm"
            value={String(settings.sleepExtendMinutes)}
            onChange={(value) => change({ sleepExtendMinutes: Number(value) })}
            options={[5, 10, 15].map((value) => ({ value: String(value), label: `${value}′` }))}
          />
        </SettingsRow>
        <SettingsRow label="Nhỏ dần">
          <ChoiceRow
            label="Nhỏ dần"
            value={String(settings.sleepFadeSeconds)}
            onChange={(value) => change({ sleepFadeSeconds: Number(value) })}
            options={[10, 30, 60].map((value) => ({ value: String(value), label: `${value}s` }))}
          />
        </SettingsRow>
      </SettingsBlock>
    </>
  );
}

function LookGroup({ settings, change }: { settings: PlayerSettings; change: Change }) {
  return (
    <SettingsBlock>
      <SettingsRow label="Màu">
        <ChoiceRow
          label="Màu"
          value={settings.theme}
          onChange={(value) => change({ theme: value })}
          options={[
            { value: "system", label: "Tự động" },
            { value: "light", label: "Sáng" },
            { value: "dark", label: "Tối" },
          ]}
        />
      </SettingsRow>
      <SettingsRow label="Nền đọc" hint="Nền của chữ khi đọc theo.">
        <ChoiceRow label="Nền đọc" value={settings.readingSurface} onChange={(value) => change({ readingSurface: value })} options={READING_SURFACES} />
      </SettingsRow>
      <SettingsRow label="Âm thanh chạm" hint={TOUCH_SOUNDS_HINT}>
        <Toggle label="Âm thanh chạm" checked={settings.touchSounds} onChange={(value) => change({ touchSounds: value })} />
      </SettingsRow>
      <SettingsRow label="Rung" hint="Rung nhẹ khi bạn chọn hay giữ.">
        <Toggle label="Rung" checked={settings.haptics} onChange={(value) => change({ haptics: value })} />
      </SettingsRow>
    </SettingsBlock>
  );
}

/** Bản lưu cũ app đang giữ hộ (lần lưu hỏng giữa chừng): chỉ hiện khi có file, đứng đầu Nâng cao vì là thứ có thể mất nếu không để ý. */
function OldSavesBlock() {
  const { data } = useOldSaves();
  // Lưu ra / xoá hết bản cũ: cả khối khép lại (MotionPresence giữ hình cuối), không biến mất cứng. `first:mt-6`: khối đứng một mình trong vỏ.
  return (
    <MotionPresence open={Boolean(data?.length)}>
      {data?.length ? (
        <SettingsBlock title={`Bản lưu cũ (${data.length})`} id="old-saves" className="first:mt-6">
          <OldSavesList files={data} />
        </SettingsBlock>
      ) : null}
    </MotionPresence>
  );
}

/** "Chẩn đoán": xem / gửi / xoá nhật ký của app (Diagnostics.kt). Gửi = bảng chia sẻ của hệ thống, bạn tự chọn gửi cho ai. */
function DiagnosticsBlock() {
  const diagnostics = useDiagnostics();
  const [asking, setAsking] = useState(false);
  return (
    <SettingsBlock title="Chẩn đoán" id="diagnostics" fold="advanced.diagnostics">
      <SettingsRow label="Nhật ký" hint={DIAGNOSTICS_HINT}>
        <Sheet open={diagnostics.open} onOpenChange={diagnostics.changeOpen} title="Nhật ký của ABook" trigger={<Button size="sm">Xem</Button>}>
          <div className="space-y-3 px-1.5 pb-3 pt-3">
            <Button size="sm" variant="ghost" loading={diagnostics.loading} onClick={() => void diagnostics.load()}>
              Làm mới
            </Button>
            <DiagnosticsPanel report={diagnostics.report} error={diagnostics.error} loading={diagnostics.loading} />
          </div>
        </Sheet>
      </SettingsRow>
      <MoreInfo>{DIAGNOSTICS_MORE}</MoreInfo>
      <SettingsRow label="Gửi nhật ký" hint={SEND_HINT}>
        <Button size="sm" loading={diagnostics.sending} onClick={() => void diagnostics.send()}>
          Gửi
        </Button>
      </SettingsRow>
      <SettingsRow label="Xoá nhật ký" hint={CLEAR_HINT}>
        <Button size="sm" onClick={() => setAsking(true)}>
          Xoá
        </Button>
      </SettingsRow>
      {/* Việc không lấy lại được thì hỏi lại trong hộp dùng chung (cùng lời với bản native: CLEAR_QUESTION). */}
      <Dialog
        open={asking}
        onOpenChange={setAsking}
        title="Xoá nhật ký?"
        description={CLEAR_QUESTION}
        footer={
          <DialogActions>
            <Button variant="ghost" onClick={() => setAsking(false)}>
              Giữ lại
            </Button>
            <Button variant="danger" onClick={() => { setAsking(false); void diagnostics.clear(); }}>
              Xoá
            </Button>
          </DialogActions>
        }
      />
    </SettingsBlock>
  );
}

// Dấu "/" cuối: lõi native chỉ mở địa chỉ bắt đầu bằng "https://github.com/ntanhpro1221/ABook/" (LibraryPlugin.openRelease).
const SOURCE_URL = "https://github.com/ntanhpro1221/ABook/";

/** "Giới thiệu": bản đang cài, mã nguồn (MIT), thành phần bên thứ ba (docs/THIRD_PARTY.md gói lúc build) trong tấm trượt. */
export function AboutBlock({ version }: { version: string | null }) {
  const [open, setOpen] = useState(false);
  return (
    <SettingsBlock title="Giới thiệu" id="about" fold="advanced.about">
      <SettingsRow label="Phiên bản">
        <span className="tabular text-sm text-fg-2">{version ?? "…"}</span>
      </SettingsRow>
      <SettingsRow label="Mã nguồn mở" hint="Giấy phép MIT - github.com/ntanhpro1221/ABook">
        <Button size="sm" onClick={() => void openRelease(SOURCE_URL)}>
          Mở
        </Button>
      </SettingsRow>
      <Sheet
        open={open}
        onOpenChange={setOpen}
        title="Thành phần sử dụng"
        trigger={
          <DisclosureRow title="Thành phần sử dụng" />
        }
      >
        <div className="px-1.5 pt-3">{open && <ThirdPartyList />}</div>
      </Sheet>
    </SettingsBlock>
  );
}

function AdvancedGroup({ version, update }: { version: string | null; update: ReturnType<typeof useAppUpdate>["update"] }) {
  return (
    <>
      <OldSavesBlock />
      {/* Điện thoại không tự cập nhật như app Windows: báo bản mới trên GitHub, mời tải APK (updates.ts). */}
      <MotionPresence open={Boolean(update)}>
        {update && (
          <SettingsBlock title="Cập nhật" className="first:mt-6">
            <SettingsRow label={`Có bản mới ${update.version}`} hint="Cài đè; sách và chỗ đang nghe giữ nguyên.">
              <Button size="sm" variant="primary" icon={Download} onClick={() => void openRelease(update.apk ?? update.page)}>
                Tải
              </Button>
            </SettingsRow>
          </SettingsBlock>
        )}
      </MotionPresence>
      <SettingsBlock title="Bộ nhớ">
        <ReadAloudStorage api={{ usage: () => ReadAloud.cacheUsage(), clear: () => ReadAloud.cacheClear() }} />
      </SettingsBlock>
      <DiagnosticsBlock />
      <AboutBlock version={version} />
    </>
  );
}

/** Bộ nhớ của WebView không ghi được (đầy, bị chặn): thay đổi vẫn dùng ngay và lõi nghe vẫn nhớ, nhưng báo để bạn kiểm lại lần mở sau. */
export const SAVE_FAILED = "Chưa lưu được thay đổi. Lần mở sau bạn xem lại Cài đặt.";

/** Dòng cảnh báo trên trang gốc (bản lưu cũ, bản mới): chỉ là lối tắt vào Nâng cao, không phải mục thứ hai. */
function RootNotice({ text, tone }: { text: string; tone: "warning" | "accent" }) {
  return (
    <DisclosureRow to={settingsPath("advanced")} className="mt-4" title={text} icon={tone === "warning" ? <TriangleAlert className="size-5 text-warning" /> : <Download className="size-5 text-accent-text" />} />
  );
}

export function SettingsScreen() {
  const { group } = useParams();
  const [settings, setSettings] = useState<PlayerSettings>(loadSettings);
  const { current, update } = useAppUpdate();
  const { data: oldSaves } = useOldSaves();
  const voiceName = useDefaultVoiceName(phoneVoices.voices);
  const change: Change = (patch) => {
    const next = { ...settings, ...patch };
    setSettings(next);
    if (!saveSettings(next)) toast.error(SAVE_FAILED, { id: "settings-not-saved" });
    if (patch.theme) applyTheme(patch.theme, true);
    if ("touchSounds" in patch || "haptics" in patch || "readingSurface" in patch) applySenses(next);
  };
  const active = isSettingsGroup(group) && PHONE_GROUPS.includes(group) ? group : null;
  if (active) {
    return (
      <div className="settings-page px-[20px] pb-10">
        <GroupHeader id={active} />
        {active === "voice" && <VoiceGroup />}
        {active === "listen" && <ListenGroup settings={settings} change={change} />}
        {active === "sleep" && <SleepGroup settings={settings} change={change} />}
        {active === "look" && <LookGroup settings={settings} change={change} />}
        {active === "devices" && <DevicesScreen />}
        {active === "advanced" && <AdvancedGroup version={current} update={update} />}
      </div>
    );
  }
  const rows: GroupRow[] = [
    { id: "voice", summary: voiceName },
    { id: "listen", summary: listenSummary(settings.autoRewind !== false, settings.autoMusic !== false) },
    { id: "sleep", summary: sleepSummary(settings.sleepSchedule, settings.safetyStopHours) },
    { id: "look", summary: themeSummary(settings.theme, "Tự động") },
    { id: "devices", summary: "Nối máy · chia sẻ · dung lượng" },
    { id: "advanced", summary: current ? `Phiên bản ${current}` : undefined },
  ];
  return (
    <div className="settings-page px-[20px] pb-10">
      <ScreenHeader title="Cài đặt" />
      {/* Lời báo trên trang gốc tới sau một lượt hỏi (bản lưu cũ, bản mới): mở ra tại chỗ, không đẩy danh sách nhóm xuống tức thì. */}
      <MotionPresence open={Boolean(oldSaves?.length)}>
        {oldSaves?.length ? <RootNotice tone="warning" text={`Bản lưu cũ (${oldSaves.length}) - cần lưu ra`} /> : null}
      </MotionPresence>
      <MotionPresence open={Boolean(update)}>{update && <RootNotice tone="accent" text={`Có bản mới ${update.version}`} />}</MotionPresence>
      <SettingsList rows={rows} className="mt-5" />
    </div>
  );
}

import { MotionRegion } from "@/shared/MotionRegion";
import { MotionPresence } from "@/shared/MotionPresence";
import { SleepSchedule } from "./SleepSchedule";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Download, FolderOpen } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { toast } from "@/shared/toast";
import { useMediaQuery } from "@/shared/media";
import { Button, Dialog, Segmented, WRAP_LABEL } from "@/shared/ui";
import { GroupHeader, isSettingsGroup, SettingsBlock, SettingsList, SettingsRow, settingsPath, type GroupRow, type SettingsGroupId } from "@/shared/SettingsNav";
import { sleepSummary, themeSummary } from "@/shared/settingsSummary";
import { ThirdPartyList } from "@/shared/ThirdPartyList";
import { cn } from "@/shared/cn";
import { TOUCH_SOUNDS_HINT } from "@/shared/feedback";
import { READING_SURFACES, readingSurfaceOr, type ReadingSurface } from "@/shared/readingSurface";
import { openExternal } from "@/shared/openExternal";
import { OnComputerOnly } from "@/shared/OnComputerOnly";
import { api, type AppInfo } from "@/studio/api";
import { pickFolder, useAppInfo, usePreferences, useVoices } from "@/studio/data";
import { StudioSettings } from "@/studio/StudioSetup";
import { PROFILE_LABEL } from "@/studio/bookTemplates";
import { SharedReadingsSettings } from "@/studio/sharedReadings";
import { BookTemplates } from "./BookTemplates";
import { LocalVoiceModules } from "@/listen/VieneuModuleCard";
import { VoiceSpeedSetting } from "@/listen/VoiceSpeedSetting";
import { EXTEND_GESTURE } from "@/listen/extendGesture";
import { LETTER_SHORTCUTS_HINT, ShortcutList } from "@/listen/Shortcuts";
import { MyMusicSection } from "@/listen/MyMusic";
import { MUSIC_CHANGED_ALL, MUSIC_CHANGED_EVENT } from "@/listen/musicBed";
import { AUTO_MUSIC_HINT, AUTO_MUSIC_LABEL } from "@/listen/playlistBed";
import { ReadAloudStorage } from "@/listen/ReadAloudStorage";
import { useDefaultVoiceName, VoiceSettings, type KeyCheck, type OnlineProviderInfo, type VoiceSettingsApi } from "@/listen/VoiceSettings";
import { httpSource } from "./httpSource";
import { OtherComputers } from "./OtherComputers";
import { OwnDiagnostics } from "./OwnDiagnostics";
import { PhoneSync, Switch, type SyncView } from "./PhoneSync";
import { checkLine, UPDATE_CHECKED_EVENT, UPDATE_CHECK_WAIT_MS, type CheckLine, type UpdateChecked } from "./updateCheck";

// Cài đặt của máy tính (chủ app 23-10: "như lạc vào ma trận"): cùng cây nhóm với điện thoại (shared/SettingsNav.tsx). Cửa sổ rộng: danh sách nhóm
// bên trái, nội dung bên phải; hẹp (trình duyệt điện thoại điều khiển từ xa): trang gốc là danh sách, mỗi nhóm một màn con như điện thoại.

const SOURCE_URL = "https://github.com/ntanhpro1221/ABook/";

/** Giọng đọc của "Nghe ngay" trên máy tính: máy chủ cục bộ (abook/readaloud) đọc, khóa của người dùng gửi trong thân yêu cầu, chỉ nhận lại bản che. */
const desktopVoices: VoiceSettingsApi = {
  voices: () => httpSource.readAloudVoices!(),
  sample: (voice, text) => httpSource.readAloudSample!(voice, text),
  online: () => api<OnlineProviderInfo[]>("/api/readaloud/online"),
  saveKey: (provider, key, region) => api<OnlineProviderInfo>(`/api/readaloud/online/${provider}`, { method: "PUT", body: { key, region } }),
  removeKey: (provider) => api<OnlineProviderInfo>(`/api/readaloud/online/${provider}`, { method: "DELETE" }),
  checkKey: (provider) => api<KeyCheck>(`/api/readaloud/online/${provider}/check`, { method: "POST", body: {} }),
};

/** Nhóm có mặt trên máy này: từ xa chỉ còn những gì đổi được từ xa; Studio khi app có Studio (đã cài hay chưa). */
export function desktopGroups(info: AppInfo | undefined, touchOnly: boolean): SettingsGroupId[] {
  const remote = Boolean(info?.remote);
  const groups: SettingsGroupId[] = [];
  if (!remote) groups.push("voice", "listen", "sleep");
  if (!remote || !touchOnly) groups.push("look");
  if (!remote) groups.push("devices");
  if ((!remote && info?.studio) || (remote && !info?.listenOnly)) groups.push("studio");
  groups.push("advanced");
  return groups;
}

// Mặc định cho sách MỚI (soát UX a5 01-10: mỗi lần tạo sách lại chọn giọng kể và chất lượng như lần trước). "Làm tiếp cuốn
// này" vẫn theo phần trước.
function NewBookDefaults() {
  const { data: preferences, update } = usePreferences();
  const { data: voices } = useVoices();
  const selectClass = "h-9 w-full rounded-lg border border-line bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-focus";
  return (
    <div className="grid gap-3 py-3 sm:grid-cols-2">
      <label htmlFor="new-book-narrator" className="block">
        <span className="block text-sm font-medium">Giọng kể</span>
        <select
          id="new-book-narrator"
          className={cn(selectClass, "mt-1")}
          value={preferences?.newBookNarrator ?? ""}
          onChange={(event) => update({ newBookNarrator: event.target.value })}
        >
          <option value="">Máy đề xuất</option>
          {(voices ?? []).map((voice) => (
            <option key={voice.name} value={voice.name}>
              {voice.name} · {voice.gender}, miền {voice.region}
            </option>
          ))}
        </select>
      </label>
      <label htmlFor="new-book-profile" className="block">
        <span className="block text-sm font-medium">Chất lượng</span>
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

// Cùng một điều khiển và cùng chữ với điện thoại (soát 24-10 T18: máy tính 3 thẻ to "Theo Windows", điện thoại segmented "Tự động").
const THEMES = [
  { value: "system", label: "Tự động" },
  { value: "light", label: "Sáng" },
  { value: "dark", label: "Tối" },
] as const;

/** App Windows đóng gói: vỏ đã tìm thấy bản mới (đã ký) - cài chỉ khi người dùng bấm, vì app phải đóng rồi mở lại. */
function UpdateRow({ update, current }: { update: { version: string; notes: string }; current: string }) {
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
      toast.success(`Đang tải ABook ${update.version}`, { description: "App tự mở lại; sách và chỗ đang nghe giữ nguyên.", duration: 60_000 });
    } catch (error) {
      setBusy(false);
      toast.error("Chưa cập nhật được", { description: (error as Error).message });
    }
  };
  return (
    <div className="py-3">
      <p className="text-sm">
        <span className="font-semibold">ABook {update.version}</span> đã có{current ? ` · đang dùng ${current}` : ""}
      </p>
      {update.notes && <p className="mt-2 whitespace-pre-line text-[0.8125rem] leading-relaxed text-fg-2 text-pretty">{update.notes}</p>}
      <Button className="mt-3" icon={Download} disabled={busy} onClick={() => void install()}>
        {busy ? "Đang tải bản mới…" : "Cập nhật ABook"}
      </Button>
    </div>
  );
}

/** Chưa có bản mới: nút kiểm lại (lần tự kiểm lúc mở app im lặng khi mất mạng) - bấm xong luôn có một lời, kể cả khi mạng đứt. */
function UpdateCheck({ current }: { current: string }) {
  const [checking, setChecking] = useState(false);
  const [line, setLine] = useState<CheckLine | null>(null);
  useEffect(() => {
    if (!checking) return;
    const done = (detail: UpdateChecked | null) => {
      setChecking(false);
      setLine(checkLine(detail, current));
    };
    const heard = (event: Event) => done((event as CustomEvent<UpdateChecked>).detail);
    window.addEventListener(UPDATE_CHECKED_EVENT, heard);
    const silent = window.setTimeout(() => done(null), UPDATE_CHECK_WAIT_MS);
    return () => {
      window.removeEventListener(UPDATE_CHECKED_EVENT, heard);
      window.clearTimeout(silent);
    };
  }, [checking, current]);
  const check = async () => {
    setLine(null);
    setChecking(true);
    try {
      await api("/api/app/check-update", { method: "POST", body: {} });
    } catch (error) {
      setChecking(false);
      setLine({ tone: "error", text: (error as Error).message });
    }
  };
  return (
    <SettingsRow
      label={current ? `ABook ${current}` : "Bản mới"}
      hint={<MotionRegion as="span" motionKey={line?.text ?? ""}>{line && <span className={cn(line.tone === "error" && "text-danger")} role="status">{line.text}</span>}</MotionRegion>}
    >
      <Button size="sm" variant="secondary" disabled={checking} onClick={() => void check()}>
        {checking ? "Đang kiểm tra…" : "Kiểm tra bản mới"}
      </Button>
    </SettingsRow>
  );
}

/** Danh sách thành phần bên thứ ba (docs/THIRD_PARTY.md, gói lúc build) trong một hộp - trang Cài đặt không dài thêm. */
function ThirdPartyButton() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button className={WRAP_LABEL} size="sm" variant="secondary" onClick={() => setOpen(true)}>
        Thành phần sử dụng
      </Button>
      <Dialog open={open} onOpenChange={setOpen} title="Thành phần sử dụng" width="max-w-2xl">
        <div className="mt-3 max-h-[65vh] select-text overflow-y-auto pr-1">{open && <ThirdPartyList />}</div>
      </Dialog>
    </>
  );
}

function VoiceGroup() {
  return (
    <SettingsBlock>
      <div className="py-3.5">
        <VoiceSettings
          api={desktopVoices}
          deviceHint="Cài giọng tiếng Việt tại Cài đặt Windows › Thời gian và ngôn ngữ › Giọng nói."
          modules={(reload) => (
            <>
              <LocalVoiceModules onChanged={reload} />
              <VoiceSpeedSetting />
            </>
          )}
        />
      </div>
    </SettingsBlock>
  );
}

function ListenGroup() {
  const { data: preferences, update } = usePreferences();
  const client = useQueryClient();
  return (
    <>
      <SettingsBlock>
        <SettingsRow label="Tự lùi" hint="Nghỉ quá 30 giây thì lùi 5 giây (quá 10 phút: 10 giây).">
          <Switch id="auto-rewind" label="Tự lùi" checked={preferences?.autoRewind !== false} onCheckedChange={(value) => update({ autoRewind: value })} />
        </SettingsRow>
      </SettingsBlock>
      {/* "Nhạc của tôi" là kho chung mọi cuốn: ở đây, không chỉ trong hộp "Sửa sách" của từng cuốn. */}
      <SettingsBlock title="Nhạc nền" id="music">
        <SettingsRow label={<span id="auto-music-name">{AUTO_MUSIC_LABEL}</span>} hint={<span id="auto-music-hint">{AUTO_MUSIC_HINT}</span>}>
          <Switch
            id="auto-music"
            labelledBy="auto-music-name"
            describedBy="auto-music-hint"
            checked={preferences?.autoMusic !== false}
            onCheckedChange={(value) =>
              update(
                { autoMusic: value },
                {
                  onSuccess: () => {
                    void client.invalidateQueries({ queryKey: ["listen"] });
                    window.dispatchEvent(new CustomEvent(MUSIC_CHANGED_EVENT, { detail: MUSIC_CHANGED_ALL })); // cuốn đang nghe đổi nhạc ngay, không đợi chương sau
                    toast.success(value ? "Đã bật tự chọn nhạc nền" : "Đã tắt tự chọn nhạc nền");
                  },
                },
              )
            }
          />
        </SettingsRow>
        <div className="py-3.5">
          <MyMusicSection />
        </div>
      </SettingsBlock>
    </>
  );
}

function SleepGroup() {
  const { data: preferences, update } = usePreferences();
  const fade = String(preferences?.sleepFadeSeconds ?? 30) as "10" | "30" | "60";
  const extend = String(preferences?.sleepExtendMinutes ?? 10) as "5" | "10" | "15";
  return (
    <SettingsBlock>
      <SettingsRow label="Tự tắt" hint="Không ai chạm máy chừng này thì nhỏ dần rồi dừng.">
        <Segmented<"0" | "1" | "2" | "3">
          label="Tự tắt"
          value={String(preferences?.safetyStopHours ?? 2) as "0" | "1" | "2" | "3"}
          onChange={(value) => update({ safetyStopHours: Number(value) })}
          options={[
            { value: "0", label: "Không" },
            { value: "1", label: "1 giờ" },
            { value: "2", label: "2 giờ" },
            { value: "3", label: "3 giờ" },
          ]}
        />
      </SettingsRow>
      <SleepSchedule />
      <SettingsRow label="Mỗi lần nghe thêm" hint={`Lúc đang nhỏ dần: ${EXTEND_GESTURE}.`}>
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
      </SettingsRow>
      <SettingsRow label="Nhỏ dần">
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
      </SettingsRow>
    </SettingsBlock>
  );
}

function LookGroup({ remote, touchOnly }: { remote: boolean; touchOnly: boolean }) {
  const { data: preferences, update } = usePreferences();
  return (
    <>
      {!remote && (
        <SettingsBlock>
          <SettingsRow label="Màu">
            <Segmented label="Màu" value={preferences?.theme ?? "system"} onChange={(theme) => update({ theme })} options={[...THEMES]} />
          </SettingsRow>
          <SettingsRow label="Nền đọc" hint="Nền của chữ khi đọc theo.">
            <Segmented<ReadingSurface>
              label="Nền đọc"
              value={readingSurfaceOr(preferences?.readingSurface)}
              onChange={(readingSurface) => update({ readingSurface })}
              options={READING_SURFACES}
            />
          </SettingsRow>
          <SettingsRow label={<span id="touch-sounds-name">Âm thanh chạm</span>} hint={<span id="touch-sounds-hint">{TOUCH_SOUNDS_HINT}</span>}>
            <Switch
              id="touch-sounds"
              labelledBy="touch-sounds-name"
              describedBy="touch-sounds-hint"
              checked={preferences?.touchSounds !== false}
              onCheckedChange={(value) => update({ touchSounds: value })}
            />
          </SettingsRow>
        </SettingsBlock>
      )}
      {/* Phím tắt vô nghĩa trên màn chỉ có cảm ứng (điện thoại, máy tính bảng không bàn phím): ẩn cả khối. */}
      {!touchOnly && (
        <SettingsBlock title="Phím tắt" id="shortcuts">
          <SettingsRow label={<span id="letter-shortcuts-name">Phím tắt chữ</span>} hint={<span id="letter-shortcuts-hint">{LETTER_SHORTCUTS_HINT}</span>}>
            {/* Công tắc này lưu ở máy tính (PUT /api/preferences không qua Studio từ xa): ở xa thì nói đổi ở đâu thay vì để nó bấm ra 403 im lặng. */}
            {remote ? (
              <OnComputerOnly verb="Đổi" className="shrink-0" />
            ) : (
              <Switch
                id="letter-shortcuts"
                labelledBy="letter-shortcuts-name"
                describedBy="letter-shortcuts-hint"
                checked={preferences?.letterShortcuts !== false}
                onCheckedChange={(value) => update({ letterShortcuts: value })}
              />
            )}
          </SettingsRow>
          <div className="py-3">
            <ShortcutList remote={remote} inSettings />
          </div>
        </SettingsBlock>
      )}
    </>
  );
}

function DevicesGroup() {
  return (
    <>
      {/* Tự dựng hai khối "Máy này" và "Thiết bị đã ghép". */}
      <PhoneSync />
      <SettingsBlock title="Máy tính khác" id="computers">
        <div className="py-3.5">
          <OtherComputers />
        </div>
      </SettingsBlock>
    </>
  );
}

function StudioGroup({ info }: { info: AppInfo | undefined }) {
  const { data: preferences, update } = usePreferences();
  if (info?.remote) {
    return (
      <SettingsBlock title="Mẫu thiết lập" id="templates">
        <div className="py-3.5">
          <BookTemplates />
        </div>
      </SettingsBlock>
    );
  }
  const installed = Boolean(info?.studio?.installed);
  return (
    <>
      {/* Trạng thái Studio (đã cài / chưa cài + Gỡ hay Cài) ở đầu nhóm cùng việc của riêng máy này; chưa cài thì các tuỳ chọn vẫn xem và chỉnh được, có một dòng nói rõ. */}
      <SettingsBlock title="Máy này" id="machine">
        <StudioSettings />
        <SettingsRow label={<span id="pause-on-battery-name">Tạm dừng dùng pin</span>} hint={<span id="pause-on-battery-hint">Cắm sạc lại thì tự làm tiếp đúng chỗ.</span>}>
          <Switch
            id="pause-on-battery"
            labelledBy="pause-on-battery-name"
            describedBy="pause-on-battery-hint"
            checked={preferences?.pauseOnBattery !== false}
            onCheckedChange={(value) => update({ pauseOnBattery: value })}
          />
        </SettingsRow>
      </SettingsBlock>
      <MotionPresence open={!installed}><p className="mt-2 text-[0.8125rem] text-fg-2">Tuỳ chọn ở trang này dùng khi đã cài Studio.</p></MotionPresence>
      <SettingsBlock title="Sách mới" fold="studio.new-book">
        <NewBookDefaults />
        <div className="py-3.5">
          <BookTemplates />
        </div>
      </SettingsBlock>
      <SettingsBlock title="Cách đọc chung" fold="studio.shared-readings">
        <SharedReadingsSettings />
      </SettingsBlock>
    </>
  );
}

export function AdvancedGroup({ info }: { info: AppInfo | undefined }) {
  const { data: preferences, update } = usePreferences();
  const remote = Boolean(info?.remote);
  const changeLibrary = async () => {
    try {
      const path = await pickFolder("Chọn thư mục thư viện", preferences?.libraryRoot ?? "");
      // Báo "đã đổi" chỉ khi máy chủ đã nhận; bị từ chối thì usePreferences báo lý do (soát a100 V3).
      if (path) update({ libraryRoot: path }, { onSuccess: () => toast.success("Đã đổi thư mục thư viện") });
    } catch (error) {
      toast.error((error as Error).message);
    }
  };
  return (
    <>
      <MotionPresence open={!info?.listenOnly}>
        <SettingsBlock title="Thư viện" id="library">
          <div className="settings-library-row flex flex-wrap items-center gap-2 py-3">
            <div className="flex min-h-10 min-w-0 flex-1 basis-48 items-center gap-3 text-sm text-fg-2">
              <FolderOpen className="size-4 shrink-0" />
              <span className="truncate" title={preferences?.libraryRoot}>{preferences?.libraryRoot}</span>
            </div>
            {info?.dialogs && (
              <Button size="sm" variant="secondary" icon={FolderOpen} className={cn("touch-row", WRAP_LABEL)} onClick={() => void changeLibrary()}>
                Đổi thư mục
              </Button>
            )}
          </div>
        </SettingsBlock>
      </MotionPresence>
      {!remote && (info?.update || info?.canCheckUpdate) && (
        <SettingsBlock title="Cập nhật" id="update">
          <MotionRegion>{info.update ? <UpdateRow update={info.update} current={info.version} /> : <UpdateCheck current={info.version} />}</MotionRegion>
        </SettingsBlock>
      )}
      {!remote && (
        <SettingsBlock title="Bộ nhớ">
          <div className="py-3.5">
            <ReadAloudStorage api={{ usage: () => httpSource.readAloudCacheTotal!(), clear: () => httpSource.readAloudCacheClearAll!() }} />
          </div>
        </SettingsBlock>
      )}
      {!remote && (
        <SettingsBlock title="Chẩn đoán" id="diagnostics" fold="advanced.diagnostics">
          <div className="py-3.5">
            <OwnDiagnostics />
          </div>
        </SettingsBlock>
      )}
      <SettingsBlock title="Giới thiệu" id="about" fold="advanced.about">
        <div className="space-y-3 py-3.5">
          <p className="text-sm text-fg-2">ABook {info?.version} - nghe sách tiếng Việt và làm sách nói.</p>
          {/* Liên kết mở ở cửa sổ mới (target="_blank"), không điều hướng chính cửa sổ app; cửa sổ app Windows nuốt target nên openExternal nhờ máy chủ mở. */}
          <p className="select-text text-sm text-fg-2">
            Mã nguồn mở (MIT):{" "}
            <a href={SOURCE_URL} target="_blank" rel="noopener noreferrer" onClick={(event) => openExternal(SOURCE_URL, event)} className="font-medium text-accent-text underline underline-offset-2 [overflow-wrap:anywhere]">
              github.com/ntanhpro1221/ABook
            </a>
          </p>
          <ThirdPartyButton />
        </div>
      </SettingsBlock>
    </>
  );
}

function GroupBody({ id, info, touchOnly }: { id: SettingsGroupId; info: AppInfo | undefined; touchOnly: boolean }) {
  const remote = Boolean(info?.remote);
  if (id === "voice") return <VoiceGroup />;
  if (id === "listen") return <ListenGroup />;
  if (id === "sleep") return <SleepGroup />;
  if (id === "look") return <LookGroup remote={remote} touchOnly={touchOnly} />;
  if (id === "devices") return <DevicesGroup />;
  if (id === "studio") return <StudioGroup info={info} />;
  return <AdvancedGroup info={info} />;
}

/** Ghi chú khi dùng ABook của máy tính qua mạng: không phải tuỳ chọn, chỉ nói cài đặt nào đổi được ở đây. */
function RemoteNote({ listenOnly }: { listenOnly: boolean }) {
  return (
    <p className="mt-3 text-[0.8125rem] text-fg-2 text-pretty">
      {listenOnly ? "Bật Điều khiển sản xuất trên máy tính để làm sách từ xa." : "Cài đặt chính nằm trên máy tính đang kết nối."}
    </p>
  );
}

function useRows(groups: readonly SettingsGroupId[], info: AppInfo | undefined): GroupRow[] {
  const { data: preferences } = usePreferences();
  const voiceName = useDefaultVoiceName(desktopVoices.voices);
  const { data: sync } = useQuery({ queryKey: ["sync"], queryFn: () => api<SyncView>("/api/sync"), enabled: groups.includes("devices") });
  const summary: Record<SettingsGroupId, string | undefined> = {
    voice: voiceName,
    listen: `${preferences?.autoRewind !== false ? "Tự lùi" : "Không tự lùi"} · ${preferences?.autoMusic !== false ? "nhạc tự chọn" : "không nhạc nền"}`,
    sleep: sleepSummary(preferences?.sleepSchedule, preferences?.safetyStopHours ?? 2),
    look: info?.remote ? "Phím tắt" : themeSummary(preferences?.theme, "Tự động"),
    devices: sync ? (sync.enabled ? `${sync.devices.length} thiết bị đã ghép` : "Đang tắt") : undefined,
    studio: info?.remote ? "Mẫu thiết lập" : info?.studio?.installed ? "Đã cài" : "Chưa cài",
    advanced: info?.update && !info.remote ? `Có bản mới ${info.update.version}` : info?.version ? `Phiên bản ${info.version}` : undefined,
  };
  return groups.map((id) => ({ id, summary: summary[id] }));
}

export function SettingsScreen() {
  const { group } = useParams();
  const { data: info } = useAppInfo();
  // Phím tắt vô nghĩa trên màn chỉ có cảm ứng (điện thoại, máy tính bảng không bàn phím): ẩn cả mục.
  const touchOnly = useMediaQuery("(hover: none) and (pointer: coarse)");
  const wide = useMediaQuery("(min-width: 1024px)");
  const groups = desktopGroups(info, touchOnly);
  const rows = useRows(groups, info);
  const active = isSettingsGroup(group) && groups.includes(group) ? group : null;
  const notices = (
    <>
      {info?.remote && <RemoteNote listenOnly={Boolean(info.listenOnly)} />}
      <MotionPresence open={Boolean(info?.update && !info.remote && !wide)}>{info?.update && !info.remote && !wide && (
        <Link to={settingsPath("advanced")} className="mt-4 flex items-center gap-3 rounded-2xl border border-line bg-panel py-3 text-sm font-medium hover:bg-hover">
          <Download className="size-5 shrink-0 text-accent-text" />
          <span className="min-w-0 flex-1">Có ABook {info.update.version}</span>
          <ChevronRight className="size-4 shrink-0 text-fg-3" />
        </Link>
      )}</MotionPresence>
    </>
  );
  if (wide) {
    // Hai cột: /settings mở sẵn nhóm đầu; đổi nhóm thay chỗ trong lịch sử như đổi tab. Hai tiêu đề khác cỡ chung một hàng lưới,
    // canh theo chân chữ (canh đỉnh để chân chữ lệch 3 px).
    const shown = active ?? groups[0];
    return (
      <div className="settings-page page-x mx-auto grid max-w-[1180px] grid-cols-[260px_minmax(0,1fr)] gap-x-8 pb-16 pt-9">
        <h1 className="self-baseline text-[1.75rem] font-bold tracking-tight">Cài đặt</h1>
        <div className="min-w-0 max-w-[760px] self-baseline">
          <GroupHeader id={shown} back={false} />
        </div>
        <div>
          {notices}
          <SettingsList rows={rows} current={shown} className="mt-5" />
        </div>
        <div className="min-w-0 max-w-[760px]">
          <GroupBody id={shown} info={info} touchOnly={touchOnly} />
        </div>
      </div>
    );
  }
  if (active) {
    return (
      <div className="settings-page page-x mx-auto max-w-[760px] pb-16 pt-4 sm:pt-7">
        <GroupHeader id={active} />
        <GroupBody id={active} info={info} touchOnly={touchOnly} />
      </div>
    );
  }
  return (
    <div className="settings-page page-x mx-auto max-w-[760px] pb-16 pt-6 sm:pt-9">
      <h1 className="text-2xl font-bold tracking-tight sm:text-[1.75rem]">Cài đặt</h1>
      {notices}
      <SettingsList rows={rows} className="mt-5" />
    </div>
  );
}

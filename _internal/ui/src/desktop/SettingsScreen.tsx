import { S } from "../shared/strings.generated";
import { DisclosureRow } from "@/shared/DisclosureRow";
import { MotionRegion } from "@/shared/MotionRegion";
import { MotionPresence } from "@/shared/MotionPresence";
import { SleepSchedule } from "./SleepSchedule";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FolderOpen } from "lucide-react";
import { useEffect, useState } from "react";
import { useParams } from "react-router";
import { toast } from "@/shared/toast";
import { useMediaQuery } from "@/shared/media";
import { Select, Button, Dialog, ChoiceRow, WRAP_LABEL } from "@/shared/ui";
import { ScreenHeader } from "@/shared/ScreenHeader";
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
import { PhoneSync, type SyncView } from "./PhoneSync";
import { Switch } from "./Switch";
import { checkLine, UPDATE_CHECKED_EVENT, UPDATE_CHECK_WAIT_MS, type CheckLine, type UpdateChecked } from "./updateCheck";
import { useFadeScroller } from "@/shared/scrollFade";

// Cài đặt của máy tính (chủ app 23-10: "như lạc vào ma trận"): cùng cây nhóm với điện thoại (shared/SettingsNav.tsx). Cửa sổ rộng: danh sách nhóm
// bên trái, nội dung bên phải; hẹp (trình duyệt điện thoại điều khiển từ xa): trang gốc là danh sách, mỗi nhóm một màn con như điện thoại.

const SOURCE_URL = "https://github.com/ntanhpro1221/ABook/";

/** Giọng đọc của "Nghe ngay" trên máy tính: máy chủ cục bộ (abook/readaloud) đọc, khoá của người dùng gửi trong thân yêu cầu, chỉ nhận lại bản che. */
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
  const selectClass = "w-full";
  return (
    <div className="grid gap-3 py-3 sm:grid-cols-2">
      <label htmlFor="new-book-narrator" className="block">
        <span className="block text-sm font-medium">{S.s_giong_ke_b209f686}</span>
        <Select
          id="new-book-narrator"
          className={cn(selectClass, "mt-1")}
          value={preferences?.newBookNarrator ?? ""}
          onChange={(event) => update({ newBookNarrator: event.target.value })}
        >
          <option value="">{S.s_may_de_xuat_dbeafc87}</option>
          {(voices ?? []).map((voice) => (
            <option key={voice.name} value={voice.name}>
              {voice.name} · {voice.gender}{S.s_mien_7b198286}{voice.region}
            </option>
          ))}
        </Select>
      </label>
      <label htmlFor="new-book-profile" className="block">
        <span className="block text-sm font-medium">{S.s_chat_luong_a12ed26c}</span>
        <Select
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
        </Select>
      </label>
    </div>
  );
}

// Cùng một điều khiển và cùng chữ với điện thoại (soát 24-10 T18: máy tính 3 thẻ to "Theo Windows", điện thoại segmented "Tự động").
const THEMES = [
  { value: "system", label: S.s_tu_dong_a25c8028 },
  { value: "light", label: S.s_sang_8f0c677d },
  { value: "dark", label: S.s_toi_4ac2d267 },
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
      toast(S.s_dang_tai_abook_0_app_se_tu_mo_lai_dac4d3b9(update.version), { duration: 60_000 });
    } catch (error) {
      setBusy(false);
      toast.error(S.s_chua_cap_nhat_duoc_1ceb4e4b, { description: (error as Error).message });
    }
  };
  return (
    <div className="py-3">
      <p className="text-sm">
        <span className="font-semibold">{S.s_abook_76b9d6fa}{update.version}</span>{S.s_da_co_d8cfc81f}{current ? S.s_dang_dung_0_a310b1d2(current) : ""}
      </p>
      {update.notes && <p className="mt-2 whitespace-pre-line text-[0.8125rem] leading-relaxed text-fg-2 text-pretty">{update.notes}</p>}
      <Button className="mt-3" icon={Download} disabled={busy} onClick={() => void install()}>
        {busy ? S.s_dang_tai_ban_moi_ee824efa : S.s_cap_nhat_abook_66fb9f08}
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
      label={current ? S.s_abook_0_555fc57e(current) : S.s_ban_moi_422f08ca}
      hint={<MotionRegion as="span" motionKey={line?.text ?? ""}>{line && <span className={cn(line.tone === "error" && "text-danger")} role="status">{line.text}</span>}</MotionRegion>}
    >
      <Button size="sm" variant="ghost" disabled={checking} onClick={() => void check()}>
        {checking ? S.s_dang_kiem_tra_424c43e3 : S.s_kiem_tra_ban_moi_f66eda92}
      </Button>
    </SettingsRow>
  );
}

/** Danh sách thành phần bên thứ ba (docs/THIRD_PARTY.md, gói lúc build) trong một hộp - trang Cài đặt không dài thêm. */
function ThirdPartyButton() {
  const scrollFade = useFadeScroller<HTMLDivElement>();
  const [open, setOpen] = useState(false);
  return (
    <>
      <DisclosureRow title={S.s_thanh_phan_su_dung_46f70f05} onClick={() => setOpen(true)} />
      <Dialog open={open} onOpenChange={setOpen} title={S.s_thanh_phan_su_dung_46f70f05} width="max-w-[560px]">
        <div ref={scrollFade.ref} style={scrollFade.style} className="mt-3 max-h-[65vh] select-text overflow-y-auto pr-1">{open && <ThirdPartyList />}</div>
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
          deviceHint={S.s_cai_giong_tieng_viet_tai_cai_dat_windows_t_a66056d9}
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
        <SettingsRow label={S.s_tu_lui_6fc7685a} hint={S.s_nghi_qua_30_giay_thi_lui_5_giay_qua_10_phu_328c3ffd}>
          <Switch id="auto-rewind" label={S.s_tu_lui_6fc7685a} checked={preferences?.autoRewind !== false} onCheckedChange={(value) => update({ autoRewind: value })} />
        </SettingsRow>
      </SettingsBlock>
      {/* "Nhạc của tôi" là kho chung mọi cuốn: ở đây, không chỉ trong hộp "Sửa sách" của từng cuốn. */}
      <SettingsBlock title={S.s_nhac_nen_271fb292} id="music">
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
                    toast.success(value ? S.s_da_bat_tu_chon_nhac_nen_7c51e64e : S.s_da_tat_tu_chon_nhac_nen_5489759c);
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
      <SleepSchedule />
      <SettingsRow label={S.s_moi_lan_nghe_them_9a74fcef} hint={S.s_luc_dang_nho_dan_0_69c5209a(EXTEND_GESTURE)}>
        <ChoiceRow<"5" | "10" | "15">
          label={S.s_so_phut_nghe_them_92256232}
          value={extend}
          onChange={(value) => update({ sleepExtendMinutes: Number(value) })}
          options={[
            { value: "5", label: S.s_5_phut_e98d21d5 },
            { value: "10", label: S.s_10_phut_ed33fe6a },
            { value: "15", label: S.s_15_phut_43786c01 },
          ]}
        />
      </SettingsRow>
      <SettingsRow label={S.s_nho_dan_ae8f3a2d}>
        <ChoiceRow<"10" | "30" | "60">
          label={S.s_do_dai_nho_dan_7c53ef6a}
          value={fade}
          onChange={(value) => update({ sleepFadeSeconds: Number(value) })}
          options={[
            { value: "10", label: S.s_10_giay_942f8aa9 },
            { value: "30", label: S.s_30_giay_03dbee33 },
            { value: "60", label: S.s_1_phut_eca10dbb },
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
          <SettingsRow label={S.s_mau_bf45a510}>
            <ChoiceRow label={S.s_mau_bf45a510} value={preferences?.theme ?? "system"} onChange={(theme) => update({ theme })} options={[...THEMES]} />
          </SettingsRow>
          <SettingsRow label={S.s_nen_doc_25ec1519} hint={S.s_nen_cua_chu_khi_doc_theo_d0cbef86}>
            <ChoiceRow<ReadingSurface>
              label={S.s_nen_doc_25ec1519}
              value={readingSurfaceOr(preferences?.readingSurface)}
              onChange={(readingSurface) => update({ readingSurface })}
              options={READING_SURFACES}
            />
          </SettingsRow>
          <SettingsRow label={<span id="touch-sounds-name">{S.s_am_thanh_cham_a33e2a3c}</span>} hint={<span id="touch-sounds-hint">{TOUCH_SOUNDS_HINT}</span>}>
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
        <SettingsBlock title={S.s_phim_tat_7baaed2f} id="shortcuts">
          <SettingsRow label={<span id="letter-shortcuts-name">{S.s_phim_tat_chu_f1e88b8a}</span>} hint={<span id="letter-shortcuts-hint">{LETTER_SHORTCUTS_HINT}</span>}>
            {/* Công tắc này lưu ở máy tính (PUT /api/preferences không qua Studio từ xa): ở xa thì nói đổi ở đâu thay vì để nó bấm ra 403 im lặng. */}
            {remote ? (
              <OnComputerOnly verb={S.s_doi_8f75900f} className="shrink-0" />
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
      {/* Tự dựng hai khối "Máy này" và "Máy đã ghép". */}
      <PhoneSync />
      <SettingsBlock title={S.s_may_tinh_khac_8c7c9cae} id="computers">
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
      <SettingsBlock title={S.s_mau_thiet_lap_be32f35e} id="templates">
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
      <SettingsBlock title={S.s_may_nay_4668c138} id="machine">
        <StudioSettings />
        <SettingsRow label={<span id="pause-on-battery-name">{S.s_tam_dung_dung_pin_8786ee21}</span>} hint={<span id="pause-on-battery-hint">{S.s_cam_sac_lai_thi_tu_lam_tiep_dung_cho_ce18fa7b}</span>}>
          <Switch
            id="pause-on-battery"
            labelledBy="pause-on-battery-name"
            describedBy="pause-on-battery-hint"
            checked={preferences?.pauseOnBattery !== false}
            onCheckedChange={(value) => update({ pauseOnBattery: value })}
          />
        </SettingsRow>
      </SettingsBlock>
      <MotionPresence open={!installed}><p className="mt-2 text-[0.8125rem] text-fg-2">{S.s_tuy_chon_o_trang_nay_dung_khi_da_cai_studi_f1c313c4}</p></MotionPresence>
      <SettingsBlock title={S.s_sach_moi_099947f8} fold="studio.new-book">
        <NewBookDefaults />
        <div className="py-3.5">
          <BookTemplates />
        </div>
      </SettingsBlock>
      <SettingsBlock title={S.s_cach_doc_chung_a7e00c51} fold="studio.shared-readings">
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
      const path = await pickFolder(S.s_chon_thu_muc_thu_vien_1f1d7479, preferences?.libraryRoot ?? "");
      // Báo "đã đổi" chỉ khi máy chủ đã nhận; bị từ chối thì usePreferences báo lý do (soát a100 V3).
      if (path) update({ libraryRoot: path }, { onSuccess: () => toast.success(S.s_da_doi_thu_muc_thu_vien_2d7bf6a5) });
    } catch (error) {
      toast.error((error as Error).message);
    }
  };
  return (
    <>
      <MotionPresence open={!info?.listenOnly}>
        <SettingsBlock title={S.s_thu_vien_58145555} id="library">
          <div className="settings-library-row flex flex-wrap items-center gap-2 py-3">
            <div className="flex min-h-10 min-w-0 flex-1 basis-48 items-center gap-3 text-sm text-fg-2">
              <FolderOpen className="size-4 shrink-0" />
              <span className="truncate" title={preferences?.libraryRoot}>{preferences?.libraryRoot}</span>
            </div>
            {info?.dialogs && (
              <Button size="sm" variant="ghost" className={cn("settings-edge-action touch-row", WRAP_LABEL)} onClick={() => void changeLibrary()}>{S.s_doi_thu_muc_b5c84428}</Button>
            )}
          </div>
        </SettingsBlock>
      </MotionPresence>
      {!remote && (info?.update || info?.canCheckUpdate) && (
        <SettingsBlock title={S.s_cap_nhat_5293d03c} id="update">
          <MotionRegion>{info.update ? <UpdateRow update={info.update} current={info.version} /> : <UpdateCheck current={info.version} />}</MotionRegion>
        </SettingsBlock>
      )}
      {!remote && (
        <SettingsBlock title={S.s_bo_nho_e3d4d2b2}>
          <ReadAloudStorage api={{ usage: () => httpSource.readAloudCacheTotal!(), clear: () => httpSource.readAloudCacheClearAll!() }} />
        </SettingsBlock>
      )}
      {!remote && (
        <SettingsBlock title={S.s_chan_doan_906791d5} id="diagnostics" fold="advanced.diagnostics">
          <div className="py-3.5">
            <OwnDiagnostics />
          </div>
        </SettingsBlock>
      )}
      <SettingsBlock title={S.s_gioi_thieu_0c84d33f} id="about" fold="advanced.about">
        <div className="space-y-3 py-3.5">
          <p className="text-sm text-fg-2">{S.s_abook_76b9d6fa}{info?.version}{S.s_nghe_sach_tieng_viet_va_lam_sach_noi_63eff2aa}</p>
          {/* Liên kết mở ở cửa sổ mới (target="_blank"), không điều hướng chính cửa sổ app; cửa sổ app Windows nuốt target nên openExternal nhờ máy chủ mở. */}
          <p className="select-text text-sm text-fg-2">{S.s_ma_nguon_mo_mit_d9c23b48}{" "}
            <a href={SOURCE_URL} target="_blank" rel="noopener noreferrer" onClick={(event) => openExternal(SOURCE_URL, event)} className="font-medium text-accent-text underline underline-offset-2 [overflow-wrap:anywhere]">{S.s_github_com_ntanhpro1221_abook_da672a7c}</a>
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
      {listenOnly ? S.s_bat_dieu_khien_san_xuat_tren_may_tinh_de_l_c4d48ea8 : S.s_cai_dat_chinh_nam_tren_may_tinh_dang_ket_n_cf16bd5f}
    </p>
  );
}

function useRows(groups: readonly SettingsGroupId[], info: AppInfo | undefined): GroupRow[] {
  const { data: preferences } = usePreferences();
  const voiceName = useDefaultVoiceName(desktopVoices.voices);
  const { data: sync } = useQuery({ queryKey: ["sync"], queryFn: () => api<SyncView>("/api/sync"), enabled: groups.includes("devices") });
  const summary: Record<SettingsGroupId, string | undefined> = {
    voice: voiceName,
    listen: `${preferences?.autoRewind !== false ? S.s_tu_lui_6fc7685a : S.s_khong_tu_lui_8aec206c} · ${preferences?.autoMusic !== false ? S.s_nhac_tu_chon_31bdb97d : S.s_khong_nhac_nen_0e54f623}`,
    sleep: sleepSummary(preferences?.sleepSchedule),
    look: info?.remote ? S.s_phim_tat_7baaed2f : themeSummary(preferences?.theme, S.s_tu_dong_a25c8028),
    devices: sync ? (sync.enabled ? S.s_0_thiet_bi_da_ghep_2fe2b8a5(sync.devices.length) : S.s_dang_tat_53bfa8b7) : undefined,
    studio: info?.remote ? S.s_mau_thiet_lap_be32f35e : info?.studio?.installed ? S.s_da_cai_e0159635 : S.s_chua_cai_17f9d6d7,
    advanced: info?.update && !info.remote ? S.s_co_ban_moi_0_f7b3885a(info.update.version) : info?.version ? S.s_phien_ban_0_164b4cda(info.version) : undefined,
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
        <DisclosureRow to={settingsPath("advanced")} className="mt-4" title={S.s_co_abook_0_6e3b5a77(info.update.version)} icon={<Download className="size-5 text-accent-text" />} />
      )}</MotionPresence>
    </>
  );
  if (wide) {
    // Hai cột: /settings mở sẵn nhóm đầu; đổi nhóm thay chỗ trong lịch sử như đổi tab. Hai tiêu đề khác cỡ chung một hàng lưới,
    // canh theo chân chữ (canh đỉnh để chân chữ lệch 3 px).
    const shown = active ?? groups[0];
    return (
      <div className="settings-page page-x mx-auto grid max-w-[1180px] grid-cols-[260px_minmax(0,1fr)] gap-x-8 pb-16">
        <ScreenHeader title={S.s_cai_dat_202e0e9b} className="self-baseline" />
        <div className="min-w-0 self-baseline">
          <GroupHeader id={shown} back={false} />
        </div>
        <div>
          {notices}
          <SettingsList rows={rows} current={shown} className="mt-5" />
        </div>
        <div className="min-w-0">
          <GroupBody id={shown} info={info} touchOnly={touchOnly} />
        </div>
      </div>
    );
  }
  if (active) {
    return (
      <div className="settings-page page-x mx-auto max-w-[760px] pb-16">
        <GroupHeader id={active} />
        <GroupBody id={active} info={info} touchOnly={touchOnly} />
      </div>
    );
  }
  return (
    <div className="settings-page page-x mx-auto max-w-[760px] pb-16">
      <ScreenHeader title={S.s_cai_dat_202e0e9b} />
      {notices}
      <SettingsList rows={rows} className="mt-5" />
    </div>
  );
}

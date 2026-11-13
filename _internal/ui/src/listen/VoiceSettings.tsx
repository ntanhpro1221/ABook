import { S } from "../shared/strings.generated";
import { DisclosureRow } from "@/shared/DisclosureRow";
import { MotionRegion } from "@/shared/MotionRegion";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Play, Square, Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Button, radioGroupKeys, radioTabIndex, ContentSkeleton, InlineError, SelectionMark } from "@/shared/ui";
import { MoreInfo } from "@/shared/SettingsNav";
import { Collapse, Fold, useFold } from "@/shared/Collapse";
import { cn } from "@/shared/cn";
import type { ReadAloudVoice } from "./readAloud";
import {
  DEFAULT_VOICE_EVENT,
  ONLINE_KEYS_CHANGED_EVENT,
  ONLINE_NOTICE,
  SAMPLE_TEXT,
  chooseDefaultVoice,
  defaultVoice,
  onlineNotice,
  resolveVoice,
} from "./readAloudVoice";
import { genderLabel, groupLabel, VOICE_GROUPS, voiceSections } from "./voiceGroups";
import { spokenVoiceName } from "./onlineConsent";

// Cài đặt › Giọng đọc (máy tính và điện thoại dùng chung): giọng mặc định của "Nghe ngay", nghe thử từng giọng, gợi ý giọng nam / nữ, câu nói
// rõ chữ của sách đi đâu với từng nhóm giọng trực tuyến, và phần gập "Khoá riêng" (nhập khoá, Kiểm tra, Xoá) ở cuối. Mỗi nền tảng
// đưa vào một `VoiceSettingsApi` (máy tính: máy chủ cục bộ abook/readaloud; điện thoại: plugin ReadAloud). Bộ nhớ bản đọc nằm ở Cài đặt › Nâng cao.

/** Một nhà cung cấp giọng dùng khoá riêng như máy chủ / lõi điện thoại mô tả (abook/readaloud/byok.py `describe`, OnlineVoices.kt). */
export interface OnlineProviderInfo {
  id: string;
  name: string;
  limits: { max_chars: number; free: string; timings: "exact" | "estimated"; region: boolean };
  hasKey: boolean;
  /** "••••abcd": đủ để nhận ra khoá nào, không bao giờ là khoá thật. */
  masked: string;
  region: string;
  valid: boolean;
  voices: number;
}

export interface KeyCheck {
  ok: boolean;
  reason?: string;
  message?: string;
  voices?: number;
  provider: OnlineProviderInfo;
}

export interface VoiceSettingsApi {
  voices(): Promise<ReadAloudVoice[]>;
  /** Đọc `SAMPLE_TEXT` bằng giọng này, trả địa chỉ phát được. */
  sample(voiceId: string, text: string): Promise<string>;
  online(): Promise<OnlineProviderInfo[]>;
  saveKey(provider: string, key: string, region: string): Promise<OnlineProviderInfo>;
  removeKey(provider: string): Promise<OnlineProviderInfo>;
  checkKey(provider: string): Promise<KeyCheck>;
}

/** Lấy khoá ở đâu - nói theo những gì người dùng thấy trên trang của nhà cung cấp. */
const KEY_HELP: Record<string, string> = {
  azure: S.s_azure_tao_speech_f0_mien_phi_keys_and_endp_13c271d5,
  google: S.s_google_cloud_bat_cloud_text_to_speech_api_6c11e0dc,
  fpt: S.s_tren_console_fpt_ai_dang_nhap_mo_muc_text_4010b0be,
  viettel: S.s_tren_viettelai_vn_dang_nhap_mo_tai_khoan_t_0f2b04ac,
};

function muted(): boolean {
  // ?mute=1: kiểm thử tự động không được phát tiếng ra loa của người dùng (như engine.ts, musicBed.ts).
  return typeof window !== "undefined" && new URLSearchParams(window.location.search).get("mute") === "1";
}

/** Câu lỗi cho bạn: lời của lõi, không có thì câu theo việc - cùng lời bên native (VoiceRepo.kt). */
function errorText(error: unknown, fallback: string): string {
  return (error as Error)?.message || fallback;
}

/** Nghe thử giọng: Cài đặt › Giọng đọc và menu giọng của trình phát dùng chung. `sample`: đọc câu mẫu bằng giọng ấy, trả địa chỉ phát được.
 *  Mỗi lần bấm "Nghe thử" / "Dừng" là một lượt mới: mẫu của lượt cũ về muộn (lấy mẫu mất vài giây) bị bỏ, không phát chồng lên giọng bấm sau, không tự phát sau khi đã bấm dừng. */
export function useVoiceSample(sample: (voiceId: string, text: string) => Promise<string>) {
  const audio = useRef<HTMLAudioElement | null>(null);
  const turn = useRef(0);
  const [playing, setPlaying] = useState("");
  const [loading, setLoading] = useState("");
  const [failed, setFailed] = useState<{ voice: string; message: string } | null>(null);
  const stop = useCallback(() => {
    turn.current += 1;
    audio.current?.pause();
    audio.current = null;
    setPlaying("");
    setLoading(""); // đang lấy mẫu mà bấm dừng: lượt ấy bị bỏ nên không còn ai tắt dấu "đang lấy"
  }, []);
  useEffect(() => stop, [stop]);
  const play = async (voice: string) => {
    stop();
    const mine = turn.current;
    setFailed(null);
    setLoading(voice);
    try {
      const url = await sample(voice, SAMPLE_TEXT);
      if (turn.current !== mine) return;
      const element = new Audio(url);
      element.muted = muted();
      element.onended = () => setPlaying((current) => (current === voice ? "" : current));
      audio.current = element;
      setPlaying(voice);
      await element.play();
    } catch (error) {
      if (turn.current !== mine) return; // lượt cũ: lỗi của nó không còn ai chờ
      setPlaying("");
      setFailed({ voice, message: errorText(error, S.s_chua_nghe_thu_duoc_giong_nay_baf64b64) });
    } finally {
      if (turn.current === mine) setLoading("");
    }
  };
  return { playing, loading, failed, play, stop };
}

/** Dòng tóm tắt của "Khoá trực tuyến": tên các nhà cung cấp đã có khoá, hay "Chưa có khoá" (VoiceText.keySummary bên native). */
function keySummary(providers: OnlineProviderInfo[]): string {
  return providers.filter((info) => info.hasKey).map((info) => info.name).join(" · ") || S.s_chua_co_khoa_fce87985;
}

function KeyCard({ info, api, onChanged }: { info: OnlineProviderInfo; api: VoiceSettingsApi; onChanged: () => void }) {
  const [key, setKey] = useState("");
  const [region, setRegion] = useState(info.region);
  const [busy, setBusy] = useState<"" | "check" | "save" | "remove">("");
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);
  // Gập sẵn (soát UX 05-10: bốn khung dài chiếm hơn nửa Cài đặt trên điện thoại); đã có khoá thì mở sẵn để thấy trạng thái.
  const [open, setOpen] = useState(info.hasKey);
  useEffect(() => setRegion(info.region), [info.region]);
  const regionChanged = Boolean(info.limits.region) && region.trim() !== info.region;
  // "Lưu" chỉ cất khoá trên máy này, không gửi gì ra mạng; "Kiểm tra" mới gọi dịch vụ (và cũng lưu khoá đang gõ trước khi kiểm).
  const save = async () => {
    setBusy("save");
    setResult(null);
    try {
      if (!key.trim() && !info.hasKey) throw new Error(S.s_dan_khoa_truoc_da_d88da35d);
      await api.saveKey(info.id, key.trim(), region.trim());
      setKey("");
      setResult({ ok: true, text: S.s_da_luu_khoa_bam_kiem_tra_de_thu_a21b7359 });
    } catch (error) {
      setResult({ ok: false, text: errorText(error, S.s_chua_luu_duoc_khoa_96a2395d) });
    } finally {
      setBusy("");
      onChanged();
    }
  };
  const check = async () => {
    setBusy("check");
    setResult(null);
    try {
      if (key.trim() || (info.limits.region && region.trim() !== info.region)) {
        if (!key.trim() && !info.hasKey) throw new Error(S.s_dan_khoa_truoc_da_d88da35d);
        await api.saveKey(info.id, key.trim() || "", region.trim());
      }
      const checked = await api.checkKey(info.id);
      setKey("");
      setResult(checked.ok
        ? { ok: true, text: S.s_dung_duoc_0_giong_tieng_viet_8d3747da(checked.voices ?? checked.provider.voices) }
        : { ok: false, text: checked.message || S.s_khoa_chua_dung_duoc_2ae17f08 });
    } catch (error) {
      setResult({ ok: false, text: errorText(error, S.s_chua_kiem_tra_duoc_khoa_dba470e0) });
    } finally {
      setBusy("");
      onChanged();
    }
  };
  const remove = async () => {
    setBusy("remove");
    try {
      await api.removeKey(info.id);
      setResult(null);
      setKey("");
    } catch (error) {
      setResult({ ok: false, text: errorText(error, S.s_chua_xoa_duoc_khoa_2df56367) });
    } finally {
      setBusy("");
      onChanged();
    }
  };
  const status = info.valid ? S.s_dung_duoc_0_giong_ddbd60b5(info.voices) : info.hasKey ? S.s_chua_dung_duoc_c68b3845 : undefined;
  return (
    <MotionRegion as="div" className="py-3" data-provider={info.id}>
      <DisclosureRow title={info.name} summary={status} expanded={open} onClick={() => setOpen((now) => !now)} />
      <Collapse open={open}>
      <p className="mt-1 text-body-small text-fg-2 text-pretty">
        {info.limits.free}. {info.limits.timings === "exact" ? S.s_to_dung_tung_chu_dang_doc_b0692da6 : S.s_to_tung_chu_dang_doc_theo_uoc_luong_b0de406b}
      </p>
      <MoreInfo label={S.s_nhan_khoa_7ba3a705} className="mt-1">{KEY_HELP[info.id]}</MoreInfo>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <label className="min-w-0 flex-1 basis-56">
          <span className="sr-only">{S.s_khoa_0_7f56ecc3(info.name)}</span>
          <input
            type="password"
            autoComplete="off"
            spellCheck={false}
            value={key}
            onChange={(event) => setKey(event.target.value)}
            placeholder={info.hasKey ? S.s_da_luu_0_dan_khoa_moi_de_thay_1b8b024d(info.masked) : S.s_dan_khoa_cua_ban_c390a2e9}
            className="h-9 w-full rounded-control border border-line bg-panel px-3 text-sm"
          />
        </label>
        {info.limits.region && (
          <label className="w-48 shrink-0">
            <span className="sr-only">{S.s_vung_0dec5e2e}{info.name}</span>
            <input
              value={region}
              onChange={(event) => setRegion(event.target.value)}
              placeholder={S.s_vung_vi_du_southeastasia_959965a2}
              spellCheck={false}
              className="h-9 w-full rounded-control border border-line bg-panel px-3 text-sm"
            />
          </label>
        )}
        <Button size="md" variant="ghost" loading={busy === "save"} disabled={Boolean(busy) || (!key.trim() && !regionChanged)} onClick={() => void save()}>{S.s_luu_e91f26c0}</Button>
        <Button size="md" icon={KeyRound} loading={busy === "check"} disabled={Boolean(busy) || (!info.hasKey && !key.trim())} onClick={() => void check()}>{S.s_kiem_tra_ff6e2891}</Button>
        {info.hasKey && (
          <Button size="md" variant="ghost" icon={Trash2} loading={busy === "remove"} disabled={Boolean(busy)} onClick={() => void remove()}>{S.s_xoa_khoa_2ec6cb1a}</Button>
        )}
      </div>
      {result && <p className={cn("mt-2 text-body-small text-pretty", result.ok ? "text-success" : "text-danger")} role="status">{result.text}</p>}
      </Collapse>
    </MotionRegion>
  );
}

/** Tên giọng mặc định cho dòng tóm tắt ở trang gốc Cài đặt ("Hoài My"); "" khi máy chưa báo giọng nào. */
export function useDefaultVoiceName(list: () => Promise<ReadAloudVoice[]>): string {
  const { data } = useQuery({ queryKey: ["readaloud", "voices"], queryFn: list, staleTime: 60_000 });
  const [chosen, setChosen] = useState(defaultVoice);
  useEffect(() => {
    const changed = () => setChosen(defaultVoice());
    window.addEventListener(DEFAULT_VOICE_EVENT, changed);
    return () => window.removeEventListener(DEFAULT_VOICE_EVENT, changed);
  }, []);
  const voice = data?.length ? resolveVoice(data, chosen) : undefined;
  return voice ? spokenVoiceName(voice.name) : "";
}

/** Mục "Giọng đọc" của Cài đặt. `deviceHint`: câu cho khi máy chưa có giọng tiếng Việt của hệ điều hành (mỗi nền tảng cài theo cách riêng) - dòng
 *  phụ dưới các giọng tải được trong app. */
/** `modules`: phần tải thêm giọng của nền tảng (máy tính: thẻ "Giọng VieNeu" và "Giọng Supertonic" - VieneuModuleCard), nhận `reload` để danh sách giọng hỏi lại khi
 *  giọng mới vừa tải xong. */
export function VoiceSettings({ api, deviceHint, modules }: { api: VoiceSettingsApi; deviceHint: string; modules?: (reload: () => void) => ReactNode }) {
  const client = useQueryClient();
  const [voices, setVoices] = useState<ReadAloudVoice[] | null>(null);
  const [providers, setProviders] = useState<OnlineProviderInfo[]>([]);
  const [chosen, setChosen] = useState(defaultVoice);
  const [loadError, setLoadError] = useState("");
  const [keysOpen, setKeysOpen] = useFold("voice.keys");
  const sample = useVoiceSample(api.sample);
  const load = useCallback(async () => {
    try {
      const [listed, online] = await Promise.all([api.voices(), api.online().catch(() => [] as OnlineProviderInfo[])]);
      setVoices(listed);
      setProviders(online);
      setLoadError("");
    } catch (error) {
      setLoadError(errorText(error, S.s_chua_tai_duoc_giong_728a140d));
    }
  }, [api]);
  useEffect(() => void load(), [load]);
  const keysChanged = () => {
    // Danh sách giọng của trình phát (readAloudVoice.voicesOf, useReadAloudVoices) hỏi lại: giọng của khoá vừa kiểm tra hiện / ẩn ngay.
    window.dispatchEvent(new CustomEvent(ONLINE_KEYS_CHANGED_EVENT));
    void client.invalidateQueries({ queryKey: ["readaloud", "voices"] });
    void load();
  };
  const current = voices?.length ? resolveVoice(voices, chosen) : undefined;
  // Máy chưa có giọng tiếng Việt của hệ điều hành: nhóm "Giọng của máy" mở đầu bằng các giọng tải được ngay trong app (thẻ `modules`), câu cài
  // giọng của Windows / điện thoại thành dòng phụ - không còn là đường duy nhất để nghe không cần mạng (soát a64).
  const keysShown = keysOpen;

  return (
    <MotionRegion as="div" className="grid grid-cols-[minmax(0,1fr)] gap-5">
      <InlineError open={Boolean(loadError)} message={S.s_ban_hay_kiem_tra_ket_noi_roi_tai_lai_giong_46330dab} onRetry={() => void load()} />
      {current && <p className="text-sm font-medium">{S.s_dang_dung_0_b3abfb1e(current.name)}</p>}
      {voices === null && !loadError && <ContentSkeleton label={S.s_dang_tai_giong_doc_ac8359a5} />}
      {voices &&
        VOICE_GROUPS.map(({ provider, title: heading, detail }) => {
          const list = voices.filter((voice) => voice.provider === provider);
          if (!list.length && provider !== "device") return null;
          const notice = provider === "edge" ? ONLINE_NOTICE : list[0] ? onlineNotice(list[0]) : "";
          // Thứ tự giọng như hiển thị (theo mục): mũi tên đổi chọn, cả nhóm chỉ một điểm dừng Tab (giọng đang chọn, hay giọng đầu nếu
          // giọng mặc định nằm ở nhóm khác). Nút "Nghe thử" chỉ vào vòng Tab ở đúng giọng ấy - 27 giọng không thành 27 điểm Tab.
          const ids = voiceSections(list).flatMap((section) => section.voices.map(({ voice }) => voice.id));
          return (
            <Fold key={provider} storageKey={`voice.provider.${provider}`} title={heading} summary={S.s_0_1_giong_2_8057303d(detail ? `${detail} · ` : "", list.length, current?.provider === provider ? S.s_dang_dung_b8df7fc3 : "")} bodyClassName="pb-3">
              {/* Thẻ tải giọng và dòng gợi ý đứng NGOÀI nhóm radio: nhóm giọng rỗng không được nhận phím của thẻ tốc độ nằm trong nó (soát a100 V1). */}
              {!list.length && <p className={cn("text-pretty", "py-1 text-body-small text-fg-2")}>{deviceHint}</p>}
              {list.length > 0 && (
              <div
                role="radiogroup"
                aria-label={groupLabel({ title: heading, detail })}
                onKeyDown={radioGroupKeys(ids, current?.id ?? "", (id) => {
                  chooseDefaultVoice(id);
                  setChosen(id);
                })}
              >
              {voiceSections(list).map((section) => (
                <div key={section.label ?? ""}>
                  {section.label && <div className="mb-1 mt-2 text-body-small font-medium text-fg-2">{section.label}</div>}
                  <ul className="divide-y divide-line">
                    {section.voices.map(({ voice, shown }) => {
                      const selected = voice.id === current?.id;
                      const playing = sample.playing === voice.id;
                      return (
                        <li key={voice.id} className="py-2">
                          <div className="flex items-center gap-3">
                          <button
                            type="button"
                            role="radio"
                            aria-checked={selected}
                            tabIndex={radioTabIndex(ids, current?.id ?? "", ids.indexOf(voice.id))}
                            onClick={() => {
                              chooseDefaultVoice(voice.id);
                              setChosen(voice.id);
                            }}
                            className="touch-row flex min-w-0 flex-1 items-center gap-3 text-left"
                          >
                            <span className="flex size-5 shrink-0 text-accent-text">
                              <SelectionMark selected={selected} className="ink-start [--icon-w:17.5px] size-5" />
                            </span>
                            <span className="min-w-0 text-pretty text-sm font-medium [overflow-wrap:anywhere]">{shown}</span>
                            {genderLabel(voice.gender) && <span className="shrink-0 text-xs text-fg-2">{genderLabel(voice.gender)}</span>}
                            {selected && <span className="shrink-0 text-xs text-accent-text">{S.s_mac_dinh_9a1af367}</span>}
                          </button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="touch-row settings-edge-action"
                            tabIndex={radioTabIndex(ids, current?.id ?? "", ids.indexOf(voice.id))}
                            icon={playing ? Square : Play}
                            loading={sample.loading === voice.id}
                            onClick={() => (playing ? sample.stop() : void sample.play(voice.id))}
                            aria-label={playing ? S.s_dung_nghe_thu_0_c63198da(voice.name) : S.s_nghe_thu_0_65a85c4d(voice.name)}
                          >
                            {playing ? S.s_dung_11554138 : S.s_nghe_thu_fa024065}
                          </Button>
                          </div>
                          {/* Lỗi nghe thử nằm ngay dưới hàng giọng vừa bấm, không ở cuối cả nhóm. */}
                          {sample.failed?.voice === voice.id && (
                            <p className="mt-1 text-body-small text-danger text-pretty" role="alert">{sample.failed.message}</p>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
              </div>
              )}
              {notice && list.length > 0 && <p className="mt-1 text-xs text-fg-2 text-pretty">{notice}</p>}
            </Fold>
          );
        })}
      {modules && modules(() => void load())}
      {providers.length > 0 && (
        <div>
          {/* Hiếm dùng: gấp sẵn, nhớ lựa chọn; số khoá luôn thấy ở đầu mục. */}
          <DisclosureRow section title={S.s_khoa_truc_tuyen_b32d4988} summary={keySummary(providers)} expanded={keysShown} onClick={() => setKeysOpen(!keysOpen)} />
          <Collapse open={keysShown}>
              <MoreInfo className="mt-1">{S.s_khoa_chi_luu_tren_may_dich_vu_co_the_tinh_a894acea}</MoreInfo>
              <div className="mt-3 grid gap-3">
                {providers.map((info) => (
                  <KeyCard key={info.id} info={info} api={api} onChanged={keysChanged} />
                ))}
              </div>
          </Collapse>
        </div>
      )}
    </MotionRegion>
  );
}

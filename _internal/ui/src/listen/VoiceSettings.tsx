import { useQueryClient } from "@tanstack/react-query";
import { Check, ChevronDown, KeyRound, Play, Square, Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Button, StatusPill, radioGroupKeys, radioTabIndex } from "@/shared/ui";
import { cn } from "@/shared/cn";
import type { ReadAloudVoice } from "./readAloud";
import {
  ONLINE_KEYS_CHANGED_EVENT,
  ONLINE_NOTICE,
  SAMPLE_TEXT,
  chooseDefaultVoice,
  defaultVoice,
  onlineNotice,
  resolveVoice,
} from "./readAloudVoice";
import { genderLabel, VOICE_GROUPS, voiceSections } from "./voiceGroups";

// Cài đặt → "Giọng đọc" (máy tính và điện thoại dùng chung): giọng mặc định của "Nghe ngay", nghe thử từng giọng, gợi ý giọng nam / nữ, câu nói
// rõ chữ của sách đi đâu với từng nhóm giọng trực tuyến, và mục "Giọng trực tuyến dùng khóa của bạn" (nhập khóa, Kiểm tra, Xóa). Mỗi nền tảng
// đưa vào một `VoiceSettingsApi` (máy tính: máy chủ cục bộ abook/readaloud; điện thoại: plugin ReadAloud).

/** Một nhà cung cấp giọng dùng khoá riêng như máy chủ / lõi điện thoại mô tả (abook/readaloud/byok.py `describe`, OnlineVoices.kt). */
export interface OnlineProviderInfo {
  id: string;
  name: string;
  limits: { max_chars: number; free: string; timings: "exact" | "estimated"; region: boolean };
  hasKey: boolean;
  /** "••••abcd": đủ để nhận ra khóa nào, không bao giờ là khóa thật. */
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

/** Lấy khóa ở đâu - nói theo những gì người dùng thấy trên trang của nhà cung cấp. */
const KEY_HELP: Record<string, string> = {
  azure: "Trên Azure: tạo tài nguyên Speech (bậc F0 miễn phí), mở mục “Keys and Endpoint” (Khoá và địa chỉ), chép “Key 1” (Khoá 1) và “Location/Region” (Vùng, ví dụ southeastasia).",
  google: "Trên Google Cloud: bật “Cloud Text-to-Speech API” (dịch vụ đọc văn bản), rồi vào “APIs & Services” (API và dịch vụ) › “Credentials” (Thông tin xác thực) › “Create credentials” (Tạo thông tin xác thực) › “API key” (Khoá API).",
  fpt: "Trên console.fpt.ai: đăng nhập, mở mục “Text to Speech” (Chuyển văn bản thành giọng nói), chép “API key” (khoá API).",
  viettel: "Trên viettelai.vn: đăng nhập, mở Tài khoản › Token, chép token.",
};

function muted(): boolean {
  // ?mute=1: kiểm thử tự động không được phát tiếng ra loa của người dùng (như engine.ts, musicBed.ts).
  return typeof window !== "undefined" && new URLSearchParams(window.location.search).get("mute") === "1";
}

function errorText(error: unknown): string {
  return (error as Error)?.message || "Không làm được lúc này.";
}

/** Nghe thử giọng: Cài đặt › Giọng đọc và menu giọng của trình phát dùng chung. `sample`: đọc câu mẫu bằng giọng ấy, trả địa chỉ phát được. */
export function useVoiceSample(sample: (voiceId: string, text: string) => Promise<string>) {
  const audio = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState("");
  const [loading, setLoading] = useState("");
  const [failed, setFailed] = useState<{ voice: string; message: string } | null>(null);
  const stop = useCallback(() => {
    audio.current?.pause();
    audio.current = null;
    setPlaying("");
  }, []);
  useEffect(() => stop, [stop]);
  const play = async (voice: string) => {
    stop();
    setFailed(null);
    setLoading(voice);
    try {
      const url = await sample(voice, SAMPLE_TEXT);
      const element = new Audio(url);
      element.muted = muted();
      element.onended = () => setPlaying((current) => (current === voice ? "" : current));
      audio.current = element;
      setPlaying(voice);
      await element.play();
    } catch (error) {
      setPlaying("");
      setFailed({ voice, message: errorText(error) });
    } finally {
      setLoading("");
    }
  };
  return { playing, loading, failed, play, stop };
}

function KeyCard({ info, api, onChanged }: { info: OnlineProviderInfo; api: VoiceSettingsApi; onChanged: () => void }) {
  const [key, setKey] = useState("");
  const [region, setRegion] = useState(info.region);
  const [busy, setBusy] = useState<"" | "check" | "save" | "remove">("");
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);
  // Gập sẵn (soát UX 05-10: bốn khung dài chiếm hơn nửa Cài đặt trên điện thoại); đã có khóa thì mở sẵn để thấy trạng thái.
  const [open, setOpen] = useState(info.hasKey);
  useEffect(() => setRegion(info.region), [info.region]);
  const regionChanged = Boolean(info.limits.region) && region.trim() !== info.region;
  // "Lưu" chỉ cất khóa trên máy này, không gửi gì ra mạng; "Kiểm tra" mới gọi dịch vụ (và cũng lưu khóa đang gõ trước khi kiểm).
  const save = async () => {
    setBusy("save");
    setResult(null);
    try {
      if (!key.trim() && !info.hasKey) throw new Error("Dán khóa trước đã.");
      await api.saveKey(info.id, key.trim(), region.trim());
      setKey("");
      setResult({ ok: true, text: "Đã lưu khóa trên máy này. Chưa kiểm tra - bấm “Kiểm tra” khi muốn biết dùng được chưa." });
    } catch (error) {
      setResult({ ok: false, text: errorText(error) });
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
        if (!key.trim() && !info.hasKey) throw new Error("Dán khóa trước đã.");
        await api.saveKey(info.id, key.trim() || "", region.trim());
      }
      const checked = await api.checkKey(info.id);
      setKey("");
      setResult(checked.ok
        ? { ok: true, text: `Dùng được - ${checked.voices ?? checked.provider.voices} giọng tiếng Việt đã hiện trong danh sách giọng.` }
        : { ok: false, text: checked.message || "Khóa chưa dùng được." });
    } catch (error) {
      setResult({ ok: false, text: errorText(error) });
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
      setResult({ ok: false, text: errorText(error) });
    } finally {
      setBusy("");
      onChanged();
    }
  };
  const status = info.valid ? <StatusPill tone="success" label={`Dùng được · ${info.voices} giọng`} /> : info.hasKey ? <StatusPill tone="warning" label="Chưa dùng được" /> : null;
  return (
    <div className="rounded-xl border border-line p-3.5" data-provider={info.id}>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((now) => !now)}
        className="touch-hit flex w-full flex-wrap items-center justify-between gap-2 text-left"
      >
        <span className="flex items-center gap-1.5 text-sm font-semibold">
          <ChevronDown className={cn("size-4 shrink-0 text-fg-3 transition-transform", !open && "-rotate-90")} aria-hidden />
          {info.name}
        </span>
        {status}
      </button>
      {open && <div>
      <p className="mt-1 text-[13px] text-fg-2 text-pretty">
        {info.limits.free}. {info.limits.timings === "exact" ? "Tô đúng từng chữ đang đọc." : "Tô từng chữ đang đọc theo ước lượng."}
      </p>
      <p className="mt-1 text-xs text-fg-3 text-pretty">{KEY_HELP[info.id]}</p>
      <div className="mt-2.5 flex flex-wrap items-center gap-2">
        <label className="min-w-0 flex-1 basis-56">
          <span className="sr-only">Khóa {info.name}</span>
          <input
            type="password"
            autoComplete="off"
            spellCheck={false}
            value={key}
            onChange={(event) => setKey(event.target.value)}
            placeholder={info.hasKey ? `Đã lưu ${info.masked} - dán khóa mới để thay` : "Dán khóa của bạn"}
            className="h-9 w-full rounded-lg border border-line bg-panel px-3 text-sm"
          />
        </label>
        {info.limits.region && (
          <label className="w-48 shrink-0">
            <span className="sr-only">Vùng {info.name}</span>
            <input
              value={region}
              onChange={(event) => setRegion(event.target.value)}
              placeholder="Vùng, ví dụ southeastasia"
              spellCheck={false}
              className="h-9 w-full rounded-lg border border-line bg-panel px-3 text-sm"
            />
          </label>
        )}
        <Button size="md" variant="outline" loading={busy === "save"} disabled={Boolean(busy) || (!key.trim() && !regionChanged)} onClick={() => void save()}>
          Lưu
        </Button>
        <Button size="md" icon={KeyRound} loading={busy === "check"} disabled={Boolean(busy) || (!info.hasKey && !key.trim())} onClick={() => void check()}>
          Kiểm tra
        </Button>
        {info.hasKey && (
          <Button size="md" variant="ghost" icon={Trash2} loading={busy === "remove"} disabled={Boolean(busy)} onClick={() => void remove()}>
            Xóa khóa
          </Button>
        )}
      </div>
      {result && <p className={cn("mt-2 text-[13px] text-pretty", result.ok ? "text-success" : "text-danger")} role="status">{result.text}</p>}
      </div>}
    </div>
  );
}

/** Mục "Giọng đọc" của Cài đặt. `deviceHint`: câu cho khi máy chưa có giọng tiếng Việt (mỗi nền tảng cài theo cách riêng). */
/** `modules`: phần tải thêm giọng của nền tảng (máy tính: thẻ "Giọng VieNeu" và "Giọng Supertonic" - VieneuModuleCard), nhận `reload` để danh sách giọng hỏi lại khi
 *  giọng mới vừa tải xong. */
export function VoiceSettings({ api, deviceHint, modules }: { api: VoiceSettingsApi; deviceHint: string; modules?: (reload: () => void) => ReactNode }) {
  const client = useQueryClient();
  const [voices, setVoices] = useState<ReadAloudVoice[] | null>(null);
  const [providers, setProviders] = useState<OnlineProviderInfo[]>([]);
  const [chosen, setChosen] = useState(defaultVoice);
  const [loadError, setLoadError] = useState("");
  const sample = useVoiceSample(api.sample);
  const load = useCallback(async () => {
    try {
      const [listed, online] = await Promise.all([api.voices(), api.online().catch(() => [] as OnlineProviderInfo[])]);
      setVoices(listed);
      setProviders(online);
      setLoadError("");
    } catch (error) {
      setVoices([]);
      setLoadError(errorText(error));
    }
  }, [api]);
  useEffect(() => void load(), [load]);
  const keysChanged = () => {
    // Danh sách giọng của trình phát (readAloudVoice.voicesOf, useReadAloudVoices) hỏi lại: giọng của khóa vừa kiểm tra hiện / ẩn ngay.
    window.dispatchEvent(new CustomEvent(ONLINE_KEYS_CHANGED_EVENT));
    void client.invalidateQueries({ queryKey: ["readaloud", "voices"] });
    void load();
  };
  const current = voices?.length ? resolveVoice(voices, chosen) : undefined;
  return (
    <div className="grid gap-5">
      {loadError && <p className="text-[13px] text-danger">{loadError}</p>}
      {voices === null && <p className="text-[13px] text-fg-2">Đang tìm các giọng…</p>}
      {voices &&
        VOICE_GROUPS.map(({ provider, title }) => {
          const list = voices.filter((voice) => voice.provider === provider);
          if (!list.length && provider !== "device") return null;
          const notice = provider === "edge" ? ONLINE_NOTICE : list[0] ? onlineNotice(list[0]) : "";
          // Thứ tự giọng như hiển thị (theo mục): mũi tên đổi chọn, cả nhóm chỉ một điểm dừng Tab (giọng đang chọn, hay giọng đầu nếu
          // giọng mặc định nằm ở nhóm khác). Nút "Thử giọng" chỉ vào vòng Tab ở đúng giọng ấy - 27 giọng không thành 27 điểm Tab.
          const ids = voiceSections(list).flatMap((section) => section.voices.map(({ voice }) => voice.id));
          return (
            <div
              key={provider}
              role="radiogroup"
              aria-label={title}
              onKeyDown={radioGroupKeys(ids, current?.id ?? "", (id) => {
                chooseDefaultVoice(id);
                setChosen(id);
              })}
            >
              <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-fg-3">{title}</div>
              {!list.length && <p className="py-1 text-[13px] text-fg-2 text-pretty">{deviceHint}</p>}
              {voiceSections(list).map((section) => (
                <div key={section.label ?? ""}>
                  {section.label && <div className="mb-0.5 mt-2 text-[13px] font-medium text-fg-2">{section.label}</div>}
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
                            className="touch-row flex min-w-0 flex-1 items-center gap-2.5 text-left"
                          >
                            <span className={cn("grid size-5 shrink-0 place-items-center rounded-full border", selected ? "border-accent bg-accent text-accent-ink" : "border-line-strong")}>
                              {selected && <Check className="size-3" strokeWidth={3} />}
                            </span>
                            <span className="min-w-0 truncate text-sm font-medium">{shown}</span>
                            {genderLabel(voice.gender) && <span className="shrink-0 text-xs text-fg-2">{genderLabel(voice.gender)}</span>}
                            {selected && <span className="shrink-0 text-xs text-accent-text">Mặc định</span>}
                          </button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="touch-row"
                            tabIndex={radioTabIndex(ids, current?.id ?? "", ids.indexOf(voice.id))}
                            icon={playing ? Square : Play}
                            loading={sample.loading === voice.id}
                            onClick={() => (playing ? sample.stop() : void sample.play(voice.id))}
                            aria-label={`${playing ? "Dừng" : "Thử"} giọng ${voice.name}`}
                          >
                            {playing ? "Dừng" : "Thử giọng"}
                          </Button>
                          </div>
                          {/* Lỗi nghe thử nằm ngay dưới hàng giọng vừa bấm, không ở cuối cả nhóm. */}
                          {sample.failed?.voice === voice.id && (
                            <p className="mt-1 text-[13px] text-danger text-pretty" role="alert">{sample.failed.message}</p>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
              {notice && list.length > 0 && <p className="mt-1 text-xs text-fg-2 text-pretty">{notice}</p>}
            </div>
          );
        })}
      {modules?.(() => void load())}
      {providers.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold">Giọng trực tuyến dùng khóa của bạn</h3>
          <p className="mt-1 text-[13px] text-fg-2 text-pretty">
            Có tài khoản ở một trong các dịch vụ dưới đây thì dán khóa vào để dùng giọng của họ. Khi đọc, chữ của sách được gửi tới dịch vụ đó, và
            dịch vụ có thể tính tiền vào tài khoản của bạn khi vượt phần miễn phí. Khóa chỉ lưu trên máy này. Khóa hết hạn mức hay bị từ chối thì
            đoạn ấy tạm đọc bằng giọng Edge hoặc giọng của máy, không dừng.
          </p>
          <div className="mt-3 grid gap-3">
            {providers.map((info) => (
              <KeyCard key={info.id} info={info} api={api} onChanged={keysChanged} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

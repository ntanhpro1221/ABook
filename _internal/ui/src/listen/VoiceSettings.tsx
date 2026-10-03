import { useQueryClient } from "@tanstack/react-query";
import { Check, KeyRound, Play, Square, Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button, StatusPill } from "@/shared/ui";
import { cn } from "@/shared/cn";
import type { ReadAloudVoice } from "./readAloud";
import {
  KEYED_PROVIDERS,
  ONLINE_KEYS_CHANGED_EVENT,
  ONLINE_NOTICE,
  SAMPLE_TEXT,
  chooseDefaultVoice,
  defaultVoice,
  onlineNotice,
  resolveVoice,
} from "./readAloudVoice";

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
  azure: "Trên Azure: tạo tài nguyên Speech (bậc F0 miễn phí), mở “Keys and Endpoint”, chép Key 1 và Location/Region.",
  google: "Trên Google Cloud: bật Cloud Text-to-Speech API, rồi APIs & Services → Credentials → Create credentials → API key.",
  fpt: "Trên console.fpt.ai: đăng nhập, mở mục Text to Speech, chép API key.",
  viettel: "Trên viettelai.vn: đăng nhập, mở Tài khoản → Token, chép token.",
};

const GROUPS: { provider: string; title: string }[] = [
  { provider: "edge", title: "Microsoft Edge · trực tuyến, miễn phí" },
  ...Object.entries(KEYED_PROVIDERS).map(([provider, name]) => ({ provider, title: `${name} · dùng khóa của bạn` })),
  { provider: "device", title: "Giọng của máy · không cần mạng" },
];

function genderLabel(gender?: string): string {
  return gender === "female" ? "Nữ" : gender === "male" ? "Nam" : "";
}

function muted(): boolean {
  // ?mute=1: kiểm thử tự động không được phát tiếng ra loa của người dùng (như engine.ts, musicBed.ts).
  return typeof window !== "undefined" && new URLSearchParams(window.location.search).get("mute") === "1";
}

function errorText(error: unknown): string {
  return (error as Error)?.message || "Không làm được lúc này.";
}

function useSample(api: VoiceSettingsApi) {
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
      const url = await api.sample(voice, SAMPLE_TEXT);
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
  const [busy, setBusy] = useState<"" | "check" | "remove">("");
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => setRegion(info.region), [info.region]);
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
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm font-semibold">{info.name}</div>
        {status}
      </div>
      <p className="mt-1 text-[13px] text-fg-2 text-pretty">
        {info.limits.free}. {info.limits.timings === "exact" ? "Sáng đúng từng chữ khi đọc." : "Sáng từng chữ theo ước lượng."}
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
              placeholder="Vùng: southeastasia"
              spellCheck={false}
              className="h-9 w-full rounded-lg border border-line bg-panel px-3 text-sm"
            />
          </label>
        )}
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
    </div>
  );
}

/** Mục "Giọng đọc" của Cài đặt. `deviceHint`: câu cho khi máy chưa có giọng tiếng Việt (mỗi nền tảng cài theo cách riêng). */
export function VoiceSettings({ api, deviceHint }: { api: VoiceSettingsApi; deviceHint: string }) {
  const client = useQueryClient();
  const [voices, setVoices] = useState<ReadAloudVoice[] | null>(null);
  const [providers, setProviders] = useState<OnlineProviderInfo[]>([]);
  const [chosen, setChosen] = useState(defaultVoice);
  const [loadError, setLoadError] = useState("");
  const sample = useSample(api);
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
        GROUPS.map(({ provider, title }) => {
          const list = voices.filter((voice) => voice.provider === provider);
          if (!list.length && provider !== "device") return null;
          const notice = provider === "edge" ? ONLINE_NOTICE : list[0] ? onlineNotice(list[0]) : "";
          return (
            <div key={provider} role="radiogroup" aria-label={title}>
              <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-fg-3">{title}</div>
              {!list.length && <p className="py-1 text-[13px] text-fg-2 text-pretty">{deviceHint}</p>}
              <ul className="divide-y divide-line">
                {list.map((voice) => {
                  const selected = voice.id === current?.id;
                  const playing = sample.playing === voice.id;
                  return (
                    <li key={voice.id} className="flex items-center gap-3 py-2">
                      <button
                        type="button"
                        role="radio"
                        aria-checked={selected}
                        onClick={() => {
                          chooseDefaultVoice(voice.id);
                          setChosen(voice.id);
                        }}
                        className="flex min-w-0 flex-1 items-center gap-2.5 text-left"
                      >
                        <span className={cn("grid size-5 shrink-0 place-items-center rounded-full border", selected ? "border-accent bg-accent text-accent-ink" : "border-line-strong")}>
                          {selected && <Check className="size-3" strokeWidth={3} />}
                        </span>
                        <span className="min-w-0 truncate text-sm font-medium">{voice.name}</span>
                        {genderLabel(voice.gender) && <span className="shrink-0 text-xs text-fg-2">{genderLabel(voice.gender)}</span>}
                        {selected && <span className="shrink-0 text-xs text-accent-text">Mặc định</span>}
                      </button>
                      <Button
                        size="sm"
                        variant="ghost"
                        icon={playing ? Square : Play}
                        loading={sample.loading === voice.id}
                        onClick={() => (playing ? sample.stop() : void sample.play(voice.id))}
                        aria-label={`${playing ? "Dừng" : "Thử"} giọng ${voice.name}`}
                      >
                        {playing ? "Dừng" : "Thử giọng"}
                      </Button>
                    </li>
                  );
                })}
              </ul>
              {sample.failed && list.some((voice) => voice.id === sample.failed!.voice) && (
                <p className="mt-1 text-[13px] text-danger text-pretty">{sample.failed.message}</p>
              )}
              {notice && list.length > 0 && <p className="mt-1 text-xs text-fg-2 text-pretty">{notice}</p>}
            </div>
          );
        })}
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

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, Music2, Pin, RefreshCw, Shuffle, VolumeX, Volume2 } from "lucide-react";
import { toast } from "sonner";
import { formatClock } from "@/shared/format";
import { Button } from "@/shared/ui";
import { api } from "./api";

// Tab "Nhạc nền" của trang dự án (docs/MUSIC_SELECTION_MODEL.md, mục 4 - ba tầng chỉnh): cả cuốn (bật/tắt, thế giới
// của truyện, mức nhạc), từng đoạn (im lặng, bỏ ghim), từng bài (không dùng bài này nữa). Máy tự làm hết; mọi chỉnh ở đây
// là tuỳ chọn và được giữ khi máy chọn lại. Sửa nhạc không bao giờ phải đọc lại giọng.

interface Scene {
  key: string;
  chapterId: number;
  start: number;
  end: number;
  valence: number;
  arousal: number;
  tension?: number;
  link: string | null;
  pinned?: boolean;
  silenced?: boolean;
}

interface TrackInfo {
  title?: string;
  creator?: string;
  attribution?: string;
}

interface MusicView {
  plan: { enabled: boolean; levelDb: number; genre: string | null; scenes: Scene[]; tracks: Record<string, TrackInfo> } | null;
  overrides: { enabled: boolean; levelDb: number; genre: string | null; pins: Record<string, string>; silenced: string[]; banned: string[] };
  error: string;
  taxonomy: {
    genres?: Record<string, { vi: string }>;
    gems?: Record<string, { vi: string; va: [number, number, number] }>;
  };
}

interface Alternative {
  link: string;
  title: string;
  creator: string;
  attribution: string;
  duration?: number;
  score: number;
}

const LEVELS: [number, string][] = [
  [-14, "To"],
  [-17, "Hơi to"],
  [-20, "Vừa (mặc định)"],
  [-23, "Nhỏ"],
  [-26, "Rất nhỏ"],
];

/** Nhãn không khí đọc được (GEMS) gần nhất với toạ độ của đoạn. */
function moodOf(scene: Scene, gems: MusicView["taxonomy"]["gems"]): string {
  if (!gems) return "";
  let best = "";
  let distance = Infinity;
  for (const item of Object.values(gems)) {
    const [v, a, t] = item.va;
    const d = (v - scene.valence) ** 2 + (a - scene.arousal) ** 2 + 0.6 * (t - (scene.tension ?? 0)) ** 2;
    if (d < distance) {
      distance = d;
      best = item.vi;
    }
  }
  return best;
}

/** "Đổi bài": các bài khác hợp đoạn này, hợp nhất trước (cùng cách chấm điểm với lúc máy chọn). Chọn = ghim bài ấy. */
function Alternatives({ bookId, sceneKey, busy, onChoose }: { bookId: string; sceneKey: string; busy: boolean; onChoose: (link: string) => void }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["music-alternatives", bookId, sceneKey],
    queryFn: () =>
      api<{ alternatives: Alternative[] }>(`/api/books/${bookId}/music/scenes/${encodeURIComponent(sceneKey)}/alternatives`),
    staleTime: 0,
    gcTime: 0,
  });
  if (isLoading) return <p className="text-fg-2">Đang tìm bài khác…</p>;
  if (error) return <p className="text-warning">{(error as Error).message}</p>;
  if (!data?.alternatives.length) return <p className="text-fg-2">Không còn bài nào khác đủ hợp đoạn này.</p>;
  return (
    <ul className="space-y-1">
      {data.alternatives.map((item) => (
        <li key={item.link} className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="min-w-0 flex-1 break-words">
            <Music2 className="mr-1.5 inline size-4 text-fg-2" />
            {item.title || "Bài nhạc"}
            {item.creator && <span className="text-fg-2"> · {item.creator}</span>}
            {item.duration ? <span className="tabular text-fg-2"> · {formatClock(item.duration)}</span> : null}
          </span>
          <Button size="sm" variant="secondary" icon={Pin} disabled={busy} onClick={() => onChoose(item.link)}>
            Chọn
          </Button>
        </li>
      ))}
    </ul>
  );
}

export function MusicTab({ bookId, chapterTitle }: { bookId: string; chapterTitle: (id: number) => string }) {
  const client = useQueryClient();
  const [swapping, setSwapping] = useState<string | null>(null); // khoá đoạn đang mở "Đổi bài"
  const key = ["music", bookId];
  const { data, isLoading } = useQuery({ queryKey: key, queryFn: () => api<MusicView>(`/api/books/${bookId}/music`) });
  const change = useMutation({
    mutationFn: (body: Record<string, unknown>) => api<MusicView>(`/api/books/${bookId}/music`, { method: "PUT", body }),
    onSuccess: (result) => {
      client.setQueryData(key, result);
      setSwapping(null);
      if (result.error) toast.warning("Đã lưu lựa chọn", { description: result.error });
    },
    onError: (error: Error) => toast.error("Không đổi được nhạc nền", { description: error.message }),
  });
  const rebuild = useMutation({
    mutationFn: () => api<MusicView>(`/api/books/${bookId}/music/rebuild`, { method: "POST" }),
    onSuccess: (result) => client.setQueryData(key, result),
    onError: (error: Error) => toast.error("Không chọn lại được nhạc", { description: error.message }),
  });

  if (isLoading || !data) return <p className="mt-6 text-sm text-fg-2">Đang dựng nhạc nền…</p>;
  const { plan, overrides, taxonomy } = data;
  const genres = Object.entries(taxonomy.genres ?? {});
  const byChapter = new Map<number, Scene[]>();
  for (const scene of plan?.scenes ?? []) byChapter.set(scene.chapterId, [...(byChapter.get(scene.chapterId) ?? []), scene]);

  return (
    <div className="mt-6 space-y-6">
      <section className="flex flex-wrap items-end gap-4 rounded-xl border border-line bg-panel p-4">
        <Button
          variant={overrides.enabled ? "primary" : "secondary"}
          icon={overrides.enabled ? Volume2 : VolumeX}
          loading={change.isPending}
          onClick={() => change.mutate({ enabled: !overrides.enabled })}
        >
          {overrides.enabled ? "Nhạc nền đang bật" : "Nhạc nền đang tắt"}
        </Button>
        <label className="text-sm">
          <span className="block text-fg-2">Thế giới của truyện</span>
          <select
            id="music-genre"
            value={overrides.genre ?? ""}
            onChange={(event) => change.mutate({ genre: event.target.value || null })}
            className="mt-1 h-9 w-64 max-w-full rounded-lg border border-line bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-accent"
          >
            <option value="">Chưa chọn (mọi phong cách)</option>
            {genres.map(([value, genre]) => (
              <option key={value} value={value}>
                {genre.vi}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="block text-fg-2">Mức nhạc dưới giọng đọc</span>
          <select
            id="music-level"
            value={String(overrides.levelDb)}
            onChange={(event) => change.mutate({ levelDb: Number(event.target.value) })}
            className="mt-1 h-9 w-48 rounded-lg border border-line bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-accent"
          >
            {LEVELS.map(([value, label]) => (
              <option key={value} value={String(value)}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <Button variant="ghost" icon={RefreshCw} loading={rebuild.isPending} onClick={() => rebuild.mutate()}>
          Chọn lại nhạc
        </Button>
      </section>

      {data.error && <p className="text-sm text-warning">{data.error}</p>}
      {!plan?.scenes.length ? (
        <p className="text-sm text-fg-2">Chưa có đoạn nào - nhạc nền dựng sau khi sách đã phân tích.</p>
      ) : (
        [...byChapter.entries()].map(([chapterId, scenes]) => (
          <section key={chapterId}>
            <h3 className="mb-2 text-sm font-semibold">{chapterTitle(chapterId)}</h3>
            <ul className="divide-y divide-line rounded-xl border border-line">
              {scenes.map((scene) => {
                const track = scene.link ? plan.tracks[scene.link] : undefined;
                return (
                  <li key={scene.key} className="flex flex-wrap items-center gap-x-4 gap-y-1.5 px-3 py-2.5 text-sm">
                    <span className="tabular w-28 shrink-0 text-fg-2">
                      {formatClock(scene.start)}–{formatClock(scene.end)}
                    </span>
                    <span className="w-24 shrink-0">{moodOf(scene, taxonomy.gems)}</span>
                    <span className="min-w-0 flex-1 break-words">
                      {scene.link ? (
                        <>
                          <Music2 className="mr-1.5 inline size-4 text-accent-text" />
                          {track?.title ?? "Bài nhạc"}
                          {track?.creator && <span className="text-fg-2"> · {track.creator}</span>}
                          {scene.pinned && <Pin className="ml-1.5 inline size-3.5 text-fg-2" aria-label="Đã ghim" />}
                        </>
                      ) : (
                        <span className="text-fg-2">{scene.silenced ? "Im lặng (bạn chọn)" : "Im lặng - không bài nào đủ hợp"}</span>
                      )}
                    </span>
                    <span className="flex shrink-0 gap-1">
                      <Button size="sm" variant="ghost" icon={Shuffle}
                        onClick={() => setSwapping(swapping === scene.key ? null : scene.key)}>
                        Đổi bài
                      </Button>
                      {scene.pinned && (
                        <Button size="sm" variant="ghost" onClick={() => change.mutate({ pins: { [scene.key]: null } })}>
                          Bỏ ghim
                        </Button>
                      )}
                      <Button size="sm" variant="ghost" icon={VolumeX}
                        onClick={() => change.mutate({ silence: { [scene.key]: !scene.silenced } })}>
                        {scene.silenced ? "Có nhạc" : "Im lặng"}
                      </Button>
                      {scene.link && !scene.pinned && (
                        <Button size="sm" variant="ghost" icon={Ban} onClick={() => change.mutate({ ban: [scene.link] })}>
                          Không dùng bài này
                        </Button>
                      )}
                    </span>
                    {swapping === scene.key && (
                      <div className="basis-full rounded-lg bg-sunken p-2.5 text-sm">
                        <Alternatives
                          bookId={bookId}
                          sceneKey={scene.key}
                          busy={change.isPending}
                          onChoose={(link) =>
                            // Đoạn đang im lặng (bạn chọn) mà chọn bài thì có nhạc lại.
                            change.mutate({ pins: { [scene.key]: link }, ...(scene.silenced ? { silence: { [scene.key]: false } } : {}) })
                          }
                        />
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        ))
      )}
      {plan && Object.keys(plan.tracks).length > 0 && (
        <details className="text-xs text-fg-2">
          <summary className="cursor-pointer">Ghi công các bài nhạc ({Object.keys(plan.tracks).length})</summary>
          <ul className="mt-2 space-y-1">
            {Object.entries(plan.tracks).map(([link, track]) => (
              <li key={link} className="break-words">{track.attribution ?? link}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

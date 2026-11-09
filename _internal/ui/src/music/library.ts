import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { S } from "../shared/strings.generated";
import { api } from "../studio/api";

// Kho nhạc (màn "Nhạc", docs/DESIGN.md mục Nhạc): danh sách cả danh mục nhạc nền, lọc / tìm ở máy chủ (abook/webui/music_library.py -
// cùng bảng ca với Android và Qt: tests/fixtures/music_library/cases.json), lưu bài về máy (bài ghim: bộ dọn bộ đệm không xoá).

export type Tempo = "slow" | "mid" | "fast";
export type Length = "short" | "mid" | "long";

export interface LibraryFilters {
  q: string;
  playlist: string;
  style: string;
  emotion: string;
  tempo: Tempo | "";
  length: Length | "";
  downloaded: boolean;
}

export const NO_FILTERS: LibraryFilters = { q: "", playlist: "", style: "", emotion: "", tempo: "", length: "", downloaded: false };

export interface LibraryTrack {
  link: string;
  title?: string;
  creator?: string;
  duration?: number;
  bpm?: number;
  style?: string;
  bytes?: number;
  audibleStart?: number;
  lufs?: number;
  saved: boolean;
  downloaded: boolean;
}

export interface LibraryList {
  tracks: LibraryTrack[];
  count: number;
  error: string;
  missingBytes: number;
  saved: { count: number; bytes: number };
  elapsedMs?: number;
}

export interface Labelled {
  id: string;
  label: string;
}

export interface LibraryMeta {
  styles: Labelled[];
  emotions: Labelled[];
  playlists: { id: string; name: string; count: number }[];
  error: string;
}

export interface TrackDetail {
  link: string;
  title?: string;
  creator?: string;
  duration?: number;
  bpm?: number;
  style?: string;
  bytes?: number;
  arousal?: number;
  license?: string;
  licenseUrl?: string;
  attribution?: string;
  landing?: string;
  vocals?: number;
  audibleStart?: number;
  emotions: { id: string; score: number }[];
  playlists: { id: string; name: string }[];
  saved: boolean;
  downloaded: boolean;
  why?: { fit: number; matches: { id: string; scene: number; track: number }[] };
}

export interface DownloadState {
  active: Record<string, { done: number; total: number | null }>;
  failed: Record<string, string>;
}

export const TEMPO_OPTIONS: { value: Tempo; label: string }[] = [
  { value: "slow", label: S.s_cham_6ddeaddc },
  { value: "mid", label: S.s_vua_8af1c03b },
  { value: "fast", label: S.s_nhanh_c2385879 },
];

export const LENGTH_OPTIONS: { value: Length; label: string }[] = [
  { value: "short", label: S.s_duoi_2_phut_c8f6f04e },
  { value: "mid", label: S.s_2_5_phut_29244d26 },
  { value: "long", label: S.s_tren_5_phut_42aafebc },
];

/** Chuỗi truy vấn của GET /api/music/library (chỉ khoá đang lọc). */
export function libraryQuery(filters: LibraryFilters): string {
  const params = new URLSearchParams();
  for (const key of ["q", "playlist", "style", "emotion", "tempo", "length"] as const) {
    const value = filters[key].trim();
    if (value) params.set(key, value);
  }
  if (filters.downloaded) params.set("downloaded", "1");
  const text = params.toString();
  return text ? `?${text}` : "";
}

/** Có bộ lọc nào đang bật không (chữ tìm không tính: ô tìm tự có nút xoá). */
export function filtering(filters: LibraryFilters): boolean {
  return Boolean(filters.playlist || filters.style || filters.emotion || filters.tempo || filters.length || filters.downloaded);
}

export const LIBRARY_KEY = ["music-library"] as const;

export function useLibraryMeta() {
  return useQuery({ queryKey: [...LIBRARY_KEY, "meta"], queryFn: () => api<LibraryMeta>("/api/music/library/meta"), staleTime: 5 * 60_000 });
}

/** `saved`: phần "Đã lưu" - chỉ bài người dùng lưu, mới lưu trước. */
export function useLibrary(filters: LibraryFilters, saved = false) {
  const base = libraryQuery(filters);
  const query = saved ? `${base}${base ? "&" : "?"}saved=1` : base;
  return useQuery({
    queryKey: [...LIBRARY_KEY, "list", query],
    queryFn: () => api<LibraryList>(`/api/music/library${query}`),
    placeholderData: (previous) => previous, // đổi bộ lọc: danh sách cũ ở lại tới khi danh sách mới về (không nháy trống)
  });
}

export function useTrackDetail(link: string | null, context?: { book: string; scene: string } | null) {
  const extra = context ? `&book=${encodeURIComponent(context.book)}&scene=${encodeURIComponent(context.scene)}` : "";
  return useQuery({
    queryKey: [...LIBRARY_KEY, "track", link, context?.book ?? "", context?.scene ?? ""],
    queryFn: () => api<TrackDetail>(`/api/music/library/track?link=${encodeURIComponent(link ?? "")}${extra}`),
    enabled: link !== null,
  });
}

/** Hàng tải: hỏi lại mỗi 700 ms khi còn bài đang tải; xong một bài thì danh sách (cờ đã tải, MB) tải lại. */
export function useDownloads() {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: [...LIBRARY_KEY, "downloads"],
    queryFn: () => api<DownloadState>("/api/music/library/downloads"),
    refetchInterval: (state) => (Object.keys(state.state.data?.active ?? {}).length ? 700 : false),
  });
  const active = Object.keys(query.data?.active ?? {}).join("|");
  useEffect(() => {
    void client.invalidateQueries({ queryKey: [...LIBRARY_KEY, "list"] });
    void client.invalidateQueries({ queryKey: [...LIBRARY_KEY, "track"] });
    void client.invalidateQueries({ queryKey: ["book-music-library"] });
  }, [active, client]);
  return query;
}

export function useSaveTracks() {
  const client = useQueryClient();
  const refresh = (state: DownloadState) => {
    client.setQueryData([...LIBRARY_KEY, "downloads"], state);
    void client.invalidateQueries({ queryKey: [...LIBRARY_KEY] });
    void client.invalidateQueries({ queryKey: ["book-music-library"] });
  };
  const save = useMutation({
    mutationFn: (links: string[]) => api<DownloadState>("/api/music/library/save", { method: "POST", body: { links } }),
    onSuccess: refresh,
  });
  const unsave = useMutation({
    mutationFn: (links: string[]) => api<DownloadState>("/api/music/library/unsave", { method: "POST", body: { links } }),
    onSuccess: refresh,
  });
  return { save, unsave };
}

/** Trạng thái tải của một bài để vẽ: đang tải (phần trăm, null = chưa biết cỡ), hỏng, đã tải, chưa tải. */
export type TrackLoad = { kind: "loading"; percent: number | null } | { kind: "failed" } | { kind: "done" } | { kind: "none" };

export function loadOf(track: { link: string; downloaded: boolean }, downloads: DownloadState | undefined): TrackLoad {
  const active = downloads?.active[track.link];
  if (active) return { kind: "loading", percent: active.total ? Math.min(99, Math.floor((active.done / active.total) * 100)) : null };
  if (downloads?.failed[track.link] !== undefined) return { kind: "failed" };
  return track.downloaded ? { kind: "done" } : { kind: "none" };
}

/** Nhãn tiếng Việt của một mã (phong cách / cảm xúc) từ taxonomy của danh mục; mã lạ thì để nguyên. */
export function labelOf(items: readonly Labelled[] | undefined, id: string | undefined): string {
  if (!id) return "";
  return items?.find((item) => item.id === id)?.label ?? id;
}

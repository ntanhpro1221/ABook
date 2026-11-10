import { galleryState } from "./state";

// Kho nhạc giả cho phòng trưng bày (màn Nhạc): 48 bài dựng sẵn, tên dài ngắn lẫn lộn (kiểm chữ cắt / đè), vài bài đã lưu, hai bài đang tải
// khi `scenario.musicDownloading`. Lọc ở đây chỉ đủ cho ảnh chụp (tìm + phong cách + danh sách phát) - luật thật ở máy chủ
// (abook/webui/music_library.py) và bảng ca chung tests/fixtures/music_library/cases.json.

const STYLES = [
  ["eastern_ancient", "Cổ phong phương Đông"], ["orchestral_epic", "Giao hưởng hùng tráng"], ["orchestral_soft", "Giao hưởng nhẹ"],
  ["medieval_folk", "Trung cổ / dân gian phương Tây"], ["piano", "Piano"], ["ambient", "Ambient / không gian"], ["dark", "U tối / kinh dị"],
  ["acoustic_light", "Mộc / nhẹ nhàng"], ["electronic", "Điện tử"], ["jazz", "Jazz / lounge"], ["rock", "Rock"],
  ["pop_dance", "Pop / nhảy (funk, disco, latin)"], ["comedic", "Hài hước"], ["world_other", "Nhạc thế giới khác (Ấn, Trung Đông, Phi...)"],
] as const;

const EMOTIONS = [
  ["peacefulness", "bình yên"], ["tenderness", "dịu dàng"], ["nostalgia", "hoài niệm"], ["sadness", "buồn"], ["joy", "vui tươi"],
  ["playful", "tinh nghịch"], ["power", "hào hùng"], ["wonder", "kỳ vĩ"], ["tension", "căng thẳng"], ["fear", "rùng rợn"],
  ["anger", "giận dữ"], ["mystery", "bí ẩn"], ["moved", "xúc động"],
] as const;

const TITLES = [
  "Ghostpocalypse - 5 Apotheosis", "Air Prelude", "Mưa trên phố cổ", "Bản tình ca của những người lữ hành trong đêm dài không trăng",
  "Clean Soul", "Đồi gió", "Hành khúc đêm", "Long Road Ahead", "Lantern Festival", "Moonlight Hall", "Sương mù", "Thunder Dreams",
  "Tea Garden", "Wanderer's Waltz", "Ánh sáng cuối hầm", "Crypto", "Dreamy Flashback", "Echoes of Time", "Firelight", "Gymnopédie No. 1",
];
const CREATORS = ["Kevin MacLeod", "Scott Buckley", "Shane Ivers", "魔王魂", "Nhóm nhạc rất dài tên để kiểm chữ cắt ở dòng người sáng tác"];

export const LIBRARY_TRACKS = Array.from({ length: 48 }, (_, index) => {
  const style = STYLES[index % STYLES.length][0];
  const emotions = Object.fromEntries(EMOTIONS.map(([id], position) => [id, ((index * 37 + position * 53) % 100) / 100]));
  return {
    link: `https://music.example/${index}.mp3`,
    title: `${TITLES[index % TITLES.length]}${index >= TITLES.length ? ` ${Math.floor(index / TITLES.length) + 1}` : ""}`,
    creator: CREATORS[index % CREATORS.length],
    duration: 45 + ((index * 53) % 420),
    bpm: 60 + ((index * 17) % 110),
    style,
    bytes: 2_400_000 + index * 91_000,
    lufs: -16 - (index % 6),
    audibleStart: 0.4,
    arousal: ((index * 29) % 200) / 100 - 1,
    emotions,
    license: index % 4 === 3 ? "cc0" : "by",
    licenseUrl: index % 4 === 3 ? "https://creativecommons.org/publicdomain/zero/1.0/" : "https://creativecommons.org/licenses/by/4.0/",
    attribution: index % 4 === 3 ? "" : `"${TITLES[index % TITLES.length]}" ${CREATORS[index % CREATORS.length]}, Licensed under Creative Commons: By Attribution 4.0 License https://creativecommons.org/licenses/by/4.0/`,
    landing: "https://incompetech.com/music/royalty-free/",
    vocals: index % 5 === 0 ? 0.8 : 0.1,
  };
});

const PLAYLISTS = [
  { id: "fantasy_adventure", name: "Kỳ ảo phiêu lưu", tracks: LIBRARY_TRACKS.filter((_, index) => index % 3 === 0).map((track) => track.link) },
  { id: "calm_reading", name: "Đọc êm", tracks: LIBRARY_TRACKS.filter((_, index) => index % 4 === 1).map((track) => track.link) },
  { id: "dark_mystery", name: "U tối bí ẩn", tracks: LIBRARY_TRACKS.filter((_, index) => index % 5 === 2).map((track) => track.link) },
];

const saved = new Set(LIBRARY_TRACKS.filter((_, index) => index % 7 === 0).map((track) => track.link));
const downloadingLinks = () => (galleryState.scenario.musicDownloading ? [LIBRARY_TRACKS[1].link, LIBRARY_TRACKS[2].link] : []);

function fold(text: string): string {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/gi, "d").toLowerCase();
}

function row(track: (typeof LIBRARY_TRACKS)[number]) {
  const { link, title, creator, duration, bpm, style, bytes, lufs, audibleStart } = track;
  return { link, title, creator, duration, bpm, style, bytes, lufs, audibleStart, saved: saved.has(link), downloaded: saved.has(link) };
}

export function libraryMeta() {
  return {
    styles: STYLES.map(([id, label]) => ({ id, label })),
    emotions: EMOTIONS.map(([id, label]) => ({ id, label })),
    playlists: PLAYLISTS.map(({ id, name, tracks }) => ({ id, name, count: tracks.length })),
    error: "",
  };
}

export function libraryList(query: URLSearchParams) {
  const words = fold(query.get("q") ?? "").split(/\s+/).filter(Boolean);
  const style = query.get("style");
  const playlist = PLAYLISTS.find((item) => item.id === query.get("playlist"));
  let tracks = LIBRARY_TRACKS.filter((track) => (!style || track.style === style) && (!playlist || playlist.tracks.includes(track.link))
    && words.every((word) => fold(`${track.title} ${track.creator}`).includes(word)));
  if (query.get("saved") === "1" || query.get("downloaded") === "1") tracks = tracks.filter((track) => saved.has(track.link));
  tracks = [...tracks].sort((a, b) => fold(a.title).localeCompare(fold(b.title)));
  const rows = tracks.map(row);
  const kept = LIBRARY_TRACKS.filter((track) => saved.has(track.link));
  return {
    tracks: rows, count: rows.length, error: "",
    missingBytes: rows.filter((track) => !track.downloaded).reduce((sum, track) => sum + track.bytes, 0),
    saved: { count: kept.length, bytes: kept.reduce((sum, track) => sum + track.bytes, 0) },
  };
}

export function libraryTrack(query: URLSearchParams) {
  const track = LIBRARY_TRACKS.find((item) => item.link === query.get("link")) ?? LIBRARY_TRACKS[0];
  const emotions = Object.entries(track.emotions).map(([id, score]) => ({ id, score })).sort((a, b) => b.score - a.score);
  const scene = query.get("scene");
  return {
    ...row(track),
    arousal: track.arousal, license: track.license, licenseUrl: track.licenseUrl, attribution: track.attribution, landing: track.landing, vocals: track.vocals,
    emotions,
    playlists: PLAYLISTS.filter((item) => item.tracks.includes(track.link)).map(({ id, name }) => ({ id, name })),
    ...(scene ? { why: { fit: 0.86, matches: emotions.slice(0, 3).map((item, index) => ({ id: item.id, scene: Math.max(0, 0.9 - index * 0.2), track: item.score })) } } : {}),
  };
}

export function libraryDownloads() {
  return { active: Object.fromEntries(downloadingLinks().map((link, index) => [link, { done: (index + 1) * 1_100_000, total: 2_500_000 }])), failed: {} };
}

export function librarySave(links: unknown, keep: boolean) {
  for (const link of Array.isArray(links) ? links : []) if (typeof link === "string") (keep ? saved.add(link) : saved.delete(link));
  return libraryDownloads();
}

export function bookMusicTracks() {
  return {
    tracks: LIBRARY_TRACKS.slice(0, 5).map((track, index) => ({ ...row(track), scenes: 9 - index * 2, scene: `1:${index + 1}` })),
    missingBytes: LIBRARY_TRACKS.slice(0, 5).filter((track) => !saved.has(track.link)).reduce((sum, track) => sum + track.bytes, 0),
  };
}

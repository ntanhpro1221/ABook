import type { Bookmark } from "@/listen/model";
import type { ActivityItem, AppInfo, BookSummary, Cast as StudioCast, Chapter, Phase, Preferences, Voice } from "@/studio/api";
import { BOOKS, bookCast, chapterScript, chapterText, findBook, importPreview, lastNight, listenBook, sessions, type GalleryBook } from "./data";
import { NOW_SECONDS } from "./clock";
import { galleryState, never } from "./state";

// Máy chủ cục bộ giả của app máy tính (abook/webui/server.py): `fetch("/api/...")` đi vào bảng đường dưới đây, trả JSON cùng hình
// dạng máy chủ thật. Đường nào chưa có thì trả 404 và ghi vào `galleryState.missing`.

type Query = URLSearchParams;
type Handler = (match: RegExpMatchArray, body: Record<string, unknown>, query: Query) => unknown;

class Reply {
  constructor(readonly status: number, readonly body: unknown) {}
}

const fail = (status: number, error: string) => new Reply(status, { error });

const projects = () => BOOKS.filter((book) => !book.imported && !book.streamed);
const book = (id: string): GalleryBook => findBook(id) ?? (() => { throw fail(404, "Không tìm thấy sách"); })();

function phaseOf(item: GalleryBook): Phase {
  if (item.chapters.every((chapter) => chapter.available)) return "done";
  if (!item.chapters.some((chapter) => chapter.available)) return item.producing ? "analysis" : "idle";
  return "synthesis";
}

function chapterRows(item: GalleryBook): Chapter[] {
  const firstMissing = item.chapters.findIndex((chapter) => !chapter.available);
  return item.chapters.map((chapter, index) => {
    const working = item.producing && !item.pauseReason && index === firstMissing;
    const segments = 120 + ((chapter.id * 37) % 60);
    const recorded = chapter.available ? segments : working ? Math.round(segments * 0.4) : 0;
    return {
      id: chapter.id,
      index: index + 1, // chapter_index thật đánh từ 1 (text_processing.build_chapter_manifest)
      title: chapter.title,
      displayTitle: chapter.title,
      subtitle: chapter.subtitle,
      fullTitle: chapter.subtitle ? `${chapter.title}: ${chapter.subtitle}` : chapter.title,
      status: chapter.available ? "completed" : working ? "synthesizing" : "analyzed",
      statusLabel: chapter.available ? "Đã xong" : working ? "Đang thu âm" : phaseOf(item) === "analysis" ? "Chờ phân tích" : "Chờ thu âm",
      segments: { total: segments, analyzed: phaseOf(item) === "analysis" ? 0 : segments, recorded, finished: recorded, failed: 0, warnings: chapter.id === 3 ? 2 : 0 },
      seconds: chapter.available ? chapter.duration : 0,
      playable: chapter.available,
      startedAt: chapter.available || working ? NOW_SECONDS - (30 - index) * 3600 : null,
      completedAt: chapter.available ? NOW_SECONDS - (24 - index) * 3600 : null,
      lastError: "",
    };
  });
}

export function summary(item: GalleryBook): BookSummary {
  const rows = chapterRows(item);
  const phase = phaseOf(item);
  const running = Boolean(item.producing) && !(galleryState.scenario.queued && item.pauseReason);
  const done = rows.filter((row) => row.playable).length;
  const segments = rows.reduce((sum, row) => sum + row.segments.total, 0);
  const recorded = rows.reduce((sum, row) => sum + row.segments.recorded, 0);
  const analysis = phase === "analysis" ? 0.62 : 1;
  const synthesis = segments ? recorded / segments : 0;
  const statusLabel = phase === "done" ? "Đã xong" : item.pauseReason === "battery" ? "Tạm dừng · máy đang chạy pin" : running ? (phase === "analysis" ? "Đang phân tích" : "Đang thu âm") : "Chưa bắt đầu";
  return {
    id: item.id,
    path: `D:/Sách nói/${item.title}`,
    title: item.title,
    status: phase,
    stage: phase,
    phase,
    statusLabel,
    running,
    interrupted: false,
    starting: false,
    startError: "",
    createdAt: item.addedAt,
    updatedAt: item.state.updatedAt ?? item.addedAt,
    lastError: "",
    pendingChanges: 0,
    settings: { profile: "balanced", profileLabel: "Cân bằng", narrator: item.narrator, analyzer: "qwen3.5:9b" },
    chapters: { total: rows.length, completed: done, failed: 0, working: running && phase === "synthesis" ? 1 : 0 },
    segments: { total: segments, analyzed: Math.round(segments * analysis), pending: Math.round(segments * (1 - analysis)), recorded, finished: recorded, failed: 0 },
    progress: { overall: galleryState.scenario.queued && !running ? 0 : phase === "analysis" ? 0.18 : 0.3 + synthesis * 0.7, analysis, synthesis },
    audioSeconds: rows.reduce((sum, row) => sum + row.seconds, 0),
    eta: item.eta ? { phase: item.eta.phase as Phase, seconds: item.eta.seconds } : null,
    speakerPass: null,
    position: item.state.last ? { chapterId: item.state.last.chapterId, seconds: item.state.last.seconds, duration: 1800, at: item.state.last.at } : null,
    queuePosition: galleryState.scenario.queued && !running ? projects().filter((entry) => !entry.producing || entry.pauseReason).findIndex((entry) => entry.id === item.id) + 1 : null,
    paused: item.pauseReason ?? null,
    canPause: true,
    stopping: false,
    runEnd: null,
    series: item.series ?? null,
    cover: item.cover ? { url: `./${item.cover.file}`, color: item.cover.color, width: 600, height: 900, version: 1 } : null,
    castLocked: phase !== "analysis",
    precast: { ready: phase !== "analysis", wait: false, announcedAt: null, held: false },
  };
}

function studioCast(item: GalleryBook): StudioCast {
  const cast = bookCast(item);
  const profile = (voice: string) => ({ key: voice, preset: voice, label: voice, tone: "ấm" });
  return {
    narrator: { ...cast.narrator, voice: item.narrator, profile: profile(item.narrator) },
    characters: cast.characters.map((member) => ({ ...member, voice: member.voice ? profile(member.voice.label ?? member.voice.preset) : null })),
    extras: cast.extras.map((member) => ({ ...member, voice: member.voice ? profile(member.voice.label ?? member.voice.preset) : null })),
  };
}

function activity(item: GalleryBook): ActivityItem[] {
  const lines: [number, ActivityItem["level"], string][] = [
    [5, "info", "Bắt đầu thu âm Chương 6"],
    [40, "success", "Xong Chương 5 · 21 phút 14 giây"],
    [95, "warning", "Chương 3: 2 câu đọc chưa chuẩn, đã đưa vào Cần nghe lại"],
    [180, "success", "Xong phân tích cả truyện · 4 nhân vật chính"],
    [600, "info", "Bắt đầu phân tích"],
  ];
  if (item.pauseReason === "battery") lines.unshift([1, "warning", "Tạm dừng: máy tính đang chạy pin. Cắm sạc để làm tiếp."]);
  return lines.map(([minutes, level, text], index) => ({ id: `a${index}`, at: NOW_SECONDS - minutes * 60, level, text }));
}

const VOICES: Voice[] = [
  { name: "Ngọc Lan", gender: "female", region: "Bắc", style: "Kể chuyện, ấm", recommended: true, preview: true },
  { name: "Quang Minh", gender: "male", region: "Bắc", style: "Trầm, chậm rãi", recommended: true, preview: true },
  { name: "Mai Anh", gender: "female", region: "Nam", style: "Trong, nhẹ", recommended: false, preview: true },
  { name: "Hữu Phước", gender: "male", region: "Nam", style: "Già, khàn", recommended: false, preview: true },
  { name: "Thu Hà", gender: "female", region: "Bắc", style: "Trẻ, sáng", recommended: false, preview: true },
  { name: "Tuấn Kiệt", gender: "male", region: "Trung", style: "Thiếu niên", recommended: false, preview: true },
  { name: "Bảo Trang", gender: "female", region: "Bắc", style: "Thiếu nữ", recommended: false, preview: true },
];

export function preferences(): Preferences {
  return {
    readAloudVoice: "",
    libraryRoot: "D:/Sách nói",
    theme: (document.documentElement.dataset.galleryTheme as Preferences["theme"]) || "light",
    playbackRate: 1,
    volume: 0.9,
    sleepFadeSeconds: 30,
    sleepExtendMinutes: 10,
    safetyStopHours: 2,
    sleepSchedule: null,
    pauseOnBattery: true,
    autoMusic: true,
    newBookNarrator: "",
    newBookProfile: "balanced",
    bookTemplates: [],
    letterShortcuts: true,
    touchSounds: true,
    readingSurface: "auto",
    autoRewind: true,
  };
}

function appInfo(): AppInfo {
  const prefs = preferences();
  return {
    version: "0.4.138",
    readOnly: false,
    dialogs: true,
    remote: false,
    update: null,
    canCheckUpdate: true,
    studio: galleryState.scenario.installedStudio ? { installed: true } : null,
    capabilities: { toolchain: true, workshop: true, link: false, sync: false, local: true },
    libraryRoot: prefs.libraryRoot,
    theme: prefs.theme,
    playbackRate: 1,
    volume: 0.9,
    sleepFadeSeconds: 30,
    sleepExtendMinutes: 10,
    safetyStopHours: 2,
    sleepSchedule: null,
    notices: [],
    libraryMoveRecovery: null,
  };
}

const listenLibrary = () => {
  const mode = galleryState.scenario.library;
  if (mode === "loading") return never();
  if (mode === "error") throw fail(500, "Không đọc được thư viện: ổ D: chưa sẵn sàng.");
  return mode === "empty" ? [] : BOOKS.filter((item) => !item.streamed || galleryState.scenario.remoteBooks).map((item) => listenBook(item, false));
};

function moduleStatus() {
  return {
    state: "missing", done: 0, total: 0, error: "", supported: true, reason: "", choices: [], parts: [], outdatedParts: [], outdatedBytes: 0,
    benchmark: {}, benchmarking: false, suggestion: null, device: { cores: 12, ramGb: 32, gpu: "NVIDIA GeForce RTX 5060", runs: "gpu" }, recommended: "turbo",
  };
}

const example = (item: GalleryBook, seq: number, extra: Record<string, unknown> = {}) => {
  const segment = chapterScript(item, 4).segments[seq];
  return { segmentId: segment.id, chapterId: 4, chapterTitle: "Chương 4", seq, text: segment.text, speaker: segment.speaker, hasAudio: true, ...extra };
};

/** "Việc cần duyệt" (studio/WorkInbox.tsx): ba thẻ quen thuộc - ai nói câu này, cách đọc một tên, nam hay nữ. */
function workItems(item: GalleryBook) {
  return [
    { kind: "speaker", key: "speaker:4-16", title: "Ai nói câu “Thế là bắt đầu rồi.”?", problem: "Máy chưa chắc ai nói câu này.", affected: 1, doubt: 0.62, score: 0.9,
      options: ["Ông Tư", "Minh Khuê", "Bảo"], current: "Ông Tư", examples: [example(item, 17, { before: "Cả ba cùng nhìn qua ô cửa kính mờ.", after: "Ông nói khẽ, giọng như thể đã chờ khoảnh khắc ấy cả một đời." })],
      lines: [{ stableId: `${item.id}-4-17`, textSha256: "a1" }] },
    { kind: "pronunciation", key: "pron:Tư Lành", title: "Đọc “Tư Lành” thế nào?", problem: "Tên riêng gặp 236 lần, máy đọc theo cách đoán.", affected: 236, doubt: 0.4, score: 0.7,
      options: [], current: "Tư Lành", surface: "Tư Lành", requested: null, examples: [example(item, 5)] },
    { kind: "gender", key: "gender:Bảo", title: "Bảo là nam hay nữ?", problem: "Truyện chưa nói rõ; giọng hiện tại là giọng nam.", affected: 158, doubt: 0.5, score: 0.6,
      options: ["male", "female"], current: "male", examples: [example(item, 15)] },
  ];
}

/** "Cần nghe lại" (studio/ReviewQueue.tsx). */
function reviewView(item: GalleryBook) {
  const row = (seq: number, kind: string, reason: string, heard: string, similarity: number | null) => {
    const segment = chapterScript(item, 3).segments[seq];
    return {
      segmentId: segment.id, stableId: segment.stableId, audioSha256: `sha${seq}`, chapterId: 3, chapterTitle: "Chương 3: Những ô cửa đóng kín", text: segment.text, heard,
      similarity, speaker: segment.speaker, kind, reason, playable: true, chapterClip: null, verdict: null, textSha256: `t${seq}`, spoken: null, pendingSpoken: null,
    };
  };
  const items = [
    row(4, "failed", "Bản thu bị cắt cụt ở cuối câu", "Cánh cửa gỗ kẽo kẹt mở ra một khe nhỏ, ánh đèn dầu vàng vọt hắt lên…", 0.71),
    row(14, "name-low", "Tên “Khuê” nghe như “Khuyên”", "Chị Khuyên! Đèn trên tháp chuông… nó vừa sáng lên!", 0.82),
    row(20, "unverified", "Chưa kiểm được: bộ nghe thử chưa chạy tới câu này", "", null),
  ];
  return { counts: { failed: 1, unverified: 1, "name-low": 1, "text-low": 0, name: 0, text: 0 }, pending: items.length, redoChapters: [], items, nextCursor: null, remaining: 0 };
}

function voiceChoices(item: GalleryBook, character: string) {
  const member = bookCast(item).characters.find((person) => person.name === character) ?? bookCast(item).characters[0];
  const current = member.voice?.label ?? "";
  return {
    character: { value: member.name, label: member.displayName, gender: member.gender === "Nữ" ? "female" : "male", lines: member.lines, chapters: 12 },
    current,
    pending: null,
    tryLine: { segmentId: 4003, text: "“Ông Tư ơi, ông còn thức không?”" },
    voices: VOICES.map((voice) => ({
      name: voice.name, key: voice.name, engine: "vieneu", engineLabel: "VieNeu", installed: true, oneStep: false, sharedWith: [], otherUsers: 0,
      gender: voice.gender, genderLabel: voice.gender === "female" ? "Nữ" : "Nam", region: voice.region, style: voice.style, preview: true,
      current: voice.name === current, pending: false, suggested: voice.recommended, description: "",
      takenBy: voice.name === item.narrator ? ["Người kể"] : undefined,
    })),
  };
}

function casting(item: GalleryBook, chapterId: number) {
  const script = chapterScript(item, chapterId);
  const cast = bookCast(item);
  const people = cast.characters.map((person) => ({ value: person.name, label: person.displayName, lines: person.lines }));
  return {
    chapterId,
    index: chapterId - 1,
    title: script.title,
    previous: chapterId > 1 ? chapterId - 1 : null,
    next: chapterId < item.chapters.length ? chapterId + 1 : null,
    castReady: true,
    firstPerson: null,
    cast: people,
    others: [],
    lines: script.segments.map((segment, seq) => {
      const narrator = segment.kind === "narration" || segment.kind === "heading";
      return {
        segmentId: segment.id, stableId: segment.stableId ?? "", textSha256: `t${seq}`, seq, paragraph: segment.paragraph, text: segment.text, kind: segment.kind,
        speaker: narrator ? "NARRATOR" : segment.speaker, current: narrator ? "NARRATOR" : segment.speaker, label: narrator ? "Người kể" : segment.speaker,
        editable: true, hasAudio: chapterId <= 5, emotion: segment.kind === "dialogue" ? "neutral" : null, intensity: null, lineWish: null, spoken: null, wish: null,
        hint: seq === 17 ? { kind: "unsure", note: "Máy chưa chắc ai nói câu này." } : null,
      };
    }),
  };
}

const ROUTES: [string, RegExp, Handler][] = [
  ["GET", /^\/api\/app$/, () => appInfo()],
  ["GET", /^\/api\/studio\/setup$/, () => ({
    installed: true, outdated: [], damaged: [], running: false, step: null, steps: [],
    progress: null, detail: "", error: null, root: "D:/ABook/Studio",
    gpu: { name: "NVIDIA GeForce RTX 5060 Laptop GPU", vram: 8 * 1024 ** 3 },
  })],
  ["GET", /^\/api\/preferences$/, () => preferences()],
  ["PUT", /^\/api\/preferences$/, (_, body) => ({ ...preferences(), ...body })],
  ["GET", /^\/api\/listen\/library$/, () => listenLibrary()],
  ["GET", /^\/api\/listen\/books\/([^/]+)$/, (match) => listenBook(book(match[1]), true)],
  ["GET", /^\/api\/listen\/books\/([^/]+)\/chapters\/(\d+)\/text$/, (match) => ({ text: chapterText(book(match[1]), Number(match[2])) })],
  ["GET", /^\/api\/listen\/books\/([^/]+)\/sessions$/, (match) => sessions(book(match[1]))],
  ["POST", /^\/api\/listen\/books\/([^/]+)\/sessions$/, () => ({})],
  ["POST", /^\/api\/listen\/books\/([^/]+)\/progress\/session$/, () => ({})],
  ["POST", /^\/api\/listen\/books\/([^/]+)\/progress$/, (match, body) => {
    const item = book(match[1]);
    item.state = { ...item.state, last: { chapterId: Number(body.chapterId), seconds: Number(body.seconds), at: NOW_SECONDS } };
    return item.state;
  }],
  ["POST", /^\/api\/listen\/books\/([^/]+)\/(rate|voice|reading|night)$/, () => ({})],
  ["POST", /^\/api\/listen\/books\/([^/]+)\/(finished|chapters\/\d+\/done)$/, (match) => book(match[1]).state],
  ["GET", /^\/api\/listen\/night$/, () => (galleryState.scenario.night ? { bookId: "suong-mu-2", night: lastNight() } : null)],
  ["POST", /^\/api\/listen\/night\/dismiss$/, () => ({})],
  ["GET", /^\/api\/books\/([^/]+)\/chapters\/(\d+)\/script$/, (match) => chapterScript(book(match[1]), Number(match[2]))],
  // Một đường cho cả hai phía (trang Nhân vật của Nghe, tab Nhân vật của Studio): máy chủ thật trả một hình dạng chung.
  ["GET", /^\/api\/books\/([^/]+)\/cast$/, (match) => studioCast(book(match[1]))],
  ["GET", /^\/api\/library$/, () => {
    const mode = galleryState.scenario.projects;
    if (mode === "loading") return never();
    return { root: "D:/Sách nói", books: mode === "empty" ? [] : projects().map(summary) };
  }],
  ["GET", /^\/api\/books\/([^/]+)$/, (match) => ({ book: summary(book(match[1])), chapters: chapterRows(book(match[1])) })],
  ["GET", /^\/api\/books\/([^/]+)\/activity$/, (match) => activity(book(match[1]))],
  ["GET", /^\/api\/voices$/, () => VOICES],
  ["GET", /^\/api\/readaloud\/voices$/, () => [
    { id: "edge:vi-VN-HoaiMyNeural", name: "Hoài My", provider: "edge", online: true, default: true, gender: "female" },
    { id: "edge:vi-VN-NamMinhNeural", name: "Nam Minh", provider: "edge", online: true, gender: "male" },
    { id: "device:vi-VN-An", name: "An (Windows)", provider: "device", online: false, gender: "male" },
  ]],
  ["GET", /^\/api\/readaloud\/prepare$/, () => ({ state: "idle", done: 0, total: 0, label: "", error: "" })],
  ["GET", /^\/api\/books\/([^/]+)\/music$/, () => ({
    plan: null,
    overrides: { enabled: true, levelDb: -20, genre: null, pins: {}, silenced: [], banned: [] },
    error: "",
    taxonomy: {},
    bannedTracks: {},
    moods: { running: false, error: "" },
    levelDb: -20,
  })],
  ["GET", /^\/api\/books\/([^/]+)\/music\/chapters\/(\d+)$/, () => ({ cues: [], levelDb: -20 })],
  ["GET", /^\/api\/books\/([^/]+)\/music\/playlist$/, () => ({ playlist: null, tracks: [], levelDb: -20 })],
  ["GET", /^\/api\/books\/([^/]+)\/suggestions$/, () => ({ suggestions: [] })],
  ["GET", /^\/api\/music\/local$/, () => ({ tracks: [], analyzer: false })],
  // Trang sách: việc nền xuất file (không việc nào đang chạy).
  ["GET", /^\/api\/books\/([^/]+)\/(bookfile|m4b|mp3|projectfile)-job$/, () => ({ state: "idle" })],
  ["GET", /^\/api\/listen\/books\/([^/]+)\/audiobook$/, () => ({ state: "idle" })],
  ["GET", /^\/api\/music\/playlists$/, () => ({ playlists: [], mine: 0, error: "" })],
  ["POST", /^\/api\/listen\/books\/([^/]+)\/bookmarks$/, (match, body): Bookmark => {
    const item = book(match[1]);
    const mark: Bookmark = { id: `bm${item.state.bookmarks.length + 1}`, chapterId: Number(body.chapterId), seconds: Number(body.seconds), note: String(body.note ?? ""), at: NOW_SECONDS, createdAt: NOW_SECONDS };
    item.state = { ...item.state, bookmarks: [...item.state.bookmarks, mark] };
    return mark;
  }],
  ["POST", /^\/api\/listen\/import\/preview$/, () => importPreview()],
  ["POST", /^\/api\/listen\/import$/, () => ({ id: "gac-xep", how: "new", chapters: 7 })],
  // Cài đặt.
  ["GET", /^\/api\/readaloud\/(vieneu|supertonic)$/, () => moduleStatus()],
  ["GET", /^\/api\/readaloud\/voice-speed$/, () => ({ choice: "auto", voices: [] })],
  ["GET", /^\/api\/readaloud\/online$/, () => [
    { id: "azure", name: "Microsoft Azure", limits: { max_chars: 3000, free: "500.000 ký tự / tháng", timings: "exact", region: true }, hasKey: false, masked: "", region: "", valid: false, voices: 0 },
  ]],
  ["GET", /^\/api\/readaloud\/cache$/, () => ({ book: 0, total: 148_000_000 })],
  ["GET", /^\/api\/sync$/, () => ({
    enabled: true, wanted: true, error: "", name: "Máy tính phòng khách", port: 47630, addresses: ["192.168.1.20"], awayAddresses: [], pairing: null,
    pairingBlocked: false, fingerprint: "3F2A 9C1B 77D0 E4A5", remoteStudio: false, bluetooth: null,
    devices: [{ id: "phone-ha", name: "Điện thoại của Hà", pairedAt: NOW_SECONDS - 40 * 86400, lastSeen: NOW_SECONDS - 600, studio: false }],
  })],
  ["GET", /^\/api\/computers$/, () => ({ name: "Máy tính phòng khách", computers: [] })],
  ["GET", /^\/api\/computers\/bluetooth$/, () => ({ devices: [] })],
  // Studio: trang dự án.
  ["GET", /^\/api\/books\/([^/]+)\/work$/, (match, _body, query) => (query.get("count") ? { count: workItems(book(match[1])).length } : { items: workItems(book(match[1])), counts: { speaker: 1, pronunciation: 1, gender: 1 } })],
  ["GET", /^\/api\/books\/([^/]+)\/review$/, (match) => reviewView(book(match[1]))],
  ["GET", /^\/api\/books\/([^/]+)\/edits-inbox$/, () => ({ devices: [], waiting: 0, recent: [], skipped: [] })],
  ["GET", /^\/api\/books\/([^/]+)\/parts$/, () => ({ parts: [] })],
  ["GET", /^\/api\/books\/([^/]+)\/continuation$/, () => { throw fail(404, "Chưa có chương mới để làm tiếp."); }],
  ["GET", /^\/api\/books\/([^/]+)\/precast$/, (match) => {
    const item = book(match[1]);
    const rows = chapterRows(item);
    const recorded = rows.filter((row) => row.playable);
    return {
      ready: true, wait: false, announcedAt: null, held: false, chapters: rows.length, recordedChapters: recorded.length,
      recordedThrough: recorded.length ? { id: recorded[recorded.length - 1].id, title: recorded[recorded.length - 1].fullTitle } : null,
      upcoming: rows.filter((row) => !row.playable).slice(0, 3).map((row) => ({ id: row.id, title: row.fullTitle })),
    };
  }],
  ["GET", /^\/api\/books\/([^/]+)\/narrator-mode$/, () => ({ available: true, mode: "narrator", castLocked: true, applied: true, plan: null })],
  ["GET", /^\/api\/books\/([^/]+)\/pronunciations$/, () => ({
    unseen: 0,
    items: [
      { surface: "Minh Khuê", spoken: "Minh Khuê", byListener: false, lines: 412, requested: null, example: { segmentId: 4003, chapterTitle: "Chương 4", seq: 2, text: "“Ông Tư ơi, ông còn thức không?”", hasAudio: true } },
      { surface: "Tư Lành", spoken: "Tư Lành", byListener: true, lines: 236, requested: null, example: null },
      { surface: "Hạnh", spoken: "Hạnh", byListener: false, lines: 61, requested: "Hạnh", example: null },
    ],
  })],
  ["GET", /^\/api\/books\/([^/]+)\/voices$/, (match, _body, query) => voiceChoices(book(match[1]), query.get("character") ?? "")],
  ["GET", /^\/api\/books\/([^/]+)\/shared-readings$/, () => ({ entries: [] })],
  ["GET", /^\/api\/books\/([^/]+)\/readings$/, () => ({ readings: [] })],
  ["GET", /^\/api\/readings$/, () => ({ entries: [] })],
  // Tab Kịch bản (studio/ScriptTab.tsx): mục lục chương + từng câu kèm người nói.
  ["GET", /^\/api\/books\/([^/]+)\/casting$/, (match) => ({
    castReady: true,
    chapters: chapterRows(book(match[1])).map((row) => ({ chapterId: row.id, index: row.index, title: row.fullTitle, lines: 23, speech: 9, hints: row.id === 4 ? 1 : 0, decided: 0 })),
  })],
  ["GET", /^\/api\/books\/([^/]+)\/casting\/stamp$/, () => ({ stamp: 1 })],
  ["GET", /^\/api\/books\/([^/]+)\/casting\/(\d+)$/, (match) => casting(book(match[1]), Number(match[2]))],
  ["GET", /^\/api\/music\/moods-model$/, () => ({ installed: false, downloading: false, progress: null, error: null, downloadable: true })],
  ["GET", /^\/api\/analysis-models$/, () => ({
    default: "qwen3.5:9b",
    reachable: true,
    models: [
      { name: "qwen3.5:9b", size: 6_600_000_000, parameters: "9.0B", quantization: "Q4_K_M" },
      { name: "abook-v4:latest", size: 5_200_000_000, parameters: "8.0B", quantization: "Q4_K_M" },
    ],
  })],
  ["GET", /^\/api\/export-jobs$/, () => ({ jobs: [] })],
  ["GET", /^\/api\/remote$/, () => ({ phones: [] })],
  ["POST", /^\/api\/player\/report$/, () => ({ commands: [], idle: true })],
  ["GET", /^\/api\/host\/opened$/, () => ({ opened: [] })],
];

export async function respond(path: string, method: string, body: Record<string, unknown>): Promise<Reply> {
  const url = new URL(path, "http://gallery.local");
  const state = galleryState.scenario.requests?.[url.pathname];
  if (method === "GET" && state === "loading") return never();
  if (method === "GET" && state === "error") return fail(503, "Bạn hãy thử lại sau một lát.");
  for (const [verb, pattern, handler] of ROUTES) {
    if (verb !== method) continue;
    const match = url.pathname.match(pattern);
    if (!match) continue;
    try {
      return new Reply(200, await handler(match, body, url.searchParams));
    } catch (error) {
      if (error instanceof Reply) return error;
      throw error;
    }
  }
  galleryState.missing.add(`${method} ${url.pathname}`);
  return fail(404, `Phòng trưng bày chưa giả đường ${method} ${url.pathname}`);
}

/** Thay `fetch` toàn cục: `/api/...` đi vào máy chủ giả, mọi thứ khác đi như thường. */
export function installDesktopApi(): void {
  const real = globalThis.fetch.bind(globalThis);
  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    // Phòng trưng bày không hỏi bản phát hành thật: ảnh và test phải độc lập với mạng / hạn mức GitHub.
    if (path === "https://api.github.com/repos/ntanhpro1221/ABook/releases/latest") {
      return new Response(JSON.stringify({ tag_name: "v0.4.138", html_url: "https://github.com/ntanhpro1221/ABook/releases/tag/v0.4.138", assets: [] }), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    const local = path.replace(/^https?:\/\/[^/]+/, "");
    if (!local.startsWith("/api/")) return real(input, init);
    const method = (init?.method ?? "GET").toUpperCase();
    const body = typeof init?.body === "string" && init.body ? (JSON.parse(init.body) as Record<string, unknown>) : {};
    const reply = await respond(local, method, body);
    return new Response(reply.body === undefined ? "" : JSON.stringify(reply.body), { status: reply.status, headers: { "Content-Type": "application/json" } });
  };
}

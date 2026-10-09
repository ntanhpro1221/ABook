// "Nhạc của tôi": nhạc người dùng tự nhập (abook/webui/music_local.py, docs/MUSIC_IMPORT.md). Phần thuần (không React) để thử riêng.

/** Một bài trong kho của máy (music_local.LocalMusic.info). `analysed` false = chưa có bộ phân tích âm thanh cho ra không khí
 *  của bài: máy không tự chọn nó, nhưng ghim tay được. */
export interface LocalTrack {
  link: string;
  title: string;
  creator: string;
  duration: number;
  analysed: boolean;
  name: string;
  album?: string;
  genre?: string;
  bytes: number;
  /** Đầu dò lời hát (chỉ bài đã phân tích bằng gói có `vox_head.npz`): xác suất 0..1 và cờ "có vẻ có lời". Bài có cờ thì máy không tự chọn nó
   *  làm nền dưới giọng đọc (ghim tay thì được). */
  vocals?: number;
  vocalsLikely?: boolean;
  /** Công tắc tự chọn của người dùng cho bài này: "on" = cho máy tự chọn dù có vẻ có lời, "off" = máy không bao giờ tự chọn (ghim tay thì được);
   *  vắng = mặc định (tự chọn được, trừ bài có vẻ có lời). */
  auto?: "on" | "off";
}

/** Một phần của mô-đun "Phân tích nhạc" (máy tính: công cụ đọc âm thanh, thư viện chạy model, model; điện thoại: thư viện chạy model, model). */
export interface MusicModulePart {
  id: string;
  label: string;
  bytes: number;
  /** current: đúng bản app này mang; outdated: đã tải nhưng app có bản mới hơn; missing: chưa tải. */
  state: "current" | "outdated" | "missing";
  /** Máy đã có sẵn phần này (không do mô-đun tải). */
  external?: boolean;
}

/** Mô-đun "Phân tích nhạc" (máy tính: webui/music_module.py; điện thoại: MusicStudentSetup.kt): nhập nhạc chạy không cần nó, nó chỉ cho
 *  máy NGHE nhạc để hiểu không khí của từng bài. Tải MỘT lần khi người dùng bấm - một nút, một tổng dung lượng, không bao giờ tự tải. */
export interface MusicModuleStatus {
  state: "missing" | "downloading" | "ready" | "outdated" | "error" | "unsupported";
  /** Đang tải: byte đã tải / tổng byte của lần tải này. Còn lại: `total` là dung lượng lần bấm kế sẽ tải. */
  done: number;
  total: number;
  /** Lý do tải hỏng, tiếng Việt; rỗng nếu không lỗi. */
  error: string;
  /** Bộ phân tích đã cắm (dùng được, kể cả khi có bản mới hơn). */
  ready: boolean;
  /** Máy này tải được không; không thì `reason` nói vì sao. */
  supported?: boolean;
  reason?: string;
  parts?: MusicModulePart[];
  /** Tên các phần có bản mới (state outdated) và số byte phải tải để cập nhật. */
  outdatedParts?: string[];
  outdatedBytes?: number;
  /** Có bản mới mà bản trên máy không chạy được (thiếu phần chạy model): phân tích nhạc đang tắt cho tới khi tải lại (điện thoại). */
  stopped?: boolean;
  /** Số bài đã phân tích bằng bản model cũ hơn: người dùng tự quyết có phân tích lại không. */
  stale?: number;
  /** Đang phân tích các bài đã nhập. */
  analysing: boolean;
  /** Máy đang dùng dữ liệu di động (tính phí). */
  metered: boolean;
  /** Thư viện mới chỉ dùng được sau khi mở lại app. */
  restart?: boolean;
  /** Lần tải vừa rồi bị người dùng huỷ (phần đã tải giữ, lần sau làm tiếp). */
  cancelled?: boolean;
  /** Có nút Huỷ khi đang tải (máy tính và điện thoại). */
  cancellable?: boolean;
  /** Chỉ máy tính. */
  precise?: PreciseMood;
  /** Chỉ máy tính: phần tuỳ chọn "Học sinh không khí cảnh". */
  scene?: SceneStudent;
}

/** Phần tuỳ chọn của "Phân tích nhạc" (webui/music_scene_student.py): model nhỏ đoán đoạn nào trong chương vui / căng hơn đoạn khác, tải khi người dùng bấm.
 *  `blocked` khác rỗng = máy này chưa tải được (lý do tiếng Việt). */
export interface SceneStudent {
  state: "current" | "outdated" | "missing";
  bytes: number;
  /** Cỡ lần tải khi bấm: gồm cả những phần của Phân tích nhạc máy còn thiếu (bằng `bytes` khi Phân tích nhạc đã đủ). */
  total?: number;
  blocked: string;
  external: boolean;
  /** Máy này dùng được phần này (có Studio để chạy nó); không thì `reason` nói vì sao và giao diện ẩn nút tải. */
  offered: boolean;
  reason: string;
}

/** "Đo cảm xúc nhạc chính xác hơn" (chỉ máy tính, webui/music_valence.py): tuỳ chọn tải thêm một model lớn, người dùng bật mới tải. `unavailable` = máy
 *  không bật được (ít RAM) - giao diện không mời. `working`: đang nghe kỹ lại các bài đã nhập (`pending` bài còn chờ). */
export interface PreciseMood {
  state: "unavailable" | "off" | "missing" | "downloading" | "error" | "ready";
  enabled: boolean;
  /** Đã có đủ file trên máy: bật không phải tải. */
  present: boolean;
  /** Đã tắt mà file còn trên đĩa: hiện nút "Xoá file". */
  removable: boolean;
  reason: string;
  bytes: number;
  done: number;
  total: number;
  error: string;
  working: boolean;
  pending: number;
  /** Lần tải vừa rồi bị huỷ (công tắc đã tắt, file dở giữ lại). */
  cancelled?: boolean;
}

export interface LocalMusicView {
  tracks: LocalTrack[];
  /** Đã có bộ phân tích âm thanh trên máy này chưa. */
  analyzer: boolean;
  /** Mô-đun "Phân tích nhạc" (cả máy tính lẫn điện thoại). */
  module?: MusicModuleStatus;
}

/** Dung lượng cho người đọc, MỘT hệ đơn vị thập phân (KB = 10^3, MB = 10^6, GB = 10^9 byte - như Hugging Face và nhà mạng ghi): dưới 1 MB ghi KB, MB làm tròn
 *  (một chữ số thập phân dưới 10 MB), từ 1 GB ghi GB hai chữ số thập phân. Số byte lấy từ máy chủ nên nhãn "(57 MB)" khớp cỡ thật của file. */
export function formatSize(bytes: number): string {
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(2).replace(".", ",")} GB`;
  const megabytes = bytes / 1e6;
  if (megabytes < 1) return `${Math.max(1, Math.round(bytes / 1e3))} KB`;
  return `${megabytes < 10 ? megabytes.toFixed(1).replace(".", ",") : Math.round(megabytes)} MB`;
}

/** Lời báo lần tải vừa rồi bị huỷ - đứng đầu câu mô tả của thẻ để người dùng biết chuyện gì đã xảy ra và lần sau thế nào. */
export const CANCELLED_NOTE = "Đã huỷ - lần tải sau làm tiếp từ chỗ dừng.";

export function modulePercent(module: Pick<MusicModuleStatus, "done" | "total">): number {
  return module.total > 0 ? Math.min(100, Math.floor((module.done / module.total) * 100)) : 0;
}

/** Câu báo về mô-đun, nói bằng điều người nghe cần biết (không nói model nào). */
export function moduleLabel(module: MusicModuleStatus): string {
  if (module.state === "error") return module.error;
  if (module.state === "downloading") return `Đang tải Phân tích nhạc (${formatSize(module.total)}, một lần) ${modulePercent(module)}%`;
  if (module.analysing) return "Đang nghe các bài bạn đã nhập để hiểu không khí của chúng…";
  if (module.state === "unsupported") return module.reason ? `Máy này chưa phân tích được nhạc: ${module.reason}.` : "Máy này chưa phân tích được nhạc.";
  if (module.state === "outdated" && module.stopped)
    return `Phân tích nhạc đang tắt: cần tải lại phần chạy (${formatSize(module.outdatedBytes ?? module.total)}) để phân tích nhạc. Bài của bạn vẫn nhập, nghe và ghim tay được.`;
  if (module.state === "outdated") return `${module.cancelled ? `${CANCELLED_NOTE} ` : ""}Phân tích nhạc có bản mới - ${formatSize(module.outdatedBytes ?? module.total)}. Bản đang dùng vẫn chạy bình thường.`;
  if (module.state === "ready") {
    if (module.restart) return "Phân tích nhạc đã cập nhật - mở lại ABook để dùng thư viện mới.";
    if ((module.stale ?? 0) > 0) return `${module.stale} bài được phân tích bằng bản cũ - vẫn dùng được, bạn có thể phân tích lại bằng bản mới.`;
    return "";
  }
  return `${module.cancelled ? `${CANCELLED_NOTE} ` : ""}Máy chưa nghe được nhạc của bạn để hiểu không khí của nó. Tải Phân tích nhạc một lần (${formatSize(module.total)}) để các bài nhập vào được phân tích ngay trên máy này; sau đó không cần mạng. Chưa tải thì bài của bạn vẫn nhập, nghe và ghim tay được.`;
}

/** Có mời người dùng bật "Đo cảm xúc nhạc chính xác hơn" không: máy đủ sức, và đã có bộ phân tích nhạc (nó dùng lại phần nghe của bộ ấy). */
export function preciseOffered(module: MusicModuleStatus | undefined): module is MusicModuleStatus & { precise: PreciseMood } {
  return Boolean(module?.precise && module.precise.state !== "unavailable" && module.ready);
}

/** Thẻ “Nhạc theo sát từng đoạn trong chương” (Học sinh không khí cảnh): hiện khi phần này chưa có trên máy - không đợi người dùng nhập bài hay tải Phân tích nhạc
 *  trước (tải model này kéo theo các phần còn thiếu, cỡ ghi ở `total`). `unavailable`: máy chưa dùng được thì thẻ nói lý do (không ẩn); rỗng = bấm tải được. */
export function sceneCard(module: MusicModuleStatus | undefined): { scene: SceneStudent; unavailable: string } | null {
  const scene = module?.scene;
  if (!scene || scene.state !== "missing") return null;
  const reason = scene.blocked || (scene.offered ? "" : scene.reason);
  return { scene, unavailable: reason ? reason[0].toUpperCase() + reason.slice(1) : "" };
}

/** Chữ trên nút tải của thẻ ấy: nói tải cái gì và cỡ thật; Phân tích nhạc còn thiếu thì nói tải cả nó. */
export function sceneButton(scene: SceneStudent): string {
  const total = scene.total ?? scene.bytes;
  return total > scene.bytes ? `Tải model nhạc theo đoạn cùng Phân tích nhạc (${formatSize(total)})` : `Tải model nhạc theo đoạn (${formatSize(scene.bytes)})`;
}

/** Đang tải hay đang nghe kỹ lại: giao diện hỏi lại view mỗi giây. */
export function preciseBusy(precise: PreciseMood | undefined): boolean {
  return precise?.state === "downloading" || Boolean(precise?.working);
}

/** Câu mô tả tuỳ chọn, nói bằng điều người nghe thấy. */
export function preciseLabel(precise: PreciseMood): string {
  const size = formatSize(precise.bytes);
  if (precise.state === "downloading") {
    const percent = precise.total > 0 ? Math.min(100, Math.floor((precise.done / precise.total) * 100)) : 0;
    return `Đang tải bộ đo cảm xúc chính xác hơn (${size}, một lần) ${percent}%`;
  }
  if (precise.state === "error") return precise.error;
  if (precise.state === "missing") return "Đã bật nhưng chưa tải xong - bài mới nhập tạm dùng số cũ.";
  if (precise.state === "ready") {
    if (precise.working) {
      return precise.pending > 0
        ? `Đang nghe kỹ ${precise.pending} bài bạn đã nhập - bài chưa tới lượt vẫn dùng số cũ.`
        : "Đang nghe kỹ bài vừa nhập…";
    }
    return "Đang bật - bài mới nhập sẽ được nghe kỹ ngầm vài giây.";
  }
  const how = precise.present ? "Chạy" : `Tải thêm ${size} một lần, sau đó chạy`;
  return `${precise.cancelled ? `${CANCELLED_NOTE} ` : ""}Máy nghe kỹ hơn từng bài bạn nhập để chọn nhạc nền hợp không khí truyện hơn. ${how} ngầm vài giây mỗi bài, không cần mạng.`;
}

export interface ImportResult extends LocalMusicView {
  added: LocalTrack[];
  existing: LocalTrack[];
  failed: string[];
}

export const LOCAL_PREFIX = "local:";

export function isLocal(link: string): boolean {
  return link.startsWith(LOCAL_PREFIX);
}

/** Mã sha1 (40 hex) của file trong link `local:<sha1>`; link khác dạng -> null. */
export function localDigest(link: string): string | null {
  const digest = isLocal(link) ? link.slice(LOCAL_PREFIX.length) : "";
  return /^[0-9a-f]{40}$/.test(digest) ? digest : null;
}

/** Đường "Nghe thử" một bài: bài của tôi qua kho của máy này, bài danh mục qua đường danh mục. */
export function previewPath(link: string): string {
  const digest = localDigest(link);
  return digest ? `/api/music/local/${digest}/file` : `/api/music/track?link=${encodeURIComponent(link)}`;
}

/** Bài này có vẻ có lời hát (đầu dò lời hát báo): hiện nhãn "Có vẻ có lời". */
export function hasVocals(track: Pick<LocalTrack, "analysed" | "vocalsLikely">): boolean {
  return track.analysed && track.vocalsLikely === true;
}

/** Nhãn khi máy không tự chọn bài này (có vẻ có lời hát, hay bạn đã tắt), hoặc bài có lời mà bạn cho tự chọn; bài bình thường thì không có nhãn. */
export function autoLabel(track: Pick<LocalTrack, "analysed" | "vocalsLikely" | "auto">): string | null {
  if (track.auto === "off") return "Máy không tự chọn bài này";
  if (!hasVocals(track)) return null;
  return track.auto === "on" ? "Có vẻ có lời - bạn cho máy tự chọn" : "Có vẻ có lời - máy không tự chọn bài này";
}

/** Nút đổi công tắc tự chọn của bài: chữ trên nút và giá trị `auto` gửi đi (null = về mặc định). */
export function autoSwitch(track: Pick<LocalTrack, "analysed" | "vocalsLikely" | "auto">): { text: string; next: "on" | "off" | null } {
  if (track.auto === "off") return { text: "Cho máy tự chọn lại", next: null };
  if (track.auto === "on") return { text: "Thôi, không cho máy tự chọn", next: null };
  return hasVocals(track) ? { text: "Vẫn cho máy tự chọn", next: "on" } : { text: "Đừng tự chọn bài này", next: "off" };
}

/** Trạng thái phân tích, nói bằng điều người nghe thấy (không nói model nào). */
export function analysisLabel(track: Pick<LocalTrack, "analysed">): string {
  return track.analysed ? "Đã phân tích - máy có thể tự chọn" : "Chưa phân tích - máy chưa tự chọn, bạn vẫn ghim được";
}

/** Lời giới thiệu "Nhạc của tôi" - MỘT câu cho mọi nơi nói về nó (tab Nhạc nền của dự án, Cài đặt, Sửa sách), kể cả chuyện bài ghim đi cùng file
 *  sách: người dùng không phải đoán chỗ này khác chỗ kia ra sao (soát UX a8 02-10). */
export const MY_MUSIC_INTRO =
  "Thêm nhạc của riêng bạn (mp3, m4a, ogg, opus, flac, wav) làm nhạc nền. File được chép vào kho nhạc của máy này. Bài nào bạn chọn cho một đoạn " +
  "(ở nút “Đổi bài”) đi cùng file sách (.abook / .abookproj), nên mở trên máy khác hay sang điện thoại vẫn nghe được - không ai khác tải được bài ấy. " +
  "ABook chỉ ghi tên bài và nghệ sĩ có sẵn trong file, không nói gì về giấy phép.";

/** Dòng chú thích của một bài trong danh sách "Đổi bài" của một đoạn: nhãn tự chọn (có vẻ có lời / bạn đã tắt), hợp không khí đoạn này, hay chưa phân tích
 *  - cùng nhãn với Cài đặt và tab Nhạc của dự án. Không có gì đáng nói thì undefined. */
export function mineNote(item: Pick<LocalTrack, "analysed" | "vocalsLikely" | "auto"> & { fits?: boolean }): string | undefined {
  const notes = [autoLabel(item), item.analysed ? (item.fits ? "Hợp không khí đoạn này" : null) : analysisLabel(item)].filter((note): note is string => Boolean(note));
  return notes.length ? notes.join(" · ") : undefined;
}

/** Gộp kết quả của nhiều lượt nhập (mỗi file một lượt, để thấy tiến độ). Danh sách bài lấy của lượt cuối. */
export function mergeImports(results: ImportResult[]): ImportResult {
  const last = results[results.length - 1];
  return {
    tracks: last?.tracks ?? [],
    analyzer: last?.analyzer ?? false,
    added: results.flatMap((result) => result.added),
    existing: results.flatMap((result) => result.existing),
    failed: results.flatMap((result) => result.failed),
  };
}

/** Câu báo sau khi nhập: nói rõ bao nhiêu bài đã vào, bao nhiêu đã có sẵn, file nào không nhập được và vì sao. */
export function importSummary(result: Pick<ImportResult, "added" | "existing" | "failed">): {
  kind: "success" | "warning" | "error";
  title: string;
  description?: string;
} {
  const { added, existing, failed } = result;
  const parts: string[] = [];
  if (added.length) parts.push(`${added.length} bài mới`);
  if (existing.length) parts.push(`${existing.length} bài đã có sẵn từ trước`);
  if (!added.length && !existing.length) {
    return { kind: "error", title: failed.length > 1 ? "Không nhập được file nào" : "Không nhập được file này", description: failed.join("\n") };
  }
  const title = `Đã nhập: ${parts.join(", ")}`;
  const unanalysed = added.filter((track) => !track.analysed).length;
  const notes: string[] = [];
  if (failed.length) notes.push(failed.join("\n"));
  if (unanalysed) notes.push(`${unanalysed} bài chưa phân tích - máy chưa tự chọn, bạn ghim được ở “Đổi bài”.`);
  return { kind: failed.length ? "warning" : "success", title, description: notes.join("\n") || undefined };
}

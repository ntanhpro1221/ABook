package vn.abook.player.ui.voice

/**
 * Việc của Giọng đọc với các lõi (VoiceModule, OnlineVoices, ReadAloud, MusicStore) - tách khỏi màn để thử bằng nguồn giả. Nguồn thật: [VoiceRepo]. Hàm suspend tự chạy ở
 * luồng nền; lỗi ném [VoiceFailure] (hay [IllegalStateException]) với câu đã sẵn cho người nghe. Không hàm nào trả hay ghi khoá thật: khoá đi xuống lõi một chiều.
 */
interface VoiceSource {
    // ---- giọng tải về máy (VoiceModule) ----

    suspend fun module(kind: ModuleKind): ModuleStatus

    /** Tải các lựa chọn `choices` (null: cập nhật phần đã cũ) trên luồng nền của lõi; trả trạng thái ngay sau khi bắt đầu. */
    suspend fun start(kind: ModuleKind, choices: List<String>?): ModuleStatus
    suspend fun cancel(kind: ModuleKind): ModuleStatus
    suspend fun measure(kind: ModuleKind): ModuleStatus

    /** Gỡ một lựa chọn (cuốn đang đọc bằng giọng vừa gỡ thì đọc tiếp bằng giọng mặc định). */
    suspend fun remove(kind: ModuleKind, choice: String): ModuleStatus

    /** Bấm "Dùng giọng ..." của lời đề nghị: mọi cuốn đang dùng giọng bắt đầu bằng `fromPrefix` và lựa chọn chung đổi sang giọng đầu tiên bắt đầu bằng `toPrefix` (không có thì giọng `fallback`). */
    suspend fun switchVoices(fromPrefix: String, toPrefix: String, fallback: String)

    // ---- khoá giọng trực tuyến (OnlineVoices) ----

    suspend fun providers(): List<KeyProvider>
    suspend fun saveKey(provider: String, key: String, region: String): KeyProvider
    suspend fun removeKey(provider: String): KeyProvider
    suspend fun checkKey(provider: String): KeyResult

    // ---- đồng ý gửi chữ (VoiceChoices.onlineOk) ----

    suspend fun consents(): Set<String>
    suspend fun allow(provider: String)

    // ---- nghe thử ----

    /** Đọc `text` bằng đúng giọng này (qua bộ đệm), trả đường file phát được. */
    suspend fun sample(voice: String, text: String): String

    // ---- Nhạc của tôi ----

    suspend fun tracks(): List<MusicTrack>

    /** Nhập các file `uris` (từng bản, một bản hỏng không làm hỏng cả lượt), báo (xong, tổng) sau mỗi bản. */
    suspend fun importMusic(uris: List<String>, progress: (done: Int, total: Int) -> Unit): MusicImportResult
    suspend fun removeTrack(link: String): List<MusicTrack>
}

/** Phát file mẫu: một lúc một mẫu; `onEnded` gọi khi phát hết (không gọi khi bị [stop]). Bản thật: [AndroidSamplePlayer]; test đưa bản giả (không bao giờ ra loa). */
interface SamplePlayer {
    fun play(path: String, onEnded: () -> Unit, onFailed: () -> Unit)

    /** Phát đoạn [startMs, endMs) của file (một câu trong file chương, Studio "Cần nghe lại"); `endMs` <= `startMs` = tới hết file. Bản mặc định phát cả file. */
    fun playRange(path: String, startMs: Int, endMs: Int, onEnded: () -> Unit, onFailed: () -> Unit) = play(path, onEnded, onFailed)

    fun stop()
}

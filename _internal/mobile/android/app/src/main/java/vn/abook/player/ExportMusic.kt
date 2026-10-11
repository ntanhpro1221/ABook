package vn.abook.player

import android.content.Context
import org.json.JSONObject
import java.io.File

/**
 * "Kèm nhạc nền" của một lượt xuất trên điện thoại ("Xuất M4B" sách đã có tiếng và "Xuất sách nói"): nhạc của cuốn sau lớp sửa
 * ([BookMusic.exportMusic]), bài thiếu tải về trước ([BookMusic.fetch], đúng đường tải sách), bộ trộn ([MusicExport.Mixer]) trên bộ đệm
 * PCM bài trong `cacheDir/music-pcm/<lượt>` và hằng số đo đỉnh sau mã hoá. [close] ở `finally` của lượt xuất: xoá bộ đệm.
 *
 * Không tích ô / sách không có nhạc: [mixer] và [guard] null - lượt xuất đi đường cũ y nguyên.
 */
class ExportMusic private constructor(
    val mixer: MusicExport.Mixer?,
    val guard: MusicRender.Params?,
    private val cache: TrackPcmCache?,
    /** Mục `music` đã áp lớp sửa (cho [BookMusic.pcmBytes] / dấu vân tay); null = không kèm nhạc. */
    val music: JSONObject?,
) : AutoCloseable {
    override fun close() {
        cache?.close()
    }

    companion object {
        /**
         * Nhạc cho lượt `run` của cuốn `bookId` ở các chương `chapterIds`. `wanted` = ô "Kèm nhạc nền". `fetching(i, N)`: đang tải bài thứ i
         * (từ 0) trong N bài thiếu; (N, N) = xong. Không lấy được bài thì mốc ấy bỏ, đếm vào [MusicExport.Mixer.missing].
         */
        fun open(context: Context, bookId: String, run: String, chapterIds: List<Int>, wanted: Boolean, stopped: () -> Boolean,
                 fetching: (Int, Int) -> Unit): ExportMusic {
            if (!wanted) return ExportMusic(null, null, null, null)
            MusicCues.mix = MusicMix.load(context)
            val music = BookMusic.exportMusic(bookId) ?: return ExportMusic(null, null, null, null)
            val dir = Store.bookDir(bookId)
            val missing = BookMusic.missing(dir, music)
            if (missing.isNotEmpty()) {
                // Sách mở từ file (không máy giữ) hay chưa ghép: không có chỗ tải, mốc của các bài ấy im.
                val link = runCatching { SyncLink.linkFor(context, bookId) }.getOrNull()?.takeIf { it.first.token.isNotBlank() }
                missing.forEachIndexed { index, track ->
                    if (stopped()) throw Mp3Export.Stopped()
                    fetching(index, missing.size)
                    if (link != null) BookMusic.fetch(dir, track) { name -> SyncLink.musicSource(context, link.first, link.second, name) }
                }
                fetching(missing.size, missing.size)
            }
            val guard = runCatching { MusicRender.Params.load(context) }.getOrNull()
                ?: throw Mp3Export.Refused("Không đọc được thiết lập nhạc nền của app - cài lại app rồi xuất lại")
            val cache = TrackPcmCache(File(context.cacheDir, "music-pcm/$run"), M4bAudio.trackDecoder({ File(it) }, stopped))
            // Chương một kênh: bù gộp theo đoạn phát của từng bài (music_export.Mixer._fold_offsets).
            val mixer = MusicExport.Mixer(BookMusic.chapterMusic(dir, music, chapterIds), cache, guard, M4bAudio.foldOffset(stopped))
            return ExportMusic(mixer, guard, cache, music)
        }

        /**
         * Nhạc từng chương của cuốn cho bản ước của hộp "Xuất sách nói" (chưa tải bài thiếu, chưa dựng bộ trộn) và chỗ trống thêm của bản kèm
         * nhạc: giọng PCM tạm của chương dài nhất + bộ đệm bài (giọng trên máy tối đa 48 kHz mono). Sách không có nhạc -> (rỗng, 0).
         */
        fun listenPlan(context: Context, bookId: String, chapters: List<ListenExport.Chapter>): Pair<Map<Int, MusicExport.ChapterMusic>, Long> {
            MusicCues.mix = MusicMix.load(context)
            val music = BookMusic.exportMusic(bookId) ?: return emptyMap<Int, MusicExport.ChapterMusic>() to 0L
            val dir = Store.bookDir(bookId)
            return BookMusic.chapterMusic(dir, music, chapters.map { it.id }) to listenBytes(dir, music, chapters)
        }

        fun listenBytes(dir: File, music: JSONObject, chapters: List<ListenExport.Chapter>): Long =
            ListenExport.voiceBytes(chapters) + BookMusic.pcmBytes(dir, music, 48_000, ListenExport.CHANNELS)
    }
}

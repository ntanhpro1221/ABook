package vn.abook.player.ui.components

import android.content.Context
import androidx.compose.foundation.text.TextAutoSize
import androidx.compose.foundation.text.modifiers.TextAutoSizeLayoutScope
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.sp
import java.io.File
import java.util.concurrent.Executor
import java.util.concurrent.Executors
import vn.abook.player.BuildConfig

/**
 * Cỡ chữ ĐÃ VỪA của bìa tự vẽ (tên sách thu cỡ cho vừa ô, nhãn tập thu cho vừa một dòng). `TextAutoSize.StepBased` tìm cỡ bằng nhiều lần dàn chữ thử (chia đôi ~6 lần mỗi ô)
 * ngay trong khung đầu tiên của Thư viện; kết quả là hàm thuần của (chữ, ràng buộc kích thước, mật độ + cỡ chữ hệ thống, kiểu chữ), nên lần trước tìm ra thì lần sau dùng lại,
 * không dàn thử nữa. [autoSize] bọc đúng `StepBased` ấy: chưa biết thì để `StepBased` tìm (cùng thuật toán, cùng kết quả) rồi nhớ lại; đã biết thì trả luôn.
 * Khoá lấy từ ràng buộc THẬT lúc đo, không từ lời nơi gọi, nên ô vuông / ô co giãn cũng đúng.
 *
 * Bộ nhớ nằm ở cacheDir (mất cũng chỉ tốn một lần dàn thử); tên tệp theo versionCode vì phông / kiểu chữ có thể đổi theo bản. Ghi ngoài luồng chính, gộp nhiều lần.
 */
internal class CoverFit(private val file: File?, private val io: Executor = WRITER) {
    private val sizes = object : LinkedHashMap<String, Float>(64, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, Float>?) = size > MAX_ENTRIES
    }
    private var loaded = false
    private var scheduled = false

    /** Số lần trả cỡ đã nhớ (test: lần dựng sau phải đúng là dùng bộ nhớ). */
    @Volatile
    internal var hits = 0
        private set

    /** Số mục đang nhớ (test). */
    @Synchronized
    internal fun size(): Int {
        load()
        return sizes.size
    }

    /** Cỡ (sp) đã vừa với khoá này, hoặc null nếu chưa biết. */
    @Synchronized
    fun get(key: String): Float? {
        load()
        return sizes[key]?.also { hits++ }
    }

    /** Ghi nhớ cỡ vừa; cỡ đã có y hệt thì không ghi lại. */
    fun put(key: String, size: Float) {
        synchronized(this) {
            load()
            if (sizes.put(key, size) == size || file == null || scheduled) return
            scheduled = true
        }
        io.execute(::write)
    }

    private fun load() {
        if (loaded) return
        loaded = true
        val lines = try { file?.takeIf { it.isFile }?.readLines() } catch (_: java.io.IOException) { null } ?: return
        for (line in lines) {
            val tab = line.indexOf('\t')
            if (tab <= 0) continue
            val size = line.substring(0, tab).toFloatOrNull() ?: continue
            sizes[unescape(line.substring(tab + 1))] = size
        }
    }

    private fun write() {
        val snapshot = synchronized(this) {
            scheduled = false
            sizes.entries.joinToString("") { "${it.value}\t${escape(it.key)}\n" }
        }
        val target = file ?: return
        try {
            val temp = File(target.path + ".tmp")
            temp.writeBytes(snapshot.toByteArray(Charsets.UTF_8))
            if (!temp.renameTo(target)) temp.delete()
        } catch (_: java.io.IOException) {
            // Bộ nhớ chỉ để nhanh hơn: không ghi được thì lần sau dàn thử lại.
        }
    }

    /** `StepBased` có nhớ cỡ: [kind] phân biệt kiểu chữ (tên / nhãn tập, cỡ lớn nhất) vì khoá không chứa kiểu chữ. */
    fun autoSize(kind: String, inner: TextAutoSize): TextAutoSize = RememberedAutoSize(this, kind, inner)

    private class RememberedAutoSize(private val store: CoverFit, private val kind: String, private val inner: TextAutoSize) : TextAutoSize {
        override fun TextAutoSizeLayoutScope.getFontSize(constraints: Constraints, text: AnnotatedString): TextUnit {
            val key = "$kind|${1.sp.toPx()}|${constraints.minWidth},${constraints.maxWidth},${constraints.minHeight},${constraints.maxHeight}|${text.text}"
            store.get(key)?.let { return it.sp }
            val size = with(inner) { getFontSize(constraints, text) }
            if (size.isSp) store.put(key, size.value)
            return size
        }

        override fun equals(other: Any?) = other is RememberedAutoSize && other.store === store && other.kind == kind && other.inner == inner
        override fun hashCode() = 31 * (31 * System.identityHashCode(store) + kind.hashCode()) + inner.hashCode()
    }

    companion object {
        private const val MAX_ENTRIES = 1024
        private val WRITER: Executor by lazy { Executors.newSingleThreadExecutor { runnable -> Thread(runnable, "cover-fit").apply { isDaemon = true } } }

        @Volatile
        private var shared: CoverFit? = null

        fun of(context: Context): CoverFit = shared ?: synchronized(this) {
            shared ?: CoverFit(File(context.applicationContext.cacheDir, "cover_fit_${BuildConfig.VERSION_CODE}.tsv")).also { shared = it }
        }

        /** Khoá nằm trên một dòng: xuống dòng / tab / gạch chéo trong tên sách được thoát. */
        internal fun escape(text: String): String =
            text.replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")

        internal fun unescape(text: String): String {
            if ('\\' !in text) return text
            val out = StringBuilder(text.length)
            var i = 0
            while (i < text.length) {
                val c = text[i]
                if (c == '\\' && i + 1 < text.length) {
                    when (text[i + 1]) {
                        'n' -> out.append('\n')
                        't' -> out.append('\t')
                        'r' -> out.append('\r')
                        else -> out.append(text[i + 1])
                    }
                    i += 2
                } else {
                    out.append(c)
                    i++
                }
            }
            return out.toString()
        }
    }
}

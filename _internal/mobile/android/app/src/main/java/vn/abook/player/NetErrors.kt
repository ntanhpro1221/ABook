package vn.abook.player

import androidx.annotation.OptIn
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.HttpDataSource
import java.io.EOFException
import java.net.ConnectException
import java.net.NoRouteToHostException
import java.net.PortUnreachableException
import java.net.SocketException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import javax.net.ssl.SSLException

/**
 * Lỗi mạng khi ghép, tải sách, nghe thẳng thành một câu người nghe hiểu, theo loại (soát a68 lỗi 4: trước đây giao diện hiện nguyên chữ
 * của Java - "Failed to connect to /10.0.2.2:47679", "Unable to parse TLS packet header", "Connection reset"). Chữ gốc vẫn đi kèm làm chi
 * tiết kỹ thuật ([technical]) - giao diện gập lại dưới lời báo (ErrorDetails).
 */
object NetErrors {
    /** Mã lỗi Capacitor khi máy kia trả 401: nó đã thôi ghép máy này (sync.py "Thiết bị chưa ghép nối") - không phải tắt máy hay khác mạng. */
    const val UNPAIRED = "UNPAIRED"

    enum class Kind { UNREACHABLE, DROPPED, SECURITY, TIMEOUT }

    /** Máy kia trả lời bằng lỗi HTTP `code` (>= 400) kèm lời của nó. */
    class Refused(val code: Int, message: String) : IllegalStateException(message)

    /** `error` hay một nguyên nhân của nó có phải 401 của máy kia (đã thôi ghép máy này) - lời gọi của app hay audio nghe thẳng (Media3). */
    @OptIn(UnstableApi::class)
    fun unpaired(error: Throwable): Boolean = generateSequence(error) { it.cause }.any {
        (it is Refused && it.code == 401) || (it is HttpDataSource.InvalidResponseCodeException && it.responseCode == 401)
    }

    /** Loại lỗi mạng của `error` (xét cả các lớp bọc - Media3 bọc vài lớp), null khi không phải lỗi mạng. */
    fun kind(error: Throwable): Kind? {
        for (cause in generateSequence(error) { it.cause }) {
            when (cause) {
                is SocketTimeoutException -> return Kind.TIMEOUT
                is ConnectException, is NoRouteToHostException, is UnknownHostException, is PortUnreachableException -> return Kind.UNREACHABLE
                // Android báo kết nối TLS bị cắt ngang ("Connection reset by peer", "Broken pipe") cũng bằng SSLException: đó là đứt mạng, không phải lỗi bảo mật.
                is SSLException -> return if (dropped(cause.message)) Kind.DROPPED else Kind.SECURITY
                is SocketException, is EOFException -> return Kind.DROPPED
            }
        }
        return null
    }

    private fun dropped(message: String?): Boolean {
        val text = message.orEmpty().lowercase()
        return listOf("connection reset", "broken pipe", "connection closed", "i/o error during system call").any { it in text }
    }

    /** Câu cho người nghe. `who`: máy ở đầu kia, như "máy tính NGDtuanh-Lecoo"; không biết thì "máy kia". */
    fun message(kind: Kind, who: String = ""): String {
        val other = who.ifBlank { "máy kia" }
        return when (kind) {
            Kind.UNREACHABLE -> "Chưa nối được $other — bạn mở ABook, kiểm tra cùng Wi-Fi và bật “Cho phép thiết bị khác kết nối qua Wi-Fi”."
            Kind.DROPPED -> "Kết nối với $other bị ngắt giữa chừng - thử lại"
            Kind.SECURITY -> "Địa chỉ của $other chưa đúng — bạn chép lại “Địa chỉ máy này” cạnh mã ghép trên máy kia."
            Kind.TIMEOUT -> "Hết giờ chờ $other trả lời - mạng chậm hay máy ấy đang bận, thử lại"
        }
    }

    /** Chữ gốc của lỗi cho mục "Chi tiết": lớp lỗi + lời của nó, kèm nguyên nhân sâu nhất nếu khác. */
    fun technical(error: Throwable): String {
        fun line(item: Throwable) = "${item.javaClass.simpleName}: ${item.message.orEmpty()}".trimEnd(' ', ':')
        val root = generateSequence(error) { it.cause }.last()
        return if (root === error) line(error) else "${line(error)} (${line(root)})"
    }
}

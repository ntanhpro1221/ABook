package vn.abook.player

import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Process
import org.json.JSONObject
import java.io.File

/**
 * Nối bộ phân tích trò ([MusicStudent]) vào điện thoại: giải mã bằng MediaCodec ([AndroidAudioDecoder]), tháp CLAP bằng ONNX Runtime
 * ([OrtClapTower]); gói model do [MusicStudentSetup] tải về `files/music/student`, thư viện ONNX Runtime ([OrtRuntime]) ở thư mục dùng chung ([SharedRuntime]). Việc phân tích chạy ở luồng của người gọi
 * (luồng nhập nhạc / luồng tải) hạ xuống ưu tiên nền - không bao giờ ở luồng giao diện.
 */
object AndroidMusicStudent {
    /** Thư mục gói đã đủ file (thư viện ONNX Runtime trong [ortFolder]) -> hàm phân tích cho [MusicStore.analyzer]. Gói hỏng / cấu hình lạ thì ném lỗi. */
    fun open(dir: File, ortFolder: File, cache: File): (File) -> JSONObject? {
        OrtRuntime.load(ortFolder)
        MusicMel.checkConfig(File(dir, "preprocessor_config.json").readText(Charsets.UTF_8))
        val student = MusicStudent(
            StudentHead.load(File(dir, "student_head_A.npz")),
            OrtClapTower(File(dir, "clap_audio_fp16.onnx")),
            AndroidAudioDecoder(File(cache, "music-pcm")),
        )
        return { file ->
            val before = Process.getThreadPriority(Process.myTid())
            Process.setThreadPriority(Process.THREAD_PRIORITY_BACKGROUND)
            try {
                student.analyze(file)
            } finally {
                Process.setThreadPriority(before)
            }
        }
    }

    /** Điện thoại THẬT đang dùng dữ liệu di động (mạng đang dùng có Internet qua sóng di động)? Thẻ tải nói "Điện thoại đang dùng dữ liệu di
     *  động", nên không có mạng nào phải là false - `isActiveNetworkMetered` lại trả true khi ấy (soát a66: lời báo hiện lúc mất mạng). */
    fun metered(context: android.content.Context): Boolean {
        val manager = context.getSystemService(android.content.Context.CONNECTIVITY_SERVICE) as? ConnectivityManager ?: return false
        val caps = manager.activeNetwork?.let { manager.getNetworkCapabilities(it) }
        return onMobileData(caps != null, caps?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) == true,
            caps?.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) == true)
    }

    /** Luật của [metered], tách ra để thử không cần Android: có mạng đang dùng, mạng ấy có Internet, và đi qua sóng di động. */
    internal fun onMobileData(network: Boolean, internet: Boolean, cellular: Boolean): Boolean = network && internet && cellular
}

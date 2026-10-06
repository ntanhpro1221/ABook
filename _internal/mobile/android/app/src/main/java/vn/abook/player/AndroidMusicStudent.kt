package vn.abook.player

import android.net.ConnectivityManager
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

    /** Mạng đang dùng tính phí (dữ liệu di động)? */
    fun metered(context: android.content.Context): Boolean =
        (context.getSystemService(android.content.Context.CONNECTIVITY_SERVICE) as? ConnectivityManager)?.isActiveNetworkMetered ?: false
}

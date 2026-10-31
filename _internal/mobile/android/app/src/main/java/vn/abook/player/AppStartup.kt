package vn.abook.player

import android.content.Context
import java.io.File

/**
 * Việc nạp / dọn một lần mỗi lần tiến trình dậy mà giao diện cần nhưng không thuộc màn nào: tên giọng người nghe thấy, kho nhạc cho phần nhập / phân tích nhạc, và dọn thư mục tạm
 * của lần nhập / chia sẻ / xuất bị bỏ dở lần trước. Gọi từ luồng nền (sau khung đầu của [vn.abook.player.ui.NativeActivity]); chạy lại trong cùng tiến trình thì bỏ qua.
 */
object AppStartup {
    @Volatile
    private var done = false

    @Synchronized
    fun run(context: Context) {
        if (done) return
        done = true
        val app = context.applicationContext
        val musicStore = DeviceMusic.store(app)
        LocalStudio.musicStore = musicStore
        LocalStudio.catalog = DeviceMusic.catalog(app)
        VoiceLabels.labels = VoiceLabels.load(app)
        // Bộ phân tích nhạc: "Gói nhạc" (model + thư viện ONNX Runtime) tải khi người dùng bấm (không bao giờ tự tải); đã có từ lần trước thì cắm luôn.
        val abi = OrtRuntime.deviceAbi()
        val runtime = SharedRuntime.of(app)
        val student = MusicStudentSetup(File(app.filesDir, MusicStudentSetup.FOLDER), musicStore, { AndroidMusicStudent.open(it, runtime.dir, app.cacheDir) },
            runtime, files = MusicStudentSetup.PACKAGE + OrtRuntime.parts(abi), supported = abi != null, metered = { AndroidMusicStudent.metered(app) })
        LocalStudio.student = student
        runCatching { student.attachIfPresent() }
        runCatching { TextImports.sweep() } // thư mục tạm của lần "Thêm sách từ file…" bị bỏ dở lần trước
        runCatching { BookFileImport.sweepCache(app.cacheDir) } // bản chép tạm `import-*.abook` của lần nhập bị giết giữa chừng
        runCatching { BookShare.sweep(app.cacheDir) } // file đã gửi qua "Chia sẻ…" lần trước: app nhận đã đọc xong từ lâu
        runCatching { ListenExports.sweep(app) } // chương tạm của "Xuất sách nói" cho cuốn đã xoá, hay bỏ dở quá 7 ngày
    }
}

package vn.abook.player

import android.os.Build
import android.os.Process
import vn.abook.player.PinnedFiles.Packed
import vn.abook.player.PinnedFiles.Part
import java.io.File

/**
 * Thư viện chạy ONNX Runtime của điện thoại: APK chỉ mang phần Java (`ai.onnxruntime`, chép nguyên từ onnxruntime-android [VERSION] -
 * chỉ `OnnxRuntime.java` khác bản gốc ở chỗ nạp thư viện); hai file native (`libonnxruntime.so` + `libonnxruntime4j_jni.so`, ~33 MB
 * trần / ~12 MB nén cho arm64) tải cùng "Gói nhạc" ([MusicStudentSetup]) vào `<thư mục gói>/ort/`, đúng ABI của máy. Bản dựng lại các
 * file này: `scripts/prepare_ort_runtime.py` (sinh luôn các dòng [Part] bên dưới); cách dựng + chỗ đặt: docs/MUSIC_IMPORT.md.
 */
object OrtRuntime {
    const val VERSION = "1.30.0"

    /** Thư mục con của thư mục gói mà hai file .so nằm trong. */
    const val FOLDER = "ort"
    private const val CORE = "libonnxruntime.so"
    private const val JNI = "libonnxruntime4j_jni.so"

    private fun part(abi: String, name: String, sha256: String, size: Long, packedSha256: String, packedSize: Long) =
        Part("$FOLDER/$name", sha256, size, remote = "$FOLDER/$VERSION/$abi/$name.gz", packed = Packed(packedSha256, packedSize), blocking = true, label = "Thư viện chạy model")

    // Ghim đúng như scripts/prepare_ort_runtime.py in ra (SHA-256 + cỡ của file thật và của bản nén gzip đặt trên máy chủ).
    private val BY_ABI: Map<String, List<Part>> = mapOf(
        "arm64-v8a" to listOf(
            part("arm64-v8a", CORE, "df5d25c72a868dca773597c71e2000756d43fe4d70ade516d3693c54e12e0ada", 32_990_480, "045291bd8f12b8dce4c033cddbfcea7ed113e297e713224872d3b43c4bb38625", 12_381_936),
            part("arm64-v8a", JNI, "0695257178815f8c58c1719ba07d6d5d91a2b339634328cca2a0a98aa7ff2952", 111_648, "41467ae99b2812b53da16e2f5645087c4db02ecb50f976c1d780506752f8ecda", 31_536),
        ),
        "armeabi-v7a" to listOf(
            part("armeabi-v7a", CORE, "d8c6e57af1848c4b9b2571a8864ac53592e57105dc67fb1e7b9e49828e555279", 23_311_344, "0508606d94dbdcf2efe1c40991d4ad3929beb21d554da6a3a408bd37f59050e9", 11_179_985),
            part("armeabi-v7a", JNI, "05c34d683a148da634af1997ee31aa4383307cf1daba0c890f15f2cfff2c3171", 81_584, "d9ead1ad66994f01a8ed4b5172c018dc0c0759cecb824bbf665513e838c10eca", 28_339),
        ),
        "x86_64" to listOf(
            part("x86_64", CORE, "f59d4d59d4c71532028d56ab6ca1dae62c3838c7982adfdad7f2560048b89ed9", 39_348_488, "7359474d6a4b70ba40a4bd04ec072dbf8bbcc1903359b0e153c06f65b370cd7b", 14_373_545),
            part("x86_64", JNI, "fba30194109597cca36512e86c8f30d18951a0bdaa177ea680b562f9d8ea77a2", 100_032, "d83ef3eccfbd54fdffa5f15065d4e809711838d8d23450b1a035351cd9a932a4", 29_478),
        ),
    )

    /** ABI của tiến trình này nếu có thư viện cho nó (không thì null: máy x86 32-bit... chưa chạy được bộ phân tích). */
    fun deviceAbi(): String? {
        val abis = if (Process.is64Bit()) Build.SUPPORTED_64_BIT_ABIS else Build.SUPPORTED_32_BIT_ABIS
        return abis.firstOrNull()?.takeIf { it in BY_ABI }
    }

    /** Các file phải tải cho [abi] (rỗng nếu ABI lạ). */
    fun parts(abi: String?): List<Part> = BY_ABI[abi].orEmpty()

    /**
     * Trỏ phần Java của ONNX Runtime tới thư mục chứa hai file .so đã tải ([gói]/ort) rồi nạp thử ngay, để gói hỏng/không hợp ABI lộ ra
     * lúc cắm bộ phân tích (xoá tải lại) chứ không phải giữa lúc phân tích một bài. Ném [IllegalStateException] nếu không nạp được.
     */
    fun load(packageDir: File) {
        System.setProperty("onnxruntime.native.path", File(packageDir, FOLDER).absolutePath)
        try {
            ai.onnxruntime.OrtEnvironment.getEnvironment()
        } catch (failure: Throwable) { // UnsatisfiedLinkError là Error, không phải Exception
            throw IllegalStateException("không nạp được thư viện ONNX Runtime (${failure.message ?: failure.javaClass.simpleName})", failure)
        }
    }
}

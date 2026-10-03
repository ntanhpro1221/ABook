package vn.abook.player

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import java.io.File
import java.nio.FloatBuffer
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledExecutorService
import java.util.concurrent.TimeUnit

/**
 * Tháp CLAP fp16 (`clap_audio_fp16.onnx`, 59 MB) chạy bằng ONNX Runtime trên CPU. Phiên nạp chậm ~nửa giây và chiếm bộ nhớ, nên mở
 * khi cần và đóng sau [IDLE_SECONDS] không dùng: nhập một lượt nhiều bài thì mở một lần, ngồi yên thì máy được trả bộ nhớ. Một cửa
 * sổ một lượt chạy (lô 1: đỉnh bộ nhớ thấp nhất; kết quả từng hàng không phụ thuộc cỡ lô).
 */
class OrtClapTower(private val model: File, private val threads: Int = min4(Runtime.getRuntime().availableProcessors())) : ClapTower {
    private var session: OrtSession? = null
    private var lastUse = 0L
    private val lock = Any()

    override fun embed(logMel: FloatArray): DoubleArray = synchronized(lock) {
        require(logMel.size == MusicMel.FRAMES * MusicMel.N_MELS) { "log-mel sai cỡ" }
        val environment = OrtEnvironment.getEnvironment()
        val active = session ?: environment.createSession(model.absolutePath, OrtSession.SessionOptions().apply {
            setIntraOpNumThreads(threads)
        }).also { session = it }
        try {
            OnnxTensor.createTensor(environment, FloatBuffer.wrap(logMel), longArrayOf(1, 1, MusicMel.FRAMES.toLong(), MusicMel.N_MELS.toLong())).use { input ->
                active.run(mapOf("input_features" to input)).use { result ->
                    @Suppress("UNCHECKED_CAST")
                    val rows = result[0].value as Array<FloatArray>
                    DoubleArray(rows[0].size) { rows[0][it].toDouble() }
                }
            }
        } finally {
            lastUse = System.nanoTime()
            scheduleRelease()
        }
    }

    private fun scheduleRelease() {
        RELEASER.schedule({
            synchronized(lock) {
                if (session != null && System.nanoTime() - lastUse >= TimeUnit.SECONDS.toNanos(IDLE_SECONDS)) close()
            }
        }, IDLE_SECONDS, TimeUnit.SECONDS)
    }

    fun close() = synchronized(lock) {
        runCatching { session?.close() }
        session = null
    }

    companion object {
        const val IDLE_SECONDS = 20L
        private fun min4(cores: Int) = cores.coerceIn(1, 4)
        private val RELEASER: ScheduledExecutorService = Executors.newSingleThreadScheduledExecutor { task ->
            Thread(task, "abook-ort-release").apply { isDaemon = true }
        }
    }
}

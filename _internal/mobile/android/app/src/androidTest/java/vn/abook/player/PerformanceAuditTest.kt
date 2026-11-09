package vn.abook.player

import android.content.Intent
import android.os.StrictMode
import android.view.accessibility.AccessibilityNodeInfo
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.Executors
import androidx.compose.ui.graphics.asAndroidBitmap
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.ui.data.CoverLoader

/** Opt-in main-thread I/O audit. Install the synthetic 60-book fixture before running with -e perfAudit true. */
class PerformanceAuditTest {
    @Test
    fun mainThreadIo() {
        assumeTrue(InstrumentationRegistry.getArguments().getString("perfAudit") == "true")
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        instrumentation.uiAutomation.serviceInfo = instrumentation.uiAutomation.serviceInfo.apply {
            flags = flags or android.accessibilityservice.AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS
        }
        val context = instrumentation.targetContext
        val violations = ConcurrentLinkedQueue<String>()
        val executor = Executors.newSingleThreadExecutor()
        var previous: StrictMode.ThreadPolicy? = null
        instrumentation.runOnMainSync {
            previous = StrictMode.getThreadPolicy()
            StrictMode.setThreadPolicy(StrictMode.ThreadPolicy.Builder()
                .detectDiskReads().detectDiskWrites().detectNetwork()
                .penaltyListener(executor) { violations.add(it.stackTraceToString()) }.build())
        }
        try {
            context.startActivity(Intent(context, vn.abook.player.ui.NativeActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK))
            click("book_cell")
            click("book_primary")
            val started = java.util.concurrent.CountDownLatch(1)
            val playing: (JSONObject) -> Unit = { if (it.optBoolean("playing")) started.countDown() }
            instrumentation.runOnMainSync {
                Playback.addListener(playing)
                if (Playback.isPlaying) started.countDown()
            }
            try {
                check(started.await(30, java.util.concurrent.TimeUnit.SECONDS)) { "Fixture did not start playing" }
            } finally {
                instrumentation.runOnMainSync { Playback.removeListener(playing) }
            }
            Thread.sleep(12_000)
            instrumentation.runOnMainSync { check(Playback.isPlaying) { "Fixture stopped during the periodic I/O audit" } }
            if (InstrumentationRegistry.getArguments().getString("auditEvents") == "true") {
                instrumentation.runOnMainSync { Playback.pause() }
                Thread.sleep(1_000)
                instrumentation.runOnMainSync {
                    check(!Playback.isPlaying) { "Pause did not settle" }
                    Playback.seekTo(60.0)
                }
                Thread.sleep(1_000)
                instrumentation.runOnMainSync { Playback.play() }
                Thread.sleep(1_000)
                instrumentation.runOnMainSync { check(Playback.isPlaying) { "Voice did not resume after the event audit" } }
            }
            instrumentation.uiAutomation.performGlobalAction(android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_BACK)
            Thread.sleep(1_000)
            click("tab_settings")
            click("tab_library")
        } finally {
            instrumentation.runOnMainSync { StrictMode.setThreadPolicy(previous!!) }
            executor.shutdown()
            executor.awaitTermination(5, java.util.concurrent.TimeUnit.SECONDS)
            val output = File(context.getExternalFilesDir(null), "perf165-strictmode.txt")
            output.writeText("violations=${violations.size}\n\n" + violations.joinToString("\n\n"))
            android.util.Log.i("Perf165", "StrictMode violations=${violations.size}; report=${output.path}")
        }
    }

    @Test
    fun coverDecode() = runBlocking {
        assumeTrue(InstrumentationRegistry.getArguments().getString("perfAudit") == "true")
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val folder = File(context.filesDir, "library/books")
        val files = folder.listFiles()!!.sortedBy { it.name }.map { File(it, "cover.jpg") }.filter { it.isFile }
        check(files.size == 60)
        val samples = JSONArray()
        val arguments = InstrumentationRegistry.getArguments()
        val repeats = arguments.getString("coverRepeats")?.toInt() ?: 3
        for (width in listOf(300, 840)) repeat(repeats) {
            val loader = CoverLoader(32 shl 20)
            var bytes = 0L
            System.gc()
            System.runFinalization()
            val nativeBefore = android.os.Debug.getNativeHeapAllocatedSize()
            val pssBefore = android.os.Debug.getPss()
            fun rssHighWaterKiB(): Long = File("/proc/self/status").useLines { rows ->
                rows.first { it.startsWith("VmHWM:") }.split(Regex("\\s+")).filter { it.isNotEmpty() }[1].toLong()
            }
            val rssHighWaterBefore = rssHighWaterKiB()
            val peakNative = java.util.concurrent.atomic.AtomicLong(nativeBefore)
            val peakPss = java.util.concurrent.atomic.AtomicLong(pssBefore)
            val sampling = java.util.concurrent.atomic.AtomicBoolean(true)
            val sampler = Thread {
                var polls = 0
                while (sampling.get()) {
                    peakNative.accumulateAndGet(android.os.Debug.getNativeHeapAllocatedSize(), ::maxOf)
                    if (polls++ % 20 == 0) peakPss.accumulateAndGet(android.os.Debug.getPss(), ::maxOf)
                    Thread.sleep(1)
                }
            }.apply { name = "cover-peak-sampler"; start() }
            val start = android.os.SystemClock.elapsedRealtimeNanos()
            try {
                for (file in files) {
                    val height = if (width == 300) 450 else 840
                    val image = loader.load(loader.key(file.path, file.lastModified(), width, height), file.path, width, height)!!
                    bytes += image.asAndroidBitmap().allocationByteCount
                    check(image.width >= width && image.height >= height)
                    peakNative.accumulateAndGet(android.os.Debug.getNativeHeapAllocatedSize(), ::maxOf)
                }
            } finally {
                sampling.set(false)
                sampler.join()
            }
            samples.put(JSONObject().put("width", width).put("bytes", bytes)
                .put("elapsedMs", (android.os.SystemClock.elapsedRealtimeNanos() - start) / 1e6)
                .put("nativeBeforeBytes", nativeBefore).put("sampledNativePeakBytes", peakNative.get())
                .put("pssBeforeKiB", pssBefore).put("sampledPssPeakKiB", peakPss.get())
                .put("rssHighWaterBeforeKiB", rssHighWaterBefore).put("rssHighWaterKiB", rssHighWaterKiB()))
            loader.trim()
        }
        File(context.getExternalFilesDir(null), "perf165-covers.json").writeText(samples.toString(2))
    }

    @Test
    fun closingDuringPreparationKeepsTheBookClosed() = runBlocking {
        assumeTrue(InstrumentationRegistry.getArguments().getString("perfAudit") == "true")
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        Store.init(context)
        val books = Store.playableBooks()
        check(books.size == 60) { "Install the synthetic fixture before this audit" }
        val request = checkNotNull(vn.abook.player.ui.data.PlayPlan.fromStore(books.first().getString("id")))
        val core = vn.abook.player.ui.data.AndroidPlaybackCore(context)
        instrumentation.runOnMainSync {
            core.load(request)
            core.close()
        }
        val scope = core.javaClass.getDeclaredField("scope").also { it.isAccessible = true }.get(core) as kotlinx.coroutines.CoroutineScope
        kotlinx.coroutines.withTimeout(30_000) {
            scope.coroutineContext[kotlinx.coroutines.Job]!!.children.toList().forEach { it.join() }
        }
        instrumentation.waitForIdleSync()
        instrumentation.runOnMainSync {
            check(Playback.bookId.isEmpty() && !Playback.isPlaying) { "A stale prepared load reopened the dismissed book" }
        }
    }

    private fun click(tag: String) {
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        val deadline = android.os.SystemClock.uptimeMillis() + 10_000
        while (android.os.SystemClock.uptimeMillis() < deadline) {
            val node = find(automation.rootInActiveWindow, tag)
            if (node != null) {
                val bounds = android.graphics.Rect()
                node.getBoundsInScreen(bounds)
                val now = android.os.SystemClock.uptimeMillis()
                val down = android.view.MotionEvent.obtain(now, now, android.view.MotionEvent.ACTION_DOWN, bounds.exactCenterX(), bounds.exactCenterY(), 0)
                val up = android.view.MotionEvent.obtain(now, now + 60, android.view.MotionEvent.ACTION_UP, bounds.exactCenterX(), bounds.exactCenterY(), 0)
                down.source = android.view.InputDevice.SOURCE_TOUCHSCREEN
                up.source = android.view.InputDevice.SOURCE_TOUCHSCREEN
                automation.injectInputEvent(down, true)
                automation.injectInputEvent(up, true)
                down.recycle()
                up.recycle()
                Thread.sleep(1_000)
                return
            }
            Thread.sleep(250)
        }
        error("Missing clickable tag: $tag")
    }

    private fun find(node: AccessibilityNodeInfo?, tag: String): AccessibilityNodeInfo? {
        node ?: return null
        if (node.viewIdResourceName == tag) return node
        for (i in 0 until node.childCount) find(node.getChild(i), tag)?.let { return it }
        return null
    }
}

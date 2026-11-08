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
            Thread.sleep(12_000)
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
        for (width in listOf(300, 840)) repeat(3) {
            val loader = CoverLoader(32 shl 20)
            var bytes = 0L
            val start = android.os.SystemClock.elapsedRealtimeNanos()
            for (file in files) {
                val height = if (width == 300) 450 else 840
                val image = loader.load(loader.key(file.path, file.lastModified(), width, height), file.path, width, height)!!
                bytes += image.asAndroidBitmap().allocationByteCount
            }
            samples.put(JSONObject().put("width", width).put("bytes", bytes)
                .put("elapsedMs", (android.os.SystemClock.elapsedRealtimeNanos() - start) / 1e6))
            loader.trim()
        }
        File(context.getExternalFilesDir(null), "perf165-covers.json").writeText(samples.toString(2))
    }

    @Test
    fun backgroundTicks() {
        assumeTrue(InstrumentationRegistry.getArguments().getString("perfAudit") == "true")
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        // The service's real sleep-button listener ignores tick events. UI is not attached in this process.
        val listener = SleepTimer.buttonsListener {}
        val samples = JSONArray()
        instrumentation.runOnMainSync {
            Playback.addListener(listener, ticks = false)
            try {
                repeat(100) { Playback.emit("tick") }
                repeat(5) {
                    val bytes = android.os.Debug.getRuntimeStat("art.gc.bytes-allocated").toLong()
                    val start = android.os.SystemClock.elapsedRealtimeNanos()
                    repeat(1_000) { Playback.emit("tick") }
                    samples.put(JSONObject().put("allocatedBytes", android.os.Debug.getRuntimeStat("art.gc.bytes-allocated").toLong() - bytes)
                        .put("elapsedMs", (android.os.SystemClock.elapsedRealtimeNanos() - start) / 1e6))
                }
            } finally {
                Playback.removeListener(listener)
            }
        }
        File(context.getExternalFilesDir(null), "perf165-ticks.json").writeText(samples.toString(2))
    }

    @Test
    fun readAlongGeometry() {
        assumeTrue(InstrumentationRegistry.getArguments().getString("perfAudit") == "true")
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val text = "Buổi sáng trời trong xanh. Con đường yên tĩnh chạy giữa hàng cây. Gió nhẹ thổi qua cửa sổ. Đây là văn bản tổng hợp dùng để đo cuộn chữ."
        val words = Regex("\\S+").findAll(text).mapIndexed { i, match ->
            vn.abook.player.ui.nowplaying.WordTiming(i * 100L, (i + 1) * 100L, match.range.first, match.range.last + 1)
        }.toList()
        val paragraph = vn.abook.player.ui.nowplaying.ReadParagraph(0, text, 0, 4_000, true, words)
        val measurer = androidx.compose.ui.text.TextMeasurer(
            androidx.compose.ui.text.font.createFontFamilyResolver(context),
            androidx.compose.ui.unit.Density(context.resources.displayMetrics.density, context.resources.configuration.fontScale),
            androidx.compose.ui.unit.LayoutDirection.Ltr,
        )
        val layout = measurer.measure(androidx.compose.ui.text.AnnotatedString(text),
            style = androidx.compose.ui.text.TextStyle(fontSize = androidx.compose.ui.unit.TextUnit(20f, androidx.compose.ui.unit.TextUnitType.Sp)),
            constraints = androidx.compose.ui.unit.Constraints(maxWidth = 900))
        val type = Class.forName("vn.abook.player.ui.nowplaying.ParagraphInk")
        val constructor = type.declaredConstructors.first().apply { isAccessible = true }
        repeat(20) { constructor.newInstance(layout, paragraph) }
        val samples = JSONArray()
        repeat(5) {
            val bytes = android.os.Debug.getRuntimeStat("art.gc.bytes-allocated").toLong()
            val start = android.os.SystemClock.elapsedRealtimeNanos()
            val retained = ArrayList<Any>(240)
            repeat(240) { retained += constructor.newInstance(layout, paragraph) }
            samples.put(JSONObject().put("paragraphs", retained.size).put("wordsPerParagraph", words.size)
                .put("elapsedMs", (android.os.SystemClock.elapsedRealtimeNanos() - start) / 1e6)
                .put("allocatedBytes", android.os.Debug.getRuntimeStat("art.gc.bytes-allocated").toLong() - bytes))
        }
        // Both implementations must keep exactly the same word-path bounds when requested.
        val ink = constructor.newInstance(layout, paragraph)
        val wordMethod = type.declaredMethods.firstOrNull { it.name == "word" }?.apply { isAccessible = true }
        val oldWords = type.declaredMethods.firstOrNull { it.name == "getWords" }?.apply { isAccessible = true }
        val bounds = JSONArray()
        for (i in words.indices) {
            val path = (wordMethod?.invoke(ink, i) ?: (oldWords!!.invoke(ink) as List<*>)[i]) as androidx.compose.ui.graphics.Path
            val box = path.getBounds()
            bounds.put(JSONArray(listOf(box.left, box.top, box.right, box.bottom)))
        }
        File(context.getExternalFilesDir(null), "perf165-geometry.json").writeText(JSONObject().put("samples", samples).put("wordBounds", bounds).toString(2))
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

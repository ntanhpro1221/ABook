package vn.abook.player

import android.app.Activity
import android.content.Intent
import android.os.Handler
import android.os.HandlerThread
import android.os.SystemClock
import android.view.FrameMetrics
import android.view.MotionEvent
import android.view.PixelCopy
import android.view.InputDevice
import android.graphics.Bitmap
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertTrue
import org.junit.Assert.assertNotNull
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.atomic.AtomicBoolean
import vn.abook.player.ui.data.Library
import vn.abook.player.ui.data.LibraryFilter
import vn.abook.player.ui.data.LibrarySort
import vn.abook.player.ui.data.LibraryState

/** The same probe runs against the saved baseline APK and the fixed APK. Seed 36 covered books first. */
@RunWith(AndroidJUnit4::class)
class LibraryTabFramesTest {
    private fun nodes(root: android.view.accessibility.AccessibilityNodeInfo?): List<android.view.accessibility.AccessibilityNodeInfo> {
        if (root == null) return emptyList()
        val found = mutableListOf(root)
        for (index in 0 until root.childCount) found.addAll(nodes(root.getChild(index)))
        return found
    }

    @Test fun tabFrames() {
        val inst = InstrumentationRegistry.getInstrumentation()
        val automation = inst.uiAutomation
        val args = InstrumentationRegistry.getArguments()
        val capturePixels = args.getString("pixels") == "1"
        val monitor = inst.addMonitor("vn.abook.player.ui.NativeActivity", null, false)
        inst.targetContext.startActivity(Intent().setClassName(inst.targetContext.packageName, "vn.abook.player.ui.NativeActivity")
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK))
        val activity = monitor.waitForActivityWithTimeout(10000) as Activity
        inst.removeMonitor(monitor)
        SystemClock.sleep(2500)
        automation.waitForIdle(200, 5000)
        var tabs = nodes(automation.rootInActiveWindow).filter { it.text?.toString() == "Thư viện" }
        val deadline = SystemClock.uptimeMillis() + 15000
        while (tabs.isEmpty() && SystemClock.uptimeMillis() < deadline) {
            SystemClock.sleep(200)
            tabs = nodes(automation.rootInActiveWindow).filter { it.text?.toString() == "Thư viện" }
        }
        assertTrue("Activity must expose the library tab", tabs.isNotEmpty())
        val libraryTab = tabs.last()
        var clickable: android.view.accessibility.AccessibilityNodeInfo? = libraryTab
        while (clickable != null && !clickable.isClickable) clickable = clickable.parent
        clickable?.performAction(android.view.accessibility.AccessibilityNodeInfo.ACTION_CLICK)
        SystemClock.sleep(600)
        assertTrue("Library filter row must be visible", nodes(automation.rootInActiveWindow).any { it.text?.toString() == "Tất cả" })
        val costs = JSONArray()
        var bookCount = 0
        inst.runOnMainSync {
            val app = activity.application as AbookApplication
            val books = (app.library.state.value as LibraryState.Ready).books
            bookCount = books.size
            assertTrue("Seed at least 30 covered books", books.size >= 30)
            repeat(10) {
                for (filter in LibraryFilter.entries) {
                    val start = System.nanoTime()
                    Library.view(books, filter, "", LibrarySort.Recent)
                    costs.put(JSONObject().put("filter", filter.ordinal).put("ms", (System.nanoTime()-start)/1e6))
                }
            }
        }
        File(inst.targetContext.getExternalFilesDir(null), "library-tab-cost-${args.getString("label") ?: "probe"}.json")
            .writeText(JSONObject().put("books", bookCount).put("viewCosts", costs).toString(2))
        val thread = HandlerThread("tab-frame-metrics").apply { start() }
        val results = JSONArray()
        val frames = CopyOnWriteArrayList<JSONObject>()
        var first = CountDownLatch(1)
        var tappedAt = 0L
        var firstDraw = 0L
        var indicatorChanged = 0L
        var contentChanged = 0L
        var before: IntArray? = null
        var indicatorY = 0
        val copying = AtomicBoolean(false)
        val width = activity.resources.displayMetrics.widthPixels
        val height = activity.resources.displayMetrics.heightPixels
        fun copyPixels(done: (IntArray) -> Unit) {
            val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
            PixelCopy.request(activity.window, bitmap, { result ->
                if (result == PixelCopy.SUCCESS) {
                    val pixels = IntArray(width * height)
                    bitmap.getPixels(pixels, 0, width, 0, 0, width, height)
                    done(pixels)
                }
                bitmap.recycle()
                copying.set(false)
            }, Handler(thread.looper))
        }
        val listener = android.view.Window.OnFrameMetricsAvailableListener { _, metric, lost ->
            val intended = metric.getMetric(FrameMetrics.INTENDED_VSYNC_TIMESTAMP)
            if (intended >= tappedAt && tappedAt > 0) {
                if (firstDraw == 0L) { firstDraw = metric.getMetric(FrameMetrics.VSYNC_TIMESTAMP); first.countDown() }
                frames.add(JSONObject().put("intendedNs", intended).put("totalNs", metric.getMetric(FrameMetrics.TOTAL_DURATION))
                    .put("deadlineNs", metric.getMetric(FrameMetrics.DEADLINE)).put("lostCallbacks", lost))
                if (capturePixels && (indicatorChanged == 0L || contentChanged == 0L) && copying.compareAndSet(false, true)) copyPixels { pixels ->
                    val old = before
                    if (old != null) {
                        val now = System.nanoTime()
                        fun changed(top: Int, bottom: Int) = (top until bottom).any { y ->
                            (0 until width step 2).any { x -> pixels[y*width+x] != old[y*width+x] }
                        }
                        if (indicatorChanged == 0L && changed(indicatorY, indicatorY + 6)) indicatorChanged = now
                        if (contentChanged == 0L && changed(indicatorY + 24, minOf(850, height))) contentChanged = now
                    }
                }
            }
        }
        inst.runOnMainSync { activity.window.addOnFrameMetricsAvailableListener(listener, Handler(thread.looper)) }
        inst.uiAutomation.executeShellCommand("dumpsys gfxinfo ${inst.targetContext.packageName} reset").close()
        val density = inst.targetContext.resources.displayMetrics.density
        // Coordinates are supplied by the evidence script from the baseline UI hierarchy.
        val xs = (args.getString("xs") ?: "80,232,410,570").split(',').map(String::toFloat)
        val y = (args.getString("y") ?: "332").toFloat()
        try {
            for (page in listOf(1,2,3,0,3,1,2,0,1,2,3,0)) {
                tappedAt = 0
                val copied = CountDownLatch(1)
                copyPixels { before = it; copied.countDown() }
                assertTrue(copied.await(3, TimeUnit.SECONDS))
                indicatorY = (200 until 450).maxBy { y -> (0 until width).count { x ->
                    val color = before!![y*width+x]
                    android.graphics.Color.red(color) > 150 && android.graphics.Color.green(color) in 70..190 && android.graphics.Color.blue(color) < 100
                } }
                frames.clear(); firstDraw = 0; indicatorChanged = 0; contentChanged = 0; first = CountDownLatch(1)
                val time = SystemClock.uptimeMillis()
                for (action in listOf(MotionEvent.ACTION_DOWN, MotionEvent.ACTION_UP)) {
                    if (action == MotionEvent.ACTION_UP) tappedAt = System.nanoTime()
                    val event = MotionEvent.obtain(time, SystemClock.uptimeMillis(), action, xs[page], y, 0)
                    event.source = InputDevice.SOURCE_TOUCHSCREEN
                    inst.sendPointerSync(event); event.recycle()
                    if (action == MotionEvent.ACTION_DOWN) SystemClock.sleep(40)
                }
                assertTrue("No frame after selecting page $page", first.await(3, TimeUnit.SECONDS))
                SystemClock.sleep(600)
                // Accessibility's cached selected flag can lag a rendered Compose frame.
                // Assert the actual amber indicator at the requested tab's pixel center.
                val bitmap = automation.takeScreenshot()!!
                val indicator = bitmap.getPixel(xs[page].toInt(), indicatorY)
                assertTrue("Touch did not render tab $page", android.graphics.Color.red(indicator) > 150 &&
                    android.graphics.Color.green(indicator) in 70..190 && android.graphics.Color.blue(indicator) < 100)
                bitmap.recycle()
                val row = JSONObject().put("page", page).put("touchToFirstFrameMs", (firstDraw-tappedAt)/1e6)
                    .put("indicatorY", indicatorY)
                    .put("indicatorChangeMs", if (indicatorChanged > 0) (indicatorChanged-tappedAt)/1e6 else -1)
                    .put("contentChangeMs", if (contentChanged > 0) (contentChanged-tappedAt)/1e6 else -1)
                    .put("frames", JSONArray(frames.toList())).put("density", density)
                results.put(row)
            }
        } finally {
            inst.runOnMainSync { activity.window.removeOnFrameMetricsAvailableListener(listener) }
            thread.quitSafely()
            File(inst.targetContext.getExternalFilesDir(null), "library-tab-frames-${args.getString("label") ?: "probe"}.json").writeText(results.toString(2))
            val descriptor = inst.uiAutomation.executeShellCommand("dumpsys gfxinfo ${inst.targetContext.packageName} framestats")
            File(inst.targetContext.getExternalFilesDir(null), "library-tab-gfxinfo-${args.getString("label") ?: "probe"}.txt")
                .writeText(android.os.ParcelFileDescriptor.AutoCloseInputStream(descriptor).bufferedReader().readText())
        }
    }
}

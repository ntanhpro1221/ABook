package vn.abook.player

import android.content.Intent
import android.graphics.Rect
import android.os.Handler
import android.os.HandlerThread
import android.os.SystemClock
import android.view.FrameMetrics
import android.view.InputDevice
import android.view.MotionEvent
import android.view.accessibility.AccessibilityNodeInfo
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.ViewRootForTest
import androidx.compose.ui.semantics.SemanticsNode
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.getOrNull
import android.view.View
import android.view.ViewGroup
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import vn.abook.player.ui.NativeActivity
import vn.abook.player.ui.data.*
import vn.abook.player.ui.screens.CastSamples
import vn.abook.player.ui.screens.castItems
import vn.abook.player.ui.screens.historyItems
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme
import vn.abook.player.ui.voice.SamplePlayer
import vn.abook.player.ui.components.rememberLazyFoldState
import java.io.File
import java.util.Collections

/** Measures production groups. Refuses physical devices; writes raw frame samples for independent analysis. */
@RunWith(AndroidJUnit4::class)
class ExpandGroupOnDeviceTest {
    @Test fun frames() {
        check(android.os.Build.HARDWARE in setOf("ranchu", "goldfish")) { "Emulator only" }
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val result = JSONArray()
        val thread = HandlerThread("expand-frames").apply { start() }
        val intent = Intent(context, NativeActivity::class.java).putExtra(NativeActivity.DEMO_BOOKS, 1)
        try {
            for (site in listOf("extras", "main", "history")) for (count in listOf(40, 200)) {
              ActivityScenario.launch<NativeActivity>(intent).use { activity ->
                Thread.sleep(2000)
                    val frames = Collections.synchronizedList(mutableListOf<JSONObject>())
                    val listener = android.view.Window.OnFrameMetricsAvailableListener { _, metrics, dropped ->
                        frames.add(JSONObject().put("vsync", metrics.getMetric(FrameMetrics.INTENDED_VSYNC_TIMESTAMP))
                            .put("total_ns", metrics.getMetric(FrameMetrics.TOTAL_DURATION))
                            .put("layout_ns", metrics.getMetric(FrameMetrics.LAYOUT_MEASURE_DURATION))
                            .put("draw_ns", metrics.getMetric(FrameMetrics.DRAW_DURATION)).put("dropped_reports", dropped))
                    }
                    activity.onActivity { screen ->
                        screen.window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                        screen.window.addOnFrameMetricsAvailableListener(listener, Handler(thread.looper))
                        screen.setContent {
                            AbookTheme(false) {
                                val people = remember(count, site) { (1..count).map { n ->
                                    CastMember("person_$n", "Person $n", null, "", 1, 3.0, CastVoice("v", "v", "Voice"), null, "1", null, null)
                                } }
                                val scope = rememberCoroutineScope()
                                val samples = remember { CastSamples("fixture", BookSource.None, object : SamplePlayer {
                                    override fun play(path: String, onEnded: () -> Unit, onFailed: () -> Unit) = Unit
                                    override fun stop() = Unit
                                }, scope) }
                                val now = System.currentTimeMillis() / 1000.0
                                val detail = remember(count, site) { BookDetail(DemoLibrary.books(1).first(), emptyList(), sessions = (1..count).map {
                                    ListenSession("session_$it", now - 10, now, 10.0, 1, 0.0, 1, 10.0)
                                }) }
                                val folds = rememberLazyFoldState()
                                LazyColumn(Modifier.fillMaxSize().background(Abook.colors.bg).statusBarsPadding().padding(horizontal = 20.dp)) {
                                    if (site == "history") historyItems(detail, true, { 1f }, folds) {}
                                    else castItems(CastView(Narrator("Voice", 0, 0.0, null, 0), if (site == "main") people else emptyList(), if (site == "extras") people else emptyList()),
                                        true, null, false, {}, samples, {}, { 1f }, folds)
                                }
                            }
                        }
                    }
                    instrumentation.waitForIdleSync()
                    Thread.sleep(1000)
                    val tag = when (site) { "main" -> "cast_main"; "history" -> "history_day_${S.s_hom_nay_e6747a82}"; else -> "cast_extras" }
                    var bounds: androidx.compose.ui.geometry.Rect? = null
                    fun node(item: SemanticsNode): SemanticsNode? {
                        if (item.config.getOrNull(SemanticsProperties.TestTag) == tag) return item
                        for (child in item.children) node(child)?.let { return it }
                        return null
                    }
                    fun view(item: View) {
                        if (item is ViewRootForTest) node(item.semanticsOwner.unmergedRootSemanticsNode)?.let { bounds = it.boundsInWindow }
                        if (item is ViewGroup) for (index in 0 until item.childCount) view(item.getChildAt(index))
                    }
                    activity.onActivity { view(it.window.decorView) }
                    val target = checkNotNull(bounds) { "Missing group header: $tag" }
                    repeat(8) { round ->
                        for (open in listOf(true, false)) {
                            frames.clear()
                            val touched = System.nanoTime()
                            val down = SystemClock.uptimeMillis()
                            for (action in listOf(MotionEvent.ACTION_DOWN, MotionEvent.ACTION_UP)) {
                                val event = MotionEvent.obtain(down, SystemClock.uptimeMillis(), action, target.center.x, target.center.y, 0)
                                event.source = InputDevice.SOURCE_TOUCHSCREEN
                                instrumentation.sendPointerSync(event)
                                event.recycle()
                                Thread.sleep(32)
                            }
                            Thread.sleep(800)
                            var expanded = false
                            fun expandedNode(item: View) {
                                if (item is ViewRootForTest) node(item.semanticsOwner.unmergedRootSemanticsNode)?.let {
                                    expanded = it.config.getOrNull(SemanticsActions.Collapse) != null
                                }
                                if (item is ViewGroup) for (index in 0 until item.childCount) expandedNode(item.getChildAt(index))
                            }
                            activity.onActivity { expandedNode(it.window.decorView) }
                            check(expanded == open) { "Tap did not ${if (open) "open" else "close"} $site/$count/$round" }
                            if (round >= 2) {
                                val measured = synchronized(frames) { frames.filter { it.getLong("vsync") >= touched }.toList() }
                                if (measured.isEmpty()) {
                                    val diagnostic = synchronized(frames) { frames.toList() }
                                    File(context.filesDir, "expand-diagnostic.json").writeText("touch=$touched target=$target raw=$diagnostic")
                                    File(context.filesDir, "expand-diagnostic.png").outputStream().use { output ->
                                        instrumentation.uiAutomation.takeScreenshot().compress(android.graphics.Bitmap.CompressFormat.PNG, 100, output)
                                    }
                                    error("No frames for $site/$count/$open touch=$touched raw=$diagnostic")
                                }
                                result.put(JSONObject().put("site", site).put("rows", count).put("open", open).put("round", round)
                                    .put("touch_ns", touched).put("frames", JSONArray(measured)))
                            }
                        }
                    }
                    activity.onActivity { it.window.removeOnFrameMetricsAvailableListener(listener) }
                }
            }
        } finally {
            thread.quitSafely()
            File(context.filesDir, "expand-frames.json").writeText(result.toString(2))
        }
    }
}

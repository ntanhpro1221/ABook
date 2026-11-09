package vn.abook.player

import android.content.Intent
import android.os.Debug
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.ui.Modifier
import androidx.compose.runtime.*
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import vn.abook.player.ui.NativeActivity
import vn.abook.player.ui.nowplaying.FakeNowPlayingModel
import vn.abook.player.ui.nowplaying.PlayerSheets
import vn.abook.player.ui.nowplaying.PlayerSheet
import vn.abook.player.ui.nowplaying.rememberNowPlayingWindowState
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme
import java.io.File

/** Run only on the task's headless emulator. No media service, network, model or speaker output. */
@RunWith(AndroidJUnit4::class)
class AudioFxOnDeviceTest {
    @Test fun screenshotsAndCpu() {
        val instrumentation=InstrumentationRegistry.getInstrumentation()
        val context=instrumentation.targetContext
        check(android.os.Build.FINGERPRINT.contains("generic") || android.os.Build.MODEL.contains("sdk")) { "Emulator only" }
        val settings=AudioFxSettings(enabled=true,boost=6.0,pitch=-1.5).withPreset(1)
        AudioFx.init(context)
        val intent=Intent(context,NativeActivity::class.java).putExtra(NativeActivity.DEMO_BOOKS,3)
        ActivityScenario.launch<NativeActivity>(intent).use { activity ->
            for(dark in listOf(false,true)) {
                activity.onActivity { screen ->
                    AudioFx.update(settings)
                    screen.setContent { key(dark) { AbookTheme(dark) {
                        val model = remember { FakeNowPlayingModel(FakeNowPlayingModel.demoState()) }
                        val window = rememberNowPlayingWindowState()
                        LaunchedEffect(Unit) { window.openSheet(PlayerSheet.Audio) }
                        Box(Modifier.fillMaxSize().background(Abook.colors.bg).statusBarsPadding().navigationBarsPadding()) {
                            PlayerSheets(model.state.value, model, window)
                        }
                    } } }
                }
                instrumentation.waitForIdleSync()
                Thread.sleep(600)
                val file=File(context.filesDir,"audiofx-${if(dark)"dark" else "light"}.png")
                val screenshot=instrumentation.uiAutomation.takeScreenshot()
                // Reject an empty scene: the sheet's text/controls must occupy the body, excluding OS bars.
                val background=screenshot.getPixel(10,screenshot.height/2)
                var ink=0
                for(y in screenshot.height/4 until screenshot.height*3/4 step 3) for(x in 20 until screenshot.width-20 step 3) {
                    val pixel=screenshot.getPixel(x,y)
                    if(kotlin.math.abs(android.graphics.Color.red(pixel)-android.graphics.Color.red(background))>80) ink++
                }
                assertTrue("Audio sheet must be painted before capturing ($ink ink samples)",ink>500)
                file.outputStream().use { screenshot.compress(android.graphics.Bitmap.CompressFormat.PNG,100,it) }
                assertTrue(file.length()>1000)
                instrumentation.uiAutomation.executeShellCommand("input swipe 450 1750 450 850 350").close()
                Thread.sleep(500)
                File(context.filesDir,"audiofx-${if(dark)"dark" else "light"}-bottom.png").outputStream().use {
                    instrumentation.uiAutomation.takeScreenshot().compress(android.graphics.Bitmap.CompressFormat.PNG,100,it)
                }
            }
        }
        val frame=doubleArrayOf(.1,.1)
        val report=StringBuilder("Emulator, 48 kHz stereo PCM, thread CPU time; no decoder/AudioTrack/model. Warm 10 s each, then 5 alternating rounds.\n")
        val times=mapOf(false to mutableListOf<Double>(),true to mutableListOf<Double>())
        for(round in 0..5) for(enabled in if(round%2==0) listOf(false,true) else listOf(true,false)) {
            val dsp=AudioFxDsp(48000,2);dsp.configure(settings.copy(enabled=enabled))
            val started=Debug.threadCpuTimeNanos()
            for(i in 0 until 48000*10) {frame[0]=.1;frame[1]=.1;dsp.process(frame)}
            val ms=(Debug.threadCpuTimeNanos()-started)/1e6
            if(round>0) times.getValue(enabled).add(ms)
            assertTrue(frame.all { it.isFinite() && kotlin.math.abs(it)<1 })
        }
        for((enabled,values) in times) report.append("enabled=$enabled cpu_ms=$values median_core_percent=${values.sorted()[2]/100}\n")
        File(context.filesDir,"audiofx-cpu.txt").writeText(report.toString())
    }
}

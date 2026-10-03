package vn.abook.player

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Build
import android.os.PowerManager
import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * [VieneuBench] as an instrumented test: copies the pushed pack (`/data/local/tmp/vneu`, see `scripts/vieneu_phone_bench.sh`) into the app's
 * `files/vneu` (an app cannot load a .so from /data/local/tmp) and runs the checks and the speed run with instrumentation arguments (`-e name value`).
 * Results: logcat tag VNEU and `files/vneu-results.jsonl`. A phone whose app freezer stops an instrumented app that is not in front (ColorOS)
 * cannot use this; [VieneuBenchMain] runs the same code from `app_process` instead.
 */
@RunWith(AndroidJUnit4::class)
class VieneuBenchTest {
    private val context: Context = InstrumentationRegistry.getInstrumentation().targetContext
    private val args: Map<String, String> = InstrumentationRegistry.getArguments().let { bundle -> bundle.keySet().associateWith { bundle.getString(it).orEmpty() } }
    private val pack = File(context.filesDir, "vneu")

    private fun bench(): Pair<VieneuBench, JSONObject> {
        val source = File(args["pack"] ?: "/data/local/tmp/vneu")
        assumeTrue("no pack in ${source.path} (scripts/vieneu_phone_bench.sh push)", File(source, "${args["bundle"] ?: "bundle"}/manifest.json").isFile)
        source.walkTopDown().filter { it.isFile }.forEach { from ->
            val to = File(pack, from.relativeTo(source).path)
            if (to.length() != from.length()) {
                to.parentFile!!.mkdirs()
                from.copyTo(to, overwrite = true)
            }
            if (to.name.endsWith(".so")) to.setReadOnly()
        }
        val bench = VieneuBench(args, pack, File(context.filesDir, "vneu-results.jsonl"), File(context.filesDir, "vneu-out"), { Log.i("VNEU", it) }, ::platformThermal)
        return bench to bench.manifest()
    }

    private fun platformThermal(): JSONObject {
        val power = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        val battery = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        return JSONObject().put("thermalStatus", if (Build.VERSION.SDK_INT >= 29) power.currentThermalStatus else -1)
            .put("headroom10s", if (Build.VERSION.SDK_INT >= 30) power.getThermalHeadroom(10).toDouble().let { if (it.isNaN()) JSONObject.NULL else it } else JSONObject.NULL)
            .put("batteryC", (battery?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1) ?: -1) / 10.0)
    }

    @Test
    fun theTurboLoopRepeatsTheDesktop() = bench().let { (bench, manifest) -> println("VIENEU_TURBO_PARITY\n" + bench.checkTurbo(manifest)) }

    @Test
    fun theNanoLoopRepeatsTheDesktop() = bench().let { (bench, manifest) -> println("VIENEU_NANO_PARITY\n" + bench.checkNano(manifest)) }

    @Test
    fun speed() = bench().let { (bench, manifest) -> bench.speed(manifest) }

    @Test
    fun sustain() = bench().let { (bench, manifest) -> bench.sustain(manifest) }
}

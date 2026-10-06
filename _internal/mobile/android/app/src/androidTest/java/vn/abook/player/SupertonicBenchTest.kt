package vn.abook.player

import android.content.Context
import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * [SupertonicBench] as an instrumented test: copies the pushed pack (`/data/local/tmp/stonic`, see `scripts/supertonic_phone_bench.sh`) into the
 * app's `files/stonic` (an app cannot load a .so from /data/local/tmp) and times the paragraphs of supertonic_bench.json (an androidTest asset).
 * Arguments `-e threads 1,2,4 -e passes 2`. Results: logcat tag STONIC and `files/stonic-results.jsonl`. Built with `-PbenchAppId=...` the
 * script installs it under its own package, so it never replaces or wipes the real app.
 */
@RunWith(AndroidJUnit4::class)
class SupertonicBenchTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context: Context = instrumentation.targetContext
    private val args: Map<String, String> = InstrumentationRegistry.getArguments().let { bundle -> bundle.keySet().associateWith { bundle.getString(it).orEmpty() } }

    private fun bench(): SupertonicBench {
        val source = File(args["pack"] ?: "/data/local/tmp/stonic")
        assumeTrue("no pack in ${source.path} (scripts/supertonic_phone_bench.sh push)", File(source, "model/onnx/tts.json").isFile)
        val pack = File(context.filesDir, "stonic")
        source.walkTopDown().filter { it.isFile }.forEach { from ->
            val to = File(pack, from.relativeTo(source).path)
            if (to.length() != from.length()) {
                to.parentFile!!.mkdirs()
                from.copyTo(to, overwrite = true)
            }
            if (to.name.endsWith(".so")) to.setReadOnly()
        }
        return SupertonicBench(args, pack, File(context.filesDir, "stonic-results.jsonl"), File(context.filesDir, "stonic-out")) { Log.i("STONIC", it) }
    }

    private fun asset(name: String) = JSONObject(instrumentation.context.assets.open(name).use { String(it.readBytes(), Charsets.UTF_8) })

    @Test
    fun speed() = bench().run(asset("supertonic_bench.json"))

    /** Styles, ids and one chunk of audio against the desktop's (supertonic.json, scripts/supertonic_android_fixtures.py). */
    @Test
    fun parity() = println("SUPERTONIC_PARITY\n" + bench().parity(asset("supertonic.json")))
}

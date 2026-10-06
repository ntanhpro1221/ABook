package vn.abook.player

import org.json.JSONObject
import java.io.File

/**
 * [SupertonicBench] from the shell, installing nothing: `app_process` runs it as the shell user with both APKs on the class path
 * (`scripts/supertonic_phone_bench.sh <serial> app threads=1,2,4`) - for phones whose app freezer stalls an instrumented app (ColorOS). Arguments:
 * `name=value` pairs of [SupertonicBench] plus `pack=` (default /data/local/tmp/stonic, which also holds supertonic_bench.json). Results go to
 * `<pack>/results.jsonl`, phone-made audio to `<pack>/out/`.
 */
object SupertonicBenchMain {
    @JvmStatic
    fun main(argv: Array<String>) {
        val args = argv.associate { it.substringBefore('=') to it.substringAfter('=', "") }
        val pack = File(args["pack"] ?: "/data/local/tmp/stonic")
        SupertonicBench(args, pack, File(pack, "results.jsonl"), File(pack, "out")) { println(it) }
            .run(JSONObject(File(pack, "supertonic_bench.json").readText(Charsets.UTF_8)))
        println("STONIC_FINISHED")
        System.exit(0)
    }
}

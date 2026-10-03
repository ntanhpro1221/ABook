package vn.abook.player

import java.io.File

/**
 * [VieneuBench] from the shell, without installing anything: the phone's `app_process` runs it as the shell user with both APKs on the class path
 * (`scripts/vieneu_phone_bench.sh app check|speed`). Arguments: `check` or `speed`, then `name=value` pairs of [VieneuBench] plus `pack=` (default
 * /data/local/tmp/vneu). Results go to `<pack>/results.jsonl`, phone-made audio to `<pack>/out/`.
 */
object VieneuBenchMain {
    @JvmStatic
    fun main(argv: Array<String>) {
        val mode = argv.firstOrNull() ?: "speed"
        val args = argv.drop(1).associate { it.substringBefore('=') to it.substringAfter('=', "") }
        val pack = File(args["pack"] ?: "/data/local/tmp/vneu")
        val bench = VieneuBench(args, pack, File(pack, "results.jsonl"), File(pack, "out"), { println(it) })
        val manifest = bench.manifest()
        when (mode) {
            "check" -> {
                println(bench.checkTurbo(manifest))
                println(bench.checkNano(manifest))
            }
            "check-turbo" -> println(bench.checkTurbo(manifest))
            "speed" -> bench.speed(manifest)
            "sustain" -> bench.sustain(manifest)
            else -> error("unknown mode $mode")
        }
        println("VNEU_FINISHED $mode")
        System.exit(0)
    }
}

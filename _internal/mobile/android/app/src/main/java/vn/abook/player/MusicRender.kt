package vn.abook.player

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.math.BigDecimal
import java.math.RoundingMode
import kotlin.math.abs
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow

/**
 * Bộ dựng nhạc nền NGOẠI TUYẾN cho xuất sách nói trên điện thoại - port 1-1 của bản tham chiếu `abook/webui/music_render.py`
 * (PHONE_EXPORT_MIX.md mục 1-4), kiểm bằng cùng fixture `tests/fixtures/music_render` (int16 lệch <= 1 LSB, g lệch <= 1e-9).
 *
 * Âm thanh là mảng double XEN KẼ KÊNH (khung `f`, kênh `c` ở `f * channels + c`), đã ở tần số/kênh của chương. Mọi phép tính giữ
 * đúng thứ tự cộng của bản Python; mọi `round(giây * rate)` là [Math.rint] (chẵn gần nhất như Python), KHÔNG `Math.round`.
 *
 * 1. [renderBus]: bus nhạc từ dòng thời gian của `music_timeline` - mẫu chương `k` trong [round(from*rate), min(round(to*rate), n))
 *    đọc mẫu bài `round(position*rate) + (k - round(from*rate))` (`loop`: modulo độ dài file; không thì ngoài file = 0), nhân biên
 *    độ nội suy TUYẾN TÍNH THEO BIÊN ĐỘ giữa các điểm `gain` (None = 0), cộng theo thứ tự dòng thời gian.
 * 2. [GuardStream]: chặn đỉnh CHỈ trên bus nhạc, ra `voice + g * bus` (g chung mọi kênh), trần `exportCeilingDbtp -
 *    exportGuardHeadroomDb` theo đỉnh thật nội suy x4 (`truePeakFir`), nhìn trước `exportGuardAttackMs`, nhả `exportGuardReleaseMs`.
 * 3. [toInt16]: clip(rint(x * 32768)).
 */
object MusicRender {
    const val FIR_TAPS = 12
    const val FIR_PHASES = 4
    const val FIR_LEFT = 5          // pha p dùng x[n-5 .. n+6]
    const val SUPPORT = FIR_TAPS / 2 // need2 = min need trong +-6 mẫu (chân bộ lọc)

    /** Hằng số xuất của `music_mix.json` (máy tính đọc cùng file; không chép tay). */
    class Params(
        val ceilingDbtp: Double,
        val headroomDb: Double,
        val attackMs: Double,
        val releaseMs: Double,
        val fir: Array<DoubleArray>,
    ) {
        companion object {
            fun parse(json: JSONObject): Params {
                val table = json.getJSONArray("truePeakFir")
                require(table.length() == FIR_PHASES) { "truePeakFir: cần $FIR_PHASES pha" }
                val fir = Array(FIR_PHASES) { p ->
                    val row = table.getJSONArray(p)
                    require(row.length() == FIR_TAPS) { "truePeakFir[$p]: cần $FIR_TAPS hệ số" }
                    DoubleArray(FIR_TAPS) { row.getDouble(it) }
                }
                return Params(
                    json.getDouble("exportCeilingDbtp"), json.getDouble("exportGuardHeadroomDb"),
                    json.getDouble("exportGuardAttackMs"), json.getDouble("exportGuardReleaseMs"), fir,
                )
            }

            fun load(context: Context): Params = context.assets.open(MusicMix.FILE).use {
                parse(JSONObject(it.readBytes().toString(Charsets.UTF_8)))
            }
        }
    }

    /** Một phần tử dòng thời gian `{track, from, to, position, gain [[giây, dB|null]], loop?}`; `gainDb` null = câm. */
    class Element(
        val track: String,
        val from: Double,
        val to: Double,
        val position: Double,
        val gainAt: DoubleArray,
        val gainDb: Array<Double?>,
        val loop: Boolean = false,
    ) {
        companion object {
            fun parse(json: JSONObject): Element {
                val gain = json.getJSONArray("gain")
                return Element(
                    json.getString("track"), json.getDouble("from"), json.getDouble("to"), json.getDouble("position"),
                    DoubleArray(gain.length()) { gain.getJSONArray(it).getDouble(0) },
                    Array(gain.length()) { gain.getJSONArray(it).let { p -> if (p.isNull(1)) null else p.getDouble(1) } },
                    json.optBoolean("loop", false),
                )
            }

            fun parseAll(json: JSONArray): List<Element> = List(json.length()) { parse(json.getJSONObject(it)) }
        }
    }

    /** Bài đã giải mã ở tần số/kênh của chương: [frames] khung, mẫu của khung `frame` kênh `channel` trong [-1, 1). */
    interface Pcm {
        val frames: Int
        val channels: Int
        fun sample(frame: Int, channel: Int): Double
    }

    /** Bài trong bộ nhớ dạng double xen kẽ kênh (test, tín hiệu tổng hợp). */
    class DoublePcm(private val data: DoubleArray, override val channels: Int) : Pcm {
        override val frames: Int get() = data.size / channels
        override fun sample(frame: Int, channel: Int): Double = data[frame * channels + channel]
    }

    /**
     * Bài PCM 16-bit xen kẽ kênh (bộ đệm bài trên đĩa của bản xuất): mẫu = short * (gain / 32768), như `_Pcm(raw, gain)` của máy tính
     * (`gain` mặc định 1; bù gộp một kênh nay cộng vào gain của phần tử - [MusicExport.FoldOffset]).
     */
    class ShortPcm(private val data: java.nio.ShortBuffer, override val channels: Int, gain: Double = 1.0) : Pcm {
        private val scale = gain / 32768.0
        override val frames: Int get() = data.limit() / channels
        override fun sample(frame: Int, channel: Int): Double = data.get(frame * channels + channel) * scale
    }

    class Bus(val data: DoubleArray, val missing: List<String>)

    fun samples(seconds: Double, rate: Int): Int = Math.rint(seconds * rate).toInt()

    /**
     * Biên độ của các điểm gain tại `t` giây, gọi với `t` KHÔNG GIẢM (con trỏ đi tới): j = (số điểm có t_i <= t) - 1; trước điểm đầu
     * = a đầu, từ điểm cuối trở đi = a cuối, giữa = `a_j + slope_j * (t - t_j)`.
     */
    private class AmplitudeCurve(private val at: DoubleArray, gainDb: Array<Double?>) {
        private val amp = DoubleArray(at.size) { gainDb[it]?.let { db -> 10.0.pow(db / 20.0) } ?: 0.0 }
        private var j = -1

        fun value(t: Double): Double {
            if (at.isEmpty()) return 0.0
            while (j + 1 < at.size && at[j + 1] <= t) j++
            if (j < 0) return amp[0]
            if (j >= at.size - 1) return amp[at.size - 1]
            val span = at[j + 1] - at[j]
            if (span <= 0.0) return amp[j + 1]
            val slope = (amp[j + 1] - amp[j]) / span
            return amp[j] + slope * (t - at[j])
        }
    }

    /**
     * Bus nhạc cho mẫu chương [start, start + n). `pcm(track)` null hay rỗng = bài không lấy được: phần tử ấy im, tên vào `missing`.
     * Dựng theo khối rồi ghép = dựng một lần (test kiểm).
     */
    fun renderBus(
        timeline: List<Element>, n: Int, rate: Int, channels: Int, pcm: (String) -> Pcm?, start: Int = 0,
    ): Bus {
        val bus = DoubleArray(n * channels)
        val missing = ArrayList<String>()
        for (element in timeline) {
            val data = pcm(element.track)
            if (data == null || data.frames == 0) {
                missing.add(element.track)
                continue
            }
            require(data.channels == channels) { "bài ${element.track}: ${data.channels} kênh, chương $channels" }
            val k0 = samples(element.from, rate)
            val k1 = if (!element.to.isFinite()) start + n else min(samples(element.to, rate), start + n)
            val lo = max(k0, start)
            if (k1 <= lo) continue
            val src0 = samples(element.position, rate).toLong() - k0
            val curve = AmplitudeCurve(element.gainAt, element.gainDb)
            val frames = data.frames.toLong()
            for (k in lo until k1) {
                var src = src0 + k
                if (element.loop) src = Math.floorMod(src, frames)
                else if (src < 0 || src >= frames) continue
                val amp = curve.value(k.toDouble() / rate)
                val to = (k - start) * channels
                for (c in 0 until channels) bus[to + c] += data.sample(src.toInt(), c) * amp
            }
        }
        return Bus(bus, missing)
    }

    /**
     * Bộ chặn theo KHỐI (chương 30 phút 48 kHz = 86 triệu mẫu: không giữ cả mảng). [feed] từng khối trả phần ra đã chốt, [finish]
     * trả phần còn lại; ra chậm `L + 12` khung so với vào. Kết quả không phụ thuộc cỡ khối. [gains] (nếu `keepGains`) = g của mọi
     * khung đã ra - chỉ để báo/kiểm.
     */
    class GuardStream(rate: Int, private val channels: Int, params: Params, keepGains: Boolean = false) {
        private val c = 10.0.pow((params.ceilingDbtp - params.headroomDb) / 20.0)
        private val fir = params.fir
        private val attack = max(1, samples(params.attackMs / 1000.0, rate))
        private val step = 1.0 / max(1, samples(params.releaseMs / 1000.0, rate))
        private var voice = DoubleArray(0)
        private var bus = DoubleArray(0)
        private var base = 0      // khung tuyệt đối của voice[0]
        private var done = 0      // khung tuyệt đối của khung ra kế tiếp
        private var prev = 1.0    // g của khung ra trước (nhả)
        val gains: MutableList<DoubleArray>? = if (keepGains) ArrayList() else null

        fun feed(voice: DoubleArray, bus: DoubleArray): DoubleArray {
            require(voice.size == bus.size && voice.size % channels == 0) { "khối giọng/bus lệch" }
            this.voice = this.voice + voice
            this.bus = this.bus + bus
            return emit(final = false)
        }

        fun finish(): DoubleArray = emit(final = true)

        /** data theo khung tuyệt đối [lo, hi), ngoài phần đang giữ = 0. */
        private fun window(data: DoubleArray, lo: Int, hi: Int): DoubleArray {
            val out = DoubleArray((hi - lo) * channels)
            val a = max(lo, base)
            val b = min(hi, base + data.size / channels)
            if (b > a) System.arraycopy(data, (a - base) * channels, out, (a - lo) * channels, (b - a) * channels)
            return out
        }

        /** need[k], k trong [lo, hi): g lớn nhất ở các điểm nội suy giữa k và k+1 để |V + g M| <= max(c, |V|). */
        private fun need(lo: Int, hi: Int): DoubleArray {
            val width = hi - lo
            val xv = window(voice, lo - FIR_LEFT, hi + FIR_TAPS - FIR_LEFT - 1)
            val xm = window(bus, lo - FIR_LEFT, hi + FIR_TAPS - FIR_LEFT - 1)
            val need = DoubleArray(width) { 1.0 }
            for (k in 0 until width) {
                var best = 1.0
                for (ch in 0 until channels) {
                    for (p in 0 until FIR_PHASES) {
                        val f = fir[p]
                        var m = 0.0
                        for (j in 0 until FIR_TAPS) m += f[j] * xm[(k + j) * channels + ch]  // cộng theo j tăng dần như Python
                        if (m == 0.0) continue                                               // |M| = 0 -> g = 1
                        var v = 0.0
                        for (j in 0 until FIR_TAPS) v += f[j] * xv[(k + j) * channels + ch]
                        val allowed = max(c, abs(v))
                        val g = ((if (m > 0.0) allowed - v else allowed + v) / abs(m)).coerceIn(0.0, 1.0)
                        if (g < best) best = g
                    }
                }
                need[k] = best
            }
            return need
        }

        private fun emit(final: Boolean): DoubleArray {
            val end = base + voice.size / channels
            val a = done
            val b = if (final) end else end - (attack + 2 * SUPPORT)
            if (b <= a) return DoubleArray(0)
            // need trên [a - 6, b + L + 6): đủ cho need2 trên [a, b + L), đủ cho nhìn trước của [a, b)
            val lo = a - SUPPORT
            val hi = b + attack + SUPPORT
            val need = need(lo, hi)
            // need chỉ có nghĩa ở khung của chương [0, n): ngoài đó = 1 (n chỉ biết khi finish)
            for (i in 0 until min(max(0, -lo), need.size)) need[i] = 1.0
            if (final) for (i in max(0, end - lo) until need.size) need[i] = 1.0
            val width = b + attack - a
            val need2 = DoubleArray(width) { 1.0 }
            for (k in need.indices) {
                if (need[k] >= 1.0) continue
                val kk = k + lo
                val s = max(a, kk - SUPPORT)
                val e = min(b + attack, kk + SUPPORT + 1)
                for (i in s until e) if (need[k] < need2[i - a]) need2[i - a] = need[k]
            }
            val count = b - a
            val attackEnv = DoubleArray(count) { 1.0 }
            for (k in 0 until width) {
                if (need2[k] >= 1.0) continue
                val s = max(0, k - attack)
                if (s >= count) continue
                val e = min(k + 1, count)
                for (m in s until e) {
                    val j = k - m
                    val ramp = 1.0 - (1.0 - need2[k]) * (1.0 - j.toDouble() / attack)
                    if (ramp < attackEnv[m]) attackEnv[m] = ramp
                }
            }
            // nhả: g[n] = min(a[n], g[n-1] + 1/R); đang không hạ (g = 1) và không bị hạ thì g giữ 1
            val g = DoubleArray(count) { 1.0 }
            var prev = this.prev
            for (k in 0 until count) {
                if (prev >= 1.0 && attackEnv[k] >= 1.0) continue
                prev = min(attackEnv[k], prev + step)
                g[k] = prev
            }
            this.prev = prev
            val out = window(voice, a, b)
            val music = window(bus, a, b)
            for (k in 0 until count) for (ch in 0 until channels) {
                val i = k * channels + ch
                out[i] += g[k] * music[i]
            }
            gains?.add(g)
            done = b
            val keep = max(base, b - (FIR_TAPS + SUPPORT))   // giữ đủ quá khứ cho nội suy + need2 của khối sau
            voice = voice.copyOfRange((keep - base) * channels, voice.size)
            bus = bus.copyOfRange((keep - base) * channels, bus.size)
            base = keep
            return out
        }
    }

    /** (ra = voice + g * bus, g) cho cả chương - chạy [GuardStream] một khối (hay từng khối `block` khung). */
    fun guard(
        voice: DoubleArray, bus: DoubleArray, rate: Int, channels: Int, params: Params, block: Int? = null,
    ): Pair<DoubleArray, DoubleArray> {
        val stream = GuardStream(rate, channels, params, keepGains = true)
        val frames = voice.size / channels
        val step = block ?: max(1, frames)
        val parts = ArrayList<DoubleArray>()
        var i = 0
        while (i < frames) {
            val j = min(frames, i + step)
            parts.add(stream.feed(voice.copyOfRange(i * channels, j * channels), bus.copyOfRange(i * channels, j * channels)))
            i = j
        }
        parts.add(stream.finish())
        return concat(parts) to concat(stream.gains!!)
    }

    private fun concat(parts: List<DoubleArray>): DoubleArray {
        val out = DoubleArray(parts.sumOf { it.size })
        var at = 0
        for (part in parts) {
            System.arraycopy(part, 0, out, at, part.size)
            at += part.size
        }
        return out
    }

    fun toInt16(x: Double): Short = Math.rint(x * 32768.0).coerceIn(-32768.0, 32767.0).toInt().toShort()

    /** Số liệu các lần chặn để báo (như `guard_stats` của Python, cùng làm tròn: chẵn gần nhất trên giá trị nhị phân đúng). */
    data class GuardStats(val spans: Int, val ms: Double, val maxSpanMs: Double, val minGainDb: Double?)

    fun guardStats(g: DoubleArray, rate: Int): GuardStats {
        var spans = 0
        var below = 0L
        var longest = 0
        var run = 0
        var low = Double.POSITIVE_INFINITY
        for (x in g) {
            if (x < low) low = x
            if (x < 1.0) {
                if (run == 0) spans++
                run++
                below++
                if (run > longest) longest = run
            } else {
                run = 0
            }
        }
        return GuardStats(
            spans, round(below.toDouble() * 1000.0 / rate, 1),
            if (spans > 0) round(longest.toDouble() * 1000.0 / rate, 1) else 0.0,
            if (g.isNotEmpty() && low > 0.0) round(20 * log10(low), 2) else null,
        )
    }

    /** Python `round(x, digits)`: chẵn gần nhất trên giá trị nhị phân đúng của x. */
    fun round(x: Double, digits: Int): Double = BigDecimal(x).setScale(digits, RoundingMode.HALF_EVEN).toDouble()
}

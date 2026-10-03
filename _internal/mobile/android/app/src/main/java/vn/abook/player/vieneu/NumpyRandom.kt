package vn.abook.player.vieneu

/**
 * numpy's legacy `RandomState(seed)` (MT19937): the stream the desktop's Turbo sampler draws from (`rng.random_sample()` per code), so a
 * phone with the same codes would pick the same ones. Seeds are 32-bit (`vieneu.seed_of`), seeded like numpy's `_legacy_seeding` for an int.
 */
class NumpyRandomState(seed: Long) : UniformSource {
    private val mt = IntArray(624)
    private var index = 624

    init {
        require(seed in 0..0xFFFF_FFFFL) { "seed must fit 32 bits" }
        mt[0] = seed.toInt()
        for (i in 1 until 624) mt[i] = 1812433253 * (mt[i - 1] xor (mt[i - 1] ushr 30)) + i
    }

    private fun next32(): Int {
        if (index >= 624) {
            for (i in 0 until 624) {
                val y = (mt[i] and 0x80000000.toInt()) or (mt[(i + 1) % 624] and 0x7fffffff)
                var v = mt[(i + 397) % 624] xor (y ushr 1)
                if (y and 1 != 0) v = v xor 0x9908b0df.toInt()
                mt[i] = v
            }
            index = 0
        }
        var y = mt[index++]
        y = y xor (y ushr 11)
        y = y xor ((y shl 7) and 0x9d2c5680.toInt())
        y = y xor ((y shl 15) and 0xefc60000.toInt())
        return y xor (y ushr 18)
    }

    /** `random_sample()`: 53 random bits in [0, 1). */
    fun randomSample(): Double {
        val a = (next32() ushr 5).toLong()
        val b = (next32() ushr 6).toLong()
        return (a * 67108864.0 + b) / 9007199254740992.0
    }

    override fun next(): Double = randomSample()
}

/**
 * numpy's `default_rng(seed)` (PCG64 seeded through `SeedSequence`) and its `standard_normal()` (the 256-step ziggurat of
 * `random_standard_normal`, tables in [NumpyZiggurat]): the start noise of the desktop's Nano, so the phone's Nano clip is the desktop's
 * clip bit for bit (shared fixture tests/fixtures/vieneu/android/rng.json).
 */
class NumpyGenerator(seed: Long) {
    // 128-bit PCG state as two 64-bit halves (hi, lo); arithmetic mod 2^128.
    private var stateHi = 0L
    private var stateLo = 0L
    private val incHi: Long
    private val incLo: Long

    init {
        require(seed >= 0) { "seed must be non-negative" }
        val words = seedSequenceState(seed)
        val initHi = words[0]
        val initLo = words[1]
        // pcg64_srandom_r: inc = (initseq << 1) | 1, state = 0, step, state += initstate, step
        incHi = (words[2] shl 1) or (words[3] ushr 63)
        incLo = (words[3] shl 1) or 1L
        step()
        val lo = stateLo + initLo
        stateHi = stateHi + initHi + (if (below(lo, stateLo)) 1L else 0L)
        stateLo = lo
        step()
    }

    private fun step() {
        // state = state * MULT + inc (mod 2^128)
        val aHi = stateHi
        val aLo = stateLo
        val lo = aLo * MULT_LO
        var hi = unsignedMultiplyHigh(aLo, MULT_LO) + aLo * MULT_HI + aHi * MULT_LO
        val sumLo = lo + incLo
        hi += incHi + (if (below(sumLo, lo)) 1L else 0L)
        stateHi = hi
        stateLo = sumLo
    }

    /** next_uint64: step, then the XSL-RR output of the new state. */
    fun nextLong(): Long {
        step()
        return java.lang.Long.rotateRight(stateHi xor stateLo, (stateHi ushr 58).toInt())
    }

    /** next_double: 53 bits in [0, 1). */
    fun nextDouble(): Double = (nextLong() ushr 11) * (1.0 / 9007199254740992.0)

    /** `Generator.standard_normal()` (float64). */
    fun standardNormal(): Double {
        while (true) {
            var r = nextLong()
            val idx = (r and 0xff).toInt()
            r = r ushr 8
            val sign = r and 1L
            val rabs = (r ushr 1) and 0x000fffffffffffffL
            var x = rabs * NumpyZiggurat.WI[idx]
            if (sign != 0L) x = -x
            if (rabs < NumpyZiggurat.KI[idx]) return x // 99.3% of the time
            if (idx == 0) {
                while (true) {
                    val xx = -NumpyZiggurat.NOR_INV_R * Math.log1p(-nextDouble())
                    val yy = -Math.log1p(-nextDouble())
                    if (yy + yy > xx * xx) return if ((rabs ushr 8) and 1L != 0L) -(NumpyZiggurat.NOR_R + xx) else NumpyZiggurat.NOR_R + xx
                }
            } else if ((NumpyZiggurat.FI[idx - 1] - NumpyZiggurat.FI[idx]) * nextDouble() + NumpyZiggurat.FI[idx] < Math.exp(-0.5 * x * x)) {
                return x
            }
        }
    }

    /** [count] draws of `standard_normal`, cast to float32 like `.astype(np.float32)`. */
    fun standardNormalFloats(count: Int): FloatArray = FloatArray(count) { standardNormal().toFloat() }

    companion object {
        /** Unsigned a < b (Long.compareUnsigned needs API 26). */
        private fun below(a: Long, b: Long) = (a xor Long.MIN_VALUE) < (b xor Long.MIN_VALUE)

        /** High 64 bits of the unsigned 128-bit product (Math.multiplyHigh needs API 31). */
        private fun unsignedMultiplyHigh(a: Long, b: Long): Long {
            val aLo = a and 0xFFFFFFFFL
            val aHi = a ushr 32
            val bLo = b and 0xFFFFFFFFL
            val bHi = b ushr 32
            val lowLow = aLo * bLo
            val middle = aHi * bLo + (lowLow ushr 32)
            val middle2 = aLo * bHi + (middle and 0xFFFFFFFFL)
            return aHi * bHi + (middle ushr 32) + (middle2 ushr 32)
        }

        private const val MULT_HI = 0x2360ED051FC65DA4L
        private const val MULT_LO = 0x4385DF649FCCF645L

        private const val INIT_A = 0x43b0d7e5
        private const val MULT_A = 0x931e8875.toInt()
        private const val INIT_B = 0x8b51f9dd.toInt()
        private const val MULT_B = 0x58f38ded
        private const val MIX_MULT_L = 0xca01f9dd.toInt()
        private const val MIX_MULT_R = 0x4973f715
        private const val POOL = 4

        /** `SeedSequence(seed).generate_state(4, uint64)` as (hi0, lo0, hi1, lo1) halves: PCG64's initstate and initseq. */
        internal fun seedSequenceState(seed: Long): LongArray {
            val entropy = ArrayList<Int>()
            var rest = seed
            do {
                entropy.add((rest and 0xFFFFFFFFL).toInt())
                rest = rest ushr 32
            } while (rest != 0L)
            var hashConst = INIT_A
            fun hashmix(input: Int): Int {
                var value = input xor hashConst
                hashConst *= MULT_A
                value *= hashConst
                return value xor (value ushr 16)
            }
            fun mix(x: Int, y: Int): Int {
                val result = MIX_MULT_L * x - MIX_MULT_R * y
                return result xor (result ushr 16)
            }
            val pool = IntArray(POOL) { hashmix(if (it < entropy.size) entropy[it] else 0) }
            for (src in 0 until POOL) for (dst in 0 until POOL) if (src != dst) pool[dst] = mix(pool[dst], hashmix(pool[src]))
            for (src in POOL until entropy.size) for (dst in 0 until POOL) pool[dst] = mix(pool[dst], hashmix(entropy[src]))
            var hashB = INIT_B
            val words = IntArray(8) { i ->
                var value = pool[i % POOL] xor hashB
                hashB *= MULT_B
                value *= hashB
                value xor (value ushr 16)
            }
            fun u64(i: Int) = (words[2 * i].toLong() and 0xFFFFFFFFL) or (words[2 * i + 1].toLong() shl 32)
            // pcg64_set_seed(seed = val[0..1], inc = val[2..3]); PCG_128BIT_CONSTANT(high, low) = val[0] << 64 | val[1]
            return longArrayOf(u64(0), u64(1), u64(2), u64(3))
        }
    }
}

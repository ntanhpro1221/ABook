package vn.abook.player.readaloud

import java.math.BigDecimal
import java.math.RoundingMode

/**
 * Mã `Sec-MS-GEC` v2 của dịch vụ đọc to của Edge (bản Kotlin; bản Python cặp đôi: abook/readaloud/edge_token.py).
 *
 * Chuyển từ rany2/edge-tts, `drm.py` (phiên bản 7.3.1), giấy phép LGPL-3.0; file này vẫn nằm dưới LGPL-3.0 (docs/THIRD_PARTY.md).
 * Phần còn lại của giọng Edge (EdgeTts.kt) viết lại từ giao thức, không chép mã. Token = "<CS64 16 hex>-<SHA-256 biến thể 64 hex>" tính từ
 * "<giờ Windows file time làm tròn xuống 5 phút, đơn vị 100 ns><TRUSTED_CLIENT_TOKEN>"; SHA-256 ở đây là biến thể (hằng số riêng), KHÔNG phải MessageDigest.
 * Hai bản đọc cùng tests/fixtures/readaloud/edge/gec_v2_vectors.json (sinh bằng mã gốc của edge-tts).
 * Hỏng lần sau (HTTP 403 với mọi người) thì đối chiếu `drm.py` + `constants.py` của edge-tts bản mới nhất, cập nhật file này, edge_token.py và file vectors.
 *
 * Số học 32 bit không dấu: mọi giá trị là Long đã che 0xFFFFFFFF; phép nhân hai số 32 bit tràn Long nhưng 32 bit thấp vẫn đúng (bù hai), nên che sau là đủ.
 */
object EdgeToken {
    const val TRUSTED_CLIENT_TOKEN = "6A5AA1D4EAFF4E9FB37E23D68491D6F4"
    private const val WIN_EPOCH = 11_644_473_600.0
    private const val MASK = 0xFFFFFFFFL

    // FIPS 180-4: https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.180-4.pdf
    private val SHA256_INITIAL = longArrayOf(0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A, 0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19)
    private val SHA256_STATE = longArrayOf(0xFD9FBEA2, 0x91243CE7, 0xBE499094, 0xCD2E1E0A, 0x6C006F49, 0x04BD35AB, 0xFEB0A7E4, 0x03EFFBD2)
    private val SHA256_SCHEDULE = longArrayOf(
        0xEB24BF9E, 0x1558691F, 0xA0C09EE2, 0x0CFA32BA, 0xA622EE8C, 0xD1DD9491, 0xC0DD25A0,
        0xF9E70AB6, 0xF0C31573, 0x7058CE4E, 0x7188E606, 0x00E5AB33, 0xD258B060, 0x72766564,
    )
    private val SHA256_ROUND_CONSTANTS = longArrayOf(
        0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5, 0x3956C25B, 0x59F111F1, 0x923F82A4, 0xAB1C5ED5,
        0xD807AA98, 0x12835B01, 0x243185BE, 0x550C7DC3, 0x72BE5D74, 0x80DEB1FE, 0x9BDC06A7, 0xC19BF174,
        0xE49B69C1, 0xEFBE4786, 0x0FC19DC6, 0x240CA1CC, 0x2DE92C6F, 0x4A7484AA, 0x5CB0A9DC, 0x76F988DA,
        0x983E5152, 0xA831C66D, 0xB00327C8, 0xBF597FC7, 0xC6E00BF3, 0xD5A79147, 0x06CA6351, 0x14292967,
        0x27B70A85, 0x2E1B2138, 0x4D2C6DFC, 0x53380D13, 0x650A7354, 0x766A0ABB, 0x81C2C92E, 0x92722C85,
        0xA2BFE8A1, 0xA81A664B, 0xC24B8B70, 0xC76C51A3, 0xD192E819, 0xD6990624, 0xF40E3585, 0x106AA070,
        0x19A4C116, 0x1E376C08, 0x2748774C, 0x34B0BCB5, 0x391C0CB3, 0x4ED8AA4A, 0x5B9CCA4F, 0x682E6FF3,
        0x748F82EE, 0x78A5636F, 0x84C87814, 0x8CC70208, 0x90BEFFFA, 0xA4506CEB, 0xBEF9A3F7, 0xC67178F2,
    )
    private const val SHA256_ADJUSTMENT = 0xC9DC06A7L
    private val SHA256_BLOCK_CONSTANTS = SHA256_ROUND_CONSTANTS.copyOf().also { it[14] = SHA256_ADJUSTMENT }
    private const val SHA256_SIGMA0_ADJUSTMENT = 0x059C0B80L
    private const val SHA256_SIGMA1_ADJUSTMENT = 0x000B92C0L

    private val CS64_COEFFICIENTS = arrayOf(
        longArrayOf(0xE82E91B1, 0xB32700D0), longArrayOf(0x44DE24C6, 0x88DFF51D), longArrayOf(0x3BEB65BC, 0x29514038),
        longArrayOf(0xC89C5933, 0xB328CBDF), longArrayOf(0x8D1EC211, 0xD405B4D5), longArrayOf(0x314EF5D5, 0x26E55F3C),
        longArrayOf(0xE92491B1, 0x607801C6), longArrayOf(0xF0A5B9D5, 0x82B2C1FB), longArrayOf(0x06064CF3, 0xFA51A3DA),
        longArrayOf(0xDA79FA60, 0x207CC464), longArrayOf(0xBED20560, 0x3C3C74F3), longArrayOf(0x89F9C9F8, 0xD2D14B61),
        longArrayOf(0x35FA38C6, 0xBB04A2C1), longArrayOf(0xCB49E3C6, 0xC5626167),
    )
    private const val CS64_FACTOR = 0x82893933L
    private const val CS64_ADJUSTMENT0 = 0xF2F90B1AL
    private const val CS64_ADJUSTMENT1 = 0x0B1A0000L

    private fun rotr(value: Long, bits: Int): Long = ((value ushr bits) or (value shl (32 - bits))) and MASK

    private fun rol16(value: Long): Long {
        val v = value and MASK
        return ((v shl 16) or (v ushr 16)) and MASK
    }

    private fun sigma0(x: Long): Long = (rotr(x, 7) xor rotr(x, 18) xor (x ushr 3)) and MASK

    private fun sigma1(x: Long): Long = (rotr(x, 17) xor rotr(x, 19) xor (x ushr 10)) and MASK

    /** Từ 32 bit little-endian của `data` (đệm 0 cho đủ bội số của 4, rồi cho số từ chẵn). */
    private fun wordsLe4Even(data: ByteArray): LongArray {
        val padded = data.copyOf(data.size + (4 - data.size % 4) % 4)
        var count = padded.size / 4
        if (count % 2 == 1) count++
        val words = LongArray(count)
        for (i in 0 until padded.size / 4) {
            words[i] = (padded[4 * i].toLong() and 0xFF) or ((padded[4 * i + 1].toLong() and 0xFF) shl 8) or
                ((padded[4 * i + 2].toLong() and 0xFF) shl 16) or ((padded[4 * i + 3].toLong() and 0xFF) shl 24)
        }
        return words
    }

    private fun bigEndian(data: ByteArray, from: Int, to: Int): Long {
        var value = 0L
        for (i in from until to) value = (value shl 8) or (data[i].toLong() and 0xFF)
        return value
    }

    private fun expandSchedule(words: LongArray, firstWord: Int) {
        for (i in firstWord until 64) {
            words[i] = (sigma1(words[i - 2]) + words[i - 7] + sigma0(words[i - 15]) + words[i - 16]) and MASK
        }
    }

    /** SHA-256 chuẩn từ vòng `firstRound` (14 = vòng đầu của khối đầu, khi trạng thái đã được tính sẵn từ 7 byte đầu). */
    private fun rounds(state: LongArray, words: LongArray, firstRound: Int): LongArray {
        var a = state[0]; var b = state[1]; var c = state[2]; var d = state[3]
        var e = state[4]; var f = state[5]; var g = state[6]; var h = state[7]
        val constants = if (firstRound == 14) SHA256_BLOCK_CONSTANTS else SHA256_ROUND_CONSTANTS
        for (i in firstRound until 64) {
            val t1 = h + (rotr(e, 6) xor rotr(e, 11) xor rotr(e, 25)) + (g xor (e and (f xor g))) + constants[i] + words[i]
            val t2 = (rotr(a, 2) xor rotr(a, 13) xor rotr(a, 22)) + ((a and b) or (c and (a or b)))
            h = g; g = f; f = e
            e = (d + t1) and MASK
            d = c; c = b; b = a
            a = (t1 + t2) and MASK
        }
        return longArrayOf(a, b, c, d, e, f, g, h)
    }

    /** Trạng thái đầu của SHA-256 biến thể, tính từ 7 byte đầu của dữ liệu. */
    private fun sha256Init(salt: ByteArray): LongArray {
        val words = LongArray(64)
        words[14] = bigEndian(salt, 0, 3)
        words[15] = bigEndian(salt, 3, 7)
        for (index in 16 until 30) {
            var value = SHA256_SCHEDULE[index - 16]
            if (index - 2 >= 14) {
                value += if (index == 16) sigma1(words[index - 2]) xor SHA256_SIGMA1_ADJUSTMENT else sigma1(words[index - 2])
            }
            if (index - 7 >= 14) value += words[index - 7]
            if (index - 15 >= 14) {
                value += if (index == 29) sigma0(words[index - 15]) xor SHA256_SIGMA0_ADJUSTMENT else sigma0(words[index - 15])
            }
            words[index] = value and MASK
        }
        words[30] = (sigma1(words[28]) + words[23] + sigma0(words[15]) + words[14] + SHA256_ADJUSTMENT - SHA256_ROUND_CONSTANTS[14]) and MASK
        expandSchedule(words, 31)
        val working = rounds(SHA256_STATE, words, 14)
        return LongArray(8) { (SHA256_INITIAL[it] + working[it]) and MASK }
    }

    private fun sha256Digest(data: ByteArray): ByteArray {
        require(data.size >= 7) { "Token salt must contain at least seven bytes" }
        val length = 57L + data.size
        val zeros = Math.floorMod(55L - length, 64L).toInt()
        val tail = data.size - 7
        val padded = ByteArray(tail + 1 + zeros + 8)
        System.arraycopy(data, 7, padded, 0, tail)
        padded[tail] = 0x80.toByte()
        val bits = length * 8
        for (i in 0 until 8) padded[padded.size - 1 - i] = (bits ushr (8 * i)).toByte()
        var state = sha256Init(data.copyOfRange(0, 7))
        for (offset in 0 until padded.size step 64) {
            val words = LongArray(64)
            for (i in 0 until 16) words[i] = bigEndian(padded, offset + 4 * i, offset + 4 * i + 4)
            expandSchedule(words, 16)
            val working = rounds(state, words, 0)
            state = LongArray(8) { (state[it] + working[it]) and MASK }
        }
        val out = ByteArray(32)
        for (i in 0 until 8) for (j in 0 until 4) out[4 * i + j] = (state[i] ushr (24 - 8 * j)).toByte()
        return out
    }

    private fun cs64Digest(data: ByteArray, digest: ByteArray): LongArray {
        val keyA = wordsLe4Even(digest.copyOf(4))[0] or 1L
        val keyB = wordsLe4Even(digest.copyOfRange(4, 8))[0] or 1L
        val factors = longArrayOf((keyA * CS64_FACTOR) and MASK, (keyB * CS64_FACTOR) and MASK)
        val dataWords = wordsLe4Even(byteArrayOf(0) + data)
        val terms = LongArray(CS64_COEFFICIENTS.size + dataWords.size)
        val offsets = LongArray(terms.size)
        for ((index, pair) in CS64_COEFFICIENTS.withIndex()) {
            terms[index] = (pair[0] * factors[index % 2]) and MASK
            offsets[index] = pair[1]
        }
        for ((index, word) in dataWords.withIndex()) {
            var term = word * (if (index % 2 == 0) keyA else keyB)
            var offset = rol16(word) * (if (index % 2 == 0) 0xEF0569FBL else 0xC31713DBL)
            if (index == 0) {
                term += CS64_ADJUSTMENT0 * factors[0]
                offset += CS64_ADJUSTMENT1
            }
            terms[CS64_COEFFICIENTS.size + index] = term and MASK
            offsets[CS64_COEFFICIENTS.size + index] = offset and MASK
        }
        var swapAcc = 0L; var swapLast = 0L; var state = 0L; var acc = 0L
        for (index in terms.indices step 2) {
            val x = terms[index]
            val y = terms[index + 1]
            var t = rol16((offsets[index] + x) and MASK)
            var q = (t * 0x76F50F34L) and MASK
            swapAcc += (rol16(q) * 0xC3EFEA97L + q) and MASK
            t = rol16((offsets[index + 1] + y) and MASK)
            q = (t * 0x1881CE3CL) and MASK
            swapLast = (rol16(q) * 0x35BD1EC9L + q) and MASK
            swapAcc = (swapAcc + swapLast) and MASK

            state = (state * keyA + x) and MASK
            state = (rol16(state) * 0xCF98B111L) and MASK
            state = (rol16(state) * 0x87085B9FL) and MASK
            state = (rol16(state) * 0x12CEB96DL) and MASK
            state = (rol16(state) * 0x257E1D83L) and MASK
            acc += state
            t = (state * keyB + y) and MASK
            t = (rol16(t) * 0xA27416F5L) and MASK
            t = (rol16(t) * 0xD38396FFL) and MASK
            state = (rol16((rol16(t) * 0x7C932B89L) and MASK) * 0xBFA49F69L) and MASK
            acc = (acc + state) and MASK
        }
        return longArrayOf(swapLast xor state, swapAcc xor acc)
    }

    private fun hex(bytes: ByteArray): String = bytes.joinToString("") { "%02X".format(it) }

    /** Token v2 cho giờ Unix `unixSeconds` (giây, đã cộng độ lệch đồng hồ nếu có): "<16 hex>-<64 hex>", hoa. */
    fun secMsGecV2(unixSeconds: Double): String {
        var ticks = unixSeconds + WIN_EPOCH
        ticks -= ticks % 300.0
        ticks *= 10_000_000.0
        val data = (BigDecimal(ticks).setScale(0, RoundingMode.HALF_EVEN).toPlainString() + TRUSTED_CLIENT_TOKEN).toByteArray(Charsets.US_ASCII)
        val digest = sha256Digest(data)
        val cs = cs64Digest(data, digest)
        val cs64 = ByteArray(8) { i -> (cs[i / 4] ushr (8 * (i % 4))).toByte() }
        return hex(cs64) + "-" + hex(digest)
    }
}

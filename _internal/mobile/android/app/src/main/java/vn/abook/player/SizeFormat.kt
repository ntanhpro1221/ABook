package vn.abook.player

import java.util.Locale

/** shared/format.ts formatSize: base 1024, vi-VN, no trailing decimal zero. */
fun formatSize(bytes: Long): String {
    fun grouped(value: Long) = String.format(Locale.ROOT, "%,d", value).replace(',', '.')
    fun decimal(value: Double): String {
        val tenths = Math.round(value * 10)
        return if (tenths % 10 == 0L) grouped(tenths / 10) else "${grouped(tenths / 10)},${tenths % 10}"
    }
    if (bytes >= 1024L * 1024 * 1024) return "${decimal(bytes / (1024.0 * 1024 * 1024))} GB"
    val mb = bytes / (1024.0 * 1024)
    if (mb < 0.1) return "${maxOf(1L, Math.round(bytes / 1024.0))} KB"
    if (mb < 10) return "${decimal(mb)} MB"
    return "${grouped(Math.round(mb))} MB"
}

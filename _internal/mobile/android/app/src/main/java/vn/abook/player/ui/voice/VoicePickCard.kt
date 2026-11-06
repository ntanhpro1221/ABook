package vn.abook.player.ui.voice

import androidx.compose.foundation.layout.Column
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import vn.abook.player.readaloud.MachineVoicePick
import vn.abook.player.readaloud.EnginePickStatus
import vn.abook.player.readaloud.EngineNumbers
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.ListSection
import vn.abook.player.ui.components.ListRow
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.data.dotJoin
import vn.abook.player.ui.data.dotJoined
import java.util.Locale

@Composable
fun VoicePickCard(voice: VoiceState) {
    val status by voice.pick.collectAsState()
    ListSection("Giọng theo máy") {
        Caption(EnginePickText.headline(status))
        for (engine in status.installed) {
            val row = status.engines.firstOrNull { it.engine == engine }
            val chosen = engine == status.chosen
            val badge = when {
                chosen -> if (status.override.isEmpty()) "Máy chọn" else "Bạn chọn"
                row == null -> "Chưa thử"
                row.verdict == "error" -> "Lỗi"
                row.verdict == "slow" -> "Chậm"
                row.verdict == "unclear" -> "Chưa rõ"
                else -> ""
            }
            val numbers = EnginePickText.numbers(row)
            ListRow(dotJoin(MachineVoicePick.name(engine), badge), hint = numbers) {
                if (!chosen && !status.measuring) TextAction("Dùng giọng này", { voice.choosePick(engine) }, "voice_pick_$engine")
            }
        }
        if (status.engines.isNotEmpty()) Caption("Cùng vài câu cho mọi giọng; chưa có bộ nghe lại trên máy này; chưa có bộ chấm tự nhiên. Chọn: kịp đọc trực tiếp, rồi nhanh nhất.")
        if (status.installed.isNotEmpty() && !status.measuring) {
            TextAction(if (status.engines.isEmpty()) "Thử" else "Thử lại", voice::measurePick, "voice_pick_measure")
            if (status.override.isNotEmpty()) TextAction("Theo số đo", { voice.choosePick("") }, "voice_pick_auto")
        }
    }
}

object EnginePickText {
    private fun number(value: Double) = String.format(Locale.forLanguageTag("vi"), "%.1f", value)

    fun headline(status: EnginePickStatus): String {
        if (status.measuring) return "Đang thử các giọng"
        if (status.error.isNotEmpty()) return status.error
        if (status.installed.isEmpty()) return "Chưa có giọng nào trên máy - tải một bộ giọng ở trên rồi máy sẽ tự thử."
        if (status.engines.isEmpty()) return "Máy chưa thử các giọng: bấm Thử để máy chọn giọng hợp nhất."
        val chosen = status.chosen?.takeIf { it.isNotEmpty() }?.let(MachineVoicePick::name)
        val who = if (status.override.isNotEmpty()) "bạn chọn" else "máy chọn theo số đo"
        return if (chosen != null) "Sách chưa chọn giọng đọc bằng $chosen ($who)."
            else "Chưa giọng nào trên máy vừa rõ vừa kịp đọc trực tiếp: sách chưa chọn giọng dùng giọng mặc định."
    }

    fun numbers(row: EngineNumbers?): String {
        if (row == null) return "Chưa thử trên máy này."
        if (row.verdict == "error") return if (row.error.isEmpty()) "Thử không được." else "Thử không được: ${row.error}"
        val clarity = row.cer?.let { "Rõ ${kotlin.math.round((1 - it) * 100).toInt()}%" } ?: "Độ rõ: chưa đo"
        val natural = row.natural?.let { "Tự nhiên ${number(it)}/5" } ?: "Tự nhiên: chưa đo"
        val speed = row.rtf?.let {
            if (it >= MachineVoicePick.LIVE_RTF) "Chậm: ${number(it)} giây cho mỗi giây nghe" else "Nhanh gấp ${number(1 / maxOf(it, 0.01))} lần"
        }
        return listOfNotNull(clarity, natural, speed, row.ramMb?.let { "RAM đỉnh $it MB" }).dotJoined()
    }
}

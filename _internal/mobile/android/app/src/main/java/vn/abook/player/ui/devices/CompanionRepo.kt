package vn.abook.player.ui.devices

import android.content.Context
import androidx.compose.runtime.Immutable
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.RemotePlayers
import vn.abook.player.StudioAlerts

@Immutable
data class OtherPlayer(
    val device: String, val name: String, val book: String, val chapter: Int?, val title: String,
    val playing: Boolean, val known: Boolean, val position: Double, val duration: Double,
    val rate: Double, val age: Double, val buffering: Boolean, val cast: Boolean, val protocol: String,
    val sleep: String = "off", val kind: String = "phone",
) {
    fun positionAfter(seconds: Double): Double = (position + if (playing && !buffering) (age + seconds.coerceAtLeast(0.0)) * rate else 0.0)
        .coerceAtLeast(0.0).let { if (duration > 0) it.coerceAtMost(duration) else it }

    companion object {
        fun from(row: JSONObject): OtherPlayer {
            val state = row.optJSONObject("state") ?: JSONObject()
            return OtherPlayer(row.optString("device"), row.optString("name"), row.optString("localBookId"),
                if (state.isNull("chapterId")) null else state.optInt("chapterId"), state.optString("chapterTitle"),
                state.optBoolean("playing"), row.optBoolean("known"), state.optDouble("position", 0.0),
                state.optDouble("duration", 0.0), state.optDouble("rate", 1.0), row.optDouble("age", 0.0),
                state.optBoolean("buffering"), row.optString("via") == "cast", row.optString("protocol"),
                row.optJSONObject("sleep")?.optString("kind", "off") ?: "off", row.optString("kind", "phone"))
        }
    }
}

@Immutable data class StudioNoticeState(val enabled: Boolean = false, val permitted: Boolean = true)
@Immutable data class CompanionState(
    val players: List<OtherPlayer> = emptyList(), val notices: StudioNoticeState = StudioNoticeState(),
    val problem: String = "", val busy: Boolean = false, val receivedAt: Long = 0,
)

/** Same cores as LibraryPlugin; no Capacitor calls and no polling while the Activity is hidden. */
interface CompanionCore {
    suspend fun scan() {}
    suspend fun players(): JSONArray
    suspend fun command(device: String, command: JSONObject)
    suspend fun notices(): StudioNoticeState
    suspend fun setNotices(enabled: Boolean): StudioNoticeState
}

class AndroidCompanionCore(private val context: Context) : CompanionCore {
    init { vn.abook.player.PhoneCast.init(context) }
    override suspend fun scan() = withContext(Dispatchers.IO) { vn.abook.player.PhoneCast.players.scan() }
    override suspend fun players() = withContext(Dispatchers.IO) { RemotePlayers.all(context) }
    override suspend fun command(device: String, command: JSONObject) = withContext(Dispatchers.IO) { RemotePlayers.command(context, device, command); Unit }
    override suspend fun notices() = StudioNoticeState(StudioAlerts.enabled(context), StudioAlerts.permitted(context))
    override suspend fun setNotices(enabled: Boolean) = withContext(Dispatchers.IO) { StudioAlerts.setEnabled(context, enabled); notices() }
}

class CompanionRepo(private val core: CompanionCore, private val now: () -> Long = android.os.SystemClock::elapsedRealtime) {
    private val flow = MutableStateFlow(CompanionState())
    val state = flow.asStateFlow()
    private val seen = linkedSetOf<String>()
    private var generation = 0

    suspend fun refresh() {
        val started = generation
        try {
            val rows = core.players()
            if (started != generation || flow.value.busy) return
            // Lượt hỏi này qua được: lời "chưa nối được" của lượt trước hết đúng; lời của lệnh bị từ chối thì giữ.
            var problem = flow.value.problem.takeUnless { it == OFFLINE }.orEmpty()
            val players = (0 until rows.length()).map { index ->
                val row = rows.getJSONObject(index)
                val acks = row.optJSONArray("acks") ?: JSONArray()
                for (i in 0 until acks.length()) {
                    val ack = acks.getJSONObject(i)
                    val id = ack.optString("id")
                    if (id.isNotBlank() && seen.add(id) && !ack.optBoolean("ok"))
                        problem = "${row.optString("name")}: ${ack.optString("message").ifBlank { "Chưa làm được lệnh" }}"
                }
                OtherPlayer.from(row)
            }
            while (seen.size > 256) seen.remove(seen.first())
            flow.value = flow.value.copy(players = players, notices = core.notices(), receivedAt = now(), problem = problem)
        } catch (cancelled: CancellationException) { throw cancelled }
        catch (_: Exception) { flow.value = flow.value.copy(problem = OFFLINE) }
    }

    private companion object {
        const val OFFLINE = "Chưa nối được, bạn thử lại"
    }

    suspend fun setNotices(enabled: Boolean) = attempt { flow.value = flow.value.copy(notices = core.setNotices(enabled)) }

    suspend fun findPlayers() = attempt { core.scan(); kotlinx.coroutines.delay(2_500) }.also { refresh() }

    suspend fun send(player: OtherPlayer, action: String, seconds: Double? = null, mode: String? = null, minutes: Int? = null): Boolean = attempt {
        generation++
        val elapsed = (now() - flow.value.receivedAt) / 1000.0
        flow.value = flow.value.copy(receivedAt = now(), players = flow.value.players.map { old ->
            val at = old.positionAfter(elapsed)
            val fresh = old.copy(position = at, age = 0.0)
            if (old.device != player.device) fresh else when (action) {
                "toggle" -> fresh.copy(playing = !old.playing)
                "pause" -> fresh.copy(playing = false)
                "play" -> fresh.copy(playing = true)
                "skip" -> fresh.copy(position = (at + (seconds ?: 0.0)).coerceIn(0.0, old.duration.takeIf { it > 0 } ?: Double.MAX_VALUE))
                else -> fresh
            }
        })
        val command = JSONObject().put("action", action)
        seconds?.let { command.put("seconds", it) }; if (mode == "chapter") command.put("endOfChapter", true); minutes?.let { command.put("minutes", it) }
        core.command(player.device, command)
    }.also { refresh() }

    /** Pause acknowledgement must arrive before local playback starts, so two devices never play together. */
    suspend fun listenHere(player: OtherPlayer, start: (String, Int, Double) -> Unit): Boolean {
        val chapter = player.chapter ?: return false
        if (!player.known) return false
        val receivedAt = flow.value.receivedAt
        return attempt {
            generation++
            core.command(player.device, JSONObject().put("action", if (player.protocol == "gcast") "stop" else "pause"))
            start(player.book, chapter, player.positionAfter((now() - receivedAt) / 1000.0))
        }.also { refresh() }
    }

    suspend fun handOff(remote: OtherPlayer, local: vn.abook.player.ui.data.PlayerState, position: Double, pause: () -> Unit): Boolean {
        if (!local.hasTrack) return false
        return attempt {
            generation++
            core.command(remote.device, JSONObject().put("action", "load").put("bookId", local.bookId)
                .put("chapterId", local.chapterId).put("seconds", position))
            pause()
        }.also { refresh() }
    }

    private suspend fun attempt(block: suspend () -> Unit): Boolean {
        if (flow.value.busy) return false
        flow.value = flow.value.copy(busy = true, problem = "")
        return try { block(); true }
        catch (cancelled: CancellationException) { throw cancelled }
        catch (_: Exception) { flow.value = flow.value.copy(problem = "Chưa làm được, bạn thử lại"); false }
        finally { flow.value = flow.value.copy(busy = false) }
    }
}

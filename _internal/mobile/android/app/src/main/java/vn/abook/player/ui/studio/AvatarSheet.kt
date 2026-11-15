package vn.abook.player.ui.studio

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import vn.abook.player.S
import vn.abook.player.ui.components.*
import vn.abook.player.ui.studio.parts.AnswerButton
import vn.abook.player.ui.theme.Abook

@Composable
internal fun AvatarSheet(member: CastMember, cast: StudioCastState) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var busy by remember { mutableStateOf(false) }
    var available by remember { mutableStateOf(false) }
    var pending by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }
    var portrait by remember { mutableStateOf(member.avatar) }
    suspend fun status() {
        val state = cast.avatarStatus(member)
        available = state.optBoolean("available"); pending = state.optBoolean("pending"); error = state.optString("error")
    }
    fun change(action: String, data: String? = null) {
        if (busy) return
        busy = true; error = ""
        scope.launch {
            try {
                val result = cast.changeAvatar(member, action, data)
                portrait = vn.abook.player.ui.data.AvatarArt.parse(result.optJSONObject("avatar")) ?: portrait
                pending = result.optBoolean("pending"); cast.refresh()
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (failure: Exception) { error = failure.message.orEmpty() }
            finally { busy = false }
        }
    }
    LaunchedEffect(Unit) { runCatching { status() }.onFailure { error = it.message.orEmpty() } }
    LaunchedEffect(pending) {
        while (pending) {
            delay(1000)
            runCatching { status() }.onFailure { error = it.message.orEmpty(); pending = false }
            if (!pending) {
                cast.refresh()
                val loaded = cast.poll.value.data
                portrait = (loaded?.characters.orEmpty() + loaded?.extras.orEmpty()).find { it.name == member.name }?.avatar ?: portrait
            }
        }
    }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) scope.launch {
            val bytes = withContext(Dispatchers.IO) {
                runCatching { context.contentResolver.openInputStream(uri)?.use { input ->
                    val out = java.io.ByteArrayOutputStream(); val buffer = ByteArray(8192)
                    while (out.size() <= 4 * 1024 * 1024) {
                        val count = input.read(buffer); if (count < 0) break; out.write(buffer, 0, count)
                    }
                    out.toByteArray().takeIf { it.size <= 4 * 1024 * 1024 }
                } }.getOrNull()
            }
            if (bytes != null) change("upload", android.util.Base64.encodeToString(bytes, android.util.Base64.NO_WRAP))
            else error = S.s_chua_lam_duoc_8b442a06
        }
    }
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        BasicText(S.s_avatar_portrait, style = Abook.type.sectionTitle)
        PersonAvatar(member.name, portrait, size = 96.dp, load = { cast.avatar(member.copy(avatar = portrait)) })
        AnswerButton(S.s_chon_anh_41ecf092, { picker.launch("image/*") }, "avatar_choose", enabled = !busy)
        AnswerButton(if (pending) S.s_avatar_generating else S.s_avatar_generate, { change("generate") }, "avatar_generate", enabled = !busy && !pending && available, pending = busy || pending)
        Reveal(!available) { RowHint(S.s_avatar_unavailable) }
        AnswerButton(S.s_avatar_pattern, { change("pattern") }, "avatar_pattern", enabled = !busy, pending = busy)
        Reveal(error.isNotEmpty()) { InlineProblem(error, { scope.launch { runCatching { status() } } }, "avatar_error") }
    }
}

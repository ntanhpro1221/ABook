package vn.abook.player.ui.nowplaying

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import vn.abook.player.*
import vn.abook.player.ui.studio.*
import vn.abook.player.ui.studio.WorkStep
import vn.abook.player.ui.voice.AndroidSamplePlayer

/** Production projects use pinned Studio endpoints; packaged/offline books use durable listener wishes. */
class AndroidPlayerLineSource(context: Context,
    private val appInfo: suspend (String) -> JSONObject = { StudioApi(context.applicationContext, it).getObject(StudioPaths.APP) },
    private val remoteSource: StudioSource = StudioRepo(context.applicationContext),
) : PlayerLineSource {
    private val app = context.applicationContext
    private val player by lazy { AndroidSamplePlayer(app) }
    private var sampleGeneration = 0
    private var remoteSample: StudioClips? = null
    private val accessDenied = HashMap<String, Boolean>()

    private suspend fun refreshAccess(bookId: String) {
        val destination = Store.editDestination(bookId) ?: return
        val denied = try { appInfo(destination.first.orEmpty()).optBoolean("listenOnly") }
        catch (_: StudioError.ListenOnly) { true }
        catch (_: StudioError.Offline) { null } // Offline wishes keep the last known access decision.
        withContext(Dispatchers.Main.immediate) { if (denied != null) accessDenied[bookId] = denied }
    }

    private suspend fun blocked(bookId: String): String {
        val caps = withContext(Dispatchers.IO) { Store.capabilitiesOf(bookId) }
        if (caps.optBoolean("local")) return S.s_sach_nay_nam_tren_dien_thoai_khac_sua_tung_269dd675
        val destination = withContext(Dispatchers.IO) { Store.editDestination(bookId) }
        val listenOnly = withContext(Dispatchers.Main.immediate) {
            accessDenied[bookId] ?: (destination != null && (app as? AbookApplication)?.studio?.session(destination.first.orEmpty())?.listenOnly == true)
        }
        if (listenOnly)
            return S.s_may_tinh_chua_cho_ban_sua_6a5d6567
        return ""
    }

    override val decisionsSource: StudioSource = object : StudioSource by StudioRepo(app) {
        override suspend fun write(computer: String, id: String, step: WorkStep, slow: Boolean): JSONObject = withContext(Dispatchers.IO) {
            val reason = blocked(id)
            check(reason.isEmpty()) { reason }
            BookActions.studio(app, "POST", id, "/${step.endpoint}", step.body)
        }
    }

    override suspend fun load(bookId: String, chapter: Int, paragraph: ReadParagraph): PlayerLineSnapshot = withContext(Dispatchers.IO) {
        Store.init(app)
        refreshAccess(bookId)
        val reason = blocked(bookId)
        val destination = Store.editDestination(bookId)
        if (reason.isEmpty() && destination != null) {
            try { return@withContext PlayerLineRemote.load(remoteSource, destination.first.orEmpty(), destination.second, chapter, paragraph) }
            catch (_: StudioError.Offline) { /* Only a failed read may fall back to durable local wishes. */ }
            catch (_: StudioError.Gone) { /* A linked packaged book may have no production project. */ }
        }
        localSnapshot(bookId, chapter, paragraph)
    }

    private suspend fun localSnapshot(bookId: String, chapter: Int, paragraph: ReadParagraph): PlayerLineSnapshot = withContext(Dispatchers.IO) {
        PlayerLineLogic.snapshot(chapter, paragraph,
            BookActions.studio(app, "GET", bookId, "/cast"), BookActions.studio(app, "GET", bookId, "/wishes"), blocked(bookId))
            .copy(refresh = { localSnapshot(bookId, chapter, paragraph) })
    }

    override suspend fun sample(bookId: String, chapter: Int, paragraph: ReadParagraph) {
        val mine = ++sampleGeneration
        val path = withContext(Dispatchers.IO) {
            val chapters = Store.manifest(bookId)?.optJSONArray("chapters") ?: error(S.s_chua_nghe_thu_duoc_f7601d1f)
            val item = (0 until chapters.length()).mapNotNull(chapters::optJSONObject).firstOrNull { it.optInt("id") == chapter }
                ?: error(S.s_chua_nghe_thu_duoc_f7601d1f)
            Store.file(bookId, item.getString("file")).takeIf { it.isFile }?.path
        }
        if (mine != sampleGeneration) return
        if (path != null) player.playRange(path, paragraph.startMs.toInt(), paragraph.endMs.toInt(), {}, {})
        else {
            val destination = withContext(Dispatchers.IO) { Store.editDestination(bookId) } ?: error(S.s_chua_nghe_thu_duoc_f7601d1f)
            val clips = (app as? AbookApplication)?.studio?.session(destination.first.orEmpty())?.clips ?: error(S.s_chua_nghe_thu_duoc_f7601d1f)
            remoteSample = clips
            clips.toggle("player-line-${paragraph.line?.stableId}", ClipSpec(destination.first.orEmpty(), StudioPaths.chapterAudio(destination.second, chapter), paragraph.startMs.toInt(), paragraph.endMs.toInt()))
        }
    }

    override fun stopSample() { ++sampleGeneration; player.stop(); remoteSample?.stop(); remoteSample = null }
}

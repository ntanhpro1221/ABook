package vn.abook.player.ui.music

import kotlinx.coroutines.CompletableDeferred

/** Nguồn nhạc nền giả: nhạc từng cuốn và menu trong bộ nhớ; ghi lại mọi lần bảng bảo lõi đổi để test so lời gọi. Lần lưu có thể bị giữ bằng một cổng. */
class FakeMusicSource : MusicSource {
    var menu = MusicMenu(
        listOf(
            PlaylistSummary("school_light", "Học đường nhẹ", "Piano sáng, đàn dây mỏng.", 95),
            PlaylistSummary("night_rain", "Đêm mưa", "Pad trầm, tiếng mưa xa.", 480),
        ),
        mine = 0, scene = true,
    )
    val books = HashMap<String, BookMusic>()
    val calls = ArrayList<String>()
    var menuReads = 0
    var bookError: MusicFailure? = null
    var changeError: MusicFailure? = null
    var changeGate: CompletableDeferred<Unit>? = null
    var importResult: (List<String>) -> MusicImported = { MusicImported("Đã thêm ${it.size} bài.", emptyList(), true) }

    override suspend fun menu(): MusicMenu { menuReads++; return menu }

    override suspend fun book(id: String): BookMusic {
        bookError?.let { throw it }
        return books[id] ?: BookMusic(MusicKind.None)
    }

    private suspend fun change(id: String, call: String, apply: (BookMusic) -> BookMusic): BookMusic {
        calls += call
        changeGate?.await()
        changeError?.let { throw it }
        return apply(books.getValue(id)).also { books[id] = it }
    }

    override suspend fun choose(id: String, playlist: String?): BookMusic =
        change(id, "choose $id $playlist") { it.copy(playlist = playlist ?: MusicText.SCENE, playlistAuto = playlist == null) }

    override suspend fun level(id: String, levelDb: Double): BookMusic = change(id, "level $id $levelDb") { it.copy(levelDb = levelDb) }

    override suspend fun enable(id: String, enabled: Boolean): BookMusic = change(id, "enable $id $enabled") { it.copy(enabled = enabled) }

    /** Nhạc của tôi cho "Đổi bài": mọi bài trừ bài đang ở đoạn ấy. */
    var mine = ArrayList<MineTrack>()
    var alternativesError: MusicFailure? = null

    override suspend fun silence(id: String, key: String, silenced: Boolean): BookMusic = change(id, "silence $id $key $silenced") { book ->
        book.copy(cues = book.cues.map { if (it.key == key) it.copy(silenced = silenced) else it })
    }

    override suspend fun pin(id: String, key: String, link: String?): BookMusic = change(id, "pin $id $key $link") { book ->
        val track = mine.firstOrNull { it.link == link }
        book.copy(cues = book.cues.map { cue ->
            when {
                cue.key != key -> cue
                track != null -> cue.copy(title = track.title, creator = track.creator, pinned = true, silenced = false)
                else -> cue.copy(title = "Bài gốc", creator = "Kevin MacLeod", pinned = false)
            }
        })
    }

    override suspend fun alternatives(id: String, key: String): List<MineTrack> {
        calls += "alternatives $id $key"
        alternativesError?.let { throw it }
        val current = books[id]?.cues?.firstOrNull { it.key == key }?.title
        return mine.filter { it.title != current }
    }

    override suspend fun importMine(uris: List<String>, progress: (done: Int, total: Int) -> Unit): MusicImported {
        calls += "import ${uris.size}"
        uris.indices.forEach { progress(it + 1, uris.size) }
        val result = importResult(uris)
        if (result.usable) menu = menu.copy(mine = menu.mine + uris.size)
        return result
    }
}

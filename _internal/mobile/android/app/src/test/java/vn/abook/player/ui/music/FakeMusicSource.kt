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

    override suspend fun importMine(uris: List<String>, progress: (done: Int, total: Int) -> Unit): MusicImported {
        calls += "import ${uris.size}"
        uris.indices.forEach { progress(it + 1, uris.size) }
        val result = importResult(uris)
        if (result.usable) menu = menu.copy(mine = menu.mine + uris.size)
        return result
    }
}

package vn.abook.player.ui.data

/** Nguồn "Làm trước" giả cho test: ghi lại mọi lời gọi, trả trạng thái / ước đã định. */
class FakePrepareSource(
    var status: PrepareStatus = PrepareStatus(),
    private val plan: PreparePlan = PreparePlan(),
    private val failWith: String? = null,
) : PrepareSource {
    val calls = mutableListOf<String>()
    private val listeners = mutableListOf<(PrepareStatus) -> Unit>()
    val listening: Int get() = listeners.size

    fun push(next: PrepareStatus) { status = next; listeners.forEach { it(next) } }

    override suspend fun status() = status
    override suspend fun plan(voice: String, bookId: String, chapterIds: List<Int>): PreparePlan { calls += "plan $voice $chapterIds"; return plan }

    override suspend fun start(voice: String, bookId: String, chapterIds: List<Int>, label: String, chargingOnly: Boolean): PrepareStatus {
        failWith?.let { throw IllegalStateException(it) }
        calls += "start $voice $chapterIds $label charging=$chargingOnly"
        status = PrepareStatus("running", voice, label, bookId = bookId, chargingOnly = chargingOnly)
        return status
    }

    override suspend fun cancel(): PrepareStatus { calls += "cancel"; status = status.copy(state = "cancelled"); return status }
    override suspend fun setChargingOnly(on: Boolean): PrepareStatus { calls += "charging=$on"; status = status.copy(chargingOnly = on); return status }

    override fun listen(onStatus: (PrepareStatus) -> Unit): () -> Unit { listeners += onStatus; return { listeners -= onStatus } }
}

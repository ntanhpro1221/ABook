package vn.abook.player

import java.util.concurrent.Executors

/**
 * Việc song song có giới hạn và có trần thời gian tổng. Danh sách sách nghe thẳng hỏi máy tính một gói sách
 * cho mỗi cuốn đã đổi: nối đuôi nhau thì thư viện 100 cuốn đổi tên mất hàng phút (soát a101 F2).
 */
object Bounded {
    /**
     * `work(mục, hếtGiờ)` cho từng mục, tối đa [parallel] việc cùng lúc; kết quả theo thứ tự của mục. `hếtGiờ()` đúng khi đã quá [budgetMs] kể từ
     * lúc bắt đầu: việc chưa hỏi mạng thì khỏi hỏi (dùng bản đã cất), việc đã hỏi dở thì làm nốt (mỗi yêu cầu mạng đã có hạn riêng) - tổng thời
     * gian không quá [budgetMs] cộng một yêu cầu. Lỗi của một việc thì ném ra như chạy tuần tự.
     */
    fun <T, R> map(items: List<T>, parallel: Int, budgetMs: Long, work: (T, () -> Boolean) -> R): List<R> {
        if (items.isEmpty()) return emptyList()
        val deadline = System.nanoTime() + budgetMs * 1_000_000
        val expired = { System.nanoTime() - deadline >= 0 }
        if (parallel <= 1 || items.size == 1) return items.map { work(it, expired) }
        val pool = Executors.newFixedThreadPool(minOf(parallel, items.size)) { task -> Thread(task, "abook-bounded").apply { isDaemon = true } }
        try {
            val futures = items.map { item -> pool.submit<R> { work(item, expired) } }
            return futures.map {
                try {
                    it.get()
                } catch (error: java.util.concurrent.ExecutionException) {
                    throw error.cause ?: error
                }
            }
        } finally {
            pool.shutdownNow()
        }
    }
}

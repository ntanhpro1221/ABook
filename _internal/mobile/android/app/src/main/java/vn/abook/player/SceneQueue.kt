package vn.abook.player

import java.util.concurrent.Future
import java.util.concurrent.FutureTask
import java.util.concurrent.PriorityBlockingQueue
import java.util.concurrent.ThreadPoolExecutor
import java.util.concurrent.TimeUnit

/**
 * Hàng dựng nhạc theo cảnh, MỘT luồng - bản Kotlin của `music_nnscene.Builder` bên máy tính: việc có số ưu tiên nhỏ đi trước (chương đang nghe 0, các chương kế 1, 2, ...; cùng số thì
 * ai tới trước), nên nhảy về chương đang ở sau mấy chương kế đã xếp hàng thì chương đang nghe vẫn được dựng TRƯỚC; việc cùng (cuốn, chương) chỉ chạy một lần (xếp lại với số ưu tiên nhỏ hơn
 * thì được đẩy lên); [cancelOthers] bỏ việc chưa chạy của cuốn khác (đổi cuốn - không còn ai chờ chúng), [cancelOutside] bỏ việc chưa chạy của cuốn này ngoài các chương còn cần.
 * Việc đang chạy không ngắt được (chạy nốt). Chạy được trong test JVM.
 */
class SceneQueue(name: String = "scene-music") {
    private class Task(val key: String, val book: String, @Volatile var priority: Int, private val sequence: Long, work: Runnable) :
        FutureTask<Unit>(work, Unit), Comparable<Task> {
        override fun compareTo(other: Task): Int = compareValuesBy(this, other, { it.priority }, { it.sequence })
    }

    private val executor = ThreadPoolExecutor(1, 1, 0L, TimeUnit.MILLISECONDS, PriorityBlockingQueue<Runnable>()) { runnable ->
        Thread(runnable, name).apply { isDaemon = true; priority = Thread.MIN_PRIORITY }
    }
    private val tasks = HashMap<String, Task>() // "cuốn/chương" -> việc chưa xong
    private var next = 0L

    private fun keyOf(book: String, chapter: Int) = "$book/$chapter"

    /** Xếp `work` cho (cuốn, chương) với số ưu tiên `priority`. Đã có việc ấy chưa xong thì dùng lại nó (số ưu tiên nhỏ hơn thì đẩy lên trước). Trả việc để chờ. */
    @Synchronized
    fun submit(book: String, chapter: Int, priority: Int, work: () -> Unit): Future<*> {
        val key = keyOf(book, chapter)
        tasks[key]?.takeIf { !it.isDone }?.let { existing ->
            // Chưa chạy mà cần đi sớm hơn: lấy ra khỏi hàng, đặt lại số, xếp lại (đang chạy rồi thì thôi).
            if (priority < existing.priority && executor.queue.remove(existing)) {
                existing.priority = priority
                executor.execute(existing)
            }
            return existing
        }
        lateinit var task: Task
        task = Task(key, book, priority, next++) {
            try {
                work()
            } finally {
                synchronized(this) { if (tasks[key] === task) tasks.remove(key) }
            }
        }
        tasks[key] = task
        executor.execute(task)
        return task
    }

    /** Đang nghe cuốn `book`: việc chưa chạy của cuốn khác bỏ đi. */
    @Synchronized
    fun cancelOthers(book: String) = cancelWhere { it.book != book }

    /** Việc chưa chạy của cuốn `book` mà chương không nằm trong `wanted` (người nghe đã đi chỗ khác) bỏ đi. */
    @Synchronized
    fun cancelOutside(book: String, wanted: Collection<Int>) {
        val keep = wanted.map { keyOf(book, it) }.toSet()
        cancelWhere { it.book == book && it.key !in keep }
    }

    private fun cancelWhere(match: (Task) -> Boolean) {
        for (task in tasks.values.filter(match)) {
            task.cancel(false) // đang chạy thì chạy nốt; chưa chạy thì không bao giờ chạy
            executor.remove(task)
            tasks.remove(task.key)
        }
    }
}

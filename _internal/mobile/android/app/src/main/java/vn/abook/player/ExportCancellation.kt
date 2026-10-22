package vn.abook.player

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequest
import androidx.work.WorkManager
import java.util.UUID

/** Dấu Dừng bền vững theo id việc: ghi xong TRƯỚC khi WorkManager nhận huỷ, kể cả nút trên thông báo và xuất thay lượt cũ. */
object ExportCancellation {
    private fun prefs(context: Context) = context.getSharedPreferences("export_cancellation", Context.MODE_PRIVATE)

    internal fun markThenCancel(mark: () -> Boolean, cancel: () -> Unit) {
        check(mark()) { "Không lưu được yêu cầu dừng xuất" }
        cancel()
    }

    fun cancelled(context: Context, id: UUID): Boolean = prefs(context).getBoolean("cancel:$id", false)

    @Synchronized
    fun cancel(context: Context, id: UUID) {
        markThenCancel({ prefs(context).edit().putBoolean("cancel:$id", true).commit() }) {
            WorkManager.getInstance(context).cancelWorkById(id)
        }
    }

    @Synchronized
    fun cancel(context: Context, name: String) {
        // WorkManager là nguồn id, kể cả việc đã có từ bản app cũ chưa ghi dấu của helper này. Gọi từ luồng I/O.
        val work = WorkManager.getInstance(context).getWorkInfosForUniqueWork(name).get()
        for (info in work) if (!info.state.isFinished) cancel(context, info.id)
    }

    @Synchronized
    fun enqueue(context: Context, name: String, request: OneTimeWorkRequest) {
        cancel(context, name)
        WorkManager.getInstance(context).enqueueUniqueWork(name, ExistingWorkPolicy.REPLACE, request)
    }

    fun stopIntent(context: Context, id: UUID): PendingIntent = PendingIntent.getBroadcast(
        context, 0, Intent(context, ExportCancelReceiver::class.java).setAction("vn.abook.player.STOP_EXPORT:$id")
            .putExtra("work", id.toString()), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )
}

/** Receiver riêng của app, không xuất ra ngoài; thông báo không đi thẳng tới nút huỷ của WorkManager. */
class ExportCancelReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val id = intent.getStringExtra("work")?.let { runCatching { UUID.fromString(it) }.getOrNull() } ?: return
        ExportCancellation.cancel(context, id)
    }
}

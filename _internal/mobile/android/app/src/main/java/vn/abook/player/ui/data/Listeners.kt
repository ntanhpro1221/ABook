package vn.abook.player.ui.data

import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.buffer
import kotlinx.coroutines.flow.callbackFlow

/**
 * Luồng tin từ một hàm `listen(callback)` của lõi: gọi `listen` khi có người nghe, gỡ bằng hàm nó trả khi hết người nghe.
 * Hàng đợi KHÔNG giới hạn: mặc định của `callbackFlow` chỉ đệm 64 tin và `trySend` bỏ tin khi đầy - luồng chính bận lâu thì rơi cả tin cuối
 * (xong / lỗi) và màn kẹt ở "Đang xuất" / "Đang tải" mãi. Tin ít và nhỏ, giữ hết rẻ hơn mất một tin cuối.
 */
fun <T> listenerFlow(listen: (send: (T) -> Unit) -> (() -> Unit)): Flow<T> = callbackFlow {
    val stop = listen { trySend(it) }
    awaitClose { stop() }
}.buffer(Channel.UNLIMITED)

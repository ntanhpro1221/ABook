package vn.abook.player.ui.data

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.repeatOnLifecycle
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.isActive
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.conflate
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.onStart

/** Entry/connectivity snapshots also run while visible in PiP (STARTED, but paused). */
internal suspend fun refreshWhenStarted(lifecycle: Lifecycle, changes: Flow<Unit>, refresh: suspend () -> Unit) {
    lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
        changes.onStart { emit(Unit) }.conflate().collect { refresh() }
    }
}

internal fun interface RefreshClock {
    suspend fun delay(milliseconds: Long)
}

/**
 * LibraryServer and desktop sync expose snapshots, not player/library subscriptions.
 * Only visible remote playback needs a ticker; idle/hidden activities have no timer.
 * collectLatest cancels both a pending clock wait and refresh when playback stops.
 */
internal suspend fun refreshRemoteWhileStarted(
    lifecycle: Lifecycle,
    remotePlaying: Flow<Boolean>,
    clock: RefreshClock = RefreshClock { kotlinx.coroutines.delay(it) },
    refresh: suspend () -> Unit,
    syncStreamed: () -> Unit,
) {
    lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
        var wasPlaying = false
        remotePlaying.distinctUntilChanged().collectLatest { playing ->
            if (!playing) {
                if (wasPlaying) syncStreamed() // Include the final saved position.
                wasPlaying = false
                return@collectLatest
            }
            wasPlaying = true
            var ticks = 0
            while (isActive) {
                clock.delay(2_000)
                refresh()
                ticks++
                if (ticks % 4 == 0) syncStreamed()
            }
        }
    }
}

internal fun networkChanges(context: Context): Flow<Unit> = callbackFlow {
    val manager = context.getSystemService(ConnectivityManager::class.java)
    val callback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) { trySend(Unit) }
        override fun onLost(network: Network) { trySend(Unit) }
    }
    manager.registerDefaultNetworkCallback(callback)
    awaitClose { manager.unregisterNetworkCallback(callback) }
}.conflate()

package vn.abook.player.ui.motion

import android.database.ContentObserver
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Box
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.MotionDurationScale
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.withContext
import vn.abook.player.ui.theme.MotionMs

/** Observe the OS setting live. Reduced transitions keep a short fade even when system animation scale is zero. */
@Composable
fun rememberReducedMotion(): Boolean {
    val resolver = LocalContext.current.contentResolver
    fun read() = Settings.Global.getFloat(resolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
    var reduced by remember(resolver) { mutableStateOf(read()) }
    DisposableEffect(resolver) {
        val observer = object : ContentObserver(Handler(Looper.getMainLooper())) {
            override fun onChange(selfChange: Boolean) { reduced = read() }
        }
        resolver.registerContentObserver(Settings.Global.getUriFor(Settings.Global.ANIMATOR_DURATION_SCALE), false, observer)
        onDispose { resolver.unregisterContentObserver(observer) }
    }
    return reduced
}

internal object FadeDurationScale : MotionDurationScale { override val scaleFactor = 1f }

/** Keep outgoing content alive until its 120 ms fade has finished; geometry switches without interpolation. */
@Composable
fun ReducedFade(visible: Boolean, content: @Composable () -> Unit) {
    var retained by remember { mutableStateOf(visible) }
    val alpha = remember { Animatable(if (visible) 1f else 0f) }
    LaunchedEffect(visible) {
        if (visible) retained = true
        withContext(FadeDurationScale) { alpha.animateTo(if (visible) 1f else 0f, tween(MotionMs.REDUCED_FADE_MS)) }
        if (!visible) retained = false
    }
    if (retained) Box(Modifier.graphicsLayer { this.alpha = alpha.value }) { content() }
}

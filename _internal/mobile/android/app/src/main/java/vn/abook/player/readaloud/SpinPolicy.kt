package vn.abook.player.readaloud

import android.content.Context
import android.os.BatteryManager

/**
 * Whether ONNX Runtime's pool threads may spin between ops (`session.intra_op.allow_spinning`) in the Supertonic and VieNeu Nano sessions. Spinning keeps the
 * big cores awake between two graph nodes: on the OPPO CPH2121 (dev/spin, 7 runs per cell, 4 threads, unplugged) it cut a 64-character Supertonic fast chunk
 * from 3.12 s to 2.52 s and a 128-character one from 5.10 s to 4.45 s (Nano 85 / 171 phones: 2.44 -> 2.03 s, 4.69 -> 3.73 s), the same bytes out, at the price of
 * battery. So only a phone on the charger spins; the choice is made when the engine is loaded (a session is not rebuilt when the cable moves; the next load follows).
 */
object SpinPolicy {
    fun spinning(charging: Boolean): Boolean = charging

    fun charging(context: Context): Boolean = context.getSystemService(BatteryManager::class.java)?.isCharging == true

    fun spinning(context: Context): Boolean = spinning(charging(context))
}

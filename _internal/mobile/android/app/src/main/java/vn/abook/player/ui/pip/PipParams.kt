package vn.abook.player.ui.pip

import android.app.PictureInPictureParams
import android.app.RemoteAction
import android.content.Context
import android.graphics.drawable.Icon
import android.os.Build
import android.util.Rational
import androidx.annotation.RequiresApi
import androidx.compose.runtime.Immutable
import vn.abook.player.Playback
import vn.abook.player.PlayerWidget

/** Ba nút hệ thống của cửa sổ nhỏ, theo thứ tự từ trái sang phải. */
enum class PipKind { Back, Toggle, Forward }

/** Một nút của PiP: nhãn (đọc cho trình đọc màn hình), lệnh phát sóng mà nó gửi và mã yêu cầu của PendingIntent. */
@Immutable
data class PipButton(val kind: PipKind, val label: String, val action: String, val code: Int)

/**
 * Điều cửa sổ nhỏ cần biết từ trạng thái phát - hàm thuần, thử không cần Android: tỉ lệ khung, ba nút (đổi Phát / Tạm dừng theo `playing`) và có tự vào PiP khi rời app
 * không. Không có sách mở thì không nút nào (và không tự vào).
 */
@Immutable
data class PipPlan(val hasBook: Boolean, val playing: Boolean, val autoEnter: Boolean, val buttons: List<PipButton>) {
    val ratioWidth: Int get() = PipParams.RATIO_WIDTH
    val ratioHeight: Int get() = PipParams.RATIO_HEIGHT
}

/**
 * Dựng [PictureInPictureParams] từ trạng thái phát (docs/DESIGN.md "Khay hệ thống và cửa sổ mini", phần điện thoại). Khung 2:3 = tỉ lệ bìa, nên bìa phủ kín không
 * bị cắt. Nút hệ thống đi cùng đường với nút của widget màn hình chính ([PlayerWidget.controlIntent] -> `onReceive`): phát / tạm dừng, lùi, tới đều qua đúng lõi
 * phát, kể cả khi giao diện đã bị đóng. Icon vẽ lại từ chính vector của trình phát ([PipIcons]).
 */
object PipParams {
    /** Tỉ lệ bìa chuẩn (rộng : cao) - cũng là tỉ lệ của BookCover. */
    const val RATIO_WIDTH = 2
    const val RATIO_HEIGHT = 3

    /** Tự vào PiP khi rời app: có sách mở VÀ công tắc "Tự mở cửa sổ mini" bật. */
    fun autoEnter(hasBook: Boolean, switchOn: Boolean): Boolean = hasBook && switchOn

    fun plan(playing: Boolean, hasBook: Boolean, switchOn: Boolean): PipPlan = PipPlan(
        hasBook, playing, autoEnter(hasBook, switchOn),
        if (!hasBook) emptyList() else listOf(
            PipButton(PipKind.Back, "Lùi ${Playback.SKIP_SECONDS} giây", PlayerWidget.ACTION_BACK, 2),
            PipButton(PipKind.Toggle, if (playing) "Tạm dừng" else "Phát", PlayerWidget.ACTION_TOGGLE, 1),
            PipButton(PipKind.Forward, "Tới ${Playback.SKIP_SECONDS} giây", PlayerWidget.ACTION_FORWARD, 3),
        ),
    )

    @RequiresApi(Build.VERSION_CODES.O)
    fun build(context: Context, plan: PipPlan): PictureInPictureParams {
        val builder = PictureInPictureParams.Builder()
            .setAspectRatio(Rational(RATIO_WIDTH, RATIO_HEIGHT))
            .setActions(plan.buttons.map { button ->
                RemoteAction(
                    Icon.createWithBitmap(PipIcons.bitmap(context, button.kind, plan.playing)),
                    button.label, button.label,
                    PlayerWidget.controlIntent(context, button.action, button.code),
                )
            })
        // Android 12+: hệ thống tự vào PiP khi vuốt về màn hình chính. Cũ hơn: Activity gọi enterPictureInPictureMode trong onUserLeaveHint.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) builder.setAutoEnterEnabled(plan.autoEnter)
        return builder.build()
    }
}

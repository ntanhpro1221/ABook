package vn.abook.player

/** Minimum content sizes calculated from res/layout/widget_player*.xml (dp). */
object WidgetLayout {
    enum class Size { SMALL, MEDIUM, LARGE }

    // 16 padding + 40 cover + 4 + 4 text margins + 44 play; height: 16 + 44.
    const val SMALL_WIDTH_DP = 108
    const val SMALL_HEIGHT_DP = 60
    // 12 padding + 236 controls (including the full 64dp timer label).
    // Height: 12 padding + 32 title/cover row + 4 gap + 4 progress + 44 controls = 96.
    const val MEDIUM_WIDTH_DP = 248
    const val MEDIUM_HEIGHT_DP = 96
    // Width: 24 padding + 84 cover + 12 gap + 236 controls = 356.
    // Height: 24 padding + max(84 cover, 16 book + 20 chapter + 8 gap + 4 progress
    //         + 6 gap + 44 controls) = 122; text row heights are explicit in XML.
    const val LARGE_WIDTH_DP = 356
    const val LARGE_HEIGHT_DP = 122

    fun select(width: Int, height: Int): Size = when {
        width >= LARGE_WIDTH_DP && height >= LARGE_HEIGHT_DP -> Size.LARGE
        width >= MEDIUM_WIDTH_DP && height >= MEDIUM_HEIGHT_DP -> Size.MEDIUM
        else -> Size.SMALL
    }
}

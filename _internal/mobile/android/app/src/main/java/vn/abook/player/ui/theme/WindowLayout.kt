package vn.abook.player.ui.theme

/** Content window classes shared by phones, split-screen windows and tablets. */
internal data class WindowLayout(val width: WidthClass, val short: Boolean) {
    val twoPane: Boolean get() = width >= WidthClass.EXPANDED || short && width >= WidthClass.MEDIUM
    val playerPanes: Boolean get() = width >= WidthClass.LARGE || short && width >= WidthClass.MEDIUM
    val floatingSheet: Boolean get() = twoPane
}

internal fun windowLayout(widthDp: Float, heightDp: Float) = WindowLayout(widthClass(widthDp.coerceAtLeast(0f)), heightDp < 480f)

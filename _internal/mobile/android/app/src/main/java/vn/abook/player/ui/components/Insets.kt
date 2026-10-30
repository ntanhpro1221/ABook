package vn.abook.player.ui.components

import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.runtime.Composable
import androidx.compose.ui.unit.Dp
import vn.abook.player.ui.theme.Dim

/**
 * Chỗ chừa dưới chân của thanh đáy (thanh tab): thanh điều hướng hệ thống chiếm bao nhiêu thì chừa bấy nhiêu, nhưng KHÔNG BAO GIỜ dưới [floor]. Máy cử chỉ ẩn vạch
 * (ColorOS: inset đáy ~0) báo inset 0 - vạch hổ phách của tab nằm sát mép dưới màn (soát điện thoại thật 30-10). Hàm thuần để test kiểm.
 */
fun bottomClearance(inset: Dp, floor: Dp = Dim.s8): Dp = if (inset > floor) inset else floor

/** [bottomClearance] của thanh điều hướng hiện tại. */
@Composable
fun navigationClearance(): Dp = bottomClearance(WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding())

package vn.abook.player.ui.components

import androidx.compose.foundation.background
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.tween
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import vn.abook.player.S
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.MotionMs

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun BookMetadataDetails(book: ListenBook) {
    var expanded by remember(book.id) { mutableStateOf(false) }
    val metadata = book.metadata
    var overflows by remember(metadata.summary) { mutableStateOf(false) }
    Column(Modifier.fillMaxWidth().testTag("book_metadata"), verticalArrangement = Arrangement.spacedBy(Dim.s8)) {
        Reveal(book.author.isNotEmpty()) { BasicText(S.s_tac_gia_0ec4731b + " " + book.author, style = Abook.type.bodySmall) }
        Reveal(metadata.illustrator.isNotEmpty()) { BasicText(S.s_bookmeta_illustrator + " " + metadata.illustrator, style = Abook.type.bodySmall) }
        Reveal(metadata.altTitles.isNotEmpty()) { BasicText(S.s_bookmeta_alt_titles + " " + metadata.altTitles.joinToString("; "), style = Abook.type.bodySmall) }
        Reveal(metadata.genres.isNotEmpty()) { FlowRow(Modifier.semantics { contentDescription = S.s_bookmeta_genres }, horizontalArrangement = Arrangement.spacedBy(Dim.s8), verticalArrangement = Arrangement.spacedBy(Dim.s8)) {
            for (genre in metadata.genres) BasicText(genre, Modifier.background(Abook.colors.bgSunken, RoundedCornerShape(Dim.radiusControl)).padding(horizontal = Dim.s8, vertical = Dim.s4), Abook.type.caption.copy(color = Abook.colors.text2))
        } }
        Reveal(metadata.summary.isNotEmpty()) { Column(verticalArrangement = Arrangement.spacedBy(Dim.s8)) {
            BasicText(S.s_tom_tat_b4bb3064, style = Abook.type.label)
            BasicText(metadata.summary, Modifier.fillMaxWidth().animateContentSize(tween(if (expanded) MotionMs.MEDIUM else MotionMs.MEDIUM_OUT, easing = if (expanded) Motion.Decelerate else Motion.Accelerate)),
                style = Abook.type.bodySmall.copy(color = Abook.colors.text2), maxLines = if (expanded) Int.MAX_VALUE else 3, overflow = TextOverflow.Clip,
                onTextLayout = { if (!expanded) overflows = it.hasVisualOverflow })
            Reveal(overflows || expanded) { InlineActionRow(if (expanded) S.s_thu_gon_1f6bf2c3 else S.s_xem_them_e0ac1b1e, { expanded = !expanded }, "book_summary_toggle",
                icon = if (expanded) LucidePaths.CHEVRON_UP else LucidePaths.CHEVRON_DOWN)
            }
        } }
    }
}

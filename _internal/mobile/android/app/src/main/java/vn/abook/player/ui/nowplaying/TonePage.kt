package vn.abook.player.ui.nowplaying

import vn.abook.player.ui.motion.SwapContent
import vn.abook.player.ui.motion.ContentLayout

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import vn.abook.player.*
import vn.abook.player.ui.components.*
import vn.abook.player.ui.screens.SheetField
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs
import kotlin.math.round

/**
 * Trang Âm sắc (tấm con của Âm thanh; tên + nút ← ở đầu tấm, [SheetTitle]). Vùng chỉnh ở trên - tên đang dùng, đường cong trong khung có vạch 0 dB,
 * năm thanh dọc - để chọn một âm sắc là thấy ngay đường cong và thanh đổi, không phải cuộn; danh sách Có sẵn / Của tôi ở dưới, dài bao nhiêu cũng chỉ
 * cuộn phần dưới. Mỗi dòng: dấu chọn tròn, tên, đường cong nhỏ xem trước; dòng Của tôi thêm nút … (Đổi tên / Nhân bản / Xoá), giữ rồi kéo để xếp lại.
 */
@Composable
fun TonePage(onBack: () -> Unit, leaveGuard: (((() -> Unit) -> Unit)?) -> Unit = {}) {
    val revision by AudioFx.toneChanges.collectAsState()
    val lib = remember(revision) { AudioFx.tones }
    val scroll = rememberScrollState()
    var pending by remember { mutableStateOf<(() -> Unit)?>(null) }
    var form by remember { mutableStateOf<String?>(null) }
    var target by remember { mutableStateOf("") }
    var name by remember { mutableStateOf("") }
    var undo by remember { mutableStateOf<DeletedTone?>(null) }
    var afterName by remember { mutableStateOf(false) }
    var menu by remember { mutableStateOf<String?>(null) }
    val suggest = S.s_tone_suggest(lib.mine.size + 1)
    fun leave(action: () -> Unit) {
        when {
            form != null -> { form = null; afterName = false }
            pending != null -> pending = null
            lib.hasEdits -> { AudioFx.changeTone { it.prepareLeave() }; pending = action }
            else -> action()
        }
    }
    val latestLeave by rememberUpdatedState<(() -> Unit) -> Unit>({ leave(it) })
    DisposableEffect(Unit) {
        leaveGuard { action -> latestLeave(action) }
        onDispose { leaveGuard(null) }
    }
    LaunchedEffect(pending, form) { if (pending != null || form != null) scroll.animateScrollTo(scroll.maxValue) }
    LaunchedEffect(undo) { if (undo != null) { scroll.animateScrollTo(scroll.maxValue); kotlinx.coroutines.delay(7000); undo = null } }
    fun finish() { if(AudioFx.tones.hasEdits){AudioFx.changeTone { it.prepareLeave() };return};val action=pending;pending=null;action?.invoke() }
    fun closeForm() { form = null }
    Column(Modifier.fillMaxWidth().fadeEdges(scroll).verticalScroll(scroll).testTag("tone_page")) {
        Row(Modifier.fillMaxWidth().heightIn(min=Dim.s48),verticalAlignment=Alignment.CenterVertically) {
            BasicText(lib.name,style=Abook.type.bodyStrong,modifier=Modifier.weight(1f).semantics { liveRegion=LiveRegionMode.Polite })
            Reveal(lib.selected.id=="draft"||lib.dirty) { TextAction(S.s_tone_save,{target="";name=suggest;form="save"},"tone_save") }
        }
        val bands=lib.selected.bands
        ToneChart(bands,Modifier.fillMaxWidth().height(104.dp).border(1.dp,Abook.colors.line,RoundedCornerShape(Dim.radiusControl))
            .padding(vertical=Dim.s12).semantics { contentDescription=S.s_am_sac_8c2f4e1a })
        Row(Modifier.fillMaxWidth().padding(top=Dim.s8)) { listOf(S.s_tone_band_0,S.s_tone_band_1,S.s_tone_band_2,S.s_tone_band_3,S.s_tone_band_4).forEachIndexed { i,label ->
            Column(Modifier.weight(1f),horizontalAlignment=Alignment.CenterHorizontally) {
                ClockLabel(S.s_tone_db(PlayerLabels.signed(bands[i])),style=Abook.type.caption.copy(color=Abook.colors.text2))
                ToneBand(label,bands[i]) { db->AudioFx.changeTone { it.edit(i,db) } }
                BasicText(label,style=Abook.type.caption.copy(color=Abook.colors.text2))
            }
        } }
        BasicText(S.s_tone_reset,style=Abook.type.caption.copy(color=Abook.colors.text2,textAlign=TextAlign.Center),
            modifier=Modifier.fillMaxWidth().padding(top=Dim.s8))
        ToneGroup(S.s_tone_builtins)
        ToneCatalog.presets.forEach { preset -> key(preset.id) { ToneRow(preset,lib.selected.id==preset.id);RowLine() } }
        ToneGroup(S.s_tone_mine)
        lib.mine.forEachIndexed { index,preset ->
            key(preset.id) {
                var distance by remember { mutableFloatStateOf(0f) }
                // Giữ rồi kéo cả dòng để xếp lại (không tay kéo riêng: dòng đã có dấu chọn, đường cong và nút …).
                val reorder=Modifier.pointerInput(preset.id) { detectDragGesturesAfterLongPress(onDragStart={distance=0f},onDrag={change,delta->
                    change.consume();distance+=delta.y
                    val steps=(distance/56.dp.toPx()).toInt()
                    if(steps!=0){AudioFx.changeTone { l->l.move(preset.id,l.mine.indexOfFirst { it.id==preset.id }+steps) };distance-=steps*56.dp.toPx()}
                }) }.semantics { stateDescription=S.s_tone_drag }
                Column(Modifier.fillMaxWidth()) {
                    ToneRow(preset,lib.selected.id==preset.id,reorder) {
                        Box(Modifier.size(Dim.s48).pressable { menu=if(menu==preset.id)null else preset.id }
                            .semantics { contentDescription=S.s_them_tuy_chon_cho_0_82a2cf4d(preset.name) }.testTag("tone_more_$index"),
                            contentAlignment=Alignment.CenterEnd) { MoreIcon(Abook.colors.text2) }
                    }
                    Reveal(menu==preset.id) {
                        Row(Modifier.fillMaxWidth().padding(start=32.dp),horizontalArrangement=Arrangement.spacedBy(Dim.s24)) {
                            TextAction(S.s_doi_ten_a2a0dc70,{menu=null;target=preset.id;name=preset.name;form="rename"},"tone_rename",align=Alignment.CenterStart)
                            TextAction(S.s_tone_duplicate,{menu=null;target=preset.id;name=suggest;form="duplicate"},"tone_duplicate",align=Alignment.CenterStart)
                            TextAction(S.s_xoa_777195ab,{menu=null;AudioFx.changeTone { undo=it.delete(preset.id) }},"tone_delete",align=Alignment.CenterStart,danger=true)
                        }
                    }
                    RowLine()
                }
            }
        }
        Row(Modifier.fillMaxWidth().heightIn(min=Dim.s48).pressable { target="";name=suggest;form="save" }.testTag("tone_add"),
            verticalAlignment=Alignment.CenterVertically) {
            PlusIcon(Abook.colors.accentText)
            Spacer(Modifier.width(Dim.s12))
            BasicText(S.s_tone_add,style=Abook.type.label.copy(color=Abook.colors.accentText))
        }
        Spacer(Modifier.height(Dim.s8))
        SwitchRow(S.s_copy_0aedb2b2cf2b,lib.scoped,{enabled->AudioFx.changeTone { it.scope(enabled) }},"tone_scope")
        SwapContent(pending, contentKey = { pending -> pending!=null }, layout = ContentLayout.Column) { pending ->
            if(pending!=null) {
                BasicText(S.s_tone_leave,style=Abook.type.body)
                TextAction(S.s_tone_overwrite,{AudioFx.changeTone { it.save(it.preset?.name?:suggest,true) };finish()},"tone_overwrite")
                TextAction(S.s_tone_new,{name=suggest;afterName=true;form="save"},"tone_new")
                TextAction(S.s_tone_discard,{AudioFx.changeTone { it.discard() };finish()},"tone_discard")
            }
        }
        SwapContent(form, contentKey = { form -> form!=null }, layout = ContentLayout.Column) { form ->
            if(form!=null) {
                SheetField(name,{name=it.take(80)},S.s_tone_name,"tone_name")
                Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
                    TextAction(S.s_tone_back,{closeForm();afterName=false},"tone_cancel")
                    TextAction(S.s_luu_e91f26c0,{
                        if(name.isNotBlank()) {
                            AudioFx.changeTone { when(form){"rename"->it.rename(target,name);"duplicate"->it.duplicate(target,name);else->it.save(name)} }
                            closeForm();if(afterName){afterName=false;finish()}
                        }
                    },"tone_confirm")
                }
            }
        }
        undo?.let { token->Row(Modifier.fillMaxWidth().background(Abook.colors.bg).padding(Dim.s8),verticalAlignment=Alignment.CenterVertically) {
            BasicText(S.s_tone_deleted,style=Abook.type.bodySmall,modifier=Modifier.weight(1f).semantics { liveRegion=LiveRegionMode.Polite })
            TextAction(S.s_hoan_tac_e72ff675,{AudioFx.changeTone { it.undo(token) };undo=null},"tone_undo")
        } }
    }
}

/** Tên nhóm (Có sẵn / Của tôi): chữ nhỏ mực phụ, cách vùng trên 16, sát hàng của nó. */
@Composable
private fun ToneGroup(title: String) {
    BasicText(title,style=Abook.type.bodySmall.copy(color=Abook.colors.text2),modifier=Modifier.padding(top=Dim.s16,bottom=Dim.s4))
}

/** Một âm sắc: dấu chọn tròn (đầy khi đang dùng), tên, đường cong nhỏ xem trước; [trailing] = nút … của dòng Của tôi. */
@Composable
private fun ToneRow(preset: TonePreset, chosen: Boolean, modifier: Modifier = Modifier, trailing: (@Composable () -> Unit)? = null) {
    val colors=Abook.colors
    Row(modifier.fillMaxWidth().heightIn(min=56.dp).pressable(Role.RadioButton) { AudioFx.changeTone { it.select(preset.id) } }
        .semantics { selected=chosen }.testTag("tone_${preset.id}"),verticalAlignment=Alignment.CenterVertically) {
        val dot by animateFloatAsState(if(chosen)1f else 0f,tween(MotionMs.FAST),label="tone-dot")
        Canvas(Modifier.size(20.dp)) {
            drawCircle(if(chosen)colors.accent else colors.text2,size.minDimension/2-1.dp.toPx(),style=Stroke(2.dp.toPx()))
            if(dot>0f)drawCircle(colors.accent,5.dp.toPx()*dot)
        }
        Spacer(Modifier.width(Dim.s12))
        BasicText(preset.name,style=Abook.type.body,modifier=Modifier.weight(1f).padding(vertical=Dim.s8))
        Spacer(Modifier.width(Dim.s8))
        Canvas(Modifier.size(48.dp,24.dp)) { drawTone(preset.bands,if(chosen)colors.accent else colors.text2,1.5.dp,dots=false) }
        if(trailing!=null)trailing() else Spacer(Modifier.width(Dim.s4))
    }
}

/** Đường cong lớn: vạch 0 dB đứt nét giữa khung, năm điểm thẳng tâm năm thanh dọc bên dưới. */
@Composable
private fun ToneChart(bands: List<Double>, modifier: Modifier) {
    val colors=Abook.colors
    Canvas(modifier) {
        drawLine(colors.line,Offset(0f,size.height/2),Offset(size.width,size.height/2),1.dp.toPx(),pathEffect=PathEffect.dashPathEffect(floatArrayOf(4.dp.toPx(),4.dp.toPx())))
        drawTone(bands,colors.accent,2.dp,dots=true)
    }
}

/** Một đường cong âm sắc (lớn và nhỏ dùng chung): điểm i ở tâm cột thứ i trong năm cột, ±12 dB chạm mép trên / dưới, nối mềm, hai đầu kéo phẳng ra mép. */
private fun DrawScope.drawTone(bands: List<Double>, color: Color, stroke: Dp, dots: Boolean) {
    val half=size.height/2-stroke.toPx()
    val points=bands.mapIndexed { i,db->Offset(size.width*(i+.5f)/bands.size,(size.height/2-db/12*half).toFloat()) }
    val path=Path().apply {
        moveTo(0f,points.first().y);lineTo(points.first().x,points.first().y)
        points.zipWithNext().forEach { (a,b)->val mid=(a.x+b.x)/2;cubicTo(mid,a.y,mid,b.y,b.x,b.y) }
        lineTo(size.width,points.last().y)
    }
    drawPath(path,color,style=Stroke(stroke.toPx(),cap=StrokeCap.Round))
    if(dots)points.forEach { drawCircle(color,3.dp.toPx(),it) }
}

/** Thanh dọc −12…+12 dB: vạch 0 giữa rãnh, đoạn tô từ 0 tới núm; chạm / kéo đặt mức, chạm đúp về 0. */
@Composable
private fun ToneBand(label: String,value: Double,onChange: (Double)->Unit) {
    val colors=Abook.colors
    val update by rememberUpdatedState(onChange)
    fun at(y: Float,height: Int,pad: Float)=round((12-(y-pad)/(height-2*pad)*24).toDouble()).coerceIn(-12.0,12.0)
    Canvas(Modifier.width(48.dp).height(136.dp).testTag("tone_band_$label").semantics {
        contentDescription=label;stateDescription=S.s_tone_db(PlayerLabels.signed(value));progressBarRangeInfo=ProgressBarRangeInfo(value.toFloat(),-12f..12f)
        setProgress { update(it.toDouble().coerceIn(-12.0,12.0));true }
    }.pointerInput(Unit) { detectTapGestures(onDoubleTap={update(0.0)},onTap={update(at(it.y,size.height,10.dp.toPx()))}) }
        .pointerInput(Unit) { detectDragGestures(onDragStart={update(at(it.y,size.height,10.dp.toPx()))},onDrag={c,_->c.consume();update(at(c.position.y,size.height,10.dp.toPx()))}) }) {
        val pad=10.dp.toPx();val x=size.width/2;val zero=size.height/2
        val y=(pad+(12-value)/24*(size.height-2*pad)).toFloat()
        drawLine(colors.line,Offset(x,pad),Offset(x,size.height-pad),4.dp.toPx(),cap=StrokeCap.Round)
        drawLine(colors.text2,Offset(x-8.dp.toPx(),zero),Offset(x+8.dp.toPx(),zero),1.dp.toPx())
        drawLine(colors.accent,Offset(x,zero),Offset(x,y),4.dp.toPx(),cap=StrokeCap.Round)
        drawCircle(colors.accent,7.dp.toPx(),Offset(x,y))
    }
}

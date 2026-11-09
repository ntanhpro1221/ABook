package vn.abook.player.ui.nowplaying

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.dp
import vn.abook.player.*
import vn.abook.player.ui.components.*
import vn.abook.player.ui.screens.SheetField
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import kotlin.math.round

@Composable
fun TonePage(onBack: () -> Unit, leaveGuard: (((() -> Unit) -> Unit)?) -> Unit = {}) {
    val revision by AudioFx.toneChanges.collectAsState()
    val lib = remember(revision) { AudioFx.tones }
    val scroll = rememberScrollState()
    val accent=Abook.colors.accent
    var pending by remember { mutableStateOf<(() -> Unit)?>(null) }
    var form by remember { mutableStateOf<String?>(null) }
    var target by remember { mutableStateOf("") }
    var name by remember { mutableStateOf("") }
    var undo by remember { mutableStateOf<DeletedTone?>(null) }
    var afterName by remember { mutableStateOf(false) }
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
    Column(Modifier.fillMaxWidth().fadeEdges(scroll).verticalScroll(scroll).testTag("tone_page")) {
        TextAction(S.s_tone_back, { leave(onBack) }, "tone_back", align=Alignment.CenterStart)
        listOf(S.s_tone_builtins to ToneCatalog.presets, S.s_tone_mine to lib.mine).forEach { (title, presets) ->
            BasicText(title, style=Abook.type.bodySmall.copy(color=Abook.colors.text2), modifier=Modifier.padding(top=Dim.s12,bottom=Dim.s4))
            presets.forEach { preset ->
                key(preset.id) {
                    Row(Modifier.fillMaxWidth().heightIn(min=48.dp),verticalAlignment=Alignment.CenterVertically) {
                        Box(Modifier.weight(1f).heightIn(min=48.dp).pressable { AudioFx.changeTone { it.select(preset.id) } }
                            .semantics { selected=lib.selected.id==preset.id }.testTag("tone_${preset.id}"),contentAlignment=Alignment.CenterStart) {
                            BasicText(preset.name, style=Abook.type.body.copy(color=if(lib.selected.id==preset.id)Abook.colors.accentText else Abook.colors.text))
                        }
                        if(preset.id.startsWith("user:")) {
                            var distance by remember { mutableFloatStateOf(0f) }
                            Box(Modifier.size(48.dp).semantics { contentDescription=S.s_tone_drag }
                                .pointerInput(preset.id) { detectDragGesturesAfterLongPress(
                                    onDragStart={distance=0f},onDrag={change,delta->
                                        change.consume();distance+=delta.y
                                        val steps=(distance/48.dp.toPx()).toInt()
                                        if(steps!=0){AudioFx.changeTone { l->l.move(preset.id,l.mine.indexOfFirst { it.id==preset.id }+steps) };distance-=steps*48.dp.toPx()}
                                    }) },contentAlignment=Alignment.Center) { Canvas(Modifier.size(16.dp)) { for(i in 0..2) drawLine(accent,Offset(0f,i*size.height/3),Offset(size.width,i*size.height/3),2.dp.toPx()) } }
                        }
                    }
                }
            }
        }
        if(lib.selected.id.startsWith("user:")) Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
            TextAction(S.s_doi_ten_a2a0dc70,{target=lib.selected.id;name=lib.preset?.name?:suggest;form="rename"},"tone_rename")
            TextAction(S.s_tone_duplicate,{target=lib.selected.id;name=suggest;form="duplicate"},"tone_duplicate")
            TextAction(S.s_xoa_777195ab,{AudioFx.changeTone { undo=it.delete(lib.selected.id) }},"tone_delete")
        }
        BasicText(lib.name,style=Abook.type.body,modifier=Modifier.padding(top=Dim.s12))
        val bands=lib.selected.bands
        Canvas(Modifier.fillMaxWidth().height(96.dp).semantics { contentDescription=S.s_am_sac_8c2f4e1a }) {
            drawLine(accent.copy(alpha=.2f),Offset(0f,size.height/2),Offset(size.width,size.height/2))
            val path=Path();bands.forEachIndexed { i,db->val x=12.dp.toPx()+(size.width-24.dp.toPx())*i/4;val y=size.height/2-(db/24*size.height*.85).toFloat();if(i==0)path.moveTo(x,y)else path.lineTo(x,y);drawCircle(accent,3.dp.toPx(),Offset(x,y)) }
            drawPath(path,accent,style=Stroke(2.dp.toPx()))
        }
        Row(Modifier.fillMaxWidth()) { listOf(S.s_tone_band_0,S.s_tone_band_1,S.s_tone_band_2,S.s_tone_band_3,S.s_tone_band_4).forEachIndexed { i,label ->
            Column(Modifier.weight(1f),horizontalAlignment=Alignment.CenterHorizontally) {
                ClockLabel("${bands[i].toInt()} dB",style=Abook.type.caption)
                ToneBand(label,bands[i]) { db->AudioFx.changeTone { it.edit(i,db) } }
                BasicText(label,style=Abook.type.caption)
            }
        } }
        RowHint(S.s_tone_reset)
        if(lib.selected.id=="draft"||lib.dirty)TextAction(S.s_tone_save,{name=suggest;form="save"},"tone_save",align=Alignment.CenterStart)
        SwitchRow(S.s_tone_scope,lib.scoped,{enabled->AudioFx.changeTone { it.scope(enabled) }},"tone_scope")
        if(pending!=null) {
            BasicText(S.s_tone_leave,style=Abook.type.body)
            TextAction(S.s_tone_overwrite,{AudioFx.changeTone { it.save(it.preset?.name?:suggest,true) };finish()},"tone_overwrite")
            TextAction(S.s_tone_new,{name=suggest;afterName=true;form="save"},"tone_new")
            TextAction(S.s_tone_discard,{AudioFx.changeTone { it.discard() };finish()},"tone_discard")
        }
        if(form!=null) {
            SheetField(name,{name=it.take(80)},S.s_tone_name,"tone_name")
            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
                TextAction(S.s_tone_back,{form=null;afterName=false},"tone_cancel")
                TextAction(S.s_luu_e91f26c0,{
                    if(name.isNotBlank()) {
                        AudioFx.changeTone { when(form){"rename"->it.rename(target,name);"duplicate"->it.duplicate(target,name);else->it.save(name)} }
                        form=null;if(afterName){afterName=false;finish()}
                    }
                },"tone_confirm")
            }
        }
        undo?.let { token->Row(Modifier.fillMaxWidth().background(Abook.colors.bg).padding(Dim.s8),verticalAlignment=Alignment.CenterVertically) {
            BasicText(S.s_tone_deleted,style=Abook.type.bodySmall,modifier=Modifier.weight(1f).semantics { liveRegion=LiveRegionMode.Polite })
            TextAction(S.s_hoan_tac_e72ff675,{AudioFx.changeTone { it.undo(token) };undo=null},"tone_undo")
        } }
    }
}

@Composable
private fun ToneBand(label: String,value: Double,onChange: (Double)->Unit) {
    val colors=Abook.colors
    val update by rememberUpdatedState(onChange)
    fun at(y: Float,height: Int,pad: Float)=round((12-(y-pad)/(height-2*pad)*24).toDouble()).coerceIn(-12.0,12.0)
    Canvas(Modifier.width(48.dp).height(144.dp).testTag("tone_band_$label").semantics {
        contentDescription=label;stateDescription="$value dB";progressBarRangeInfo=ProgressBarRangeInfo(value.toFloat(),-12f..12f)
        setProgress { update(it.toDouble().coerceIn(-12.0,12.0));true }
    }.pointerInput(Unit) { detectTapGestures(onDoubleTap={update(0.0)},onTap={update(at(it.y,size.height,8.dp.toPx()))}) }
        .pointerInput(Unit) { detectDragGestures(onDragStart={update(at(it.y,size.height,8.dp.toPx()))},onDrag={c,_->c.consume();update(at(c.position.y,size.height,8.dp.toPx()))}) }) {
        val x=size.width/2;drawLine(colors.line,Offset(x,8.dp.toPx()),Offset(x,size.height-8.dp.toPx()),4.dp.toPx())
        val y=((12-value)/24*size.height).toFloat().coerceIn(8.dp.toPx(),size.height-8.dp.toPx());drawCircle(colors.accent,7.dp.toPx(),Offset(x,y))
    }
}

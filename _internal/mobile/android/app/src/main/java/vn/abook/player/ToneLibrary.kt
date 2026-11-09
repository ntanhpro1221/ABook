package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

data class TonePreset(val id: String, val name: String, val bands: List<Double>)
data class ToneSelection(val id: String = "off", val bands: List<Double> = List(5) { 0.0 })
data class DeletedTone(val preset: TonePreset, val index: Int, val shared: ToneSelection?, val books: Map<String, ToneSelection>, val draft: List<Double>?)

/** Device-local listener presets, independent of the book's recorded audio and casting. */
class ToneLibrary {
    val mine = mutableListOf<TonePreset>()
    val drafts = mutableMapOf<String,List<Double>>()
    var shared = ToneSelection()
    val books = mutableMapOf<String, ToneSelection>()
    var book = ""
    val scoped get() = book.isNotEmpty() && books.containsKey(book)
    val selected get() = if (scoped) books.getValue(book) else shared
    val preset get() = (ToneCatalog.presets + mine).find { it.id == selected.id }
    val dirty get() = selected.id.startsWith("user:") && preset?.bands != selected.bands
    val hasEdits get() = drafts.isNotEmpty()
    fun prepareLeave(): Boolean { val id=drafts.keys.firstOrNull()?:return false;select(id);return true }
    fun discard() { drafts.remove(selected.id);select(selected.id) }
    val name get() = if (dirty || selected.id == "draft") S.s_tone_draft else preset?.name ?: S.s_tat_3286064e
    private fun put(value: ToneSelection) { if (scoped) books[book] = value else shared = value }
    fun scope(enabled: Boolean) {
        if (book.isEmpty() || enabled == scoped) return
        if (enabled) books[book] = selected.copy() else books.remove(book)
    }
    fun select(id: String) { (ToneCatalog.presets + mine).find { it.id == id }?.let { put(ToneSelection(it.id, drafts[it.id] ?: it.bands)) } }
    fun edit(index: Int, value: Double) {
        if (index !in 0..4) return
        if (selected.id.startsWith("user:")) {
            val b=selected.bands.mapIndexed { i,n->if(i==index)if(value.isFinite())value.coerceIn(-12.0,12.0)else 0.0 else n }
            if(b==preset?.bands)drafts.remove(selected.id)else drafts[selected.id]=b
        }
        put(ToneSelection(if (selected.id.startsWith("user:")) selected.id else "draft",
            selected.bands.mapIndexed { i, n -> if (i == index) if (value.isFinite()) value.coerceIn(-12.0,12.0) else 0.0 else n }))
    }
    fun save(name: String, overwrite: Boolean = false): String? {
        if (name.isBlank()) return null
        drafts.remove(selected.id)
        val id = if (overwrite && selected.id.startsWith("user:")) selected.id else "user:${UUID.randomUUID()}"
        val p = TonePreset(id, name.trim().take(80), selected.bands.toList())
        val index = mine.indexOfFirst { it.id == id }; if (index >= 0) mine[index] = p else mine.add(p)
        if (shared.id == id) shared = ToneSelection(id, p.bands)
        books.keys.toList().forEach { if (books[it]?.id == id) books[it] = ToneSelection(id,p.bands) }
        put(ToneSelection(id,p.bands)); return id
    }
    fun rename(id: String, name: String) { val i=mine.indexOfFirst { it.id==id }; if(i>=0 && name.isNotBlank()) mine[i]=mine[i].copy(name=name.trim().take(80)) }
    fun duplicate(id: String, name: String) { mine.find { it.id==id }?.let { if(name.isNotBlank()) mine.add(it.copy(id="user:${UUID.randomUUID()}", name=name.trim().take(80))) } }
    fun move(id: String, to: Int) { val i=mine.indexOfFirst { it.id==id };if(i>=0){val p=mine.removeAt(i);mine.add(to.coerceIn(0,mine.size),p)} }
    fun delete(id: String): DeletedTone? {
        val i=mine.indexOfFirst { it.id==id };if(i<0)return null
        val p=mine.removeAt(i);val old=shared.takeIf { it.id==id };val affected=books.filterValues { it.id==id }
        if(old!=null)shared=ToneSelection();affected.keys.forEach { books[it]=ToneSelection() }
        return DeletedTone(p,i,old,affected,drafts.remove(id))
    }
    fun undo(token: DeletedTone) {
        if(mine.any { it.id==token.preset.id })return
        mine.add(token.index.coerceAtMost(mine.size),token.preset)
        token.draft?.let { drafts[token.preset.id]=it }
        if(token.shared!=null && shared.id=="off")shared=token.shared
        token.books.forEach { (b,s)->if(books[b]?.id=="off")books[b]=s }
    }
    fun json(): JSONObject {
        fun selection(s: ToneSelection)=JSONObject().put("id",s.id).put("bands",JSONArray(s.bands))
        return JSONObject().put("mine",JSONArray(mine.map { selection(ToneSelection(it.id,it.bands)).put("name",it.name) }))
            .put("drafts",JSONObject().also { o->drafts.forEach { (id,b)->o.put(id,JSONArray(b)) } }).put("shared",selection(shared)).put("books",JSONObject().also { o->books.forEach { (b,s)->o.put(b,selection(s)) } })
    }
    companion object {
        fun read(o: JSONObject): ToneLibrary = ToneLibrary().apply {
            fun bands(o: JSONObject)=List(5){i->o.optJSONArray("bands")?.optDouble(i,0.0)?.takeIf { it.isFinite() }?.coerceIn(-12.0,12.0)?:0.0}
            val rows=o.optJSONArray("mine")?:JSONArray()
            for(i in 0 until rows.length())rows.optJSONObject(i)?.let { p->
                val id=p.optString("id");val name=p.optString("name").trim().take(80)
                if(id.startsWith("user:") && name.isNotEmpty() && mine.none { it.id==id })mine.add(TonePreset(id,name,bands(p)))
            }
            fun selection(v: JSONObject?): ToneSelection {
                val id=v?.optString("id")?:"off"
                return if(v!=null && (id=="draft" || (ToneCatalog.presets+mine).any { it.id==id }))ToneSelection(id,bands(v)) else ToneSelection()
            }
            o.optJSONObject("drafts")?.let { d->d.keys().forEach { id->if(mine.any { it.id==id })drafts[id]=bands(JSONObject().put("bands",d.optJSONArray(id))) } }
            shared=selection(o.optJSONObject("shared"));o.optJSONObject("books")?.let { b->b.keys().forEach { books[it]=selection(b.optJSONObject(it)) } }
        }
    }
}

package vn.abook.player

import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.json.JSONObject
import java.io.File
import kotlin.math.*

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[35],application=android.app.Application::class)
class ToneLibraryTest {
    @Test fun editsSurviveAuditioningOtherPresetsAndReopen() {
        val l=ToneLibrary();l.select("clear");val id=l.save("First")!!;l.edit(0,9.0);l.select("bright")
        assertTrue(l.hasEdits);assertFalse(l.dirty);val copy=ToneLibrary.read(l.json());assertTrue(copy.prepareLeave());assertEquals(id,copy.selected.id)
        assertEquals(9.0,copy.selected.bands[0],0.0);copy.discard();assertFalse(copy.hasEdits);assertEquals(-4.0,copy.selected.bands[0],0.0)
    }
    @Test fun crudAndOrderingAndUndo() {
        val l=ToneLibrary();l.select("clear");l.edit(0,7.0);assertEquals("draft",l.selected.id)
        val id=l.save(" Mine ")!!;l.rename(id,"Renamed");assertEquals("Renamed",l.name)
        l.duplicate(id,"Copy");val copy=l.mine[1].id;l.move(copy,0);assertEquals(listOf(copy,id),l.mine.map { it.id })
        val token=l.delete(id)!!;assertEquals("off",l.selected.id);l.undo(token);assertEquals(id,l.selected.id)
        assertEquals(listOf(copy,id),l.mine.map { it.id });assertEquals(-4.0,ToneCatalog.presets[1].bands[0],0.0)
    }
    @Test fun bookScopePersistenceAndUndoDoesNotClobberLaterSelection() {
        val l=ToneLibrary();l.select("warm");l.book="a";l.scope(true);l.select("clear");val id=l.save("Book")!!
        l.book="b";assertEquals("warm",l.selected.id);l.book="a";assertEquals(id,l.selected.id)
        val copy=ToneLibrary.read(l.json());copy.book="a";assertEquals(id,copy.selected.id)
        val token=copy.delete(id)!!;copy.select("bright");copy.undo(token);assertEquals("bright",copy.selected.id)
        copy.scope(false);assertEquals("warm",copy.selected.id)
    }
    @Test fun editsWaitForSaveAndNewDoesNotOverwrite() {
        val l=ToneLibrary();l.select("clear");l.save("First");l.edit(2,12.0);assertTrue(l.dirty);assertEquals(2.0,l.preset!!.bands[2],0.0)
        l.save("First",true);assertFalse(l.dirty);assertEquals(1,l.mine.size)
        l.edit(1,-12.0);l.save("Second");assertEquals(2,l.mine.size);assertEquals(-2.0,l.mine[0].bands[1],0.0)
    }
    @Test fun offIsBitExactAcrossFullPcmRangeAndAfterFiltering() {
        val dsp=AudioFxDsp(48000,2);dsp.configure(AudioFxSettings(enabled=true,bands=List(5){12.0}))
        dsp.process(doubleArrayOf(1.0,-1.0));dsp.configure(AudioFxSettings())
        for(i in -32768..32767){val f=doubleArrayOf(i/32768.0,-i/32768.0);val original=f.copyOf();dsp.process(f);assertArrayEquals(original,f,0.0)}
    }
    @Test fun actualDspMatchesShared31FrequencyResponseCases() {
        val fixture=File("../../../abook/webui/assets/tone_response_cases.json").let { if(it.exists())it else File("../../abook/webui/assets/tone_response_cases.json") }
        val data=JSONObject(fixture.readText());val rows=data.getJSONArray("cases");val frequencies=data.getJSONArray("frequencies");var worst=0.0;var count=0
        for(ci in 0 until rows.length()) {
            val c=rows.getJSONObject(ci);val rate=c.getInt("rate");val p=ToneCatalog.presets.first { it.id==c.getString("id") }
            for(fi in 0 until frequencies.length()) {
                val frequency=frequencies.getDouble(fi);val dsp=AudioFxDsp(rate,2);dsp.configure(AudioFxSettings(enabled=p.id!="off",bands=p.bands))
                val f=DoubleArray(2);var energy=0.0;var source=0.0
                for(i in 0 until rate){val x=.001*sin(2*PI*frequency*i/rate);f[0]=x;f[1]=x;dsp.process(f);if(i>=rate/2){energy+=f[0]*f[0];source+=x*x}}
                val db=10*log10(energy/source);val error=abs(db-c.getJSONArray("db").getDouble(fi));worst=max(worst,error);count++
                assertTrue("${p.id} rate=$rate f=$frequency error=$error",error<=data.getDouble("toleranceDb"))
            }
        }
        println("TONE_RESPONSE_ANDROID measurements=$count worst_db=$worst")
    }
}

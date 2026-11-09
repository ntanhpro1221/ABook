package vn.abook.player

import androidx.media3.common.C
import androidx.media3.common.audio.AudioProcessor.AudioFormat
import androidx.media3.common.audio.AudioProcessor.StreamMetadata
import androidx.media3.common.audio.SonicAudioProcessor
import org.junit.Assert.*
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.*

class AudioFxTest {
    @Test fun presetsWithinOneDbAtEveryBand() {
        var worst = 0.0
        for (rate in listOf(24000,44100,48000)) for (preset in 0..4) for (band in 0..4) {
            // Frequencies above Nyquist are represented at the same .45*rate clamp as the engine.
            val frequency = min(AudioFxSettings.FREQUENCIES[band], rate*.45)
            val dsp=AudioFxDsp(rate,2)
            val settings=AudioFxSettings(enabled=true).withPreset(preset)
            dsp.configure(settings)
            val frame=DoubleArray(2); var sum=0.0; var source=0.0
            for (i in 0 until rate) {
                val x=.001*sin(2*PI*frequency*i/rate)
                frame[0]=x;frame[1]=x;dsp.process(frame)
                if (i>=rate/4) {sum+=frame[0]*frame[0];source+=x*x}
            }
            val db=10*log10(sum/source)
            val error=abs(db-settings.bands[band]);worst=max(worst,error)
            assertTrue("$rate preset=$preset band=$band actual=$db",error<=1)
        }
        println("AUDIOFX EQ worst_error_db=$worst (75 measurements)")
    }
    @Test fun limiterBoundsWorstSettingsAndKeepsStereoLinked() {
        val dsp=AudioFxDsp(48000,2)
        dsp.configure(AudioFxSettings(enabled=true,bands=List(5){12.0},bass=12.0,boost=12.0))
        val frame=DoubleArray(2);var peak=0.0
        for (i in 0..48000) {
            val x=if(i==0) 10.0 else sin(2*PI*1000*i/48000)
            frame[0]=x;frame[1]=x/2;dsp.process(frame)
            peak=max(peak,abs(frame[0]));assertEquals(frame[0]/2,frame[1],1e-10)
        }
        assertTrue(peak<=10.0.pow(-1.0/20)+1e-10)
        println("AUDIOFX limiter_peak=$peak")
    }
    @Test fun settingsRejectNonfiniteAndClampRanges() {
        val s=AudioFxSettings(pitch=Double.NaN,boost=99.0,bass=-4.0,bands=listOf(Double.POSITIVE_INFINITY),volume=2.0).safe()
        assertEquals(0.0,s.pitch,0.0); assertEquals(12.0,s.boost,0.0); assertEquals(0.0,s.bass,0.0)
        assertEquals(List(5){0.0},s.bands);assertEquals(1.0,s.volume,0.0)
    }
    @Test fun bassShelfAddsTwelveDbBelowItsCorner() {
        val dsp=AudioFxDsp(48000,1);dsp.configure(AudioFxSettings(enabled=true,bass=12.0))
        val frame=DoubleArray(1);var sum=0.0;var source=0.0
        for(i in 0 until 96000) {val x=.001*sin(2*PI*20*i/48000);frame[0]=x;dsp.process(frame);if(i>=24000){sum+=frame[0]*frame[0];source+=x*x}}
        assertEquals(12.0,10*log10(sum/source),1.0)
    }
    @Test fun sonicPitchChangesF0WithoutChangingDuration() {
        for (semitones in listOf(-6.0,-3.0,3.0,6.0)) for (speed in listOf(1f,1.5f)) {
            val sonic=SonicAudioProcessor();sonic.setSpeed(speed);sonic.setPitch(2.0.pow(semitones/12).toFloat())
            sonic.configure(AudioFormat(48000,1,C.ENCODING_PCM_16BIT));sonic.flush(StreamMetadata.DEFAULT)
            val input=ByteBuffer.allocateDirect(48000*4*2).order(ByteOrder.nativeOrder())
            for(i in 0 until 48000*4) input.putShort((6000*sin(2*PI*220*i/48000)).toInt().toShort())
            input.flip();sonic.queueInput(input);sonic.queueEndOfStream()
            val samples=ArrayList<Short>()
            while(!sonic.isEnded) {val out=sonic.output.order(ByteOrder.nativeOrder());while(out.hasRemaining())samples+=out.short}
            var crossings=0;val from=4800;val to=samples.size-4800
            for(i in from+1 until to) if(samples[i-1]<=0 && samples[i]>0) crossings++
            val hz=crossings*48000.0/(to-from);val expected=220*2.0.pow(semitones/12)
            assertTrue("pitch=$semitones speed=$speed hz=$hz",abs(hz/expected-1)<.03)
            assertTrue("duration=${samples.size/48000.0}",abs(samples.size/(48000*4.0/speed)-1)<.005)
            println("AUDIOFX pitch=$semitones speed=$speed f0=$hz seconds=${samples.size/48000.0}")
        }
    }
    @Test fun sustainedStereoProcessingRemainsFinite() {
        val dsp=AudioFxDsp(48000,2);dsp.configure(AudioFxSettings(enabled=true,boost=12.0).withPreset(1))
        val frame=doubleArrayOf(.1,.1)
        for(i in 0 until 48000*10) {frame[0]=.1;frame[1]=.1;dsp.process(frame)}
        assertTrue(frame.all { it.isFinite() && abs(it) <= .891251 })
    }
}

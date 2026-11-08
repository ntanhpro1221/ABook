package vn.abook.player

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import androidx.media3.common.C
import androidx.media3.common.audio.AudioProcessor.AudioFormat
import androidx.media3.common.audio.AudioProcessor.StreamMetadata
import java.nio.ByteBuffer
import java.nio.ByteOrder

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = android.app.Application::class)
class AudioFxProfileTest {
    @Test fun monoSourceCanBeBalancedToEitherEar() {
        for(balance in listOf(-1.0,0.0,1.0)) {
            AudioFx.update(AudioFxSettings(balance=balance))
            val processor=AudioFxProcessor()
            val format=processor.configure(AudioFormat(48000,1,C.ENCODING_PCM_16BIT))
            assertEquals(2,format.channelCount);processor.flush(StreamMetadata.DEFAULT)
            val input=ByteBuffer.allocateDirect(2).order(ByteOrder.nativeOrder()).putShort(6000.toShort())
            input.flip();processor.queueInput(input)
            val output=processor.output.order(ByteOrder.nativeOrder());assertEquals(4,output.remaining())
            val left=output.short.toInt();val right=output.short.toInt()
            assertEquals(if(balance==1.0)0 else 5999,left);assertEquals(if(balance== -1.0)0 else 5999,right)
        }
        AudioFx.update(AudioFxSettings())
    }
    @Test fun processorChainReturnsOriginalClockAfterTrimming() {
        AudioFx.update(AudioFxSettings(skipSilence=true))
        val chain=AudioFxChain()
        val processor=chain.audioProcessors[0]
        processor.configure(AudioFormat(1000,2,C.ENCODING_PCM_16BIT));processor.flush(StreamMetadata.DEFAULT)
        val input=ByteBuffer.allocateDirect(6800*4).order(ByteOrder.nativeOrder())
        for(i in 0 until 6800) { val voiced=i<100 || i in 1600..1699 || i>=6700;input.putShort(if(voiced)3000.toShort() else 0);input.putShort(if(voiced)6000.toShort() else 0) }
        input.flip();processor.queueInput(input)
        var frames=processor.output.remaining()/4
        processor.queueEndOfStream();frames+=processor.output.remaining()/4
        assertEquals(3300,frames)
        assertEquals(6_700_000,chain.getMediaDuration(3_200_000))
        processor.flush(StreamMetadata.DEFAULT)
        assertEquals(200_000,chain.getMediaDuration(200_000)) // seek starts a fresh map
        AudioFx.update(AudioFxSettings())
    }
    @Test fun sharedBookAndReopenDoNotLeak() {
        val context=ApplicationProvider.getApplicationContext<Context>()
        context.getSharedPreferences("audio_fx",Context.MODE_PRIVATE).edit().clear().commit()
        AudioFx.init(context);AudioFx.selectBook("")
        AudioFx.update(AudioFxSettings(boost=3.0,speed=1.5,volume=.7))
        AudioFx.selectBook("A");assertFalse(AudioFx.bookOnly.value)
        AudioFx.setBookOnly(true);AudioFx.update(AudioFx.current.copy(boost=9.0,speed=2.0,volume=.4,mono=true))
        AudioFx.selectBook("B");assertEquals(3.0,AudioFx.current.boost,0.0);assertEquals(1.5,AudioFx.current.speed,0.0)
        AudioFx.selectBook("A");assertTrue(AudioFx.bookOnly.value);assertEquals(.4,AudioFx.current.volume,0.0);assertTrue(AudioFx.current.mono)
        assertTrue(context.getSharedPreferences("audio_fx",Context.MODE_PRIVATE).getString("book:A",null)!!.contains("\"speed\":2"))
        AudioFx.setBookOnly(false);assertEquals(.7,AudioFx.current.volume,0.0);assertEquals(1.5,AudioFx.current.speed,0.0)
        AudioFx.selectBook("A");assertFalse(AudioFx.bookOnly.value)
        AudioFx.selectBook("");AudioFx.update(AudioFxSettings())
    }
}

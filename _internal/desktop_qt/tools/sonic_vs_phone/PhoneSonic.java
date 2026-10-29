import androidx.media3.common.C;
import androidx.media3.common.audio.AudioProcessor;
import androidx.media3.common.audio.SonicAudioProcessor;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Paths;

// Đúng đường tiếng của điện thoại: ExoPlayer DefaultAudioSink (không float) -> SonicAudioProcessor 16-bit, media3 1.11.1.
// java PhoneSonic <vào.s16le> <tốc_độ> <ra.s16le> <tần_số> <kênh>
public class PhoneSonic {
    public static void main(String[] a) throws Exception {
        byte[] in = Files.readAllBytes(Paths.get(a[0]));
        float speed = Float.parseFloat(a[1]);
        int rate = Integer.parseInt(a[3]);
        int channels = Integer.parseInt(a[4]);
        SonicAudioProcessor p = new SonicAudioProcessor();
        p.setSpeed(speed);
        p.setPitch(1f);
        p.configure(new AudioProcessor.AudioFormat(rate, channels, C.ENCODING_PCM_16BIT));
        p.flush(AudioProcessor.StreamMetadata.DEFAULT);
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        int chunk = 4096 * channels;   // cỡ buffer giải mã của MediaCodec: vài nghìn khung
        for (int pos = 0; pos < in.length; pos += chunk) {
            int n = Math.min(chunk, in.length - pos);
            ByteBuffer b = ByteBuffer.allocateDirect(n).order(ByteOrder.nativeOrder());
            b.put(in, pos, n).flip();
            while (b.hasRemaining()) { p.queueInput(b); drain(p, out); }
        }
        p.queueEndOfStream();
        while (!p.isEnded()) drain(p, out);
        Files.write(Paths.get(a[2]), out.toByteArray());
    }

    static void drain(SonicAudioProcessor p, ByteArrayOutputStream out) {
        ByteBuffer o = p.getOutput();
        byte[] t = new byte[o.remaining()];
        o.get(t);
        out.write(t, 0, t.length);
    }
}

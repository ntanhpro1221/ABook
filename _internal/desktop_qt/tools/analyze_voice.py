"""Bounded-memory numerical analysis of offline PCM evidence; opens no sound device."""
import json
import math
from pathlib import Path
import numpy as np
import soundfile as sf

OUT = Path(__file__).resolve().parents[1] / "build/voicemix-evidence"


def stats(path):
    energy, count, peak, nonfinite = 0.0, 0, 0.0, 0
    with sf.SoundFile(path) as source:
        rate, frames, channels = source.samplerate, source.frames, source.channels
        for block in source.blocks(blocksize=48000 * 4, dtype="float32", always_2d=True):
            nonfinite += int(np.count_nonzero(~np.isfinite(block)))
            energy += float(np.sum(block.astype(np.float64) ** 2))
            count += block.size
            peak = max(peak, float(np.max(np.abs(block))))
    return dict(frames=frames, rate=rate, channels=channels, duration_s=frames / rate, rms_dbfs=10 * math.log10(energy / count), peak=peak, nonfinite=nonfinite)


def boundaries(path):
    # The exporter changes block length using exactly this deterministic schedule.
    with sf.SoundFile(path) as stream:
        before, wanted, at = None, 997, 0
        boundary_steps = []
        hist = np.zeros(2001, dtype=np.int64)
        longest_zero = zero = 0
        for block in stream.blocks(blocksize=48000 * 4, dtype="float32", always_2d=True):
            mono = block[:, 0]
            changes = np.abs(np.diff(mono, prepend=mono[0] if before is None else before))
            hist += np.histogram(changes, bins=np.linspace(0, 2.001, 2002))[0]
            before = mono[-1]
        stream.seek(0)
        while at < stream.frames:
            block = stream.read(min(wanted, stream.frames - at), dtype="float32", always_2d=True)
            if at:
                boundary_steps.append(float(abs(block[0, 0] - last)))
            last = block[-1, 0]
            at += len(block)
            wanted = wanted * 7 % 4096 + 1
    cumulative = np.cumsum(hist)
    p999 = float(np.searchsorted(cumulative, cumulative[-1] * 0.999) / 1000)
    p9999 = float(np.searchsorted(cumulative, cumulative[-1] * 0.9999) / 1000)
    return dict(boundaries=len(boundary_steps), boundary_p99_step=float(np.percentile(boundary_steps, 99)),
                boundary_max_step=max(boundary_steps), all_steps_p999=p999, all_steps_p9999=p9999,
                boundary_fraction_over_all_p999=float(np.mean(np.array(boundary_steps) > p999)))


def main():
    rows = json.loads((OUT / "chapter.json").read_bytes())
    reference = stats(OUT / "chapter-source-reader.wav")
    for row in rows:
        suffix = f"{row['rate']:.1f}"
        row["voice"] = stats(OUT / f"chapter-voice-{suffix}.wav")
        row["mix"] = stats(OUT / f"chapter-mix-{suffix}.wav")
        row["voice_level_vs_source_reader_db"] = row["voice"]["rms_dbfs"] - reference["rms_dbfs"]
        row["buffer_boundaries"] = boundaries(OUT / f"chapter-mix-{suffix}.wav")
        row["length_pass"] = abs(row["length_error_pct"]) <= 0.5
        row["level_pass"] = abs(row["voice_level_vs_source_reader_db"]) <= 0.5
        assert row["length_pass"] and row["level_pass"] and row["voice"]["nonfinite"] == row["mix"]["nonfinite"] == 0
    result = dict(kind="offline PCM, NOT physical loopback or MFMediaEngine capture", source_reader_reference=reference, rows=rows)
    (OUT / "signal.json").write_text(json.dumps(result, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__": main()

# Streaming voice fixtures

Synthetic pink noise, 16 seconds, 48 kHz mono, seed 123. No book or speaker recording is included.

Generated with the existing imageio-ffmpeg executable and libmp3lame:

```
-f lavfi -i anoisesrc=color=pink:sample_rate=48000:seed=123:duration=16 -ac 1 -c:a libmp3lame -b:a 128k cbr.mp3
-f lavfi -i anoisesrc=color=pink:sample_rate=48000:seed=123:duration=16 -ac 1 -c:a libmp3lame -q:a 2 vbr.mp3
```

Each file exceeds the first range page. VoiceTests compares full decode and HTTP seeks at 12.345 s
against Mp3Source, including gapless trimming and MP3 reservoir preroll. The fake server exercises
both 206 (short, honored ranges) and 200 (ignored Range).

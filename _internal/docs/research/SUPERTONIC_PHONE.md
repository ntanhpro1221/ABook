# Supertonic voice on the phone: speed first (07-10)

Question: can the phone run the desktop's "Giọng Supertonic" (Supertonic 3, `abook/readaloud/supertonic.py`) fast enough to read live?
Gate set by the lead: port only if the emulator's warm RTF is at most 0.8.

## What was measured

- Model: the files the desktop module pins (`abook/webui/supertonic_module.py`): Hugging Face `Supertone/supertonic-3` at commit
  `724fb5abbf5502583fb520898d45929e62f02c0b`, `onnx/` (duration_predictor, text_encoder, vector_estimator, vocoder; 398 MB fp32) and
  `voice_styles/` (10 voices). The copy used had the same SHA-256 as the pins. Voice F1, 8 denoising steps, speed `speed_for(text)`
  (1.54 for these paragraphs), seed `seed_of("supertonic", voice, text)`: exactly what the app does for one chunk.
- Text: three fixed paragraphs of 148-150 characters (`tests/fixtures/readaloud/supertonic/supertonic_bench.json`, written for the
  bench, no numbers so no sea-g2p needed). Each is one chunk and gives 9.4 / 10.2 / 10.7 s of audio.
- RTF = compute seconds / audio seconds for one `infer` (text cleaning, the four graphs, trim and fade). Cold = pass 0 of a fresh
  engine (the very first run is paragraph 1); warm = median of the next 2 (phone) or 3 (PC) passes. Load = creating the four
  sessions + reading the voice style.
- Phone side: the Kotlin port (`mobile/android/.../readaloud/SupertonicTts.kt`, `SupertonicEngine`) on onnxruntime-android 1.30.0
  (the `OrtRuntime.kt` libraries, CPU, no spinning, one inter-op thread - the same session options as VieNeu), run by
  `androidTest/.../SupertonicBench.kt` through `scripts/supertonic_phone_bench.sh` (installed as `com.ngdtuanh.abook.stbench`).
- PC side: `scripts/supertonic_bench.py` (the desktop's own `SupertonicEngine`, onnxruntime 1.28.0, numpy 2.4.6).
- Both at 01:00-01:15 on 07-10 on the home laptop (AMD Ryzen 9 8945HX, 16 cores / 32 threads) while other jobs kept it 40-60%
  busy. The absolute numbers are therefore higher than an idle machine gives (the module's own note says RTF 0.19 at 8 threads);
  the PC and emulator columns were taken under the same load and are comparable with each other.

## Numbers

Emulator: AVD `ebook_pixel`, Android 16 x86_64 (sdk_gphone64_x86_64), 4 vCPUs, started with `-no-audio`.

| where | threads | load | cold RTF (p1 / p2 / p3) | warm RTF (p1 / p2 / p3) | warm median |
|---|---|---|---|---|---|
| emulator (Kotlin, ORT 1.30) | 1 | 1.19 s | 0.401 / 0.383 / 0.379 | 0.403 / 0.387 / 0.390 | **0.390** |
| emulator | 2 | 1.04 s | 0.334 / 0.325 / 0.310 | 0.332 / 0.328 / 0.311 | **0.328** |
| emulator | 4 | 0.93 s | 0.321 / 0.318 / 0.303 | 0.315 / 0.323 / 0.306 | **0.315** |
| PC (Python, ORT 1.28) | 1 | 0.69 s | 0.377 / 0.413 / 0.407 | 0.385 / 0.394 / 0.381 | 0.385 |
| PC | 2 | 0.84 s | 0.424 / 0.395 / 0.371 | 0.416 / 0.404 / 0.381 | 0.404 |
| PC | 4 | 0.75 s | 0.332 / 0.301 / 0.323 | 0.348 / 0.327 / 0.334 | 0.334 |
| PC | 8 | 0.82 s | 0.333 / 0.333 / 0.327 | 0.301 / 0.328 / 0.317 | 0.317 |

- Where the time goes (emulator, 4 threads, one paragraph): duration + text encoder 36-45 ms, vector estimator (8 steps) 2.6-2.9 s,
  vocoder 0.22-0.24 s. The estimator is ~90% of the work, so speed scales with how fast the phone runs that one fp32 graph.
- Cold costs almost nothing extra here (the first run is within 0.01 of warm); load is about 1 s.
- More threads help little (1 -> 4 threads: 0.39 -> 0.32) on both sides: the graphs are small per step (about 140 latent frames
  for 10 s of audio).
- Peak resident memory of the instrumented process: ~0.71 GB (includes the test runner); the desktop module notes ~0.53 GiB.
- Output: the emulator's audio has the desktop's exact length for all three paragraphs, and against the PC's audio its largest
  sample difference is 7.8e-5 (mean 7e-7, SNR 89-91 dB): the same audio up to float rounding between two ONNX Runtime builds.

Decision by the gate: emulator warm RTF 0.315 at 4 threads is far under 0.8, so the port goes ahead.

## The emulator is not a phone

The emulator runs x86_64 code on the laptop's own cores (hardware virtualisation), so it is as fast as the laptop: the table shows
emulator and PC within 5% of each other. It proves the Kotlin port runs and gives the desktop's audio; it says nothing about an ARM
phone's speed.

**Estimate (not measured) for a mid-range ARM phone.** Grounded on the one real phone the project has measured, the owner's OPPO
A93 (MediaTek Helio P95: 2x Cortex-A75 2.2 GHz + 6x A55, ORT 1.30, docs/LISTEN_ANYTHING.md "Phone, measured 03-10"):

- VieNeu Nano, the closest relative (flow-matching vector estimator dominating the time, fp32, ORT CPU), ran at RTF 0.18 on this
  laptop and 1.8-1.9 on the A93 at 4-8 threads: the phone was ~10x slower.
- Supertonic is about as heavy as Nano on the desktop (RTF 0.19 vs 0.18 in the modules' own measurements: 99M parameters but 8
  single estimator passes per chunk, against Nano's 48M parameters and 16 steps x 2 passes with guidance). Same kernels, same
  precision, so the same ~10x ratio is the best guess: **Supertonic RTF about 1.9 on a Helio P95-class phone (2020 mid-range) - it
  would not keep up live there.**
- Newer mid-range chips are faster per big core (Cortex-A78/A715 at 2.4-2.8 GHz: roughly 1.7-2x the A75 in public single-core
  scores, 1.3-2.5x in multi-core). Scaling the A93 estimate: **about 1.0-1.3 for a 2023 mid-range phone (Dimensity 7050,
  Snapdragon 7s Gen 2) and about 0.6-0.8 for an upper mid-range one (Snapdragon 7+ Gen 2, Dimensity 8000 series).**
- The ORT x86 vs ARM gap itself is not the main factor: both use MLAS fp32 GEMM kernels (AVX2/AVX-512 vs NEON); the gap is per-core
  throughput (a Zen 4 core at ~5 GHz with two 256-bit FMA pipes vs an A75 at 2.2 GHz with two 128-bit pipes: ~4.5x peak per core)
  plus memory bandwidth, which matches the ~10x measured for Nano with fewer fast cores on the phone.

So: the port is right (it runs and matches the desktop), but whether a given phone reads live must come from the phone's own
self-benchmark after download, exactly like VieNeu - a slow phone gets the "Làm trước" / online-voice suggestion, never a silent
switch. If the lead wants a real number before release: run the bench below on the A93.

## Running it on a real phone (not done here)

The bench builds and installs under its own package (`com.ngdtuanh.abook.stbench` + `.test`), so the installed app
`com.ngdtuanh.abook`, its books and settings are never replaced or wiped; `clean` removes only the bench packages and the pushed files.

```bash
# once: node_modules in _internal/mobile and _internal/ui (npm ci), the web UI built (npm run build:android in _internal/ui, then npx cap sync android in _internal/mobile)
export JAVA_HOME="C:/Program Files/Android/Android Studio/jbr" ANDROID_HOME="$LOCALAPPDATA/Android/Sdk" ADB="$LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe"
export MODEL=<folder with onnx/ + voice_styles/ of Supertone/supertonic-3 at the pinned commit>
cd _internal
bash scripts/supertonic_phone_bench.sh <serial> build      # gradle -PbenchAppId=com.ngdtuanh.abook.stbench
bash scripts/supertonic_phone_bench.sh <serial> install    # refuses an APK whose package is not the bench id
bash scripts/supertonic_phone_bench.sh <serial> push       # /data/local/tmp/stonic: model, ORT for the phone's ABI, the paragraphs
bash scripts/supertonic_phone_bench.sh <serial> speed threads 1,2,4,8 passes 2
bash scripts/supertonic_phone_bench.sh <serial> results    # one JSON line per thread count
bash scripts/supertonic_phone_bench.sh <serial> clean
```

On ColorOS (the A93), whose app freezer stalls an instrumented app that is not in front, use `app threads=1,2,4,8` then
`wait-app` / `app-results` instead of `install` + `speed`: it runs the same code through `app_process` as the shell user and
installs nothing at all.

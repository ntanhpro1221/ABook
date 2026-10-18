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

## 18-10: int8 + fewer steps

The A93 (OPPO A93, Helio P95) read Supertonic fp32 at RTF ~2 - more than twice slower than listening - and VieNeu Nano likewise. The
vector estimator is ~90% of the work for both, so the app now ships its own int8 copies of that one graph (static QDQ quantisation of
the heavy layers only; every other graph and every voice file unchanged) and reads in fewer steps. Files: Hugging Face
`NGDtuanh/abook-music-student` at commit `f42d118d`, `supertonic3-int8/{top30,fast}/vector_estimator.onnx` and
`vieneu-nano-int8/vector_estimator.onnx` (SHA-256 + size pinned in the modules; licences in THIRD_PARTY.md).

### A93, warm RTF (median, CPU)

| voice | configuration | threads | RTF |
|---|---|---|---|
| Supertonic | fp32, 8 steps (before) | 2 / 4 | 1.99 / 2.13 |
| Supertonic | top30 int8, 8 steps (quality tier) | 4 | 1.21 |
| Supertonic | fast int8, 8 steps | 4 | 1.01 |
| Supertonic | fast int8, 5 steps (fast tier) | 4 | ~0.70 (estimated from the 8-step run) |
| Nano | fp32, 16 steps (before; the phone was throttled) | 4 | 2.16 |
| Nano | int8 | 4 | 1.67 |
| Nano | int8, 8 steps (fast tier) | 4 | ~0.95 (estimated) |

So no tier keeps up live on the A93 yet; the fast tier halves the wait. What a given phone does is decided by its own self-benchmark
(below), never by these numbers.

### Desktop listening test, Supertonic (144 clips per configuration)

24 paragraphs x voices F1 / M4 / F2 x 2 seeds; ASR faster-whisper large-v3-turbo (CER per clip capped at 100%), UTMOS; paired bootstrap
over paragraphs (2000 samples, CI90 = 5th-95th percentile). Rules fixed before generating: replacing fp32 at 8 steps (H1) dCER <= +0.5
(upper CI90 <= +1.0), dUTMOS >= -0.05 (lower CI90 >= -0.10), at most 1/24 paragraphs worse than fp32 by > 5 pp on both seeds; a fast
tier (H2) dCER <= +2.0 (<= +3.0), dUTMOS >= -0.10 (>= -0.20), at most 2/24. RTF = desktop, 4 threads, shared machine (relative only).

| configuration | RTF | CER % | dCER (CI90) | UTMOS | dUTMOS (CI90) | worse paragraphs | rule |
|---|---|---|---|---|---|---|---|
| fp32, 8 steps (reference) | 0.178 | 1.36 | - | 3.149 | - | - | - |
| **top30 int8, 8 steps (quality tier)** | 0.146 | 1.51 | +0.15 (+0.02..+0.29) | 3.123 | -0.026 (-0.045..-0.005) | 0/24 | H1 PASS |
| top30 int8, 6 steps | 0.116 | 1.63 | +0.26 (+0.10..+0.43) | 3.153 | +0.004 (-0.024..+0.034) | 0/24 | H2 PASS |
| top20 int8, 5 steps | 0.085 | 1.91 | +0.55 (+0.34..+0.75) | 3.083 | -0.066 (-0.096..-0.034) | 0/24 | H2 PASS |
| **fast int8, 5 steps (fast tier)** | 0.074 | 2.06 | +0.70 (+0.46..+0.93) | 3.062 | -0.087 (-0.119..-0.055) | 0/24 | H2 PASS |
| fp32, 4 steps (reference) | 0.098 | 2.70 | +1.34 (+1.02..+1.68) | 3.102 | -0.047 (-0.087..-0.006) | 0/24 | H2 PASS |

dCER by voice (pp): quality tier F1 -0.03, M4 +0.19, F2 +0.28; fast tier F1 +0.62, M4 +0.48, F2 +0.99. No clip above 50% CER.

### Desktop listening test, VieNeu Nano

Voices Adam, Ái Hân, Mỹ Duyên through the app's own text path. Speed on the desktop (Ryzen 9 8945HX, median of 3 interleaved runs):
the vector estimator is 91% of Nano's time.

| configuration | RTF 1 / 2 / 4 threads | estimator size | DEV CER % (d) | DEV UTMOS (d) | DEV rule |
|---|---|---|---|---|---|
| fp32, 16 steps (before) | 0.589 / 0.375 / 0.271 | 155 MB | 2.67 | 2.431 | reference |
| fp32, 12 steps | 0.446 / 0.295 / 0.211 | 155 MB | 2.82 (+0.15) | 2.492 (+0.061) | pass |
| fp32, 8 steps | 0.329 / 0.214 / 0.148 | 155 MB | 2.89 (+0.21) | 2.415 (-0.016) | pass |
| fp32, 6 steps | 0.256 / 0.170 / 0.118 | 155 MB | 3.69 (+1.02) | 2.359 (-0.072) | fail |
| int8 (MatMul only), 16 steps | 0.318 / 0.228 / 0.184 | 46 MB | 2.70 (+0.02) | 2.390 (-0.041) | pass |
| int8 (MatMul only), 8 steps | 0.189 / 0.135 / 0.102 | 46 MB | 3.02 (+0.35) | 2.352 (-0.079) | fail (UTMOS, by 0.03; seed noise 0.07) |

TEST (24 paragraphs x 3 voices x 2 seeds = 144 clips, used once; reference fp32 16 steps CER 1.65%, UTMOS 2.460):

| configuration | RTF (4 threads) | dCER (CI90) | dUTMOS (CI90) | worse paragraphs | result |
|---|---|---|---|---|---|
| fp32, 8 steps (quality tier) | 0.135 (16 steps: 0.248) | +0.14 (+0.05..+0.22) | -0.043 (-0.071..-0.015) | 0/24 | PASS |
| int8, 16 steps | 0.155 | +0.11 (+0.02..+0.20) | -0.046 (-0.078..-0.011) | 0/24 | PASS |

Hence the tiers (same on the desktop and the phone, one constant pair each to change):

| voice | "Chất lượng cao nhất" | "Nhanh hơn" (live listening only) |
|---|---|---|
| Supertonic | top30 int8, 8 steps (replaces fp32; upstream's fp32 file is no longer downloaded) | fast int8, 5 steps (`supertonic.FAST`, `SupertonicText.FAST_ESTIMATOR` / `FAST_STEPS`) |
| VieNeu Nano | upstream fp32, 8 steps (`NANO_STEPS` 16 -> 8) | none since 19-10 (int8 at 10 steps shipped in 0.4.98, then dropped: see below) |

Nano's fast tier was tested once on the 144 test clips under the fast-tier rule (mean dCER <= +2.0 pp, CI90 upper <= +3.0; dUTMOS >= -0.10,
CI lower >= -0.20; <= 2/24 paragraphs worse by 5 pp on both seeds): int8 at 8 steps FAILED (dCER +0.16 pp, dUTMOS -0.112), int8 at 10 steps
PASSED at the edge (dCER +0.14 pp [+0.03, +0.26], dUTMOS -0.092 [-0.122, -0.061]); about 2.7x the fp32 16-step speed on the desktop. Studio and every export always read the quality tier.

"Tốc độ giọng trên máy" (Settings, desktop `webui/voice_speed.py`, phone `readaloud/VoiceSpeed.kt`): Tự động (default) / Chất lượng cao
nhất / Nhanh hơn, one choice per device. Tự động reads the quality tier when that tier's self-benchmark (run after each download) is under
SLOW_RTF 0.8, else the fast tier; it never moves to another voice, and an explicit choice is never overridden. The fast file is
downloaded only when the fast tier is wanted (the module card offers it with its size). A fast clip carries the tier tag "fast<steps>"
after the reading tags of its cache key, so an export never reuses one.

## 19-10: the 0.4.98 tiers timed on the A93

Paired in one session, 4 threads, warm, `app_process` in the foreground, screen off (night) - the phone was busier and hotter than on 18-10
(load average ~23, little cores down to 774 MHz), so compare the tiers with each other, not with the 18-10 table.

| voice | quality tier | fast tier | fast / quality |
|---|---|---|---|
| Supertonic (median of 3 paragraphs) | top30 int8, 8 steps: 1.48 | fast int8, 5 steps: 0.87 | 0.59 |
| VieNeu Nano (longest of 5 sentences, 7 s audio) | fp32, 8 steps: 1.22 | int8, 10 steps: 1.15 | 0.94 |

Supertonic's fast tier scaled to the 18-10 quality number (1.21) gives about 0.71: live listening keeps up on this phone.
Nano's int8 estimator costs about 0.74x fp32 per step (6.25 s / 10 steps vs 6.77 s / 8 steps on the long sentence), so 10 int8 steps are
about 7.4 fp32 steps, and the decoder (fp32, ~1.5 s = 19 %) does not change: the fast tier was 6 % faster, sounded worse and downloaded
48 MB more. Nano therefore has one tier, like Turbo. A Nano fast tier would need int8 at 8 steps or fewer, which failed the fast-tier rule.
Reproduce: `S/fastvoice/phone_fast.sh` (bench args `estimator=`, `steps=` in `SupertonicBench` / `VieneuBench`).

## 19-10: an int8 vocoder for Supertonic, a lighter Nano (R6)

The vocoder was the last fp32 graph and about 20 % of the phone time. Static QDQ int8 (weights int8 per channel, activations uint8,
QLinearConv - the dynamic ConvInteger path is 8x slower, see 18-10), calibrated on the development clips only. Sensitivity was ranked by
the mel distance of the output when one convolution alone is quantized (waveform SNR ranked the output convolution too low); the 10 worst
convolutions stay fp32. 101 MB -> 45 MB.

Listening test (the R2 set: 24 paragraphs, voices F1/F2/M4, 2 seeds, paired bootstrap by paragraph, CI90), against the shipped tier with
the fp32 vocoder:

| tier | dCER (pp) | dUTMOS | paragraphs worse > 5 pp | rule |
|---|---|---|---|---|
| quality (top30, 8 steps) | -0.01 [-0.05; +0.02] | -0.018 [-0.040; +0.004] | 0/24 | replace: PASS |
| fast (fast, 5 steps) | -0.01 [-0.05; +0.03] | -0.021 [-0.059; +0.019] | 0/24 | replace: PASS |

A93, paired in one session (4 threads, warm median of 3 paragraphs, screen off at night - the phone was slower than in the morning
tables, so read the ratios):

| tier | fp32 vocoder | int8 vocoder | ratio | vocoder ms (fp32 -> int8) | peak RSS |
|---|---|---|---|---|---|
| quality | 2.04 | 1.87 | 0.92 | ~3200 -> ~1500 | 569 -> 528 MB |
| fast | 0.96 | 0.83 | 0.87 | ~2700 -> ~1570 | 530 -> 493 MB |

The vocoder takes half the time with no measurable loss, so it replaces the fp32 one in both tiers and in Studio/exports.
Reproduce: `S/fastvoice/phone_voc.sh` (pushes either vocoder as `onnx/vocoder.onnx`; no bench change needed).

### Nano: guidance in a limited interval + an int8 codec decoder

Nano runs the estimator twice per step (classifier-free guidance, weight 3). Guiding only part of the trajectory is training-free
(Kynkäänniemi et al. 2024, "Applying guidance in a limited interval improves sample and distribution quality in diffusion models"). On the
development set, at 8 steps (dCER vs the shipped schedule, pp): guidance on steps 1-6 +0.28, 2-7 +0.36, 0-5 +0.73, 0-4 +0.82, 0-3 +2.83
(fails); reusing the previous step's (cond - uncond) on odd steps +1.07. Dropping the guidance of the last steps hurts, of the first step
much less. The codec decoder was quantized like the Supertonic vocoder (static QDQ, QLinearConv/QLinearMatMul, 6 of 34 weighted nodes kept
fp32 by output SNR; 99 MB -> 41 MB).

Test set (24 paragraphs x Adam / Ái Hân / Mỹ Duyên x 2 seeds), guidance on steps 1-6 + int8 decoder against fp32 guided on every step:
dCER +0.23 [-0.00; +0.48], dUTMOS +0.038, 0/24 paragraphs worse > 5 pp: passes the replace rule. (Reusing the guidance on odd steps
passes only the fast-tier rule, UTMOS -0.064, and Nano has no fast tier.) An independent audio check (clicks by LPC residual, energy above
8 kHz, noise in silences, loudness) found nothing new against the reference.

A93, paired, 4 threads, warm, 5 sentences (screen off at night), order base / new / new / base:

| | estimator calls per chunk | long sentence (7 s) RTF | estimator s | decoder s | all 5 sentences RTF | peak RSS |
|---|---|---|---|---|---|---|
| fp32 decoder, guided every step | 16 | 1.225 / 1.225 | 6.8 | 1.5 | 1.30 / 1.32 | 491-498 MB |
| int8 decoder, guided on steps 1-6 | 14 | 1.023 / 1.023 | 6.0 | 0.9 | 1.10 / 1.10 | 457 MB |

16 % faster at the same quality, so it replaces the shipped schedule and decoder (desktop `vieneu_engine.NANO_CFG_ENDS`, phone
`VieneuNano.CFG_ENDS`). Nano still reads slower than real time on this phone; the remaining time is the estimator itself.
Reproduce: `S/fastvoice/phone_nano_r6.sh` (bench arg `cfg=all` for the old schedule).

# TTS research (Model lane)

Open Vietnamese TTS engines measured against VieNeu v3 Turbo, the engine the app ships. Everything is machine-scored; the
owner judges voices by ear on a review page. Nothing in the Studio pipeline changed for these runs. Scripts, raw results
and audio stay outside the public repo (Model-lane scratchpad + `D:/Novels/LLM_Train/tts_bench`).

## 2026-10-03 - preset-voice engines vs VieNeu v3 Turbo

### Question and scope

VieNeu v4 is closed (API only), so v3 Turbo is the last open VieNeu. Is there an open engine that fits the home card
(8 GB, RTX 5060 Laptop, sm_120) or the CPU and reads Vietnamese LN-style text better?

Owner decisions on 03-10 shaped the scope:

- 21:1x: voice cloning is not a criterion.
- 21:5x: only engines that ship preset voices count. Each vendor's voice count is taken at face value, and the owner
  judges the voices himself on a review page. Machine "distinctness" analysis was stopped.

In scope:

| engine | preset voices | runs on | licence |
|---|---|---|---|
| VieNeu v3 Turbo | 25 (14 male / 11 female, SDK labels) | GPU (Studio) | weights Apache-2.0 |
| VieNeu v3 Nano | 11 (6 / 5) | CPU (phone, desktop) | Apache-2.0 |
| Supertonic 3 | 10 (F1-F5, M1-M5) | CPU, ONNX | OpenRAIL-M (no impersonation, disclose synthetic speech) |
| ZeroTTS | 8 (4 / 4, `voices/index.json`) | CPU, ONNX | MIT |
| Viterbox | 3 sample voices in the repo's `wavs/`, used by `get_random_voice()` when no prompt is given; gender not labelled, source of the clips unknown | GPU | CC-BY-NC-4.0 |

Supertone Inc. dissolved in 2026 (services shut 08-31, GitHub archived 09-09), so the Supertonic weights are final.
Tested files: HF `Supertone/supertonic-3` commit `724fb5abbf5502583fb520898d45929e62f02c0b` (pip `supertonic` 1.3.1),
`onnx/vector_estimator.onnx` sha256 `883ac868…7c61c`, `onnx/vocoder.onnx` `085de76d…c4ba`, `onnx/text_encoder.onnx`
`c7befd5e…02ff`, `onnx/duration_predictor.onnx` `c3eb9141…25db` (full list kept with the bench). Pin that commit if
it is adopted.

Measured and dropped (no preset voices, or worse):

- **OmniVoice:** clone mode was the best reader (CER 2.5 %), and instruct-designed voices held their timbre across 32
  lines. But the weights are NC and it has no presets.
- **VoxCPM2:** 16-28 % of lines drift away from the designed voice; 6.1 GiB VRAM; 122 s per 1000 chars.
- **Gwen-TTS 0.6B:** clone only; CER 18.5 %, numbers unusable; 175 s per 1000 chars.
- **F5-TTS-ViVoice:** clone only; the fork crashes when given a seed (`infer(seed=…)` never sets `self.seed`); not re-run.
- **Viterbox (excluded by the owner, 03-10 22:2x):** measured below with its 3 shipped voices, then dropped. The owner
  marked none of them on the review page; the licence is CC-BY-NC; the voice files' provenance is unknown; it is ~11×
  slower than Turbo and needs 3.85 GiB VRAM. No further runs.
- **Chatterbox Multilingual:** has no Vietnamese; Viterbox is its Vietnamese fine-tune.
- **dangvansam/viet-tts:** Linux-only, torch 2.0.1, abandoned.

### Method

- **Sentences.** 32 lines written for this test, no story text, in four groups of 8:
  - LN-style dialogue;
  - Japanese/Korean transliterated names (Yamada-senpai, Nukumizu, Kim Jaehun, Gu Yangcheon…);
  - English words mixed in (ChatGPT, OpenAI, email, level up, Google Drive…);
  - numbers and dates (2025, 9,3 triệu, 7 giờ 30, 01/11/2026, 3 %, 3-2…).

  Each line lists its focus words. A second set of 8 lines writes the same names the way the app respells them for
  reading ("Ca-du-hi-cô", "Xư-ki-nô-ki", "Hên-cơ", "Oát-li").
- **Voices.** Two presets per engine, one female and one male: VieNeu Đức Trí + Trúc Ly, Supertonic F1 + M1, ZeroTTS
  baotrang + giahuy, Viterbox vb1 + vb2. One sample per line per voice.
- **Speaking rate.** Supertonic at its default speed (1.05) speaks at 2.57 syllables/s against VieNeu's 3.78, and the
  ASR then mishears it (CER 8.0 %). ABook sets speed per voice, so it is compared at speed 1.54 (3.84 syllables/s).
- **Clips are scored the way the app hears them.** Edge silence is capped to 0.35 s with
  `abook.audio_io._edge_silence_seconds` + `SEGMENT_EDGE_SILENCE_CAP_SECONDS`, exactly as `_cap_segment_edge_silence`
  does when a chapter is assembled.
- **Scores, all computed in one GPU pass:**
  - **CER.** The app's ASR (faster-whisper large-v3-turbo, vi, beam 5), then the app's `normalize_transcript` on both
    sides.
  - **Focus-word hit rate.** The normalised focus word appears in the normalised transcript; a diacritic-folded match
    also counts. This is strict: "Yamada Senpi" misses.
  - **UTMOSv2.** Exactly as the app runs it: fusion_stage3, fold 0, seed 42, pinned checkpoint, sarulab, 3 repetitions.
  - **Speed.** The primary figure is synthesis seconds per 1000 input characters. RTF is flattered by slow or padded
    audio.
  - **Speaking rate.** Syllables (after `normalize_transcript`) per second of non-silent audio, using the app's
    silence floor.
  - **Memory.** Peak VRAM above the idle baseline, or peak RAM of the process tree.

### Results

| engine | CER % overall (dialogue / names / English / numbers) | focus words right % (names / English / numbers) | respelled names right % | UTMOSv2 | s per 1000 chars | syllables/s | memory |
|---|---|---|---|---|---|---|---|
| VieNeu v3 Turbo (GPU) | **3.6** (1.1 / 6.0 / 0.4 / 6.7) | 27 / 88 / 80 | 62 | 2.96 | **6.5** | 3.7 | ~1.1 GiB VRAM |
| VieNeu v3 Nano (CPU) | **3.6** (1.5 / 4.9 / 0.9 / 7.2) | 60 / 92 / 77 | 58 | 2.64 | 12.8 | 3.4 | 0.48 GiB RAM |
| Supertonic 3 @1.54 (CPU) | **3.4** (1.0 / 2.4 / 0.4 / 9.8) | 70 / 92 / 67 | 50 | **3.25** | 17.7 | 3.8 | 0.53 GiB RAM |
| ZeroTTS (CPU) | **2.6** (2.3 / 3.0 / 0.4 / 4.7) | 60 / 92 / 90 | 54 | 3.12 | 43.8 | 4.0 | 1.5 GiB RAM on these lines; 8-11 GB on 400-char paragraphs (Lead's bake-off) |
| Viterbox shipped voices (GPU) | **4.1** (2.5 / 4.6 / 1.8 / 7.6) | 63 / 92 / 80 | 62 | 2.97 | 74.2 | 3.8 | 3.85 GiB VRAM |

How to read the table:

- **CER.** At matched speaking rate the five engines read Vietnamese about equally well: overall CER 2.6-4.1 % on 64
  lines each, where a point is roughly noise. ZeroTTS reads numbers best. Supertonic's README lists a Vietnamese error
  rate of 4.49; here it was 3.4 at speed 1.54 and 8.0 at its default speed.
- **Names.** VieNeu Turbo reads raw Japanese/Korean names worst: "Senpi", "Niukumizu", "Yonami", "Hikiga". With the
  app's respellings it reaches 62 %, level with the best. The respelled set's match ignores spaces, because a correct
  reading is often transcribed as the original name ("Henco" for "Hên-cơ"), so it is more lenient than the main set's
  rule. Compare the respelled column across engines, not with the names column. With only 26 focus names, the
  respelled-name differences between engines are within noise.
- **Naturalness.** UTMOSv2 ranks Supertonic and ZeroTTS above both VieNeu models. The owner's ear decides voice choice.
- **Speed.** VieNeu Turbo on the GPU is fastest by far. Among the CPU engines Nano is fastest, then Supertonic. ZeroTTS
  is 3.4× slower than Nano on the CPU. Viterbox needs the GPU and is 11× slower than Turbo.
- **Sentence ends.** No engine truncates them in a way the ASR can see. The few "misses" are the ASR spelling a
  final name differently, plus one case where the ASR invented words in Supertonic's trailing noise.

Caveats:

- One sample per line per voice, and the ASR is itself a model.
- RTF for Supertonic at 1.54 was measured while the GPU bench ran, so its CPU figure may be slightly pessimistic.
- VRAM for VieNeu presets is corrected for a baseline taken while the cloning run's model was still loaded.

### Voice variety (stopped by the owner, recorded for the record)

Before the owner chose to listen himself, preset distinctness was checked three ways:

- **Speaker embeddings** (WavLM-sv, pairs at cosine ≥ 0.90 counted as hard to tell apart).
- **Acoustics** (F0, spectral tilt and centroid, speaking rate).
- **Language control** (the same lines in English and Korean).

Findings:

- **The closest pairs are genuinely close.** Supertonic F3~F5 (cos 0.99): F0 179/173 Hz, same rate. ZeroTTS
  hamy~maichi (0.99): F0 280/282 Hz, only the speaking rate differs. ZeroTTS giahuy~huuduc (0.95): F0 113/106 Hz. They
  stay close in English and Korean too, so this is not a Vietnamese-specific collapse.
- **The counts are a lower bound.** Many pairs at 0.90-0.94 differ by 2-6 semitones of F0, so a 0.90 cut under-counts
  distinct voices. Embedding counts at 0.90: Supertonic 6/10, ZeroTTS 4/8.
- **The spectral rule was unusable.** The pre-registered acoustic rule's spectral thresholds (centroid ≥ 15 %, tilt
  ≥ 2 dB/oct) fall inside within-voice variation across sentences (11-20 % and 1.4-2.4 dB/oct). Only F0 and rate
  separate voices.

The owner's review page uses 3 lines per voice (narration, dialogue, names + numbers), leveled and trimmed like the app,
for all 57 preset voices above.

### Review page result (owner, 03-10 22:2x)

- **Supertonic 3:** liked F1, F3, M4, M5.
- **ZeroTTS:** liked baotrang, giahuy, huuduc, kimoanh, quangminh.
- **Viterbox:** none liked, so the engine is excluded (see above).
- **Unmarked voices** are "tạm" (acceptable), not rejected.
- **VieNeu** was not re-rated; the 18-09 verdicts stand.

Next steps, as Lead work: Supertonic in desktop "Nghe ngay", then Studio casting across several engines (Supertonic and
ZeroTTS for side roles) on a dev branch.

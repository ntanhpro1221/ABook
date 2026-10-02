# D. How far AI / computer science has taken text-to-music emotional matching

Scope: the machine side of the problem. Psychology (GEMS, valence/arousal/tension, discrete emotions, narrative function) is covered in a separate report; here I review what models and methods exist, what they achieve in numbers, and what transfers to an app that must pick background music for scenes of Vietnamese-translated JP/KR/CN web novels, running locally on an 8 GB NVIDIA GPU or a Mac mini M4 16 GB.

Compiled 2026-10-02. Every number below was read from the cited paper or model card during this research session (PDFs downloaded and grepped where possible). Where I could not verify something it is marked **[unverified]**. Evidence grades used in section 5: **P** = proven by at least one controlled study that matches our setting reasonably well; **I** = indirect (proven in a neighbouring setting: video, image, speech, games); **S** = speculative (my engineering inference, no study found).

---

## 0. Executive summary

1. **No public dataset of (story scene, music track) pairs exists for prose fiction.** Every text-to-music emotion system to date bridges the modalities *through emotion labels* learned separately on each side (Won et al. 2021; Sonus Texere 2022; Bardo 2017) or *through an LLM that writes a music description* (Babel Bardo 2024, M2M-Gen 2024/25, WavJourney, MM-StoryAgent). The "glue" is therefore an open research problem; nobody has a validated model we can download.
2. **The best-studied glue is a small, explicit affect space.** In the only direct text-to-music retrieval study (Won et al., ISMIR 2021, best student paper), regressing *both* sides into valence-arousal and matching by distance was the best or tied-best of six strategies; a data-driven three-branch metric-learning space was "comparable, more general". Image-to-music (Emo-CLIM 2024, MMVA 2025) and speech-to-music (Doh et al. 2023) reach the same picture: shared emotion supervision works; P@5 around 0.6-0.7 on 5-7 coarse classes.
3. **Music side: arousal is solved well enough, valence moderately, categorical moods poorly, GEMS badly.** Best frozen foundation-model probes reach R² ≈ 0.75-0.79 for arousal and 0.52-0.63 for valence (EmoMusic, PMEmo, DEAM). Multi-label mood/theme tagging (MTG-Jamendo, 56 tags) tops out at PR-AUC ≈ 0.15-0.16. GEMS-9 classification on Emotify is ≈ 46-52 % accuracy with supervised probes and 17-34 % zero-shot (chance 11 %).
4. **Zero-shot CLAP-style mood tagging is weak** (GlobalMood, ISMIR 2025: mean r = 0.08 against human mood ratings; fine-tuning on 1,180 songs raised it to 0.31). A frontier cloud model (Gemini 2.5 Pro) reached r = 0.50, matching the human split-half ceiling. No *local* audio model has been shown to do this.
5. **Text side: LLMs are good at valence and at obvious categories, weak at arousal and at emotional uncertainty.** On EmoBank, small open 8B models reach r ≈ 0.49-0.56 for valence but only ≈ 0.19-0.23 for arousal; their outputs have about half the human spread (Inoshita et al. 2026). Comparative annotation (best-worst scaling / pairwise) is more reliable than direct ratings, for humans and for LLMs (Kiritchenko & Mohammad 2017; Bagdon et al. 2024; EmoPair 2026).
6. **Licensing narrows the music-model menu sharply.** The strongest MER encoders (MERT, MuQ/MuQ-MuLan, TTMR++, Jukebox, Essentia's trained heads) are non-commercial (CC-BY-NC / NC-SA / custom NC); openSMILE forbids "any sort of commercial product". Permissive options: LAION-CLAP (Apache-2.0 music checkpoints), MS-CLAP (MIT), PANNs (MIT; outputs AudioSet's 7 mood classes directly), MusicFM-FMA (MIT/Apache), MusiCNN (ISC), CLaMP 3 code (MIT, but its audio path consumes MERT features).
7. **The music library is small and fixed (Incompetech, ~2,000 tracks).** This changes the economics: the music side can be *annotated* once, carefully (models + human/LLM comparative judgments), instead of relying on model generalisation. IncompeBench (2026) already built 125k graded text-to-Incompetech relevance labels with a frontier LLM and verified them against expert humans (quadratic-weighted κ = 0.94).
8. **Recommended glue (section 5):** a calibrated, interpretable affect vector per scene and per track segment - valence, arousal, tension, each with an uncertainty - plus a small categorical distribution for "story-music moods", plus a secondary semantic embedding similarity. Combine with weights learned from blind pairwise human judgments (Bradley-Terry), add hysteresis for switching, and an explicit abstain threshold that falls back to a neutral bed or silence. The weighting, calibration and abstain rules are *not* established by any study - they must be our own experiments.

---

## 1. Music side: music emotion recognition (MER)

### 1.1 The benchmarks and what they actually measure

| Dataset | Size / unit | Labels | Perceived vs induced | Notes |
|---|---|---|---|---|
| EmoMusic ("1000 songs", Soleymani et al. 2013) | 744 × 45 s clips (MARBLE split) | static + dynamic V/A | perceived | MARBLE's emotion regression task; metric R² |
| DEAM (Aljanaki, Yang, Soleymani, PLoS ONE 2017) | ~1.8-2k excerpts, 45 s (Kang & Herremans list 2,058) | static + dynamic V/A | perceived | mostly rock/pop/electronic |
| PMEmo (Zhang et al., ICMR 2018) | 794 songs (chorus excerpts) | static + dynamic V/A, EDA | perceived | Chinese university annotators |
| MTG-Jamendo mood/theme (Bogdanov et al. 2019) | ~18.5k tracks | 56-59 multi-label mood/theme tags | user tags (not psych-grounded) | Creative-Commons music; very noisy labels |
| Emotify (Aljanaki, Wiering, Veltkamp, IP&M 2016) | 400 × 1 min, 4 genres | GEMS-9 (induced) | induced | crowdsourcing game; PCA of GEMS gave 3 dims explaining 69 % variance |
| Soundtracks (Eerola & Vuoskoski 2011) | film-music excerpts (Kang & Herremans list 470) | 6 discrete + 3 dims (V, energy, tension) | perceived | closest content to "background music" |
| AudioSet mood subset (Gemmeke et al. 2017) | 16,995 × 10 s YouTube clips (per Won et al.) | 7 exclusive classes: happy, funny, sad, tender, exciting, angry, scary | weak web labels | used by Won 2021, Emo-CLIM, Doh 2023 |
| EMMA database (Univ. Innsbruck, used by Moscati et al., UMAP 2024) | 453 tracks annotated in 2023 | GEMS-9 intensities 0-100, ~15 raters/track | induced | the most psychology-grounded GEMS data I found |
| GlobalMood (Lee et al., ISMIR 2025) | 1,180 songs from 59 countries; 988,925 ratings, 2,519 raters, 5 locations | culture-specific mood terms | perceived | shows a shared V/A structure but term meanings diverge across cultures |

Source of the subjectivity ceiling: the survey by Kang & Herremans (IEEE Trans. Affective Computing 2025, arXiv 2406.08809) catalogues dependence of ratings on musical training, gender, familiarity, culture, genre preference and age, and calls low inter-rater reliability a core obstacle. GlobalMood measured within-country split-half reliability of single mood terms at only r ≈ 0.43-0.49 - i.e. **any model correlating ≈ 0.45-0.5 with mean ratings of a single term is at human level**.

### 1.2 Classic feature engineering vs deep representations

Hand-crafted pipelines (Essentia, openSMILE, MIRtoolbox features + SVR/RF) are not dead but have been overtaken by frozen deep embeddings + a small probe. The survey table (Kang & Herremans 2025) lists e.g. feature-selection + SVR/RF on DEAM at R² = 0.587 V / 0.645 A [ref 107 in the survey], comparable to some CNNs of the same era but below foundation-model probes. Sonus Texere (ISMIR 2022) is instructive in the other direction: for a real book-soundtrack application they ended up using *major/minor mode* (key-strength from MIRtoolbox) as the valence signal because "approaches that predict emotion from audio ... didn't work as well for our application".

**Frozen-probe results on the standard MER tasks (all from the papers' own tables):**

| Model (pretraining) | EmoMusic R² valence | EmoMusic R² arousal | MTG mood/theme ROC-AUC / PR-AUC | Source |
|---|---|---|---|---|
| MusiCNN (supervised MSD) | 0.444 | 0.688 | 0.740 / 0.126 | MARBLE (Yuan et al., NeurIPS 2023 D&B) |
| CLMR (contrastive SSL) | 0.444 | 0.703 | 0.735 / 0.126 | MARBLE |
| Jukebox-5B (generative LM) | 0.570 | 0.730 | 0.776 / 0.153 | MARBLE |
| MULE (supervised, production music) | 0.607 | 0.731 | 0.780 / 0.154 | MARBLE |
| MERT-v1-95M | 0.555 | 0.763 | 0.764 / 0.134 | MARBLE |
| MERT-v1-330M | 0.590 | 0.758 | 0.765 / 0.140 | MARBLE |
| MusicFM (MSD) | 0.603 | 0.763 | - | MuQ paper (Zhu et al. 2025) |
| MuQ-iter (160k h) | 0.628 | 0.761 | - | MuQ paper |
| Previous task SOTA (any setup) | 0.617 | 0.721 | 0.786 / 0.161 | MARBLE table |
| Kang & Herremans 2025 (MERT + multitask + knowledge distillation) | PMEmo 0.547 / DEAM 0.518 | PMEmo 0.794 / DEAM 0.623 | 0.781 / 0.154 | arXiv 2502.03979 via survey |

Text-music joint models probed the same way (TTMR, Doh et al., ICASSP 2023): MTG mood/theme 0.763 / 0.140; Emotify (GEMS-9 single-label) accuracy 0.46-0.53 depending on variant.

### 1.3 How well each representation is predicted

| Target | Typical best result | Reading |
|---|---|---|
| Arousal (static, clip-level) | R² ≈ 0.72-0.79 | reliable; driven by tempo, loudness, timbre brightness |
| Valence (static) | R² ≈ 0.52-0.63 | moderate; strongly genre- and culture-dependent |
| Categorical mood/theme tags (MTG-Jamendo, 56 tags) | ROC-AUC ≈ 0.78, PR-AUC ≈ 0.15-0.16 | poor in absolute terms; much of it is label noise and tag ambiguity |
| GEMS-9 (Emotify, induced) | 46-53 % accuracy (supervised probe), 17-34 % zero-shot (TTMR); LLM-embedding zero-shot F1 40 % (Liu, Roy, Herremans 2024) | weak; chance is 11 % |
| Cross-cultural single mood terms | open CLAP zero-shot r = 0.08; fine-tuned r = 0.31; Gemini 2.5 Pro r = 0.50 ≈ human ceiling (GlobalMood) | only frontier audio-LLMs reach human level |

No benchmark I found reports prediction of a **tension** dimension from audio with modern encoders; tension appears as an annotation dimension (Soundtracks dataset; IsoVAT corpus, TISMIR 2022) and in game-music generation (PreGLAM-MMM, FDG 2022), not as a benchmarked MER target. **Gap.**

### 1.4 Zero-shot mood tagging with joint audio-text models

| Model | Zero-shot evidence relevant to mood | Source |
|---|---|---|
| TTMR (contrastive, BERT text, MSD 0.5M) | MTG mood/theme ROC/PR 0.669 / 0.087 zero-shot vs 0.763 / 0.140 probed; Emotify accuracy 17.5-33.8 % zero-shot vs ≈ 46-52 % probed | Doh, Won, Choi, Nam, ICASSP 2023 |
| MuQ-MuLan | SOTA zero-shot MTT tagging ROC-AUC 79.3, ahead of LAION-CLAP, MS-CLAP 2023 and Google MuLan; no mood-specific number | Zhu et al. 2025 |
| LAION-CLAP / CLAP | GlobalMood zero-shot r = 0.08 (all languages), fine-tune on GlobalMood → 0.31; fine-tune on LLM-translated English terms → 0.13 only | Lee et al., ISMIR 2025 |
| CLaMP 3, TTMR++, LAION-CLAP, ColQwen-Omni | Fine-grained text-to-music retrieval on 1,574 Incompetech snippets, 500 queries incl. mood: nDCG@10 strict 0.46 (CLAP), 0.50 (TTMR++), 0.51 (ColQwen-Omni), 0.57 (CLaMP 3); lenient 0.59-0.70 | Clavié et al. 2026 (IncompeBench) |

Pattern: zero-shot joint embeddings retrieve *tangentially* relevant music reliably (lenient precision@10 > 0.85 for all on IncompeBench), but rank nuance poorly, and their mood axis is far weaker than a supervised probe on the same audio embedding.

### 1.5 Known failure modes (documented)

- **Text tower is the weak link.** Two-tower music models favour generic prompts, are sensitive to specific words, and do not exploit extra context (Vasilakis, Bittner, Pauwels, ISMIR 2024, "I can listen but cannot read"); audio-text models largely ignore word order (Wu, Nieto, Bello, Salamon, ICASSP 2023). Long scene descriptions do not help a CLAP text encoder.
- **Taxonomy mismatch.** Classification across mismatched vocabularies fails outright (Won 2021: P@5 = 0 for ISEAR→AudioSet with a plain classifier).
- **Mode collapse in shared heads.** Won's multi-head classifier predicted one or two emotions for every input.
- **Label noise.** MTG-Jamendo tags and AudioSet mood labels are weak web labels; PR-AUC ≈ 0.15 is partly a ceiling of the labels.
- **Culture and language.** Dictionary-equivalent mood terms are perceived differently across cultures (GlobalMood); "happy" had lower between-country agreement than "calm".
- **Induced ≠ perceived.** User tags vs GEMS-annotated profiles agree poorly (Moscati et al., UMAP 2024: low Cohen's κ / Kendall τ).
- **Clip length.** Emo-CLIM attributes better encoders partly to longer input (10 s CLAP vs 3.7 s CNN); 10 s windows cannot see a track's arc.

### 1.6 Pretrained music models usable locally, by licence

| Model | What it gives | Licence (code / weights) | Usable in a free app? |
|---|---|---|---|
| PANNs CNN14 (Kong et al., TASLP 2020) | 527 AudioSet logits incl. the 7 mood classes; 2048-d embedding | MIT / MIT (Zenodo) | **Yes** |
| LAION-CLAP `larger_clap_music` (Wu et al., ICASSP 2023) | joint audio-text 512-d | Apache-2.0 (HF card) | **Yes** |
| MS-CLAP 2022/2023 (Elizalde et al.) | joint audio-text | MIT | **Yes** |
| MusicFM-FMA (Won, Hung, Le, ICASSP 2024) | SSL music embedding; MSD variant stronger | MIT/Apache badges; FMA version released "to avoid potential licensing complications" | **Yes (FMA version)** |
| MusiCNN (Pons & Serra 2019) | MSD/MTT tagger + embedding | ISC | **Yes** (weakest) |
| CLaMP 3 (Wu et al., Findings ACL 2025) | multilingual text (XLM-R, 100 languages incl. Vietnamese) ↔ music | MIT code; audio path uses **MERT** features | **Text side yes; audio side inherits MERT's NC** |
| MERT-v1-95M/330M (Li et al., ICLR 2024) | strong SSL embedding (24 kHz) | CC-BY-NC-4.0 | Amber: non-commercial only |
| MuQ / MuQ-MuLan (Tencent, 2025) | strongest SSL + joint text | MIT code / CC-BY-NC-4.0 weights | Amber |
| TTMR++ (Doh et al., ICASSP 2024) | text-music 128-d | CC-BY-NC-4.0 | Amber |
| Essentia models (MTG) | ready heads: mood_happy/sad/relaxed/aggressive/party, mtg_jamendo_moodtheme, DEAM/EmoMusic/MuSe A-V regressors | CC BY-NC-SA 4.0 (proprietary on request); library AGPL-3.0 | Amber/red (SA + AGPL) |
| Jukebox | strong but 5B, slow | "Noncommercial Use License" | Red (size too) |
| openSMILE | eGeMAPS etc. | "not allowed ... for any sort of commercial product"; private/research/education only | Red for a distributed app |

"Amber" means: a free, non-monetised app is arguably non-commercial, but CC-BY-NC is ambiguous for redistribution in an app and blocks any later monetisation; get an explicit decision from the book owner before shipping. Training-data licences (DEAM, PMEmo, EmoMusic) also need checking before training a shipped head on them **[unverified per dataset]**.

---

## 2. Text side: emotion in text and narrative

### 2.1 Supervised classifiers and their ceilings

| Resource | Content | Reliability / ceiling | Best model numbers |
|---|---|---|---|
| GoEmotions (Demszky et al., ACL 2020) | 58k Reddit comments, 27 emotions + neutral, multi-label | inter-rater correlation varies widely per emotion; grief/relief/realization hardest | BERT avg F1 0.46 (28 classes), 0.64 (Ekman 6), 0.69 (sentiment groups) |
| EmoBank (Buechel & Hahn, EACL 2017) | 10k English sentences, VAD 1-5, reader + writer views | reader perspective gives higher agreement | EmoPair re-annotation raised Krippendorff α for arousal 0.595 → 0.896, dominance 0.570 → 0.865 |
| Alm's fairy tales (Alm, Roth, Sproat 2005) | ~1.2k sentences, 5-7 emotions | κ 0.24-0.51, overlap 45-64 % (as cited by Bardo 2017) | - |
| ISEAR (Scherer & Wallbott) | 7.6k self-reports, 7 emotions | - | GPT-4 macro-F1 0.739 vs BERT 0.726 (Niu et al. 2024) |
| REMAN (Kim & Klinger, COLING 2018) | literary passages with emotion, experiencer, cause, target | - | literature-specific; survey: Kim & Klinger 2019 |
| NRC VAD Lexicon v2 (Mohammad 2025) | 55k English terms incl. 10k multi-word expressions | split-half r = 0.99 V, 0.98 A, 0.96 D | lexicon, not a model |
| BRIGHTER / SemEval-2025 Task 11 | ~100k texts, 28 languages, 6 emotions + intensity 0-3 | CC-BY-4.0 | **no Vietnamese, Japanese or Korean**; Chinese included |

Domain matters: Bardo's tabletop-RPG transcripts got κ = 0.60 with a deliberately coarse 4-class "story emotion" model (happy, calm, agitated, suspenseful), above fairy-tale agreement. **Coarser, music-relevant label sets are easier to agree on.**

### 2.2 LLMs as zero/few-shot emotion and VAD annotators

| Study | Finding |
|---|---|
| Niu, Jaiswal, Mower Provost 2024 (arXiv 2408.17026) | GPT-4 ≈ BERT on ISEAR (0.739 vs 0.726 macro-F1) but well below on GoEmotions (0.375 vs 0.521). Yet blind human evaluators *preferred GPT-4's labels over the original human labels* on 62-71 % of items. |
| Inoshita, Zhou, Kawai, Yada 2026 (arXiv 2604.27345) | EmoBank Pearson r - valence: GPT-5.4-mini 0.669, Claude Haiku 4.5 0.658, Llama-3.1-8B 0.562, Qwen3-8B 0.486; arousal: 0.342 / 0.342 / 0.227 / 0.188; dominance ≤ 0.34. LLM rating SD 0.24-0.34 vs human 0.48-0.68 (compressed). On GoEmotions distributions, zero-shot JSD ≥ 0.45 vs 0.30 for fine-tuned RoBERTa; entropy correlation 0.20-0.24 vs 0.47. Isotonic regression calibration cut JSD 8-14 % but did not close the gap. LLMs succeed on "lexically transparent" emotions, fail on pragmatic ones. |
| Bagdon, Karmalkar, Gurulingappa, Klinger, NAACL 2024 | For LLM intensity annotation, best-worst scaling beats direct rating scales; models trained on automatic BWS labels perform comparably to models trained on human labels. |
| Kiritchenko & Mohammad, ACL 2017 | For humans, BWS gives significantly more reliable intensity rankings than rating scales for the same annotation budget. |
| EmoPair (Chrzan et al., ICML AI4Good workshop 2026) | Pairwise comparisons + concept-guided CoT LLM, validated with the Alternative Annotator Test; large reliability gains on arousal/dominance. |
| Calderon, Reichart, Dror, ACL 2025 (alt-test) | Statistical test to justify replacing human annotators with an LLM using a modest human-labelled subset; closed models sometimes pass, open ones less often. |
| EmotionArcs (LaTeCH-CLfL 2024) | Emotion arcs for 9,000 literary texts; volunteers judged the model's category correct in 225/232 checked passages (validation of presence, not of intensity). |

Implication for us: a local 8-9B LLM asked "rate arousal 1-9" will give a compressed, noisy signal (r ≈ 0.2 on EmoBank for 8B models). Asking it to *compare* scenes within a chapter, and then calibrating, is the evidence-backed way to get usable arousal/tension.

### 2.3 Scene- and document-level mood

Research is thin. What exists:
- Sentence-level classifiers aggregated over windows: Bardo (sliding window + density threshold, finite-state machine that switches only when evidence exceeds a threshold, because "emotion transitions are somewhat rare"); Sonus Texere (paragraph classifier, majority vote per chapter segment; unsupervised text segmentation gave 87 segments for 17 chapters, ≈ 4 min of reading each).
- LLM scene segmentation: M2M-Gen prompts GPT-4/4o to split a manga into scenes from dialogue and to write a scene-level "music directive", then page-level captions.
- Emotion arcs (EmotionArcs 2024; earlier Reagan et al. 2016) model trajectories, but not "what music fits this 3-minute span".

There is **no benchmark for scene-level "mood for underscoring"** in prose. Our own gold set will be the first for this genre mix.

### 2.4 Mixed emotions: label distributions and representation mapping

- **Emotion Distribution Learning** (Zhou et al., EMNLP 2016): predict a distribution over emotions with intensities, using Plutchik-wheel relations as constraints.
- **Categorical → dimensional** (Park et al., EMNLP 2021): learn VAD from categorically labelled data by sorting labels along NRC-VAD values and minimising Earth Mover's Distance between predicted and label-induced distributions. Useful when we only have categorical scene labels.
- **Representation mapping** (Buechel & Hahn, COLING 2018, EmoMap): converting VAD ↔ basic emotions is "about as reliable as human annotation" across many languages.
- **Distributional evaluation** (Inoshita 2026): report JSD/entropy correlation, not only accuracy; LLMs under-represent ambiguity.

### 2.5 Vietnamese, CJK and cross-lingual transfer

| Resource | Language | Size / labels | Best reported |
|---|---|---|---|
| UIT-VSMEC (Ho et al., PACLING 2019; arXiv 1911.09339) | Vietnamese social media | 6.9k sentences, 7 Ekman-style labels | CNN weighted-F1 59.7 % (original); PhoBERT accuracy ≈ 64.7 %; BERT weighted-F1 66.0 % in later studies |
| ViGoEmotions (Tran et al., EACL 2026) | Vietnamese social comments | 20,664 comments, 27 GoEmotions labels, CC-BY-4.0 | ViSoBERT macro-F1 61.5 %, weighted-F1 63.3 % |
| WRIME (Kajiwara et al., NAACL 2021) | Japanese SNS | 17k posts, Plutchik-8 × 4 intensities, writer + reader | readers underestimate writers' emotions |
| KOTE (Jeon et al. 2022; LREC-COLING 2024 guide) | Korean online comments | 50k comments, 43 emotions + none | culturally derived taxonomy |
| Chinese EmoBank (Lee et al., TALLIP 2022) | Chinese | VA resources | - |
| BRIGHTER | 28 languages | 6 emotions + intensity | no vi/ja/ko |

None of these is narrative fiction, and none is Vietnamese *translated* fiction. Cross-lingual: XLM-R-based encoders (also the CLaMP 3 text tower) and multilingual LLMs are the practical route. GlobalMood's control experiment is a warning for the music vocabulary: fine-tuning CLAP on LLM-translated English mood terms did not help (r 0.13 vs 0.31 with native terms) - **mood words do not translate one-to-one**. For our pipeline, that argues for an *language-independent numeric glue* (V/A/T) rather than matching Vietnamese mood words to English music tags.

---

## 3. The bridge: cross-modal text ↔ music (and nearest neighbours)

### 3.1 Direct text → music by emotion

| Work | Shared representation | Training data | Objective | Evaluation | Headline result / conclusion |
|---|---|---|---|---|---|
| **Won, Salamon, Bryan, Mysore, Serra - "Emotion Embedding Spaces for Matching Music to Stories", ISMIR 2021** (best student paper; MIT code) | Compared 6: classification, shared-MLP multi-head, **V-A regression** (labels → V-A via NRC-VAD), Word2Vec regression (music-domain W2V), 2-branch and **3-branch metric learning** (tag/text/music triplets) | Text: Alm's fairy tales (1,040 train sentences; Beatrix Potter held out) and ISEAR (7,666); Music: AudioSet mood subset (16,104 train clips, 7 classes) | MSE regression; triplet loss with distance-weighted negative sampling; nearest W2V tag as cross-modal positive | Macro P@5 and MRR under three label mappings (V-A, W2V, manual) | Alm, manual mapping: V-A regression P@5 0.61 / MRR 0.74; 3-branch 0.52 / 0.59. ISEAR manual: V-A 0.62 / 0.71; 3-branch 0.60 / 0.67; W2V regression best MRR 0.77. Classification fails (0 on ISEAR). V-A is "a powerful baseline"; 3-branch metric learning "comparable, more general" and preserves within-modality neighbourhoods. Text input = several sentences. |
| **Doh, Won, Choi, Nam - Textless speech-to-music retrieval, ICASSP 2023** | joint embedding + emotion-similarity regulariser | IEMOCAP, RAVDESS, HIKIA speech; AudioSet mood music | triplet + regulariser pulling pairs close in proportion to emotion similarity | P@5, MRR | ≈ 0.67-0.68 P@5 (as tabulated by Emo-CLIM). Shows "soft" emotion similarity helps beyond hard labels. |
| **Liu, Roy, Herremans - LLM embeddings for cross-dataset label alignment, AIMC 2026 (arXiv 2410.11522)** | LLM embedding space of emotion *words*; Mean-Shift clusters as anchors | MTG-Jamendo, CAL500, Emotify | map MERT features onto label-cluster centres + alignment regulariser | zero-shot on unseen label set | Emotify zero-shot F1 40 %; method for merging heterogeneous taxonomies without hand mapping |
| **Sonus Texere (Shriram, Tapaswi, Alluri, ISMIR 2022)** | coarse valence: text pos/neu/neg (BERT on Reddit) vs music major/minor mode | Harry Potter 1 + its film score (19 tracks → 47 segments) | no training of the bridge; book↔film alignment via dialogue + CLIP, emotion fallback | 10 readers, semi-structured interviews, no control condition | 45/87 segments got film-aligned music, 42 used emotion fallback. All readers said immersion improved; instrumental preferred; looped repetition acceptable; transitions at narrative shifts were noticed and liked. Audio-emotion models "didn't work as well" as mode. |
| **Story2MIDI (Shokri et al., 2025, arXiv 2512.02192)** | shared emotion label | text sentiment datasets merged with music emotion datasets into pseudo-pairs | seq2seq generation | objective metrics + listening study | pseudo-pairs via shared labels are enough to learn emotion-relevant generation (generation, not retrieval) |

### 3.2 General text → music retrieval (joint embeddings)

| Work | Data | Objective | Relevance to us |
|---|---|---|---|
| MuLan (Huang et al., ISMIR 2022) | 44M recordings, weak free text | contrastive, 128-d | proves scale works; closed |
| MusCALL (Manco et al., ISMIR 2022) | production-music captions | contrastive + intra-modal | zero-shot genre/tagging |
| TTMR (Doh et al., ICASSP 2023) | MSD + tags/captions | contrastive beats triplet; "stochastic" tag/sentence sampling | zero-shot mood much weaker than probing (1.4) |
| LP-MusicCaps (Doh et al., ISMIR 2023) | 2.2M LLM pseudo-captions from tags, 0.5M clips | captioning | LLM-generated text from tags is usable supervision |
| TTMR++ (Doh et al., ICASSP 2024) | + fine-tuned LLaMA-2 captions + artist metadata | contrastive | richer text → better retrieval (NC licence) |
| CLaMP 3 (Wu et al., Findings ACL 2025) | multilingual, multi-modal | contrastive with text as hub | best on IncompeBench; Vietnamese text in principle supported (XLM-R) |
| IncompeBench (Clavié et al. 2026) | 1,574 Incompetech snippets, 500 queries, 125k graded labels | evaluation only | **directly our catalogue**; LLM judge (Gemini 3 Pro) vs 3 humans incl. a musician on n = 385: macro precision 0.92, quadratic κ 0.94; main LLM error: leniency (0 labelled as 1) |

### 3.3 Image/video → music (most mature neighbour)

| Work | Representation | Supervision | Result / lesson |
|---|---|---|---|
| CBVMR (Hong, Im, Yang, ICMR 2018; HIMV-200K) | two-branch embedding | 200k co-occurring video-music pairs | soft *intra-modal structure* loss keeps each modality's neighbourhood - same idea as Won's 3-branch |
| Prétet, Richard, Peeters (IJCNN 2021; ISMIR 2021) | embedding | music videos | pretrained audio embeddings largely improve recommendation |
| MVPt (Surís, Vondrick, Russell, Salamon, CVPR 2022) | Transformers over long temporal context | self-supervised, no labels | up to 10× retrieval accuracy over prior SOTA; long context matters |
| ViML (McKee, Salamon, Sivic, Russell, CVPR 2023) | video + free-text prompt → music | (video, music) pairs + LLM-made "prompt analogies" for missing text | users steer retrieval with language; YouTube8M-MusicTextClips released |
| EmoMV (Thao, Roig, Herremans, Information Fusion 2023) | matched / mismatched by emotion | EmoMV-A human labels; B and C labels *predicted by a pretrained network* | emotion-correspondence datasets can be bootstrapped with model labels |
| Emo-CLIM (Stewart, Avramidis, Feng, Narayanan, ICASSP 2024) | joint image-music space | DeepEmotion (21,829 images) + AudioSet mood (13,713 clips); manual label mapping, ambiguous classes dropped | cross-modal + intra-modal **SupCon** (weights 0.25 each); frozen CLAP encoder best: image→music P@5 68.2 %, MRR 76.7 % |
| MMVA (Choi, Kim, Kang, AAAI 2025 AI4Music workshop) | V-A continuous | IMEMNet-C: 24,756 images + 25,944 music clips (+ LLM captions) | pairs scored by S = exp(−d(VA_img, VA_music)), enabling **soft positives from separately labelled data** |
| Stewart et al., ICASSP 2025 (Dolby) | joint video-music | self-supervised pairs + label-supervised contrastive | inference-time knob between "co-occurrence" and "label" similarity |
| MuseChat (Dong et al., CVPR 2024) | retrieval + Vicuna-7B explanation | conversational dataset | dialogue refinement of music choice |
| Video2Music (Kang, Poria, Herremans, ESWA 2024); SymMV (Zhuo et al., ICCV 2023); MVED (Pandeya & Lee 2021) | generation / datasets | emotion features as conditioning | emotion is used as an explicit control signal in generation |

### 3.4 Stories, games, LLM agents

| Work | Glue | Evaluation | Lesson |
|---|---|---|---|
| Bardo (Padovani, Ferreira, Lelis, AIIDE 2017) | 4 story emotions; songs pre-labelled | 61 participants, 305 paired judgments of D&D videos: Bardo preferred 163, original authors' music 74, ties 68 (binomial p = 7.3e-9); per-excerpt preference tracked classifier accuracy | coarse classes + hysteresis already beat human-chosen music in that setting |
| Bardo Composer (Ferreira, Lelis, Whitehead, AIIDE 2020) | 4 classes mapped to V/A quadrants; separate V and A classifiers | 116 participants identified intended emotion | V and A treated independently works |
| Babel Bardo (Marra & Ferreira, LAMIR 2024) | LLM writes music descriptions for MusicGen every 30 s | objective only: FAD, PaSST-label KL to the original soundtrack, transition KL | the **emotion-only** variant beat detailed LLM descriptions on story alignment and transition smoothness; consistency between consecutive descriptions matters |
| M2M-Gen (Sharma, Haseeb, Xia, Tsuruoka, 2024) | GPT-4o scene directive → page captions → text-to-music | 22 Japanese-fluent raters, 5-pt Likert: relevance 3.40 vs baseline 3.25 vs random 2.34; consistency +0.5 | Relevance / quality / consistency triad is a usable rating protocol; random lower bound is essential |
| WavJourney (Liu et al., 2023; IEEE journal version 2025), MM-StoryAgent (2025), BackgroundMellow (2026), Audio-Oscar (2026) | LLM script → generators; BackgroundMellow adds a cinematic BGM *retriever* | mostly subjective MOS or objective proxies | agent pipelines exist but none validates the matching decision itself |
| PreGLAM-MMM (Plut, Pasquier, Ens, Tchemeube, FDG 2022); IsoVAT (TISMIR 2022); survey Plut & Pasquier, Entertainment Computing 2020 | **Valence-Arousal-Tension** from an appraisal model of gameplay | adaptive score rated nearly equivalent to a composed linear score for congruency, immersion, preference | VAT is the established game-music control space; tension is first-class there |
| Sound of Story (Bae et al., Findings EMNLP 2023) | story (image+text) ↔ background audio retrieval | 27,354 stories, 984 h audio | closest large paired data, but visual stories |

### 3.5 What a product team can take from section 3

1. Use a **shared, explicit affect space** as the contract between sides; it is the only bridge validated for *text* → music, and it degrades gracefully when vocabularies differ (Won 2021).
2. Train or tune with **soft** similarity, not only exact label equality (Doh 2023 regulariser; MMVA exp(−d)); add **intra-modal** terms to keep each side's structure (CBVMR, Won 3-branch, Emo-CLIM).
3. **Coarse beats fine** at the decision level: 4-7 classes or 2-3 dimensions produce better-agreed labels and, in Babel Bardo, better story alignment than rich descriptions.
4. **Stability is part of quality**: switching hysteresis (Bardo) and consistent descriptions (Babel Bardo) measurably help; readers tolerate loops (Sonus Texere).
5. **Instrumental, style-consistent** music is preferred under reading (Sonus Texere interviews).
6. Evaluate with **blind paired preference against a baseline and a random floor** (Bardo, M2M-Gen).

---

## 4. Training methods when paired (scene, track) data is scarce

### 4.1 Toolbox, with evidence

| Method | How | Evidence | Data needed (observed in literature) |
|---|---|---|---|
| Separate regressors into a fixed space (V/A, V/A/T) | text → VAT; music → VAT; nearest neighbour | Won 2021 (best/tied), Bardo Composer | Won: ~1k text sentences + ~16k music clips |
| Shared-label weak supervision, metric learning | triplets (anchor text, positive track with "nearby" label) + tag branch | Won 3-branch; CBVMR | same as above |
| Supervised contrastive (SupCon) across modalities | batch-wide positives = same label | Emo-CLIM (beats triplet-based prior work) | 21.8k images + 13.7k clips |
| Soft positives from continuous labels | weight pair by exp(−‖VA_t − VA_m‖) | MMVA 2025; Doh 2023 | tens of thousands per side |
| LLM-embedding label anchors | embed every tag/emotion word with an LLM, cluster, regress audio onto anchors | Liu, Roy, Herremans 2024 | existing tagged music sets |
| LLM pseudo-text for music | LLM writes captions from tags/metadata, train text-music | LP-MusicCaps, TTMR++, MMVA | 0.5M clips (we can do far less for fine-tuning) |
| Knowledge distillation across heterogeneous datasets | teachers per dataset → multitask student | Kang & Herremans 2025 | several MER sets |
| Ranking from pairwise judgments | ListNet/RankNet/Bradley-Terry over pairs | Yang & Chen, IEEE TASLP 2011 (ranking-based MER: lower annotation load, more reliable ground truth); BWS/EmoPair for text | hundreds to a few thousand comparisons |
| LLM-as-annotator with validation | LLM labels, check with alt-test or sampled human audit | IncompeBench (κ 0.94 on 385 sampled pairs); alt-test (ACL 2025) | audit set ≈ 385 for ±5 % at 95 % confidence (IncompeBench's sample-size rule) |
| Fine-tuning joint encoders on small native data | e.g. CLAP on 1,180 songs | GlobalMood: r 0.08 → 0.31 | ~1k items moves a zero-shot model a lot |
| Active learning for cross-modal matching | uncertainty sampling of (scene, track) pairs | **no study found for text-music** | - |

### 4.2 A training recipe that fits our constraints (S, assembled from I-grade pieces)

1. **Music side, offline, once.** Segment each track into homogeneous sections (Sonus Texere used key-strength novelty; any SSM novelty works). For each segment compute permissive embeddings (CLAP-music, PANNs, MusicFM-FMA) and train small V/A heads on DEAM/PMEmo/EmoMusic if licences allow; get tension from a head trained on Soundtracks-style data or from comparative labels. Then **re-anchor on our own library** with comparative judgments (BWS over 4-tuples of tracks, by the book owner and by an LLM that sees only text metadata + feature summaries - an audio-listening LLM is not available locally).
2. **Text side.** Local LLM (the project's Qwen 9B LoRA) produces for each scene: (a) categorical distribution over a small story-music vocabulary, (b) **comparative** arousal/tension/valence rankings within a chapter window, converted to scores by BWS counting or Bradley-Terry; (c) a short music-style descriptor. Distil into a small, fast regressor if needed.
3. **Calibration.** Fit isotonic (monotone) maps from each side's raw scores to a common anchored scale using a shared anchor set (section 5.3).
4. **Glue weights.** Collect blind pairwise human preferences "track A vs track B for this scene"; fit a Bradley-Terry / logistic model over per-dimension distances, category JSD and embedding cosine. This is the only part that is genuinely cross-modal, and it needs few parameters - so hundreds of judgments suffice to fit it, unlike a deep joint encoder.
5. **Only later**, once ≥ ~1-2k validated (scene, track, preference) triples exist, try a learned joint space (3-branch metric learning or SupCon with soft positives) initialised from the frozen encoders, and keep it only if it beats step 4 on held-out books.

### 4.3 Evaluation protocol (what the literature supports)

- **Blind, paired, with floors**: system vs baseline (e.g. arousal-only or random-in-genre) vs random; binomial test on preferences (Bardo) or within-subject ANOVA on Likert relevance/quality/consistency (M2M-Gen).
- **Human ceiling first**: measure split-half or inter-rater reliability on the same items (GlobalMood's rwithin); a model at the ceiling cannot be improved by more modelling.
- **Graded relevance + nDCG** for ranked candidates (IncompeBench), with strict and lenient variants.
- **Distributional metrics** for mixed emotions (JSD, entropy correlation; Inoshita 2026).
- **LLM judges only after an audit**: alt-test or a stratified sample (n ≈ 385) with κ reported; watch for leniency bias.
- **Preregister** (before looking at results): item sampling, rater instructions, primary metric, decision thresholds - consistent with the project's "pre-registered rules" practice. Hold out whole books (Won held out an author to avoid leakage).

### 4.4 Standards and ontologies for machine use

- **EmotionML 1.0**, W3C Recommendation, 22 May 2014: represents emotions as categories, dimensions, appraisals and action tendencies, standalone or embedded; custom vocabularies are allowed by URI.
- **Vocabularies for EmotionML**, W3C Working Group Note, 1 April 2014: category sets (Ekman big six, 17 everyday categories, OCC 22, FSRE 24, Frijda 12), dimension sets (Mehrabian PAD; FSRE valence/potency/arousal/unpredictability; intensity), appraisal sets (OCC, Scherer, EMA), Frijda action tendencies. **No GEMS and no music-specific set.**
- **De-facto music vocabularies**: AudioSet ontology's 7 mood classes; MTG-Jamendo's 56 mood/theme tags; MIREX 5 mood clusters (Essentia `moods_mirex`).
- **GEMS for machines**: no standard found. GEMS-9 names are used freely; the **GEMS-45 term list requires permission** from Zentner et al. (stated by Moscati et al., UMAP 2024). EMMA is the main GEMS-annotated database. IsoVAT gives a VAT-parameterised feature corpus for composition.
- Practical stance: store our affect data as EmotionML-compatible JSON with our own vocabulary URIs (e.g. `abook:vat` dimension set, `abook:story-mood` category set), plus Mehrabian PAD where a standard dimension name is wanted.

---

## 5. Conclusions for implementation

### 5.1 The glue: a calibrated affect contract plus a learned combiner

Per scene *s* and per track segment *m*:

- `vat` = (valence, arousal, tension), each in [−1, 1], each with σ (uncertainty).
- `mood` = probability distribution over ~8-12 story-music moods (seed from AudioSet-7 + calm, suspense, mysterious, epic/heroic, nostalgic, romantic; final list from the psychology report).
- `sem` = optional embedding for style/setting (e.g. "medieval tavern", "school festival"), using CLaMP 3 text (multilingual, MIT) against a permissive audio tower, or LAION-CLAP on an English rewrite.
- Hard tags: vocals (none required), intensity ceiling under narration, loop-ability.

Why this and not a single learned embedding: it is the only representation validated for text→music; it is language-independent (important given GlobalMood's translation result); it is inspectable and editable by the book owner ("đề xuất, không tự sửa" fits naturally); and it lets us use the reliable dimension (arousal) at full weight while down-weighting the weak ones.

### 5.2 Models on each side (local, licence-safe first)

| Side | Primary | Secondary / check |
|---|---|---|
| Music embeddings | LAION-CLAP music (Apache-2.0), PANNs CNN14 (MIT, gives AudioSet mood logits), MusicFM-FMA (MIT) | MERT / MuQ only if the owner accepts CC-BY-NC |
| Music V/A/T heads | small MLP probes on frozen embeddings; re-anchored on our library with comparative labels | Essentia DEAM/EmoMusic heads as a reference during development only (NC-SA) |
| Music structure | segment tracks; score per segment | keep segment boundaries as allowed switch points |
| Text | local Qwen 9B LoRA: scene segmentation, mood distribution, *comparative* VAT | ViGoEmotions/UIT-VSMEC fine-tuned PhoBERT/ViSoBERT as a cheap cross-check on Vietnamese surface emotion |
| Semantics | CLaMP 3 text tower (XLM-R) or LLM English rewrite → CLAP text | IncompeBench to sanity-check retrieval on Incompetech |

### 5.3 Calibrating both sides into the same space

1. **Anchor set.** ~40-60 "anchor scenes" and ~40-60 "anchor tracks" spanning the space; the book owner (and optionally 2-3 more raters) places them by BWS on each dimension. This defines the shared scale, the way NRC-VAD anchors words.
2. **Monotone maps.** Fit isotonic regression from each side's raw outputs to the anchored scale (Inoshita 2026: isotonic was the best post-hoc calibrator). Re-expand LLM variance - its raw spread is about half of humans'.
3. **Per-dimension reliability.** Estimate σ per dimension from held-out error; expect arousal tightest, valence/tension looser (music) and valence tightest, arousal loosest (text, small LLMs). These σ's become the weights in matching.
4. **Avoid naive quantile matching** of book vs library distributions: a dark book should not be forced to use bright music.

### 5.4 Scoring a match

Score(s, m) = − Σ_d w_d (μ_s,d − μ_m,d)² / (σ_s,d² + σ_m,d² + τ_d²) − λ · JSD(mood_s, mood_m) + γ · cos(sem_s, sem_m) − penalties (vocals, over-loud, recently used) + κ · [m continues the current track/cue].

Fit w, λ, γ, κ, τ by Bradley-Terry on blind pairwise preferences. Switching: only change cue when the new best beats the current cue by a margin for ≥ N consecutive text units (Bardo-style hysteresis), and prefer switches at scene boundaries.

### 5.5 Uncertainty, mixed emotion, and "no good match → silence"

- Mixed scenes: keep the full mood distribution; if bimodal (e.g. comic + sad), prefer tracks whose own distribution is broad, or the mood that persists in the *next* scene (foreshadowing was appreciated in Sonus Texere) - **S**.
- Abstain: define P(fit) = sigmoid(calibrated score) from the human data; if max P(fit) < θ or text uncertainty (σ or entropy) is high, use a **neutral bed** (low-arousal, mid-valence ambient) or silence. θ chosen on a held-out set to keep the "bad fit" rate under a preregistered limit.
- No study evaluates when silence beats any music for narrated text - **gap**; our experiment E5 must decide it.

### 5.6 Proven vs speculative

| Claim | Grade |
|---|---|
| Shared V-A regression bridges text and music across mismatched taxonomies | **P** (Won 2021, fairy tales/ISEAR, AudioSet mood) |
| Arousal from audio is reliable (R² ≈ 0.75); valence moderate (≈ 0.55-0.63) | **P** (MARBLE, MuQ, Kang 2025) |
| GEMS-9 from audio is weak (≈ 50 % / 9 classes) | **P** (TTMR on Emotify) |
| Zero-shot CLAP mood scores are near useless for fine judgments | **P** (GlobalMood r = 0.08) |
| Coarse emotion classes + hysteresis beat human-chosen music for RPG videos | **P** in that domain (Bardo, n = 61) |
| Readers like a continuous, instrumental, emotion-matched book soundtrack | **I** (Sonus Texere, n = 10, no control) |
| Comparative (BWS/pairwise) annotation beats direct rating for text intensity, also with LLMs | **P** (Kiritchenko 2017; Bagdon 2024) |
| Small local LLMs give weak arousal ratings (r ≈ 0.2) | **P** on EmoBank sentences; **I** for novel scenes |
| Soft-positive / SupCon training creates a usable joint space from separately labelled data | **I** (image/speech-music) |
| LLM relevance judgments on Incompetech match experts (κ 0.94) | **P** for a frontier cloud model; **S** for a local 9B |
| Learned BT weights over affect distances will beat fixed weights | **S** |
| Abstain/silence threshold improves experience | **S** (gap) |
| Tension prediction from audio with modern encoders | **S** (gap; only annotation datasets) |

### 5.7 Prioritised experiments (expected value = impact × probability of a usable answer ÷ cost)

| # | Experiment | Why first | Cost | Expected value |
|---|---|---|---|---|
| E1 | **Gold set + human ceiling**: 150-300 scenes from JP LN / KR / CN translations × 6-8 candidate tracks each; blind pairwise preferences from the owner (+ 1-2 more raters on a subset); split-half reliability | every later metric needs it; tells us how good "good" can be | medium (rating hours) | **Very high** |
| E2 | **Music affect on our library**: compare PANNs-mood, CLAP zero-shot, CLAP/MusicFM + probe (trained on DEAM/PMEmo), against BWS ratings of ~200 track segments | music side is fixed and finite - errors here hurt every book | low-medium | **High**; expect arousal ρ ≥ 0.7, valence lower |
| E3 | **Text affect**: local LLM direct ratings vs within-chapter pairwise/BWS vs fine-tuned PhoBERT cross-check, scored against E1 scene labels; isotonic calibration | decides how the text side is produced | low (GPU time) | **High**; pairwise expected to win on arousal/tension |
| E4 | **Glue ablation**: V/A only → +T → +mood JSD → +semantic cosine → BT-learned weights; metric = agreement with E1 preferences and nDCG@5 | identifies which part of the contract carries the signal | low once E1-E3 exist | **High** |
| E5 | **Abstain / silence**: at several score levels, raters compare best-match vs neutral bed vs silence | no literature; directly shapes UX | medium | Medium-high |
| E6 | **Switching policy**: hysteresis margin and minimum dwell; ratings of transitions + count of switches per chapter | stability shown to matter (Bardo, Babel Bardo) | low | Medium |
| E7 | **Learned joint space** (3-branch metric learning or SupCon with exp(−dVAT) soft positives, frozen encoders + small heads) | only once ≥ 1-2k validated triples exist | medium | Medium; keep only if it beats E4 on held-out books |
| E8 | **LLM judge audit**: can a local model (text-only, from track metadata + features) reproduce E1 preferences? alt-test on a stratified sample | would let annotation scale cheaply | low | Medium |

### 5.8 Gaps where no research exists (as far as I could find)

1. A paired (prose scene, background track) dataset with human fit judgments - for any language.
2. Any study of music matching for **Vietnamese** text, or for translated JP/KR/CN web fiction.
3. Prediction of **tension** from audio with modern foundation models; prediction of **GEMS** from text.
4. When silence beats music under narration; how narration loudness/voice interacts with chosen music emotion.
5. Validation of **local** audio-language models as music-emotion judges (only Gemini evaluated against humans in GlobalMood).
6. Active learning for cross-modal emotional matching.
7. Long-form consistency (leitmotifs, per-character themes) in retrieval rather than generation - Sonus Texere borrowed it from a film score; nobody has solved it for a generic library.
8. Cultural calibration for Vietnamese listeners (GlobalMood covers U.S., France, Mexico, South Korea, Egypt).

---

## References (with links)

Music representation and MER
- Yuan, Ma, Li, Zhang et al. MARBLE: Music Audio Representation Benchmark for Universal Evaluation. NeurIPS 2023 Datasets & Benchmarks. https://arxiv.org/abs/2306.10548
- Zhu, Zhou, Chen, Yu et al. MuQ: Self-Supervised Music Representation Learning with Mel Residual Vector Quantization. arXiv 2025. https://arxiv.org/abs/2501.01108 ; weights https://huggingface.co/OpenMuQ
- Li et al. MERT. ICLR 2024. https://huggingface.co/m-a-p/MERT-v1-95M (CC-BY-NC-4.0)
- Won, Hung, Le. A Foundation Model for Music Informatics (MusicFM). ICASSP 2024. https://github.com/minzwon/musicfm
- Kong et al. PANNs. IEEE/ACM TASLP 2020. https://github.com/qiuqiangkong/audioset_tagging_cnn
- Wu et al. Large-scale contrastive language-audio pretraining (LAION-CLAP). ICASSP 2023. https://huggingface.co/laion/larger_clap_music
- Elizalde, Deshmukh, Wang. MS-CLAP. https://github.com/microsoft/CLAP
- Pons & Serra. musicnn. https://github.com/jordipons/musicnn
- Essentia models (CC BY-NC-SA 4.0). https://essentia.upf.edu/models.html
- openSMILE licensing. https://github.com/audeering/opensmile
- Jukebox (Noncommercial Use License). https://github.com/openai/jukebox
- Kang & Herremans. Are we there yet? A brief survey of music emotion prediction datasets, models and outstanding challenges. IEEE Trans. Affective Computing 2025. https://arxiv.org/abs/2406.08809
- Kang & Herremans. Towards unified music emotion recognition across dimensional and categorical models. arXiv 2025. https://arxiv.org/abs/2502.03979
- Liu, Roy, Herremans. Leveraging LLM embeddings for cross dataset label alignment and zero shot music emotion prediction. AIMC 2026 / arXiv 2410.11522. https://arxiv.org/abs/2410.11522
- Lee, Çelen, Harrison, Anglada-Tort, van Rijn, Park, Schönwiesner, Jacoby. GlobalMood: A cross-cultural benchmark for music emotion recognition. ISMIR 2025. https://arxiv.org/abs/2505.09539
- Aljanaki, Wiering, Veltkamp. Studying emotion induced by music through a crowdsourcing game. Information Processing & Management 2016. https://doi.org/10.1016/j.ipm.2015.03.004
- Moscati, Strauß, Jacobsen, Peintner, Zangerle, Zentner, Schedl. Emotion-based music recommendation from quality annotations and large-scale user-generated tags. UMAP 2024. https://doi.org/10.1145/3627043.3659540
- Vasilakis, Bittner, Pauwels. I can listen but cannot read. ISMIR 2024. https://arxiv.org/abs/2407.18058
- Wu, Nieto, Bello, Salamon. Audio-text models do not yet leverage natural language. ICASSP 2023. https://arxiv.org/abs/2303.10667
- Yang & Chen. Ranking-based emotion recognition for music organization and retrieval. IEEE TASLP 19(4), 2011.

Text emotion
- Demszky et al. GoEmotions. ACL 2020. https://aclanthology.org/2020.acl-main.372/
- Buechel & Hahn. EmoBank. EACL 2017. https://aclanthology.org/E17-2092/
- Buechel & Hahn. Emotion representation mapping ... (mostly) performs on human level. COLING 2018. https://aclanthology.org/C18-1245/
- Park et al. Dimensional emotion detection from categorical emotion. EMNLP 2021. https://aclanthology.org/2021.emnlp-main.358/
- Zhou et al. Emotion distribution learning from texts. EMNLP 2016. https://aclanthology.org/D16-1061/
- Mohammad. NRC VAD Lexicon v2. 2025. https://arxiv.org/abs/2503.23547
- Niu, Jaiswal, Mower Provost. From text to emotion: unveiling the emotion annotation capabilities of LLMs. 2024. https://arxiv.org/abs/2408.17026
- Inoshita, Zhou, Kawai, Yada. LLMs capture emotion labels, not emotion uncertainty. 2026. https://arxiv.org/abs/2604.27345
- Bagdon, Karmalkar, Gurulingappa, Klinger. Automatic best-worst-scaling annotations for emotion intensity modeling. NAACL 2024. https://aclanthology.org/2024.naacl-long.439/
- Kiritchenko & Mohammad. Best-worst scaling more reliable than rating scales. ACL 2017. https://aclanthology.org/P17-2074/
- Chrzan et al. EmoPair. ICML AI4Good workshop 2026. https://github.com/EDSI-UMD-College-Park/EmoPair
- Calderon, Reichart, Dror. The Alternative Annotator Test for LLM-as-a-Judge. ACL 2025. https://aclanthology.org/2025.acl-long.782/
- Kim & Klinger. A survey on sentiment and emotion analysis for computational literary studies. 2019. https://arxiv.org/abs/1808.03137
- EmotionArcs: Emotion arcs for 9000 literary texts. LaTeCH-CLfL 2024. https://aclanthology.org/2024.latechclfl-1.7.pdf
- Ho et al. Emotion recognition for Vietnamese social media text (UIT-VSMEC). PACLING 2019. https://arxiv.org/abs/1911.09339
- Tran, Pham, Luu, Nguyen. ViGoEmotions. EACL 2026. https://aclanthology.org/2026.eacl-long.129/
- Kajiwara et al. WRIME. NAACL 2021. https://aclanthology.org/2021.naacl-main.169/
- Jeon et al. KOTE. https://arxiv.org/abs/2205.05300
- Muhammad et al. BRIGHTER / SemEval-2025 Task 11. https://arxiv.org/abs/2502.11926 ; https://arxiv.org/abs/2503.07269

Bridge: text/speech/image/video ↔ music
- Won, Salamon, Bryan, Mysore, Serra. Emotion embedding spaces for matching music to stories. ISMIR 2021. https://arxiv.org/abs/2111.13468 ; code (MIT) https://github.com/minzwon/text2music-emotion-embedding
- Doh, Won, Choi, Nam. Textless speech-to-music retrieval using emotion similarity. ICASSP 2023. https://arxiv.org/abs/2303.10539
- Doh, Won, Choi, Nam. Toward universal text-to-music retrieval. ICASSP 2023. https://arxiv.org/abs/2211.14558
- Doh, Lee, Jeong, Nam. Enriching music descriptions with a finetuned-LLM and metadata (TTMR++). ICASSP 2024. https://arxiv.org/abs/2410.03264 ; https://github.com/seungheondoh/music-text-representation-pp
- Doh, Choi, Lee, Nam. LP-MusicCaps. ISMIR 2023. https://arxiv.org/abs/2307.16372
- Huang et al. MuLan. ISMIR 2022. https://archives.ismir.net/ismir2022/paper/000067.pdf
- Manco, Benetos, Quinton, Fazekas. MusCALL. ISMIR 2022. https://arxiv.org/abs/2208.12208
- Wu et al. CLaMP 3. Findings of ACL 2025. https://arxiv.org/abs/2502.10362 ; https://github.com/sanderwood/clamp3
- Clavié et al. IncompeBench. 2026. https://arxiv.org/abs/2602.11941
- Stewart, Avramidis, Feng, Narayanan. Emotion-aligned contrastive learning between images and music (Emo-CLIM). ICASSP 2024. https://arxiv.org/abs/2308.12610
- Choi, Kim, Kang. MMVA: multimodal matching based on valence and arousal. AAAI 2025 AI4Music workshop. https://arxiv.org/abs/2501.01094
- Stewart, KV, Lu, Fanelli. Semi-supervised contrastive learning for controllable video-to-music retrieval. ICASSP 2025. https://arxiv.org/abs/2412.05831
- Hong, Im, Yang. CBVMR. ICMR 2018.
- Prétet, Richard, Peeters. Cross-modal music-video recommendation: a study of design choices. IJCNN 2021.
- Surís, Vondrick, Russell, Salamon. It's time for artistic correspondence in music and video. CVPR 2022. https://arxiv.org/abs/2206.07148
- McKee, Salamon, Sivic, Russell. Language-guided music recommendation for video via prompt analogies. CVPR 2023.
- Thao, Roig, Herremans. EmoMV. Information Fusion 91, 2023. https://www.sciencedirect.com/science/article/abs/pii/S1566253522001725
- Dong et al. MuseChat. CVPR 2024. https://arxiv.org/abs/2310.06282
- Zhuo et al. Video background music generation (SymMV). ICCV 2023. https://arxiv.org/abs/2211.11248
- Kang, Poria, Herremans. Video2Music. Expert Systems with Applications 2024. https://arxiv.org/abs/2311.00968
- Pandeya & Lee. MVED (music video emotion dataset). https://zenodo.org/records/4542796
- Shriram, Tapaswi, Alluri. Sonus Texere! Automated dense soundtrack construction for books using movie adaptations. ISMIR 2022. https://arxiv.org/abs/2212.01033
- Padovani, Ferreira, Lelis. Bardo. AIIDE 2017. https://webdocs.cs.ualberta.ca/~santanad/papers/2017/padovaniFL17.pdf
- Ferreira, Lelis, Whitehead. Computer-generated music for tabletop role-playing games. AIIDE 2020. https://arxiv.org/abs/2008.07009
- Marra & Ferreira. Long-form text-to-music generation with adaptive prompts (Babel Bardo). LAMIR 2024. https://arxiv.org/abs/2411.03948
- Sharma, Haseeb, Xia, Tsuruoka. M2M-Gen. 2024. https://arxiv.org/abs/2410.09928
- Shokri et al. Story2MIDI. 2025. https://arxiv.org/abs/2512.02192
- Liu et al. WavJourney. https://arxiv.org/abs/2307.14335
- MM-StoryAgent. 2025. https://arxiv.org/abs/2503.05242
- Jamulkar & Hazra. BackgroundMellow. 2026. https://arxiv.org/abs/2607.11364
- Bae et al. Sound of Story. Findings of EMNLP 2023. https://arxiv.org/abs/2310.19264
- Plut & Pasquier. Generative music in video games. Entertainment Computing 33, 2020. https://doi.org/10.1016/j.entcom.2019.100337
- Plut, Pasquier, Ens, Tchemeube. PreGLAM-MMM. FDG 2022. https://dl.acm.org/doi/10.1145/3555858.3555947

Standards
- W3C. Emotion Markup Language (EmotionML) 1.0. Recommendation, 22 May 2014. https://www.w3.org/TR/emotionml/
- W3C. Vocabularies for EmotionML. Working Group Note, 1 April 2014. https://www.w3.org/TR/emotion-voc/

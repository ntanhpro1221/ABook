# B. The story side and the cross-modal bridge

How do we describe a story scene so it can be matched to background music, and how do we connect that description to a music library?

Scope: the text and scene side (emotion in text, emotion in fiction, scene segmentation and scene types), film and game music theory about what underscore does, cross-modal text/scene-to-music research, and a synthesis for ABook (Vietnamese translations of JP light novels and KR/CN web novels, read by TTS).

Citation policy: every work below was either checked against its publisher or arXiv page during this research, or is a long-standing standard reference (Ekman 1992, Russell 1980, Gorbman 1987, Chion 1994, Collins 2008). Numbers marked "(checked)" were read from the paper itself. Anything uncertain is flagged in the text.

---

## 0. Summary of conclusions

1. **No single emotion vocabulary is shared between text research and music research.** Won et al. (2021) showed that plain classification across mismatched vocabularies fails outright (P@5 = 0 when two datasets share no labels). Every working system uses a bridge: a hand-designed dimensional space (valence-arousal), a word-embedding space, a learned joint embedding, or recently an LLM that rewrites the scene as a music description.
2. **Valence + arousal is the most defensible shared core.** Tension (or suspense) is the best-supported third axis for *narrative* underscore. It appears in music psychology (Eerola & Vuoskoski 2011, "tension arousal"; IsoVAT, Plut et al. 2022), in adaptive game music (Prechtl 2016), and in narrative theory (suspense models: Doust & Piwek 2017; Wilmot & Keller 2020). Dominance (the D in VAD) has weak support on the music side.
3. **Affect alone is not enough.** The only published end-to-end audiobook soundtracking system (Chen et al., Interspeech 2022, Chinese web novels) used **12 plot categories that mix affect with narrative function**: warmth, happiness, romance, highlight, threat, sadness, injury, misunderstanding, conflict, positive background, negative background, neutral event. Film-music theory (Gorbman's "referential" cueing; Tagg's genre synecdoche) and a 2026 manga-BGM study (Action/Person/Place/Time/Weather tags) also argue for **setting/culture** as a separate axis.
4. **What text models can estimate reliably:** coarse valence is the most reliable. Coarse emotion groups are reasonable (GoEmotions BERT: F1 .46 on 27 classes, .64 on Ekman-6, .69 on 4-way sentiment; checked). Fine-grained emotions, writer/character perspective, intensity and suspense are much weaker. Human agreement on emotion in fiction is itself low (Alm et al. 2005: κ = .24-.51). Aggregating over a scene and smoothing over time is what makes arcs reliable (Reagan et al. 2016; Teodorescu & Mohammad 2023).
5. **Represent uncertainty as distributions.** Use a distribution over categories plus a mean and spread in VA(T), not a single argmax label. There is direct support for this: label distribution learning (Geng 2016), learning from disagreement (Uma et al. 2021), GoEmotions releasing all raters' labels, and WRIME/EmoBank separating perspectives.
6. **Congruence is the default; counterpoint is a deliberate exception.** Experiments show music *changes* how a scene is interpreted and remembered (Marshall & Cohen 1988; Boltz 2001; Herget 2021 review). A wrong track is therefore not neutral: it actively misleads. Chen et al. (2022) found their main gap to human soundtracking was **intensity**, not category.

---

## 1. Emotion in text: schemes, resources, reliability

### 1.1 Label schemes

| Scheme | Values | Origin / key reference | Notes for us |
|---|---|---|---|
| Ekman basic 6 | anger, disgust, fear, joy, sadness, surprise | Ekman 1992, *Cognition & Emotion* 6(3-4):169-200, doi:10.1080/02699939208411068 | Only one positive emotion. Poor fit for "calm", "warm" and "romantic" scenes, which are common in LN/web novels. |
| Plutchik wheel | 8 primaries (joy, trust, fear, surprise, sadness, disgust, anger, anticipation) × 3 intensities (e.g. serenity/joy/ecstasy; apprehension/fear/terror; pensiveness/sadness/grief), plus dyads (joy+trust = love, anticipation+joy = optimism, fear+surprise = awe, sadness+disgust = remorse, ...) | Plutchik 1980, *Emotion: A Psychoevolutionary Synthesis*; Plutchik 2001, *American Scientist* 89(4) | Built-in intensity and blends suit scene description. Used by NRC EmoLex and by the Japanese WRIME dataset. |
| Izard-extended 9 / Alm 5 | angry, fearful, happy, sad, surprised (+ variants) | Alm, Roth & Sproat 2005 (HLT/EMNLP), fairy tales | Earliest narrative emotion corpus. |
| GoEmotions | 27 emotions + neutral (admiration, amusement, anger, annoyance, approval, caring, confusion, curiosity, desire, disappointment, disapproval, disgust, embarrassment, excitement, fear, gratitude, grief, joy, love, nervousness, optimism, pride, realization, relief, remorse, sadness, surprise) | Demszky et al. 2020, ACL, arXiv:2005.00547 | Ships an official hierarchy to Ekman-6 and to 4-way sentiment. |
| Dimensional VA / VAD | valence, arousal (, dominance) | Russell 1980, *JPSP* 39(6); Mehrabian & Russell 1974 | The common currency with music research. |
| Korean KOTE | 43 emotions + no-emotion, derived by clustering Korean emotion words | Jeon et al., LREC-COLING 2024 (arXiv:2205.05300) | Shows that language-specific taxonomies differ from English ones. |
| Vietnamese UIT-VSMEC | enjoyment, sadness, anger, surprise, fear, disgust, other | Ho et al. 2019 (arXiv:1911.09339); 6,927 Facebook sentences, ~82% agreement (checked via search summary) | The only sizeable Vietnamese emotion corpus found. Social media, not fiction. |
| SemEval-2025 Task 11 | Ekman-6 multi-label + intensity 0-3 (none/low/moderate/high), 28+ languages | Muhammad et al. 2025 | Frames the task as *perceived* emotion, i.e. what most people think the speaker feels. |

### 1.2 Lexicons

| Resource | Content | Reliability (checked) | Reference |
|---|---|---|---|
| NRC EmoLex | ~14k English words × Plutchik 8 + pos/neg, binary | crowd-sourced, agreement reported per emotion | Mohammad & Turney 2013, *Computational Intelligence* 29(3) |
| NRC VAD v1 | 20k English words, real-valued V, A, D | split-half reliability V .95, A .90, D .90 | Mohammad 2018, ACL, aclanthology P18-1017 |
| NRC VAD v2 | 55,133 terms (44,928 unigrams + 10,205 multi-word expressions) | split-half r = .99 V, .98 A, .96 D | Mohammad 2025, arXiv:2503.23547 |
| EmoBank | 10k English sentences across genres, VAD from both **writer** and **reader** perspective; a subset also has categorical labels | reader perspective gives higher agreement | Buechel & Hahn 2017, EACL, aclanthology E17-2092 |
| WRIME | Japanese SNS posts, Plutchik 8 × intensity, rated by the **writer** and by 3 readers | readers cannot fully recover writer emotion, especially anger and trust | Kajiwara et al. 2021, NAACL, aclanthology 2021.naacl-main.169 |
| Chinese EmoBank | Chinese VA resources (words, phrases, sentences) | n/a | Lee et al., *ACM TALLIP* 2022, doi:10.1145/3489141 |

Lexicons give high word-level reliability, but word-level is not scene-level. Their real value for us is as a **calibration bridge**. Because the NRC VAD lexicon places emotion *words* in VA space, any categorical label (text side or music side) can be projected into VA. Won et al. 2021 did exactly this with NRC VAD.

### 1.3 Reliability numbers to keep in mind

- **GoEmotions** (checked from the paper): BERT macro F1 = .46 over 27+neutral, .64 after grouping to Ekman-6, .69 for the 4-way sentiment grouping. 94% of examples have at least two of three raters agreeing on at least one label. Per-emotion agreement (Appendix C, Table 7) ranges from about .10 (grief) to about .75 (gratitude), with a mean of about .3. The table has two columns (interrater correlation and Cohen's κ) that I could not cleanly separate in the extracted text, so treat these figures as approximate. Emotions with explicit lexical markers ("thanks", "lol") are reliable. Implicit ones (grief, nervousness) are not, and those are exactly the ones fiction relies on.
- **Fiction specifically:** Alm et al. 2005 report κ = .24-.51 between annotator pairs on fairy-tale sentences (45-64% raw overlap). REMAN (Kim & Klinger 2018, COLING) annotated 1,720 Gutenberg excerpts with emotion cues, experiencers, targets and causes, and found that agreement on emotion categories in literature is low. Their survey (below) stresses that literary emotion is often implied rather than stated.
- **Perspective matters.** EmoBank found the reader perspective more reliable than the writer's. WRIME found writer emotion hard to infer for readers and models. For fiction a third perspective appears: the **character's** emotion. A fourth, the **audience's** induced feeling (e.g. suspense), is what film music usually serves (see §3).
- **LLMs as annotators.** Niu et al. 2024 (Interspeech, arXiv:2408.17026) found that human judges *preferred* GPT-4's emotion labels over the original human labels in 62-71% of pairwise comparisons. They also found systematic differences from human perception. Treat LLM labels as a strong but biased annotator, not ground truth.

---

## 2. Emotion and structure in fiction

### 2.1 Surveys and arcs

- **Kim & Klinger 2019**, "A Survey on Sentiment and Emotion Analysis for Computational Literary Studies", *Zeitschrift für digitale Geisteswissenschaften*, doi:10.17175/2019_008 (arXiv:1808.03137). This is the standard map of the field. It classifies work into genre/story-type classification, emotional arcs, character-relation analysis and others, and repeatedly notes the lack of shared annotation schemes for literature.
- **Mohammad 2011**, "From Once Upon a Time to Happily Ever After: Tracking Emotions in Novels and Fairy Tales" (LaTeCH; arXiv:1309.5909). Builds EmoLex-based emotion density curves across a book.
- **Reagan et al. 2016**, "The emotional arcs of stories are dominated by six basic shapes", *EPJ Data Science* 5:31, doi:10.1140/epjds/s13688-016-0093-1. Sliding-window lexicon sentiment over 1,327 Gutenberg books yields six arcs: rags-to-riches (rise), riches-to-rags (fall), man-in-a-hole (fall-rise), Icarus (rise-fall), Cinderella (rise-fall-rise), Oedipus (fall-rise-fall). This is **valence only**, and the result depends on large windows; arcs are smooth because windows are large.
- **Kim, Padó & Klinger 2017** (LaTeCH-CLfL) relate emotional plot development to genre. **Kim & Klinger 2019** (Storytelling workshop, arXiv:1906.02402) study how fan fiction communicates emotion: through direct description, through characters' bodily reactions, and so on. This matters because LN prose leans heavily on bodily/indirect cues.
- **Teodorescu & Mohammad 2023**, "Evaluating Emotion Arcs Across Languages", Findings of EMNLP (aclanthology 2023.findings-emnlp.271). This systematically evaluates how arcs built from noisy per-instance predictions match gold arcs. The key practical finding: **arcs from simple methods become accurate once enough instances are aggregated per time step**, even when instance-level accuracy is mediocre. This also holds when the lexicon is translated into lower-resource languages. That is good news for Vietnamese.
- **Vishnubhotla, Hammond, Hirst & Mohammad 2024**, "The Emotion Dynamics of Literary Novels", Findings of ACL (2024.findings-acl.150). Separates narration from character dialogue and computes emotion dynamics (home base, variability, rise and recovery rates) per character.
- **Boyd, Blackburn & Pennebaker 2020**, "The narrative arc: Revealing core narrative structures through text analysis", *Science Advances*. Across about 40k narratives they find three function-word-based processes: **staging** (front-loaded), **plot progression** (rising) and **cognitive tension** (peaking near the climax). This is non-emotion evidence that tension is a measurable narrative axis.

### 2.2 Suspense and tension

| Work | Model of suspense / tension | What it outputs |
|---|---|---|
| Doust & Piwek 2017, INLG (aclanthology W17-3527) | Per narrative thread: **imminence, importance, foregroundedness, confidence** | sentence-level suspense prediction |
| Wilmot & Keller 2020, ACL, pp. 1763-1788 (2020.acl-main.161) | Compares **surprise** (backward-looking) with **uncertainty reduction** (forward-looking: how different the possible continuations are), computed over neural story representations. Evaluated against crowd suspense judgments on short stories. Uncertainty reduction tracks human suspense better. | sentence-level suspense curve |
| Lehne & Koelsch 2015, *Frontiers in Psychology* 6:79 | psychological model: tension/suspense from conflict, uncertainty and anticipation; same mechanism across music and narrative | theory |
| Boyd et al. 2020 | cognitive-tension word rate | chapter-level tension curve |

Suspense is an **audience-side** construct: what the reader feels about an uncertain outcome. It is **not** the emotion of a character. A hero can be calm while the reader is anxious. Film music typically scores the audience side (§3). Suspense is computable but noisy; no study found reports high agreement on fine-grained suspense.

### 2.3 Mood vs emotion vs atmosphere

- **Emotion** is brief, has an object, and is high-intensity. **Mood** is longer, diffuse, has no object, and is lower-intensity (Beedie, Terry & Lane 2005, *Cognition & Emotion* 19(6):847-878; Scherer 2005, *Social Science Information* 44(4)).
- For background music this distinction maps cleanly. **Underscore for a scene should track mood**, a scene-level, slowly varying state. Momentary character emotions are sentence-level and fast; if music tracked them it would change too often. Chen et al. (2022) reached the same conclusion empirically: paragraphs contain too little information to classify reliably, so they classify whole plots.
- **"Atmosphere"** (setting plus mood: rainy night town, festival, battlefield) has no standard computational scheme that I could find. Phenomenological aesthetics discusses atmospheres, but I found no annotation standard for them, so this is flagged as a gap. In practice it decomposes into *setting* (place, time, weather, era/culture) plus *mood*. That is exactly what the 2026 manga-BGM study tags (Action/Person/Place/Time/Weather; §4.3).

### 2.4 Scene segmentation

| Domain | Definition / method | Agreement / performance | Reference |
|---|---|---|---|
| Literary fiction | A **scene** is a span where story time ≈ discourse time, with one action, one location and a stable set of characters; boundaries where these change | γ = 0.70 (σ 0.07) between annotators on German dime novels; automatic detection is hard | Zehe et al. 2021, EACL, "Detecting Scenes in Fiction" (2021.eacl-main.276) |
| Chinese web novels (audiobook BGM) | **Plot**: continuous, sentimentally close segment depicting one event. Boundary when (1) a main role first appears or acts, (2) time or location changes, or (3) the atmosphere of events or the main role's emotion changes. Paragraph-level sequence labelling with BERT. | Acc-0 .26 / Acc-3 .51 (exact vs within-3-paragraphs boundary match), versus a no-context baseline at .16 / .33 (checked) | Chen et al. 2022, Interspeech |
| Film | Shot → scene grouping (MovieScenes / MovieNet) | n/a here | Rao et al. 2020 CVPR; Huang et al. 2020 ECCV (MovieNet) |

**For ABook:** the Chen et al. boundary criteria, which combine Zehe's place/time/character criteria with an affect-change criterion, are the right definition for *music* scenes. Their tolerance metric (within E paragraphs) is the right evaluation: a music change one paragraph late is acceptable, while a wrong mood is not.

### 2.5 Scene type / narrative function

No standard taxonomy of "scene types" exists in NLP. The evidence available:

| Source | Categories | Kind |
|---|---|---|
| Chen et al. 2022 (CN web novels, audiobook BGM) | warmth, happiness, romance, highlight (climax/"cool" moment), threat, sadness, injury, misunderstanding, conflict, positive background, negative background, neutral event | **mixed affect + narrative function**; translated from Chinese by the authors |
| Bardo (Padovani, Ferreira & Lelis 2017, AIIDE) | happy, calm, agitated, suspenseful | affect, chosen *for music selection* in tabletop RPG sessions |
| Labov & Waletzky 1967; Freytag | orientation / complicating action / evaluation / resolution / coda; exposition-rising-climax-falling-dénouement | structural position |
| MovieGraphs (Vicol et al. 2018, CVPR) | free-text "situation" labels per clip plus character emotions and relationships | situation |

The Chen et al. list is the most important empirical data point. Built by a production team for Chinese web novels (the closest genre to ours), it shows practitioners needed categories like **romance, highlight, misunderstanding, injury and background (pos/neg)**, which are not emotions. "Highlight" (爽点, the payoff moment in web novels) and "misunderstanding" (a comedy-of-errors staple of LN/rom-com) are genre-specific functions. The "background" classes mean "low-salience narration, play a quiet bed". Their classifier reached macro F1 ≈ .53 on 12 classes, against a .37 baseline (checked), which shows these categories are learnable but noisy.

---

## 3. What background music does: film and game theory

### 3.1 Film-music theory and evidence

| Theory / study | Claim | Implication for matching |
|---|---|---|
| **Gorbman 1987**, *Unheard Melodies: Narrative Film Music* (Indiana UP) | Classical underscore principles: (1) invisibility, (2) **inaudibility**: subordinate to dialogue and narrative, not consciously heard, (3) signifier of emotion, (4) **narrative cueing**, both *referential* (point of view, setting, characters) and *connotative* (interpreting events), (5) formal and rhythmic **continuity**, (6) **unity**, (7) any rule may be broken in service of the others | Music must sit *under* the voice. Two description axes (emotion and referential setting) plus a structural constraint (continuity, so no rapid switching). |
| **Cohen, Congruence-Association Model (CAM)**: Cohen 2001 (in Juslin & Sloboda, *Music and Emotion*); Cohen 2013, "Congruence-Association Model of music and multimedia: Origin and evolution", in Tan, Cohen, Lipscomb & Kendall (eds.), *The Psychology of Music in Multimedia*, OUP, pp. 17-47 | Two channels. (a) **Structural/temporal congruence** between music and other media steers *attention*. (b) **Associations** the music brings to mind are attached to whatever is attended. Later extended with a "working narrative" that integrates bottom-up input with top-down story inference. | In an audiobook the "visual" is the narrated text plus imagination. Congruence means **music changes aligned to scene boundaries and intensity peaks**; association means **music connotations become attributed to the scene**. |
| **Marshall & Cohen 1988**, *Music Perception* 6(1):95-112 | Different soundtracks changed viewers' judgments of the *same* animated geometric figures (activity, potency, evaluation) | Music writes meaning onto the scene. |
| **Boltz 2001**, *Music Perception* 18:427-454 (checked) | Ambiguous film clips with positive vs negative music: viewers' predicted endings, character judgments and later memory were biased in a mood-congruent way. Music acts as a schema. | A mismatched track is **not neutral**: it misleads the listener's interpretation of the story. |
| **Tan, Spackman & Bezdek 2007**, *Music Perception* 25(2) | Music placed before or after a character's appearance changes perceived character emotion | Timing of a change relative to a scene matters. |
| **Herget 2021**, "On music's potential to convey meaning in film: A systematic review of empirical evidence", *Psychology of Music* 49(1):21-49, doi:10.1177/0305735619835019 | 24 studies: music reliably shifts the perception of plot, characters and their relationships, going beyond simply adding emotion | Same as above, with stronger evidence. |
| **Ansani et al. 2020**, *Frontiers in Psychology*, doi:10.3389/fpsyg.2020.02242 | Soundtrack changes what viewers report seeing and their eye movements | Same. |
| **Chion 1994**, *Audio-Vision* | **Empathetic** music (mirrors the scene's feeling) vs **anempathetic** music (indifferent: a waltz continuing over violence), the latter intensifying by contrast | Counterpoint is a deliberate, authored effect, and rare. |
| **Tagg** (Tagg 1979 *Kojak*; Tagg & Clarida 2003 *Ten Little Title Tunes*; Tagg 2013 *Music's Meanings*) | **Musemes**: minimal units of musical meaning. Reception tests show listeners give highly shared verbal-visual associations to TV title tunes. **Genre synecdoche**: a style fragment evokes a whole place or culture (e.g. pentatonic plus erhu → "China") | Connotation is shared and learnable from tags/text. Setting/culture is conveyed by instrumentation/style, which supports a **setting axis**. |
| **Eerola & Vuoskoski 2011**, *Psychology of Music* 39(1):18-49 | 360 **film-music** excerpts rated by 116 listeners on discrete (anger, fear, sadness, happiness, tenderness) and 3-D (valence, energy arousal, **tension arousal**) scales. Dimensional ratings discriminated excerpts better. Two components (valence, arousal) explained 89.9% of variance in mean ratings. | For film music, VA captures most variance. Tension is distinguishable but correlated. **Tenderness** is a key category missing from Ekman-6. |

Audiobook-specific: Ji, Liu, Xu & Gong 2024 (*SAGE Open*, doi:10.1177/21582440241257357) model audiobook listening motivation and include BGM alongside narrator performance and telepresence. This is evidence that listeners register BGM as part of immersion. I did not find controlled experiments on BGM *congruence* in audiobooks specifically. The film evidence has to be transferred, which is a gap.

### 3.2 Congruence vs counterpoint: a disagreement

- Most of the empirical literature (Boltz; Marshall & Cohen; Herget's review) measures **mood-congruent** effects, and treats incongruent pairings as a manipulation that changes interpretation.
- Film theory (Chion, Eisenstein's "audiovisual counterpoint") values deliberate incongruence as art.
- **For an automatic system** the asymmetry is clear. Correct counterpoint requires authorial intent the system cannot verify, while wrong "counterpoint" is just an error that misleads the listener (Boltz). Default to congruence. Allow **"lighter than the scene"** (e.g. a quiet, sparse bed under heavy narration) as a safe fallback. That is Gorbman's inaudibility principle, not counterpoint.

### 3.3 Game and adaptive music: which axes real systems vary

| System / source | Input axes | Musical controls |
|---|---|---|
| Industry practice: Collins 2008, *Game Sound* (MIT Press); Sweet 2014, *Writing Interactive Music for Video Games* | game state (explore / combat / stealth / boss), **intensity level**, location/biome, player health/danger | **horizontal re-sequencing** (switch or branch segments at musical boundaries), **vertical remixing / layering** (add or drop stems as intensity rises), stingers, transition segments |
| Williams, Kirke, Eaton, Miranda et al. 2015, AES 56th Conf. "Dynamic game soundtrack generation in response to a continuously varying emotional trajectory" | **valence, arousal** trajectory (circumplex) | 5 musical parameters via a 2nd-order Markov model |
| Prechtl 2016, PhD thesis, Open University, "Adaptive Music Generation for Computer Games" | **tension** (plus valence-related features) | dissonance, tempo, chord transition matrix; tested in the horror game *Escape Point*, where dynamic music was rated most tense and exciting |
| Scirea et al. (MetaCompose, 2016-2017) | valence, arousal | evolutionary composition |
| Ferreira & Whitehead 2019, ISMIR, "Learning to generate music with sentiment" (VGMIDI dataset) | valence (positive/negative) | LSTM + sentiment neuron |
| Padovani, Ferreira & Lelis 2017, AIIDE, **Bardo** | speech → text → 4 classes: happy, calm, agitated, suspenseful | **selects** a track from a library labelled with the same 4 classes |
| Ferreira, Lelis & Whitehead 2020, AIIDE, Bardo Composer | story emotion from players' speech | **generates** music matching the story emotion |
| Plut, Pasquier, Ens & Tchemeris 2022, **IsoVAT** corpus, *TISMIR*, doi:10.5334/tismir.120 | **valence, arousal, tension** (VAT) | 90 four-bar clips that isolate each dimension; a guide mapping musical features to V, A and T |
| Plut & Pasquier 2020, *Entertainment Computing* 33:100337 | review and taxonomy of generative game music | n/a |

**Pattern.** Systems that *must* run automatically converge on 2-3 continuous axes (valence, arousal, tension/intensity) plus a discrete *state/context* (combat, explore, location). Commercial practice treats **intensity** as the main continuous control (layers) and **state** as the selector (which cue). For an audiobook this suggests:

- **Scene category** selects the cue family.
- **Intensity/tension** selects the layer, version or volume within it.
- Changes snap to scene boundaries (horizontal re-sequencing) rather than happening mid-sentence.

Bardo is the closest analogue to ABook: text in, *library selection* out. Its designers deliberately chose a tiny, music-oriented vocabulary (4 classes) instead of a psychology vocabulary.

---

## 4. Cross-modal text/scene → music research

### 4.1 Systems for stories, books and comics

| Work | Input | Shared representation | Music side | Evaluation |
|---|---|---|---|---|
| **Won, Salamon, Bryan, Mysore & Serra 2021**, "Emotion Embedding Spaces for Matching Music to Stories", ISMIR (best student paper), arXiv:2111.13468 | Story sentences (Alm fairy tales: 5 emotions; ISEAR: 7 emotions) | Compared: classification; **VA regression** (labels → VA via NRC VAD); Word2Vec regression; 2-branch and **3-branch metric learning** (text, music, tag) | AudioSet mood subset (16,995 clips; happy, funny, sad, tender, exciting, angry, scary) | macro P@5 and MRR, scored through three vocabulary mappings (VA distance, W2V distance, manual). Checked: classification **fails** (Alm and AudioSet share only happy and sad; ISEAR and AudioSet share nothing, so 0). VA regression scores well where a manual tag-to-VA mapping exists. 3-branch metric learning is best overall and data-driven, e.g. Alm/manual mapping: P@5 .61, MRR .74. |
| **Chen, Wu, Pan & Yin 2022**, "An Automatic Soundtracking System for Text-to-Speech Audiobooks", Interspeech (ByteDance) | Chinese web-novel chapters (5,000 chapters; 23k+ plots annotated by two annotators plus a specialist) | **12 plot categories** (see §2.5) | in-house *generated* BGM library labelled by the same categories and by duration; heuristic: plots shorter than 80 characters get no music, longer plots concatenate pieces, with fade/trim/loop | 40 raters, 80 chapters, 1-5 scale. "Qualified" (≥3): model 88.75% = human-labelled 88.75%, baseline 63.75%. "Excellent" (≥4): model 45.0%, human 52.5%, baseline 23.75% (checked). The authors attribute the gap to **emotional intensity**. |
| Lobo et al. 2021, AIMV, "Emotionally relevant background music generation for audiobooks" (IEEE 9670959) | audiobook text | hybrid emotion model → emotion label | generated music | small-scale; details not verified beyond the abstract |
| **Bae et al. 2023**, "Sound of Story", Findings of EMNLP (arXiv:2310.19264) | image + text story sequences from movies (CMD, LSMDC) | learned retrieval embeddings | 984 h of speech-removed background audio (music + sound), 27,354 stories | cross-modal retrieval, audio generation |
| **Sharma, Haseeb, Xia & Tsuruoka 2024**, M2M-Gen (arXiv:2410.09928) | **Japanese manga**: scene boundaries from dialogue, emotion from faces | GPT-4o writes a "music directive", then page-level music captions | text-to-music generation | subjective evaluation |
| **Takarada & Hayashi 2026** (Nihon Univ., supervisor T. Kitahara), BGM for a manga viewer (zenodo 18427178; Japanese student thesis, not peer-reviewed) | manga pages → LLM | scene tags: **Action, Person, Place, Time, Weather** | existing BGM library | boundaries judged appropriate 61.5%; tag validity 2.32/4; BGM chosen over random 67.2% |
| Shokri et al. 2025, Story2MIDI (arXiv:2512.02192) | text | paired text-emotion and music-emotion data | symbolic generation | listening study, small scale |

### 4.2 General text ↔ music joint embeddings (music side of the bridge)

- **MuLan** (Huang et al. 2022, ISMIR): audio-text joint embedding trained on noisy web text.
- **CLAP** (Elizalde et al. 2023, ICASSP; LAION-CLAP, Wu et al. 2023, ICASSP): contrastive audio-language pretraining.
- **TTMR** (Doh, Won, Choi & Nam 2023, ICASSP, "Toward Universal Text-to-Music Retrieval"): handles tag queries *and* sentence queries in one space. This matters because scene descriptions are sentences while libraries have tags.
- **CLaMP 2 / CLaMP 3** (Wu et al. 2024 and 2025, arXiv:2410.13267, arXiv:2502.10362): music-text retrieval across about 100 languages, including unseen ones. Relevant because our scene text is Vietnamese. Whether Vietnamese retrieval quality holds up is **not verified**.

These spaces encode *genre, instrument and mood words* well. They do **not** encode narrative function ("misunderstanding", "highlight") unless that is phrased as a musical description. That is why the LLM-as-translator pattern (M2M-Gen, the manga viewer study, FilmComposer arXiv:2503.08147) has emerged: text scene → LLM → *music caption* → text-to-music retrieval or generation.

### 4.3 Video → music (closest large-scale analogue)

| Dataset / work | Content | Representation |
|---|---|---|
| YT8M-MusicVideo; **McKee, Salamon, Sivic & Russell 2023**, CVPR (ViML; YouTube8M-MusicTextClips, 4k clips with music descriptions) | video + optional free text → music | joint embedding. Text descriptions synthesised by an LLM from tagger outputs (analogy prompting) |
| **Di et al. 2021**, ACM MM, Controllable Music Transformer (V2M line) | video rhythm features (motion speed, saliency, timing) | rhythm/structure, *not* emotion |
| **Zhuo et al. 2023**, ICCV, **SymMV** | 1,181 video-music pairs, 78.9 h, chord/melody annotations | generation; new metric VMCP (Video-Music CLIP Precision) |
| **Kang, Poria & Herremans 2024**, *Expert Systems with Applications* 249, Video2Music / **MuVi-Sync** | music videos with emotion, scene-offset and motion features | affective multimodal transformer (explicit affect-matching loss) + user study |
| **Pandeya & Lee 2021**, MVED | music videos, 6 emotion classes | classification |
| EmoMV (2022, *Information Fusion*) | music-video affective correspondence | retrieval |
| Hung et al. 2021, **EMOPIA**, ISMIR | 1,087 piano clips, including **Japanese anime** covers, labelled with 4 VA quadrants | music-side emotion with anime content |

**On anime/LN-specific work:** I found **no** peer-reviewed study of background-music matching for light novels or web novels, and none for Korean webtoon BGM (Korean webtoons do ship BGM commercially). The closest Asian-content works are Chen et al. 2022 (Chinese web novels), M2M-Gen (Japanese manga), the Nihon University manga-viewer thesis (2026), and EMOPIA (anime piano covers on the music side).

### 4.4 How matching is evaluated

| Metric type | Examples | Weakness |
|---|---|---|
| Retrieval with label proxies | P@k, MRR, Recall@k, computed through a vocabulary mapping (Won 2021) | Measures only label agreement, not suitability. Depends on the mapping. |
| Embedding similarity | VMCP (SymMV), CLAP score | Circular when the same encoder is used for retrieval. |
| Human absolute rating | 1-5 scale, "qualified rate" (≥3) and "excellent rate" (≥4) (Chen 2022) | Cost. Chen's split between qualified and excellent is useful: it separates "not wrong" from "good". |
| Human pairwise preference | system vs random, or system vs system (manga thesis: 67.2% vs random; Niu 2024 for labels) | Most sensitive. Recommended for ABook A/B tests. |

---

## 5. Synthesis for ABook

### 5.1 Recommended scene descriptor

Each axis below is supported by at least two independent lines of evidence.

| Axis | Values / type | Evidence | Text-side estimability |
|---|---|---|---|
| **Valence** | continuous [-1, 1], stored as mean ± sd | Russell; NRC VAD; Eerola & Vuoskoski (music); Reagan (arcs); Won 2021 (best manual bridge) | **High** at scene level, especially aggregated (Teodorescu & Mohammad 2023) |
| **Arousal / energy** | continuous [0, 1] | same, plus every game system | **Medium**: text arousal is less reliable than valence (lexicon split-half .90 vs .95; EmoBank) |
| **Tension / suspense** | continuous [0, 1], *audience-side* | Eerola tension-arousal; IsoVAT; Prechtl; Doust & Piwek; Wilmot & Keller; Boyd et al. cognitive tension; game intensity layers | **Low-medium**: computable, but no high-agreement benchmark. Estimate relative to the book's own baseline (z-score per book). |
| **Scene function / category** | distribution over ~10-14 classes | Chen et al. 12 classes; Bardo 4 classes; film situations | **Medium** (Chen: macro F1 .53 on 12 classes); LLM zero-shot likely comparable or better (unverified for Vietnamese) |
| **Setting / culture / era** | tags: era (modern / medieval-fantasy / ancient-CN wuxia / xianxia / sci-fi), place (school, city, palace, wilderness, dungeon), time of day, weather | Gorbman referential cueing; Tagg genre synecdoche; manga BGM thesis (Place/Time/Weather); Chen's "background" classes | **High** for era/genre (book-level, mostly constant); medium for place and time |
| **Salience / foreground-ness** | {background narration, normal, highlight/climax} | Gorbman inaudibility; Chen "positive/negative background" vs "highlight"; game layers | Medium. Correlates with tension and position in the chapter. |

Proposed category set, adapted from Chen et al. 2022 plus Bardo, with the music-psychology category **tenderness** added (Eerola & Vuoskoski):
`daily/calm`, `warm/tender`, `happy/comedic`, `romance`, `misunderstanding/awkward-comedy`, `mystery/eerie`, `suspense/threat`, `battle/action`, `highlight/triumph`, `sad/loss`, `injury/despair`, `conflict/argument`, `solemn/ceremonial`, `neutral-background`.
This is a **proposal**, not an established standard. No published taxonomy covers LN/web-novel scenes beyond Chen's 12.

### 5.2 Representing uncertainty and mixtures

- Store a **distribution** over categories, not an argmax. This is supported by label distribution learning (Geng 2016, *IEEE TKDE* 28(7)), emotion distribution learning from text (Zhou et al. 2016, EMNLP), and learning from disagreement (Uma et al. 2021, *JAIR* 72:1385-1470, doi:10.1613/jair.1.12752). GoEmotions released all raters' labels for this reason.
- For VA(T), store a **mean and spread**. Spread comes from disagreement across sentences in the scene, across multiple LLM samples, or across annotators.
- **Mixtures are real in fiction.** A bittersweet farewell is high-valence and sad at once. Plutchik's dyads model this explicitly. With a distribution, a 0.5 `sad` / 0.4 `warm` scene can match a "bittersweet" track whose music-side distribution overlaps both. With an argmax it would get a purely sad track.
- **Decision rule under uncertainty:** when the category distribution is flat (high entropy) or VA spread is large, choose a **low-salience, low-arousal, neutral-valence** bed, or no music. This follows Gorbman's inaudibility principle and Chen's choice to leave very short plots unscored. Given Boltz's results, a confidently wrong track is worse than a modest one.
- **Perspective:** label *reader/audience-perceived scene mood*, not character emotion. Reader-perspective labels are more reliable (EmoBank), and film music serves the audience (suspense while the hero is calm). Character emotion (which the app already tracks for TTS) is a useful *feature*, not the target.

### 5.3 Mapping text-side labels to music-side labels

| Strategy | How | Pros | Cons | Evidence |
|---|---|---|---|---|
| A. Shared hand-designed space (VA or VAT) | Project both sides into VA(T). Text via classifier or LLM. Music via MER model or tags mapped through NRC VAD. | Interpretable, tunable, needs no paired data | VA cannot tell `romance` from `happy`, or `battle` from `fear` (both high arousal), and ignores setting | Won 2021: strong where a manual mapping exists; Eerola: 2 dimensions carry about 90% of music-emotion variance |
| B. Shared discrete vocabulary with a manual mapping table | Same category set on both sides; tag the library by hand or with an LLM | Simple; works with a small curated library (Bardo, Chen) | Vocabulary mismatch with public music datasets; brittle | Bardo; Chen 2022 (generated library labelled by category) |
| C. Learned joint embedding | Metric learning (Won 3-branch), CLAP/TTMR/CLaMP | Data-driven, handles new words | Needs paired data, which does not exist for LN scenes; general encoders lack narrative-function knowledge | Won 2021: best; McKee 2023 |
| D. LLM as translator | Scene text → LLM → music description (mood, tempo, instruments, setting) → text-to-music retrieval over the library | Captures setting and function; zero-shot; multilingual | Inherits LLM bias; hard to evaluate without humans | M2M-Gen 2024; manga thesis 2026; FilmComposer 2025 |

**Recommendation (a design inference, not a proven result):**

1. **Use a hybrid.** A discrete scene category (B) with a setting tag selects the candidate set.
2. **Rank within that set by VA(T) distance (A).** Tension or intensity picks the layer or version.
3. **Use the LLM description and text-music embedding (D + C) as a tie-breaker** and for open-vocabulary setting cues.
4. **Keep the music-side labels on the same axes**, so the matching is symmetric and auditable.

This mirrors the game-industry split: state selects the cue, intensity selects the layer. It also isolates the axes text models estimate poorly (tension, fine emotion) from those they estimate well (valence, coarse category, setting).

### 5.4 Disagreements and open questions

1. **Discrete vs dimensional.** Music psychology (Eerola & Vuoskoski 2011) finds dimensions more discriminative. NLP practice (GoEmotions, KOTE) moves toward *more* categories. Production systems (Chen, Bardo) use small *task-specific* category sets. My reading: they answer different questions, so use both (§5.3).
2. **Is tension a third axis or just arousal?** Eerola's PCA folds most variance into two components; IsoVAT, Prechtl and game practice keep tension separate. For narrative scoring, tension (anticipation of an uncertain outcome) differs from arousal (energy): quiet dread is low arousal and high tension. Keep it, but expect it to be the noisiest text estimate.
3. **Dominance** is in the NRC VAD lexicon but has little use on the music side. I recommend dropping it.
4. **Granularity.** Character emotion changes per sentence; music should change per scene. Chen et al. found paragraph-level sentiment too unreliable and classified whole plots. The theory (Gorbman's continuity) agrees.
5. **Congruence vs counterpoint.** See §3.2. Default to congruence; fall back to low salience, never to "creative" contrast.
6. **Cross-cultural transfer.** Taxonomies differ by language (KOTE's 43 Korean categories; WRIME's writer/reader gap in Japanese), and genre conventions differ ("highlight" in CN web novels, "misunderstanding" in JP rom-com LN). Our text is a *Vietnamese translation*, and the only Vietnamese emotion corpus (UIT-VSMEC) is social media. Expect domain shift; evaluate on our own books.
7. **Missing evidence.** There are no controlled listening studies of BGM congruence in audiobooks (as opposed to film), and no LN/web-novel scene taxonomy beyond Chen 2022. ABook's own owner ratings would be original data.

### 5.5 What to measure in ABook (evaluation design borrowed from the literature)

- **Scene boundaries:** Acc-E within ±1-2 paragraphs (Chen 2022), or γ against a hand-segmented chapter (Zehe 2021).
- **Scene labels:** agreement of the LLM with the owner on a small gold set. Report per-axis agreement (valence vs category vs tension) separately, since they differ widely in reliability.
- **End-to-end matching:** pairwise preference (system vs random, system vs simpler variant) plus Chen-style "qualified" (≥3/5) and "excellent" (≥4/5) rates. Track intensity mismatches separately, since that was Chen's main failure mode.

---

## References (verified in this session unless marked)

- Alm, C. O., Roth, D., & Sproat, R. (2005). Emotions from text: machine learning for text-based emotion prediction. HLT/EMNLP. https://aclanthology.org/H05-1073
- Ansani, A., et al. (2020). How soundtracks shape what we see. *Frontiers in Psychology*. doi:10.3389/fpsyg.2020.02242
- Bae, J., et al. (2023). Sound of Story: Multi-modal Storytelling with Audio. Findings of EMNLP. https://aclanthology.org/2023.findings-emnlp.898
- Beedie, C., Terry, P., & Lane, A. (2005). Distinctions between emotion and mood. *Cognition & Emotion* 19(6):847-878. (standard reference, not re-checked)
- Boltz, M. G. (2001). Musical soundtracks as a schematic influence on the cognitive processing of filmed events. *Music Perception* 18:427-454.
- Boyd, R. L., Blackburn, K. G., & Pennebaker, J. W. (2020). The narrative arc: Revealing core narrative structures through text analysis. *Science Advances*.
- Buechel, S., & Hahn, U. (2017). EmoBank. EACL. https://aclanthology.org/E17-2092
- Chen, Z., Wu, L., Pan, J., & Yin, X. (2022). An Automatic Soundtracking System for Text-to-Speech Audiobooks. Interspeech. https://www.isca-archive.org/interspeech_2022/chen22j_interspeech.html
- Chion, M. (1994). *Audio-Vision: Sound on Screen*. Columbia UP. (standard)
- Cohen, A. J. (2013). Congruence-Association Model of music and multimedia: Origin and evolution. In Tan, Cohen, Lipscomb & Kendall (eds.), *The Psychology of Music in Multimedia*, OUP, 17-47.
- Collins, K. (2008). *Game Sound*. MIT Press. (standard)
- Demszky, D., et al. (2020). GoEmotions. ACL. arXiv:2005.00547
- Di, S., et al. (2021). Video background music generation with controllable music transformer. ACM MM. (not re-checked)
- Doh, S., Won, M., Choi, K., & Nam, J. (2023). Toward Universal Text-to-Music Retrieval. ICASSP.
- Doust, R., & Piwek, P. (2017). A model of suspense for narrative generation. INLG. https://aclanthology.org/W17-3527
- Eerola, T., & Vuoskoski, J. K. (2011). A comparison of the discrete and dimensional models of emotion in music. *Psychology of Music* 39(1):18-49.
- Ekman, P. (1992). An argument for basic emotions. *Cognition & Emotion* 6(3-4):169-200.
- Ferreira, L., & Whitehead, J. (2019). Learning to generate music with sentiment. ISMIR.
- Ferreira, L., Lelis, L., & Whitehead, J. (2020). Computer-generated music for tabletop role-playing games. AIIDE.
- Geng, X. (2016). Label distribution learning. *IEEE TKDE* 28(7). (standard, not re-checked)
- Gorbman, C. (1987). *Unheard Melodies: Narrative Film Music*. Indiana UP. (standard)
- Herget, A.-K. (2021). On music's potential to convey meaning in film. *Psychology of Music* 49(1):21-49. doi:10.1177/0305735619835019
- Ho, V. A., et al. (2019). Emotion Recognition for Vietnamese Social Media Text (UIT-VSMEC). arXiv:1911.09339
- Huang, Q., et al. (2022). MuLan. ISMIR.
- Hung, H.-T., et al. (2021). EMOPIA. ISMIR. arXiv:2108.01374
- Jeon, D., et al. (2024). User Guide for KOTE. LREC-COLING. https://aclanthology.org/2024.lrec-main.1499
- Ji, D., Liu, B., Xu, J., & Gong, J. (2024). Why do we listen to audiobooks? *SAGE Open*. doi:10.1177/21582440241257357
- Kajiwara, T., et al. (2021). WRIME. NAACL. https://aclanthology.org/2021.naacl-main.169
- Kang, J., Poria, S., & Herremans, D. (2024). Video2Music. *Expert Systems with Applications* 249. arXiv:2311.00968
- Kim, E., & Klinger, R. (2018). Who Feels What and Why? (REMAN). COLING. https://aclanthology.org/C18-1114
- Kim, E., & Klinger, R. (2019). A Survey on Sentiment and Emotion Analysis for Computational Literary Studies. *ZfdG*. doi:10.17175/2019_008
- Kim, E., & Klinger, R. (2019). An Analysis of Emotion Communication Channels in Fan Fiction. arXiv:1906.02402
- Lehne, M., & Koelsch, S. (2015). Toward a general psychological model of tension and suspense. *Frontiers in Psychology* 6:79. (not re-checked)
- Lobo, D., et al. (2021). Emotionally relevant background music generation for audiobooks. AIMV. IEEE 9670959
- Marshall, S. K., & Cohen, A. J. (1988). Effects of musical soundtracks on attitudes toward animated geometric figures. *Music Perception* 6(1). (standard)
- McKee, D., Salamon, J., Sivic, J., & Russell, B. (2023). Language-Guided Music Recommendation for Video via Prompt Analogies. CVPR.
- Mohammad, S. (2011). From Once Upon a Time to Happily Ever After. LaTeCH. arXiv:1309.5909
- Mohammad, S. (2018). Obtaining reliable human ratings of valence, arousal, and dominance for 20,000 English words. ACL. https://aclanthology.org/P18-1017
- Mohammad, S. (2025). NRC VAD Lexicon v2. arXiv:2503.23547
- Mohammad, S., & Turney, P. (2013). Crowdsourcing a word-emotion association lexicon. *Computational Intelligence* 29(3). (standard)
- Muhammad, S. H., et al. (2025). SemEval-2025 Task 11: Bridging the Gap in Text-Based Emotion Detection.
- Niu, M., et al. (2024). From Text to Emotion: Unveiling the Emotion Annotation Capabilities of LLMs. Interspeech. arXiv:2408.17026
- Padovani, R., Ferreira, L., & Lelis, L. (2017). Bardo: Emotion-Based Music Recommendation for Tabletop Role-Playing Games. AIIDE. https://ojs.aaai.org/index.php/AIIDE/article/view/12958
- Pandeya, Y. R., & Lee, J. (2021). Deep learning-based late fusion of multimodal information for emotion classification of music video (MVED). *Multimedia Tools and Applications*.
- Plut, C., & Pasquier, P. (2020). Generative music in video games. *Entertainment Computing* 33:100337.
- Plut, C., Pasquier, P., et al. (2022). The IsoVAT Corpus. *TISMIR*. doi:10.5334/tismir.120
- Plutchik, R. (1980). *Emotion: A Psychoevolutionary Synthesis*. Harper & Row. (standard)
- Prechtl, A. (2016). *Adaptive Music Generation for Computer Games*. PhD thesis, Open University. https://oro.open.ac.uk/45340/
- Reagan, A. J., et al. (2016). The emotional arcs of stories are dominated by six basic shapes. *EPJ Data Science* 5:31. doi:10.1140/epjds/s13688-016-0093-1
- Russell, J. A. (1980). A circumplex model of affect. *JPSP* 39(6):1161-1178. (standard)
- Sharma, M., Haseeb, M. T., Xia, G., & Tsuruoka, Y. (2024). M2M-Gen. arXiv:2410.09928
- Shokri, M., et al. (2025). Story2MIDI. arXiv:2512.02192
- Sweet, M. (2014). *Writing Interactive Music for Video Games*. Addison-Wesley. (standard)
- Tagg, P., & Clarida, B. (2003). *Ten Little Title Tunes*. MMMSP. (standard)
- Takarada, R., & Hayashi, R. (2026). BGM付き漫画ビューアのための音楽推薦システムに関する研究. Nihon University thesis. https://zenodo.org/records/18427178
- Tan, S.-L., Spackman, M. P., & Bezdek, M. A. (2007). Viewers' interpretations of film characters' emotions. *Music Perception* 25(2). (not re-checked)
- Teodorescu, D., & Mohammad, S. (2023). Evaluating Emotion Arcs Across Languages. Findings of EMNLP. https://aclanthology.org/2023.findings-emnlp.271
- Uma, A., Fornaciari, T., Hovy, D., Paun, S., Plank, B., & Poesio, M. (2021). Learning from Disagreement: A Survey. *JAIR* 72:1385-1470. doi:10.1613/jair.1.12752
- Vicol, P., Tapaswi, M., Castrejon, L., & Fidler, S. (2018). MovieGraphs. CVPR. (standard)
- Vishnubhotla, K., et al. (2024). The Emotion Dynamics of Literary Novels. Findings of ACL. https://aclanthology.org/2024.findings-acl.150
- Williams, D., Kirke, A., et al. (2015). Dynamic game soundtrack generation in response to a continuously varying emotional trajectory. AES 56th Int. Conf. https://centaur.reading.ac.uk/40605/
- Wilmot, D., & Keller, F. (2020). Modelling Suspense in Short Stories as Uncertainty Reduction over Neural Representation. ACL. https://aclanthology.org/2020.acl-main.161
- Won, M., Salamon, J., Bryan, N. J., Mysore, G. J., & Serra, X. (2021). Emotion Embedding Spaces for Matching Music to Stories. ISMIR. arXiv:2111.13468
- Wu, S., et al. (2025). CLaMP 3. arXiv:2502.10362
- Zehe, A., et al. (2021). Detecting Scenes in Fiction: A new Segmentation Task. EACL. https://aclanthology.org/2021.eacl-main.276
- Zhou, D., et al. (2016). Emotion distribution learning from texts. EMNLP. (not re-checked)
- Zhuo, L., et al. (2023). Video Background Music Generation: Dataset, Method and Evaluation (SymMV). ICCV. arXiv:2211.11248

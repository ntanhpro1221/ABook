# A. Psychology of music and emotion, and how MER turns it into data

Scope: the affective representations available for describing (a) a story scene and (b) a music track
in one shared space, so that background music can be retrieved per scene. Written 2026-10-02.

**About the evidence.** Every citation below is to a real publication. Items marked **[verified]** were
checked against the paper, its abstract, or the dataset page during this research. Items marked
**[from memory]** are standard textbook facts that I did not re-open this session. Numbers marked
**[approx.]** should be checked before anyone relies on the exact digits. Where I could not confirm
something, the text says so.

---

## 0. Executive summary

1. **No single model "wins" for music.** The evidence supports a **hybrid**: a few continuous core-affect
   dimensions, plus a music-specific set of categories, each scored independently.
   - On the dimensional side, valence and arousal carry most of the variance. In Eerola & Vuoskoski (2011)
     and Vuoskoski & Eerola (2011), two principal components explained about 90% of the variance across
     *all* scales of *all* models **[verified]**.
   - On the categorical side, specific feeling categories ("triumphant", "scary", "amusing") are **more stable
     across cultures than valence/arousal levels** (Cowen et al., 2020 **[verified]**). Bottom-up taxonomies
     also find that VA under-describes what music expresses (Eerola & Saari, 2025 **[verified]**).
2. **Arousal is the most reliable axis. Valence is the least reliable of the core axes.**
   - Human agreement: DEAM Cronbach α was 0.75 for arousal vs 0.65 for valence **[verified]**.
   - Machine prediction: the meta-analysis of 2014–2024 MER studies found r ≈ 0.81 for arousal vs 0.67 for
     valence (Eerola & Anderson, 2026 **[verified]**).
   - Tension is highly agreed for film-type music (GEMS tension α = .98 in Vuoskoski & Eerola, 2011
     **[verified]**). It is also what a narrative soundtrack most needs (Lehne & Koelsch, 2015).
3. **GEMS-9 is good but not sufficient for a soundtrack.**
   - It was built for *induced, aesthetic* emotion in listeners. It therefore lacks **fear/horror,
     anger/aggression, humour/comic, and mystery**, which story scenes need constantly.
   - Two of its factors (**wonder, transcendence**) have the *lowest* rater consistency of any scale tested
     (α ≈ .64/.67) **[verified]**.
   - Its extension GEMIAC (Coutinho & Scherer, 2017) adds 5 classes **[verified]**: *moved, inspired,
     energetic, bored, agitated/aggressive*.
4. **For background music, describe the emotion the music *expresses* (perceived), not the one it *induces*.**
   - What matters is the music's fit with, and its colouring of, the scene's meaning. Induced ratings are
     contaminated by liking, mood and memory (Aljanaki et al., 2016), and they systematically *under-report*
     negative emotions.
   - Felt intensity is usually lower than expressed intensity (Schubert, 2013 review **[verified]**).
   - Keep the scene side "expressed/portrayed" too, so both sides live in the same "expressed" space.
5. **Store scores as independent intensities in [0,1] (multi-label), not one categorical distribution that
   must sum to 1.** Then derive a normalised distribution only for similarity.
   - Music legitimately expresses mixed emotions (Hunter et al., 2008; Larsen & Stastny, 2011).
   - Being moved and nostalgia are mixed by nature (Menninghaus et al., 2015; Barrett et al., 2010).
   - Keep uncertainty (SD or the annotator count) with each score, following Yang & Chen (2011) and the
     Acoustic Emotion Gaussians (AEG) approach (Wang et al., 2012).

---

## 1. General emotion models and what they mean for music

### 1.1 Overview table

| Family | Key sources | Claim | Axes / values | Measured by | Main criticisms | Relevance to music |
|---|---|---|---|---|---|---|
| **Basic/discrete** | Ekman 1992; Izard 1977, 2007 | A small set of biologically based, universal emotions with distinct signals | Ekman: happiness, sadness, anger, fear, disgust, surprise. Izard: ~10 incl. interest, shame, contempt | Forced choice or per-category Likert intensity | Weak evidence for "fingerprints" (Barrett 2006); depends on language; can't express mixtures or ambiguity | Music conveys **happy/sad/anger/fear/tenderness** reliably (Juslin & Laukka 2003 meta-analysis). Disgust/surprise barely apply. Juslin's music variant swaps disgust for **tenderness** |
| **Circumplex (2-D)** | Russell 1980; Russell 2003 ("core affect") | All affect lies on two bipolar axes in a circle | Valence (unpleasant↔pleasant), arousal (deactivated↔activated) | Two Likert/slider scales, the Affect Grid, continuous 2-D joystick | Merges energy with tension (fear and excitement both "high arousal"); valence is ambiguous for music (sad music can be "pleasant") | De-facto MER standard (DEAM, PMEmo, AMG1608, MoodSwings). Quadrants give the "4Q" labels |
| **PAD (3-D)** | Mehrabian & Russell 1974 | Pleasure, arousal, dominance | Each bipolar, often −1..+1 | Semantic differential (18 adjective pairs) or SAM pictograms | Dominance is poorly understood and unreliable for music, so most MER datasets drop it (Kang & Herremans 2024 survey) | MuSe derives V/A/D from tags. A "power"-like third dimension does recur in music (Bigand et al. 2005: third MDS dimension) **[from memory]** |
| **Energy–tension (2-D)** | Thayer 1989 | Two *arousal* systems | Energetic arousal (tired↔energetic), tense arousal (calm↔tense) | Adjective checklists | Valence is only implicit | Fits music well: "energetic but not tense" (dance) vs "tense but low energy" (suspense) is a real distinction |
| **3-D: V + EA + TA** | Schimmack & Grob 2000 **[verified]** | Pleasure, energetic arousal and tense arousal are all needed; a 2-D model is not enough | Valence, energy, tension | SEM on adjective ratings | Later music data partly contradict it (below) | Basis of the **Soundtracks** dataset scales (valence, energy, tension) |
| **Appraisal / CPM** | Scherer (Component Process Model); Scherer 2004 | Emotions arise from evaluating events (novelty, goal relevance, coping...) | Appraisal checks, not labels | Appraisal questionnaires | Music rarely has "goals" to appraise, so classic appraisal fits it poorly (Scherer 2004; Juslin 2013) | Explains why music-*induced* emotion is mostly "aesthetic" (wonder, nostalgia) rather than utilitarian (anger, fear). Underlies GEMS |
| **Constructionist** | Barrett 2006, 2017; Russell 2003 | Emotions are constructed from core affect (V/A) plus conceptual categorisation in context | Core affect + learned concepts | Core affect ratings + free labels | Hard to operationalise; categories still needed for communication | Cespedes-Guevara & Eerola 2018 **[verified]**: music communicates **core affect** (V/A fluctuations), and listeners *attribute* specific emotions from context. Directly relevant: a **scene supplies the context** that turns a music's core affect into a specific emotion |

### 1.2 What the music evidence says about dimensionality

- **Eerola & Vuoskoski (2011)** used 110 film-music excerpts rated by 116 non-musicians on five discrete
  emotions (anger, fear, happiness, sadness, tenderness) and on three dimensions (valence, energy, tension)
  **[verified]**.
  - The two models mapped onto each other along two central dimensions, *valence* and *arousal*.
  - Three dimensions "could be reduced to two without significantly reducing the goodness of fit".
  - The main weakness of the discrete model was **poorer resolution for emotionally ambiguous examples**.
- **Vuoskoski & Eerola (2011)** compared discrete, dimensional and GEMS scales for *induced* emotion
  (148 participants, 16 film excerpts) **[verified]**.
  - The dimensional model had the **highest consistency** and the best discrimination between excerpts.
  - Two components explained **89.9%** of variance across all scales of all models.
  - GEMS had both the weakest scales (wonder α .64, transcendence α .67) and some of the strongest
    (tension α .98).
- **Schimmack & Grob (2000)** found that, for general affect, the 3-D model could *not* be reduced to 2-D
  **[verified]**. For music, Eerola & Vuoskoski (2011) found the reduction acceptable.
  **Disagreement flag**: whether "tension" is a separate axis depends on the domain and the stimuli. For
  narrative scoring, keeping it is still justified on functional grounds (see §2.6).
- **Cowen, Fang, Sauter & Keltner (2020, PNAS)** **[verified]** used 2,168 music samples rated by US
  (n = 1,591) and Chinese (n = 1,258) participants.
  - They found **at least 13 distinct dimensions** of subjective experience: amusing, annoying,
    anxious/tense, beautiful, calm/relaxing, dreamy, energizing/pump-up, erotic, defiant, joyful, sad, scary,
    triumphant.
  - The specific feelings were **better preserved across cultures than valence/arousal levels**. Whether
    something feels good or bad was more culture-specific.
  - A PNAS letter disputed the claim that categories are primary, arguing that using language as the
    measure confounds the result (*"Claims of categorical primacy for musical affect are confounded by using
    language as a measure"*, PNAS 2020) **[verified title]**.
  - **Disagreement flag**: categories vs dimensions is unresolved.
- **Eerola & Saari (2025, PLOS ONE)** **[verified]** ran an iterative crowdsourcing study: 647 candidate
  terms reduced to 88, with ~5,300 participants across three experiments.
  - The structure of emotions *expressed* by music came out as a **7-factor model**: romantic, fun,
    energetic, powerful, sad, soft, good.
  - A 14-factor version adds dreamy, relaxed, festive, aggressive, melancholic, heroic, spiritual, dramatic
    and others.
  - A 4-factor "meta" version: happy/festive; romantic/melancholic; relaxed/dreamy; powerful/aggressive/energetic.
  - The terms are heavily positive (64% on the positive-valence side). V/A correlated with the factors but
    "did not adequately capture" expressed emotions.

---

## 2. Music-specific models

### 2.1 Hevner adjective circle and its revisions

| Version | Items | Structure | Notes |
|---|---|---|---|
| Hevner 1936 (*Am. J. Psychol.* 48:246–268) **[from memory]** | 67 adjectives | 8 clusters on a circle (dignified/solemn, sad, dreamy/sentimental, serene, graceful/light, happy, exciting, vigorous) | The first music-specific scale. Adjacent clusters are similar, opposite ones contrast: a proto-circumplex |
| Farnsworth 1954 (*JAAC* 13:97–103) **[from memory]** | Hevner's list re-grouped | 10 clusters (later revisions vary) | Found that Hevner's circularity did not hold empirically |
| Schubert 2003 (*Percept. Mot. Skills* 96:1117–1122) **[verified]** | 46 words (from 91 candidates, 133 musically experienced raters) | 9 clusters | A modern update. Cluster positions map roughly onto the valence-arousal plane |

Relevance: Hevner-type clusters are close to how production-music libraries and tag folksonomies describe
music (MIREX clusters, AllMusic moods). That makes them good *vocabulary* sources for the music side.

### 2.2 GEMS: Geneva Emotional Music Scale

**Source**: Zentner, Grandjean & Scherer (2008), *Emotion* 8(4):494–521 **[verified]**.

**Construction.**
- A lexicon of 515 terms was reduced to 66, and then to 45 terms consistently chosen for *felt* emotion
  with music **[verified]**.
- Across four studies with confirmatory factor analysis, a domain-specific 9-factor model fitted better
  than basic-emotion or circumplex models **[from memory]**.
- The 9 factors group into 3 second-order factors **[verified]**:

| Second-order | First-order factor (GEMS-9) | Typical GEMS-9 item wording (Zentner & Eerola 2010) **[from memory]** |
|---|---|---|
| **Sublimity** | Wonder | filled with wonder, dazzled, moved |
| | Transcendence | fascinated, overwhelmed, feelings of transcendence/spirituality |
| | Tenderness | tender, affectionate, in love |
| | Nostalgia | nostalgic, dreamy, melancholic |
| | Peacefulness | serene, calm, soothed |
| **Vitality** | Power | strong, triumphant, energetic |
| | Joyful activation | joyful, amused, bouncy |
| **Unease** | Tension | tense, agitated, nervous |
| | Sadness | sad, sorrowful |

**Versions** (Zentner & Eerola 2010, in Juslin & Sloboda (eds.), *Handbook of Music and Emotion*,
pp. 187–221) **[verified]**:
- **GEMS-45**: full form.
- **GEMS-25**: items cut by confirmatory factor analysis.
- **GEMS-9**: one item per factor, each glossed by ~3 adjectives.
- The ratings are typically **1–5, "not at all" to "very much"** **[from memory]**.

**Induced vs perceived.**
- GEMS was designed for **felt (induced)** emotion.
- Zentner et al. reported that negative emotions (sadness, anger, fear) are *perceived* in music far more
  often than they are *felt* **[from memory]**. This is why GEMS has no fear or anger factor.

**Later validations and critiques.**
- **Vuoskoski & Eerola 2011** (above): wonder and transcendence are the least consistent scales, and
  tension and joyful activation the most.
- **Aljanaki, Wiering & Veltkamp** (Emotify, ISMIR 2014 paper on the same data) **[verified]**:
  - Emotify replaced *wonder → amazement*, *transcendence → solemnity* and (in the released data)
    *peacefulness → calmness*.
  - PCA over the 9 Emotify categories gave **3 components explaining 69%** of variance:
    - calmness vs power (32%);
    - joyful activation vs sadness (23%);
    - solemnity vs nostalgia (14%).
  - The authors read this as GEMS being effectively ~3-D and "redundant", and suggested improvements to
    the scale. They found that mood, gender and liking influence the induced ratings.
- **Lykartsis et al. 2013** (ICMPC/ESCOM proceedings, JYX repository) **[verified, abstract only]** tested
  GEMS-25 across popular and electroacoustic music. GEMS-25 reached only **configural** invariance. A
  German GEMS-28-G reached weak factorial invariance. In plain terms, **the factor meanings shift across
  genres**.
- **Chełkowska-Zacharewicz & Janowski 2021** (*Psychology of Music*, Polish adaptation) **[verified title]**
  examined factor structure and reliability. I did not re-check the exact fit figures.
- **Coutinho & Scherer 2017, GEMIAC** (*Music Perception* 34(4):371–386) **[verified]**:
  - Motivation: GEMS missed common reactions such as boredom, "enjoying pure beauty", enthusiasm and
    "being moved". GEMS-9 items were hard for listeners to interpret (wonder, transcendence).
  - The result is **14 two-term fuzzy classes**: (1) wonder/amazed, (2) **moved/touched** (new),
    (3) enchanted/in awe [transcendence], (4) **inspired/enthusiastic** (new), (5) **energetic/lively** (new),
    (6) joyful/wanting to dance, (7) powerful/strong, (8) tender/warmhearted, (9) relaxed/peaceful,
    (10) melancholic/sad, (11) nostalgic/sentimental, (12) **indifferent/bored** (new),
    (13) tense/uneasy, (14) **agitated/aggressive** (new).
  - It comes in intensity and frequency versions.
- **Jacobsen, Strauss, Vigl, Zangerle & Zentner 2025** (*Musicae Scientiae*) **[verified, abstract-level]**:
  - GEMS-9 is similar to GEMS-45 in inter-rater agreement and per-excerpt mean ratings, but can disagree
    depending on how the GEMS-45 score is aggregated.
  - Excerpt-level estimates stabilise at about **10–20 listeners**.
- **Strauss et al. 2024, EMMA** (*Behavior Research Methods*) **[verified]**: 364 excerpts (classical, pop,
  hip-hop), each rated for **felt** emotion with GEMS by an average of 28.8 participants (517 English- and
  German-speaking participants in total). It is designed around inter-rater agreement.

**Cross-cultural use.**
- Translations exist and have been tested (German, Polish).
- The samples are overwhelmingly European.
- I found **no validated Vietnamese, Japanese, Korean or Chinese GEMS** in this search. That does not prove
  none exists, but treat it as unvalidated for East/South-East Asian listeners.

### 2.3 AESTHEMOS (Schindler et al., 2017, *PLOS ONE* 12(6):e0178899) [verified]

AESTHEMOS is a domain-general scale of aesthetic emotions (art, music, film, literature).
- 42 items in **21 two-item subscales**, rated on a 5-point scale, measuring **felt** emotion.
- **Prototypical aesthetic**: feeling of beauty/liking, fascination, being moved, awe, enchantment,
  nostalgia.
- **Pleasing**: joy, humor, vitality, energy, relaxation.
- **Epistemic**: surprise, interest, intellectual challenge, insight.
- **Negative**: feeling of ugliness, boredom, confusion, anger, uneasiness, sadness.
- Cronbach α ranges from .55 (awe) to .85 (humor).

Relevance: AESTHEMOS shows which *aesthetic* states the GEMS family misses (interest, surprise, confusion,
humour). Because it covers literature as well as music, it is a candidate shared vocabulary for "scene
feeling" and "music feeling". Its liking/ugliness subscales, however, are evaluations, not expressed
emotions, so do not use them for matching.

### 2.4 Mechanisms: Juslin's BRECVEMA

Juslin & Västfjäll 2008 (*Behav. Brain Sci.* 31:559–575) proposed six mechanisms. Juslin 2013 (*Physics of
Life Reviews* 10:235–266) extended this to **eight** **[verified]**:

| Mechanism | What triggers it | Implication for background-music selection |
|---|---|---|
| **B**rain-stem reflex | Sudden, loud, dissonant or fast events | Jump-scare stingers. Avoid under calm narration |
| **R**hythmic entrainment | Strong external pulse | High-tempo, strong-beat music pushes arousal regardless of scene |
| **E**valuative conditioning | Learned pairing of music with a valenced stimulus | Listener-specific; unpredictable from audio |
| **C**ontagion | Listener "mimics" the music's expressed emotion | The main bridge from *perceived* to *induced* |
| **V**isual imagery | Music evokes images | Strongly relevant for audiobooks: music co-creates the imagined scene |
| **E**pisodic memory | Music evokes a personal memory ("Darling, they're playing our tune") | Source of nostalgia; listener-specific |
| **M**usical expectancy | Violations and confirmations of syntactic expectation | Source of tension/suspense (§2.6) |
| **A**esthetic judgment | Evaluation of beauty, skill, novelty | Source of wonder/awe; depends on taste |

Consequence for an app: of the eight mechanisms, only **contagion, reflex, entrainment and expectancy** are
predictable from the audio. Memory and conditioning are personal. A content-based system can therefore
only target **expressed emotion plus generic arousal and tension effects**.

### 2.5 Perceived (expressed) vs induced (felt)

- **Gabrielsson 2002** (*Musicae Scientiae*, special issue 2001–2002, pp. 123–147) **[verified via
  Schubert 2013]** proposed four relationships between perceived and felt emotion:
  - positive (feel what is expressed);
  - negative (feel the opposite);
  - no systematic relation;
  - no relation (no emotion felt).
- **Evans & Schubert 2008** (*Musicae Scientiae* 12:75–99) tested these empirically. A "matched" (positive)
  relation was the most common case, but far from universal. I could not re-verify the exact percentage,
  which is usually quoted as about 60%. **[approx.]**
- **Kallinen & Ravaja 2006** (*Musicae Scientiae* 10:191–213) **[from memory]**: felt and perceived
  emotion are similar but not identical. Felt emotion is sometimes *stronger* for positive and calm
  emotions.
- **Schubert 2013 review** (*Front. Psychol.* 4:837) **[verified]**: across the tabulated studies, felt
  emotion was usually rated **lower** than expressed. Felt exceeded expressed in only 45 of 178
  comparisons.
- **Song, Dixon, Pearce & Halpern 2016** (*Music Perception* 33:472–492) **[verified]**: 80 Last.fm-tagged
  pop excerpts; induced emotion is broadly similar to perceived emotion under both categorical and
  dimensional models. Sad music tends to be felt less sad than it is perceived **[from memory]**.

**Which one matters for a soundtrack.** The literature on music in film and multimedia supports *expressed*
emotion as the matching target:
- **Boltz 2001** (*Music Perception* 18:427–454) **[from memory]**: the mood of a soundtrack biases how
  viewers interpret and remember *ambiguous* scenes. Music acts on meaning through what it expresses.
- **Cohen's Congruence-Association Model** (Cohen 2013, in Tan, Cohen, Lipscomb & Kendall (eds.), *The
  Psychology of Music in Multimedia*, OUP) **[from memory]**: music contributes through *structural
  congruence* (timing, accents) and *associative meaning* (expressed mood). Both are properties of the
  music as perceived.
- The intended effect on the listener is induced, but it arises from scene plus music together. Contagion
  is the main route from what the music expresses to what the listener feels.

**Recommendation.** Annotate and predict **perceived/expressed** emotion for tracks. Annotate
**portrayed/expressed** emotion for scenes. Use induced-emotion datasets (Emotify, EMMA, PMEmo-style
physiological data) as auxiliary, lower-weight evidence, and remember their known biases (fewer negative
labels, influenced by liking).

### 2.6 Special states that matter for narrative

| State | Key evidence | Does it map to V/A? | Store as |
|---|---|---|---|
| **Mixed emotions** (bittersweet) | Hunter, Schellenberg & Schimmack 2008 (*Cogn. Emot.* 22:327–352) **[verified]**: conflicting cues (fast + minor, slow + major) raise happy *and* sad ratings together. Larsen & Stastny 2011 (*Emotion* 11:1469–1473) **[verified]**: genuinely *simultaneous* mixed responses | No. Bipolar valence cannot represent "both" | Independent intensities for happy and sad (multi-label), never one valence number |
| **Being moved** | Menninghaus et al. 2015 (*PLOS ONE* e0128451) **[verified]**: sad and joyful variants; co-activation of positive and negative affect; **low-to-mid arousal but high intensity** | Poorly (an intensity, not an arousal) | Own category (GEMIAC #2, AESTHEMOS) plus an "intensity" field |
| **Nostalgia** | Barrett et al. 2010 (*Emotion* 10:390–403) **[verified]**: stronger with autobiographical salience, familiarity and arousal; mixed positive and negative | Partly (mid valence) | GEMS factor; note its personal (episodic-memory) component |
| **Awe / wonder** | GEMS wonder/transcendence; AESTHEMOS awe (α .55); Cowen's "triumphant", "beautiful", "dreamy" | No | Category. Expect low rater agreement, so weight it lower |
| **Tension / suspense** | Huron 2006, *Sweet Anticipation* (ITPRA: Imagination, Tension, Prediction, Reaction, Appraisal) **[from memory]**. Lehne & Koelsch 2015 (*Front. Psychol.* 6:79) **[verified]**: tension arises from conflict, instability, dissonance or uncertainty that triggers prediction of emotionally significant future events. *Domain-general*: the same in music, film and literature. Farbood 2012 (*Music Perception* 29:387–428) **[from memory]**: tension is predictable from loudness, pitch height, harmonic tension and onset frequency | Partly (tense arousal; Thayer, Schimmack & Grob) | A separate continuous axis, *and* time-varying (it builds and resolves) |

**Why tension deserves its own axis here.** Lehne & Koelsch show that narrative suspense and musical
tension share mechanisms. That makes tension the single most "shared" construct between text and music.
It also had the highest rater consistency of any scale in Vuoskoski & Eerola (2011).

---

## 3. MER datasets and how they turn emotion into data

### 3.1 Master table

| Dataset | Labels / axes | Scale / format | Static vs continuous | Annotators | Reliability reported | Size | Perceived / induced | Licence / access |
|---|---|---|---|---|---|---|---|---|
| **MIREX AMC 2007** (Hu, Downie, Laurier, Bay & Ehmann, ISMIR 2008) **[verified]** | 5 mood clusters, single label | Pick one of 5 (+ "Other") | Static, 30 s clips | Volunteers, 2–3 per clip via Evalutron 6000 | Clips needed ≥2 agreeing judges. Cluster agreement highest for C3/C5 (>70%), lowest for C1. Of the 600 final clips, 153 had 3/3 agreement | 600 clips (120 per cluster) from APM production music | Perceived | Not redistributable (APM contract) |
| **AllMusic moods** (used to build MIREX clusters, AMG1608, 4Q) | ~290 editorial mood tags **[approx.]** | Binary tags | Static (song) | Expert editors | None | Very large (commercial) | Perceived (expert) | Proprietary |
| **CAL500** (Turnbull et al. 2008, IEEE TASLP 16:467–476) **[verified]** | 174 tags incl. ~18 emotion tags **[approx.]** | Graded or binary per tag | Static (whole song) | ≥3 paid students per song; 1,700 annotations total **[verified]** | Tag-level agreement varies; emotion tags are among the noisier **[from memory]** | 500 Western pop songs | Perceived | Features and labels public; audio restricted |
| **MoodSwings** (Kim, Schmidt & Emelle, ISMIR 2008) **[verified]** | Valence, arousal | Point in a 2-D plane | **Continuous, per second** | Online 2-player game | Game rewards agreement, which biases towards consensus | >50,000 point labels on >1,000 songs **[verified]** | Perceived | Partly released (MoodSwings Turk subset) |
| **AMG1608** (Chen, Yang, Wang & Chen, ICASSP 2015) **[verified]** | Valence, arousal | 2-D VA plane | Static, 30 s clips | 665 MTurk subjects; 46 annotated >150 clips | Designed for *personalised* MER (many raters per song) | 1,608 clips | Perceived | Annotations public; audio via AllMusic previews |
| **CH818** (Hu & Yang 2017, IEEE TAFFC 8(2)) **[verified]** | Valence, arousal | VA ratings | Static | Chinese annotators | Paper shows reliability of the test set limits cross-dataset results | 818 Chinese pop clips (TW/HK/CN) | Perceived | On request **[approx.]** |
| **DEAM** (Aljanaki, Yang & Soleymani 2017, *PLOS ONE* e0173392) **[verified]** | Valence, arousal | Dynamic **−10..+10**; static **9-point** | **Both**: 2 Hz continuous plus whole-clip | MTurk with qualification test. ≥10 per excerpt (2013–14); 5 per song in 2015 (3 top workers + 2 lab) | Cronbach α (2015): **valence 0.65 ± 0.22, arousal 0.75 ± 0.16**. Agreement reached only after ~13 s, so the authors advise discarding the first 15 s | 1,802 (1,744 × 45 s + 58 full songs) | Perceived | **Creative Commons** audio (freemusicarchive, jamendo, medleyDB) |
| **PMEmo** (Zhang et al., ICMR 2018) **[verified]** | Valence, arousal + **EDA** physiology | 9-point Likert normalised to **[0,1]** | Static + dynamic (2 Hz) **[approx. for dynamic]** | 457 subjects, lab-controlled | Reported in the paper (not re-checked) | 794 pop choruses | Perceived (+ physiological, i.e. induced signal) | Research use; GitHub |
| **4Q Audio Emotion** (Panda, Malheiro & Paiva, IEEE TAFFC 2018/2020) **[verified]** | Russell quadrant Q1–Q4 | Single class | Static, 30 s | AllMusic tags mapped to quadrants, then **manual validation** by the authors | Balanced: 225 per quadrant. Novel features raised F1 to 76.4% | 900 clips | Perceived | Research download (mir.dei.uc.pt) |
| **Soundtracks** (Eerola & Vuoskoski 2011) **[verified]** | Discrete: anger, fear, happy, sad, tender (dataset docs also list a categorical "tension") + 3 dims (**valence, energy, tension**) | Likert per scale | Static, ~15 s excerpts **[approx.]** | Set 1: 360 excerpts rated by a small expert panel (size not re-verified). Set 2: 110 excerpts × 116 non-musicians | High mean-level agreement for film music (see §1.2) | 360 + 110 | **Perceived** (expressed) | Academic research use (JYU); ratings also in `MusicScienceData` (MIT) |
| **Emotify** (Aljanaki, Wiering & Veltkamp, *Inf. Process. Manage.* 52(1):115–128, 2016) **[verified]** | **GEMS-9** (amazement, solemnity, tenderness, nostalgia, calmness, power, joyful activation, tension, sadness) | Choose ≤3 of 9 (binary) | Static, 60 s | >1,700 players of a Facebook game; mean 20.8 per excerpt (≥10), 8,407 annotations | Low agreement. 33 of 400 songs dropped for **negative Fleiss κ**. Krippendorff α analysed per category | 400 excerpts (100 each: rock, classical, pop, electronic) | **Induced** ("how music made you feel") | Free for research with citation. Audio from Magnatune (CC) **[approx.]** |
| **Emotify+** (Wiafe, Sieranoja, Bhuiyan & Fränti, EURASIP JASMP 2025) **[verified]** | 10 terms: amusing, annoying, anxious, dreamy, energizing, happy, joyful, neutral, sad, relaxing (+ intensity) | Category + intensity | Static | 181 volunteers from Ghana, Finland, Bangladesh, Germany | See paper | Same 400 excerpts | Perceived | Open access; cs.uef.fi/ml/musicemotions |
| **EMMA** (Strauss et al., *Behav. Res. Methods* 2024) **[verified]** | GEMS (felt) | Likert | Static | 517 EN/DE participants, ~28.8 per excerpt | Built around inter-rater agreement | 364 excerpts | **Induced** | Online database |
| **MTG-Jamendo moodtheme** (Bogdanov, Won, Tovstogan, Porter & Serra, ICML-W 2019) **[verified]** | **56 mood/theme tags**. Mixes moods (happy, sad, dark, epic, calm, melancholic...) with *uses* (film, trailer, background, documentary, game, advertising...) **[tag list from memory]** | Binary multi-label | Static (full track) | Uploaders' own tags | None (weak labels). Benchmark scores are low (MediaEval 2019–21 PR-AUC ≈ 0.1–0.15 **[approx.]**) | 18,486 full tracks | Perceived/intended (creator) | **CC licences** (track-specific) |
| **AudioSet "music mood"** (Gemmeke et al., ICASSP 2017) | 7 classes: happy, funny, sad, tender, exciting, angry, scary **[verified]** | Single label per 10 s | Static, 10 s | Human raters verifying YouTube candidates | Ontology-level quality ratings only | ~13.7k mood clips **[verified via secondary source]** | Perceived | CC-BY labels; audio = YouTube IDs |
| **MuSe** (Akiki & Burghardt, *J. Open Humanities Data* 7, 2021) **[verified]** | Valence, arousal, dominance | Continuous; derived from **Last.fm tags × Warriner word norms** (Warriner et al. 2013) | Static | No direct annotation (lexicon projection) | Indirect; tag-derived | 90,001 songs | Perceived (social tags) | Kaggle; Spotify/MBIDs only |
| **Music4All** (Santana et al., IWSSIP 2020) **[verified]** | Last.fm tags (19,541 unique) + Spotify *valence, energy, danceability* | Spotify features in [0,1] | Static | Spotify's proprietary model + users' tags | Spotify "valence" is an undocumented model output | 109,269 songs (30 s clips) | Mixed / unknown | Research licence on request |
| **Last.fm tags** (e.g. Laurier et al., ISMIR 2009 **[verified]**) | Free mood tags. LSA gives a **4-cluster** space close to the VA quadrants | Tag counts | Static | Crowd | None | Millions | Perceived | API terms |
| **MusicCaps** (Agostinelli et al. 2023, MusicLM paper) **[verified]** | Free-text caption + "aspect list" (often includes mood words) | Text | Static, 10 s | Professional musicians (1 per clip) | Annotator subjectivity documented (CEUR 2023 paper "Annotator subjectivity in the MusicCaps dataset") **[verified title]** | 5,521 clips | Perceived | **CC BY-SA 4.0** labels; audio via YouTube |
| **GlobalMood** (Lee et al., ISMIR 2025) **[verified]** | Culture-specific emotion terms elicited bottom-up | Ratings | Static | 2,519 raters in US, France, Mexico, South Korea, Egypt; 988,925 ratings | Shared VA structure across cultures, but dictionary-equivalent terms diverge | 1,180 songs from 59 countries | Perceived | **CC BY 4.0** |
| **CLAP zero-shot moods** (LAION-CLAP, Wu et al. 2023; MS-CLAP, Elizalde et al. 2023) | Any text prompt ("sad piano music") | Cosine similarity | Static | None | Weak: on GlobalMood, zero-shot CLAP correlated only **r ≈ 0.08**, rising to 0.31 after fine-tuning **[verified via secondary summary; check the paper]** | — | Perceived (caption-trained) | Model licences vary |

### 3.2 Patterns across datasets: how emotion is standardised

| Design choice | Options in the literature | Typical convention |
|---|---|---|
| **Locus** | Perceived (most MER), induced (Emotify, EMMA, PMEmo-EDA) | Ask explicitly; Emotify told players "how the music made you feel, not what it expressed" **[verified]** |
| **Granularity in time** | Static per clip vs dynamic (1–2 Hz) | DEAM/MoodSwings dynamic at 2 Hz; discard the first ~15 s (orientation lag) |
| **Clip length** | 10 s (AudioSet, MusicCaps), 30 s (MIREX, 4Q, AMG1608), 45–60 s (DEAM, Emotify), full track (Jamendo) | 30–60 s for static mood |
| **Scale** | 9-point SAM/Likert (DEAM static, PMEmo), −10..+10 slider (DEAM dynamic), 2-D plane click (MoodSwings, AMG1608), binary choose-k (Emotify), single class (4Q, AudioSet) | Normalise to [−1,1] for bipolar axes and [0,1] for unipolar intensities |
| **Aggregation** | Mean ± SD; proportion of raters endorsing a category (Emotify: score = fraction of listeners who selected the term **[verified]**); Gaussian / GMM in VA (AEG, Wang et al. 2012) | Keep the dispersion, not just the mean |
| **Quality control** | Qualification tests, gold clips, discarding raters who dislike the music (Emotify), discarding items with κ < 0 | Report α / ICC per dimension |
| **Raters per item** | 2–3 (MIREX), 5–10 (DEAM), ~20–30 (Emotify, EMMA), hundreds (Cowen) | GEMS estimates stabilise at ~10–20 listeners (Jacobsen et al. 2025) |

---

## 4. Reliability facts

### 4.1 Which dimensions humans agree on

1. **Arousal > valence**, repeatedly.
   - DEAM: α_A 0.75 vs α_V 0.65 **[verified]**.
   - MER prediction r 0.81 vs 0.67 in the meta-analysis of 34 studies and 290 models (Eerola & Anderson,
     *ACM Computing Surveys* 58(10), 2026, doi 10.1145/3796518) **[verified]**.
   - Aljanaki et al. (2014): "valence is more difficult to model than arousal" **[verified]**.
   - Explanation offered: valence has fewer robust acoustic predictors (mode, harmony) and more individual
     differences.
2. **Tension and joyful activation** are the most reliable GEMS-type scales. **Wonder and transcendence**
   are the least reliable (Vuoskoski & Eerola 2011) **[verified]**.
3. **Dominance** is usually dropped for unreliability (survey: Kang & Herremans 2024, arXiv:2406.08809
   **[verified]**).
4. **Basic emotions in music** (happiness, sadness, anger, fear, tenderness) are decoded well above
   chance. Happiness and sadness are the most accurate (Juslin & Laukka 2003, *Psychol. Bull.*
   129:770–814) **[from memory]**.
5. **Categorical clusters** in MIREX: human agreement was only 60–90% per cluster even on pre-filtered
   production music. Cluster 1 ("passionate/rousing") was most confused **[verified]**. Laurier and
   colleagues noted semantic overlap between clusters, e.g. C2 cheerful vs C4 humorous **[from memory]**.

### 4.2 Cultural consistency

| Study | Finding | Implication |
|---|---|---|
| Balkwill & Thompson 1999 (*Music Perception* 17:43–64) **[verified]** | 30 Western listeners recognised the intended joy, sadness, anger and peace in 12 Hindustani rāga excerpts; ratings tracked tempo and complexity cues | Low-level cues (tempo, complexity, pitch range) carry emotion across cultures |
| Fritz et al. 2009 (*Current Biology* 19:573–576) **[verified]** | Mafa listeners in Cameroon with no exposure to Western music recognised **happy, sad, scared** in Western music above chance | A *small* core set is near-universal |
| Hu & Yang 2017 (IEEE TAFFC) **[verified]** | VA regression generalises across datasets only when the *culture* of the music or annotators matches; test-set reliability bounds the results | Western-trained MER may misjudge Chinese/Korean/Japanese pop and OST styles |
| Cowen et al. 2020 (PNAS) **[verified]** | US vs China: specific categories preserved better than valence/arousal levels | Category labels may transfer to Vietnamese listeners better than raw V numbers |
| Celen, van Rijn, Lee & Jacoby 2025 (CogSci; arXiv:2502.08744) **[verified]** | Brazil/US/South Korea: agreement high for **high-arousal, positive-valence** emotions and variable elsewhere. **Machine translation of emotion terms often fails** to keep music-specific meaning | Do not define categories by a single translated word. Define them by descriptions and prototypes |
| Lee et al. 2025, GlobalMood (ISMIR) **[verified]** | VA structure shared across 5 countries, but dictionary-equivalent terms diverge | Same as above |

### 4.3 Distributions vs single labels

- **Yang & Chen 2011** (IEEE TASLP 19(7):2184–2196) **[verified]** represent a clip's perceived emotion as
  a **probability distribution over the VA plane** and predict it from discrete samples.
- **Acoustic Emotion Gaussians** (Wang, Yang, Wang & Jeng, ACM MM 2012) **[verified]** learn a GMM in VA
  space from many raters, which models subjectivity directly.
- **Label distribution learning** (Geng 2016, IEEE TKDE) **[from memory]** is the general framework:
  - targets are a vector of description degrees summing to 1;
  - losses are KL or Jensen-Shannon divergence;
  - it is used widely for subjective labels (facial expression, music).
- **Emotify-style** data are *not* a single distribution. Each listener picks up to 3 of 9 terms, so each
  category has its own endorsement rate. That is **9 Bernoulli probabilities**, and their sum ranges from
  1 to 3 per listener.
  - Forcing them onto a probability simplex discards the information that two emotions co-occur (mixed
    emotions; §2.6).
- **Personalisation**: Gómez-Cañón et al. 2021 (*IEEE Signal Processing Magazine* 38(6):106–114, doi
  10.1109/MSP.2021.3106232) **[verified]** argue that MER standards should report disagreement and
  context, and support personalised models rather than one "ground truth". AMG1608 and TROMPA-MER were
  built for this purpose.

---

## 5. Synthesis: which representation for matching background music to scenes

### 5.1 What the evidence supports

| Question | Evidence-based answer | Confidence | Disagreement in the literature |
|---|---|---|---|
| Dimensional, discrete, music-specific, or hybrid? | **Hybrid.** Dimensions carry most variance and handle ambiguity (Eerola & Vuoskoski 2011). Categories transfer better across cultures and capture qualities VA misses (Cowen 2020; Eerola & Saari 2025) | High | Categories vs dimensions as "primary" (Cowen 2020 vs the PNAS reply; constructionists) |
| How many dimensions? | **3: valence, energy (energetic arousal), tension.** 2-D suffices statistically for music, but tension is the narratively crucial and most reliable extra axis (Schimmack & Grob 2000; Lehne & Koelsch 2015) | Medium-high | E&V 2011: 3 reducible to 2. S&G 2000: not reducible |
| Is GEMS-9 the right category set? | **A good backbone, but incomplete and partly unreliable for soundtracks.** Missing: fear/scary, anger/aggression, humour/comic, mystery/eerie. Unreliable: wonder, transcendence | High | GEMS was validated for *felt* emotion in concert/listening settings, not for expressed emotion in narrative underscore |
| Perceived or induced? | **Perceived/expressed** on both sides. Induced data serve as weak auxiliary signals | High | Some argue the end goal is induced effect. In practice induced = expressed + personal noise + damping of negative emotions |
| Single label or distribution? | **Per-category intensity in [0,1] + uncertainty**, plus a derived normalised distribution for similarity | High | LDL-simplex vs multi-label are both used. Simplex loses mixed emotions |

### 5.2 Recommended concrete schema (both scene and track)

**Layer 1: core affect (continuous, bipolar), each stored as `mean`, `sd`, `n` or `confidence`.**

| Axis | Range | Anchors | Notes |
|---|---|---|---|
| `valence` | −1..+1 | −1 very negative / dark, 0 neutral or ambiguous, +1 very positive / bright | Lowest reliability; give it the lowest weight in matching. Culture-sensitive |
| `energy` (energetic arousal) | −1..+1 | −1 very calm / sparse / slow, +1 very energetic / dense / fast | Most reliable; highest weight. Predictable from tempo, loudness, onset density |
| `tension` (tense arousal) | −1..+1 | −1 relaxed / resolved, +1 very tense / suspenseful / dissonant | Separate from energy (quiet suspense = low energy, high tension). For long scenes, store as a short **time series** (build-up vs release) |

Conversions:
- 9-point Likert: `(x−5)/4`.
- DEAM dynamic: `x/10`.
- PMEmo [0,1]: `2x−1`.
- Spotify "valence/energy" [0,1]: `2x−1`, but treat as a different instrument and z-score per source
  before merging, because each dataset's anchors differ (Hu & Yang 2017).

**Layer 2: expressed-emotion categories (unipolar intensities 0..1, multi-label, independent).**
GEMS-9 forms the backbone, plus the classes that narrative underscore needs. Each class is defined by
**2–3 descriptors and audio/text prototypes, not by one word** (translation problem; Celen et al. 2025).
Sources for each added class are given in brackets.

| # | Category | Descriptors | Source |
|---|---|---|---|
| 1 | Peacefulness | serene, calm, soothing | GEMS |
| 2 | Tenderness | tender, warm, affectionate/romantic | GEMS (+ Eerola & Saari "romantic") |
| 3 | Nostalgia / melancholy | nostalgic, wistful, bittersweet | GEMS |
| 4 | Sadness | sad, sorrowful, grieving | GEMS |
| 5 | Joyful activation | joyful, cheerful, bouncy | GEMS |
| 6 | **Playful / comic** | amusing, whimsical, quirky | Cowen "amusing"; MIREX C4; AudioSet "funny"; AESTHEMOS humor |
| 7 | Power / heroic | strong, triumphant, epic | GEMS power; Cowen "triumphant" |
| 8 | Wonder / awe | amazed, majestic, transcendent | GEMS wonder+transcendence merged, because separately they are the least reliable |
| 9 | Tension / suspense | tense, uneasy, anticipatory | GEMS |
| 10 | **Fear / eerie** | scary, ominous, uncanny | Basic emotion (Fritz 2009 universal); AudioSet "scary"; Cowen "scary"; *absent from GEMS* |
| 11 | **Anger / aggression** | aggressive, fierce, agitated | GEMIAC #14; MIREX C5; AudioSet "angry"; Cowen "defiant" |
| 12 | **Mystery / dreamy** | mysterious, dreamy, ethereal | Cowen "dreamy"; Eerola & Saari "dreamy" |
| 13 | **Being moved** (optional) | moving, touching, poignant | GEMIAC #2; Menninghaus 2015. Overlaps tenderness+sadness+wonder, so keep it only if annotators separate it |

Optional meta fields:
- `intensity` (0..1): overall emotional strength, distinct from energy. Needed for "being moved" (low
  arousal, high intensity).
- `locus` (`expressed` | `induced`) and `source` (`human` | `model:<name>` | `tags`), so that data from
  different instruments are never mixed silently.

**Layer 3: derived representations for retrieval (not stored as truth).**
- A normalised category distribution `p = s / Σs` for divergence-based similarity (Jensen-Shannon).
- The second-order GEMS groups (sublimity / vitality / unease), useful as a coarse fallback.

### 5.3 Matching rules suggested by the evidence

1. Weight the axes by reliability: **energy > tension > valence**. For example, start at 1.0 / 0.8 / 0.6
   and tune on owner judgements.
2. Use the uncertainty. Mahalanobis or Gaussian overlap (Bhattacharyya) on Layer 1 lets a high-SD
   (ambiguous) track match a broader set of scenes. This follows the AEG logic.
3. For categories, use cosine or JS on intensities. **Do not penalise mixed profiles.** A bittersweet scene
   should match a track with both sadness and tenderness high.
4. Treat GEMS-*induced* predictions (e.g. a model trained on Emotify) as auxiliary features:
   - map amazement → wonder, solemnity → wonder/power, calmness → peacefulness;
   - expect negative categories to be **under-estimated** relative to expressed emotion.
5. Background music must not overpower narration. Brain-stem-reflex and entrainment effects (§2.4) argue
   for capping energy and transient sharpness under dialogue, whatever the emotional match. This is a
   design inference, not a tested result.

### 5.4 Open disagreements to keep in mind

- **Categories vs dimensions as fundamental.** Cowen 2020 and Eerola & Saari 2025 favour categories.
  Russell, Barrett, and Cespedes-Guevara & Eerola 2018 favour core affect plus construction. The hybrid
  hedges between them.
- **2-D vs 3-D.** For music, tension is statistically largely reducible (E&V 2011). For general affect it is
  not (S&G 2000).
- **GEMS factor structure.** Nine factors (Zentner 2008) vs about three effective dimensions in crowd data
  (Aljanaki 2014). Measurement invariance across genres is only weak or configural (Lykartsis et al. 2013).
- **Universality.** A small universal core (Fritz 2009; Balkwill & Thompson 1999) vs culture-specific
  valence and term meanings (Cowen 2020; Celen 2025; Hu & Yang 2017). No validated
  Vietnamese/Japanese/Korean/Chinese music-emotion instrument was found in this search.
- **Perceived vs induced** relations are mostly positive but not always (Gabrielsson 2002; Evans & Schubert
  2008; Schubert 2013).
- **Tag datasets** (Jamendo, Last.fm, MuSe, Music4All) are large but weak. Their labels mix mood with use
  context and have no reliability estimates. They suit pre-training, not ground truth.

### 5.5 Directly related prior work on text-to-music emotion matching

**Won, Salamon, Bryan, Mysore & Serra (ISMIR 2021, "Emotion Embedding Spaces for Matching Music to
Stories", arXiv:2111.13468)** **[verified abstract]** treat story-to-music matching as cross-modal
retrieval. They compare:
- manually defined spaces (valence-arousal);
- learned emotion embeddings (word-embedding and metric-learning based), which bridge the different emotion
  vocabularies of text datasets and music datasets.

Both work. Learned embeddings generalise to new vocabularies. This supports keeping a learned joint
embedding *alongside* the interpretable axes/categories above. On the text side, word-level VAD norms
(Warriner et al. 2013; NRC-VAD lexicon, Mohammad 2018 **[from memory]**) give the same three-number
interface as MuSe does for music.

---

## 6. References

Grouped by section; DOIs or links where verified.

**General emotion theory**
- Barrett, L. F. (2006). Are emotions natural kinds? *Perspectives on Psychological Science*, 1, 28–58. [from memory]
- Barrett, L. F. (2017). *How Emotions Are Made.* Houghton Mifflin Harcourt. [from memory]
- Cespedes-Guevara, J., & Eerola, T. (2018). Music communicates affects, not basic emotions. *Frontiers in Psychology*, 9, 215. https://doi.org/10.3389/fpsyg.2018.00215
- Ekman, P. (1992). An argument for basic emotions. *Cognition & Emotion*, 6, 169–200. [from memory]
- Izard, C. E. (1977). *Human Emotions.* Plenum; Izard (2007), *Perspectives on Psychological Science* 2, 260–280. [from memory]
- Mehrabian, A., & Russell, J. A. (1974). *An Approach to Environmental Psychology.* MIT Press. [from memory]
- Russell, J. A. (1980). A circumplex model of affect. *JPSP*, 39, 1161–1178. https://doi.org/10.1037/h0077714
- Russell, J. A. (2003). Core affect and the psychological construction of emotion. *Psychological Review*, 110, 145–172. [from memory]
- Schimmack, U., & Grob, A. (2000). Dimensional models of core affect: A quantitative comparison by means of structural equation modeling. *European Journal of Personality*, 14, 325–345.
- Scherer, K. R. (2004). Which emotions can be induced by music? *Journal of New Music Research*, 33, 239–251. [from memory]
- Thayer, R. E. (1989). *The Biopsychology of Mood and Arousal.* Oxford University Press. [from memory]

**Music-specific models**
- Barrett, F. S., et al. (2010). Music-evoked nostalgia: Affect, memory, and personality. *Emotion*, 10, 390–403.
- Bigand, E., et al. (2005). Multidimensional scaling of emotional responses to music. *Cognition & Emotion*, 19, 1113–1139. [from memory]
- Boltz, M. G. (2001). Musical soundtracks as a schematic influence on the cognitive processing of filmed events. *Music Perception*, 18, 427–454. [from memory]
- Cohen, A. J. (2013). Congruence-Association Model of music and multimedia. In Tan, Cohen, Lipscomb & Kendall (Eds.), *The Psychology of Music in Multimedia*. OUP. [from memory]
- Coutinho, E., & Scherer, K. R. (2017). Introducing the GEneva Music-Induced Affect Checklist (GEMIAC). *Music Perception*, 34(4), 371–386. https://doi.org/10.1525/mp.2017.34.4.371
- Cowen, A. S., Fang, X., Sauter, D., & Keltner, D. (2020). What music makes us feel: At least 13 dimensions organize subjective experiences associated with music across different cultures. *PNAS*, 117(4), 1924–1934. https://doi.org/10.1073/pnas.1910704117
- Chełkowska-Zacharewicz, M., & Janowski, M. (2021). Polish adaptation of the Geneva Emotional Music Scale. *Psychology of Music*. https://doi.org/10.1177/0305735620927474
- Eerola, T., & Vuoskoski, J. K. (2011). A comparison of the discrete and dimensional models of emotion in music. *Psychology of Music*, 39(1), 18–49. https://doi.org/10.1177/0305735610362821
- Eerola, T., & Vuoskoski, J. K. (2013). A review of music and emotion studies: Approaches, emotion models, and stimuli. *Music Perception*, 30(3), 307–340. https://online.ucpress.edu/mp/article/30/3/307/62574 (251 studies reviewed; ~70% used discrete or dimensional models)
- Eerola, T., & Saari, P. (2025). What emotions does music express? Structure of affect terms in music using iterative crowdsourcing paradigm. *PLOS ONE*. https://doi.org/10.1371/journal.pone.0313502
- Evans, P., & Schubert, E. (2008). Relationships between expressed and felt emotions in music. *Musicae Scientiae*, 12, 75–99.
- Farbood, M. M. (2012). A parametric, temporal model of musical tension. *Music Perception*, 29, 387–428. [from memory]
- Farnsworth, P. R. (1954). A study of the Hevner adjective list. *JAAC*, 13, 97–103. [from memory]
- Gabrielsson, A. (2002). Emotion perceived and emotion felt: Same or different? *Musicae Scientiae*, Special issue 2001–2002, 123–147.
- Hevner, K. (1936). Experimental studies of the elements of expression in music. *American Journal of Psychology*, 48, 246–268. [from memory]
- Hunter, P. G., Schellenberg, E. G., & Schimmack, U. (2008). Mixed affective responses to music with conflicting cues. *Cognition & Emotion*, 22, 327–352.
- Huron, D. (2006). *Sweet Anticipation: Music and the Psychology of Expectation.* MIT Press. [from memory]
- Jacobsen, P.-O., Strauss, H., Vigl, J., Zangerle, E., & Zentner, M. (2025). Assessing aesthetic music-evoked emotions in a minute or less: A comparison of the GEMS-45 and the GEMS-9. *Musicae Scientiae*. https://doi.org/10.1177/10298649241256252
- Juslin, P. N. (2013). From everyday emotions to aesthetic emotions: Towards a unified theory of musical emotions. *Physics of Life Reviews*, 10(3), 235–266.
- Juslin, P. N., & Laukka, P. (2003). Communication of emotions in vocal expression and music performance. *Psychological Bulletin*, 129, 770–814. [from memory]
- Juslin, P. N., & Västfjäll, D. (2008). Emotional responses to music: The need to consider underlying mechanisms. *Behavioral and Brain Sciences*, 31, 559–575. [from memory]
- Kallinen, K., & Ravaja, N. (2006). Emotion perceived and emotion felt: Same and different. *Musicae Scientiae*, 10, 191–213. [from memory]
- Larsen, J. T., & Stastny, B. J. (2011). It's a bittersweet symphony: Simultaneously mixed emotional responses to music with conflicting cues. *Emotion*, 11, 1469–1473.
- Lehne, M., & Koelsch, S. (2015). Toward a general psychological model of tension and suspense. *Frontiers in Psychology*, 6, 79. https://doi.org/10.3389/fpsyg.2015.00079
- Lykartsis, A., Pysiewicz, A., et al. (2013). The emotionality of sonic events: Testing the GEMS for popular and electroacoustic music. ICME3 proceedings, JYX. https://jyx.jyu.fi/jyx/Record/jyx_123456789_41586
- Menninghaus, W., et al. (2015). Towards a psychological construct of being moved. *PLOS ONE*, 10(6), e0128451. https://doi.org/10.1371/journal.pone.0128451
- Schindler, I., et al. (2017). Measuring aesthetic emotions: A review of the literature and a new assessment tool. *PLOS ONE*, 12(6), e0178899. https://doi.org/10.1371/journal.pone.0178899
- Schubert, E. (2003). Update of the Hevner adjective checklist. *Perceptual and Motor Skills*, 96, 1117–1122. https://doi.org/10.2466/pms.2003.96.3c.1117
- Schubert, E. (2013). Emotion felt by the listener and expressed by the music: Literature review and theoretical perspectives. *Frontiers in Psychology*, 4, 837. https://doi.org/10.3389/fpsyg.2013.00837
- Song, Y., Dixon, S., Pearce, M. T., & Halpern, A. R. (2016). Perceived and induced emotion responses to popular music: Categorical and dimensional models. *Music Perception*, 33(4), 472–492. https://doi.org/10.1525/mp.2016.33.4.472
- Strauss, H., Vigl, J., et al. (2024). The Emotion-to-Music Mapping Atlas (EMMA). *Behavior Research Methods*. https://doi.org/10.3758/s13428-024-02336-0
- Vuoskoski, J. K., & Eerola, T. (2011). Measuring music-induced emotion: A comparison of emotion models, personality biases, and intensity of experiences. *Musicae Scientiae*, 15(2), 159–173. https://doi.org/10.1177/1029864911403367
- Zentner, M., Grandjean, D., & Scherer, K. R. (2008). Emotions evoked by the sound of music: Characterization, classification, and measurement. *Emotion*, 8(4), 494–521.
- Zentner, M., & Eerola, T. (2010). Self-report measures and models. In Juslin & Sloboda (Eds.), *Handbook of Music and Emotion* (pp. 187–221). OUP.

**Cross-cultural**
- Balkwill, L.-L., & Thompson, W. F. (1999). A cross-cultural investigation of the perception of emotion in music. *Music Perception*, 17(1), 43–64.
- Celen, E., van Rijn, P., Lee, H., & Jacoby, N. (2025). Are expressions for music emotions the same across cultures? CogSci 2025. https://arxiv.org/abs/2502.08744
- Fritz, T., et al. (2009). Universal recognition of three basic emotions in music. *Current Biology*, 19(7), 573–576. https://doi.org/10.1016/j.cub.2009.02.058
- Hu, X., & Yang, Y.-H. (2017). Cross-dataset and cross-cultural music mood prediction: A case on Western and Chinese pop songs. *IEEE TAFFC*, 8(2). https://doi.org/10.1109/TAFFC.2016.2523503
- Lee, H., Çelen, E., Harrison, P., et al. (2025). GlobalMood: A cross-cultural benchmark for music emotion recognition. ISMIR 2025. https://arxiv.org/abs/2505.09539

**MER datasets and methods**
- Agostinelli, A., et al. (2023). MusicLM: Generating music from text (MusicCaps). https://arxiv.org/abs/2301.11325 ; https://huggingface.co/datasets/google/MusicCaps
- Akiki, C., & Burghardt, M. (2021). MuSe: The Musical Sentiment Dataset. *Journal of Open Humanities Data*, 7. https://www.kaggle.com/datasets/cakiki/muse-the-musical-sentiment-dataset
- Aljanaki, A., Wiering, F., & Veltkamp, R. C. (2014). Computational modeling of induced emotion using GEMS. ISMIR 2014. https://archives.ismir.net/ismir2014/paper/000325.pdf
- Aljanaki, A., Wiering, F., & Veltkamp, R. C. (2016). Studying emotion induced by music through a crowdsourcing game. *Information Processing & Management*, 52(1), 115–128. https://doi.org/10.1016/j.ipm.2015.03.004 ; data: https://www.projects.science.uu.nl/memotion/emotifydata/
- Aljanaki, A., Yang, Y.-H., & Soleymani, M. (2017). Developing a benchmark for emotional analysis of music. *PLOS ONE*, 12(3), e0173392. https://doi.org/10.1371/journal.pone.0173392
- Bogdanov, D., Won, M., Tovstogan, P., Porter, A., & Serra, X. (2019). The MTG-Jamendo dataset for automatic music tagging. ICML ML4MD workshop. https://mtg.github.io/mtg-jamendo-dataset/
- Chen, Y.-A., Yang, Y.-H., Wang, J.-C., & Chen, H. (2015). The AMG1608 dataset for music emotion recognition. ICASSP 2015.
- Eerola, T., & Anderson, C. J. (2026). A meta-analysis of music emotion recognition studies. *ACM Computing Surveys*, 58(10). https://doi.org/10.1145/3796518
- Elizalde, B., et al. (2023). CLAP: Learning audio concepts from natural language supervision. ICASSP. https://arxiv.org/abs/2206.04769
- Gemmeke, J. F., et al. (2017). Audio Set: An ontology and human-labeled dataset for audio events. ICASSP 2017. [from memory]
- Geng, X. (2016). Label distribution learning. *IEEE TKDE*, 28(7), 1734–1748. [from memory]
- Gómez-Cañón, J. S., Cano, E., Eerola, T., Herrera, P., Hu, X., Yang, Y.-H., & Gómez, E. (2021). Music emotion recognition: Toward new, robust standards in personalized and context-sensitive applications. *IEEE Signal Processing Magazine*, 38(6), 106–114. https://doi.org/10.1109/MSP.2021.3106232
- Hu, X., Downie, J. S., Laurier, C., Bay, M., & Ehmann, A. F. (2008). The 2007 MIREX audio mood classification task: Lessons learned. ISMIR 2008, 462–467. https://ismir2008.ismir.net/papers/ISMIR2008_263.pdf
- Kang, J., & Herremans, D. (2024). Are we there yet? A brief survey of music emotion prediction datasets, models and outstanding challenges. https://arxiv.org/abs/2406.08809 (author names from memory; title verified)
- Kim, Y. E., Schmidt, E. M., & Emelle, L. (2008). MoodSwings: A collaborative game for music mood label collection. ISMIR 2008. https://archives.ismir.net/ismir2008/paper/000257.pdf
- Laurier, C., Sordo, M., Serrà, J., & Herrera, P. (2009). Music mood representations from social tags. ISMIR 2009, 381–386. https://ismir2009.ismir.net/proceedings/OS5-4.pdf
- Panda, R., Malheiro, R., & Paiva, R. P. (2018/2020). Novel audio features for music emotion recognition. *IEEE TAFFC*. https://mir.dei.uc.pt/downloads.html
- Santana, I. A. P., et al. (2020). Music4All: A new music database and its applications. IWSSIP 2020. http://www.din.uem.br/yandre/IWSSIP_2020_Music4All.pdf
- Turnbull, D., Barrington, L., Torres, D., & Lanckriet, G. (2008). Semantic annotation and retrieval of music and sound effects. *IEEE TASLP*, 16(2), 467–476. http://eceweb.ucsd.edu/~gert/papers/TASLP-08.pdf
- Wang, J.-C., Yang, Y.-H., Wang, H.-M., & Jeng, S.-K. (2012). The acoustic emotion Gaussians model for emotion-based music annotation and retrieval. ACM Multimedia 2012. https://doi.org/10.1145/2393347.2393367
- Warriner, A. B., Kuperman, V., & Brysbaert, M. (2013). Norms of valence, arousal, and dominance for 13,915 English lemmas. *Behavior Research Methods*, 45, 1191–1207. [from memory]
- Wiafe, A., Sieranoja, S., Bhuiyan, A., & Fränti, P. (2025). Emotional response to music: the Emotify+ dataset. *EURASIP Journal on Audio, Speech, and Music Processing*. https://doi.org/10.1186/s13636-025-00419-0
- Won, M., Salamon, J., Bryan, N. J., Mysore, G. J., & Serra, X. (2021). Emotion embedding spaces for matching music to stories. ISMIR 2021. https://arxiv.org/abs/2111.13468
- Wu, Y., et al. (2023). Large-scale contrastive language-audio pretraining (LAION-CLAP). ICASSP 2023. [from memory]
- Yang, Y.-H., & Chen, H. H. (2011). Prediction of the distribution of perceived music emotions using discrete samples. *IEEE TASLP*, 19(7), 2184–2196.
- Zhang, K., Zhang, H., Li, S., Yang, C., & Sun, L. (2018). The PMEmo dataset for music emotion recognition. ICMR 2018. https://doi.org/10.1145/3206025.3206037 ; https://github.com/HuiZhangDB/PMEmo

**Not verified / gaps from this search:**
- the exact Evans & Schubert (2008) percentage;
- the full MTG-Jamendo tag list (recalled from memory);
- the AllMusic mood count;
- the number of expert raters for Soundtracks set 1;
- the CAL500 emotion-tag count;
- the exact PMEmo dynamic-annotation details;
- whether GEMS has a validated East-Asian or Vietnamese version (none found).

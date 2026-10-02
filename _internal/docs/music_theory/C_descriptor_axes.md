# C. Non-emotion descriptor axes for background music under narration

Research note, 2026-10-02. Scope: which axes besides emotion are used to describe music, what values they take, how industry and research encode them as data, and a proposed set for ABook. ABook picks background cues under a Vietnamese TTS narrator for translated JP light novels and KR/CN web novels, using free catalogs (Incompetech, OpenGameArt, Scott Buckley, Jamendo; FreePD is now closed, see 1.4).

Every source below was found and opened or searched on 2026-10-02. Where only a secondary source was available, the text says so. Where evidence is weak or I inferred something, it is marked **[weak]** or **[inference]**.

---

## 0. Key findings (short)

1. **Professional libraries use about 8 to 12 facet families, and they agree on them.** The families are genre, mood, instruments, tempo/BPM, vocals, duration, "use case / theme / music-for", era/period, country/region, character/movement, and track type/version. APM's submission spec has **29 facets with explicit min/max counts per facet**, and it is the most complete published schema I found (1.1).
2. **Vocal presence is graded, not binary, in the best schemas.** Epidemic Sound uses `NONE / PRESENCE / LEAD`, PremiumBeat lists "Oohs & Aahs" as an undistracting option, and APM defines an "Underscore" version as a track with no vocal *or instrumental* melodic line. This last idea, melodic salience, is the second most important axis for music under speech.
3. **Research on music under speech points to a short list of acoustic axes.** These are lyrics (worst when the lyric language matches the listener's language), changing-state or busyness, register and tempo, speech-band energy (1 to 4 kHz), and the loudness difference to the voice (at least 10 LU preferred for commentary over music). These are measurable from audio (section 3).
4. **The standard open taxonomies have no East Asian traditional instruments.** AudioSet (632 classes) has only a generic "Zither", and MTG-Jamendo's 40 instruments have none. That blocks the xianxia, wuxia and Japanese-setting axes. Chinese-instrument datasets exist (ChMusic, 11 instruments; CCMusic/CTIS, 287 instrument types). For Japanese and Korean instruments I found no comparable open dataset **[weak: absence of evidence]**.
5. **Free catalogs carry little and uneven metadata.** Incompetech's `pieces.json` (1,443 pieces, fetched today) has 19 "feel" values, free-text instruments (260 distinct strings), BPM on 1,196 of 1,443 pieces, and only about 17 pieces whose description or feel mentions Asian or oriental styles. **Coverage for xianxia/wuxia settings is the binding constraint, not the tagging scheme.**
6. **Story-to-music systems in research use emotion plus one context axis.** Bardo (2017) uses 4 emotions. Won et al. (ISMIR 2021) use emotion embeddings. Sonus Texere (ISMIR 2022) adds scene context and style consistency. None publishes a full non-emotion axis set for audiobook background music. The axis set in section 5 is therefore a synthesis, not a validated standard.

---

## 1. Production music libraries: metadata taxonomies

### 1.1 Facet comparison

| Library | Facets exposed (search/filter) | Size of vocabularies | Who tags | Source |
|---|---|---|---|---|
| **APM Music** | 29 facets in the submission spec: Master Genre (exactly 1), Additional Genre (0-7), **Music For** (1-8), **Track Type** (1: Main / Underscore / Alternate / Link / Sting), Trailer Track, Mood (1-20, "five most relevant" advised, max 2 children per parent), **Character** (0-5), **Movement** (0-5), **Tempo** (1), Inst/Vocal Groupings (0-4), Instruments (0-8), Vocals (0-5), Solo, Amateur/Poorly Played, Sound Effects, **Country & Region** (0-5), National Anthem, **Musical Form** (0-2), **Time Period** (0-3, contiguous), Vintage Style, Archival Recording, **Has Lyrics**, Lyric Subject (0-3), Explicit, Stems Not Available, Artist Driven, **Well-Known Tune**, Key, Language; plus integer **BPM** (required) and "StyleALike" references | Facets are numbered members of a master list ("APM Facet Members and Numbers Master"; not public) | Composers/publishers tag through a portal under validation rules; trailer and artist-driven tags are reviewed by staff | [APM Metadata File Format & Submission Guidelines v2.0, 2023](https://static.prod.apmmusic.com/images/apm-metadata-guidelines.pdf) |
| **Epidemic Sound** | Moods, genres (parent/child, e.g. indie-rock under rock), BPM range, **vocals = `NONE` / `PRESENCE` / `LEAD`**, duration, beat timestamps, "highlights"; filters combine with AND | Not stated in API docs | In-house curation; themes are hand-picked playlists | [Epidemic Sound developer docs](https://developers.epidemicsite.com/docs/music/); [Epidemic discovery blog](https://www.epidemicsound.com/blog/our-new-music-discovery-experience/) |
| **Artlist** | Genre, Mood, **Video Theme** (Travel, Wedding, Technology...), Instrument; Vocals/Instrumental (female, male, duet, group, a cappella), duration (1 s - 7 min), BPM (20-200), stems | Not stated | Not stated | [Artlist help: Browsing the catalog](https://help.artlist.io/hc/en-us/articles/29596157272221-Browsing-Artlist-s-Music-catalog) |
| **Musicbed** | Genre (20), Mood (14), Instrument (40+), Artist, **Attributes (82, e.g. "Earthy", "French")**, vocals (male/female/choir), **"build"** of the song, length, BPM, key; include/exclude per filter | Counts as stated by Musicbed | Not stated | [Musicbed blog: 5 ways to find music](https://www.musicbed.com/articles/music/5-ways-to-find-the-perfect-music-for-your-films/) |
| **PremiumBeat** | Genre (incl. a "Games" branch: Adventure... Racing), Mood (incl. use-like moods such as "Aerobics / Workout"), instrument, BPM, duration, **track type**, vocals incl. **"Oohs & Aahs"**, "Instrumental only" | ~20,000 tracks | Not stated | [No Film School guide](https://nofilmschool.com/how-to-use-premiumbeat-music-and-sound-effects) (secondary) |
| **YouTube Audio Library** | Genre, Mood, Instrument, Duration, Attribution (required / not required) | Moods include angry, bright, calm, dark, dramatic, funky, happy, inspirational, romantic, sad | Google | [YouTube Help](https://support.google.com/youtube/answer/3376882?hl=en) |
| **Audio Network** | Mood, tempo, genre, instrumentation, BPM, emotion; AI similarity search | "300,000 tracks... 800 genres" | Editorial plus AI similarity | [Audio Network: Discover](https://us.audionetwork.com/music) |
| **Sonoton (SONOfind)** | Genres, facets, filters; AI reference search "Trackster" (2019) | 130k+ works | First library search software (1992), online in 1998 | [Wikipedia: Sonoton](https://en.wikipedia.org/wiki/Sonoton); [Sonoton on X, 2019](https://x.com/SONOTONmusic/status/1152108593786904576) |
| **Cyanite** (ML tagger sold to libraries) | 23 output categories: genre/sub-genre, mood, **character**, **movement**, energy level, **emotional dynamics**, instruments + presence, voice presence and gender, BPM, key, meter, valence, arousal, musical era, brand values | 13 simple moods, 131 advanced moods, 23 main genres, 58 sub-genres, 5,000+ free genre tags | Fully automatic from audio | [Cyanite: AI auto-tagging guide, 2026](https://cyanite.ai/blog/ai-auto-tagging-music-catalogs/) |
| Pond5, BMAT | Not verified. I found no public facet spec | - | - | **[weak: not covered]** |

What this shows:

- **"Use case" is its own facet everywhere.** It is called *Music For* at APM, *Video Theme* at Artlist, *Themes* at Epidemic, and part of *Mood* at PremiumBeat. It describes the *job* of the cue (wedding, sports, documentary), not its emotion. For ABook the analogue is **scene function** (battle, daily life, cultivation, court intrigue).
- **"Character" and "Movement" are separate from mood** at both APM and Cyanite. Character describes texture or attitude (e.g. "quirky", "majestic"). Movement describes motion (e.g. "flowing", "pulsing", "irregular > tempo changes"). These overlap with this app's busyness and rhythm axes. **[inference: the APM member lists are not public, so the example values are illustrative]**
- **Versions are part of the data model.** APM defines one Main version per song plus Underscore, Alternate (including 60 s and 30 s cut-downs), Link (15-20 s transition) and Sting (≤7 s). "Underscore" is defined as *"the track without any vocal or instrumental melodic line but with the other rhythmic and harmonic elements in place"*. For music under narration, the underscore version is usually the right one.
- **Counts are capped on purpose.** APM warns that over-tagging lowers search ranking, advises the 3 or 5 most relevant moods, and forbids parent and child tags from the same branch. This fits "store top-k with probabilities" better than "store every tag".
- **Familiarity is a facet.** APM has "Well-Known Tune". This is relevant because familiar music behaves differently under speech (section 3).

### 1.2 Who tags: editors versus ML

- Older libraries (APM, Sonoton) rely on **composer or publisher tagging under validation rules**, with editorial review for some facets.
- Since about 2019, libraries add **audio-similarity and auto-tagging** (Sonoton Trackster 2019, Audio Network AI similarity, Cyanite sold as a service to production libraries). Cyanite tags everything, including mood, from audio alone.
- The usual pattern is **ML proposes and an editor curates** for high-value facets such as themes and playlists. Epidemic's themes are "handpicked by expert music curators". **[inference from the sources above; no library publishes its exact split]**

### 1.3 How music supervisors and anime sound directors choose cues

- **Spotting sessions.** Director, editor and composer or music editor watch the cut and decide, cue by cue, *whether* music plays, where it starts and stops, and *what it is doing* (its function). The cues are logged against timecode. A temp track is judged by "what is it doing for the scene", not by its sound ([Modwheel: spotting](https://modwheel.net/guides/scoring-to-picture-spotting); [Film Scoring Tips](https://filmscoringtips.com/film-editors-spotting-session/), practitioner sources).
- **Classic film-music principles.** Gorbman, *Unheard Melodies: Narrative Film Music* (Indiana UP / BFI, 1987), lists the principles of the classical Hollywood score. Two of them are "inaudibility" (music is subordinate to dialogue and not consciously heard) and "narrative cueing" (music signals point of view, setting and mood). This is the canonical statement that background music has a *subordination* axis separate from emotion. (Cited from my knowledge of a standard text, not fetched today.)
- **Anime TV score (劇伴) "music menu".** The sound director, with the director, reads the scripts and storyboards and drafts an **音楽メニュー**. It is a numbered list (M1, M2, …) of roughly 50 pieces for a TV series, each with a provisional title naming the intended scene ("◎◎のテーマ") and comments on length and use. Titles are only assigned at release ([Interview with 腹巻猫, author of 『劇伴音楽入門』, Mono Magazine](https://www.monomagazine.com/111026)). A practitioner blog gives 30-80 cues per series, 1-2 minute loopable cues, daily-life cues around 70-90 BPM and battle cues around 140-180 BPM ([core-ms.net, 2026](https://core-ms.net/2026/07/20/anime-music-composition-method/) **[weak: blog]**). For ABook the key point is that **anime scores are commissioned by scene function** (daily life, battle, comedy, sorrow, a character's theme). That is the same "use case" axis as in 1.1, applied to the source medium of light novels.

### 1.4 What the free catalogs actually give

| Catalog | Machine-readable metadata | Notes |
|---|---|---|
| **Incompetech** (Kevin MacLeod, CC-BY) | `pieces.json`: title, length, `instruments` (free text), `genre` (numeric id), `bpm`, `description`, `feel` (comma list), `isrc` | Fetched 2026-10-02: **1,443 pieces**. `feel` has 19 values (Dark 419, Grooving 374, Relaxed 354, Bright 329, Calming 307, Bouncy 303, Driving 271, Mysterious 261, Intense 221, Eerie 185, Unnerving 177, Somber 166, Mystical 164, Uplifting 154, Humorous 151, Epic 130, Action 120, Suspenseful 102, Aggressive 82). A new piece adds "Ren Faire, Medieval", so setting words are starting to enter `feel`. 260 distinct instrument strings with mixed singular/plural forms. BPM present for 1,196 pieces. Only **~17** pieces mention Asian or oriental styles in description or feel. Instrument strings: koto 5, erhu 3, guzheng 1, pipa 1, yangqin 1, taiko 1. The website filter shows 24 genres, including "Silent Film Score", "Horror", "Stings", "World" ([Incompetech](https://incompetech.com/music/royalty-free/music.html)). |
| **Jamendo API v3** | `tags`/`fuzzytags`; `vocalinstrumental` ∈ {vocal, instrumental}; `acousticelectric` ∈ {acoustic, electric}; `speed` ∈ {verylow, low, medium, high, veryhigh}; `gender`; lyric `lang`; `durationbetween`; license flags (ccsa, ccnd); `musicinfo` returns genres / instruments / vartags | Uploader tags. This is the source of MTG-Jamendo (2.1) ([Jamendo API docs](https://developer.jamendo.com/v3.0/tracks)) |
| **Scott Buckley** (CC-BY 4.0) | Web filters: genres, ~40+ moods, 30+ instrumentation options, albums | No API seen ([scottbuckley.com.au/library](https://www.scottbuckley.com.au/library/)) |
| **OpenGameArt** | Free-form tags (style such as "orchestral", content such as "fantasy", plus function words such as "battle", "town", "boss", "loop"), with a separate license field | Function words in titles and tags are a cheap source of the **scene-function** axis ([OpenGameArt tag guidance](https://opengameart.org/content/art-tags)) |
| **FreePD** | n/a | **Site closed.** Its notice says the service went offline after 17 years ([freepd.com](https://freepd.com/)). Any FreePD tracks already downloaded keep their PD status, but there is no catalog to sync. |

---

## 2. Standard descriptor ontologies and model vocabularies

| Vocabulary | Axes | Size | Use for ABook | Source |
|---|---|---|---|---|
| **Music Ontology** (Raimond, Abdallah, Sandler, Giasson, ISMIR 2007) | RDF framework: editorial (FRBR-style work/expression/manifestation), events, timeline, instruments, genre via external taxonomies | Schema only, no value lists | A model for *provenance and versioning*, not for values | [ISMIR 2007 paper](https://ismir2007.ismir.net/proceedings/ISMIR2007_p417_raimond.pdf) |
| **Discogs** genres/styles | 2-level: 15 genres (incl. "Stage & Screen", "Folk, World, & Country") → styles | ~400-519 styles. Essentia ships **Discogs400** and **Discogs519** classifiers | Genre/style as a weak proxy for setting (e.g. "Score", "Soundtrack", "Chinese Classical"?) **[weak: I did not verify which Asian styles exist]** | [Discogs style guide](https://reference.discogs.com/wiki/style-guide); [Essentia models](https://essentia.upf.edu/models.html) |
| **MusicBrainz** genres | Curated genre list over folksonomy tags | Hundreds (exact count not checked) | Not needed | [musicbrainz.org/genres](https://musicbrainz.org/genres) |
| **AllMusic (Rovi)** | Moods, themes (themes = occasions or subjects, e.g. "Road Trip"), styles | 2009 crawl: **178 moods, 73 themes** | Precedent for a "theme" axis separate from mood | [Bischoff et al., ISMIR 2009](https://archives.ismir.net/ismir2009/paper/000106.pdf) |
| **Essentia / MTG model zoo** | Genre (Discogs400/519, MTG-Jamendo 87), mood binaries (aggressive, happy, party, relaxed, sad, acoustic, electronic), MIREX 5 clusters, MTG-Jamendo mood/theme 56, arousal/valence regressors (DEAM, emoMusic, MuSe; 1-9), **danceability**, **voice/instrumental**, **voice gender**, **tonal/atonal**, timbre, **NSynth acoustic/electronic, bright/dark, reverb**, MTG-Jamendo instrument (40), top-50, **approachability** (mainstream vs niche), **engagement** (lean-forward vs lean-back), **music loop role**, TempoCNN, AudioSet-YAMNet | See left | The main CPU-friendly source of track-side descriptors. **Engagement (lean-back)** and **voice/instrumental** map directly to the background requirement | [Essentia models](https://essentia.upf.edu/models.html) |
| **AudioSet ontology** (Gemmeke et al., ICASSP 2017) | Music → Musical instrument, Music genre, Musical concepts, **Music role**, Music mood | 632 classes total. Music role = {**Background music**, Theme music, Jingle, **Soundtrack music**, Lullaby, **Video game music**, Christmas, Dance, Wedding, Birthday}. Mood = {Happy, Funny, Sad, Tender, Exciting, Angry, Scary}. Instruments include Zither, Gong, Sitar, Tabla, Bagpipes, Didgeridoo, Singing bowl. **No guzheng, erhu, koto, shakuhachi, shamisen, dizi, pipa, taiko.** Music of Asia has only Carnatic and Bollywood | "Music role" is the only standard vocabulary with an explicit *background* class. Gaps confirmed by parsing `ontology.json` today | [AudioSet paper](https://www.researchgate.net/publication/317723317_Audio_Set_An_ontology_and_human-labeled_dataset_for_audio_events); [ontology.json](https://github.com/audioset/ontology) |
| **MTG-Jamendo** (Bogdanov et al., ICML-ML4MD 2019) | Genre 87, instrument 40, mood/theme 56 | 55k CC tracks. Instruments: accordion, acousticbassguitar, acousticguitar, bass, beat, bell, bongo, brass, cello, clarinet, classicalguitar, computer, doublebass, drummachine, drums, electricguitar, electricpiano, flute, guitar, harmonica, harp, horn, keyboard, oboe, orchestra, organ, pad, percussion, piano, pipeorgan, rhodes, sampler, saxophone, strings, synthesizer, trombone, trumpet, viola, violin, voice | Same CC ecosystem as Jamendo. Mood/theme mixes moods with themes such as "adventure", "film", "game", "christmas" | [MTG-Jamendo](https://mtg.github.io/mtg-jamendo-dataset/) |
| **MusicCaps** (Agostinelli et al., MusicLM, 2023) | Per-clip **aspect list** + free caption by musicians | 5,521 ten-second AudioSet clips. Aspects cover genre, instruments, mood, tempo, recording quality ("low quality", "amateur recording"), vocals, rhythm | Shows what musicians name spontaneously. Recording quality is a real axis | [HF: google/MusicCaps](https://huggingface.co/datasets/google/MusicCaps); [MusicLM paper](https://arxiv.org/pdf/2301.11325) |
| **Hornbostel-Sachs (1914), MIMO revision 2011** | Instrument classification by sound production: 1 idiophones, 2 membranophones, 3 chordophones, 4 aerophones, 5 electrophones (added by MIMO) | Decimal hierarchical codes | Culture-neutral parent level for instruments. Guzheng/koto are 3.1.2 board zithers, erhu is a bowed chordophone, shakuhachi/dizi are aerophones, taiko is a membranophone | [MIMO revision PDF](http://www.mimo-international.com/documents/hornbostel%20sachs.pdf) |
| **ChMusic** (2021) | 11 Chinese instruments: erhu, pipa, sanxian, dizi, suona, zhuiqin, zhongruan, liuqin, guzheng, yangqin, sheng | 55 excerpts (small) | Training or eval for Chinese-instrument detection | [arXiv 2108.08470](https://arxiv.org/abs/2108.08470) |
| **CCMusic / CTIS** (TISMIR 2025) | Chinese MIR database, including CTIS: 287 varieties of Chinese traditional, reformed and minority instruments | Larger | Same use as ChMusic | [TISMIR](https://transactions.ismir.net/articles/10.5334/tismir.194) |
| **Text-audio embeddings (CLAP, MuQ-MuLan)** | Open vocabulary: any text label can be scored | LAION-CLAP: ~71% zero-shot on GTZAN, 73.9 ROC-AUC on MagnaTagATune (as reported) | The only cheap route to custom axes such as "wuxia", "guzheng", "isekai tavern". **Accuracy on non-Western instruments is unreported [weak]** | [LAION-CLAP](https://github.com/LAION-AI/CLAP); [instrument-recognition evaluation of two-tower models, 2024](https://arxiv.org/pdf/2407.18058) |

Takeaways:
- For **track-side automatic tagging**, Essentia covers vocals, tonal/atonal, acoustic/electronic, bright/dark, danceability, engagement, Western instruments, genre and tempo. CLAP covers setting and culture. Small curated sets cover East Asian instruments.
- The standard vocabularies have no axis for **"how well this sits under a voice"**. ABook has to measure that directly (section 3).

---

## 3. Axes specific to background music under speech

### 3.1 Evidence table

| Finding | Study | Implication for axis |
|---|---|---|
| Music with lyrics impairs reading comprehension more than instrumental music, and liked or disliked lyrical music both hurt | Perham & Currie, 2014, *Applied Cognitive Psychology* ([summary via Bournemouth preprint context](https://eprints.bournemouth.ac.uk/38543/1/Preprint_rev1.pdf)) | **Vocal presence**: hard filter |
| Lyrics hurt reading comprehension, **most when the lyric language matches the text language**, and most for non-habitual listeners | Sun et al., 2024, *Frontiers in Psychology* 15:1363562, n=90 ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11027201/)) | **Lyric language**: Vietnamese lyrics worst; foreign lyrics still bad |
| Audiobook + pop songs at 0 dB SNR: comprehension impaired vs silence; **vocals further hinder** neural tracking of the story; familiar music changes the effect; listeners with less musical ability are hit harder | Brown & Bidelman, 2022, *Brain Sciences* 12:1320 ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9599198/)). Its abstract also says that, behaviourally, *familiar* music and vocals inhibit speech recognition | **Vocals** (hard); **familiarity** (soft penalty) |
| Piano masker: **low octave and fast tempo mask speech most**, high octave and slow tempo least. Music masks less than speech-shaped noise at equal level (50 dBA) | Ekström & Borg, 2011, *Noise & Health* 13(53):277-285 ([PubMed](https://pubmed.ncbi.nlm.nih.gov/21768731/)) | **Register/low-mid energy** and **tempo** |
| Changing sounds disrupt serial memory more than steady ones, and instrumental tones do too ("changing-state hypothesis") | Jones et al. 1992; Jones & Macken 1993, *JEP:LMC* 19(2) ([PDF listing](https://www.researchgate.net/publication/232417838_Irrelevant_tones_produce_an_irrelevant_speech_effect_Implications_for_phonological_coding_in_working_memory)); Salamé & Baddeley 1989 (background music and phonological memory) | **Busyness / changing-state density** |
| Meta-analysis: overall effect of background music on cognition ≈ null, but **reading is disturbed**. Emotional responses improve. Music tempo carries over to activity tempo | Kämpfe, Sedlmeier & Renkewitz, 2011, *Psychology of Music* 39(4) ([ERIC](https://eric.ed.gov/?id=EJ944201)) | Background music is a trade-off: emotion gain against comprehension cost |
| Commentary over music: listeners prefer **≥10 LU** loudness difference (≥15 LU over ambience). Non-experts want 4 LU more than experts | Torcoli et al., 2019, *JAES* 67(12) ([Salford repository](https://salford-repository.worktribe.com/output/1360952/preferred-levels-for-background-ducking-to-produce-esthetically-pleasing-audio-for-tv-with-clear-speech)) | **Loudness difference** is a mix parameter. Each track's **masking potential** shifts the LD it needs |
| Preferred dialogue-to-background LD varies a lot across people (IQR 5.7 LU) but is predictable per item from objective intelligibility metrics (MAE ≈2.5 LU) | Resti, Strauss, Torcoli, Habets, Edler, QoMEX 2023 ([arXiv 2305.19100](https://arxiv.org/abs/2305.19100)) | A per-track **required LD** can be *computed* and stored |
| Speech intelligibility weight peaks in the ~1-2.5 kHz 1/3-octave bands | ANSI S3.5-1997 SII ([summary](https://www.researchgate.net/publication/324581011_SII-Speech_intelligibility_index_standard_ANSI_S35_1997)) | **Speech-band occupancy**, SII-weighted |
| Mixing practice: cut music at 1-4 kHz or apply sidechain multiband ducking at 1.5-4 kHz under dialogue. Dynamic EQ judged most effective in one thesis | [iZotope, mixing audio for video pt. 4](https://www.izotope.com/en/learn/mixing-audio-for-video-part-4-mixing-techniques) (industry); [DiVA thesis](https://www.diva-portal.org/smash/get/diva2:1596853/FULLTEXT01.pdf) **[weak: student thesis]** | The app can repair part of the spectral overlap at mix time. Store the axis anyway for ranking |
| Broadcast and streaming normalise on dialogue: EBU R128 −23 LUFS programme loudness with LRA as a supplementary descriptor; Netflix −27 LKFS dialogue-gated | [EBU Tech 3342 (LRA)](https://tech.ebu.ch/docs/tech/tech3342.pdf), [EBU Tech 3343](https://tech.ebu.ch/docs/tech/tech3343.pdf); [Netflix spec via Production Expert](https://www.production-expert.com/home-page/2018/8/23/has-netflix-turned-the-clock-back-10-years-or-is-their-new-loudness-delivery-spec-a-stroke-of-genius) | Anchor music level to **narration loudness**. Store **LRA** and peak excursions per track |
| Story absorption and enjoyment survive moderate masking (babble), though effort rises | Herrmann & Johnsrude, 2020, *Trends in Hearing* 24 ([DOI](https://doi.org/10.1177/2331216520967850)) | Some masking is tolerable. Don't over-optimise |
| Survey (n=537): BGM in audiobooks raises telepresence and emotional connectedness | Ji, Liu, Xu, Gong, 2024, *SAGE Open* ([link](https://journals.sagepub.com/doi/10.1177/21582440241257357)) | Supports BGM at all. Self-report only **[weak for design]** |
| Robotic storytelling: sound effects and BGM increased enjoyment for romance and trended to lower fatigue | 2024, *Computers in Human Behavior: Artificial Humans* ([link](https://www.sciencedirect.com/science/article/pii/S2949882124000458)) | Genre-dependent benefit **[weak: small, robot context]** |

I found **no controlled study that varies music descriptors under audiobook narration and measures comprehension** apart from Brown & Bidelman, who used pop songs at 0 dB, far louder than any sane BGM mix. The thresholds in 5.x are therefore engineering choices, informed by the studies above.

### 3.2 The axes, defined

1. **Vocal presence and kind.** Values: `none / wordless (choir pad, "oohs") / lead_foreign / lead_same_language`. Epidemic's NONE/PRESENCE/LEAD is the industry precedent. Measure with Essentia `voice_instrumental` probability. Where vocals are detected, run source separation (Demucs, Rouard et al. ICASSP 2023) and Whisper language ID on the vocal stem to get the lyric language. Use metadata where present (Jamendo `vocalinstrumental`, `lang`; APM "Has Lyrics").
2. **Melodic salience (foreground versus underscore).** This is the APM "Underscore" concept: is there a continuous prominent melody line? Measure with pitch-salience (Essentia `PitchSalience`), melody-extraction voicing ratio and confidence (Melodia; Salamon & Gómez, IEEE TASLP 2012), and the energy share of the "other" stem against the drums/bass stems. Essentia's **engagement** model (lean-forward vs lean-back) is a learned proxy. Scale 0-1.
3. **Speech-band occupancy / masking potential.** This is the share of the track's long-term spectrum inside 1-4 kHz, weighted by SII band importance, computed *relative to the narrator's long-term average spectrum*. A stronger version simulates a mix at a nominal LD (e.g. −12 LU) and computes a glimpse proportion (Cooke, *JASA* 119(3), 2006), or an objective intelligibility metric as used by Resti et al. 2023. Store `masking_index` 0-1 and the derived `required_ld_lu`.
4. **Low-register weight.** Ekström & Borg found low-octave piano masked more. Store energy share at 100-500 Hz. **[weak: one study, piano only]**
5. **Busyness / changing-state density.** Onset rate (events/s; MIRtoolbox *eventdensity*, Lartillot & Toiviainen DAFx 2007; Essentia `OnsetRate`), spectral-flux variance, and note density from melody extraction. Scale: events/s, plus a 0-1 percentile within the catalog.
6. **Tempo.** BPM (float, with confidence and octave-ambiguity flag; Essentia TempoCNN, or All-In-One, Kim & Nam WASPAA 2023). Also a coarse class, `speed` {verylow…veryhigh} as in Jamendo, so metadata and model agree on one scale.
7. **Dynamics.** Integrated loudness (LUFS), **LRA (LU, EBU Tech 3342)**, max short-term minus integrated loudness (sudden swells or hits), and a **build** flag (Musicbed's "build"; APM trailer three-part structure). Background music wants low LRA, no sudden peaks and slow builds.
8. **Tonal stability.** Essentia tonal/atonal probability, key strength, mode, and dissonance or roughness. Used both to *avoid* (atonal under calm scenes) and to *target* (suspense, horror).
9. **Structure and loopability.** Duration; intro and outro lengths and segment labels (All-In-One gives intro/verse/chorus/bridge/outro plus beats and downbeats); ending type (`fade / hard_end / sting`); best seamless loop points and quality (PyMusicLooper does waveform-match loop detection and can export intro/loop/outro, [GitHub](https://github.com/arkrow/PyMusicLooper)); Essentia "music loop" model. Version type: APM's `main / underscore / alternate / link / sting`.
10. **Technical quality.** Sample rate, codec bitrate, noise floor, clipping, true peak. MusicCaps aspect lists name "low quality" and "amateur recording" as descriptors, and APM has "Amateur/Poorly Played". Hard-filter the worst.
11. **Familiarity / over-exposure.** APM "Well-Known Tune". Some free tracks are extremely widely reused in online video. Familiar background music measurably changes speech tracking (Brown & Bidelman 2022), and recognising a meme track breaks immersion **[inference]**. Proxy: a manual blocklist, or usage counts if available. Soft penalty.

---

## 4. Cultural and setting axes ("world" of the story versus "world" of the music)

### 4.1 Literature

- **Exoticism as a set of signifiers.** Locke, *Musical Exoticism: Images and Reflections* (Cambridge UP, 2009), analyses how Western music signals foreign places through scales, instruments and harmonies, and notes that imitation of the real culture is only one strategy ([Cambridge](https://www.cambridge.org/9780521877930)). For ABook this means an "East Asian" setting can be signalled two ways. One is *authentic* traditional idiom (a guzheng solo in a Chinese mode). The other is *stylised* film/game idiom (Western orchestra plus pentatonic melody plus dizi). Listeners of donghua and C-dramas are used to the second. Tag them as **different values**. **[inference]**
- **Musical topics.** Monelle, *The Musical Topic: Hunt, Military and Pastoral* (Indiana UP, 2006), defines topics as conventional figures with stable associations. Teaching material extends the topics to film and games: magic, outer space, underwater, soaring ([Lavengood, MUSI 216 notes](https://musi216.meganlavengood.com/mm-lessons/topics/) **[weak: course page]**). Topics give a vocabulary for "heroic/military", "pastoral", "magic", "space".
- **Empirical connotation tests.** Tagg & Clarida, *Ten Little Title Tunes* (2003), collected hundreds of listeners' free associations to TV and film title music and linked them to musical structure ([IASPM review](https://www.iaspm.net/review/taggclarida.htm)). It is the strongest empirical evidence that genre/setting connotations are shared and stable within a culture. It used Western respondents, so for Vietnamese listeners **[weak: transfer unverified]**.
- **Gufeng (古风).** A modern Chinese genre that uses pentatonic melody and Chinese instruments. It is commonly used in xianxia and wuxia games, anime and dramas ([Wikipedia: Gufeng music](https://en.wikipedia.org/wiki/Gufeng_music) **[weak: encyclopedia]**). This is the natural target idiom for cultivation novels.
- **Anime and game scoring by function.** See the anime music menu (1.3). JRPG soundtracks conventionally have town, field/overworld, dungeon, battle, boss, victory fanfare, inn/rest and character themes. Free asset packs on itch.io and OpenGameArt are named that way. I found only commercial and blog sources for this list, not a peer-reviewed taxonomy (Summers, *Understanding Video Game Music*, Cambridge UP 2016, discusses functions but I could not verify a cue-type list) **[weak]**. Isekai light novels borrow JRPG worlds directly (guilds, dungeons, towns), so this function list maps well to that genre. **[inference]**
- **Story-to-music systems.** Bardo (Padovani, Ferreira, Lelis, AIIDE 2017) uses 4 emotions only ([PDF](https://webdocs.cs.ualberta.ca/~santanad/papers/2017/padovaniFL17.pdf)). Won, Salamon, Bryan, Mysore, Serra (ISMIR 2021) build emotion embedding spaces for matching text to music ([arXiv 2111.13468](https://arxiv.org/abs/2111.13468)). **Sonus Texere** (Shriram, Tapaswi, Alluri, ISMIR 2022) mines film-adaptation soundtracks and matches on scene emotion *and context*, keeping style consistent across a book ([arXiv 2212.01033](https://arxiv.org/abs/2212.01033)). M2M-Gen (2024) uses LLMs to generate manga BGM ([arXiv 2410.09928](https://arxiv.org/pdf/2410.09928)). **Style consistency across a book** is the main non-emotion axis this line of work adds.

### 4.2 Proposed setting vocabulary (track idiom ↔ story world)

| Value (`idiom`) | Typical markers | Story genres it serves |
|---|---|---|
| `cn_traditional` | guzheng, guqin, erhu, dizi, xiao, pipa, pentatonic, sparse | xianxia, wuxia, palace/court, Chinese historical |
| `cn_cinematic` (gufeng/donghua orchestral) | orchestra + Chinese solo instruments, taiko-like drums, choir | xianxia battles, sect wars, epic cultivation |
| `jp_traditional` | koto, shamisen, shakuhachi, taiko, in/yo scales | Japanese historical, shrine/yokai, onmyoji |
| `kr_traditional` | gayageum, haegeum, daegeum, janggu | Korean historical/murim **[weak: almost no free catalog supply]** |
| `west_medieval_fantasy` | lute, recorder, harp, hurdy-gurdy, fiddle, modal folk; "Ren Faire, Medieval" | isekai towns, taverns, guilds, European-fantasy LN |
| `west_orchestral_cinematic` | strings, brass, choir, timpani | generic epic/heroic/battle in any Western-fantasy story |
| `jrpg_game` | synth-orchestral, chiptune-adjacent, loop-oriented | isekai "game-world", dungeon/system/status-screen stories |
| `contemporary_acoustic_pop` | piano, acoustic guitar, light drums, glockenspiel | school life, romance, slice of life (JP/KR modern) |
| `electronic_scifi` | synth pads, arps, pulses, NSynth "electronic" | sci-fi, VR-game, cyber, space |
| `ambient_neutral` | pads, drones, no cultural marker | any setting: the safe fallback |
| `horror_textural` | atonal, drones, prepared sounds | horror, curses, eldritch |
| `comedic_light` | pizzicato, bassoon, ukulele, "Humorous" | comedy beats in any genre |

Plus a separate optional **`era`** axis (APM Time Period analogue): `ancient / medieval / early_modern / modern / futuristic`. Values are multi-label probabilities. `ambient_neutral` always scores as compatible.

---

## 5. Synthesis: proposed non-emotion axes for ABook

### 5.1 Axis table

H = hard filter, S = soft score term, M = mix-time parameter (affects ducking/EQ, not selection). "Scene side" says what the narration/scene pipeline must provide.

| # | Axis | Type / range | Track side: how obtained | Scene side | Role | Evidence |
|---|---|---|---|---|---|---|
| 1 | `vocal_kind` | enum {none, wordless, lead_foreign, lead_vi} + `p_voice` ∈[0,1] | Essentia voice_instrumental; if p_voice>0.3: Demucs vocal stem + Whisper LID; metadata (Jamendo vocalinstrumental/lang) | Optional flag "climax may allow wordless choir" | **H**: exclude lead_*. Wordless only by scene permission | Strong (3.1) |
| 2 | `melodic_salience` | float 0-1 | Pitch salience + melody voicing ratio + "other"-stem share; Essentia engagement as feature | Dialogue density of the passage (lines of quoted speech per minute) | **S**: penalty grows with dialogue density | Medium (APM Underscore concept; changing-state literature) |
| 3 | `masking_index`, `required_ld_lu` | float 0-1; LU (typ. 8-20) | Long-term spectrum vs narrator LTAS, SII-weighted 1-4 kHz share; optional glimpse/intelligibility sim | Narrator voice id (each TTS voice has its own LTAS) | **S** + **M** (sets ducking depth and dynamic EQ) | Strong for principle (SII, Torcoli 2019, Resti 2023); thresholds are engineering choices |
| 4 | `low_mid_share` | float 0-1 (100-500 Hz energy share) | Spectrum | - | **S** (small weight) | **Weak** (single study) |
| 5 | `busyness` | onsets/s (float) + catalog percentile 0-1 | Essentia OnsetRate, spectral-flux variance | Scene pace (action vs reflective) from LLM | **S** (target band per scene type) | Medium (changing-state hypothesis) |
| 6 | `tempo_bpm`, `tempo_conf`, `speed_class` | float 30-220; 0-1; enum 5 levels | TempoCNN or All-In-One; Incompetech/Jamendo metadata as prior | Scene pace class | **S** | Medium (Ekström & Borg; anime practice 70-90 vs 140-180 BPM is a blog figure **[weak]**) |
| 7 | `lra_lu`, `peak_excursion_lu`, `has_build` | LU floats; bool | pyloudnorm / EBU R128 meter (short-term loudness), All-In-One segments | - | **H** if peak_excursion > ~8 LU [engineering]; **S** on LRA | Medium (EBU practice) |
| 8 | `tonality` | p_tonal 0-1, key, mode {major, minor, modal/unknown}, dissonance 0-1 | Essentia tonal_atonal, KeyExtractor, Dissonance | Scene wants "unsettled" (horror/suspense) or "stable" | **S** | Medium |
| 9 | `structure` | duration_s; intro_s; outro_s; ending enum {fade, hard, sting}; loop_points[]; loop_quality 0-1; version enum {main, underscore, alternate, link, sting} | All-In-One segments; PyMusicLooper; metadata (APM-style version names, OpenGameArt "loop") | Scene length (estimated narration seconds) | **H** for transitions (only link/sting/fade-ends); **S** for fitting duration (prefer loopable when scene ≫ track) | Strong as industry practice (APM track types) |
| 10 | `instruments` | map label→p over controlled vocab (MTG-Jamendo 40 + East Asian extension), each label has a Hornbostel-Sachs code; `acoustic_electronic` 0-1; `ensemble` enum {solo, small, band, orchestra} | Essentia MTG-Jamendo instrument + NSynth acoustic/electronic; CLAP zero-shot for East Asian labels; Incompetech `instruments` text normalised to vocab; human check on East Asian tags | Usually not needed directly. Derived from idiom (#11) | **S** | Medium (Western), **weak** (East Asian zero-shot accuracy unknown) |
| 11 | `idiom` | map value→p over the 4.2 vocabulary (12 values) | CLAP zero-shot with several prompts per value, combined with #10 instruments and metadata keywords (feel "Medieval", description "oriental", OpenGameArt tags); human-confirmed for top candidates | **Book-level palette** from genre and setting (LLM on synopsis or first chapters), plus scene-level override (e.g. modern-world flashback in an isekai) | **H** at book level: allowed idioms = palette ∪ {ambient_neutral}. **S** at scene level | Theory strong (Locke, Tagg), automatic tagging **weak** |
| 12 | `era` | map {ancient, medieval, early_modern, modern, futuristic}→p | CLAP + idiom priors | LLM on book setting | **S** | Weak, low priority |
| 13 | `function` (scene role) | map over ~16 values: daily_life, travel_explore, battle, boss_climax, tension, mystery, romance, comedy, sorrow, triumph, training_cultivation, town_tavern, court_ceremony, night_rest, horror, transition | Title/tag keywords (OpenGameArt "battle", "town"; Incompetech description), CLAP prompts, LLM over metadata text | LLM scene classifier (same vocabulary) | **S** (strongest non-emotion term) | Strong as practice (anime music menu, library "use case" facets); vocabulary is ours |
| 14 | `quality` | sample_rate, bitrate, true_peak, clip_ratio, noise_floor_db; bool `ok` | ffprobe + meters | - | **H** | Practice |
| 15 | `familiarity` | float 0-1 (manual / usage proxy) | Manual list of over-used tracks | - | **S** penalty | Weak (inference from Brown & Bidelman + APM facet) |
| 16 | `book_consistency` | Not a track field: distance in embedding / idiom / instrument space to the cues already used in this book | CLAP/Discogs-EffNet embeddings | Running state per book | **S** (prefer staying in palette) | Medium (Sonus Texere) |
| 17 | `license` | enum {CC0, PD, CC-BY, CC-BY-SA, other} + attribution string + `ok_for_app` | Catalog metadata | - | **H** | Required (attribution) |

Emotion axes (valence/arousal, mood tags) are out of scope here. Note that libraries' "energy level" and Essentia arousal overlap with #5-#7. Keep energy as a *measured* quantity (loudness + busyness) and leave arousal to the emotion module, so one concept is not scored twice. **[inference]**

### 5.2 Selection logic (sketch)

1. **Hard filters**: license ok, quality ok, `vocal_kind` allowed for this scene, idiom ∈ book palette ∪ {ambient_neutral}, no sudden peaks, version allowed for this slot (bed or transition).
2. **Soft score** = w_emo·emotion_match + w_fn·function_match + w_idiom·idiom_match + w_cons·book_consistency − w_mel·melodic_salience·dialogue_density − w_mask·masking_index − w_busy·|busyness − target(scene)| − w_tempo·|log(bpm/target)| − w_fam·familiarity + w_len·duration_fit.
3. **Mix**: use `required_ld_lu` (clamped, e.g. ≥10 LU under narration per Torcoli 2019) and optional dynamic EQ in 1-4 kHz under speech.

Start with hand-set weights. Learn them later from the owner's accept/reject judgements, which are effectively pairwise labels. Weights are **[inference]**, and no study gives them.

### 5.3 Storage

Recommended schema (SQLite, consistent with the app's existing project DB style **[assumption]**):

```
music_track(
  track_id TEXT PK, catalog TEXT, catalog_ref TEXT, title TEXT,
  license TEXT, attribution TEXT, duration_s REAL, sample_rate INT, bitrate_kbps INT,
  audio_sha256 TEXT, version_type TEXT CHECK(version_type IN ('main','underscore','alternate','link','sting','loop'))
)

music_descriptor(              -- one row per (track, axis, source)
  track_id TEXT, axis TEXT,    -- e.g. 'tempo_bpm', 'idiom', 'instruments'
  value_num REAL,              -- scalar axes, in SI/standard units (BPM, LU, LUFS, 0-1)
  value_json TEXT,             -- enum or {label: p} maps, sorted, top-k (k<=8) + 'other'
  confidence REAL,             -- 0-1, model calibration or human=1.0
  source TEXT,                 -- 'meta:incompetech' | 'model:essentia/voice_instrumental-musicnn@<ver>' | 'clap:<ckpt>@<prompt_set_ver>' | 'human:owner'
  vocab_version TEXT,          -- version of the label set used
  computed_at TEXT,
  PRIMARY KEY(track_id, axis, source)
)

music_embedding(track_id TEXT, model TEXT, dim INT, vec BLOB)  -- CLAP / Discogs-EffNet, for re-scoring new vocab without re-running audio

music_segment(track_id TEXT, start_s REAL, end_s REAL, label TEXT)  -- intro/verse/.../loop region
```

Rules:
- **Probabilities, not booleans**, for every model output. Threshold at query time, so cut-offs can change without recomputing.
- **Keep every source** (metadata, model, human) as separate rows. Resolve with a precedence order (human > curated metadata > model) in a view. This is the APM/Cyanite pattern, with ML proposing and editors overriding.
- **Version the vocabularies** (`vocab_version`), and store embeddings so a new idiom or function label can be scored by CLAP from stored vectors without decoding audio again.
- **Units**: BPM float; loudness in LUFS/LU; spectral shares 0-1; durations in seconds. Enums use lowercase snake_case English codes. Vietnamese display names live in the UI layer.
- **Scene side** uses the *same* vocabularies (`function`, `idiom`, `era`, pace class, dialogue_density, allow_wordless). Matching is then a lookup, not a translation.

### 5.4 Where the evidence is weak, and what to measure ourselves

1. **Thresholds under audiobook narration.** No study gives masking, busyness or salience thresholds for BGM at realistic levels (−10 to −20 LU under the voice). A small in-house A/B test with the owner (same scene, high vs low salience or masking) would settle the weights.
2. **East Asian instrument and idiom detection.** CLAP zero-shot accuracy on guzheng/erhu/koto is unreported. Build a ~100-clip check set from ChMusic plus hand-labelled catalog tracks before trusting it.
3. **Catalog coverage.** Incompetech has about 17 Asian-styled pieces out of 1,443. Before tuning `idiom`, count supply per idiom across all catalogs. If `cn_traditional` has fewer than about 20 usable tracks, the matcher will repeat cues regardless of scoring.
4. **Cross-cultural connotations.** Tagg's reception tests are Anglo-American. Vietnamese listeners steeped in C-drama/donghua may hear "Chinese cinematic" as the default fantasy sound. This is untested.
5. **Pond5 / BMAT / Musiio taxonomies** were not verified. Gorbman (1987) and Salamé & Baddeley (1989) are cited from standard knowledge, not fetched today.
6. **Effective anime/JRPG cue-type list.** It comes only from practitioner and commercial sources. The `function` vocabulary in 5.1 is our own synthesis.

---

### Sources (all accessed 2026-10-02)

Industry: [APM metadata guidelines v2.0 (2023)](https://static.prod.apmmusic.com/images/apm-metadata-guidelines.pdf) · [Epidemic Sound API docs](https://developers.epidemicsite.com/docs/music/) · [Artlist help](https://help.artlist.io/hc/en-us/articles/29596157272221-Browsing-Artlist-s-Music-catalog) · [Musicbed blog](https://www.musicbed.com/articles/music/5-ways-to-find-the-perfect-music-for-your-films/) · [PremiumBeat guide (No Film School)](https://nofilmschool.com/how-to-use-premiumbeat-music-and-sound-effects) · [YouTube Audio Library help](https://support.google.com/youtube/answer/3376882?hl=en) · [Audio Network](https://us.audionetwork.com/music) · [Sonoton (Wikipedia)](https://en.wikipedia.org/wiki/Sonoton) · [Cyanite auto-tagging guide](https://cyanite.ai/blog/ai-auto-tagging-music-catalogs/) · [Incompetech](https://incompetech.com/music/royalty-free/music.html) + `pieces.json` · [Jamendo API](https://developer.jamendo.com/v3.0/tracks) · [Scott Buckley library](https://www.scottbuckley.com.au/library/) · [OpenGameArt tags](https://opengameart.org/content/art-tags) · [FreePD closure](https://freepd.com/) · [Mono Magazine: 腹巻猫 interview](https://www.monomagazine.com/111026) · [Modwheel: spotting](https://modwheel.net/guides/scoring-to-picture-spotting) · [iZotope mixing for video](https://www.izotope.com/en/learn/mixing-audio-for-video-part-4-mixing-techniques) · [EBU Tech 3342](https://tech.ebu.ch/docs/tech/tech3342.pdf) · [EBU Tech 3343](https://tech.ebu.ch/docs/tech/tech3343.pdf)

Research: [Music Ontology, ISMIR 2007](https://ismir2007.ismir.net/proceedings/ISMIR2007_p417_raimond.pdf) · [Bischoff et al., ISMIR 2009](https://archives.ismir.net/ismir2009/paper/000106.pdf) · [Essentia models](https://essentia.upf.edu/models.html) · [AudioSet, ICASSP 2017](https://www.researchgate.net/publication/317723317_Audio_Set_An_ontology_and_human-labeled_dataset_for_audio_events) · [MTG-Jamendo, 2019](https://mtg.github.io/mtg-jamendo-dataset/) · [MusicCaps / MusicLM, 2023](https://arxiv.org/pdf/2301.11325) · [MIMO Hornbostel-Sachs 2011](http://www.mimo-international.com/documents/hornbostel%20sachs.pdf) · [ChMusic, 2021](https://arxiv.org/abs/2108.08470) · [CCMusic, TISMIR](https://transactions.ismir.net/articles/10.5334/tismir.194) · [LAION-CLAP](https://github.com/LAION-AI/CLAP) · [Two-tower instrument recognition eval, 2024](https://arxiv.org/pdf/2407.18058) · [All-In-One, WASPAA 2023](https://github.com/mir-aidj/all-in-one) · [PyMusicLooper](https://github.com/arkrow/PyMusicLooper) · [Ekström & Borg 2011](https://pubmed.ncbi.nlm.nih.gov/21768731/) · [Brown & Bidelman 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9599198/) · [Sun et al. 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11027201/) · [Perham & Currie 2014 (via preprint)](https://eprints.bournemouth.ac.uk/38543/1/Preprint_rev1.pdf) · [Kämpfe et al. 2011](https://eric.ed.gov/?id=EJ944201) · [Jones & Macken 1993](https://www.researchgate.net/publication/232417838_Irrelevant_tones_produce_an_irrelevant_speech_effect_Implications_for_phonological_coding_in_working_memory) · [Torcoli et al. 2019](https://salford-repository.worktribe.com/output/1360952/preferred-levels-for-background-ducking-to-produce-esthetically-pleasing-audio-for-tv-with-clear-speech) · [Resti et al. 2023](https://arxiv.org/abs/2305.19100) · [ANSI S3.5-1997 SII](https://www.researchgate.net/publication/324581011_SII-Speech_intelligibility_index_standard_ANSI_S35_1997) · [Herrmann & Johnsrude 2020](https://doi.org/10.1177/2331216520967850) · [Ji et al. 2024](https://journals.sagepub.com/doi/10.1177/21582440241257357) · [Robotic storytelling 2024](https://www.sciencedirect.com/science/article/pii/S2949882124000458) · [Locke 2009](https://www.cambridge.org/9780521877930) · [Monelle 2006](https://muse.jhu.edu/pub/3/monograph/book/4023) · [Tagg & Clarida 2003](https://www.iaspm.net/review/taggclarida.htm) · [Gufeng music (Wikipedia)](https://en.wikipedia.org/wiki/Gufeng_music) · [Bardo 2017](https://webdocs.cs.ualberta.ca/~santanad/papers/2017/padovaniFL17.pdf) · [Won et al. 2021](https://arxiv.org/abs/2111.13468) · [Sonus Texere 2022](https://arxiv.org/abs/2212.01033) · [M2M-Gen 2024](https://arxiv.org/pdf/2410.09928)

Cited from standard knowledge, not fetched today: Gorbman, *Unheard Melodies* (1987); Salamé & Baddeley (1989); Cooke, "A glimpsing model of speech perception in noise", *JASA* 119(3) (2006); Salamon & Gómez, Melodia, *IEEE TASLP* (2012); Lartillot & Toiviainen, MIRtoolbox, DAFx (2007); Rouard, Massa, Défossez, Hybrid Transformer Demucs, ICASSP (2023); Radford et al., Whisper (2022); Summers, *Understanding Video Game Music* (2016, existence verified, content not).

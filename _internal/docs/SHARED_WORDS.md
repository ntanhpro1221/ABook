# Shared words: a learned table decides Vietnamese or English

sea-g2p holds 231 words in both of its dictionaries, 227 with two different sounds (`do`, `sang`, `bay`, `to`, `so`...). It
gives each run of such words the language of the nearest unambiguous neighbour, English on a tie, and an unknown ASCII word
(a name) counts as English: "con boss **to** quá", "quay **sang** Susan", "Lucy **bay**" come out /tuː/, /sæŋ/, /beɪ/. The
root cause and the phoneme-level repair (`restore_vietnamese`: swap a stand-in word into the G2P input only, the spoken
string never changes) are section 6 of [TEXT_NORMALIZATION.md](TEXT_NORMALIZATION.md).

This file is about the DECISION: which occurrences are Vietnamese. Three rounds of hand rules (word lists, 146 compound
pairs, "before English" exceptions) each fixed the cases already seen and left a new blind sample with new misses. The rules
are gone; `phoneme_policy.vietnamese_shared` (Python) = `PhonemePolicy.vietnameseShared` (Kotlin) now add up a score from
one table, `abook/readaloud/shared_words.json`, and claim the word when the score reaches the threshold.

## What is scored

A sentence is seen as the engine sees it: the normalized chunk plus the ASCII words written with a capital mid-sentence.
Every word gets one of these kinds: `V` Vietnamese syllable with a diacritic, `o` other non-ASCII, `n` capital mid-sentence
(a name), `X` an `<en>` span, `e` certainly English, `s` in both sea-g2p dictionaries with two sounds, `h` toneless
Vietnamese syllable that is also an English word, `a` toneless syllable that is not, `f` any other ASCII word (names,
romaji). A neighbour across `. ! ? ; : …` is no neighbour (`^`); across a comma it only counts as Vietnamese-like or not
(`,v` / `,x`).

The score of one occurrence, all integers (hundredths of a logit):

| term | table key | what it says |
|---|---|---|
| the word itself | `words[w].p` | how the word behaves over the corpus: how often it is capitalised, tagged, read English, stands between two Vietnamese words |
| kind of the left / right neighbour | `words[w].l[kind]`, `.r[kind]` | per word: `sang` after a name is Vietnamese, `in` after a name is a Korean syllable |
| that very neighbour | `words[w].L[word]`, `.R[word]` | how much more often this neighbour stands beside the word when it is Vietnamese than its kind alone predicts ("so **sánh**", "**ban** nãy", "say **xỉn**") |
| the two neighbours together | `pair[5 x 5]` | e.g. name + word + Vietnamese word |
| the word one further out | `second.L`, `second.R` | Vietnamese with a diacritic, toneless, something else, nothing |
| both neighbours foreign | `words[w].f` | "Julius **sang** Emily" against "Big **Bang** Theory" |
| no diacritic in the chunk | `no_diacritics` | an all-ASCII sentence is seldom Vietnamese |
| share of the chunk that is certainly English / accented Vietnamese | `english_share`, `vietnamese_share` | |
| the text layer tagged the word `<en>` | `tagged` | a single tagged word can still be claimed ("`<en>the</en>` thé") |
| the word is doubled | `words[w].x` | per word: "hi hi", "lay lay" are Vietnamese, "go go", "no no" are not |

A word written with a capital mid-sentence is a name and is never claimed (unchanged from the rules; see the ceiling below).

**Which words are in the table: 72.** Only words whose bare spelling sea-g2p's Vietnamese dictionary reads as a level-tone
syllable. For the others the "Vietnamese" sound is a guess at a missing diacritic, not the word: `cat` -> "cát", `met` ->
"mệt", `pa` -> "pà", `gun` -> "gùn". Claiming those would trade one wrong sound for another ("óp-**pa**" became "óp pà" in
the first trial). One exception kept from the rules: `toe` ("toe toét").

## How the table is made

Nothing in the table is written by hand. It is fitted in three steps from the private corpus (`Corpus/_full`, read-only;
no story text enters the repository):

1. **Corpus statistics, no labels.** The runtime view of every sentence that holds a shared word, from series whose
   name hash never served a test sample (sha1 residues 5-11 mod 12 for truyen / sang-tac, 5-29 mod 30 for ai-dich):
   5,050 series, 1.74 million chunks, 1,883,791 occurrences of 197 words, 111,019 of them read English by sea-g2p or
   tagged by the text layer (the only occurrences the decision can change). From these: per-word behaviour counts, and a
   two-stage EM mixture (Vietnamese / not) that yields per-word neighbour-kind tables and the neighbour identity ratios
   (smoothed observed / expected, 35,368 kept).
2. **Labelled rows.** 1,410 occurrences that sea-g2p reads English, each labelled Vietnamese / English / name-romaji /
   sound / unclear from its context only: the five earlier samples (design + four holdouts, labels sealed before any
   evaluation), 1,130 rows drawn from the training pool (random, closest-to-threshold, doubled words; labelled without
   seeing any score), the repository's own fixture and 19 self-written anchor sentences.
3. **Calibration.** One regularised logistic regression with GLOBAL weights over the statistics of step 1, plus small
   per-word corrections (bias, doubled-word weight, neighbour-kind weights) shrunk hard toward zero. Real English weighs
   3, romaji / Korean syllables / sounds 0.3 (either sound is tolerable there), threshold 0. The weights are folded into
   the per-word integer table, so the runtime only adds integers. Python float model and integer table agree on all
   1,520 labelled rows that can be scored.

Because the weights are few and global, a word with no labelled row still gets its decision from its corpus statistics;
because real English weighs most, the fit prefers leaving a Vietnamese word English over the reverse.

The fitting scripts and the labelled rows hold story sentences and therefore live outside the repository (the task
scratch folder `g2pvi4/work`: `extract_train.py`, `build_rows.py`, `em5.py`, `model6.py`, `fit6.py`, `loso.py`,
`pool?_labelled.jsonl`). `scripts/build_shared_words.py` only writes the Kotlin copy (`vieneu/SharedWords.kt`) of the
JSON; `tests/test_shared_vietnamese.py` and `PhonemePolicyTest` check that the two are the same table and that both
front ends give the same claims and phonemes on `tests/fixtures/readaloud/shared_vietnamese/cases.json`.

## Measurements

See the dated entry in [TEST_REPORT.md](TEST_REPORT.md) for the five-sample table, the leave-one-sample-out table, the
fifth (verdict) sample drawn after the table was frozen, latency and the corpus-weighted estimate.

## Two tiers: the table, then the book's own answers

The table alone leaves a ceiling (next section). Since g2pvi5 the decision has two tiers.

**Tier 1** is the table, on every platform, with no model. `shared_word_verdicts` (Python) = `sharedWordVerdicts`
(Kotlin) returns for each occurrence the claim AND whether it is sure. An occurrence is in doubt when

- its prose score is in `doubt` = [-100, 0) of `shared_words.json` (just below the threshold);
- it is written as a name (capital mid-sentence, or a shouted word in a sentence that is not all shouting) and scores
  at least `name_doubt` = 0, i.e. prose would have called it Vietnamese ("guild **Say** xỉn", "[**Bay** Lv0]");
- it has the borrowed-noun shape whatever the score: the word opens a sentence, then a certainly English word, then
  an accented Vietnamese one ("**Do** trans sắp thi").

The capital rule reads the WRITTEN text (`source`), not the lower-cased spoken string, so "admin BAN nick" and
"Lalaport TOKYO BAY" stay English; name particles ("gia tộc de Valis", "Hikaru no Go") are never claimed.
A doubt keeps tier 1's guess (English, except prose at or above the threshold) until a ruling says otherwise.

**Tier 2** runs once per book in Studio, after analysis and before music (`worker.run_shared_rulings_after_analysis`,
`readaloud/shared_rulings.py`), with the project's analysis model through Ollama: temperature 0, seed from the model
digest and the prompt, JSON schema, eight questions per call. It answers two kinds of question:

- **each doubtful occurrence**, with its sentence, the neighbouring sentences and the character roster: Vietnamese
  word, Vietnamese name, English word or foreign name. Only "Vietnamese word" claims the word.
- **each roster name**: Vietnamese, Japanese, Korean or other. A Vietnamese name ("An", "Long", "Sơn" typed "Son")
  is read Vietnamese when written as a name, when in doubt in prose, or when it opens a sentence with no English
  word after it ("An An.", "Ban?"). A Japanese or Korean name gets its own romanization reading, name by name:
  "Chiaki" in a book of unknown origin, "Jieun" in a Japanese book. "Other" changes nothing.

The answers are stored in the project (`shared_rulings.json`) and travel in the `.abook` as `sharedWords` of
`book.json` ([ABOOK_FILE_FORMAT.md](ABOOK_FILE_FORMAT.md)), so the phone and the PC player apply them without a model.
An occurrence is keyed by its two words on each side (`shared_word_contexts`), so the same answer is found again
wherever the same words meet. A book with rulings puts a `w` + 16 hex tag in its clip keys.

**Listen-now** (a text-only book that never went through Studio) has tier 1 only: "An An." and "Do trans sắp thi."
read English there, and a name is read by the book-level guess as before.

Why these bands (311 design rows, analysis model on CPU): in prose [-100, 0) the model finds 22 of 26 Vietnamese
words and loses 3 of 5 real English ones; in [-200, -100) it loses 18 of 33 real English words, so the band stops at
-100. No band makes the sure part 99.5 % right: the widest tried, [-800, 100), reaches 99.26 % with 22 % of the
occurrences in doubt. Refitting the table with "Do <borrowed noun>" anchors moved "Do trans sắp thi." only from
-169 to -68 and flipped Korean "Do Hyun" to Vietnamese, hence the shape rule. Making the shape Vietnamese at tier 1
was tried and dropped: it also turns "Say goodbye đi." Vietnamese, and the sixth sample holds no row of the shape.

## What tier 1 cannot decide (the ceiling)

- **A Vietnamese word written with a capital mid-sentence** ("Rust Monster **Ban** đầu là...", "guild **Say** xỉn",
  the Vietnamese name "**An**"): a capital is a name by rule. Most capitals are names ("Leo", "Do Cheol-ho", "Sang-hyun").
- **Toneless Vietnamese typed without diacritics** ("ba **met**", "**rat** nhiều"): the word is outside the table on
  purpose; sea-g2p's Vietnamese sound would be another word.
- **Name + word + Vietnamese word, for a word that is usually a foreign syllable there** ("Leila **in** qua khe cửa"
  against "Yang Hye **in** lập tức"): the context kinds are identical; only knowing the name's language would tell.
- **A sentence-initial word before an English noun** ("**Do** trans sắp thi" against "**Do** exercise đi"): same kinds on
  both sides. Tier 1 says English and marks the doubt; tier 2 decides (and called the invented "Do exercise đi." Vietnamese).
- **A word that is not in the table** ("**Dan**!" reads Vietnamese /zaːn/): no tier looks at it.
- **Typos that split a word** ("Sauk hi" for "Sau khi"): `hi` after an unknown ASCII word now stays English.
- **A name followed by a two-syllable Vietnamese word whose first syllable is in the table** ("Regulus bang hoàng"): mostly right ("Lisa hi vọng", "Albert say mê"), not always.
- **Text that is ambiguous to a reader too**: stutters ("to, to, toire"), a lone "Ban.", sounds that work in either
  language ("pa pa pa", "bang bang").

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

## What it cannot decide (the ceiling)

- **A Vietnamese word written with a capital mid-sentence** ("Rust Monster **Ban** đầu là...", "guild **Say** xỉn",
  the Vietnamese name "**An**"): a capital is a name by rule. Most capitals are names ("Leo", "Do Cheol-ho", "Sang-hyun").
- **Toneless Vietnamese typed without diacritics** ("ba **met**", "**rat** nhiều"): the word is outside the table on
  purpose; sea-g2p's Vietnamese sound would be another word.
- **Name + word + Vietnamese word, for a word that is usually a foreign syllable there** ("Leila **in** qua khe cửa"
  against "Yang Hye **in** lập tức"): the context kinds are identical; only knowing the name's language would tell.
- **A sentence-initial word before an English noun** ("**Do** trans sắp thi" against "**Do** exercise đi"): same kinds on
  both sides; the rules had a hand list of borrowed nouns for it.
- **Text that is ambiguous to a reader too**: stutters ("to, to, toire"), a lone "Ban.", sounds that work in either
  language ("pa pa pa", "bang bang").

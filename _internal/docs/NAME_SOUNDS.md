# Name sounds: syllables of a romanized name the voice cannot say as written

2026-11-10, revised 2026-11-11 after the owner listened; branch `dev/koeun`. Data: `abook/readaloud/name_sounds.json`. Code: `phoneme_policy.respell_rare_rimes`,
`repair_level_tone` (Python) = `PhonemePolicy.respellRareRimes`, `repairLevelTone` (Kotlin, the build hands the JSON
over as `BuildConfig.NAME_SOUNDS`). Shared cases: `tests/fixtures/readaloud/phoneme_delivery/cases.json`.

## The complaint

"Jieun" is spoken "Gi-ưn" (`names.py`, Korean Revised Romanization). The owner: "it is still *ưng* where it must
be *ưn*; and the two syllables are a little too far apart, only a little".

## Rule kept

Only phoneme strings that sea-g2p itself makes from a Vietnamese spelling (owner, 10-11): no IPA dictionary of our
own, no pitch or formant change. So the repair is a *spelling* handed to the phonemizer; the spoken text, the
transcript and the word timing keep "Gi-ưn".

## Which syllables are rare

Every syllable the name romanizers can emit was counted in the corpus (13,374 sampled chapter files, 61 M words;
344,544 Japanese-name and 67,839 Korean-only name occurrences, 710 distinct target syllables), against its
frequency in Vietnamese prose, which is what VieNeu learned from.

| rime | name syllables (occurrences) | in Vietnamese prose |
|---|---|---|
| ưn /ɯn/ | ưn 486, nưn 259, xưn 223, cưn 44, gưn 17 | 0.8 per million syllables |
| ưm /ɯm/ | rưm 225, ưm 32, cưm 25, xưm 8, nưm 5 | with an onset: under 0.1 per million; bare "ưm": 35.5 per million |

"ưm" is rare too, but it is NOT respelled (owner, 11-11, see "ưm stays" below). The bare syllable "ưm" is also a
Vietnamese interjection ("Ưm, được rồi."): 2,173 occurrences in prose against 32 in names (Soleum).

Everything else the romanizers emit is a common Vietnamese syllable or was heard right ("éc", "eng" as rimes: no
change).

A second class is not rare but mis-phonemized: sea-g2p gives a tone to a few syllables written without a tone mark,
because its dictionary holds them as other words - "un" /ˈu2n/ (as "ùn"), "gin" /zˈi2n/, "pa" /pˈaː2/, "pan"
/pˈaːɜn/, "sun", "gun", "nun", "mum", "eng". In names: un 4,219 (Hyun, Seoul), gin 3,623 (Jin), pa 1,275, pan 600,
sun 219, gun 70, nun 33, mum 20, eng 17.

## Choosing the spelling for "ưn"

VieNeu v3 Nano on CPU, voice Adam, three carriers ("X gật đầu.", "Đó là X.", "X!") by three seeds; judge 1 is
faster-whisper large-v3-turbo free transcription, judge 2 an LDA on the log-mel of the last 80 ms before the closure,
trained on 80 real Vietnamese syllables (-n against -ng; leave-one-rime-out 98.75 %).

| spelling given | phonemes | heard with -n | what the machine wrote |
|---|---|---|---|
| Gi-ưn (before) | `zˈi ˈyn` | 4/9 | "ưng" 5/9 |
| Gi-ừn | `zˈi ˈy2n` | 2/9 | "ừng" |
| Gi-ứn | `zˈi ˈyɜn` | 1/9 | "ứng" |
| **Gi-ân** | `zˈi ˈən` | **9/9** | "ân" |
| Gi-ơn | `zˈi ˈəːn` | 9/9 | "ơn", "Zion" |
| Gi-ươn | `zˈi ˈɯən` | fails before g, k | "ương" |
| Gi-uơn | | 3 syllables | |
| Giưn | `zˈyn` | loses the "i" | |

"ân" /ən/ is the nearest vowel to /ɯ/ that keeps the final in every seed (short, central, unrounded; "ơn" is long
and is heard as English "Zion"). The same holds in other names: Ha-nưn -> "Ninh", "Nưng"; Ha-nân 6/6 -n; Xưn-ki ->
"Xin", "Sưng"; Xân-ki 6/6; Ân-gi 6/6. So `rimes` is `{"ưn": "ân"}`; "ưng" is a common rime and is not touched.
The owner listened on 11-11: "ưng" before, "ân" now - kept.

## "ưm" stays

On 2026-11-10 "ưm" was respelled "âm" on the transcriber's word alone (A-rưm -> "dưng", "rừng", "Rương"; A-râm
keeps -m 6/6). The owner listened on 11-11 and heard the opposite: "Gieo-rưm" (before) is right, "Gieo-râm" (after)
is wrong. The rule is gone: every "ưm" syllable of a name is said as written (`ɹˈym`, `kˈym`, `ˈym`).

Why the machine was wrong: the transcriber has no word "rưm", so for a right "rưm" it writes the nearest real word.
Seven sentences (Yeoreum x2, Areum x2, Boreum, Geum, Soleum), the app's seed and seeds 1-3, 28 clips each way:

| | what the machine wrote |
|---|---|
| "ưm" as written (now) | "rưm" 1, "ưm" 1, "rừng" 5, "dương" / "dưng" / "rương" 7, "cơm" 4, "ươm" / "ơm" 2, others 8 |
| "âm" (10-11, removed) | "râm" / "dâm" / "câm" / "âm" 23 of 28 |

So a free transcription cannot judge this rime, and a forced choice between spellings only asks the same
vocabulary again. The owner's ear is the judge here; the table is kept as the record of the mistake.

## The gap between the two syllables

Measured on the audio of "X gật đầu.", five seeds: the interval between the two vowel nuclei, the depth of the
energy dip between them and the time spent more than 6 dB under the lower nucleus.

| | interval | dip | under -6 dB |
|---|---|---|---|
| Gi-ưn (before) | 0.210 s | 36 dB | 0.092 s |
| Gi-ân (now) | 0.174 s | 14 dB | 0.054 s |
| Vietnamese two-syllable words with a vowel-initial second syllable (dị ứng, chị em, bí ẩn, kỳ ảo, chú ý, cô ấy ...), median | 0.18 s | 20 dB | 0.06-0.08 s |

The long gap was the voice hesitating before a syllable it does not know, not the join: with "ân" the name sits
inside the range of ordinary words. The joined delivery (`a‿b`, `japanese_delivery.py`) was tried on the same names
and swallows syllables on Nano - "Gi‿ưn" is heard "Xin", "Dinh", "Jim"; "Ha‿ru‿tô" "Hà tô", "How to"; "Chi‿a‿ki"
"Chi thi" in one seed of three - so names stay spaced, as "Chi-a-ki" (which the owner confirmed) already was.

## What is not done

- A short English name inside a sentence can be swallowed by Nano: "Rồi Dan quay sang nhìn Tom." lost "Dan" in one
  seed of three, "Rồi Ben ..." likewise; 2 of 27 clips (Dan, Ben, Ken in three carriers by three seeds), both right
  after "Rồi"; Jack and Bob, English before this branch, 0 of 18.
- "Hi-un U" (Hyun Woo): the tone is level now, but the transcriber writes "Hinh U" / "Hiêng U" in two seeds of
  three - three vowels in a row; not judged right.
- "min", "pin" are read with English /ɪ/ by sea-g2p; not in the `level` list (a different fault, not measured here).
- The numbers are Nano on CPU. The rime is absent from the training speech of every VieNeu tier, but the other
  tiers were not measured.

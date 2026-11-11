# Name sounds: syllables of a romanized name the voice cannot say as written

2026-11-10, revised 2026-11-11 after the owner listened; branch `dev/koeun`. Data: `abook/readaloud/name_sounds.json`. Code: `phoneme_policy.respell_rare_rimes`,
`repair_level_tone`, `restore_unread_words`, `foreign_names` (Python) = `PhonemePolicy.respellRareRimes`, `repairLevelTone`,
`restoreUnreadWords`, `foreignNames` (Kotlin, the build hands the JSON over as `BuildConfig.NAME_SOUNDS`). Shared cases:
`tests/fixtures/readaloud/phoneme_delivery/cases.json`.

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

## Vietnamese words sea-g2p has no Vietnamese sound for (`unread`, and more of `level`)

"min" and "pin" were noticed in names (Min-ji, Ha-min); the fault is a class. Every valid Vietnamese syllable that
is written in plain ASCII letters without a tone mark (1,125: onsets by open and nasal-final rimes) was phonemized
as written and again with a grave mark; the two must agree once the tone is taken off. 1,024 agree, 15 differ
only by a tone, 85 otherwise, one is split in two. The ones that differ were counted in the corpus sample
(13,374 files, 61 M words; "lower" = standing alone in lower case, "Vietnamese" = of those, beside a word with a
Vietnamese diacritic; capitalized and hyphenated uses are names).

| word | sea-g2p as written | now | lower / Vietnamese | capitalized / in a hyphenated name | seen in |
|---|---|---|---|---|---|
| pin | `pˈɪn` (English "pin") | `pˈin` | 441 / 332 | 772 / 0 | đèn pin, hết pin |
| veo | `vˈiːəʊ` | `vˈɛw` | 210 / 150 | 0 / 0 | trong veo, sạch veo |
| boa | `bˈoʊə` | `bwˈaː` | 18 / 17 | 14 / 0 | tiền boa |
| min | `mˈɪn` | `mˈin` | 35 / 1 | 210 / 392 | Min-ji, Ha-min, Kim Min-jun |
| qui | `kwj` (no vowel) | `kwˈi` | 34 / 26 | 1 / 1 | bánh qui, qui định |
| gim | `zm` (no vowel) | `zˈim` | 2 / 1 | 9 / 0 | kẹp gim; "Jim-in" is spoken "Gim-in" |
| quim, quinh, ginh | `kwjm`, `kwjɲ`, `zɲ` (no vowel) | `kwˈim`, `kwˈiɲ`, `zˈiɲ` | 1-2 / 0 | 0 | same broken class, kept whole |

The reading is sea-g2p's own for the same syllable written with a grave mark ("pìn", "vèo", "boà", "mìn", "quì"),
less the tone - the rule above. ("bòa", the new-style placement, is itself misread `bˈɔ2`; "boà" is right.)
The word keeps its English sound where the word right before or right after it, with no punctuation between, is
certainly English ("Pin it on the board.", "Min max", an `<en>` span); "Hết pin. It is over." is Vietnamese then
English.

The same audit found six more syllables that sea-g2p gives a tone; they joined `level`:

| word | sea-g2p as written | now | lower / Vietnamese | seen in |
|---|---|---|---|---|
| toe | `t̪wˈɛɜ` (as "toé") | `t̪wˈɛ` | 590 / 582 | cười toe toét |
| vin | `vˈi6n` | `vˈin` | 26 / 25 | vin vào |
| toong | `t̪wˈɔ2ŋ` | `t̪wˈɔŋ` | 23 / 13 | ba toong |
| sia | `sˈiə6` | `sˈiə` | 3 / 0 (capitalized 88) | the name Sia |
| poong, vim | `pwˈɔ6ŋ`, `vˈi6m` | `pwˈɔŋ`, `vˈim` | 1-2 / 0 | - |

Found and left alone, with the reason:

- "poi" `pˈɔɪ` (10 / 8): the English diphthong is the same sound as Vietnamese "oi".
- "moe" `mˈoʊ` (112 / 65): the Japanese loan "moe", not a Vietnamese word; neither reading is right.
- "trim", "by", "buy", "try", "pay", "guy", "on", "them": English words that only look like a toneless syllable;
  0-3 uses beside a Vietnamese word, except "them" (8, the unmarked typing of "thêm").
- "ten" `t̪ˈen` (60 / 51, "tèn ten"), "ben", "den", "din", "gong", "pong": sea-g2p's Vietnamese dictionary reads
  them with a close vowel. A different fault (no English sound, no tone), not measured.
- "quin", "gum", "pun", "pam", "pom", "pon", "doe", "roe", "loen": 0 uses beside a Vietnamese word.
- "cho", "khi", "la", "ma", "thi", "va", "vi", "du" differ only in stress (function words); "boong", "xoong",
  "coong" are read `ˈɔŋ` both ways. Not faults.

## A Western roster name spelled like a Vietnamese syllable (`foreign_onsets`)

"Dan", "Tom", "Ben", "Ken" of a Western roster are Vietnamese syllables to sea-g2p ("dan" /zaːn/), and no `<en>` tag
changes that. koeun (2026-11-10) gave them the English sound through the possessive ("dan's" /dˈænz/ less the /z/):
/dˈæn/, /tˈɑːm/, /bˈɛn/, /kˈɛn/. The owner heard "Rồi Dan quay sang nhìn Tom." at the app's seed with no "Dan" at all,
and koeun had already lost "Dan" and "Ben" right after "Rồi" in 2 clips of 27.

Measured (VieNeu v3 Nano, CPU, voice Adam; transcriber faster-whisper large-v3-turbo with word timestamps; the slot
between the carrier's neighbour words is "swallowed" when no word is written there, "short" when the word there
lasts under 0.12 s). Six carriers per name - "Rồi X quay sang nhìn tôi.", "Và X cũng gật đầu.", "Nếu vậy thì X sẽ đi
trước.", "X mở cửa bước vào.", "Tôi thấy X đứng ở cổng trường.", "Người mở cửa là X." - plus the owner's "Rồi X quay
sang nhìn Tom." for Dan; five seeds each: the app's seed of the sentence, then 1-4.

| name | phonemes | from | clips | right | swallowed | short | other word | bad at the app's seed |
|---|---|---|---|---|---|---|---|---|
| Dan | `dˈæn` | English possessive (koeun) | 35 | 32 | 1 | 1 | 1 | 1 ("Rồi, quay sang nhìn Tom.") |
| Dan | `zˈaːn` | Vietnamese "dan" | 35 | 0 | 0 | 0 | 34 ("Gian") | - |
| Dan | `ɗˈaːn` | Vietnamese "đan" | 35 | 34 | 0 | 1 | 0 | 0 |
| Dan | `ɗˈɛn` | Vietnamese "đen" | 35 | 35 | 0 | 0 | 0 | 0 |
| Ben | `bˈɛn` | English possessive | 30 | 28 | 2 | 0 | 0 | 1 |
| Ben | `bˈen` | Vietnamese "ben" | 30 | 26 | 1 | 2 | 1 | 0 |
| Ken | `kˈɛn` | English = Vietnamese "ken" | 30 | 29 | 1 | 0 | 0 | 1 ("Rồi, quay sang nhìn tôi.") |
| Tom | `tˈɑːm` | English possessive | 30 | 28 | 0 | 0 | 2 | 0 |
| Tom | `t̪ˈɔm` | Vietnamese "tom" | 30 | 30 | 0 | 0 | 0 | 0 |
| Sam | `sˈæm` / `sˈaːm` | English / Vietnamese | 30 / 30 | 30 / 30 | 0 | 0 | 0 | 0 |
| Lan, Nam (Vietnamese names) | `lˈaːn`, `nˈaːm` | Vietnamese | 30 / 30 | 29 / 30 | 0 | 0 | 1 / 0 | 0 |

A second round put one syllable at a time into the same slot of three carriers ("Rồi X quay sang nhìn tôi.", "Sau
đó X quay sang nhìn tôi.", "Và X cũng gật đầu.") by ten seeds (the app's, then 1-9), 30 clips a syllable:

| syllable | from | swallowed | short | note |
|---|---|---|---|---|
| `ɗˈaːn` | "đan" | 0 | 0 | |
| `lˈaːn` | "lan" (control) | 0 | 0 | |
| `t̪ˈɔm` | "tom" | 0 | 1 | |
| `kˈɛn` | "ken" = English | 1 | 0 | at the app's seed of "Rồi Ken ..." |
| `ɗˈɛn` | "đen" | 1 | 1 | |
| `dˈɛn` | English "den" | 1 | 1 | heard "đen" otherwise |
| `dˈæn` | English possessive "dan's" | 2 | 1 | |
| `tˈɑːm` | English "tom's" | 0 | 3 | |
| `bˈɛn` | English "ben's" | 2 | 2 | |
| `bˈen` | "ben" | 3 | 2 | |

The place is the cause as much as the syllable: every swallowed clip of both rounds but one stands right after "Rồi"
(the voice breaks after "Rồi" as after a comma, and a short level syllable with a close or front vowel - "en", "ɛn",
"æn" - is lost in the break); after "Sau đó" or "Và" nothing is swallowed. The syllables never lost have a long open
vowel the voice knows well (/aː/, /ɔ/): /ɗaːn/ 0 of 65, /laːn/ 0 of 60.

**Decision.** Such a name is read as the Vietnamese syllable it is spelled as, and only an onset letter that
Vietnamese reads otherwise is respelled: "d" -> "đ" (`name_sounds.json` "foreign_onsets"). "Dan" is "đan" /ɗˈaːn/ -
the owner's "đan", 0 swallowed in 35 - not "đen": /æ/ is between the two and "Đan" is how Vietnamese writes the name.
"Tom", "Ben", "Ken", "Sam" keep sea-g2p's Vietnamese reading of their spelling (`t̪ˈɔm`, `bˈen`, `kˈɛn`, `sˈaːm`), as
before koeun. The spoken text and the transcript keep "Dan"; the roster still decides which Dan is Western
(`shared_rulings.foreign_names`), and lower-case "dan" in prose is never touched.

## What is not done

- "Ben" is still lost or shortened in 3 clips of 30 as `bˈen` (2 of 30 as English `bˈɛn`): neither reading is a
  Vietnamese word the voice knows; no in-distribution spelling of "Ben" does better. "Jack" and "Bob", English
  before this branch, 0 of 18.
- "Hi-un U" (Hyun Woo) stays. Seven spellings were measured in four carriers by six seeds (`hˈi ˈun ˈu`, "Hiu-un U",
  "Hi-ơn U", "Hi-ân U", "Hiun U", "Hiên U", and `hˈiˌun ˈu` joined): the transcriber keeps the three sounds hi / un /
  u apart for the current spelling in 19 of 24 (17 as "hi un u", 4 of 4 at the app's seeds); "Hiu-un U" 18 of 24 but
  never with "hi" ("hiếu", "hu"), "Hi-ơn U" 18 of 24 but never with "un" ("an"), "Hiên U" 0. The five misses are
  all at the end of a sentence ("vị cứu tinh của Hyun Woo.": "hinh u", "hiêng u", "hyung u").
- The numbers are Nano on CPU. The rime is absent from the training speech of every VieNeu tier, but the other
  tiers were not measured.

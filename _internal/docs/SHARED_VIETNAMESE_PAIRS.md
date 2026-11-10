# Vietnamese shared-word compounds

> **Superseded (g2pvi4, policy version 6).** The `pairs` data described here was removed from `english_policy.json`; the decision is now the
> learned table of [SHARED_WORDS.md](SHARED_WORDS.md). This file is kept as the record of how the compound list was mined and what it measured.

Read-only mining covered all 227 different-sounding shared dictionary words in the exposed g2pvi residue-1 partition: 523 series, 9,212 chapters, 30,917,405 regex word tokens. The original whitespace-token count was 30,808,762; the tokenizer difference is intentional. The third holdout is excluded from mining.

Selection requires at least three occurrences in at least two series, an adjacent Vietnamese-only dictionary partner, a recognizable Vietnamese compound or reduplication, and 100% Vietnamese labels in the text-only reservoir (up to five windows per pair). Labels describe intended language, not the old engine output. Labels are model-only, not owner annotations; five windows do not prove population precision. Contexts stay outside git.

There were 22,856 observed pairs, 7,590 passed the frequency/series floor, and 145 lexical candidates were reviewed. Reject nonlexical juxtapositions, borrowed English phrases, names and unclear text. An nhien was rejected because every sampled occurrence was a name; loan truyen was rejected for unclear translation contexts. The only permitted pair containing `the` is `the thé`. Three prior common/common pairs remain. The resulting 146 pairs are data in english_policy.json.

Only shared dictionary members enter pair_words. Newly added pair_only_words retain their old English contextual classification until a compound proves them Vietnamese. Otherwise merely adding thin to the search set would wrongly pull man in "The thin man đến rồi" into Vietnamese. Mid-sentence capitals and explicit English spans remain protected, including a capitalized compound partner.

The clause-start experiment accepts only do + trans + an immediately adjacent accented Vietnamese word. Arbitrary do + English and so + English are unsafe ("Do exercise đi", "So cute quá"). A separate bounded borrowing entry allows in + logo with a proven Vietnamese word immediately before in; other in + English phrases keep their old behavior. All lists live in the same shared JSON, with matching Python/Kotlin consumers.

The app version is unchanged. The pronunciation policy version changes from 4 to 5, giving cached clips the direct-en5 namespace so old audio cannot hide the phoneme correction. This cache-only follow-up does not alter the frozen decisions or spoken bytes. The quality implementation hash changes.

| Pair | Corpus occurrences | Series | V labels / total | Accepted |
|---|---:|---:|---:|---|
| lý do | 12094 | 442 | 5/5 | yes |
| im lặng | 6405 | 421 | 5/5 | yes |
| ban đầu | 3875 | 394 | 5/5 | yes |
| may mắn | 3450 | 400 | 5/5 | yes |
| an toàn | 3265 | 367 | 5/5 | yes |
| do dự | 2454 | 338 | 5/5 | yes |
| tự do | 2072 | 339 | 5/5 | yes |
| lí do | 1979 | 166 | 5/5 | yes |
| tan biến | 1664 | 308 | 5/5 | yes |
| to lớn | 1646 | 298 | 5/5 | yes |
| ban nãy | 1643 | 219 | 5/5 | yes |
| bất an | 1634 | 262 | 5/5 | yes |
| can thiệp | 1158 | 269 | 5/5 | yes |
| an ủi | 1103 | 288 | 5/5 | yes |
| an nhiên | 1060 | 9 | 0/5 | no |
| hi vọng | 830 | 177 | 5/5 | yes |
| an tâm | 728 | 230 | 5/5 | yes |
| ban đêm | 715 | 221 | 5/5 | yes |
| can đảm | 706 | 245 | 5/5 | yes |
| ban nhạc | 705 | 38 | 5/5 | yes |
| ban ngày | 636 | 223 | 5/5 | yes |
| trấn an | 590 | 217 | 5/5 | yes |
| bình an | 588 | 165 | 5/5 | yes |
| an ninh | 569 | 141 | 5/5 | yes |
| lay động | 553 | 161 | 5/5 | yes |
| mảy may | 544 | 158 | 5/5 | yes |
| to tát | 526 | 194 | 5/5 | yes |
| toe toét | 521 | 180 | 5/5 | yes |
| tan chảy | 508 | 189 | 5/5 | yes |
| ủy ban | 484 | 49 | 5/5 | yes |
| máy bay | 474 | 84 | 5/5 | yes |
| gay gắt | 474 | 188 | 5/5 | yes |
| sang trọng | 471 | 201 | 5/5 | yes |
| lung tung | 455 | 190 | 5/5 | yes |
| im bặt | 392 | 164 | 5/5 | yes |
| liên bang | 389 | 24 | 5/5 | yes |
| bay lượn | 353 | 120 | 5/5 | yes |
| vận may | 349 | 128 | 5/5 | yes |
| than vãn | 343 | 153 | 5/5 | yes |
| ban công | 342 | 99 | 5/5 | yes |
| tan vỡ | 333 | 156 | 5/5 | yes |
| tung bay | 329 | 139 | 5/5 | yes |
| ngủ say | 325 | 149 | 5/5 | yes |
| tâm can | 320 | 113 | 5/5 | yes |
| non nớt | 311 | 130 | 5/5 | yes |
| than thở | 301 | 150 | 5/5 | yes |
| dây leo | 297 | 66 | 5/5 | yes |
| hi sinh | 291 | 114 | 5/5 | yes |
| lan can | 290 | 102 | 5/5 | yes |
| man rợ | 270 | 57 | 5/5 | yes |
| say sưa | 251 | 118 | 5/5 | yes |
| lay chuyển | 245 | 125 | 5/5 | yes |
| cam chịu | 244 | 123 | 5/5 | yes |
| am hiểu | 225 | 106 | 5/5 | yes |
| ôi chao | 220 | 73 | 5/5 | yes |
| say mê | 217 | 123 | 5/5 | yes |
| bang hội | 204 | 21 | 5/5 | yes |
| chao đảo | 193 | 103 | 5/5 | yes |
| to đùng | 173 | 93 | 5/5 | yes |
| dã man | 171 | 84 | 5/5 | yes |
| say đắm | 167 | 93 | 5/5 | yes |
| than phiền | 165 | 101 | 5/5 | yes |
| mông lung | 165 | 87 | 5/5 | yes |
| gang tấc | 156 | 99 | 5/5 | yes |
| cam lòng | 154 | 72 | 5/5 | yes |
| le lói | 143 | 83 | 5/5 | yes |
| miên man | 143 | 77 | 5/5 | yes |
| say rượu | 131 | 65 | 5/5 | yes |
| cam kết | 129 | 57 | 5/5 | yes |
| the thé | 125 | 67 | 5/5 | yes |
| lung linh | 125 | 80 | 5/5 | yes |
| can ngăn | 124 | 69 | 5/5 | yes |
| mỏ neo | 124 | 17 | 5/5 | yes |
| say xỉn | 119 | 67 | 5/5 | yes |
| đỏ hoe | 116 | 83 | 5/5 | yes |
| cam tâm | 112 | 57 | 5/5 | yes |
| van nài | 109 | 63 | 5/5 | yes |
| cam đoan | 106 | 68 | 5/5 | yes |
| than khóc | 105 | 46 | 5/5 | yes |
| then chốt | 96 | 51 | 5/5 | yes |
| máy in | 88 | 27 | 5/5 | yes |
| leo núi | 88 | 46 | 5/5 | yes |
| lon ton | 87 | 56 | 5/5 | yes |
| máu me | 87 | 61 | 5/5 | yes |
| no nê | 86 | 58 | 5/5 | yes |
| chao ôi | 86 | 46 | 5/5 | yes |
| leo thang | 84 | 61 | 5/5 | yes |
| in hằn | 80 | 46 | 5/5 | yes |
| hăng say | 73 | 55 | 5/5 | yes |
| núi non | 65 | 40 | 5/5 | yes |
| day dứt | 63 | 35 | 5/5 | yes |
| mê man | 59 | 44 | 5/5 | yes |
| can dự | 58 | 47 | 5/5 | yes |
| say khướt | 56 | 43 | 5/5 | yes |
| mầm non | 50 | 35 | 5/5 | yes |
| man mác | 46 | 30 | 5/5 | yes |
| bản in | 45 | 21 | 5/5 | yes |
| in đậm | 44 | 37 | 5/5 | yes |
| màu be | 42 | 31 | 5/5 | yes |
| non trẻ | 40 | 30 | 5/5 | yes |
| neo đậu | 39 | 25 | 5/5 | yes |
| khóc than | 38 | 31 | 5/5 | yes |
| éo le | 37 | 26 | 5/5 | yes |
| leo lét | 36 | 22 | 5/5 | yes |
| giấy in | 34 | 13 | 5/5 | yes |
| lan man | 33 | 27 | 5/5 | yes |
| no đủ | 31 | 18 | 5/5 | yes |
| mơn man | 31 | 23 | 5/5 | yes |
| thin thít | 30 | 26 | 5/5 | yes |
| lay lắt | 30 | 22 | 5/5 | yes |
| vàng hoe | 27 | 20 | 5/5 | yes |
| be bé | 26 | 19 | 5/5 | yes |
| son môi | 26 | 18 | 5/5 | yes |
| gay cấn | 24 | 22 | 5/5 | yes |
| be bét | 24 | 20 | 5/5 | yes |
| ngoại bang | 24 | 16 | 5/5 | yes |
| am tường | 22 | 12 | 5/5 | yes |
| lăm le | 20 | 18 | 5/5 | yes |
| thành bang | 20 | 5 | 5/5 | yes |
| đỏ son | 17 | 9 | 5/5 | yes |
| gang tay | 17 | 13 | 5/5 | yes |
| chao lượn | 17 | 9 | 5/5 | yes |
| he hé | 15 | 12 | 5/5 | yes |
| sum vầy | 13 | 8 | 5/5 | yes |
| le lưỡi | 13 | 9 | 5/5 | yes |
| van lơn | 12 | 9 | 5/5 | yes |
| sum họp | 11 | 11 | 5/5 | yes |
| sơn son | 9 | 4 | 5/5 | yes |
| loan truyền | 9 | 5 | 2/5 | no |
| canh me | 8 | 7 | 5/5 | yes |
| loan đao | 8 | 3 | 5/5 | yes |
| vắng hoe | 8 | 5 | 5/5 | yes |
| loan báo | 8 | 5 | 5/5 | yes |
| chồng son | 7 | 6 | 5/5 | yes |
| then cài | 7 | 6 | 5/5 | yes |
| son dưỡng | 7 | 6 | 5/5 | yes |
| lồng son | 7 | 3 | 5/5 | yes |
| then cửa | 5 | 5 | 5/5 | yes |
| gang thép | 4 | 2 | 4/4 | yes |
| chao liệng | 4 | 4 | 4/4 | yes |
| hăm he | 4 | 3 | 4/4 | yes |
| sum suê | 3 | 3 | 3/3 | yes |
| dưa gang | 3 | 3 | 3/3 | yes |
| tua bin | 3 | 3 | 3/3 | yes |
| in ấn | 29 | 21 | 5/5 | yes |

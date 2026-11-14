# TN benchmark

Two boundaries: text and production VieNeu G2P; no synthesis or acoustic accuracy claim.
Cloud engines (Edge/Azure/Google/FPT) perform their own TN and are outside this measurement.

| Category | N | Nghe ngay chuỗi | Nghe ngay sau G2P | Studio chuỗi | Studio sau G2P |
|---|---:|---:|---:|---:|---:|
| cardinal_small | 20 | 20/20 = 100.00% | 20/20 = 100.00% | 20/20 = 100.00% | 20/20 = 100.00% |
| cardinal_large | 20 | 10/20 = 50.00% | 10/20 = 50.00% | 10/20 = 50.00% | 10/20 = 50.00% |
| decimal | 20 | 7/20 = 35.00% | 14/20 = 70.00% | 7/20 = 35.00% | 14/20 = 70.00% |
| ordinal | 20 | 0/20 = 0.00% | 20/20 = 100.00% | 0/20 = 0.00% | 20/20 = 100.00% |
| roman | 20 | 17/20 = 85.00% | 19/20 = 95.00% | 17/20 = 85.00% | 19/20 = 95.00% |
| date | 20 | 2/20 = 10.00% | 19/20 = 95.00% | 2/20 = 10.00% | 19/20 = 95.00% |
| time | 20 | 1/20 = 5.00% | 16/20 = 80.00% | 1/20 = 5.00% | 16/20 = 80.00% |
| range | 20 | 1/20 = 5.00% | 15/20 = 75.00% | 1/20 = 5.00% | 15/20 = 75.00% |
| percentage | 20 | 0/20 = 0.00% | 17/20 = 85.00% | 0/20 = 0.00% | 17/20 = 85.00% |
| currency | 20 | 6/20 = 30.00% | 12/20 = 60.00% | 6/20 = 30.00% | 12/20 = 60.00% |
| unit | 20 | 0/20 = 0.00% | 17/20 = 85.00% | 0/20 = 0.00% | 17/20 = 85.00% |
| phone_code | 20 | 0/20 = 0.00% | 13/20 = 65.00% | 0/20 = 0.00% | 12/20 = 60.00% |
| abbrev_vi | 20 | 14/20 = 70.00% | 16/20 = 80.00% | 14/20 = 70.00% | 16/20 = 80.00% |
| abbrev_en | 20 | 7/20 = 35.00% | 7/20 = 35.00% | 7/20 = 35.00% | 7/20 = 35.00% |
| english | 20 | 20/20 = 100.00% | 20/20 = 100.00% | 20/20 = 100.00% | 20/20 = 100.00% |
| japanese | 20 | 14/20 = 70.00% | 14/20 = 70.00% | 14/20 = 70.00% | 14/20 = 70.00% |
| symbol | 20 | 2/20 = 10.00% | 14/20 = 70.00% | 8/20 = 40.00% | 14/20 = 70.00% |
| url_email | 20 | 0/20 = 0.00% | 4/20 = 20.00% | 0/20 = 0.00% | 5/20 = 25.00% |
| vocalization | 20 | 17/20 = 85.00% | 13/20 = 65.00% | 18/20 = 90.00% | 14/20 = 70.00% |
| punctuation | 20 | 20/20 = 100.00% | 20/20 = 100.00% | 20/20 = 100.00% | 20/20 = 100.00% |
| uppercase | 20 | 20/20 = 100.00% | 20/20 = 100.00% | 20/20 = 100.00% | 20/20 = 100.00% |
| game | 20 | 2/20 = 10.00% | 11/20 = 55.00% | 4/20 = 20.00% | 11/20 = 55.00% |
| **Overall** | 440 | 180/440 = 40.91% | 331/440 = 75.23% | 189/440 = 42.95% | 332/440 = 75.45% |

## Priority by post-G2P errors

| Hạng | Lớp | Số dấu hiệu mẫu | /100k từ | Sai sau G2P trung bình | Điểm ưu tiên |
|---:|---|---:|---:|---:|---:|
| 1 | symbol | 1968 | 167.463 | 30.0% | 50.239 |
| 2 | japanese | 1950 | 165.931 | 30.0% | 49.779 |
| 3 | abbrev_en | 151 | 12.849 | 65.0% | 8.352 |
| 4 | vocalization | 178 | 15.147 | 32.5% | 4.923 |
| 5 | cardinal_large | 100 | 8.509 | 50.0% | 4.255 |
| 6 | roman | 416 | 35.399 | 5.0% | 1.770 |
| 7 | decimal | 66 | 5.616 | 30.0% | 1.685 |
| 8 | game | 40 | 3.404 | 45.0% | 1.532 |
| 9 | currency | 28 | 2.383 | 40.0% | 0.953 |
| 10 | unit | 36 | 3.063 | 15.0% | 0.460 |

## Phoneme diagnostics: top five categories

Up to ten failing cases per category and path, in fixture order; all failures are shown when fewer exist.

### symbol / nghe_ngay: 6 cases

```json
{"id": "symbol_07", "text": "Trà / cà phê.", "expected": ["Trà hoặc cà phê.", "Trà trên cà phê."], "got": "Trà, cà phê.", "got_phonemes": "tʃˈaː2, kˈaː2 fˈe.", "expected_phonemes": ["tʃˈaː2 hwˌa6c kˈaː2 fˈe.", "tʃˈaː2 tʃˈen kˈaː2 fˈe."]}
```

```json
{"id": "symbol_09", "text": "Khay → hộp.", "expected": ["Khay sang hộp.", "Khay đến hộp.", "Khay chuyển thành hộp."], "got": "Khay thành hộp.", "got_phonemes": "xˈaj tˈe-2ɲ hˈo6p.", "expected_phonemes": ["xˈaj sˈaːŋ hˈo6p.", "xˈaj ɗˌeɜn hˈo6p.", "xˈaj tʃwˈiɛ4n tˈe-2ɲ hˈo6p."]}
```

```json
{"id": "symbol_10", "text": "Xếp hạng ★★★.", "expected": ["Xếp hạng ba sao.", "Xếp hạng sao sao sao."], "got": "Xếp hạng .", "got_phonemes": "sˈeɜp hˈaː6ŋ.", "expected_phonemes": ["sˈeɜp hˈaː6ŋ bˈaː sˈaːw.", "sˈeɜp hˈaː6ŋ sˈaːw sˈaːw sˈaːw."]}
```

```json
{"id": "symbol_12", "text": "Tính 5 − 2.", "expected": "Tính năm trừ hai.", "got": "Tính năm − hai.", "got_phonemes": "t̪ˈiɜɲ nˈam hˈaːj.", "expected_phonemes": ["t̪ˈiɜɲ nˈam tʃˈy2 hˈaːj."]}
```

```json
{"id": "symbol_16", "text": "Điểm ≠ 0.", "expected": "Điểm khác không.", "got": "Điểm không phải là 0.", "got_phonemes": "ɗˈiɛ4m xˌoŋ fˌaː4j lˌaː2 xˌoŋ.", "expected_phonemes": ["ɗˈiɛ4m xˈaːɜc xˌoŋ."]}
```

```json
{"id": "symbol_20", "text": "Nhãn A&B.", "expected": ["Nhãn a và bê.", "Nhãn ây và bi."], "got": "Nhãn A en B.", "got_phonemes": "ɲˈaː5n ˈaː ˈɛn bˈe.", "expected_phonemes": ["ɲˈaː5n ˈaː vˌaː2 bˈe.", "ɲˈaː5n ˈəɪ vˌaː2 bˈi."]}
```

### symbol / studio: 6 cases

```json
{"id": "symbol_07", "text": "Trà / cà phê.", "expected": ["Trà hoặc cà phê.", "Trà trên cà phê."], "got": "Trà, cà phê.", "got_phonemes": "tʃˈaː2, kˈaː2 fˈe.", "expected_phonemes": ["tʃˈaː2 hwˌa6c kˈaː2 fˈe.", "tʃˈaː2 tʃˈen kˈaː2 fˈe."]}
```

```json
{"id": "symbol_09", "text": "Khay → hộp.", "expected": ["Khay sang hộp.", "Khay đến hộp.", "Khay chuyển thành hộp."], "got": "Khay, hộp.", "got_phonemes": "xˈaj, hˈo6p.", "expected_phonemes": ["xˈaj sˈaːŋ hˈo6p.", "xˈaj ɗˌeɜn hˈo6p.", "xˈaj tʃwˈiɛ4n tˈe-2ɲ hˈo6p."]}
```

```json
{"id": "symbol_10", "text": "Xếp hạng ★★★.", "expected": ["Xếp hạng ba sao.", "Xếp hạng sao sao sao."], "got": "Xếp hạng .", "got_phonemes": "sˈeɜp hˈaː6ŋ.", "expected_phonemes": ["sˈeɜp hˈaː6ŋ bˈaː sˈaːw.", "sˈeɜp hˈaː6ŋ sˈaːw sˈaːw sˈaːw."]}
```

```json
{"id": "symbol_12", "text": "Tính 5 − 2.", "expected": "Tính năm trừ hai.", "got": "Tính năm − hai.", "got_phonemes": "t̪ˈiɜɲ nˈam hˈaːj.", "expected_phonemes": ["t̪ˈiɜɲ nˈam tʃˈy2 hˈaːj."]}
```

```json
{"id": "symbol_16", "text": "Điểm ≠ 0.", "expected": "Điểm khác không.", "got": "Điểm không phải là 0.", "got_phonemes": "ɗˈiɛ4m xˌoŋ fˌaː4j lˌaː2 xˌoŋ.", "expected_phonemes": ["ɗˈiɛ4m xˈaːɜc xˌoŋ."]}
```

```json
{"id": "symbol_20", "text": "Nhãn A&B.", "expected": ["Nhãn a và bê.", "Nhãn ây và bi."], "got": "Nhãn A en B.", "got_phonemes": "ɲˈaː5n ˈaː ˈɛn bˈe.", "expected_phonemes": ["ɲˈaː5n ˈaː vˌaː2 bˈe.", "ɲˈaː5n ˈəɪ vˌaː2 bˈi."]}
```

### japanese / nghe_ngay: 6 cases

```json
{"id": "japanese_04", "text": "Yuki-sama xếp khay.", "expected": ["Yu-ki-xa-ma xếp khay.", "Yư-ki-xa-ma xếp khay."], "got": "Giu-ki-xa-ma xếp khay.", "got_phonemes": "zˈu kˈi sˈaː mˈaː sˈeɜp xˈaj.", "expected_phonemes": ["jˈuː kˈi sˈaː mˈaː sˈeɜp xˈaj.", "ˈiˈy kˈi sˈaː mˈaː sˈeɜp xˈaj."]}
```

```json
{"id": "japanese_12", "text": "Sensei xem phiếu.", "expected": ["Xen-xê xem phiếu.", "Sen-sê xem phiếu."], "got": "xen-xây xem phiếu.", "got_phonemes": "sˈɛn sˈəɪ sˈɛm fˈiɛɜw.", "expected_phonemes": ["sˈɛn sˈe sˈɛm fˈiɛɜw.", "sˈɛn sˈe sˈɛm fˈiɛɜw."]}
```

```json
{"id": "japanese_13", "text": "Kouhai xem phiếu.", "expected": ["Cô-hai xem phiếu.", "Kô-hai xem phiếu."], "got": "Câu-hai xem phiếu.", "got_phonemes": "kˈə1w hˈaːj sˈɛm fˈiɛɜw.", "expected_phonemes": ["kˈo hˈaːj sˈɛm fˈiɛɜw.", "kˈaːˈo hˈaːj sˈɛm fˈiɛɜw."]}
```

```json
{"id": "japanese_14", "text": "Arigatou, xin nhận.", "expected": ["A-ri-ga-tô, xin nhận.", "A-ri-ga-tou, xin nhận."], "got": "a-ri-ga-tâu, xin nhận.", "got_phonemes": "ˈaː ɹˈi ɣˈaː t̪ˈə1w, sˈin ɲˈə6n.", "expected_phonemes": ["ˈaː ɹˈi ɣˈaː t̪ˈo, sˈin ɲˈə6n.", "ˈaː ɹˈi ɣˈaː tˈuː, sˈin ɲˈə6n."]}
```

```json
{"id": "japanese_15", "text": "Ohayou, mời vào.", "expected": ["Ô-ha-yô, mời vào.", "O-ha-yo, mời vào."], "got": "ô-ha-giâu, mời vào.", "got_phonemes": "ˈo hˈaː zˈə1w, mˈəː2j vˈaː2w.", "expected_phonemes": ["ˈo hˈaː ˈiˈo, mˈəː2j vˈaː2w.", "ˈo hˈaː jˈoʊ, mˈəː2j vˈaː2w."]}
```

```json
{"id": "japanese_20", "text": "Onee-chan đến.", "expected": ["Ô-nê-chan đến.", "O-nê-chan đến."], "got": "ô-ne-chan đến.", "got_phonemes": "ˈo nˈɛ tʃˈaːn ɗˌeɜn.", "expected_phonemes": ["ˈo nˈe tʃˈaːn ɗˌeɜn.", "ˈo nˈe tʃˈaːn ɗˌeɜn."]}
```

### japanese / studio: 6 cases

```json
{"id": "japanese_04", "text": "Yuki-sama xếp khay.", "expected": ["Yu-ki-xa-ma xếp khay.", "Yư-ki-xa-ma xếp khay."], "got": "Giu-ki-xa-ma xếp khay.", "got_phonemes": "zˈu kˈi sˈaː mˈaː sˈeɜp xˈaj.", "expected_phonemes": ["jˈuː kˈi sˈaː mˈaː sˈeɜp xˈaj.", "ˈiˈy kˈi sˈaː mˈaː sˈeɜp xˈaj."]}
```

```json
{"id": "japanese_12", "text": "Sensei xem phiếu.", "expected": ["Xen-xê xem phiếu.", "Sen-sê xem phiếu."], "got": "xen-xây xem phiếu.", "got_phonemes": "sˈɛn sˈəɪ sˈɛm fˈiɛɜw.", "expected_phonemes": ["sˈɛn sˈe sˈɛm fˈiɛɜw.", "sˈɛn sˈe sˈɛm fˈiɛɜw."]}
```

```json
{"id": "japanese_13", "text": "Kouhai xem phiếu.", "expected": ["Cô-hai xem phiếu.", "Kô-hai xem phiếu."], "got": "Câu-hai xem phiếu.", "got_phonemes": "kˈə1w hˈaːj sˈɛm fˈiɛɜw.", "expected_phonemes": ["kˈo hˈaːj sˈɛm fˈiɛɜw.", "kˈaːˈo hˈaːj sˈɛm fˈiɛɜw."]}
```

```json
{"id": "japanese_14", "text": "Arigatou, xin nhận.", "expected": ["A-ri-ga-tô, xin nhận.", "A-ri-ga-tou, xin nhận."], "got": "a-ri-ga-tâu, xin nhận.", "got_phonemes": "ˈaː ɹˈi ɣˈaː t̪ˈə1w, sˈin ɲˈə6n.", "expected_phonemes": ["ˈaː ɹˈi ɣˈaː t̪ˈo, sˈin ɲˈə6n.", "ˈaː ɹˈi ɣˈaː tˈuː, sˈin ɲˈə6n."]}
```

```json
{"id": "japanese_15", "text": "Ohayou, mời vào.", "expected": ["Ô-ha-yô, mời vào.", "O-ha-yo, mời vào."], "got": "ô-ha-giâu, mời vào.", "got_phonemes": "ˈo hˈaː zˈə1w, mˈəː2j vˈaː2w.", "expected_phonemes": ["ˈo hˈaː ˈiˈo, mˈəː2j vˈaː2w.", "ˈo hˈaː jˈoʊ, mˈəː2j vˈaː2w."]}
```

```json
{"id": "japanese_20", "text": "Onee-chan đến.", "expected": ["Ô-nê-chan đến.", "O-nê-chan đến."], "got": "ô-ne-chan đến.", "got_phonemes": "ˈo nˈɛ tʃˈaːn ɗˌeɜn.", "expected_phonemes": ["ˈo nˈe tʃˈaːn ɗˌeɜn.", "ˈo nˈe tʃˈaːn ɗˌeɜn."]}
```

### abbrev_en / nghe_ngay: 10 cases

```json
{"id": "abbrev_en_05", "text": "Gặp CEO.", "expected": ["Gặp xi i ô.", "Gặp giám đốc điều hành."], "got": "Gặp <en>C E O</en>.", "got_phonemes": "ɣˈa6p sˈiː ˈiː ˈoʊ.", "expected_phonemes": ["ɣˈa6p sˈi ˈi ˈo.", "ɣˈa6p zˈaːɜm ɗˈoɜk ɗˈiɛ2w hˈe-2ɲ."]}
```

```json
{"id": "abbrev_en_07", "text": "Đỏ vs. xanh.", "expected": ["Đỏ với xanh.", "Đỏ đấu với xanh.", "Đỏ versus xanh."], "got": "Đỏ vs. xanh.", "got_phonemes": "ɗˈɔ4 vˌiːˈɛs, sˈe-ɲ.", "expected_phonemes": ["ɗˈɔ4 vˌəːɜj sˈe-ɲ.", "ɗˈɔ4 ɗˈəɜw vˌəːɜj sˈe-ɲ.", "ɗˈɔ4 vˈɜːsᵻz sˈe-ɲ."]}
```

```json
{"id": "abbrev_en_08", "text": "Gắn CPU.", "expected": ["Gắn xi pi iu.", "Gắn xê pê u."], "got": "Gắn <en>C P U</en>.", "got_phonemes": "ɣˈaɜn sˈiː pˈiː jˈuː.", "expected_phonemes": ["ɣˈaɜn sˈi pˈi ˈiw.", "ɣˈaɜn sˈe pˈe ˈu."]}
```

```json
{"id": "abbrev_en_09", "text": "Gắn GPU.", "expected": ["Gắn gi pi iu.", "Gắn gi pê u."], "got": "Gắn <en>G P U</en>.", "got_phonemes": "ɣˈaɜn dʒˈiː pˈiː jˈuː.", "expected_phonemes": ["ɣˈaɜn zˈi pˈi ˈiw.", "ɣˈaɜn zˈi pˈe ˈu."]}
```

```json
{"id": "abbrev_en_10", "text": "Đọc PDF.", "expected": ["Đọc pi đi ép.", "Đọc pê đê ép."], "got": "Đọc <en>P D F</en>.", "got_phonemes": "ɗˈɔ6k pˈiː dˈiː ˈɛf.", "expected_phonemes": ["ɗˈɔ6k pˈi ɗˈi ˈɛɜp.", "ɗˈɔ6k pˈe ɗˈe ˈɛɜp."]}
```

```json
{"id": "abbrev_en_11", "text": "Mở USB.", "expected": ["Mở iu ét bi.", "Mở u ét bê."], "got": "Mở <en>U S B</en>.", "got_phonemes": "mˈəː4 jˈuː ˈɛs bˈiː.", "expected_phonemes": ["mˈəː4 ˈiw ˈɛɜt̪ bˈi.", "mˈəː4 ˈu ˈɛɜt̪ bˈe."]}
```

```json
{"id": "abbrev_en_12", "text": "Dùng GPS.", "expected": ["Dùng gi pi ét.", "Dùng gi pê ét."], "got": "Dùng <en>G P S</en>.", "got_phonemes": "zˈu2ŋ dʒˈiː pˈiː ˈɛs.", "expected_phonemes": ["zˈu2ŋ zˈi pˈi ˈɛɜt̪.", "zˈu2ŋ zˈi pˈe ˈɛɜt̪."]}
```

```json
{"id": "abbrev_en_13", "text": "Tăng FPS.", "expected": ["Tăng ép pi ét.", "Tăng ép pê ét."], "got": "Tăng <en>F P S</en>.", "got_phonemes": "t̪ˈaŋ ˈɛf pˈiː ˈɛs.", "expected_phonemes": ["t̪ˈaŋ ˈɛɜp pˈi ˈɛɜt̪.", "t̪ˈaŋ ˈɛɜp pˈe ˈɛɜt̪."]}
```

```json
{"id": "abbrev_en_14", "text": "Chơi RPG.", "expected": ["Chơi a pi gi.", "Chơi rờ pê gi."], "got": "Chơi <en>R P G</en>.", "got_phonemes": "tʃˈəːj ˈɑːɹ pˈiː dʒˈiː.", "expected_phonemes": ["tʃˈəːj ˈaː pˈi zˈi.", "tʃˈəːj ɹˈəː2 pˈe zˈi."]}
```

```json
{"id": "abbrev_en_15", "text": "Tăng EXP.", "expected": ["Tăng i éc pi.", "Tăng e ích pê.", "Tăng kinh nghiệm."], "got": "Tăng <en>E X P</en>.", "got_phonemes": "t̪ˈaŋ ˈiː ˈɛks pˈiː.", "expected_phonemes": ["t̪ˈaŋ ˈi ˈɛɜc pˈi.", "t̪ˈaŋ ˈɛ ˈiɜc pˈe.", "t̪ˈaŋ kˈiɲ ŋˈiɛ6m."]}
```

### abbrev_en / studio: 10 cases

```json
{"id": "abbrev_en_05", "text": "Gặp CEO.", "expected": ["Gặp xi i ô.", "Gặp giám đốc điều hành."], "got": "Gặp <en>C E O</en>.", "got_phonemes": "ɣˈa6p sˈiː ˈiː ˈoʊ.", "expected_phonemes": ["ɣˈa6p sˈi ˈi ˈo.", "ɣˈa6p zˈaːɜm ɗˈoɜk ɗˈiɛ2w hˈe-2ɲ."]}
```

```json
{"id": "abbrev_en_07", "text": "Đỏ vs. xanh.", "expected": ["Đỏ với xanh.", "Đỏ đấu với xanh.", "Đỏ versus xanh."], "got": "Đỏ vs. xanh.", "got_phonemes": "ɗˈɔ4 vˌiːˈɛs, sˈe-ɲ.", "expected_phonemes": ["ɗˈɔ4 vˌəːɜj sˈe-ɲ.", "ɗˈɔ4 ɗˈəɜw vˌəːɜj sˈe-ɲ.", "ɗˈɔ4 vˈɜːsᵻz sˈe-ɲ."]}
```

```json
{"id": "abbrev_en_08", "text": "Gắn CPU.", "expected": ["Gắn xi pi iu.", "Gắn xê pê u."], "got": "Gắn <en>C P U</en>.", "got_phonemes": "ɣˈaɜn sˈiː pˈiː jˈuː.", "expected_phonemes": ["ɣˈaɜn sˈi pˈi ˈiw.", "ɣˈaɜn sˈe pˈe ˈu."]}
```

```json
{"id": "abbrev_en_09", "text": "Gắn GPU.", "expected": ["Gắn gi pi iu.", "Gắn gi pê u."], "got": "Gắn <en>G P U</en>.", "got_phonemes": "ɣˈaɜn dʒˈiː pˈiː jˈuː.", "expected_phonemes": ["ɣˈaɜn zˈi pˈi ˈiw.", "ɣˈaɜn zˈi pˈe ˈu."]}
```

```json
{"id": "abbrev_en_10", "text": "Đọc PDF.", "expected": ["Đọc pi đi ép.", "Đọc pê đê ép."], "got": "Đọc <en>P D F</en>.", "got_phonemes": "ɗˈɔ6k pˈiː dˈiː ˈɛf.", "expected_phonemes": ["ɗˈɔ6k pˈi ɗˈi ˈɛɜp.", "ɗˈɔ6k pˈe ɗˈe ˈɛɜp."]}
```

```json
{"id": "abbrev_en_11", "text": "Mở USB.", "expected": ["Mở iu ét bi.", "Mở u ét bê."], "got": "Mở <en>U S B</en>.", "got_phonemes": "mˈəː4 jˈuː ˈɛs bˈiː.", "expected_phonemes": ["mˈəː4 ˈiw ˈɛɜt̪ bˈi.", "mˈəː4 ˈu ˈɛɜt̪ bˈe."]}
```

```json
{"id": "abbrev_en_12", "text": "Dùng GPS.", "expected": ["Dùng gi pi ét.", "Dùng gi pê ét."], "got": "Dùng <en>G P S</en>.", "got_phonemes": "zˈu2ŋ dʒˈiː pˈiː ˈɛs.", "expected_phonemes": ["zˈu2ŋ zˈi pˈi ˈɛɜt̪.", "zˈu2ŋ zˈi pˈe ˈɛɜt̪."]}
```

```json
{"id": "abbrev_en_13", "text": "Tăng FPS.", "expected": ["Tăng ép pi ét.", "Tăng ép pê ét."], "got": "Tăng <en>F P S</en>.", "got_phonemes": "t̪ˈaŋ ˈɛf pˈiː ˈɛs.", "expected_phonemes": ["t̪ˈaŋ ˈɛɜp pˈi ˈɛɜt̪.", "t̪ˈaŋ ˈɛɜp pˈe ˈɛɜt̪."]}
```

```json
{"id": "abbrev_en_14", "text": "Chơi RPG.", "expected": ["Chơi a pi gi.", "Chơi rờ pê gi."], "got": "Chơi <en>R P G</en>.", "got_phonemes": "tʃˈəːj ˈɑːɹ pˈiː dʒˈiː.", "expected_phonemes": ["tʃˈəːj ˈaː pˈi zˈi.", "tʃˈəːj ɹˈəː2 pˈe zˈi."]}
```

```json
{"id": "abbrev_en_15", "text": "Tăng EXP.", "expected": ["Tăng i éc pi.", "Tăng e ích pê.", "Tăng kinh nghiệm."], "got": "Tăng <en>E X P</en>.", "got_phonemes": "t̪ˈaŋ ˈiː ˈɛks pˈiː.", "expected_phonemes": ["t̪ˈaŋ ˈi ˈɛɜc pˈi.", "t̪ˈaŋ ˈɛ ˈiɜc pˈe.", "t̪ˈaŋ kˈiɲ ŋˈiɛ6m."]}
```

### vocalization / nghe_ngay: 7 cases

```json
{"id": "vocalization_01", "text": "Aaaa!", "expected": ["a… a!", "a... a!", "a!"], "got": "a… a!", "got_phonemes": "ˈaː, ˈaː!", "expected_phonemes": ["ɐ, ɐ!", "ɐ, ɐ!", "ɐ!"]}
```

```json
{"id": "vocalization_02", "text": "Áaaaa!", "expected": ["á… a!", "á... a!", "á!"], "got": "á… á!", "got_phonemes": "ˈaːɜ, ˈaːɜ!", "expected_phonemes": ["ˈaːɜ, ˈaː!", "ˈaːɜ, ˈaː!", "ˈaːɜ!"]}
```

```json
{"id": "vocalization_03", "text": "Oooo!", "expected": ["o… o!", "o... o!", "ô!"], "got": "o… o_!", "got_phonemes": "ˈo, ˈɔ!", "expected_phonemes": ["ˈo, ˈo!", "ˈo, ˈo!", "ˈo!"]}
```

```json
{"id": "vocalization_05", "text": "Eeee!", "expected": ["e… e!", "e... e!", "e!"], "got": "e… e!", "got_phonemes": "ˈɛ, ˈɛ!", "expected_phonemes": ["ˈiː, ˈiː!", "ˈiː, ˈiː!", "ˈiː!"]}
```

```json
{"id": "vocalization_07", "text": "Uuuu!", "expected": ["u… u!", "u... u!", "u!"], "got": "u… u!", "got_phonemes": "ˈu, ˈu!", "expected_phonemes": ["jˈuː, jˈuː!", "jˈuː, jˈuː!", "jˈuː!"]}
```

```json
{"id": "vocalization_19", "text": "Aaaa...!?", "expected": ["a… a…!?", "a... a...!?", "a!"], "got": "a… a...?", "got_phonemes": "ˈaː, ˈaː?", "expected_phonemes": ["ɐ, ɐ!", "ɐ, ɐ!", "ɐ!"]}
```

```json
{"id": "vocalization_20", "text": "[thở dài]", "expected": ["hầy.", "hầy…", "hầy..."], "got": "[thở dài]", "got_phonemes": "tˈəː4 zˈaː2j.", "expected_phonemes": ["hˈəɪ2.", "hˈəɪ2.", "hˈəɪ2."]}
```

### vocalization / studio: 6 cases

```json
{"id": "vocalization_01", "text": "Aaaa!", "expected": ["a… a!", "a... a!", "a!"], "got": "a… a!", "got_phonemes": "ˈaː, ˈaː!", "expected_phonemes": ["ɐ, ɐ!", "ɐ, ɐ!", "ɐ!"]}
```

```json
{"id": "vocalization_02", "text": "Áaaaa!", "expected": ["á… a!", "á... a!", "á!"], "got": "á… á!", "got_phonemes": "ˈaːɜ, ˈaːɜ!", "expected_phonemes": ["ˈaːɜ, ˈaː!", "ˈaːɜ, ˈaː!", "ˈaːɜ!"]}
```

```json
{"id": "vocalization_03", "text": "Oooo!", "expected": ["o… o!", "o... o!", "ô!"], "got": "o… o_!", "got_phonemes": "ˈo, ˈɔ!", "expected_phonemes": ["ˈo, ˈo!", "ˈo, ˈo!", "ˈo!"]}
```

```json
{"id": "vocalization_05", "text": "Eeee!", "expected": ["e… e!", "e... e!", "e!"], "got": "e… e!", "got_phonemes": "ˈɛ, ˈɛ!", "expected_phonemes": ["ˈiː, ˈiː!", "ˈiː, ˈiː!", "ˈiː!"]}
```

```json
{"id": "vocalization_07", "text": "Uuuu!", "expected": ["u… u!", "u... u!", "u!"], "got": "u… u!", "got_phonemes": "ˈu, ˈu!", "expected_phonemes": ["jˈuː, jˈuː!", "jˈuː, jˈuː!", "jˈuː!"]}
```

```json
{"id": "vocalization_19", "text": "Aaaa...!?", "expected": ["a… a…!?", "a... a...!?", "a!"], "got": "a… a...?", "got_phonemes": "ˈaː, ˈaː?", "expected_phonemes": ["ɐ, ɐ!", "ɐ, ɐ!", "ɐ!"]}
```

### cardinal_large / nghe_ngay: 10 cases

```json
{"id": "cardinal_large_06", "text": "Phiếu ghi 1000000.", "expected": "Phiếu ghi một triệu.", "got": "Phiếu ghi 1000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ tʃˈiɛ6w."]}
```

```json
{"id": "cardinal_large_07", "text": "Phiếu ghi 2000000.", "expected": "Phiếu ghi hai triệu.", "got": "Phiếu ghi 2000000.", "got_phonemes": "fˈiɛɜw ɣˈi hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi hˈaːj tʃˈiɛ6w."]}
```

```json
{"id": "cardinal_large_08", "text": "Phiếu ghi 10000000.", "expected": "Phiếu ghi mười triệu.", "got": "Phiếu ghi 10000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈyə2j tʃˈiɛ6w."]}
```

```json
{"id": "cardinal_large_09", "text": "Phiếu ghi 100000000.", "expected": "Phiếu ghi một trăm triệu.", "got": "Phiếu ghi 100000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ tʃˈam tʃˈiɛ6w."]}
```

```json
{"id": "cardinal_large_10", "text": "Phiếu ghi 1000000000.", "expected": ["Phiếu ghi một tỷ.", "Phiếu ghi một tỉ."], "got": "Phiếu ghi 1000000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4.", "fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4."]}
```

```json
{"id": "cardinal_large_11", "text": "Phiếu ghi 2000000000.", "expected": ["Phiếu ghi hai tỷ.", "Phiếu ghi hai tỉ."], "got": "Phiếu ghi 2000000000.", "got_phonemes": "fˈiɛɜw ɣˈi hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi hˈaːj t̪ˈi4.", "fˈiɛɜw ɣˈi hˈaːj t̪ˈi4."]}
```

```json
{"id": "cardinal_large_12", "text": "Phiếu ghi 10000000000.", "expected": ["Phiếu ghi mười tỷ.", "Phiếu ghi mười tỉ."], "got": "Phiếu ghi 10000000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈyə2j t̪ˈi4.", "fˈiɛɜw ɣˈi mˈyə2j t̪ˈi4."]}
```

```json
{"id": "cardinal_large_18", "text": "Phiếu ghi 3200000.", "expected": "Phiếu ghi ba triệu hai trăm nghìn.", "got": "Phiếu ghi 3200000.", "got_phonemes": "fˈiɛɜw ɣˈi bˈaː hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi bˈaː tʃˈiɛ6w hˈaːj tʃˈam ŋˈi2n."]}
```

```json
{"id": "cardinal_large_19", "text": "Phiếu ghi 45000000.", "expected": "Phiếu ghi bốn mươi lăm triệu.", "got": "Phiếu ghi 45000000.", "got_phonemes": "fˈiɛɜw ɣˈi bˈoɜn nˈam xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi bˈoɜn mˈyəj lˈam tʃˈiɛ6w."]}
```

```json
{"id": "cardinal_large_20", "text": "Phiếu ghi 1200000000.", "expected": ["Phiếu ghi một tỷ hai trăm triệu.", "Phiếu ghi một tỉ hai trăm triệu."], "got": "Phiếu ghi 1200000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4 hˈaːj tʃˈam tʃˈiɛ6w.", "fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4 hˈaːj tʃˈam tʃˈiɛ6w."]}
```

### cardinal_large / studio: 10 cases

```json
{"id": "cardinal_large_06", "text": "Phiếu ghi 1000000.", "expected": "Phiếu ghi một triệu.", "got": "Phiếu ghi 1000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ tʃˈiɛ6w."]}
```

```json
{"id": "cardinal_large_07", "text": "Phiếu ghi 2000000.", "expected": "Phiếu ghi hai triệu.", "got": "Phiếu ghi 2000000.", "got_phonemes": "fˈiɛɜw ɣˈi hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi hˈaːj tʃˈiɛ6w."]}
```

```json
{"id": "cardinal_large_08", "text": "Phiếu ghi 10000000.", "expected": "Phiếu ghi mười triệu.", "got": "Phiếu ghi 10000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈyə2j tʃˈiɛ6w."]}
```

```json
{"id": "cardinal_large_09", "text": "Phiếu ghi 100000000.", "expected": "Phiếu ghi một trăm triệu.", "got": "Phiếu ghi 100000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ tʃˈam tʃˈiɛ6w."]}
```

```json
{"id": "cardinal_large_10", "text": "Phiếu ghi 1000000000.", "expected": ["Phiếu ghi một tỷ.", "Phiếu ghi một tỉ."], "got": "Phiếu ghi 1000000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4.", "fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4."]}
```

```json
{"id": "cardinal_large_11", "text": "Phiếu ghi 2000000000.", "expected": ["Phiếu ghi hai tỷ.", "Phiếu ghi hai tỉ."], "got": "Phiếu ghi 2000000000.", "got_phonemes": "fˈiɛɜw ɣˈi hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi hˈaːj t̪ˈi4.", "fˈiɛɜw ɣˈi hˈaːj t̪ˈi4."]}
```

```json
{"id": "cardinal_large_12", "text": "Phiếu ghi 10000000000.", "expected": ["Phiếu ghi mười tỷ.", "Phiếu ghi mười tỉ."], "got": "Phiếu ghi 10000000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈyə2j t̪ˈi4.", "fˈiɛɜw ɣˈi mˈyə2j t̪ˈi4."]}
```

```json
{"id": "cardinal_large_18", "text": "Phiếu ghi 3200000.", "expected": "Phiếu ghi ba triệu hai trăm nghìn.", "got": "Phiếu ghi 3200000.", "got_phonemes": "fˈiɛɜw ɣˈi bˈaː hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi bˈaː tʃˈiɛ6w hˈaːj tʃˈam ŋˈi2n."]}
```

```json
{"id": "cardinal_large_19", "text": "Phiếu ghi 45000000.", "expected": "Phiếu ghi bốn mươi lăm triệu.", "got": "Phiếu ghi 45000000.", "got_phonemes": "fˈiɛɜw ɣˈi bˈoɜn nˈam xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi bˈoɜn mˈyəj lˈam tʃˈiɛ6w."]}
```

```json
{"id": "cardinal_large_20", "text": "Phiếu ghi 1200000000.", "expected": ["Phiếu ghi một tỷ hai trăm triệu.", "Phiếu ghi một tỉ hai trăm triệu."], "got": "Phiếu ghi 1200000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4 hˈaːj tʃˈam tʃˈiɛ6w.", "fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4 hˈaːj tʃˈam tʃˈiɛ6w."]}
```

## All mismatches (each stage)

### cardinal_large_06 / nghe_ngay / string

```json
{"text": "Phiếu ghi 1000000.", "expected": "Phiếu ghi một triệu.", "got": "Phiếu ghi 1000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_06 / nghe_ngay / post_g2p

```json
{"text": "Phiếu ghi 1000000.", "expected": "Phiếu ghi một triệu.", "got": "Phiếu ghi 1000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_06 / studio / string

```json
{"text": "Phiếu ghi 1000000.", "expected": "Phiếu ghi một triệu.", "got": "Phiếu ghi 1000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_06 / studio / post_g2p

```json
{"text": "Phiếu ghi 1000000.", "expected": "Phiếu ghi một triệu.", "got": "Phiếu ghi 1000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_07 / nghe_ngay / string

```json
{"text": "Phiếu ghi 2000000.", "expected": "Phiếu ghi hai triệu.", "got": "Phiếu ghi 2000000.", "got_phonemes": "fˈiɛɜw ɣˈi hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi hˈaːj tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_07 / nghe_ngay / post_g2p

```json
{"text": "Phiếu ghi 2000000.", "expected": "Phiếu ghi hai triệu.", "got": "Phiếu ghi 2000000.", "got_phonemes": "fˈiɛɜw ɣˈi hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi hˈaːj tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_07 / studio / string

```json
{"text": "Phiếu ghi 2000000.", "expected": "Phiếu ghi hai triệu.", "got": "Phiếu ghi 2000000.", "got_phonemes": "fˈiɛɜw ɣˈi hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi hˈaːj tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_07 / studio / post_g2p

```json
{"text": "Phiếu ghi 2000000.", "expected": "Phiếu ghi hai triệu.", "got": "Phiếu ghi 2000000.", "got_phonemes": "fˈiɛɜw ɣˈi hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi hˈaːj tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_08 / nghe_ngay / string

```json
{"text": "Phiếu ghi 10000000.", "expected": "Phiếu ghi mười triệu.", "got": "Phiếu ghi 10000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈyə2j tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_08 / nghe_ngay / post_g2p

```json
{"text": "Phiếu ghi 10000000.", "expected": "Phiếu ghi mười triệu.", "got": "Phiếu ghi 10000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈyə2j tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_08 / studio / string

```json
{"text": "Phiếu ghi 10000000.", "expected": "Phiếu ghi mười triệu.", "got": "Phiếu ghi 10000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈyə2j tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_08 / studio / post_g2p

```json
{"text": "Phiếu ghi 10000000.", "expected": "Phiếu ghi mười triệu.", "got": "Phiếu ghi 10000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈyə2j tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_09 / nghe_ngay / string

```json
{"text": "Phiếu ghi 100000000.", "expected": "Phiếu ghi một trăm triệu.", "got": "Phiếu ghi 100000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ tʃˈam tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_09 / nghe_ngay / post_g2p

```json
{"text": "Phiếu ghi 100000000.", "expected": "Phiếu ghi một trăm triệu.", "got": "Phiếu ghi 100000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ tʃˈam tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_09 / studio / string

```json
{"text": "Phiếu ghi 100000000.", "expected": "Phiếu ghi một trăm triệu.", "got": "Phiếu ghi 100000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ tʃˈam tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_09 / studio / post_g2p

```json
{"text": "Phiếu ghi 100000000.", "expected": "Phiếu ghi một trăm triệu.", "got": "Phiếu ghi 100000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ tʃˈam tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_10 / nghe_ngay / string

```json
{"text": "Phiếu ghi 1000000000.", "expected": ["Phiếu ghi một tỷ.", "Phiếu ghi một tỉ."], "got": "Phiếu ghi 1000000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4.", "fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_10 / nghe_ngay / post_g2p

```json
{"text": "Phiếu ghi 1000000000.", "expected": ["Phiếu ghi một tỷ.", "Phiếu ghi một tỉ."], "got": "Phiếu ghi 1000000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4.", "fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_10 / studio / string

```json
{"text": "Phiếu ghi 1000000000.", "expected": ["Phiếu ghi một tỷ.", "Phiếu ghi một tỉ."], "got": "Phiếu ghi 1000000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4.", "fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_10 / studio / post_g2p

```json
{"text": "Phiếu ghi 1000000000.", "expected": ["Phiếu ghi một tỷ.", "Phiếu ghi một tỉ."], "got": "Phiếu ghi 1000000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4.", "fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_11 / nghe_ngay / string

```json
{"text": "Phiếu ghi 2000000000.", "expected": ["Phiếu ghi hai tỷ.", "Phiếu ghi hai tỉ."], "got": "Phiếu ghi 2000000000.", "got_phonemes": "fˈiɛɜw ɣˈi hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi hˈaːj t̪ˈi4.", "fˈiɛɜw ɣˈi hˈaːj t̪ˈi4."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_11 / nghe_ngay / post_g2p

```json
{"text": "Phiếu ghi 2000000000.", "expected": ["Phiếu ghi hai tỷ.", "Phiếu ghi hai tỉ."], "got": "Phiếu ghi 2000000000.", "got_phonemes": "fˈiɛɜw ɣˈi hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi hˈaːj t̪ˈi4.", "fˈiɛɜw ɣˈi hˈaːj t̪ˈi4."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_11 / studio / string

```json
{"text": "Phiếu ghi 2000000000.", "expected": ["Phiếu ghi hai tỷ.", "Phiếu ghi hai tỉ."], "got": "Phiếu ghi 2000000000.", "got_phonemes": "fˈiɛɜw ɣˈi hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi hˈaːj t̪ˈi4.", "fˈiɛɜw ɣˈi hˈaːj t̪ˈi4."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_11 / studio / post_g2p

```json
{"text": "Phiếu ghi 2000000000.", "expected": ["Phiếu ghi hai tỷ.", "Phiếu ghi hai tỉ."], "got": "Phiếu ghi 2000000000.", "got_phonemes": "fˈiɛɜw ɣˈi hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi hˈaːj t̪ˈi4.", "fˈiɛɜw ɣˈi hˈaːj t̪ˈi4."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_12 / nghe_ngay / string

```json
{"text": "Phiếu ghi 10000000000.", "expected": ["Phiếu ghi mười tỷ.", "Phiếu ghi mười tỉ."], "got": "Phiếu ghi 10000000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈyə2j t̪ˈi4.", "fˈiɛɜw ɣˈi mˈyə2j t̪ˈi4."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_12 / nghe_ngay / post_g2p

```json
{"text": "Phiếu ghi 10000000000.", "expected": ["Phiếu ghi mười tỷ.", "Phiếu ghi mười tỉ."], "got": "Phiếu ghi 10000000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈyə2j t̪ˈi4.", "fˈiɛɜw ɣˈi mˈyə2j t̪ˈi4."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_12 / studio / string

```json
{"text": "Phiếu ghi 10000000000.", "expected": ["Phiếu ghi mười tỷ.", "Phiếu ghi mười tỉ."], "got": "Phiếu ghi 10000000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈyə2j t̪ˈi4.", "fˈiɛɜw ɣˈi mˈyə2j t̪ˈi4."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_12 / studio / post_g2p

```json
{"text": "Phiếu ghi 10000000000.", "expected": ["Phiếu ghi mười tỷ.", "Phiếu ghi mười tỉ."], "got": "Phiếu ghi 10000000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈyə2j t̪ˈi4.", "fˈiɛɜw ɣˈi mˈyə2j t̪ˈi4."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_18 / nghe_ngay / string

```json
{"text": "Phiếu ghi 3200000.", "expected": "Phiếu ghi ba triệu hai trăm nghìn.", "got": "Phiếu ghi 3200000.", "got_phonemes": "fˈiɛɜw ɣˈi bˈaː hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi bˈaː tʃˈiɛ6w hˈaːj tʃˈam ŋˈi2n."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_18 / nghe_ngay / post_g2p

```json
{"text": "Phiếu ghi 3200000.", "expected": "Phiếu ghi ba triệu hai trăm nghìn.", "got": "Phiếu ghi 3200000.", "got_phonemes": "fˈiɛɜw ɣˈi bˈaː hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi bˈaː tʃˈiɛ6w hˈaːj tʃˈam ŋˈi2n."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_18 / studio / string

```json
{"text": "Phiếu ghi 3200000.", "expected": "Phiếu ghi ba triệu hai trăm nghìn.", "got": "Phiếu ghi 3200000.", "got_phonemes": "fˈiɛɜw ɣˈi bˈaː hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi bˈaː tʃˈiɛ6w hˈaːj tʃˈam ŋˈi2n."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_18 / studio / post_g2p

```json
{"text": "Phiếu ghi 3200000.", "expected": "Phiếu ghi ba triệu hai trăm nghìn.", "got": "Phiếu ghi 3200000.", "got_phonemes": "fˈiɛɜw ɣˈi bˈaː hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi bˈaː tʃˈiɛ6w hˈaːj tʃˈam ŋˈi2n."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_19 / nghe_ngay / string

```json
{"text": "Phiếu ghi 45000000.", "expected": "Phiếu ghi bốn mươi lăm triệu.", "got": "Phiếu ghi 45000000.", "got_phonemes": "fˈiɛɜw ɣˈi bˈoɜn nˈam xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi bˈoɜn mˈyəj lˈam tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_19 / nghe_ngay / post_g2p

```json
{"text": "Phiếu ghi 45000000.", "expected": "Phiếu ghi bốn mươi lăm triệu.", "got": "Phiếu ghi 45000000.", "got_phonemes": "fˈiɛɜw ɣˈi bˈoɜn nˈam xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi bˈoɜn mˈyəj lˈam tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_19 / studio / string

```json
{"text": "Phiếu ghi 45000000.", "expected": "Phiếu ghi bốn mươi lăm triệu.", "got": "Phiếu ghi 45000000.", "got_phonemes": "fˈiɛɜw ɣˈi bˈoɜn nˈam xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi bˈoɜn mˈyəj lˈam tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_19 / studio / post_g2p

```json
{"text": "Phiếu ghi 45000000.", "expected": "Phiếu ghi bốn mươi lăm triệu.", "got": "Phiếu ghi 45000000.", "got_phonemes": "fˈiɛɜw ɣˈi bˈoɜn nˈam xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi bˈoɜn mˈyəj lˈam tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_20 / nghe_ngay / string

```json
{"text": "Phiếu ghi 1200000000.", "expected": ["Phiếu ghi một tỷ hai trăm triệu.", "Phiếu ghi một tỉ hai trăm triệu."], "got": "Phiếu ghi 1200000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4 hˈaːj tʃˈam tʃˈiɛ6w.", "fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4 hˈaːj tʃˈam tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_20 / nghe_ngay / post_g2p

```json
{"text": "Phiếu ghi 1200000000.", "expected": ["Phiếu ghi một tỷ hai trăm triệu.", "Phiếu ghi một tỉ hai trăm triệu."], "got": "Phiếu ghi 1200000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4 hˈaːj tʃˈam tʃˈiɛ6w.", "fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4 hˈaːj tʃˈam tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_20 / studio / string

```json
{"text": "Phiếu ghi 1200000000.", "expected": ["Phiếu ghi một tỷ hai trăm triệu.", "Phiếu ghi một tỉ hai trăm triệu."], "got": "Phiếu ghi 1200000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4 hˈaːj tʃˈam tʃˈiɛ6w.", "fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4 hˈaːj tʃˈam tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_20 / studio / post_g2p

```json
{"text": "Phiếu ghi 1200000000.", "expected": ["Phiếu ghi một tỷ hai trăm triệu.", "Phiếu ghi một tỉ hai trăm triệu."], "got": "Phiếu ghi 1200000000.", "got_phonemes": "fˈiɛɜw ɣˈi mˈo6t̪ hˈaːj xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4 hˈaːj tʃˈam tʃˈiɛ6w.", "fˈiɛɜw ɣˈi mˈo6t̪ t̪ˈi4 hˈaːj tʃˈam tʃˈiɛ6w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_01 / nghe_ngay / string

```json
{"text": "Mức là 1,5.", "expected": "Mức là một phẩy năm.", "got": "Mức là 1,5.", "got_phonemes": "mˈyɜc lˌaː2 mˈo6t̪ fˈəɪ4 nˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 mˈo6t̪ fˈəɪ4 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_01 / studio / string

```json
{"text": "Mức là 1,5.", "expected": "Mức là một phẩy năm.", "got": "Mức là 1,5.", "got_phonemes": "mˈyɜc lˌaː2 mˈo6t̪ fˈəɪ4 nˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 mˈo6t̪ fˈəɪ4 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_02 / nghe_ngay / string

```json
{"text": "Mức là 2.5.", "expected": "Mức là hai phẩy năm.", "got": "Mức là 2.5.", "got_phonemes": "mˈyɜc lˌaː2 hˈaːj tʃˈəɜm nˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 hˈaːj fˈəɪ4 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_02 / nghe_ngay / post_g2p

```json
{"text": "Mức là 2.5.", "expected": "Mức là hai phẩy năm.", "got": "Mức là 2.5.", "got_phonemes": "mˈyɜc lˌaː2 hˈaːj tʃˈəɜm nˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 hˈaːj fˈəɪ4 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_02 / studio / string

```json
{"text": "Mức là 2.5.", "expected": "Mức là hai phẩy năm.", "got": "Mức là 2.5.", "got_phonemes": "mˈyɜc lˌaː2 hˈaːj tʃˈəɜm nˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 hˈaːj fˈəɪ4 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_02 / studio / post_g2p

```json
{"text": "Mức là 2.5.", "expected": "Mức là hai phẩy năm.", "got": "Mức là 2.5.", "got_phonemes": "mˈyɜc lˌaː2 hˈaːj tʃˈəɜm nˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 hˈaːj fˈəɪ4 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_03 / nghe_ngay / string

```json
{"text": "Mức là 0,25.", "expected": "Mức là không phẩy hai năm.", "got": "Mức là 0,25.", "got_phonemes": "mˈyɜc lˌaː2 xˌoŋ fˈəɪ4 hˈaːj lˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 xˌoŋ fˈəɪ4 hˈaːj nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_03 / nghe_ngay / post_g2p

```json
{"text": "Mức là 0,25.", "expected": "Mức là không phẩy hai năm.", "got": "Mức là 0,25.", "got_phonemes": "mˈyɜc lˌaː2 xˌoŋ fˈəɪ4 hˈaːj lˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 xˌoŋ fˈəɪ4 hˈaːj nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_03 / studio / string

```json
{"text": "Mức là 0,25.", "expected": "Mức là không phẩy hai năm.", "got": "Mức là 0,25.", "got_phonemes": "mˈyɜc lˌaː2 xˌoŋ fˈəɪ4 hˈaːj lˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 xˌoŋ fˈəɪ4 hˈaːj nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_03 / studio / post_g2p

```json
{"text": "Mức là 0,25.", "expected": "Mức là không phẩy hai năm.", "got": "Mức là 0,25.", "got_phonemes": "mˈyɜc lˌaː2 xˌoŋ fˈəɪ4 hˈaːj lˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 xˌoŋ fˈəɪ4 hˈaːj nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_04 / nghe_ngay / string

```json
{"text": "Mức là 0.75.", "expected": "Mức là không phẩy bảy năm.", "got": "Mức là 0.75.", "got_phonemes": "mˈyɜc lˌaː2 xˌoŋ tʃˈəɜm bˈa4j lˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 xˌoŋ fˈəɪ4 bˈa4j nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_04 / nghe_ngay / post_g2p

```json
{"text": "Mức là 0.75.", "expected": "Mức là không phẩy bảy năm.", "got": "Mức là 0.75.", "got_phonemes": "mˈyɜc lˌaː2 xˌoŋ tʃˈəɜm bˈa4j lˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 xˌoŋ fˈəɪ4 bˈa4j nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_04 / studio / string

```json
{"text": "Mức là 0.75.", "expected": "Mức là không phẩy bảy năm.", "got": "Mức là 0.75.", "got_phonemes": "mˈyɜc lˌaː2 xˌoŋ tʃˈəɜm bˈa4j lˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 xˌoŋ fˈəɪ4 bˈa4j nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_04 / studio / post_g2p

```json
{"text": "Mức là 0.75.", "expected": "Mức là không phẩy bảy năm.", "got": "Mức là 0.75.", "got_phonemes": "mˈyɜc lˌaː2 xˌoŋ tʃˈəɜm bˈa4j lˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 xˌoŋ fˈəɪ4 bˈa4j nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_05 / nghe_ngay / string

```json
{"text": "Mức là 3,14.", "expected": "Mức là ba phẩy một bốn.", "got": "Mức là 3,14.", "got_phonemes": "mˈyɜc lˌaː2 bˈaː fˈəɪ4 mˈo6t̪ bˈoɜn.", "expected_phonemes": ["mˈyɜc lˌaː2 bˈaː fˈəɪ4 mˈo6t̪ bˈoɜn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_05 / studio / string

```json
{"text": "Mức là 3,14.", "expected": "Mức là ba phẩy một bốn.", "got": "Mức là 3,14.", "got_phonemes": "mˈyɜc lˌaː2 bˈaː fˈəɪ4 mˈo6t̪ bˈoɜn.", "expected_phonemes": ["mˈyɜc lˌaː2 bˈaː fˈəɪ4 mˈo6t̪ bˈoɜn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_06 / nghe_ngay / string

```json
{"text": "Mức là 6.28.", "expected": "Mức là sáu phẩy hai tám.", "got": "Mức là 6.28.", "got_phonemes": "mˈyɜc lˌaː2 sˈaɜw tʃˈəɜm hˈaːj t̪ˈaːɜm.", "expected_phonemes": ["mˈyɜc lˌaː2 sˈaɜw fˈəɪ4 hˈaːj t̪ˈaːɜm."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_06 / nghe_ngay / post_g2p

```json
{"text": "Mức là 6.28.", "expected": "Mức là sáu phẩy hai tám.", "got": "Mức là 6.28.", "got_phonemes": "mˈyɜc lˌaː2 sˈaɜw tʃˈəɜm hˈaːj t̪ˈaːɜm.", "expected_phonemes": ["mˈyɜc lˌaː2 sˈaɜw fˈəɪ4 hˈaːj t̪ˈaːɜm."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_06 / studio / string

```json
{"text": "Mức là 6.28.", "expected": "Mức là sáu phẩy hai tám.", "got": "Mức là 6.28.", "got_phonemes": "mˈyɜc lˌaː2 sˈaɜw tʃˈəɜm hˈaːj t̪ˈaːɜm.", "expected_phonemes": ["mˈyɜc lˌaː2 sˈaɜw fˈəɪ4 hˈaːj t̪ˈaːɜm."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_06 / studio / post_g2p

```json
{"text": "Mức là 6.28.", "expected": "Mức là sáu phẩy hai tám.", "got": "Mức là 6.28.", "got_phonemes": "mˈyɜc lˌaː2 sˈaɜw tʃˈəɜm hˈaːj t̪ˈaːɜm.", "expected_phonemes": ["mˈyɜc lˌaː2 sˈaɜw fˈəɪ4 hˈaːj t̪ˈaːɜm."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_07 / nghe_ngay / string

```json
{"text": "Mức là 10,01.", "expected": "Mức là mười phẩy không một.", "got": "Mức là 10,01.", "got_phonemes": "mˈyɜc lˌaː2 mˈyə2j fˈəɪ4 xˌoŋ mˈo6t̪.", "expected_phonemes": ["mˈyɜc lˌaː2 mˈyə2j fˈəɪ4 xˌoŋ mˈo6t̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_07 / studio / string

```json
{"text": "Mức là 10,01.", "expected": "Mức là mười phẩy không một.", "got": "Mức là 10,01.", "got_phonemes": "mˈyɜc lˌaː2 mˈyə2j fˈəɪ4 xˌoŋ mˈo6t̪.", "expected_phonemes": ["mˈyɜc lˌaː2 mˈyə2j fˈəɪ4 xˌoŋ mˈo6t̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_08 / nghe_ngay / string

```json
{"text": "Mức là 12.05.", "expected": "Mức là mười hai phẩy không năm.", "got": "Mức là 12.05.", "got_phonemes": "mˈyɜc lˌaː2 mˈyə2j hˈaːj tʃˈəɜm xˌoŋ nˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 mˈyə2j hˈaːj fˈəɪ4 xˌoŋ nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_08 / nghe_ngay / post_g2p

```json
{"text": "Mức là 12.05.", "expected": "Mức là mười hai phẩy không năm.", "got": "Mức là 12.05.", "got_phonemes": "mˈyɜc lˌaː2 mˈyə2j hˈaːj tʃˈəɜm xˌoŋ nˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 mˈyə2j hˈaːj fˈəɪ4 xˌoŋ nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_08 / studio / string

```json
{"text": "Mức là 12.05.", "expected": "Mức là mười hai phẩy không năm.", "got": "Mức là 12.05.", "got_phonemes": "mˈyɜc lˌaː2 mˈyə2j hˈaːj tʃˈəɜm xˌoŋ nˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 mˈyə2j hˈaːj fˈəɪ4 xˌoŋ nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_08 / studio / post_g2p

```json
{"text": "Mức là 12.05.", "expected": "Mức là mười hai phẩy không năm.", "got": "Mức là 12.05.", "got_phonemes": "mˈyɜc lˌaː2 mˈyə2j hˈaːj tʃˈəɜm xˌoŋ nˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 mˈyə2j hˈaːj fˈəɪ4 xˌoŋ nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_09 / nghe_ngay / string

```json
{"text": "Mức là -1,5.", "expected": "Mức là âm một phẩy năm.", "got": "Mức là âm 1,5.", "got_phonemes": "mˈyɜc lˌaː2 ˈəm mˈo6t̪ fˈəɪ4 nˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 ˈəm mˈo6t̪ fˈəɪ4 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_09 / studio / string

```json
{"text": "Mức là -1,5.", "expected": "Mức là âm một phẩy năm.", "got": "Mức là âm 1,5.", "got_phonemes": "mˈyɜc lˌaː2 ˈəm mˈo6t̪ fˈəɪ4 nˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 ˈəm mˈo6t̪ fˈəɪ4 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_10 / nghe_ngay / string

```json
{"text": "Mức là -2.5.", "expected": "Mức là âm hai phẩy năm.", "got": "Mức là âm 2.5.", "got_phonemes": "mˈyɜc lˌaː2 ˈəm hˈaːj tʃˈəɜm nˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 ˈəm hˈaːj fˈəɪ4 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_10 / nghe_ngay / post_g2p

```json
{"text": "Mức là -2.5.", "expected": "Mức là âm hai phẩy năm.", "got": "Mức là âm 2.5.", "got_phonemes": "mˈyɜc lˌaː2 ˈəm hˈaːj tʃˈəɜm nˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 ˈəm hˈaːj fˈəɪ4 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_10 / studio / string

```json
{"text": "Mức là -2.5.", "expected": "Mức là âm hai phẩy năm.", "got": "Mức là âm 2.5.", "got_phonemes": "mˈyɜc lˌaː2 ˈəm hˈaːj tʃˈəɜm nˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 ˈəm hˈaːj fˈəɪ4 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_10 / studio / post_g2p

```json
{"text": "Mức là -2.5.", "expected": "Mức là âm hai phẩy năm.", "got": "Mức là âm 2.5.", "got_phonemes": "mˈyɜc lˌaː2 ˈəm hˈaːj tʃˈəɜm nˈam.", "expected_phonemes": ["mˈyɜc lˌaː2 ˈəm hˈaːj fˈəɪ4 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_15 / nghe_ngay / string

```json
{"text": "Cân 1.234,5 kg.", "expected": ["Cân một nghìn hai trăm ba mươi bốn phẩy năm ki lô gam.", "Cân một nghìn hai trăm ba mươi tư phẩy năm ki lô gam."], "got": "Cân 1.234,5 kg.", "got_phonemes": "kˈən mˈo6t̪ ŋˈi2n hˈaːj tʃˈam bˈaː mˈyəj bˈoɜn fˈəɪ4 nˈam kˈi lˈo ɣˈaːm.", "expected_phonemes": ["kˈən mˈo6t̪ ŋˈi2n hˈaːj tʃˈam bˈaː mˈyəj bˈoɜn fˈəɪ4 nˈam kˈi lˈo ɣˈaːm.", "kˈən mˈo6t̪ ŋˈi2n hˈaːj tʃˈam bˈaː mˈyəj t̪ˈy fˈəɪ4 nˈam kˈi lˈo ɣˈaːm."], "note": "Hai dấu phân cách theo kiểu Việt."}
```

### decimal_15 / studio / string

```json
{"text": "Cân 1.234,5 kg.", "expected": ["Cân một nghìn hai trăm ba mươi bốn phẩy năm ki lô gam.", "Cân một nghìn hai trăm ba mươi tư phẩy năm ki lô gam."], "got": "Cân 1.234,5 kg.", "got_phonemes": "kˈən mˈo6t̪ ŋˈi2n hˈaːj tʃˈam bˈaː mˈyəj bˈoɜn fˈəɪ4 nˈam kˈi lˈo ɣˈaːm.", "expected_phonemes": ["kˈən mˈo6t̪ ŋˈi2n hˈaːj tʃˈam bˈaː mˈyəj bˈoɜn fˈəɪ4 nˈam kˈi lˈo ɣˈaːm.", "kˈən mˈo6t̪ ŋˈi2n hˈaːj tʃˈam bˈaː mˈyəj t̪ˈy fˈəɪ4 nˈam kˈi lˈo ɣˈaːm."], "note": "Hai dấu phân cách theo kiểu Việt."}
```

### decimal_16 / nghe_ngay / string

```json
{"text": "Cân 1,234.5 kg.", "expected": ["Cân một nghìn hai trăm ba mươi bốn phẩy năm ki lô gam.", "Cân một nghìn hai trăm ba mươi tư phẩy năm ki lô gam."], "got": "Cân 1,234.5 kg.", "got_phonemes": "kˈən mˈo6t̪ ŋˈi2n hˈaːj tʃˈam bˈaː mˈyəj bˈoɜn fˈəɪ4 nˈam kˈi lˈo ɣˈaːm.", "expected_phonemes": ["kˈən mˈo6t̪ ŋˈi2n hˈaːj tʃˈam bˈaː mˈyəj bˈoɜn fˈəɪ4 nˈam kˈi lˈo ɣˈaːm.", "kˈən mˈo6t̪ ŋˈi2n hˈaːj tʃˈam bˈaː mˈyəj t̪ˈy fˈəɪ4 nˈam kˈi lˈo ɣˈaːm."], "note": "Hai dấu phân cách theo kiểu Anh."}
```

### decimal_16 / studio / string

```json
{"text": "Cân 1,234.5 kg.", "expected": ["Cân một nghìn hai trăm ba mươi bốn phẩy năm ki lô gam.", "Cân một nghìn hai trăm ba mươi tư phẩy năm ki lô gam."], "got": "Cân 1,234.5 kg.", "got_phonemes": "kˈən mˈo6t̪ ŋˈi2n hˈaːj tʃˈam bˈaː mˈyəj bˈoɜn fˈəɪ4 nˈam kˈi lˈo ɣˈaːm.", "expected_phonemes": ["kˈən mˈo6t̪ ŋˈi2n hˈaːj tʃˈam bˈaː mˈyəj bˈoɜn fˈəɪ4 nˈam kˈi lˈo ɣˈaːm.", "kˈən mˈo6t̪ ŋˈi2n hˈaːj tʃˈam bˈaː mˈyəj t̪ˈy fˈəɪ4 nˈam kˈi lˈo ɣˈaːm."], "note": "Hai dấu phân cách theo kiểu Anh."}
```

### decimal_19 / nghe_ngay / string

```json
{"text": "Mức là 0,001.", "expected": "Mức là không phẩy không không một.", "got": "Mức là 0,001.", "got_phonemes": "mˈyɜc lˌaː2 xˌoŋ fˈəɪ4 xˌoŋ xˌoŋ mˈo6t̪.", "expected_phonemes": ["mˈyɜc lˌaː2 xˌoŋ fˈəɪ4 xˌoŋ xˌoŋ mˈo6t̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_19 / studio / string

```json
{"text": "Mức là 0,001.", "expected": "Mức là không phẩy không không một.", "got": "Mức là 0,001.", "got_phonemes": "mˈyɜc lˌaː2 xˌoŋ fˈəɪ4 xˌoŋ xˌoŋ mˈo6t̪.", "expected_phonemes": ["mˈyɜc lˌaː2 xˌoŋ fˈəɪ4 xˌoŋ xˌoŋ mˈo6t̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_01 / nghe_ngay / string

```json
{"text": "Lượt thứ 1.", "expected": ["Lượt thứ nhất.", "Lượt thứ một."], "got": "Lượt thứ 1.", "got_phonemes": "lˈyə6t̪ tˈyɜ ɲˈəɜt̪.", "expected_phonemes": ["lˈyə6t̪ tˈyɜ ɲˈəɜt̪.", "lˈyə6t̪ tˈyɜ mˈo6t̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_01 / studio / string

```json
{"text": "Lượt thứ 1.", "expected": ["Lượt thứ nhất.", "Lượt thứ một."], "got": "Lượt thứ 1.", "got_phonemes": "lˈyə6t̪ tˈyɜ ɲˈəɜt̪.", "expected_phonemes": ["lˈyə6t̪ tˈyɜ ɲˈəɜt̪.", "lˈyə6t̪ tˈyɜ mˈo6t̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_02 / nghe_ngay / string

```json
{"text": "Lượt thứ 2.", "expected": "Lượt thứ hai.", "got": "Lượt thứ 2.", "got_phonemes": "lˈyə6t̪ tˈyɜ hˈaːj.", "expected_phonemes": ["lˈyə6t̪ tˈyɜ hˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_02 / studio / string

```json
{"text": "Lượt thứ 2.", "expected": "Lượt thứ hai.", "got": "Lượt thứ 2.", "got_phonemes": "lˈyə6t̪ tˈyɜ hˈaːj.", "expected_phonemes": ["lˈyə6t̪ tˈyɜ hˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_03 / nghe_ngay / string

```json
{"text": "Lượt thứ 3.", "expected": "Lượt thứ ba.", "got": "Lượt thứ 3.", "got_phonemes": "lˈyə6t̪ tˈyɜ bˈaː.", "expected_phonemes": ["lˈyə6t̪ tˈyɜ bˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_03 / studio / string

```json
{"text": "Lượt thứ 3.", "expected": "Lượt thứ ba.", "got": "Lượt thứ 3.", "got_phonemes": "lˈyə6t̪ tˈyɜ bˈaː.", "expected_phonemes": ["lˈyə6t̪ tˈyɜ bˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_04 / nghe_ngay / string

```json
{"text": "Lượt thứ 4.", "expected": ["Lượt thứ tư.", "Lượt thứ bốn."], "got": "Lượt thứ 4.", "got_phonemes": "lˈyə6t̪ tˈyɜ t̪ˈy.", "expected_phonemes": ["lˈyə6t̪ tˈyɜ t̪ˈy.", "lˈyə6t̪ tˈyɜ bˈoɜn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_04 / studio / string

```json
{"text": "Lượt thứ 4.", "expected": ["Lượt thứ tư.", "Lượt thứ bốn."], "got": "Lượt thứ 4.", "got_phonemes": "lˈyə6t̪ tˈyɜ t̪ˈy.", "expected_phonemes": ["lˈyə6t̪ tˈyɜ t̪ˈy.", "lˈyə6t̪ tˈyɜ bˈoɜn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_05 / nghe_ngay / string

```json
{"text": "Lượt thứ 5.", "expected": "Lượt thứ năm.", "got": "Lượt thứ 5.", "got_phonemes": "lˈyə6t̪ tˈyɜ nˈam.", "expected_phonemes": ["lˈyə6t̪ tˈyɜ nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_05 / studio / string

```json
{"text": "Lượt thứ 5.", "expected": "Lượt thứ năm.", "got": "Lượt thứ 5.", "got_phonemes": "lˈyə6t̪ tˈyɜ nˈam.", "expected_phonemes": ["lˈyə6t̪ tˈyɜ nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_06 / nghe_ngay / string

```json
{"text": "Lượt thứ 6.", "expected": "Lượt thứ sáu.", "got": "Lượt thứ 6.", "got_phonemes": "lˈyə6t̪ tˈyɜ sˈaɜw.", "expected_phonemes": ["lˈyə6t̪ tˈyɜ sˈaɜw."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_06 / studio / string

```json
{"text": "Lượt thứ 6.", "expected": "Lượt thứ sáu.", "got": "Lượt thứ 6.", "got_phonemes": "lˈyə6t̪ tˈyɜ sˈaɜw.", "expected_phonemes": ["lˈyə6t̪ tˈyɜ sˈaɜw."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_07 / nghe_ngay / string

```json
{"text": "Lượt thứ 7.", "expected": "Lượt thứ bảy.", "got": "Lượt thứ 7.", "got_phonemes": "lˈyə6t̪ tˈyɜ bˈa4j.", "expected_phonemes": ["lˈyə6t̪ tˈyɜ bˈa4j."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_07 / studio / string

```json
{"text": "Lượt thứ 7.", "expected": "Lượt thứ bảy.", "got": "Lượt thứ 7.", "got_phonemes": "lˈyə6t̪ tˈyɜ bˈa4j.", "expected_phonemes": ["lˈyə6t̪ tˈyɜ bˈa4j."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_08 / nghe_ngay / string

```json
{"text": "Lượt thứ 8.", "expected": "Lượt thứ tám.", "got": "Lượt thứ 8.", "got_phonemes": "lˈyə6t̪ tˈyɜ t̪ˈaːɜm.", "expected_phonemes": ["lˈyə6t̪ tˈyɜ t̪ˈaːɜm."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_08 / studio / string

```json
{"text": "Lượt thứ 8.", "expected": "Lượt thứ tám.", "got": "Lượt thứ 8.", "got_phonemes": "lˈyə6t̪ tˈyɜ t̪ˈaːɜm.", "expected_phonemes": ["lˈyə6t̪ tˈyɜ t̪ˈaːɜm."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_09 / nghe_ngay / string

```json
{"text": "Lượt thứ 9.", "expected": "Lượt thứ chín.", "got": "Lượt thứ 9.", "got_phonemes": "lˈyə6t̪ tˈyɜ tʃˈiɜn.", "expected_phonemes": ["lˈyə6t̪ tˈyɜ tʃˈiɜn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_09 / studio / string

```json
{"text": "Lượt thứ 9.", "expected": "Lượt thứ chín.", "got": "Lượt thứ 9.", "got_phonemes": "lˈyə6t̪ tˈyɜ tʃˈiɜn.", "expected_phonemes": ["lˈyə6t̪ tˈyɜ tʃˈiɜn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_10 / nghe_ngay / string

```json
{"text": "Lượt thứ 10.", "expected": "Lượt thứ mười.", "got": "Lượt thứ 10.", "got_phonemes": "lˈyə6t̪ tˈyɜ mˈyə2j.", "expected_phonemes": ["lˈyə6t̪ tˈyɜ mˈyə2j."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_10 / studio / string

```json
{"text": "Lượt thứ 10.", "expected": "Lượt thứ mười.", "got": "Lượt thứ 10.", "got_phonemes": "lˈyə6t̪ tˈyɜ mˈyə2j.", "expected_phonemes": ["lˈyə6t̪ tˈyɜ mˈyə2j."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_11 / nghe_ngay / string

```json
{"text": "Vị trí thứ 11.", "expected": "Vị trí thứ mười một.", "got": "Vị trí thứ 11.", "got_phonemes": "vˈi6 tʃˈiɜ tˈyɜ mˈyə2j mˈo6t̪.", "expected_phonemes": ["vˈi6 tʃˈiɜ tˈyɜ mˈyə2j mˈo6t̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_11 / studio / string

```json
{"text": "Vị trí thứ 11.", "expected": "Vị trí thứ mười một.", "got": "Vị trí thứ 11.", "got_phonemes": "vˈi6 tʃˈiɜ tˈyɜ mˈyə2j mˈo6t̪.", "expected_phonemes": ["vˈi6 tʃˈiɜ tˈyɜ mˈyə2j mˈo6t̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_12 / nghe_ngay / string

```json
{"text": "Vị trí thứ 12.", "expected": "Vị trí thứ mười hai.", "got": "Vị trí thứ 12.", "got_phonemes": "vˈi6 tʃˈiɜ tˈyɜ mˈyə2j hˈaːj.", "expected_phonemes": ["vˈi6 tʃˈiɜ tˈyɜ mˈyə2j hˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_12 / studio / string

```json
{"text": "Vị trí thứ 12.", "expected": "Vị trí thứ mười hai.", "got": "Vị trí thứ 12.", "got_phonemes": "vˈi6 tʃˈiɜ tˈyɜ mˈyə2j hˈaːj.", "expected_phonemes": ["vˈi6 tʃˈiɜ tˈyɜ mˈyə2j hˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_13 / nghe_ngay / string

```json
{"text": "Vị trí thứ 14.", "expected": ["Vị trí thứ mười bốn.", "Vị trí thứ mười tư."], "got": "Vị trí thứ 14.", "got_phonemes": "vˈi6 tʃˈiɜ tˈyɜ mˈyə2j bˈoɜn.", "expected_phonemes": ["vˈi6 tʃˈiɜ tˈyɜ mˈyə2j bˈoɜn.", "vˈi6 tʃˈiɜ tˈyɜ mˈyə2j t̪ˈy."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_13 / studio / string

```json
{"text": "Vị trí thứ 14.", "expected": ["Vị trí thứ mười bốn.", "Vị trí thứ mười tư."], "got": "Vị trí thứ 14.", "got_phonemes": "vˈi6 tʃˈiɜ tˈyɜ mˈyə2j bˈoɜn.", "expected_phonemes": ["vˈi6 tʃˈiɜ tˈyɜ mˈyə2j bˈoɜn.", "vˈi6 tʃˈiɜ tˈyɜ mˈyə2j t̪ˈy."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_14 / nghe_ngay / string

```json
{"text": "Vị trí thứ 15.", "expected": "Vị trí thứ mười lăm.", "got": "Vị trí thứ 15.", "got_phonemes": "vˈi6 tʃˈiɜ tˈyɜ mˈyə2j lˈam.", "expected_phonemes": ["vˈi6 tʃˈiɜ tˈyɜ mˈyə2j lˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_14 / studio / string

```json
{"text": "Vị trí thứ 15.", "expected": "Vị trí thứ mười lăm.", "got": "Vị trí thứ 15.", "got_phonemes": "vˈi6 tʃˈiɜ tˈyɜ mˈyə2j lˈam.", "expected_phonemes": ["vˈi6 tʃˈiɜ tˈyɜ mˈyə2j lˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_15 / nghe_ngay / string

```json
{"text": "Vị trí thứ 20.", "expected": "Vị trí thứ hai mươi.", "got": "Vị trí thứ 20.", "got_phonemes": "vˈi6 tʃˈiɜ tˈyɜ hˈaːj mˈyəj.", "expected_phonemes": ["vˈi6 tʃˈiɜ tˈyɜ hˈaːj mˈyəj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_15 / studio / string

```json
{"text": "Vị trí thứ 20.", "expected": "Vị trí thứ hai mươi.", "got": "Vị trí thứ 20.", "got_phonemes": "vˈi6 tʃˈiɜ tˈyɜ hˈaːj mˈyəj.", "expected_phonemes": ["vˈi6 tʃˈiɜ tˈyɜ hˈaːj mˈyəj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_16 / nghe_ngay / string

```json
{"text": "Vị trí thứ 21.", "expected": "Vị trí thứ hai mươi mốt.", "got": "Vị trí thứ 21.", "got_phonemes": "vˈi6 tʃˈiɜ tˈyɜ hˈaːj mˈyəj mˈoɜt̪.", "expected_phonemes": ["vˈi6 tʃˈiɜ tˈyɜ hˈaːj mˈyəj mˈoɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_16 / studio / string

```json
{"text": "Vị trí thứ 21.", "expected": "Vị trí thứ hai mươi mốt.", "got": "Vị trí thứ 21.", "got_phonemes": "vˈi6 tʃˈiɜ tˈyɜ hˈaːj mˈyəj mˈoɜt̪.", "expected_phonemes": ["vˈi6 tʃˈiɜ tˈyɜ hˈaːj mˈyəj mˈoɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_17 / nghe_ngay / string

```json
{"text": "Vị trí thứ 24.", "expected": ["Vị trí thứ hai mươi bốn.", "Vị trí thứ hai mươi tư."], "got": "Vị trí thứ 24.", "got_phonemes": "vˈi6 tʃˈiɜ tˈyɜ hˈaːj mˈyəj bˈoɜn.", "expected_phonemes": ["vˈi6 tʃˈiɜ tˈyɜ hˈaːj mˈyəj bˈoɜn.", "vˈi6 tʃˈiɜ tˈyɜ hˈaːj mˈyəj t̪ˈy."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_17 / studio / string

```json
{"text": "Vị trí thứ 24.", "expected": ["Vị trí thứ hai mươi bốn.", "Vị trí thứ hai mươi tư."], "got": "Vị trí thứ 24.", "got_phonemes": "vˈi6 tʃˈiɜ tˈyɜ hˈaːj mˈyəj bˈoɜn.", "expected_phonemes": ["vˈi6 tʃˈiɜ tˈyɜ hˈaːj mˈyəj bˈoɜn.", "vˈi6 tʃˈiɜ tˈyɜ hˈaːj mˈyəj t̪ˈy."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_18 / nghe_ngay / string

```json
{"text": "Vị trí thứ 25.", "expected": "Vị trí thứ hai mươi lăm.", "got": "Vị trí thứ 25.", "got_phonemes": "vˈi6 tʃˈiɜ tˈyɜ hˈaːj mˈyəj lˈam.", "expected_phonemes": ["vˈi6 tʃˈiɜ tˈyɜ hˈaːj mˈyəj lˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_18 / studio / string

```json
{"text": "Vị trí thứ 25.", "expected": "Vị trí thứ hai mươi lăm.", "got": "Vị trí thứ 25.", "got_phonemes": "vˈi6 tʃˈiɜ tˈyɜ hˈaːj mˈyəj lˈam.", "expected_phonemes": ["vˈi6 tʃˈiɜ tˈyɜ hˈaːj mˈyəj lˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_19 / nghe_ngay / string

```json
{"text": "Vị trí thứ 100.", "expected": "Vị trí thứ một trăm.", "got": "Vị trí thứ 100.", "got_phonemes": "vˈi6 tʃˈiɜ tˈyɜ mˈo6t̪ tʃˈam.", "expected_phonemes": ["vˈi6 tʃˈiɜ tˈyɜ mˈo6t̪ tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_19 / studio / string

```json
{"text": "Vị trí thứ 100.", "expected": "Vị trí thứ một trăm.", "got": "Vị trí thứ 100.", "got_phonemes": "vˈi6 tʃˈiɜ tˈyɜ mˈo6t̪ tʃˈam.", "expected_phonemes": ["vˈi6 tʃˈiɜ tˈyɜ mˈo6t̪ tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_20 / nghe_ngay / string

```json
{"text": "Vị trí thứ 101.", "expected": ["Vị trí thứ một trăm linh một.", "Vị trí thứ một trăm lẻ một."], "got": "Vị trí thứ 101.", "got_phonemes": "vˈi6 tʃˈiɜ tˈyɜ mˈo6t̪ tʃˈam lˈɛ4 mˈo6t̪.", "expected_phonemes": ["vˈi6 tʃˈiɜ tˈyɜ mˈo6t̪ tʃˈam lˈiɲ mˈo6t̪.", "vˈi6 tʃˈiɜ tˈyɜ mˈo6t̪ tʃˈam lˈɛ4 mˈo6t̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_20 / studio / string

```json
{"text": "Vị trí thứ 101.", "expected": ["Vị trí thứ một trăm linh một.", "Vị trí thứ một trăm lẻ một."], "got": "Vị trí thứ 101.", "got_phonemes": "vˈi6 tʃˈiɜ tˈyɜ mˈo6t̪ tʃˈam lˈɛ4 mˈo6t̪.", "expected_phonemes": ["vˈi6 tʃˈiɜ tˈyɜ mˈo6t̪ tʃˈam lˈiɲ mˈo6t̪.", "vˈi6 tʃˈiɜ tˈyɜ mˈo6t̪ tʃˈam lˈɛ4 mˈo6t̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### roman_17 / nghe_ngay / string

```json
{"text": "Chữ V in đậm.", "expected": ["Chữ vê in đậm.", "Chữ vi in đậm."], "got": "Chữ V in đậm.", "got_phonemes": "tʃˈy5 vˈe ˈin ɗˈə6m.", "expected_phonemes": ["tʃˈy5 vˈe ˈin ɗˈə6m.", "tʃˈy5 vˈi ˈin ɗˈə6m."], "note": "Không đọc thành năm."}
```

### roman_17 / studio / string

```json
{"text": "Chữ V in đậm.", "expected": ["Chữ vê in đậm.", "Chữ vi in đậm."], "got": "Chữ V in đậm.", "got_phonemes": "tʃˈy5 vˈe ˈin ɗˈə6m.", "expected_phonemes": ["tʃˈy5 vˈe ˈin ɗˈə6m.", "tʃˈy5 vˈi ˈin ɗˈə6m."], "note": "Không đọc thành năm."}
```

### roman_18 / nghe_ngay / string

```json
{"text": "Chữ X in nhỏ.", "expected": ["Chữ ích in nhỏ.", "Chữ éc in nhỏ.", "Chữ ét in nhỏ."], "got": "Chữ X in nhỏ.", "got_phonemes": "tʃˈy5 ˈiɜc ˈin ɲˈɔ4.", "expected_phonemes": ["tʃˈy5 ˈiɜc ˈin ɲˈɔ4.", "tʃˈy5 ˈɛɜc ˈin ɲˈɔ4.", "tʃˈy5 ˈɛɜt̪ ˈin ɲˈɔ4."], "note": "Không đọc thành mười."}
```

### roman_18 / studio / string

```json
{"text": "Chữ X in nhỏ.", "expected": ["Chữ ích in nhỏ.", "Chữ éc in nhỏ.", "Chữ ét in nhỏ."], "got": "Chữ X in nhỏ.", "got_phonemes": "tʃˈy5 ˈiɜc ˈin ɲˈɔ4.", "expected_phonemes": ["tʃˈy5 ˈiɜc ˈin ɲˈɔ4.", "tʃˈy5 ˈɛɜc ˈin ɲˈɔ4.", "tʃˈy5 ˈɛɜt̪ ˈin ɲˈɔ4."], "note": "Không đọc thành mười."}
```

### roman_20 / nghe_ngay / string

```json
{"text": "Ông X ký phiếu.", "expected": ["Ông ích ký phiếu.", "Ông X ký phiếu."], "got": "Ông <en>X</en> ký phiếu.", "got_phonemes": "ˈoŋ ˈɛks kˈiɜ fˈiɛɜw.", "expected_phonemes": ["ˈoŋ ˈiɜc kˈiɜ fˈiɛɜw.", "ˈoŋ ˈiɜc kˈiɜ fˈiɛɜw."], "note": "Ẩn danh, không phải số La Mã."}
```

### roman_20 / nghe_ngay / post_g2p

```json
{"text": "Ông X ký phiếu.", "expected": ["Ông ích ký phiếu.", "Ông X ký phiếu."], "got": "Ông <en>X</en> ký phiếu.", "got_phonemes": "ˈoŋ ˈɛks kˈiɜ fˈiɛɜw.", "expected_phonemes": ["ˈoŋ ˈiɜc kˈiɜ fˈiɛɜw.", "ˈoŋ ˈiɜc kˈiɜ fˈiɛɜw."], "note": "Ẩn danh, không phải số La Mã."}
```

### roman_20 / studio / string

```json
{"text": "Ông X ký phiếu.", "expected": ["Ông ích ký phiếu.", "Ông X ký phiếu."], "got": "Ông <en>X</en> ký phiếu.", "got_phonemes": "ˈoŋ ˈɛks kˈiɜ fˈiɛɜw.", "expected_phonemes": ["ˈoŋ ˈiɜc kˈiɜ fˈiɛɜw.", "ˈoŋ ˈiɜc kˈiɜ fˈiɛɜw."], "note": "Ẩn danh, không phải số La Mã."}
```

### roman_20 / studio / post_g2p

```json
{"text": "Ông X ký phiếu.", "expected": ["Ông ích ký phiếu.", "Ông X ký phiếu."], "got": "Ông <en>X</en> ký phiếu.", "got_phonemes": "ˈoŋ ˈɛks kˈiɜ fˈiɛɜw.", "expected_phonemes": ["ˈoŋ ˈiɜc kˈiɜ fˈiɛɜw.", "ˈoŋ ˈiɜc kˈiɜ fˈiɛɜw."], "note": "Ẩn danh, không phải số La Mã."}
```

### date_01 / nghe_ngay / string

```json
{"text": "Ngày 1/2/2026.", "expected": "Ngày một tháng hai năm hai nghìn không trăm hai mươi sáu.", "got": "Ngày 1/2/2026.", "got_phonemes": "ŋˈa2j mˈo6t̪ tˈaːɜŋ hˈaːj nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj sˈaɜw.", "expected_phonemes": ["ŋˈa2j mˈo6t̪ tˈaːɜŋ hˈaːj nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj sˈaɜw."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_01 / studio / string

```json
{"text": "Ngày 1/2/2026.", "expected": "Ngày một tháng hai năm hai nghìn không trăm hai mươi sáu.", "got": "Ngày 1/2/2026.", "got_phonemes": "ŋˈa2j mˈo6t̪ tˈaːɜŋ hˈaːj nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj sˈaɜw.", "expected_phonemes": ["ŋˈa2j mˈo6t̪ tˈaːɜŋ hˈaːj nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj sˈaɜw."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_02 / nghe_ngay / string

```json
{"text": "Ngày 02/03/2025.", "expected": "Ngày hai tháng ba năm hai nghìn không trăm hai mươi lăm.", "got": "Ngày 02/03/2025.", "got_phonemes": "ŋˈa2j hˈaːj tˈaːɜŋ bˈaː nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj lˈam.", "expected_phonemes": ["ŋˈa2j hˈaːj tˈaːɜŋ bˈaː nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj lˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_02 / studio / string

```json
{"text": "Ngày 02/03/2025.", "expected": "Ngày hai tháng ba năm hai nghìn không trăm hai mươi lăm.", "got": "Ngày 02/03/2025.", "got_phonemes": "ŋˈa2j hˈaːj tˈaːɜŋ bˈaː nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj lˈam.", "expected_phonemes": ["ŋˈa2j hˈaːj tˈaːɜŋ bˈaː nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj lˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_03 / nghe_ngay / string

```json
{"text": "Ngày 15/4/2024.", "expected": "Ngày mười lăm tháng tư năm hai nghìn không trăm hai mươi bốn.", "got": "Ngày 15/4/2024.", "got_phonemes": "ŋˈa2j mˈyə2j lˈam tˈaːɜŋ t̪ˈy nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj bˈoɜn.", "expected_phonemes": ["ŋˈa2j mˈyə2j lˈam tˈaːɜŋ t̪ˈy nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj bˈoɜn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_03 / studio / string

```json
{"text": "Ngày 15/4/2024.", "expected": "Ngày mười lăm tháng tư năm hai nghìn không trăm hai mươi bốn.", "got": "Ngày 15/4/2024.", "got_phonemes": "ŋˈa2j mˈyə2j lˈam tˈaːɜŋ t̪ˈy nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj bˈoɜn.", "expected_phonemes": ["ŋˈa2j mˈyə2j lˈam tˈaːɜŋ t̪ˈy nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj bˈoɜn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_04 / nghe_ngay / string

```json
{"text": "Ngày 20/5/2023.", "expected": "Ngày hai mươi tháng năm năm hai nghìn không trăm hai mươi ba.", "got": "Ngày 20/5/2023.", "got_phonemes": "ŋˈa2j hˈaːj mˈyəj tˈaːɜŋ nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj bˈaː.", "expected_phonemes": ["ŋˈa2j hˈaːj mˈyəj tˈaːɜŋ nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj bˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_04 / studio / string

```json
{"text": "Ngày 20/5/2023.", "expected": "Ngày hai mươi tháng năm năm hai nghìn không trăm hai mươi ba.", "got": "Ngày 20/5/2023.", "got_phonemes": "ŋˈa2j hˈaːj mˈyəj tˈaːɜŋ nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj bˈaː.", "expected_phonemes": ["ŋˈa2j hˈaːj mˈyəj tˈaːɜŋ nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj bˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_05 / nghe_ngay / string

```json
{"text": "Ngày 30/6/2022.", "expected": "Ngày ba mươi tháng sáu năm hai nghìn không trăm hai mươi hai.", "got": "Ngày 30/6/2022.", "got_phonemes": "ŋˈa2j bˈaː mˈyəj tˈaːɜŋ sˈaɜw nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj hˈaːj.", "expected_phonemes": ["ŋˈa2j bˈaː mˈyəj tˈaːɜŋ sˈaɜw nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj hˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_05 / studio / string

```json
{"text": "Ngày 30/6/2022.", "expected": "Ngày ba mươi tháng sáu năm hai nghìn không trăm hai mươi hai.", "got": "Ngày 30/6/2022.", "got_phonemes": "ŋˈa2j bˈaː mˈyəj tˈaːɜŋ sˈaɜw nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj hˈaːj.", "expected_phonemes": ["ŋˈa2j bˈaː mˈyəj tˈaːɜŋ sˈaɜw nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj hˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_06 / nghe_ngay / string

```json
{"text": "Ngày 31/7/2123.", "expected": "Ngày ba mươi mốt tháng bảy năm hai nghìn một trăm hai mươi ba.", "got": "Ngày 31/7/2123.", "got_phonemes": "ŋˈa2j bˈaː mˈyəj mˈoɜt̪ tˈaːɜŋ bˈa4j nˈam hˈaːj ŋˈi2n mˈo6t̪ tʃˈam hˈaːj mˈyəj bˈaː.", "expected_phonemes": ["ŋˈa2j bˈaː mˈyəj mˈoɜt̪ tˈaːɜŋ bˈa4j nˈam hˈaːj ŋˈi2n mˈo6t̪ tʃˈam hˈaːj mˈyəj bˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_06 / studio / string

```json
{"text": "Ngày 31/7/2123.", "expected": "Ngày ba mươi mốt tháng bảy năm hai nghìn một trăm hai mươi ba.", "got": "Ngày 31/7/2123.", "got_phonemes": "ŋˈa2j bˈaː mˈyəj mˈoɜt̪ tˈaːɜŋ bˈa4j nˈam hˈaːj ŋˈi2n mˈo6t̪ tʃˈam hˈaːj mˈyəj bˈaː.", "expected_phonemes": ["ŋˈa2j bˈaː mˈyəj mˈoɜt̪ tˈaːɜŋ bˈa4j nˈam hˈaːj ŋˈi2n mˈo6t̪ tʃˈam hˈaːj mˈyəj bˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_07 / nghe_ngay / string

```json
{"text": "Ngày 8/8/2020.", "expected": "Ngày tám tháng tám năm hai nghìn không trăm hai mươi.", "got": "Ngày 8/8/2020.", "got_phonemes": "ŋˈa2j t̪ˈaːɜm tˈaːɜŋ t̪ˈaːɜm nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj.", "expected_phonemes": ["ŋˈa2j t̪ˈaːɜm tˈaːɜŋ t̪ˈaːɜm nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_07 / studio / string

```json
{"text": "Ngày 8/8/2020.", "expected": "Ngày tám tháng tám năm hai nghìn không trăm hai mươi.", "got": "Ngày 8/8/2020.", "got_phonemes": "ŋˈa2j t̪ˈaːɜm tˈaːɜŋ t̪ˈaːɜm nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj.", "expected_phonemes": ["ŋˈa2j t̪ˈaːɜm tˈaːɜŋ t̪ˈaːɜm nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_08 / nghe_ngay / string

```json
{"text": "Ngày 9/9/2019.", "expected": "Ngày chín tháng chín năm hai nghìn không trăm mười chín.", "got": "Ngày 9/9/2019.", "got_phonemes": "ŋˈa2j tʃˈiɜn tˈaːɜŋ tʃˈiɜn nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam mˈyə2j tʃˈiɜn.", "expected_phonemes": ["ŋˈa2j tʃˈiɜn tˈaːɜŋ tʃˈiɜn nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam mˈyə2j tʃˈiɜn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_08 / studio / string

```json
{"text": "Ngày 9/9/2019.", "expected": "Ngày chín tháng chín năm hai nghìn không trăm mười chín.", "got": "Ngày 9/9/2019.", "got_phonemes": "ŋˈa2j tʃˈiɜn tˈaːɜŋ tʃˈiɜn nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam mˈyə2j tʃˈiɜn.", "expected_phonemes": ["ŋˈa2j tʃˈiɜn tˈaːɜŋ tʃˈiɜn nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam mˈyə2j tʃˈiɜn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_09 / nghe_ngay / string

```json
{"text": "Ngày 10/10/2018.", "expected": "Ngày mười tháng mười năm hai nghìn không trăm mười tám.", "got": "Ngày 10/10/2018.", "got_phonemes": "ŋˈa2j mˈyə2j tˈaːɜŋ mˈyə2j nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam mˈyə2j t̪ˈaːɜm.", "expected_phonemes": ["ŋˈa2j mˈyə2j tˈaːɜŋ mˈyə2j nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam mˈyə2j t̪ˈaːɜm."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_09 / studio / string

```json
{"text": "Ngày 10/10/2018.", "expected": "Ngày mười tháng mười năm hai nghìn không trăm mười tám.", "got": "Ngày 10/10/2018.", "got_phonemes": "ŋˈa2j mˈyə2j tˈaːɜŋ mˈyə2j nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam mˈyə2j t̪ˈaːɜm.", "expected_phonemes": ["ŋˈa2j mˈyə2j tˈaːɜŋ mˈyə2j nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam mˈyə2j t̪ˈaːɜm."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_10 / nghe_ngay / string

```json
{"text": "Ngày 11/11/2347.", "expected": "Ngày mười một tháng mười một năm hai nghìn ba trăm bốn mươi bảy.", "got": "Ngày 11/11/2347.", "got_phonemes": "ŋˈa2j mˈyə2j mˈo6t̪ tˈaːɜŋ mˈyə2j mˈo6t̪ nˈam hˈaːj ŋˈi2n bˈaː tʃˈam bˈoɜn mˈyəj bˈa4j.", "expected_phonemes": ["ŋˈa2j mˈyə2j mˈo6t̪ tˈaːɜŋ mˈyə2j mˈo6t̪ nˈam hˈaːj ŋˈi2n bˈaː tʃˈam bˈoɜn mˈyəj bˈa4j."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_10 / studio / string

```json
{"text": "Ngày 11/11/2347.", "expected": "Ngày mười một tháng mười một năm hai nghìn ba trăm bốn mươi bảy.", "got": "Ngày 11/11/2347.", "got_phonemes": "ŋˈa2j mˈyə2j mˈo6t̪ tˈaːɜŋ mˈyə2j mˈo6t̪ nˈam hˈaːj ŋˈi2n bˈaː tʃˈam bˈoɜn mˈyəj bˈa4j.", "expected_phonemes": ["ŋˈa2j mˈyə2j mˈo6t̪ tˈaːɜŋ mˈyə2j mˈo6t̪ nˈam hˈaːj ŋˈi2n bˈaː tʃˈam bˈoɜn mˈyəj bˈa4j."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_11 / nghe_ngay / string

```json
{"text": "Ngày 12/12/2458.", "expected": "Ngày mười hai tháng mười hai năm hai nghìn bốn trăm năm mươi tám.", "got": "Ngày 12/12/2458.", "got_phonemes": "ŋˈa2j mˈyə2j hˈaːj tˈaːɜŋ mˈyə2j hˈaːj nˈam hˈaːj ŋˈi2n bˈoɜn tʃˈam nˈam mˈyəj t̪ˈaːɜm.", "expected_phonemes": ["ŋˈa2j mˈyə2j hˈaːj tˈaːɜŋ mˈyə2j hˈaːj nˈam hˈaːj ŋˈi2n bˈoɜn tʃˈam nˈam mˈyəj t̪ˈaːɜm."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_11 / studio / string

```json
{"text": "Ngày 12/12/2458.", "expected": "Ngày mười hai tháng mười hai năm hai nghìn bốn trăm năm mươi tám.", "got": "Ngày 12/12/2458.", "got_phonemes": "ŋˈa2j mˈyə2j hˈaːj tˈaːɜŋ mˈyə2j hˈaːj nˈam hˈaːj ŋˈi2n bˈoɜn tʃˈam nˈam mˈyəj t̪ˈaːɜm.", "expected_phonemes": ["ŋˈa2j mˈyə2j hˈaːj tˈaːɜŋ mˈyə2j hˈaːj nˈam hˈaːj ŋˈi2n bˈoɜn tʃˈam nˈam mˈyəj t̪ˈaːɜm."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_12 / nghe_ngay / string

```json
{"text": "Ngày 29/2/2024.", "expected": "Ngày hai mươi chín tháng hai năm hai nghìn không trăm hai mươi bốn.", "got": "Ngày 29/2/2024.", "got_phonemes": "ŋˈa2j hˈaːj mˈyəj tʃˈiɜn tˈaːɜŋ hˈaːj nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj bˈoɜn.", "expected_phonemes": ["ŋˈa2j hˈaːj mˈyəj tʃˈiɜn tˈaːɜŋ hˈaːj nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj bˈoɜn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_12 / studio / string

```json
{"text": "Ngày 29/2/2024.", "expected": "Ngày hai mươi chín tháng hai năm hai nghìn không trăm hai mươi bốn.", "got": "Ngày 29/2/2024.", "got_phonemes": "ŋˈa2j hˈaːj mˈyəj tʃˈiɜn tˈaːɜŋ hˈaːj nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj bˈoɜn.", "expected_phonemes": ["ŋˈa2j hˈaːj mˈyəj tʃˈiɜn tˈaːɜŋ hˈaːj nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj bˈoɜn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_13 / nghe_ngay / string

```json
{"text": "Ngày 1-3-2026.", "expected": "Ngày một tháng ba năm hai nghìn không trăm hai mươi sáu.", "got": "Ngày 1-3-2026.", "got_phonemes": "ŋˈa2j mˈo6t̪ tˈaːɜŋ bˈaː nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj sˈaɜw.", "expected_phonemes": ["ŋˈa2j mˈo6t̪ tˈaːɜŋ bˈaː nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj sˈaɜw."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_13 / studio / string

```json
{"text": "Ngày 1-3-2026.", "expected": "Ngày một tháng ba năm hai nghìn không trăm hai mươi sáu.", "got": "Ngày 1-3-2026.", "got_phonemes": "ŋˈa2j mˈo6t̪ tˈaːɜŋ bˈaː nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj sˈaɜw.", "expected_phonemes": ["ŋˈa2j mˈo6t̪ tˈaːɜŋ bˈaː nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj sˈaɜw."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_14 / nghe_ngay / string

```json
{"text": "Ngày 2.4.2026.", "expected": "Ngày hai tháng tư năm hai nghìn không trăm hai mươi sáu.", "got": "Ngày 2.4.2026.", "got_phonemes": "ŋˈa2j hˈaːj tˈaːɜŋ t̪ˈy nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj sˈaɜw.", "expected_phonemes": ["ŋˈa2j hˈaːj tˈaːɜŋ t̪ˈy nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj sˈaɜw."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_14 / studio / string

```json
{"text": "Ngày 2.4.2026.", "expected": "Ngày hai tháng tư năm hai nghìn không trăm hai mươi sáu.", "got": "Ngày 2.4.2026.", "got_phonemes": "ŋˈa2j hˈaːj tˈaːɜŋ t̪ˈy nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj sˈaɜw.", "expected_phonemes": ["ŋˈa2j hˈaːj tˈaːɜŋ t̪ˈy nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj sˈaɜw."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_15 / nghe_ngay / string

```json
{"text": "Ngày 2026-05-03.", "expected": "Ngày ba tháng năm năm hai nghìn không trăm hai mươi sáu.", "got": "Ngày 2026-05-03.", "got_phonemes": "ŋˈa2j bˈaː tˈaːɜŋ nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj sˈaɜw.", "expected_phonemes": ["ŋˈa2j bˈaː tˈaːɜŋ nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj sˈaɜw."], "note": "Định dạng ISO, năm đi trước."}
```

### date_15 / studio / string

```json
{"text": "Ngày 2026-05-03.", "expected": "Ngày ba tháng năm năm hai nghìn không trăm hai mươi sáu.", "got": "Ngày 2026-05-03.", "got_phonemes": "ŋˈa2j bˈaː tˈaːɜŋ nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj sˈaɜw.", "expected_phonemes": ["ŋˈa2j bˈaː tˈaːɜŋ nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj sˈaɜw."], "note": "Định dạng ISO, năm đi trước."}
```

### date_16 / nghe_ngay / string

```json
{"text": "Hẹn ngày 4/6.", "expected": "Hẹn ngày bốn tháng sáu.", "got": "Hẹn ngày 4 tháng 6.", "got_phonemes": "hˈɛ6n ŋˈa2j bˈoɜn tˈaːɜŋ sˈaɜw.", "expected_phonemes": ["hˈɛ6n ŋˈa2j bˈoɜn tˈaːɜŋ sˈaɜw."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_16 / studio / string

```json
{"text": "Hẹn ngày 4/6.", "expected": "Hẹn ngày bốn tháng sáu.", "got": "Hẹn ngày 4 tháng 6.", "got_phonemes": "hˈɛ6n ŋˈa2j bˈoɜn tˈaːɜŋ sˈaɜw.", "expected_phonemes": ["hˈɛ6n ŋˈa2j bˈoɜn tˈaːɜŋ sˈaɜw."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_17 / nghe_ngay / string

```json
{"text": "Hẹn ngày 5-7.", "expected": "Hẹn ngày năm tháng bảy.", "got": "Hẹn ngày 5 đến 7.", "got_phonemes": "hˈɛ6n ŋˈa2j nˈam ɗˌeɜn bˈa4j.", "expected_phonemes": ["hˈɛ6n ŋˈa2j nˈam tˈaːɜŋ bˈa4j."], "note": "Có tiền tố ngày, ưu tiên ngày tháng."}
```

### date_17 / nghe_ngay / post_g2p

```json
{"text": "Hẹn ngày 5-7.", "expected": "Hẹn ngày năm tháng bảy.", "got": "Hẹn ngày 5 đến 7.", "got_phonemes": "hˈɛ6n ŋˈa2j nˈam ɗˌeɜn bˈa4j.", "expected_phonemes": ["hˈɛ6n ŋˈa2j nˈam tˈaːɜŋ bˈa4j."], "note": "Có tiền tố ngày, ưu tiên ngày tháng."}
```

### date_17 / studio / string

```json
{"text": "Hẹn ngày 5-7.", "expected": "Hẹn ngày năm tháng bảy.", "got": "Hẹn ngày 5 đến 7.", "got_phonemes": "hˈɛ6n ŋˈa2j nˈam ɗˌeɜn bˈa4j.", "expected_phonemes": ["hˈɛ6n ŋˈa2j nˈam tˈaːɜŋ bˈa4j."], "note": "Có tiền tố ngày, ưu tiên ngày tháng."}
```

### date_17 / studio / post_g2p

```json
{"text": "Hẹn ngày 5-7.", "expected": "Hẹn ngày năm tháng bảy.", "got": "Hẹn ngày 5 đến 7.", "got_phonemes": "hˈɛ6n ŋˈa2j nˈam ɗˌeɜn bˈa4j.", "expected_phonemes": ["hˈɛ6n ŋˈa2j nˈam tˈaːɜŋ bˈa4j."], "note": "Có tiền tố ngày, ưu tiên ngày tháng."}
```

### date_18 / nghe_ngay / string

```json
{"text": "Tháng 8/2026.", "expected": "Tháng tám năm hai nghìn không trăm hai mươi sáu.", "got": "Tháng 8 năm 2026.", "got_phonemes": "tˈaːɜŋ t̪ˈaːɜm nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj sˈaɜw.", "expected_phonemes": ["tˈaːɜŋ t̪ˈaːɜm nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj sˈaɜw."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_18 / studio / string

```json
{"text": "Tháng 8/2026.", "expected": "Tháng tám năm hai nghìn không trăm hai mươi sáu.", "got": "Tháng 8 năm 2026.", "got_phonemes": "tˈaːɜŋ t̪ˈaːɜm nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj sˈaɜw.", "expected_phonemes": ["tˈaːɜŋ t̪ˈaːɜm nˈam hˈaːj ŋˈi2n xˌoŋ tʃˈam hˈaːj mˈyəj sˈaɜw."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_01 / nghe_ngay / string

```json
{"text": "Hẹn lúc 7:00.", "expected": ["Hẹn lúc bảy giờ.", "Hẹn lúc bảy giờ không phút."], "got": "Hẹn lúc 7:00.", "got_phonemes": "hˈɛ6n lˌuɜc bˈa4j zˈəː2 xˌoŋ fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc bˈa4j zˈəː2.", "hˈɛ6n lˌuɜc bˈa4j zˈəː2 xˌoŋ fˈuɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_01 / studio / string

```json
{"text": "Hẹn lúc 7:00.", "expected": ["Hẹn lúc bảy giờ.", "Hẹn lúc bảy giờ không phút."], "got": "Hẹn lúc 7:00.", "got_phonemes": "hˈɛ6n lˌuɜc bˈa4j zˈəː2 xˌoŋ fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc bˈa4j zˈəː2.", "hˈɛ6n lˌuɜc bˈa4j zˈəː2 xˌoŋ fˈuɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_02 / nghe_ngay / string

```json
{"text": "Hẹn lúc 07:05.", "expected": ["Hẹn lúc bảy giờ năm phút.", "Hẹn lúc bảy giờ linh năm phút."], "got": "Hẹn lúc 07:05.", "got_phonemes": "hˈɛ6n lˌuɜc bˈa4j zˈəː2 nˈam fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc bˈa4j zˈəː2 nˈam fˈuɜt̪.", "hˈɛ6n lˌuɜc bˈa4j zˈəː2 lˈiɲ nˈam fˈuɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_02 / studio / string

```json
{"text": "Hẹn lúc 07:05.", "expected": ["Hẹn lúc bảy giờ năm phút.", "Hẹn lúc bảy giờ linh năm phút."], "got": "Hẹn lúc 07:05.", "got_phonemes": "hˈɛ6n lˌuɜc bˈa4j zˈəː2 nˈam fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc bˈa4j zˈəː2 nˈam fˈuɜt̪.", "hˈɛ6n lˌuɜc bˈa4j zˈəː2 lˈiɲ nˈam fˈuɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_03 / nghe_ngay / string

```json
{"text": "Hẹn lúc 8:15.", "expected": "Hẹn lúc tám giờ mười lăm phút.", "got": "Hẹn lúc 8:15.", "got_phonemes": "hˈɛ6n lˌuɜc t̪ˈaːɜm zˈəː2 mˈyə2j lˈam fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc t̪ˈaːɜm zˈəː2 mˈyə2j lˈam fˈuɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_03 / studio / string

```json
{"text": "Hẹn lúc 8:15.", "expected": "Hẹn lúc tám giờ mười lăm phút.", "got": "Hẹn lúc 8:15.", "got_phonemes": "hˈɛ6n lˌuɜc t̪ˈaːɜm zˈəː2 mˈyə2j lˈam fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc t̪ˈaːɜm zˈəː2 mˈyə2j lˈam fˈuɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_04 / nghe_ngay / string

```json
{"text": "Hẹn lúc 9:30.", "expected": ["Hẹn lúc chín giờ ba mươi phút.", "Hẹn lúc chín giờ rưỡi."], "got": "Hẹn lúc 9:30.", "got_phonemes": "hˈɛ6n lˌuɜc tʃˈiɜn zˈəː2 bˈaː mˈyəj fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc tʃˈiɜn zˈəː2 bˈaː mˈyəj fˈuɜt̪.", "hˈɛ6n lˌuɜc tʃˈiɜn zˈəː2 ɹˈyə5j."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_04 / studio / string

```json
{"text": "Hẹn lúc 9:30.", "expected": ["Hẹn lúc chín giờ ba mươi phút.", "Hẹn lúc chín giờ rưỡi."], "got": "Hẹn lúc 9:30.", "got_phonemes": "hˈɛ6n lˌuɜc tʃˈiɜn zˈəː2 bˈaː mˈyəj fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc tʃˈiɜn zˈəː2 bˈaː mˈyəj fˈuɜt̪.", "hˈɛ6n lˌuɜc tʃˈiɜn zˈəː2 ɹˈyə5j."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_05 / nghe_ngay / string

```json
{"text": "Hẹn lúc 10:45.", "expected": "Hẹn lúc mười giờ bốn mươi lăm phút.", "got": "Hẹn lúc 10:45.", "got_phonemes": "hˈɛ6n lˌuɜc mˈyə2j zˈəː2 bˈoɜn mˈyəj lˈam fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc mˈyə2j zˈəː2 bˈoɜn mˈyəj lˈam fˈuɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_05 / studio / string

```json
{"text": "Hẹn lúc 10:45.", "expected": "Hẹn lúc mười giờ bốn mươi lăm phút.", "got": "Hẹn lúc 10:45.", "got_phonemes": "hˈɛ6n lˌuɜc mˈyə2j zˈəː2 bˈoɜn mˈyəj lˈam fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc mˈyə2j zˈəː2 bˈoɜn mˈyəj lˈam fˈuɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_06 / nghe_ngay / string

```json
{"text": "Hẹn lúc 12:00.", "expected": ["Hẹn lúc mười hai giờ.", "Hẹn lúc mười hai giờ không phút."], "got": "Hẹn lúc 12:00.", "got_phonemes": "hˈɛ6n lˌuɜc mˈyə2j hˈaːj zˈəː2 xˌoŋ fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc mˈyə2j hˈaːj zˈəː2.", "hˈɛ6n lˌuɜc mˈyə2j hˈaːj zˈəː2 xˌoŋ fˈuɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_06 / studio / string

```json
{"text": "Hẹn lúc 12:00.", "expected": ["Hẹn lúc mười hai giờ.", "Hẹn lúc mười hai giờ không phút."], "got": "Hẹn lúc 12:00.", "got_phonemes": "hˈɛ6n lˌuɜc mˈyə2j hˈaːj zˈəː2 xˌoŋ fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc mˈyə2j hˈaːj zˈəː2.", "hˈɛ6n lˌuɜc mˈyə2j hˈaːj zˈəː2 xˌoŋ fˈuɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_07 / nghe_ngay / string

```json
{"text": "Hẹn lúc 13:20.", "expected": "Hẹn lúc mười ba giờ hai mươi phút.", "got": "Hẹn lúc 13:20.", "got_phonemes": "hˈɛ6n lˌuɜc mˈyə2j bˈaː zˈəː2 hˈaːj mˈyəj fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc mˈyə2j bˈaː zˈəː2 hˈaːj mˈyəj fˈuɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_07 / studio / string

```json
{"text": "Hẹn lúc 13:20.", "expected": "Hẹn lúc mười ba giờ hai mươi phút.", "got": "Hẹn lúc 13:20.", "got_phonemes": "hˈɛ6n lˌuɜc mˈyə2j bˈaː zˈəː2 hˈaːj mˈyəj fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc mˈyə2j bˈaː zˈəː2 hˈaːj mˈyəj fˈuɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_08 / nghe_ngay / string

```json
{"text": "Hẹn lúc 18:40.", "expected": "Hẹn lúc mười tám giờ bốn mươi phút.", "got": "Hẹn lúc 18:40.", "got_phonemes": "hˈɛ6n lˌuɜc mˈyə2j t̪ˈaːɜm zˈəː2 bˈoɜn mˈyəj fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc mˈyə2j t̪ˈaːɜm zˈəː2 bˈoɜn mˈyəj fˈuɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_08 / studio / string

```json
{"text": "Hẹn lúc 18:40.", "expected": "Hẹn lúc mười tám giờ bốn mươi phút.", "got": "Hẹn lúc 18:40.", "got_phonemes": "hˈɛ6n lˌuɜc mˈyə2j t̪ˈaːɜm zˈəː2 bˈoɜn mˈyəj fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc mˈyə2j t̪ˈaːɜm zˈəː2 bˈoɜn mˈyəj fˈuɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_09 / nghe_ngay / string

```json
{"text": "Hẹn lúc 23:00.", "expected": "Hẹn lúc hai mươi ba giờ.", "got": "Hẹn lúc 23:00.", "got_phonemes": "hˈɛ6n lˌuɜc hˈaːj mˈyəj bˈaː zˈəː2 xˌoŋ fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc hˈaːj mˈyəj bˈaː zˈəː2."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_09 / nghe_ngay / post_g2p

```json
{"text": "Hẹn lúc 23:00.", "expected": "Hẹn lúc hai mươi ba giờ.", "got": "Hẹn lúc 23:00.", "got_phonemes": "hˈɛ6n lˌuɜc hˈaːj mˈyəj bˈaː zˈəː2 xˌoŋ fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc hˈaːj mˈyəj bˈaː zˈəː2."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_09 / studio / string

```json
{"text": "Hẹn lúc 23:00.", "expected": "Hẹn lúc hai mươi ba giờ.", "got": "Hẹn lúc 23:00.", "got_phonemes": "hˈɛ6n lˌuɜc hˈaːj mˈyəj bˈaː zˈəː2 xˌoŋ fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc hˈaːj mˈyəj bˈaː zˈəː2."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_09 / studio / post_g2p

```json
{"text": "Hẹn lúc 23:00.", "expected": "Hẹn lúc hai mươi ba giờ.", "got": "Hẹn lúc 23:00.", "got_phonemes": "hˈɛ6n lˌuɜc hˈaːj mˈyəj bˈaː zˈəː2 xˌoŋ fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc hˈaːj mˈyəj bˈaː zˈəː2."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_10 / nghe_ngay / string

```json
{"text": "Hẹn lúc 00:00.", "expected": ["Hẹn lúc không giờ.", "Hẹn lúc không giờ không phút."], "got": "Hẹn lúc 00:00.", "got_phonemes": "hˈɛ6n lˌuɜc xˌoŋ zˈəː2 xˌoŋ fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc xˌoŋ zˈəː2.", "hˈɛ6n lˌuɜc xˌoŋ zˈəː2 xˌoŋ fˈuɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_10 / studio / string

```json
{"text": "Hẹn lúc 00:00.", "expected": ["Hẹn lúc không giờ.", "Hẹn lúc không giờ không phút."], "got": "Hẹn lúc 00:00.", "got_phonemes": "hˈɛ6n lˌuɜc xˌoŋ zˈəː2 xˌoŋ fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc xˌoŋ zˈəː2.", "hˈɛ6n lˌuɜc xˌoŋ zˈəː2 xˌoŋ fˈuɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_11 / nghe_ngay / string

```json
{"text": "Hẹn lúc 7h.", "expected": "Hẹn lúc bảy giờ.", "got": "Hẹn lúc 7h.", "got_phonemes": "hˈɛ6n lˌuɜc bˈa4j zˈəː2.", "expected_phonemes": ["hˈɛ6n lˌuɜc bˈa4j zˈəː2."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_11 / studio / string

```json
{"text": "Hẹn lúc 7h.", "expected": "Hẹn lúc bảy giờ.", "got": "Hẹn lúc 7h.", "got_phonemes": "hˈɛ6n lˌuɜc bˈa4j zˈəː2.", "expected_phonemes": ["hˈɛ6n lˌuɜc bˈa4j zˈəː2."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_12 / nghe_ngay / string

```json
{"text": "Hẹn lúc 8h05.", "expected": ["Hẹn lúc tám giờ năm phút.", "Hẹn lúc tám giờ linh năm phút."], "got": "Hẹn lúc 8h05.", "got_phonemes": "hˈɛ6n lˌuɜc t̪ˈaːɜm zˈəː2 nˈam fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc t̪ˈaːɜm zˈəː2 nˈam fˈuɜt̪.", "hˈɛ6n lˌuɜc t̪ˈaːɜm zˈəː2 lˈiɲ nˈam fˈuɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_12 / studio / string

```json
{"text": "Hẹn lúc 8h05.", "expected": ["Hẹn lúc tám giờ năm phút.", "Hẹn lúc tám giờ linh năm phút."], "got": "Hẹn lúc 8h05.", "got_phonemes": "hˈɛ6n lˌuɜc t̪ˈaːɜm zˈəː2 nˈam fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc t̪ˈaːɜm zˈəː2 nˈam fˈuɜt̪.", "hˈɛ6n lˌuɜc t̪ˈaːɜm zˈəː2 lˈiɲ nˈam fˈuɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_13 / nghe_ngay / string

```json
{"text": "Hẹn lúc 9h30.", "expected": ["Hẹn lúc chín giờ ba mươi phút.", "Hẹn lúc chín giờ rưỡi."], "got": "Hẹn lúc 9h30.", "got_phonemes": "hˈɛ6n lˌuɜc tʃˈiɜn zˈəː2 bˈaː mˈyəj fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc tʃˈiɜn zˈəː2 bˈaː mˈyəj fˈuɜt̪.", "hˈɛ6n lˌuɜc tʃˈiɜn zˈəː2 ɹˈyə5j."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_13 / studio / string

```json
{"text": "Hẹn lúc 9h30.", "expected": ["Hẹn lúc chín giờ ba mươi phút.", "Hẹn lúc chín giờ rưỡi."], "got": "Hẹn lúc 9h30.", "got_phonemes": "hˈɛ6n lˌuɜc tʃˈiɜn zˈəː2 bˈaː mˈyəj fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc tʃˈiɜn zˈəː2 bˈaː mˈyəj fˈuɜt̪.", "hˈɛ6n lˌuɜc tʃˈiɜn zˈəː2 ɹˈyə5j."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_14 / nghe_ngay / string

```json
{"text": "Hẹn lúc 10h45.", "expected": "Hẹn lúc mười giờ bốn mươi lăm phút.", "got": "Hẹn lúc 10h45.", "got_phonemes": "hˈɛ6n lˌuɜc mˈyə2j zˈəː2 bˈoɜn mˈyəj lˈam fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc mˈyə2j zˈəː2 bˈoɜn mˈyəj lˈam fˈuɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_14 / studio / string

```json
{"text": "Hẹn lúc 10h45.", "expected": "Hẹn lúc mười giờ bốn mươi lăm phút.", "got": "Hẹn lúc 10h45.", "got_phonemes": "hˈɛ6n lˌuɜc mˈyə2j zˈəː2 bˈoɜn mˈyəj lˈam fˈuɜt̪.", "expected_phonemes": ["hˈɛ6n lˌuɜc mˈyə2j zˈəː2 bˈoɜn mˈyəj lˈam fˈuɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_16 / nghe_ngay / string

```json
{"text": "Đồng hồ 01:02:03.", "expected": "Đồng hồ một giờ hai phút ba giây.", "got": "Đồng hồ 01:02:03.", "got_phonemes": "ɗˈo2ŋ hˈo2 mˈo6t̪ zˈəː2 hˈaːj fˈuɜt̪ bˈaː zˈəɪ.", "expected_phonemes": ["ɗˈo2ŋ hˈo2 mˈo6t̪ zˈəː2 hˈaːj fˈuɜt̪ bˈaː zˈəɪ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_16 / studio / string

```json
{"text": "Đồng hồ 01:02:03.", "expected": "Đồng hồ một giờ hai phút ba giây.", "got": "Đồng hồ 01:02:03.", "got_phonemes": "ɗˈo2ŋ hˈo2 mˈo6t̪ zˈəː2 hˈaːj fˈuɜt̪ bˈaː zˈəɪ.", "expected_phonemes": ["ɗˈo2ŋ hˈo2 mˈo6t̪ zˈəː2 hˈaːj fˈuɜt̪ bˈaː zˈəɪ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_17 / nghe_ngay / string

```json
{"text": "Đồng hồ 12:34:56.", "expected": ["Đồng hồ mười hai giờ ba mươi bốn phút năm mươi sáu giây.", "Đồng hồ mười hai giờ ba mươi tư phút năm mươi sáu giây."], "got": "Đồng hồ 12:34:56.", "got_phonemes": "ɗˈo2ŋ hˈo2 mˈyə2j hˈaːj zˈəː2 bˈaː mˈyəj bˈoɜn fˈuɜt̪ nˈam mˈyəj sˈaɜw zˈəɪ.", "expected_phonemes": ["ɗˈo2ŋ hˈo2 mˈyə2j hˈaːj zˈəː2 bˈaː mˈyəj bˈoɜn fˈuɜt̪ nˈam mˈyəj sˈaɜw zˈəɪ.", "ɗˈo2ŋ hˈo2 mˈyə2j hˈaːj zˈəː2 bˈaː mˈyəj t̪ˈy fˈuɜt̪ nˈam mˈyəj sˈaɜw zˈəɪ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_17 / studio / string

```json
{"text": "Đồng hồ 12:34:56.", "expected": ["Đồng hồ mười hai giờ ba mươi bốn phút năm mươi sáu giây.", "Đồng hồ mười hai giờ ba mươi tư phút năm mươi sáu giây."], "got": "Đồng hồ 12:34:56.", "got_phonemes": "ɗˈo2ŋ hˈo2 mˈyə2j hˈaːj zˈəː2 bˈaː mˈyəj bˈoɜn fˈuɜt̪ nˈam mˈyəj sˈaɜw zˈəɪ.", "expected_phonemes": ["ɗˈo2ŋ hˈo2 mˈyə2j hˈaːj zˈəː2 bˈaː mˈyəj bˈoɜn fˈuɜt̪ nˈam mˈyəj sˈaɜw zˈəɪ.", "ɗˈo2ŋ hˈo2 mˈyə2j hˈaːj zˈəː2 bˈaː mˈyəj t̪ˈy fˈuɜt̪ nˈam mˈyəj sˈaɜw zˈəɪ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_18 / nghe_ngay / string

```json
{"text": "Hẹn lúc 7 AM.", "expected": "Hẹn lúc bảy giờ sáng.", "got": "Hẹn lúc bảy AM.", "got_phonemes": "hˈɛ6n lˌuɜc bˈa4j ˈeɪ ˈɛm.", "expected_phonemes": ["hˈɛ6n lˌuɜc bˈa4j zˈəː2 sˈaːɜŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_18 / nghe_ngay / post_g2p

```json
{"text": "Hẹn lúc 7 AM.", "expected": "Hẹn lúc bảy giờ sáng.", "got": "Hẹn lúc bảy AM.", "got_phonemes": "hˈɛ6n lˌuɜc bˈa4j ˈeɪ ˈɛm.", "expected_phonemes": ["hˈɛ6n lˌuɜc bˈa4j zˈəː2 sˈaːɜŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_18 / studio / string

```json
{"text": "Hẹn lúc 7 AM.", "expected": "Hẹn lúc bảy giờ sáng.", "got": "Hẹn lúc bảy AM.", "got_phonemes": "hˈɛ6n lˌuɜc bˈa4j ˈeɪ ˈɛm.", "expected_phonemes": ["hˈɛ6n lˌuɜc bˈa4j zˈəː2 sˈaːɜŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_18 / studio / post_g2p

```json
{"text": "Hẹn lúc 7 AM.", "expected": "Hẹn lúc bảy giờ sáng.", "got": "Hẹn lúc bảy AM.", "got_phonemes": "hˈɛ6n lˌuɜc bˈa4j ˈeɪ ˈɛm.", "expected_phonemes": ["hˈɛ6n lˌuɜc bˈa4j zˈəː2 sˈaːɜŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_19 / nghe_ngay / string

```json
{"text": "Hẹn lúc 8 PM.", "expected": "Hẹn lúc tám giờ tối.", "got": "Hẹn lúc tám <en>P M</en>.", "got_phonemes": "hˈɛ6n lˌuɜc t̪ˈaːɜm pˈiː ˈɛm.", "expected_phonemes": ["hˈɛ6n lˌuɜc t̪ˈaːɜm zˈəː2 t̪ˈoɜj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_19 / nghe_ngay / post_g2p

```json
{"text": "Hẹn lúc 8 PM.", "expected": "Hẹn lúc tám giờ tối.", "got": "Hẹn lúc tám <en>P M</en>.", "got_phonemes": "hˈɛ6n lˌuɜc t̪ˈaːɜm pˈiː ˈɛm.", "expected_phonemes": ["hˈɛ6n lˌuɜc t̪ˈaːɜm zˈəː2 t̪ˈoɜj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_19 / studio / string

```json
{"text": "Hẹn lúc 8 PM.", "expected": "Hẹn lúc tám giờ tối.", "got": "Hẹn lúc tám <en>P M</en>.", "got_phonemes": "hˈɛ6n lˌuɜc t̪ˈaːɜm pˈiː ˈɛm.", "expected_phonemes": ["hˈɛ6n lˌuɜc t̪ˈaːɜm zˈəː2 t̪ˈoɜj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_19 / studio / post_g2p

```json
{"text": "Hẹn lúc 8 PM.", "expected": "Hẹn lúc tám giờ tối.", "got": "Hẹn lúc tám <en>P M</en>.", "got_phonemes": "hˈɛ6n lˌuɜc t̪ˈaːɜm pˈiː ˈɛm.", "expected_phonemes": ["hˈɛ6n lˌuɜc t̪ˈaːɜm zˈəː2 t̪ˈoɜj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_20 / nghe_ngay / string

```json
{"text": "Hẹn lúc 3:15 PM.", "expected": "Hẹn lúc ba giờ mười lăm phút chiều.", "got": "Hẹn lúc 3:15 <en>P M</en>.", "got_phonemes": "hˈɛ6n lˌuɜc bˈaː zˈəː2 mˈyə2j lˈam fˈuɜt̪ pˈiː ˈɛm.", "expected_phonemes": ["hˈɛ6n lˌuɜc bˈaː zˈəː2 mˈyə2j lˈam fˈuɜt̪ tʃˈiɛ2w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_20 / nghe_ngay / post_g2p

```json
{"text": "Hẹn lúc 3:15 PM.", "expected": "Hẹn lúc ba giờ mười lăm phút chiều.", "got": "Hẹn lúc 3:15 <en>P M</en>.", "got_phonemes": "hˈɛ6n lˌuɜc bˈaː zˈəː2 mˈyə2j lˈam fˈuɜt̪ pˈiː ˈɛm.", "expected_phonemes": ["hˈɛ6n lˌuɜc bˈaː zˈəː2 mˈyə2j lˈam fˈuɜt̪ tʃˈiɛ2w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_20 / studio / string

```json
{"text": "Hẹn lúc 3:15 PM.", "expected": "Hẹn lúc ba giờ mười lăm phút chiều.", "got": "Hẹn lúc 3:15 <en>P M</en>.", "got_phonemes": "hˈɛ6n lˌuɜc bˈaː zˈəː2 mˈyə2j lˈam fˈuɜt̪ pˈiː ˈɛm.", "expected_phonemes": ["hˈɛ6n lˌuɜc bˈaː zˈəː2 mˈyə2j lˈam fˈuɜt̪ tʃˈiɛ2w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_20 / studio / post_g2p

```json
{"text": "Hẹn lúc 3:15 PM.", "expected": "Hẹn lúc ba giờ mười lăm phút chiều.", "got": "Hẹn lúc 3:15 <en>P M</en>.", "got_phonemes": "hˈɛ6n lˌuɜc bˈaː zˈəː2 mˈyə2j lˈam fˈuɜt̪ pˈiː ˈɛm.", "expected_phonemes": ["hˈɛ6n lˌuɜc bˈaː zˈəː2 mˈyə2j lˈam fˈuɜt̪ tʃˈiɛ2w."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_01 / nghe_ngay / string

```json
{"text": "Cần 1-2 hạt.", "expected": ["Cần một đến hai hạt.", "Cần một hai hạt."], "got": "Cần 1 đến 2 hạt.", "got_phonemes": "kˈə2n mˈo6t̪ ɗˌeɜn hˈaːj hˈaː6t̪.", "expected_phonemes": ["kˈə2n mˈo6t̪ ɗˌeɜn hˈaːj hˈaː6t̪.", "kˈə2n mˈo6t̪ hˈaːj hˈaː6t̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_01 / studio / string

```json
{"text": "Cần 1-2 hạt.", "expected": ["Cần một đến hai hạt.", "Cần một hai hạt."], "got": "Cần 1 đến 2 hạt.", "got_phonemes": "kˈə2n mˈo6t̪ ɗˌeɜn hˈaːj hˈaː6t̪.", "expected_phonemes": ["kˈə2n mˈo6t̪ ɗˌeɜn hˈaːj hˈaː6t̪.", "kˈə2n mˈo6t̪ hˈaːj hˈaː6t̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_02 / nghe_ngay / string

```json
{"text": "Cần 3~5 túi.", "expected": "Cần ba đến năm túi.", "got": "Cần 3 đến 5 túi.", "got_phonemes": "kˈə2n bˈaː ɗˌeɜn nˈam t̪ˈuɜj.", "expected_phonemes": ["kˈə2n bˈaː ɗˌeɜn nˈam t̪ˈuɜj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_02 / studio / string

```json
{"text": "Cần 3~5 túi.", "expected": "Cần ba đến năm túi.", "got": "Cần 3 đến 5 túi.", "got_phonemes": "kˈə2n bˈaː ɗˌeɜn nˈam t̪ˈuɜj.", "expected_phonemes": ["kˈə2n bˈaː ɗˌeɜn nˈam t̪ˈuɜj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_03 / nghe_ngay / string

```json
{"text": "Cần 6–8 khay.", "expected": "Cần sáu đến tám khay.", "got": "Cần 6, 8 khay.", "got_phonemes": "kˈə2n sˈaɜw, t̪ˈaːɜm xˈaj.", "expected_phonemes": ["kˈə2n sˈaɜw ɗˌeɜn t̪ˈaːɜm xˈaj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_03 / nghe_ngay / post_g2p

```json
{"text": "Cần 6–8 khay.", "expected": "Cần sáu đến tám khay.", "got": "Cần 6, 8 khay.", "got_phonemes": "kˈə2n sˈaɜw, t̪ˈaːɜm xˈaj.", "expected_phonemes": ["kˈə2n sˈaɜw ɗˌeɜn t̪ˈaːɜm xˈaj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_03 / studio / string

```json
{"text": "Cần 6–8 khay.", "expected": "Cần sáu đến tám khay.", "got": "Cần 6, 8 khay.", "got_phonemes": "kˈə2n sˈaɜw, t̪ˈaːɜm xˈaj.", "expected_phonemes": ["kˈə2n sˈaɜw ɗˌeɜn t̪ˈaːɜm xˈaj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_03 / studio / post_g2p

```json
{"text": "Cần 6–8 khay.", "expected": "Cần sáu đến tám khay.", "got": "Cần 6, 8 khay.", "got_phonemes": "kˈə2n sˈaɜw, t̪ˈaːɜm xˈaj.", "expected_phonemes": ["kˈə2n sˈaɜw ɗˌeɜn t̪ˈaːɜm xˈaj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_04 / nghe_ngay / string

```json
{"text": "Cần 10—12 cốc.", "expected": "Cần mười đến mười hai cốc.", "got": "Cần 10, 12 cốc.", "got_phonemes": "kˈə2n mˈyə2j, mˈyə2j hˈaːj kˈoɜk.", "expected_phonemes": ["kˈə2n mˈyə2j ɗˌeɜn mˈyə2j hˈaːj kˈoɜk."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_04 / nghe_ngay / post_g2p

```json
{"text": "Cần 10—12 cốc.", "expected": "Cần mười đến mười hai cốc.", "got": "Cần 10, 12 cốc.", "got_phonemes": "kˈə2n mˈyə2j, mˈyə2j hˈaːj kˈoɜk.", "expected_phonemes": ["kˈə2n mˈyə2j ɗˌeɜn mˈyə2j hˈaːj kˈoɜk."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_04 / studio / string

```json
{"text": "Cần 10—12 cốc.", "expected": "Cần mười đến mười hai cốc.", "got": "Cần 10, 12 cốc.", "got_phonemes": "kˈə2n mˈyə2j, mˈyə2j hˈaːj kˈoɜk.", "expected_phonemes": ["kˈə2n mˈyə2j ɗˌeɜn mˈyə2j hˈaːj kˈoɜk."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_04 / studio / post_g2p

```json
{"text": "Cần 10—12 cốc.", "expected": "Cần mười đến mười hai cốc.", "got": "Cần 10, 12 cốc.", "got_phonemes": "kˈə2n mˈyə2j, mˈyə2j hˈaːj kˈoɜk.", "expected_phonemes": ["kˈə2n mˈyə2j ɗˌeɜn mˈyə2j hˈaːj kˈoɜk."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_05 / nghe_ngay / string

```json
{"text": "Cần 20 - 30 que.", "expected": "Cần hai mươi đến ba mươi que.", "got": "Cần 20 đến 30 que.", "got_phonemes": "kˈə2n hˈaːj mˈyəj ɗˌeɜn bˈaː mˈyəj kwˈɛ.", "expected_phonemes": ["kˈə2n hˈaːj mˈyəj ɗˌeɜn bˈaː mˈyəj kwˈɛ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_05 / studio / string

```json
{"text": "Cần 20 - 30 que.", "expected": "Cần hai mươi đến ba mươi que.", "got": "Cần 20 đến 30 que.", "got_phonemes": "kˈə2n hˈaːj mˈyəj ɗˌeɜn bˈaː mˈyəj kwˈɛ.", "expected_phonemes": ["kˈə2n hˈaːj mˈyəj ɗˌeɜn bˈaː mˈyəj kwˈɛ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_06 / nghe_ngay / string

```json
{"text": "Cần 40 ~ 50 lá.", "expected": "Cần bốn mươi đến năm mươi lá.", "got": "Cần 40 đến 50 lá.", "got_phonemes": "kˈə2n bˈoɜn mˈyəj ɗˌeɜn nˈam mˈyəj lˈaːɜ.", "expected_phonemes": ["kˈə2n bˈoɜn mˈyəj ɗˌeɜn nˈam mˈyəj lˈaːɜ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_06 / studio / string

```json
{"text": "Cần 40 ~ 50 lá.", "expected": "Cần bốn mươi đến năm mươi lá.", "got": "Cần 40 đến 50 lá.", "got_phonemes": "kˈə2n bˈoɜn mˈyəj ɗˌeɜn nˈam mˈyəj lˈaːɜ.", "expected_phonemes": ["kˈə2n bˈoɜn mˈyəj ɗˌeɜn nˈam mˈyəj lˈaːɜ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_07 / nghe_ngay / string

```json
{"text": "Cần 100-200 viên.", "expected": "Cần một trăm đến hai trăm viên.", "got": "Cần 100 đến 200 viên.", "got_phonemes": "kˈə2n mˈo6t̪ tʃˈam ɗˌeɜn hˈaːj tʃˈam vˈiɛn.", "expected_phonemes": ["kˈə2n mˈo6t̪ tʃˈam ɗˌeɜn hˈaːj tʃˈam vˈiɛn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_07 / studio / string

```json
{"text": "Cần 100-200 viên.", "expected": "Cần một trăm đến hai trăm viên.", "got": "Cần 100 đến 200 viên.", "got_phonemes": "kˈə2n mˈo6t̪ tʃˈam ɗˌeɜn hˈaːj tʃˈam vˈiɛn.", "expected_phonemes": ["kˈə2n mˈo6t̪ tʃˈam ɗˌeɜn hˈaːj tʃˈam vˈiɛn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_08 / nghe_ngay / string

```json
{"text": "Cần 2-4 kg.", "expected": "Cần hai đến bốn ki lô gam.", "got": "Cần 2 đến 4 kg.", "got_phonemes": "kˈə2n hˈaːj ɗˌeɜn bˈoɜn kˈi lˈo ɣˈaːm.", "expected_phonemes": ["kˈə2n hˈaːj ɗˌeɜn bˈoɜn kˈi lˈo ɣˈaːm."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_08 / studio / string

```json
{"text": "Cần 2-4 kg.", "expected": "Cần hai đến bốn ki lô gam.", "got": "Cần 2 đến 4 kg.", "got_phonemes": "kˈə2n hˈaːj ɗˌeɜn bˈoɜn kˈi lˈo ɣˈaːm.", "expected_phonemes": ["kˈə2n hˈaːj ɗˌeɜn bˈoɜn kˈi lˈo ɣˈaːm."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_09 / nghe_ngay / string

```json
{"text": "Cần 5~7 km.", "expected": "Cần năm đến bảy ki lô mét.", "got": "Cần 5 đến 7 km.", "got_phonemes": "kˈə2n nˈam ɗˌeɜn bˈa4j kˈi lˈo mˈɛɜt̪.", "expected_phonemes": ["kˈə2n nˈam ɗˌeɜn bˈa4j kˈi lˈo mˈɛɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_09 / studio / string

```json
{"text": "Cần 5~7 km.", "expected": "Cần năm đến bảy ki lô mét.", "got": "Cần 5 đến 7 km.", "got_phonemes": "kˈə2n nˈam ɗˌeɜn bˈa4j kˈi lˈo mˈɛɜt̪.", "expected_phonemes": ["kˈə2n nˈam ɗˌeɜn bˈa4j kˈi lˈo mˈɛɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_10 / nghe_ngay / string

```json
{"text": "Cần 8–10 cm.", "expected": "Cần tám đến mười xen ti mét.", "got": "Cần 8, 10 cm.", "got_phonemes": "kˈə2n t̪ˈaːɜm, mˈyə2j sˈɛn t̪ˈi mˈɛɜt̪.", "expected_phonemes": ["kˈə2n t̪ˈaːɜm ɗˌeɜn mˈyə2j sˈɛn t̪ˈi mˈɛɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_10 / nghe_ngay / post_g2p

```json
{"text": "Cần 8–10 cm.", "expected": "Cần tám đến mười xen ti mét.", "got": "Cần 8, 10 cm.", "got_phonemes": "kˈə2n t̪ˈaːɜm, mˈyə2j sˈɛn t̪ˈi mˈɛɜt̪.", "expected_phonemes": ["kˈə2n t̪ˈaːɜm ɗˌeɜn mˈyə2j sˈɛn t̪ˈi mˈɛɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_10 / studio / string

```json
{"text": "Cần 8–10 cm.", "expected": "Cần tám đến mười xen ti mét.", "got": "Cần 8, 10 cm.", "got_phonemes": "kˈə2n t̪ˈaːɜm, mˈyə2j sˈɛn t̪ˈi mˈɛɜt̪.", "expected_phonemes": ["kˈə2n t̪ˈaːɜm ɗˌeɜn mˈyə2j sˈɛn t̪ˈi mˈɛɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_10 / studio / post_g2p

```json
{"text": "Cần 8–10 cm.", "expected": "Cần tám đến mười xen ti mét.", "got": "Cần 8, 10 cm.", "got_phonemes": "kˈə2n t̪ˈaːɜm, mˈyə2j sˈɛn t̪ˈi mˈɛɜt̪.", "expected_phonemes": ["kˈə2n t̪ˈaːɜm ɗˌeɜn mˈyə2j sˈɛn t̪ˈi mˈɛɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_11 / nghe_ngay / string

```json
{"text": "Tuổi 18-20.", "expected": "Tuổi mười tám đến hai mươi.", "got": "Tuổi 18 đến 20.", "got_phonemes": "t̪ˈuə4j mˈyə2j t̪ˈaːɜm ɗˌeɜn hˈaːj mˈyəj.", "expected_phonemes": ["t̪ˈuə4j mˈyə2j t̪ˈaːɜm ɗˌeɜn hˈaːj mˈyəj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_11 / studio / string

```json
{"text": "Tuổi 18-20.", "expected": "Tuổi mười tám đến hai mươi.", "got": "Tuổi 18 đến 20.", "got_phonemes": "t̪ˈuə4j mˈyə2j t̪ˈaːɜm ɗˌeɜn hˈaːj mˈyəj.", "expected_phonemes": ["t̪ˈuə4j mˈyə2j t̪ˈaːɜm ɗˌeɜn hˈaːj mˈyəj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_12 / nghe_ngay / string

```json
{"text": "Trang 21-25.", "expected": "Trang hai mươi mốt đến hai mươi lăm.", "got": "Trang 21 đến 25.", "got_phonemes": "tʃˈaːŋ hˈaːj mˈyəj mˈoɜt̪ ɗˌeɜn hˈaːj mˈyəj lˈam.", "expected_phonemes": ["tʃˈaːŋ hˈaːj mˈyəj mˈoɜt̪ ɗˌeɜn hˈaːj mˈyəj lˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_12 / studio / string

```json
{"text": "Trang 21-25.", "expected": "Trang hai mươi mốt đến hai mươi lăm.", "got": "Trang 21 đến 25.", "got_phonemes": "tʃˈaːŋ hˈaːj mˈyəj mˈoɜt̪ ɗˌeɜn hˈaːj mˈyəj lˈam.", "expected_phonemes": ["tʃˈaːŋ hˈaːj mˈyəj mˈoɜt̪ ɗˌeɜn hˈaːj mˈyəj lˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_13 / nghe_ngay / string

```json
{"text": "Chương 2-3.", "expected": "Chương hai đến ba.", "got": "Chương 2 đến 3.", "got_phonemes": "tʃˈyəŋ hˈaːj ɗˌeɜn bˈaː.", "expected_phonemes": ["tʃˈyəŋ hˈaːj ɗˌeɜn bˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_13 / studio / string

```json
{"text": "Chương 2-3.", "expected": "Chương hai đến ba.", "got": "Chương 2 đến 3.", "got_phonemes": "tʃˈyəŋ hˈaːj ɗˌeɜn bˈaː.", "expected_phonemes": ["tʃˈyəŋ hˈaːj ɗˌeɜn bˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_14 / nghe_ngay / string

```json
{"text": "Mức 0,5-1,5.", "expected": "Mức không phẩy năm đến một phẩy năm.", "got": "Mức 0,5-1,5.", "got_phonemes": "mˈyɜc xˌoŋ fˈəɪ4 nˈam ɗˌeɜn mˈo6t̪ fˈəɪ4 nˈam.", "expected_phonemes": ["mˈyɜc xˌoŋ fˈəɪ4 nˈam ɗˌeɜn mˈo6t̪ fˈəɪ4 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_14 / studio / string

```json
{"text": "Mức 0,5-1,5.", "expected": "Mức không phẩy năm đến một phẩy năm.", "got": "Mức 0,5-1,5.", "got_phonemes": "mˈyɜc xˌoŋ fˈəɪ4 nˈam ɗˌeɜn mˈo6t̪ fˈəɪ4 nˈam.", "expected_phonemes": ["mˈyɜc xˌoŋ fˈəɪ4 nˈam ɗˌeɜn mˈo6t̪ fˈəɪ4 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_15 / nghe_ngay / string

```json
{"text": "Mức 1.5~2.5.", "expected": "Mức một phẩy năm đến hai phẩy năm.", "got": "Mức 1.5 đến 2.5.", "got_phonemes": "mˈyɜc mˈo6t̪ tʃˈəɜm nˈam ɗˌeɜn hˈaːj tʃˈəɜm nˈam.", "expected_phonemes": ["mˈyɜc mˈo6t̪ fˈəɪ4 nˈam ɗˌeɜn hˈaːj fˈəɪ4 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_15 / nghe_ngay / post_g2p

```json
{"text": "Mức 1.5~2.5.", "expected": "Mức một phẩy năm đến hai phẩy năm.", "got": "Mức 1.5 đến 2.5.", "got_phonemes": "mˈyɜc mˈo6t̪ tʃˈəɜm nˈam ɗˌeɜn hˈaːj tʃˈəɜm nˈam.", "expected_phonemes": ["mˈyɜc mˈo6t̪ fˈəɪ4 nˈam ɗˌeɜn hˈaːj fˈəɪ4 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_15 / studio / string

```json
{"text": "Mức 1.5~2.5.", "expected": "Mức một phẩy năm đến hai phẩy năm.", "got": "Mức 1.5 đến 2.5.", "got_phonemes": "mˈyɜc mˈo6t̪ tʃˈəɜm nˈam ɗˌeɜn hˈaːj tʃˈəɜm nˈam.", "expected_phonemes": ["mˈyɜc mˈo6t̪ fˈəɪ4 nˈam ɗˌeɜn hˈaːj fˈəɪ4 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_15 / studio / post_g2p

```json
{"text": "Mức 1.5~2.5.", "expected": "Mức một phẩy năm đến hai phẩy năm.", "got": "Mức 1.5 đến 2.5.", "got_phonemes": "mˈyɜc mˈo6t̪ tʃˈəɜm nˈam ɗˌeɜn hˈaːj tʃˈəɜm nˈam.", "expected_phonemes": ["mˈyɜc mˈo6t̪ fˈəɪ4 nˈam ɗˌeɜn hˈaːj fˈəɪ4 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_17 / nghe_ngay / string

```json
{"text": "Nhiệt độ -5–0 °C.", "expected": "Nhiệt độ âm năm đến không độ xê.", "got": "Nhiệt độ âm 5, 0 °C.", "got_phonemes": "ɲˈiɛ6t̪ ɗˈo6 ˈəm nˈam, xˌoŋ ɗˈo6 sˈe.", "expected_phonemes": ["ɲˈiɛ6t̪ ɗˈo6 ˈəm nˈam ɗˌeɜn xˌoŋ ɗˈo6 sˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_17 / nghe_ngay / post_g2p

```json
{"text": "Nhiệt độ -5–0 °C.", "expected": "Nhiệt độ âm năm đến không độ xê.", "got": "Nhiệt độ âm 5, 0 °C.", "got_phonemes": "ɲˈiɛ6t̪ ɗˈo6 ˈəm nˈam, xˌoŋ ɗˈo6 sˈe.", "expected_phonemes": ["ɲˈiɛ6t̪ ɗˈo6 ˈəm nˈam ɗˌeɜn xˌoŋ ɗˈo6 sˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_17 / studio / string

```json
{"text": "Nhiệt độ -5–0 °C.", "expected": "Nhiệt độ âm năm đến không độ xê.", "got": "Nhiệt độ âm 5, 0 °C.", "got_phonemes": "ɲˈiɛ6t̪ ɗˈo6 ˈəm nˈam, xˌoŋ ɗˈo6 sˈe.", "expected_phonemes": ["ɲˈiɛ6t̪ ɗˈo6 ˈəm nˈam ɗˌeɜn xˌoŋ ɗˈo6 sˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_17 / studio / post_g2p

```json
{"text": "Nhiệt độ -5–0 °C.", "expected": "Nhiệt độ âm năm đến không độ xê.", "got": "Nhiệt độ âm 5, 0 °C.", "got_phonemes": "ɲˈiɛ6t̪ ɗˈo6 ˈəm nˈam, xˌoŋ ɗˈo6 sˈe.", "expected_phonemes": ["ɲˈiɛ6t̪ ɗˈo6 ˈəm nˈam ɗˌeɜn xˌoŋ ɗˈo6 sˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_18 / nghe_ngay / string

```json
{"text": "Giờ mở 8-10 giờ.", "expected": "Giờ mở tám đến mười giờ.", "got": "Giờ mở 8 đến 10 giờ.", "got_phonemes": "zˈəː2 mˈəː4 t̪ˈaːɜm ɗˌeɜn mˈyə2j zˈəː2.", "expected_phonemes": ["zˈəː2 mˈəː4 t̪ˈaːɜm ɗˌeɜn mˈyə2j zˈəː2."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_18 / studio / string

```json
{"text": "Giờ mở 8-10 giờ.", "expected": "Giờ mở tám đến mười giờ.", "got": "Giờ mở 8 đến 10 giờ.", "got_phonemes": "zˈəː2 mˈəː4 t̪ˈaːɜm ɗˌeɜn mˈyə2j zˈəː2.", "expected_phonemes": ["zˈəː2 mˈəː4 t̪ˈaːɜm ɗˌeɜn mˈyə2j zˈəː2."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_19 / nghe_ngay / string

```json
{"text": "Giá 10-20 đồng.", "expected": "Giá mười đến hai mươi đồng.", "got": "Giá 10 đến 20 đồng.", "got_phonemes": "zˈaːɜ mˈyə2j ɗˌeɜn hˈaːj mˈyəj ɗˈo2ŋ.", "expected_phonemes": ["zˈaːɜ mˈyə2j ɗˌeɜn hˈaːj mˈyəj ɗˈo2ŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_19 / studio / string

```json
{"text": "Giá 10-20 đồng.", "expected": "Giá mười đến hai mươi đồng.", "got": "Giá 10 đến 20 đồng.", "got_phonemes": "zˈaːɜ mˈyə2j ɗˌeɜn hˈaːj mˈyəj ɗˈo2ŋ.", "expected_phonemes": ["zˈaːɜ mˈyə2j ɗˌeɜn hˈaːj mˈyəj ɗˈo2ŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_20 / nghe_ngay / string

```json
{"text": "Tỉ lệ 30~40%.", "expected": "Tỉ lệ ba mươi đến bốn mươi phần trăm.", "got": "Tỉ lệ 30 đến 40%.", "got_phonemes": "t̪ˈi4 lˈe6 bˈaː mˈyəj ɗˌeɜn bˈoɜn mˈyəj fˈə2n tʃˈam.", "expected_phonemes": ["t̪ˈi4 lˈe6 bˈaː mˈyəj ɗˌeɜn bˈoɜn mˈyəj fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_20 / studio / string

```json
{"text": "Tỉ lệ 30~40%.", "expected": "Tỉ lệ ba mươi đến bốn mươi phần trăm.", "got": "Tỉ lệ 30 đến 40%.", "got_phonemes": "t̪ˈi4 lˈe6 bˈaː mˈyəj ɗˌeɜn bˈoɜn mˈyəj fˈə2n tʃˈam.", "expected_phonemes": ["t̪ˈi4 lˈe6 bˈaː mˈyəj ɗˌeɜn bˈoɜn mˈyəj fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_01 / nghe_ngay / string

```json
{"text": "Mức đạt 0%.", "expected": "Mức đạt không phần trăm.", "got": "Mức đạt 0%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ xˌoŋ fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ xˌoŋ fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_01 / studio / string

```json
{"text": "Mức đạt 0%.", "expected": "Mức đạt không phần trăm.", "got": "Mức đạt 0%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ xˌoŋ fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ xˌoŋ fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_02 / nghe_ngay / string

```json
{"text": "Mức đạt 1%.", "expected": "Mức đạt một phần trăm.", "got": "Mức đạt 1%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ mˈo6t̪ fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ mˈo6t̪ fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_02 / studio / string

```json
{"text": "Mức đạt 1%.", "expected": "Mức đạt một phần trăm.", "got": "Mức đạt 1%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ mˈo6t̪ fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ mˈo6t̪ fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_03 / nghe_ngay / string

```json
{"text": "Mức đạt 2%.", "expected": "Mức đạt hai phần trăm.", "got": "Mức đạt 2%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ hˈaːj fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ hˈaːj fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_03 / studio / string

```json
{"text": "Mức đạt 2%.", "expected": "Mức đạt hai phần trăm.", "got": "Mức đạt 2%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ hˈaːj fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ hˈaːj fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_04 / nghe_ngay / string

```json
{"text": "Mức đạt 5%.", "expected": "Mức đạt năm phần trăm.", "got": "Mức đạt 5%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ nˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ nˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_04 / studio / string

```json
{"text": "Mức đạt 5%.", "expected": "Mức đạt năm phần trăm.", "got": "Mức đạt 5%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ nˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ nˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_05 / nghe_ngay / string

```json
{"text": "Mức đạt 10%.", "expected": "Mức đạt mười phần trăm.", "got": "Mức đạt 10%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ mˈyə2j fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ mˈyə2j fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_05 / studio / string

```json
{"text": "Mức đạt 10%.", "expected": "Mức đạt mười phần trăm.", "got": "Mức đạt 10%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ mˈyə2j fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ mˈyə2j fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_06 / nghe_ngay / string

```json
{"text": "Mức đạt 15%.", "expected": "Mức đạt mười lăm phần trăm.", "got": "Mức đạt 15%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ mˈyə2j lˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ mˈyə2j lˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_06 / studio / string

```json
{"text": "Mức đạt 15%.", "expected": "Mức đạt mười lăm phần trăm.", "got": "Mức đạt 15%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ mˈyə2j lˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ mˈyə2j lˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_07 / nghe_ngay / string

```json
{"text": "Mức đạt 20%.", "expected": "Mức đạt hai mươi phần trăm.", "got": "Mức đạt 20%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ hˈaːj mˈyəj fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ hˈaːj mˈyəj fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_07 / studio / string

```json
{"text": "Mức đạt 20%.", "expected": "Mức đạt hai mươi phần trăm.", "got": "Mức đạt 20%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ hˈaːj mˈyəj fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ hˈaːj mˈyəj fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_08 / nghe_ngay / string

```json
{"text": "Mức đạt 25%.", "expected": "Mức đạt hai mươi lăm phần trăm.", "got": "Mức đạt 25%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ hˈaːj mˈyəj lˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ hˈaːj mˈyəj lˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_08 / studio / string

```json
{"text": "Mức đạt 25%.", "expected": "Mức đạt hai mươi lăm phần trăm.", "got": "Mức đạt 25%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ hˈaːj mˈyəj lˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ hˈaːj mˈyəj lˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_09 / nghe_ngay / string

```json
{"text": "Mức đạt 30%.", "expected": "Mức đạt ba mươi phần trăm.", "got": "Mức đạt 30%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ bˈaː mˈyəj fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ bˈaː mˈyəj fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_09 / studio / string

```json
{"text": "Mức đạt 30%.", "expected": "Mức đạt ba mươi phần trăm.", "got": "Mức đạt 30%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ bˈaː mˈyəj fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ bˈaː mˈyəj fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_10 / nghe_ngay / string

```json
{"text": "Mức đạt 50%.", "expected": "Mức đạt năm mươi phần trăm.", "got": "Mức đạt 50%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ nˈam mˈyəj fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ nˈam mˈyəj fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_10 / studio / string

```json
{"text": "Mức đạt 50%.", "expected": "Mức đạt năm mươi phần trăm.", "got": "Mức đạt 50%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ nˈam mˈyəj fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ nˈam mˈyəj fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_11 / nghe_ngay / string

```json
{"text": "Mức đạt 75%.", "expected": "Mức đạt bảy mươi lăm phần trăm.", "got": "Mức đạt 75%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ bˈa4j mˈyəj lˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ bˈa4j mˈyəj lˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_11 / studio / string

```json
{"text": "Mức đạt 75%.", "expected": "Mức đạt bảy mươi lăm phần trăm.", "got": "Mức đạt 75%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ bˈa4j mˈyəj lˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ bˈa4j mˈyəj lˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_12 / nghe_ngay / string

```json
{"text": "Mức đạt 99%.", "expected": "Mức đạt chín mươi chín phần trăm.", "got": "Mức đạt 99%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ tʃˈiɜn mˈyəj tʃˈiɜn fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ tʃˈiɜn mˈyəj tʃˈiɜn fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_12 / studio / string

```json
{"text": "Mức đạt 99%.", "expected": "Mức đạt chín mươi chín phần trăm.", "got": "Mức đạt 99%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ tʃˈiɜn mˈyəj tʃˈiɜn fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ tʃˈiɜn mˈyəj tʃˈiɜn fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_13 / nghe_ngay / string

```json
{"text": "Mức đạt 100%.", "expected": "Mức đạt một trăm phần trăm.", "got": "Mức đạt 100%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ mˈo6t̪ tʃˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ mˈo6t̪ tʃˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_13 / studio / string

```json
{"text": "Mức đạt 100%.", "expected": "Mức đạt một trăm phần trăm.", "got": "Mức đạt 100%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ mˈo6t̪ tʃˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ mˈo6t̪ tʃˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_14 / nghe_ngay / string

```json
{"text": "Mức đạt 150%.", "expected": "Mức đạt một trăm năm mươi phần trăm.", "got": "Mức đạt 150%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ mˈo6t̪ tʃˈam nˈam mˈyəj fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ mˈo6t̪ tʃˈam nˈam mˈyəj fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_14 / studio / string

```json
{"text": "Mức đạt 150%.", "expected": "Mức đạt một trăm năm mươi phần trăm.", "got": "Mức đạt 150%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ mˈo6t̪ tʃˈam nˈam mˈyəj fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ mˈo6t̪ tʃˈam nˈam mˈyəj fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_15 / nghe_ngay / string

```json
{"text": "Mức đạt 0,5%.", "expected": "Mức đạt không phẩy năm phần trăm.", "got": "Mức đạt 0,5%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ xˌoŋ fˈəɪ4 nˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ xˌoŋ fˈəɪ4 nˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_15 / studio / string

```json
{"text": "Mức đạt 0,5%.", "expected": "Mức đạt không phẩy năm phần trăm.", "got": "Mức đạt 0,5%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ xˌoŋ fˈəɪ4 nˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ xˌoŋ fˈəɪ4 nˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_16 / nghe_ngay / string

```json
{"text": "Mức đạt 1.5%.", "expected": "Mức đạt một phẩy năm phần trăm.", "got": "Mức đạt 1.5%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ mˈo6t̪ tʃˈəɜm nˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ mˈo6t̪ fˈəɪ4 nˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_16 / nghe_ngay / post_g2p

```json
{"text": "Mức đạt 1.5%.", "expected": "Mức đạt một phẩy năm phần trăm.", "got": "Mức đạt 1.5%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ mˈo6t̪ tʃˈəɜm nˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ mˈo6t̪ fˈəɪ4 nˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_16 / studio / string

```json
{"text": "Mức đạt 1.5%.", "expected": "Mức đạt một phẩy năm phần trăm.", "got": "Mức đạt 1.5%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ mˈo6t̪ tʃˈəɜm nˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ mˈo6t̪ fˈəɪ4 nˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_16 / studio / post_g2p

```json
{"text": "Mức đạt 1.5%.", "expected": "Mức đạt một phẩy năm phần trăm.", "got": "Mức đạt 1.5%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ mˈo6t̪ tʃˈəɜm nˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ mˈo6t̪ fˈəɪ4 nˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_17 / nghe_ngay / string

```json
{"text": "Mức đạt 12,5%.", "expected": "Mức đạt mười hai phẩy năm phần trăm.", "got": "Mức đạt 12,5%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ mˈyə2j hˈaːj fˈəɪ4 nˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ mˈyə2j hˈaːj fˈəɪ4 nˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_17 / studio / string

```json
{"text": "Mức đạt 12,5%.", "expected": "Mức đạt mười hai phẩy năm phần trăm.", "got": "Mức đạt 12,5%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ mˈyə2j hˈaːj fˈəɪ4 nˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ mˈyə2j hˈaːj fˈəɪ4 nˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_18 / nghe_ngay / string

```json
{"text": "Mức đạt 2.25%.", "expected": "Mức đạt hai phẩy hai năm phần trăm.", "got": "Mức đạt 2.25%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ hˈaːj tʃˈəɜm hˈaːj lˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ hˈaːj fˈəɪ4 hˈaːj nˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_18 / nghe_ngay / post_g2p

```json
{"text": "Mức đạt 2.25%.", "expected": "Mức đạt hai phẩy hai năm phần trăm.", "got": "Mức đạt 2.25%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ hˈaːj tʃˈəɜm hˈaːj lˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ hˈaːj fˈəɪ4 hˈaːj nˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_18 / studio / string

```json
{"text": "Mức đạt 2.25%.", "expected": "Mức đạt hai phẩy hai năm phần trăm.", "got": "Mức đạt 2.25%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ hˈaːj tʃˈəɜm hˈaːj lˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ hˈaːj fˈəɪ4 hˈaːj nˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_18 / studio / post_g2p

```json
{"text": "Mức đạt 2.25%.", "expected": "Mức đạt hai phẩy hai năm phần trăm.", "got": "Mức đạt 2.25%.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ hˈaːj tʃˈəɜm hˈaːj lˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ hˈaːj fˈəɪ4 hˈaːj nˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_19 / nghe_ngay / string

```json
{"text": "Mức đạt 25 %.", "expected": "Mức đạt hai mươi lăm phần trăm.", "got": "Mức đạt hai mươi lăm %.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ hˈaːj mˈyəj lˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ hˈaːj mˈyəj lˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_19 / studio / string

```json
{"text": "Mức đạt 25 %.", "expected": "Mức đạt hai mươi lăm phần trăm.", "got": "Mức đạt hai mươi lăm %.", "got_phonemes": "mˈyɜc ɗˈaː6t̪ hˈaːj mˈyəj lˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc ɗˈaː6t̪ hˈaːj mˈyəj lˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_20 / nghe_ngay / string

```json
{"text": "Mức giảm -5%.", "expected": "Mức giảm âm năm phần trăm.", "got": "Mức giảm trừ 5%.", "got_phonemes": "mˈyɜc zˈaː4m tʃˈy2 nˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc zˈaː4m ˈəm nˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_20 / nghe_ngay / post_g2p

```json
{"text": "Mức giảm -5%.", "expected": "Mức giảm âm năm phần trăm.", "got": "Mức giảm trừ 5%.", "got_phonemes": "mˈyɜc zˈaː4m tʃˈy2 nˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc zˈaː4m ˈəm nˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_20 / studio / string

```json
{"text": "Mức giảm -5%.", "expected": "Mức giảm âm năm phần trăm.", "got": "Mức giảm trừ 5%.", "got_phonemes": "mˈyɜc zˈaː4m tʃˈy2 nˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc zˈaː4m ˈəm nˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_20 / studio / post_g2p

```json
{"text": "Mức giảm -5%.", "expected": "Mức giảm âm năm phần trăm.", "got": "Mức giảm trừ 5%.", "got_phonemes": "mˈyɜc zˈaː4m tʃˈy2 nˈam fˈə2n tʃˈam.", "expected_phonemes": ["mˈyɜc zˈaː4m ˈəm nˈam fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_04 / nghe_ngay / string

```json
{"text": "Giá 20.000đ.", "expected": "Giá hai mươi nghìn đồng.", "got": "Giá 20.000đ.", "got_phonemes": "zˈaːɜ hˈaːj mˈyəj ŋˈi2n ɗˈo2ŋ.", "expected_phonemes": ["zˈaːɜ hˈaːj mˈyəj ŋˈi2n ɗˈo2ŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_04 / studio / string

```json
{"text": "Giá 20.000đ.", "expected": "Giá hai mươi nghìn đồng.", "got": "Giá 20.000đ.", "got_phonemes": "zˈaːɜ hˈaːj mˈyəj ŋˈi2n ɗˈo2ŋ.", "expected_phonemes": ["zˈaːɜ hˈaːj mˈyəj ŋˈi2n ɗˈo2ŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_05 / nghe_ngay / string

```json
{"text": "Giá 50.000₫.", "expected": "Giá năm mươi nghìn đồng.", "got": "Giá năm mươi nghìn₫.", "got_phonemes": "zˈaːɜ nˈam mˈyəj ŋˈi2n.", "expected_phonemes": ["zˈaːɜ nˈam mˈyəj ŋˈi2n ɗˈo2ŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_05 / nghe_ngay / post_g2p

```json
{"text": "Giá 50.000₫.", "expected": "Giá năm mươi nghìn đồng.", "got": "Giá năm mươi nghìn₫.", "got_phonemes": "zˈaːɜ nˈam mˈyəj ŋˈi2n.", "expected_phonemes": ["zˈaːɜ nˈam mˈyəj ŋˈi2n ɗˈo2ŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_05 / studio / string

```json
{"text": "Giá 50.000₫.", "expected": "Giá năm mươi nghìn đồng.", "got": "Giá năm mươi nghìn₫.", "got_phonemes": "zˈaːɜ nˈam mˈyəj ŋˈi2n.", "expected_phonemes": ["zˈaːɜ nˈam mˈyəj ŋˈi2n ɗˈo2ŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_05 / studio / post_g2p

```json
{"text": "Giá 50.000₫.", "expected": "Giá năm mươi nghìn đồng.", "got": "Giá năm mươi nghìn₫.", "got_phonemes": "zˈaːɜ nˈam mˈyəj ŋˈi2n.", "expected_phonemes": ["zˈaːɜ nˈam mˈyəj ŋˈi2n ɗˈo2ŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_07 / nghe_ngay / string

```json
{"text": "Giá $5.", "expected": ["Giá năm đô la.", "Giá năm đô."], "got": "Giá 5 đô la.", "got_phonemes": "zˈaːɜ nˈam ɗˈo lˈaː.", "expected_phonemes": ["zˈaːɜ nˈam ɗˈo lˈaː.", "zˈaːɜ nˈam ɗˈo."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_07 / studio / string

```json
{"text": "Giá $5.", "expected": ["Giá năm đô la.", "Giá năm đô."], "got": "Giá 5 đô la.", "got_phonemes": "zˈaːɜ nˈam ɗˈo lˈaː.", "expected_phonemes": ["zˈaːɜ nˈam ɗˈo lˈaː.", "zˈaːɜ nˈam ɗˈo."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_08 / nghe_ngay / string

```json
{"text": "Giá 10$.", "expected": ["Giá mười đô la.", "Giá mười đô."], "got": "Giá 10 đô la.", "got_phonemes": "zˈaːɜ mˈyə2j ɗˈo lˈaː.", "expected_phonemes": ["zˈaːɜ mˈyə2j ɗˈo lˈaː.", "zˈaːɜ mˈyə2j ɗˈo."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_08 / studio / string

```json
{"text": "Giá 10$.", "expected": ["Giá mười đô la.", "Giá mười đô."], "got": "Giá 10 đô la.", "got_phonemes": "zˈaːɜ mˈyə2j ɗˈo lˈaː.", "expected_phonemes": ["zˈaːɜ mˈyə2j ɗˈo lˈaː.", "zˈaːɜ mˈyə2j ɗˈo."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_09 / nghe_ngay / string

```json
{"text": "Giá $1.50.", "expected": ["Giá một phẩy năm không đô la.", "Giá một đô la năm mươi xu."], "got": "Giá 1.50 đô la.", "got_phonemes": "zˈaːɜ mˈo6t̪ tʃˈəɜm nˈam xˌoŋ ɗˈo lˈaː.", "expected_phonemes": ["zˈaːɜ mˈo6t̪ fˈəɪ4 nˈam xˌoŋ ɗˈo lˈaː.", "zˈaːɜ mˈo6t̪ ɗˈo lˈaː nˈam mˈyəj sˈu."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_09 / nghe_ngay / post_g2p

```json
{"text": "Giá $1.50.", "expected": ["Giá một phẩy năm không đô la.", "Giá một đô la năm mươi xu."], "got": "Giá 1.50 đô la.", "got_phonemes": "zˈaːɜ mˈo6t̪ tʃˈəɜm nˈam xˌoŋ ɗˈo lˈaː.", "expected_phonemes": ["zˈaːɜ mˈo6t̪ fˈəɪ4 nˈam xˌoŋ ɗˈo lˈaː.", "zˈaːɜ mˈo6t̪ ɗˈo lˈaː nˈam mˈyəj sˈu."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_09 / studio / string

```json
{"text": "Giá $1.50.", "expected": ["Giá một phẩy năm không đô la.", "Giá một đô la năm mươi xu."], "got": "Giá 1.50 đô la.", "got_phonemes": "zˈaːɜ mˈo6t̪ tʃˈəɜm nˈam xˌoŋ ɗˈo lˈaː.", "expected_phonemes": ["zˈaːɜ mˈo6t̪ fˈəɪ4 nˈam xˌoŋ ɗˈo lˈaː.", "zˈaːɜ mˈo6t̪ ɗˈo lˈaː nˈam mˈyəj sˈu."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_09 / studio / post_g2p

```json
{"text": "Giá $1.50.", "expected": ["Giá một phẩy năm không đô la.", "Giá một đô la năm mươi xu."], "got": "Giá 1.50 đô la.", "got_phonemes": "zˈaːɜ mˈo6t̪ tʃˈəɜm nˈam xˌoŋ ɗˈo lˈaː.", "expected_phonemes": ["zˈaːɜ mˈo6t̪ fˈəɪ4 nˈam xˌoŋ ɗˈo lˈaː.", "zˈaːɜ mˈo6t̪ ɗˈo lˈaː nˈam mˈyəj sˈu."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_10 / nghe_ngay / string

```json
{"text": "Giá 20 USD.", "expected": ["Giá hai mươi đô la Mỹ.", "Giá hai mươi đô la.", "Giá hai mươi u ét đê."], "got": "Giá hai mươi <en>U S D</en>.", "got_phonemes": "zˈaːɜ hˈaːj mˈyəj jˈuː ˈɛs dˈiː.", "expected_phonemes": ["zˈaːɜ hˈaːj mˈyəj ɗˈo lˈaː mˈi5.", "zˈaːɜ hˈaːj mˈyəj ɗˈo lˈaː.", "zˈaːɜ hˈaːj mˈyəj ˈu ˈɛɜt̪ ɗˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_10 / nghe_ngay / post_g2p

```json
{"text": "Giá 20 USD.", "expected": ["Giá hai mươi đô la Mỹ.", "Giá hai mươi đô la.", "Giá hai mươi u ét đê."], "got": "Giá hai mươi <en>U S D</en>.", "got_phonemes": "zˈaːɜ hˈaːj mˈyəj jˈuː ˈɛs dˈiː.", "expected_phonemes": ["zˈaːɜ hˈaːj mˈyəj ɗˈo lˈaː mˈi5.", "zˈaːɜ hˈaːj mˈyəj ɗˈo lˈaː.", "zˈaːɜ hˈaːj mˈyəj ˈu ˈɛɜt̪ ɗˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_10 / studio / string

```json
{"text": "Giá 20 USD.", "expected": ["Giá hai mươi đô la Mỹ.", "Giá hai mươi đô la.", "Giá hai mươi u ét đê."], "got": "Giá hai mươi <en>U S D</en>.", "got_phonemes": "zˈaːɜ hˈaːj mˈyəj jˈuː ˈɛs dˈiː.", "expected_phonemes": ["zˈaːɜ hˈaːj mˈyəj ɗˈo lˈaː mˈi5.", "zˈaːɜ hˈaːj mˈyəj ɗˈo lˈaː.", "zˈaːɜ hˈaːj mˈyəj ˈu ˈɛɜt̪ ɗˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_10 / studio / post_g2p

```json
{"text": "Giá 20 USD.", "expected": ["Giá hai mươi đô la Mỹ.", "Giá hai mươi đô la.", "Giá hai mươi u ét đê."], "got": "Giá hai mươi <en>U S D</en>.", "got_phonemes": "zˈaːɜ hˈaːj mˈyəj jˈuː ˈɛs dˈiː.", "expected_phonemes": ["zˈaːɜ hˈaːj mˈyəj ɗˈo lˈaː mˈi5.", "zˈaːɜ hˈaːj mˈyəj ɗˈo lˈaː.", "zˈaːɜ hˈaːj mˈyəj ˈu ˈɛɜt̪ ɗˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_11 / nghe_ngay / string

```json
{"text": "Giá USD 30.", "expected": ["Giá ba mươi đô la Mỹ.", "Giá ba mươi đô la.", "Giá u ét đê ba mươi."], "got": "Giá <en>U S D</en> ba mươi.", "got_phonemes": "zˈaːɜ jˈuː ˈɛs dˈiː bˈaː mˈyəj.", "expected_phonemes": ["zˈaːɜ bˈaː mˈyəj ɗˈo lˈaː mˈi5.", "zˈaːɜ bˈaː mˈyəj ɗˈo lˈaː.", "zˈaːɜ ˈu ˈɛɜt̪ ɗˈe bˈaː mˈyəj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_11 / nghe_ngay / post_g2p

```json
{"text": "Giá USD 30.", "expected": ["Giá ba mươi đô la Mỹ.", "Giá ba mươi đô la.", "Giá u ét đê ba mươi."], "got": "Giá <en>U S D</en> ba mươi.", "got_phonemes": "zˈaːɜ jˈuː ˈɛs dˈiː bˈaː mˈyəj.", "expected_phonemes": ["zˈaːɜ bˈaː mˈyəj ɗˈo lˈaː mˈi5.", "zˈaːɜ bˈaː mˈyəj ɗˈo lˈaː.", "zˈaːɜ ˈu ˈɛɜt̪ ɗˈe bˈaː mˈyəj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_11 / studio / string

```json
{"text": "Giá USD 30.", "expected": ["Giá ba mươi đô la Mỹ.", "Giá ba mươi đô la.", "Giá u ét đê ba mươi."], "got": "Giá <en>U S D</en> ba mươi.", "got_phonemes": "zˈaːɜ jˈuː ˈɛs dˈiː bˈaː mˈyəj.", "expected_phonemes": ["zˈaːɜ bˈaː mˈyəj ɗˈo lˈaː mˈi5.", "zˈaːɜ bˈaː mˈyəj ɗˈo lˈaː.", "zˈaːɜ ˈu ˈɛɜt̪ ɗˈe bˈaː mˈyəj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_11 / studio / post_g2p

```json
{"text": "Giá USD 30.", "expected": ["Giá ba mươi đô la Mỹ.", "Giá ba mươi đô la.", "Giá u ét đê ba mươi."], "got": "Giá <en>U S D</en> ba mươi.", "got_phonemes": "zˈaːɜ jˈuː ˈɛs dˈiː bˈaː mˈyəj.", "expected_phonemes": ["zˈaːɜ bˈaː mˈyəj ɗˈo lˈaː mˈi5.", "zˈaːɜ bˈaː mˈyəj ɗˈo lˈaː.", "zˈaːɜ ˈu ˈɛɜt̪ ɗˈe bˈaː mˈyəj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_12 / nghe_ngay / string

```json
{"text": "Giá 100 USD.", "expected": ["Giá một trăm đô la Mỹ.", "Giá một trăm đô la."], "got": "Giá một trăm <en>U S D</en>.", "got_phonemes": "zˈaːɜ mˈo6t̪ tʃˈam jˈuː ˈɛs dˈiː.", "expected_phonemes": ["zˈaːɜ mˈo6t̪ tʃˈam ɗˈo lˈaː mˈi5.", "zˈaːɜ mˈo6t̪ tʃˈam ɗˈo lˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_12 / nghe_ngay / post_g2p

```json
{"text": "Giá 100 USD.", "expected": ["Giá một trăm đô la Mỹ.", "Giá một trăm đô la."], "got": "Giá một trăm <en>U S D</en>.", "got_phonemes": "zˈaːɜ mˈo6t̪ tʃˈam jˈuː ˈɛs dˈiː.", "expected_phonemes": ["zˈaːɜ mˈo6t̪ tʃˈam ɗˈo lˈaː mˈi5.", "zˈaːɜ mˈo6t̪ tʃˈam ɗˈo lˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_12 / studio / string

```json
{"text": "Giá 100 USD.", "expected": ["Giá một trăm đô la Mỹ.", "Giá một trăm đô la."], "got": "Giá một trăm <en>U S D</en>.", "got_phonemes": "zˈaːɜ mˈo6t̪ tʃˈam jˈuː ˈɛs dˈiː.", "expected_phonemes": ["zˈaːɜ mˈo6t̪ tʃˈam ɗˈo lˈaː mˈi5.", "zˈaːɜ mˈo6t̪ tʃˈam ɗˈo lˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_12 / studio / post_g2p

```json
{"text": "Giá 100 USD.", "expected": ["Giá một trăm đô la Mỹ.", "Giá một trăm đô la."], "got": "Giá một trăm <en>U S D</en>.", "got_phonemes": "zˈaːɜ mˈo6t̪ tʃˈam jˈuː ˈɛs dˈiː.", "expected_phonemes": ["zˈaːɜ mˈo6t̪ tʃˈam ɗˈo lˈaː mˈi5.", "zˈaːɜ mˈo6t̪ tʃˈam ɗˈo lˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_13 / nghe_ngay / string

```json
{"text": "Giá ¥500.", "expected": ["Giá năm trăm yên.", "Giá yên năm trăm."], "got": "Giá ¥500.", "got_phonemes": "zˈaːɜ nˈam tʃˈam ˈiɛn.", "expected_phonemes": ["zˈaːɜ nˈam tʃˈam ˈiɛn.", "zˈaːɜ ˈiɛn nˈam tʃˈam."], "note": "Quy ước ¥ là yên Nhật trong benchmark."}
```

### currency_13 / studio / string

```json
{"text": "Giá ¥500.", "expected": ["Giá năm trăm yên.", "Giá yên năm trăm."], "got": "Giá ¥500.", "got_phonemes": "zˈaːɜ nˈam tʃˈam ˈiɛn.", "expected_phonemes": ["zˈaːɜ nˈam tʃˈam ˈiɛn.", "zˈaːɜ ˈiɛn nˈam tʃˈam."], "note": "Quy ước ¥ là yên Nhật trong benchmark."}
```

### currency_14 / nghe_ngay / string

```json
{"text": "Giá 1000¥.", "expected": "Giá một nghìn yên.", "got": "Giá 1000¥.", "got_phonemes": "zˈaːɜ mˈo6t̪ ŋˈi2n ˈiɛn.", "expected_phonemes": ["zˈaːɜ mˈo6t̪ ŋˈi2n ˈiɛn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_14 / studio / string

```json
{"text": "Giá 1000¥.", "expected": "Giá một nghìn yên.", "got": "Giá 1000¥.", "got_phonemes": "zˈaːɜ mˈo6t̪ ŋˈi2n ˈiɛn.", "expected_phonemes": ["zˈaːɜ mˈo6t̪ ŋˈi2n ˈiɛn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_17 / nghe_ngay / string

```json
{"text": "Giá 300 JPY.", "expected": ["Giá ba trăm yên Nhật.", "Giá ba trăm yên."], "got": "Giá ba trăm <en>J P Y</en>.", "got_phonemes": "zˈaːɜ bˈaː tʃˈam dʒˈeɪ pˈiː wˈaɪ.", "expected_phonemes": ["zˈaːɜ bˈaː tʃˈam ˈiɛn ɲˈə6t̪.", "zˈaːɜ bˈaː tʃˈam ˈiɛn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_17 / nghe_ngay / post_g2p

```json
{"text": "Giá 300 JPY.", "expected": ["Giá ba trăm yên Nhật.", "Giá ba trăm yên."], "got": "Giá ba trăm <en>J P Y</en>.", "got_phonemes": "zˈaːɜ bˈaː tʃˈam dʒˈeɪ pˈiː wˈaɪ.", "expected_phonemes": ["zˈaːɜ bˈaː tʃˈam ˈiɛn ɲˈə6t̪.", "zˈaːɜ bˈaː tʃˈam ˈiɛn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_17 / studio / string

```json
{"text": "Giá 300 JPY.", "expected": ["Giá ba trăm yên Nhật.", "Giá ba trăm yên."], "got": "Giá ba trăm <en>J P Y</en>.", "got_phonemes": "zˈaːɜ bˈaː tʃˈam dʒˈeɪ pˈiː wˈaɪ.", "expected_phonemes": ["zˈaːɜ bˈaː tʃˈam ˈiɛn ɲˈə6t̪.", "zˈaːɜ bˈaː tʃˈam ˈiɛn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_17 / studio / post_g2p

```json
{"text": "Giá 300 JPY.", "expected": ["Giá ba trăm yên Nhật.", "Giá ba trăm yên."], "got": "Giá ba trăm <en>J P Y</en>.", "got_phonemes": "zˈaːɜ bˈaː tʃˈam dʒˈeɪ pˈiː wˈaɪ.", "expected_phonemes": ["zˈaːɜ bˈaː tʃˈam ˈiɛn ɲˈə6t̪.", "zˈaːɜ bˈaː tʃˈam ˈiɛn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_18 / nghe_ngay / string

```json
{"text": "Giá €10.", "expected": ["Giá mười ơ rô.", "Giá mười euro."], "got": "Giá €10.", "got_phonemes": "zˈaːɜ mˈyə2j jˈʊɹɹoʊ.", "expected_phonemes": ["zˈaːɜ mˈyə2j ˈəː ɹˈo.", "zˈaːɜ mˈyə2j jˈʊɹɹoʊ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_18 / studio / string

```json
{"text": "Giá €10.", "expected": ["Giá mười ơ rô.", "Giá mười euro."], "got": "Giá €10.", "got_phonemes": "zˈaːɜ mˈyə2j jˈʊɹɹoʊ.", "expected_phonemes": ["zˈaːɜ mˈyə2j ˈəː ɹˈo.", "zˈaːɜ mˈyə2j jˈʊɹɹoʊ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_19 / nghe_ngay / string

```json
{"text": "Giá 20 EUR.", "expected": ["Giá hai mươi ơ rô.", "Giá hai mươi euro."], "got": "Giá hai mươi <en>E U R</en>.", "got_phonemes": "zˈaːɜ hˈaːj mˈyəj ˈiː jˈuː ˈɑːɹ.", "expected_phonemes": ["zˈaːɜ hˈaːj mˈyəj ˈəː ɹˈo.", "zˈaːɜ hˈaːj mˈyəj jˈʊɹɹoʊ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_19 / nghe_ngay / post_g2p

```json
{"text": "Giá 20 EUR.", "expected": ["Giá hai mươi ơ rô.", "Giá hai mươi euro."], "got": "Giá hai mươi <en>E U R</en>.", "got_phonemes": "zˈaːɜ hˈaːj mˈyəj ˈiː jˈuː ˈɑːɹ.", "expected_phonemes": ["zˈaːɜ hˈaːj mˈyəj ˈəː ɹˈo.", "zˈaːɜ hˈaːj mˈyəj jˈʊɹɹoʊ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_19 / studio / string

```json
{"text": "Giá 20 EUR.", "expected": ["Giá hai mươi ơ rô.", "Giá hai mươi euro."], "got": "Giá hai mươi <en>E U R</en>.", "got_phonemes": "zˈaːɜ hˈaːj mˈyəj ˈiː jˈuː ˈɑːɹ.", "expected_phonemes": ["zˈaːɜ hˈaːj mˈyəj ˈəː ɹˈo.", "zˈaːɜ hˈaːj mˈyəj jˈʊɹɹoʊ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_19 / studio / post_g2p

```json
{"text": "Giá 20 EUR.", "expected": ["Giá hai mươi ơ rô.", "Giá hai mươi euro."], "got": "Giá hai mươi <en>E U R</en>.", "got_phonemes": "zˈaːɜ hˈaːj mˈyəj ˈiː jˈuː ˈɑːɹ.", "expected_phonemes": ["zˈaːɜ hˈaːj mˈyəj ˈəː ɹˈo.", "zˈaːɜ hˈaːj mˈyəj jˈʊɹɹoʊ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_20 / nghe_ngay / string

```json
{"text": "Giá £5.", "expected": "Giá năm bảng Anh.", "got": "Giá £5.", "got_phonemes": "zˈaːɜ nˈam pˈaʊnd.", "expected_phonemes": ["zˈaːɜ nˈam bˈaː4ŋ ˈe-ɲ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_20 / nghe_ngay / post_g2p

```json
{"text": "Giá £5.", "expected": "Giá năm bảng Anh.", "got": "Giá £5.", "got_phonemes": "zˈaːɜ nˈam pˈaʊnd.", "expected_phonemes": ["zˈaːɜ nˈam bˈaː4ŋ ˈe-ɲ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_20 / studio / string

```json
{"text": "Giá £5.", "expected": "Giá năm bảng Anh.", "got": "Giá £5.", "got_phonemes": "zˈaːɜ nˈam pˈaʊnd.", "expected_phonemes": ["zˈaːɜ nˈam bˈaː4ŋ ˈe-ɲ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_20 / studio / post_g2p

```json
{"text": "Giá £5.", "expected": "Giá năm bảng Anh.", "got": "Giá £5.", "got_phonemes": "zˈaːɜ nˈam pˈaʊnd.", "expected_phonemes": ["zˈaːɜ nˈam bˈaː4ŋ ˈe-ɲ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_01 / nghe_ngay / string

```json
{"text": "Dài 2 km.", "expected": ["Dài hai ki lô mét.", "Dài hai cây số."], "got": "Dài 2 km.", "got_phonemes": "zˈaː2j hˈaːj kˈi lˈo mˈɛɜt̪.", "expected_phonemes": ["zˈaː2j hˈaːj kˈi lˈo mˈɛɜt̪.", "zˈaː2j hˈaːj kˈəɪ sˈoɜ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_01 / studio / string

```json
{"text": "Dài 2 km.", "expected": ["Dài hai ki lô mét.", "Dài hai cây số."], "got": "Dài 2 km.", "got_phonemes": "zˈaː2j hˈaːj kˈi lˈo mˈɛɜt̪.", "expected_phonemes": ["zˈaː2j hˈaːj kˈi lˈo mˈɛɜt̪.", "zˈaː2j hˈaːj kˈəɪ sˈoɜ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_02 / nghe_ngay / string

```json
{"text": "Nặng 3 kg.", "expected": ["Nặng ba ki lô gam.", "Nặng ba ký."], "got": "Nặng 3 kg.", "got_phonemes": "nˈa6ŋ bˈaː kˈi lˈo ɣˈaːm.", "expected_phonemes": ["nˈa6ŋ bˈaː kˈi lˈo ɣˈaːm.", "nˈa6ŋ bˈaː kˈiɜ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_02 / studio / string

```json
{"text": "Nặng 3 kg.", "expected": ["Nặng ba ki lô gam.", "Nặng ba ký."], "got": "Nặng 3 kg.", "got_phonemes": "nˈa6ŋ bˈaː kˈi lˈo ɣˈaːm.", "expected_phonemes": ["nˈa6ŋ bˈaː kˈi lˈo ɣˈaːm.", "nˈa6ŋ bˈaː kˈiɜ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_03 / nghe_ngay / string

```json
{"text": "Rộng 4 m².", "expected": "Rộng bốn mét vuông.", "got": "Rộng 4 m².", "got_phonemes": "ɹˈo6ŋ bˈoɜn mˈɛɜt̪ vˈuəŋ.", "expected_phonemes": ["ɹˈo6ŋ bˈoɜn mˈɛɜt̪ vˈuəŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_03 / studio / string

```json
{"text": "Rộng 4 m².", "expected": "Rộng bốn mét vuông.", "got": "Rộng 4 m².", "got_phonemes": "ɹˈo6ŋ bˈoɜn mˈɛɜt̪ vˈuəŋ.", "expected_phonemes": ["ɹˈo6ŋ bˈoɜn mˈɛɜt̪ vˈuəŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_04 / nghe_ngay / string

```json
{"text": "Nóng 25 °C.", "expected": ["Nóng hai mươi lăm độ xê.", "Nóng hai mươi lăm độ C."], "got": "Nóng hai mươi lăm °C.", "got_phonemes": "nˈɔɜŋ hˈaːj mˈyəj lˈam ɗˈo6 sˈe.", "expected_phonemes": ["nˈɔɜŋ hˈaːj mˈyəj lˈam ɗˈo6 sˈe.", "nˈɔɜŋ hˈaːj mˈyəj lˈam ɗˈo6 sˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_04 / studio / string

```json
{"text": "Nóng 25 °C.", "expected": ["Nóng hai mươi lăm độ xê.", "Nóng hai mươi lăm độ C."], "got": "Nóng hai mươi lăm °C.", "got_phonemes": "nˈɔɜŋ hˈaːj mˈyəj lˈam ɗˈo6 sˈe.", "expected_phonemes": ["nˈɔɜŋ hˈaːj mˈyəj lˈam ɗˈo6 sˈe.", "nˈɔɜŋ hˈaːj mˈyəj lˈam ɗˈo6 sˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_05 / nghe_ngay / string

```json
{"text": "Dài 5 cm.", "expected": "Dài năm xen ti mét.", "got": "Dài 5 cm.", "got_phonemes": "zˈaː2j nˈam sˈɛn t̪ˈi mˈɛɜt̪.", "expected_phonemes": ["zˈaː2j nˈam sˈɛn t̪ˈi mˈɛɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_05 / studio / string

```json
{"text": "Dài 5 cm.", "expected": "Dài năm xen ti mét.", "got": "Dài 5 cm.", "got_phonemes": "zˈaː2j nˈam sˈɛn t̪ˈi mˈɛɜt̪.", "expected_phonemes": ["zˈaː2j nˈam sˈɛn t̪ˈi mˈɛɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_06 / nghe_ngay / string

```json
{"text": "Dày 6 mm.", "expected": "Dày sáu mi li mét.", "got": "Dày 6 mm.", "got_phonemes": "zˈa2j sˈaɜw mˈi lˈi mˈɛɜt̪.", "expected_phonemes": ["zˈa2j sˈaɜw mˈi lˈi mˈɛɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_06 / studio / string

```json
{"text": "Dày 6 mm.", "expected": "Dày sáu mi li mét.", "got": "Dày 6 mm.", "got_phonemes": "zˈa2j sˈaɜw mˈi lˈi mˈɛɜt̪.", "expected_phonemes": ["zˈa2j sˈaɜw mˈi lˈi mˈɛɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_07 / nghe_ngay / string

```json
{"text": "Cao 7 m.", "expected": "Cao bảy mét.", "got": "Cao 7 m.", "got_phonemes": "kˈaːw bˈa4j mˈɛɜt̪.", "expected_phonemes": ["kˈaːw bˈa4j mˈɛɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_07 / studio / string

```json
{"text": "Cao 7 m.", "expected": "Cao bảy mét.", "got": "Cao 7 m.", "got_phonemes": "kˈaːw bˈa4j mˈɛɜt̪.", "expected_phonemes": ["kˈaːw bˈa4j mˈɛɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_08 / nghe_ngay / string

```json
{"text": "Chứa 8 m³.", "expected": "Chứa tám mét khối.", "got": "Chứa 8 m³.", "got_phonemes": "tʃˈyəɜ t̪ˈaːɜm mˈɛɜt̪ xˈoɜj.", "expected_phonemes": ["tʃˈyəɜ t̪ˈaːɜm mˈɛɜt̪ xˈoɜj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_08 / studio / string

```json
{"text": "Chứa 8 m³.", "expected": "Chứa tám mét khối.", "got": "Chứa 8 m³.", "got_phonemes": "tʃˈyəɜ t̪ˈaːɜm mˈɛɜt̪ xˈoɜj.", "expected_phonemes": ["tʃˈyəɜ t̪ˈaːɜm mˈɛɜt̪ xˈoɜj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_09 / nghe_ngay / string

```json
{"text": "Cân 9 g.", "expected": "Cân chín gam.", "got": "Cân 9 g.", "got_phonemes": "kˈən tʃˈiɜn ɣˈaːm.", "expected_phonemes": ["kˈən tʃˈiɜn ɣˈaːm."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_09 / studio / string

```json
{"text": "Cân 9 g.", "expected": "Cân chín gam.", "got": "Cân 9 g.", "got_phonemes": "kˈən tʃˈiɜn ɣˈaːm.", "expected_phonemes": ["kˈən tʃˈiɜn ɣˈaːm."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_10 / nghe_ngay / string

```json
{"text": "Liều 10 mg.", "expected": "Liều mười mi li gam.", "got": "Liều 10 mg.", "got_phonemes": "lˈiɛ2w mˈyə2j mˈi lˈi ɣˈaːm.", "expected_phonemes": ["lˈiɛ2w mˈyə2j mˈi lˈi ɣˈaːm."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_10 / studio / string

```json
{"text": "Liều 10 mg.", "expected": "Liều mười mi li gam.", "got": "Liều 10 mg.", "got_phonemes": "lˈiɛ2w mˈyə2j mˈi lˈi ɣˈaːm.", "expected_phonemes": ["lˈiɛ2w mˈyə2j mˈi lˈi ɣˈaːm."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_11 / nghe_ngay / string

```json
{"text": "Rót 2 l.", "expected": "Rót hai lít.", "got": "Rót 2 l.", "got_phonemes": "ɹˈɔɜt̪ hˈaːj lˈiɜt̪.", "expected_phonemes": ["ɹˈɔɜt̪ hˈaːj lˈiɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_11 / studio / string

```json
{"text": "Rót 2 l.", "expected": "Rót hai lít.", "got": "Rót 2 l.", "got_phonemes": "ɹˈɔɜt̪ hˈaːj lˈiɜt̪.", "expected_phonemes": ["ɹˈɔɜt̪ hˈaːj lˈiɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_12 / nghe_ngay / string

```json
{"text": "Rót 250 ml.", "expected": "Rót hai trăm năm mươi mi li lít.", "got": "Rót 250 ml.", "got_phonemes": "ɹˈɔɜt̪ hˈaːj tʃˈam nˈam mˈyəj mˈi lˈi lˈiɜt̪.", "expected_phonemes": ["ɹˈɔɜt̪ hˈaːj tʃˈam nˈam mˈyəj mˈi lˈi lˈiɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_12 / studio / string

```json
{"text": "Rót 250 ml.", "expected": "Rót hai trăm năm mươi mi li lít.", "got": "Rót 250 ml.", "got_phonemes": "ɹˈɔɜt̪ hˈaːj tʃˈam nˈam mˈyəj mˈi lˈi lˈiɜt̪.", "expected_phonemes": ["ɹˈɔɜt̪ hˈaːj tʃˈam nˈam mˈyəj mˈi lˈi lˈiɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_13 / nghe_ngay / string

```json
{"text": "Chạy 60 km/h.", "expected": ["Chạy sáu mươi ki lô mét trên giờ.", "Chạy sáu mươi cây số một giờ."], "got": "Chạy 60 km/h.", "got_phonemes": "tʃˈa6j sˈaɜw mˈyəj kˈi lˈo mˈɛɜt̪ tʃˈen zˈəː2.", "expected_phonemes": ["tʃˈa6j sˈaɜw mˈyəj kˈi lˈo mˈɛɜt̪ tʃˈen zˈəː2.", "tʃˈa6j sˈaɜw mˈyəj kˈəɪ sˈoɜ mˈo6t̪ zˈəː2."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_13 / studio / string

```json
{"text": "Chạy 60 km/h.", "expected": ["Chạy sáu mươi ki lô mét trên giờ.", "Chạy sáu mươi cây số một giờ."], "got": "Chạy 60 km/h.", "got_phonemes": "tʃˈa6j sˈaɜw mˈyəj kˈi lˈo mˈɛɜt̪ tʃˈen zˈəː2.", "expected_phonemes": ["tʃˈa6j sˈaɜw mˈyəj kˈi lˈo mˈɛɜt̪ tʃˈen zˈəː2.", "tʃˈa6j sˈaɜw mˈyəj kˈəɪ sˈoɜ mˈo6t̪ zˈəː2."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_14 / nghe_ngay / string

```json
{"text": "Tốc độ 5 m/s.", "expected": "Tốc độ năm mét trên giây.", "got": "Tốc độ 5 m/s.", "got_phonemes": "t̪ˈoɜk ɗˈo6 nˈam mˈɛɜt̪ tʃˈen zˈəɪ.", "expected_phonemes": ["t̪ˈoɜk ɗˈo6 nˈam mˈɛɜt̪ tʃˈen zˈəɪ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_14 / studio / string

```json
{"text": "Tốc độ 5 m/s.", "expected": "Tốc độ năm mét trên giây.", "got": "Tốc độ 5 m/s.", "got_phonemes": "t̪ˈoɜk ɗˈo6 nˈam mˈɛɜt̪ tʃˈen zˈəɪ.", "expected_phonemes": ["t̪ˈoɜk ɗˈo6 nˈam mˈɛɜt̪ tʃˈen zˈəɪ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_15 / nghe_ngay / string

```json
{"text": "Đèn 12 W.", "expected": "Đèn mười hai oát.", "got": "Đèn 12 W.", "got_phonemes": "ɗˈɛ2n mˈyə2j hˈaːj wˈaːɜt̪.", "expected_phonemes": ["ɗˈɛ2n mˈyə2j hˈaːj wˈaːɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_15 / studio / string

```json
{"text": "Đèn 12 W.", "expected": "Đèn mười hai oát.", "got": "Đèn 12 W.", "got_phonemes": "ɗˈɛ2n mˈyə2j hˈaːj wˈaːɜt̪.", "expected_phonemes": ["ɗˈɛ2n mˈyə2j hˈaːj wˈaːɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_16 / nghe_ngay / string

```json
{"text": "Nguồn 220 V.", "expected": "Nguồn hai trăm hai mươi vôn.", "got": "Nguồn 220 V.", "got_phonemes": "ŋˈuə2n hˈaːj tʃˈam hˈaːj mˈyəj vˈe.", "expected_phonemes": ["ŋˈuə2n hˈaːj tʃˈam hˈaːj mˈyəj vˈon."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_16 / nghe_ngay / post_g2p

```json
{"text": "Nguồn 220 V.", "expected": "Nguồn hai trăm hai mươi vôn.", "got": "Nguồn 220 V.", "got_phonemes": "ŋˈuə2n hˈaːj tʃˈam hˈaːj mˈyəj vˈe.", "expected_phonemes": ["ŋˈuə2n hˈaːj tʃˈam hˈaːj mˈyəj vˈon."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_16 / studio / string

```json
{"text": "Nguồn 220 V.", "expected": "Nguồn hai trăm hai mươi vôn.", "got": "Nguồn 220 V.", "got_phonemes": "ŋˈuə2n hˈaːj tʃˈam hˈaːj mˈyəj vˈe.", "expected_phonemes": ["ŋˈuə2n hˈaːj tʃˈam hˈaːj mˈyəj vˈon."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_16 / studio / post_g2p

```json
{"text": "Nguồn 220 V.", "expected": "Nguồn hai trăm hai mươi vôn.", "got": "Nguồn 220 V.", "got_phonemes": "ŋˈuə2n hˈaːj tʃˈam hˈaːj mˈyəj vˈe.", "expected_phonemes": ["ŋˈuə2n hˈaːj tʃˈam hˈaːj mˈyəj vˈon."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_17 / nghe_ngay / string

```json
{"text": "Nhịp 50 Hz.", "expected": "Nhịp năm mươi héc.", "got": "Nhịp 50 Hz.", "got_phonemes": "ɲˈi6p nˈam mˈyəj hˈɛɜc.", "expected_phonemes": ["ɲˈi6p nˈam mˈyəj hˈɛɜc."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_17 / studio / string

```json
{"text": "Nhịp 50 Hz.", "expected": "Nhịp năm mươi héc.", "got": "Nhịp 50 Hz.", "got_phonemes": "ɲˈi6p nˈam mˈyəj hˈɛɜc.", "expected_phonemes": ["ɲˈi6p nˈam mˈyəj hˈɛɜc."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_18 / nghe_ngay / string

```json
{"text": "Kho 2 GB.", "expected": ["Kho hai ghi ga bai.", "Kho hai gi ga bai."], "got": "Kho 2 <en>G B</en>.", "got_phonemes": "xˈɔ hˈaːj dʒˈiː bˈiː.", "expected_phonemes": ["xˈɔ hˈaːj ɣˈi ɣˈaː bˈaːj.", "xˈɔ hˈaːj zˈi ɣˈaː bˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_18 / nghe_ngay / post_g2p

```json
{"text": "Kho 2 GB.", "expected": ["Kho hai ghi ga bai.", "Kho hai gi ga bai."], "got": "Kho 2 <en>G B</en>.", "got_phonemes": "xˈɔ hˈaːj dʒˈiː bˈiː.", "expected_phonemes": ["xˈɔ hˈaːj ɣˈi ɣˈaː bˈaːj.", "xˈɔ hˈaːj zˈi ɣˈaː bˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_18 / studio / string

```json
{"text": "Kho 2 GB.", "expected": ["Kho hai ghi ga bai.", "Kho hai gi ga bai."], "got": "Kho 2 <en>G B</en>.", "got_phonemes": "xˈɔ hˈaːj dʒˈiː bˈiː.", "expected_phonemes": ["xˈɔ hˈaːj ɣˈi ɣˈaː bˈaːj.", "xˈɔ hˈaːj zˈi ɣˈaː bˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_18 / studio / post_g2p

```json
{"text": "Kho 2 GB.", "expected": ["Kho hai ghi ga bai.", "Kho hai gi ga bai."], "got": "Kho 2 <en>G B</en>.", "got_phonemes": "xˈɔ hˈaːj dʒˈiː bˈiː.", "expected_phonemes": ["xˈɔ hˈaːj ɣˈi ɣˈaː bˈaːj.", "xˈɔ hˈaːj zˈi ɣˈaː bˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_19 / nghe_ngay / string

```json
{"text": "Mức 30 dB.", "expected": "Mức ba mươi đề xi ben.", "got": "Mức ba mươi db.", "got_phonemes": "mˈyɜc bˈaː mˈyəj dˌiːbˈiː.", "expected_phonemes": ["mˈyɜc bˈaː mˈyəj ɗˈe2 sˈi bˈen."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_19 / nghe_ngay / post_g2p

```json
{"text": "Mức 30 dB.", "expected": "Mức ba mươi đề xi ben.", "got": "Mức ba mươi db.", "got_phonemes": "mˈyɜc bˈaː mˈyəj dˌiːbˈiː.", "expected_phonemes": ["mˈyɜc bˈaː mˈyəj ɗˈe2 sˈi bˈen."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_19 / studio / string

```json
{"text": "Mức 30 dB.", "expected": "Mức ba mươi đề xi ben.", "got": "Mức ba mươi db.", "got_phonemes": "mˈyɜc bˈaː mˈyəj dˌiːbˈiː.", "expected_phonemes": ["mˈyɜc bˈaː mˈyəj ɗˈe2 sˈi bˈen."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_19 / studio / post_g2p

```json
{"text": "Mức 30 dB.", "expected": "Mức ba mươi đề xi ben.", "got": "Mức ba mươi db.", "got_phonemes": "mˈyɜc bˈaː mˈyəj dˌiːbˈiː.", "expected_phonemes": ["mˈyɜc bˈaː mˈyəj ɗˈe2 sˈi bˈen."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_20 / nghe_ngay / string

```json
{"text": "Diện tích 1 ha.", "expected": "Diện tích một héc ta.", "got": "Diện tích 1 ha.", "got_phonemes": "zˈiɛ6n t̪ˈiɜc mˈo6t̪ hˈɛɜc t̪ˈaː.", "expected_phonemes": ["zˈiɛ6n t̪ˈiɜc mˈo6t̪ hˈɛɜc t̪ˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_20 / studio / string

```json
{"text": "Diện tích 1 ha.", "expected": "Diện tích một héc ta.", "got": "Diện tích 1 ha.", "got_phonemes": "zˈiɛ6n t̪ˈiɜc mˈo6t̪ hˈɛɜc t̪ˈaː.", "expected_phonemes": ["zˈiɛ6n t̪ˈiɜc mˈo6t̪ hˈɛɜc t̪ˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### phone_code_01 / nghe_ngay / string

```json
{"text": "Số thử 0900123456.", "expected": "Số thử không chín không không một hai ba bốn năm sáu.", "got": "Số thử 0900123456.", "got_phonemes": "sˈoɜ tˈy4 xˌoŋ tʃˈiɜn xˌoŋ xˌoŋ mˈo6t̪ hˈaːj bˈaː bˈoɜn nˈam sˈaɜw.", "expected_phonemes": ["sˈoɜ tˈy4 xˌoŋ tʃˈiɜn xˌoŋ xˌoŋ mˈo6t̪ hˈaːj bˈaː bˈoɜn nˈam sˈaɜw."], "note": "Số giả dùng thử; đọc từng chữ số, không gọi điện."}
```

### phone_code_01 / studio / string

```json
{"text": "Số thử 0900123456.", "expected": "Số thử không chín không không một hai ba bốn năm sáu.", "got": "Số thử 0900123456.", "got_phonemes": "sˈoɜ tˈy4 xˌoŋ tʃˈiɜn xˌoŋ xˌoŋ mˈo6t̪ hˈaːj bˈaː bˈoɜn nˈam sˈaɜw.", "expected_phonemes": ["sˈoɜ tˈy4 xˌoŋ tʃˈiɜn xˌoŋ xˌoŋ mˈo6t̪ hˈaːj bˈaː bˈoɜn nˈam sˈaɜw."], "note": "Số giả dùng thử; đọc từng chữ số, không gọi điện."}
```

### phone_code_02 / nghe_ngay / string

```json
{"text": "Số thử 0910234567.", "expected": "Số thử không chín một không hai ba bốn năm sáu bảy.", "got": "Số thử 0910234567.", "got_phonemes": "sˈoɜ tˈy4 xˌoŋ tʃˈiɜn mˈo6t̪ xˌoŋ hˈaːj bˈaː bˈoɜn nˈam sˈaɜw bˈa4j.", "expected_phonemes": ["sˈoɜ tˈy4 xˌoŋ tʃˈiɜn mˈo6t̪ xˌoŋ hˈaːj bˈaː bˈoɜn nˈam sˈaɜw bˈa4j."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_02 / studio / string

```json
{"text": "Số thử 0910234567.", "expected": "Số thử không chín một không hai ba bốn năm sáu bảy.", "got": "Số thử 0910234567.", "got_phonemes": "sˈoɜ tˈy4 xˌoŋ tʃˈiɜn mˈo6t̪ xˌoŋ hˈaːj bˈaː bˈoɜn nˈam sˈaɜw bˈa4j.", "expected_phonemes": ["sˈoɜ tˈy4 xˌoŋ tʃˈiɜn mˈo6t̪ xˌoŋ hˈaːj bˈaː bˈoɜn nˈam sˈaɜw bˈa4j."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_03 / nghe_ngay / string

```json
{"text": "Số thử 0920345678.", "expected": "Số thử không chín hai không ba bốn năm sáu bảy tám.", "got": "Số thử 0920345678.", "got_phonemes": "sˈoɜ tˈy4 xˌoŋ tʃˈiɜn hˈaːj xˌoŋ bˈaː bˈoɜn nˈam sˈaɜw bˈa4j t̪ˈaːɜm.", "expected_phonemes": ["sˈoɜ tˈy4 xˌoŋ tʃˈiɜn hˈaːj xˌoŋ bˈaː bˈoɜn nˈam sˈaɜw bˈa4j t̪ˈaːɜm."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_03 / studio / string

```json
{"text": "Số thử 0920345678.", "expected": "Số thử không chín hai không ba bốn năm sáu bảy tám.", "got": "Số thử 0920345678.", "got_phonemes": "sˈoɜ tˈy4 xˌoŋ tʃˈiɜn hˈaːj xˌoŋ bˈaː bˈoɜn nˈam sˈaɜw bˈa4j t̪ˈaːɜm.", "expected_phonemes": ["sˈoɜ tˈy4 xˌoŋ tʃˈiɜn hˈaːj xˌoŋ bˈaː bˈoɜn nˈam sˈaɜw bˈa4j t̪ˈaːɜm."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_04 / nghe_ngay / string

```json
{"text": "Số thử 0930456789.", "expected": "Số thử không chín ba không bốn năm sáu bảy tám chín.", "got": "Số thử 0930456789.", "got_phonemes": "sˈoɜ tˈy4 xˌoŋ tʃˈiɜn bˈaː xˌoŋ bˈoɜn nˈam sˈaɜw bˈa4j t̪ˈaːɜm tʃˈiɜn.", "expected_phonemes": ["sˈoɜ tˈy4 xˌoŋ tʃˈiɜn bˈaː xˌoŋ bˈoɜn nˈam sˈaɜw bˈa4j t̪ˈaːɜm tʃˈiɜn."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_04 / studio / string

```json
{"text": "Số thử 0930456789.", "expected": "Số thử không chín ba không bốn năm sáu bảy tám chín.", "got": "Số thử 0930456789.", "got_phonemes": "sˈoɜ tˈy4 xˌoŋ tʃˈiɜn bˈaː xˌoŋ bˈoɜn nˈam sˈaɜw bˈa4j t̪ˈaːɜm tʃˈiɜn.", "expected_phonemes": ["sˈoɜ tˈy4 xˌoŋ tʃˈiɜn bˈaː xˌoŋ bˈoɜn nˈam sˈaɜw bˈa4j t̪ˈaːɜm tʃˈiɜn."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_05 / nghe_ngay / string

```json
{"text": "Số thử 0940567890.", "expected": "Số thử không chín bốn không năm sáu bảy tám chín không.", "got": "Số thử 0940567890.", "got_phonemes": "sˈoɜ tˈy4 xˌoŋ tʃˈiɜn bˈoɜn xˌoŋ nˈam sˈaɜw bˈa4j t̪ˈaːɜm tʃˈiɜn xˌoŋ.", "expected_phonemes": ["sˈoɜ tˈy4 xˌoŋ tʃˈiɜn bˈoɜn xˌoŋ nˈam sˈaɜw bˈa4j t̪ˈaːɜm tʃˈiɜn xˌoŋ."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_05 / studio / string

```json
{"text": "Số thử 0940567890.", "expected": "Số thử không chín bốn không năm sáu bảy tám chín không.", "got": "Số thử 0940567890.", "got_phonemes": "sˈoɜ tˈy4 xˌoŋ tʃˈiɜn bˈoɜn xˌoŋ nˈam sˈaɜw bˈa4j t̪ˈaːɜm tʃˈiɜn xˌoŋ.", "expected_phonemes": ["sˈoɜ tˈy4 xˌoŋ tʃˈiɜn bˈoɜn xˌoŋ nˈam sˈaɜw bˈa4j t̪ˈaːɜm tʃˈiɜn xˌoŋ."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_06 / nghe_ngay / string

```json
{"text": "Số thử 0900 111 222.", "expected": "Số thử không chín không không một một một hai hai hai.", "got": "Số thử 0900 111 222.", "got_phonemes": "sˈoɜ tˈy4 xˌoŋ tʃˈiɜn xˌoŋ xˌoŋ, mˈo6t̪ mˈo6t̪ mˈo6t̪, hˈaːj hˈaːj hˈaːj.", "expected_phonemes": ["sˈoɜ tˈy4 xˌoŋ tʃˈiɜn xˌoŋ xˌoŋ mˈo6t̪ mˈo6t̪ mˈo6t̪ hˈaːj hˈaːj hˈaːj."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_06 / studio / string

```json
{"text": "Số thử 0900 111 222.", "expected": "Số thử không chín không không một một một hai hai hai.", "got": "Số thử 0900 111 222.", "got_phonemes": "sˈoɜ tˈy4 xˌoŋ tʃˈiɜn xˌoŋ xˌoŋ, mˈo6t̪ mˈo6t̪ mˈo6t̪, hˈaːj hˈaːj hˈaːj.", "expected_phonemes": ["sˈoɜ tˈy4 xˌoŋ tʃˈiɜn xˌoŋ xˌoŋ mˈo6t̪ mˈo6t̪ mˈo6t̪ hˈaːj hˈaːj hˈaːj."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_07 / nghe_ngay / string

```json
{"text": "Số thử +84 900 123 456.", "expected": "Số thử cộng tám bốn chín không không một hai ba bốn năm sáu.", "got": "Số thử +84 900 123 456.", "got_phonemes": "sˈoɜ tˈy4 kˈo6ŋ t̪ˈaːɜm bˈoɜn, tʃˈiɜn xˌoŋ xˌoŋ, mˈo6t̪ hˈaːj bˈaː, bˈoɜn nˈam sˈaɜw.", "expected_phonemes": ["sˈoɜ tˈy4 kˈo6ŋ t̪ˈaːɜm bˈoɜn tʃˈiɜn xˌoŋ xˌoŋ mˈo6t̪ hˈaːj bˈaː bˈoɜn nˈam sˈaɜw."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_07 / studio / string

```json
{"text": "Số thử +84 900 123 456.", "expected": "Số thử cộng tám bốn chín không không một hai ba bốn năm sáu.", "got": "Số thử cộng 84 900 123 456.", "got_phonemes": "sˈoɜ tˈy4 kˈo6ŋ t̪ˈaːɜm mˈyəj bˈoɜn t̪ˈi4 tʃˈiɜn tʃˈam tʃˈiɛ6w mˈo6t̪ tʃˈam hˈaːj mˈyəj bˈaː ŋˈi2n bˈoɜn tʃˈam nˈam mˈyəj sˈaɜw.", "expected_phonemes": ["sˈoɜ tˈy4 kˈo6ŋ t̪ˈaːɜm bˈoɜn tʃˈiɜn xˌoŋ xˌoŋ mˈo6t̪ hˈaːj bˈaː bˈoɜn nˈam sˈaɜw."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_07 / studio / post_g2p

```json
{"text": "Số thử +84 900 123 456.", "expected": "Số thử cộng tám bốn chín không không một hai ba bốn năm sáu.", "got": "Số thử cộng 84 900 123 456.", "got_phonemes": "sˈoɜ tˈy4 kˈo6ŋ t̪ˈaːɜm mˈyəj bˈoɜn t̪ˈi4 tʃˈiɜn tʃˈam tʃˈiɛ6w mˈo6t̪ tʃˈam hˈaːj mˈyəj bˈaː ŋˈi2n bˈoɜn tʃˈam nˈam mˈyəj sˈaɜw.", "expected_phonemes": ["sˈoɜ tˈy4 kˈo6ŋ t̪ˈaːɜm bˈoɜn tʃˈiɜn xˌoŋ xˌoŋ mˈo6t̪ hˈaːj bˈaː bˈoɜn nˈam sˈaɜw."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_08 / nghe_ngay / string

```json
{"text": "Mã PIN 0123.", "expected": ["Mã pin không một hai ba.", "Mã pi ai en không một hai ba."], "got": "Mã pin 0123.", "got_phonemes": "mˈaː5 pˈin xˌoŋ mˈo6t̪ hˈaːj bˈaː.", "expected_phonemes": ["mˈaː5 pˈin xˌoŋ mˈo6t̪ hˈaːj bˈaː.", "mˈaː5 pˈi ˈaːj ˈɛn xˌoŋ mˈo6t̪ hˈaːj bˈaː."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_08 / studio / string

```json
{"text": "Mã PIN 0123.", "expected": ["Mã pin không một hai ba.", "Mã pi ai en không một hai ba."], "got": "Mã pin 0123.", "got_phonemes": "mˈaː5 pˈin xˌoŋ mˈo6t̪ hˈaːj bˈaː.", "expected_phonemes": ["mˈaː5 pˈin xˌoŋ mˈo6t̪ hˈaːj bˈaː.", "mˈaː5 pˈi ˈaːj ˈɛn xˌoŋ mˈo6t̪ hˈaːj bˈaː."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_09 / nghe_ngay / string

```json
{"text": "Mã PIN 0005.", "expected": ["Mã pin không không không năm.", "Mã pi ai en không không không năm."], "got": "Mã pin 0005.", "got_phonemes": "mˈaː5 pˈin xˌoŋ xˌoŋ xˌoŋ nˈam.", "expected_phonemes": ["mˈaː5 pˈin xˌoŋ xˌoŋ xˌoŋ nˈam.", "mˈaː5 pˈi ˈaːj ˈɛn xˌoŋ xˌoŋ xˌoŋ nˈam."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_09 / studio / string

```json
{"text": "Mã PIN 0005.", "expected": ["Mã pin không không không năm.", "Mã pi ai en không không không năm."], "got": "Mã pin 0005.", "got_phonemes": "mˈaː5 pˈin xˌoŋ xˌoŋ xˌoŋ nˈam.", "expected_phonemes": ["mˈaː5 pˈin xˌoŋ xˌoŋ xˌoŋ nˈam.", "mˈaː5 pˈi ˈaːj ˈɛn xˌoŋ xˌoŋ xˌoŋ nˈam."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_10 / nghe_ngay / string

```json
{"text": "Mã OTP 654321.", "expected": ["Mã ô ti pi sáu năm bốn ba hai một.", "Mã ô tê pê sáu năm bốn ba hai một."], "got": "Mã <en>O T P</en> sáu trăm năm mươi bốn nghìn ba trăm hai mươi mốt.", "got_phonemes": "mˈaː5 ˈoʊ tˈiː pˈiː sˈaɜw tʃˈam nˈam mˈyəj bˈoɜn ŋˈi2n bˈaː tʃˈam hˈaːj mˈyəj mˈoɜt̪.", "expected_phonemes": ["mˈaː5 ˈo t̪ˈi pˈi sˈaɜw nˈam bˈoɜn bˈaː hˈaːj mˈo6t̪.", "mˈaː5 ˈo t̪ˈe pˈe sˈaɜw nˈam bˈoɜn bˈaː hˈaːj mˈo6t̪."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_10 / nghe_ngay / post_g2p

```json
{"text": "Mã OTP 654321.", "expected": ["Mã ô ti pi sáu năm bốn ba hai một.", "Mã ô tê pê sáu năm bốn ba hai một."], "got": "Mã <en>O T P</en> sáu trăm năm mươi bốn nghìn ba trăm hai mươi mốt.", "got_phonemes": "mˈaː5 ˈoʊ tˈiː pˈiː sˈaɜw tʃˈam nˈam mˈyəj bˈoɜn ŋˈi2n bˈaː tʃˈam hˈaːj mˈyəj mˈoɜt̪.", "expected_phonemes": ["mˈaː5 ˈo t̪ˈi pˈi sˈaɜw nˈam bˈoɜn bˈaː hˈaːj mˈo6t̪.", "mˈaː5 ˈo t̪ˈe pˈe sˈaɜw nˈam bˈoɜn bˈaː hˈaːj mˈo6t̪."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_10 / studio / string

```json
{"text": "Mã OTP 654321.", "expected": ["Mã ô ti pi sáu năm bốn ba hai một.", "Mã ô tê pê sáu năm bốn ba hai một."], "got": "Mã <en>O T P</en> sáu trăm năm mươi bốn nghìn ba trăm hai mươi mốt.", "got_phonemes": "mˈaː5 ˈoʊ tˈiː pˈiː sˈaɜw tʃˈam nˈam mˈyəj bˈoɜn ŋˈi2n bˈaː tʃˈam hˈaːj mˈyəj mˈoɜt̪.", "expected_phonemes": ["mˈaː5 ˈo t̪ˈi pˈi sˈaɜw nˈam bˈoɜn bˈaː hˈaːj mˈo6t̪.", "mˈaː5 ˈo t̪ˈe pˈe sˈaɜw nˈam bˈoɜn bˈaː hˈaːj mˈo6t̪."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_10 / studio / post_g2p

```json
{"text": "Mã OTP 654321.", "expected": ["Mã ô ti pi sáu năm bốn ba hai một.", "Mã ô tê pê sáu năm bốn ba hai một."], "got": "Mã <en>O T P</en> sáu trăm năm mươi bốn nghìn ba trăm hai mươi mốt.", "got_phonemes": "mˈaː5 ˈoʊ tˈiː pˈiː sˈaɜw tʃˈam nˈam mˈyəj bˈoɜn ŋˈi2n bˈaː tʃˈam hˈaːj mˈyəj mˈoɜt̪.", "expected_phonemes": ["mˈaː5 ˈo t̪ˈi pˈi sˈaɜw nˈam bˈoɜn bˈaː hˈaːj mˈo6t̪.", "mˈaː5 ˈo t̪ˈe pˈe sˈaɜw nˈam bˈoɜn bˈaː hˈaːj mˈo6t̪."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_11 / nghe_ngay / string

```json
{"text": "Mã OTP 100200.", "expected": ["Mã ô ti pi một không không hai không không.", "Mã ô tê pê một không không hai không không."], "got": "Mã <en>O T P</en> một trăm nghìn hai trăm.", "got_phonemes": "mˈaː5 ˈoʊ tˈiː pˈiː mˈo6t̪ tʃˈam ŋˈi2n hˈaːj tʃˈam.", "expected_phonemes": ["mˈaː5 ˈo t̪ˈi pˈi mˈo6t̪ xˌoŋ xˌoŋ hˈaːj xˌoŋ xˌoŋ.", "mˈaː5 ˈo t̪ˈe pˈe mˈo6t̪ xˌoŋ xˌoŋ hˈaːj xˌoŋ xˌoŋ."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_11 / nghe_ngay / post_g2p

```json
{"text": "Mã OTP 100200.", "expected": ["Mã ô ti pi một không không hai không không.", "Mã ô tê pê một không không hai không không."], "got": "Mã <en>O T P</en> một trăm nghìn hai trăm.", "got_phonemes": "mˈaː5 ˈoʊ tˈiː pˈiː mˈo6t̪ tʃˈam ŋˈi2n hˈaːj tʃˈam.", "expected_phonemes": ["mˈaː5 ˈo t̪ˈi pˈi mˈo6t̪ xˌoŋ xˌoŋ hˈaːj xˌoŋ xˌoŋ.", "mˈaː5 ˈo t̪ˈe pˈe mˈo6t̪ xˌoŋ xˌoŋ hˈaːj xˌoŋ xˌoŋ."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_11 / studio / string

```json
{"text": "Mã OTP 100200.", "expected": ["Mã ô ti pi một không không hai không không.", "Mã ô tê pê một không không hai không không."], "got": "Mã <en>O T P</en> một trăm nghìn hai trăm.", "got_phonemes": "mˈaː5 ˈoʊ tˈiː pˈiː mˈo6t̪ tʃˈam ŋˈi2n hˈaːj tʃˈam.", "expected_phonemes": ["mˈaː5 ˈo t̪ˈi pˈi mˈo6t̪ xˌoŋ xˌoŋ hˈaːj xˌoŋ xˌoŋ.", "mˈaː5 ˈo t̪ˈe pˈe mˈo6t̪ xˌoŋ xˌoŋ hˈaːj xˌoŋ xˌoŋ."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_11 / studio / post_g2p

```json
{"text": "Mã OTP 100200.", "expected": ["Mã ô ti pi một không không hai không không.", "Mã ô tê pê một không không hai không không."], "got": "Mã <en>O T P</en> một trăm nghìn hai trăm.", "got_phonemes": "mˈaː5 ˈoʊ tˈiː pˈiː mˈo6t̪ tʃˈam ŋˈi2n hˈaːj tʃˈam.", "expected_phonemes": ["mˈaː5 ˈo t̪ˈi pˈi mˈo6t̪ xˌoŋ xˌoŋ hˈaːj xˌoŋ xˌoŋ.", "mˈaː5 ˈo t̪ˈe pˈe mˈo6t̪ xˌoŋ xˌoŋ hˈaːj xˌoŋ xˌoŋ."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_12 / nghe_ngay / string

```json
{"text": "Mã vé 0017.", "expected": "Mã vé không không một bảy.", "got": "Mã vé 0017.", "got_phonemes": "mˈaː5 vˈɛɜ xˌoŋ xˌoŋ mˈo6t̪ bˈa4j.", "expected_phonemes": ["mˈaː5 vˈɛɜ xˌoŋ xˌoŋ mˈo6t̪ bˈa4j."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_12 / studio / string

```json
{"text": "Mã vé 0017.", "expected": "Mã vé không không một bảy.", "got": "Mã vé 0017.", "got_phonemes": "mˈaː5 vˈɛɜ xˌoŋ xˌoŋ mˈo6t̪ bˈa4j.", "expected_phonemes": ["mˈaː5 vˈɛɜ xˌoŋ xˌoŋ mˈo6t̪ bˈa4j."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_13 / nghe_ngay / string

```json
{"text": "Mã vé 0204.", "expected": "Mã vé không hai không bốn.", "got": "Mã vé 0204.", "got_phonemes": "mˈaː5 vˈɛɜ xˌoŋ hˈaːj xˌoŋ bˈoɜn.", "expected_phonemes": ["mˈaː5 vˈɛɜ xˌoŋ hˈaːj xˌoŋ bˈoɜn."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_13 / studio / string

```json
{"text": "Mã vé 0204.", "expected": "Mã vé không hai không bốn.", "got": "Mã vé 0204.", "got_phonemes": "mˈaː5 vˈɛɜ xˌoŋ hˈaːj xˌoŋ bˈoɜn.", "expected_phonemes": ["mˈaː5 vˈɛɜ xˌoŋ hˈaːj xˌoŋ bˈoɜn."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_14 / nghe_ngay / string

```json
{"text": "Mã vé 3006.", "expected": "Mã vé ba không không sáu.", "got": "Mã vé ba nghìn không trăm lẻ sáu.", "got_phonemes": "mˈaː5 vˈɛɜ bˈaː ŋˈi2n xˌoŋ tʃˈam lˈɛ4 sˈaɜw.", "expected_phonemes": ["mˈaː5 vˈɛɜ bˈaː xˌoŋ xˌoŋ sˈaɜw."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_14 / nghe_ngay / post_g2p

```json
{"text": "Mã vé 3006.", "expected": "Mã vé ba không không sáu.", "got": "Mã vé ba nghìn không trăm lẻ sáu.", "got_phonemes": "mˈaː5 vˈɛɜ bˈaː ŋˈi2n xˌoŋ tʃˈam lˈɛ4 sˈaɜw.", "expected_phonemes": ["mˈaː5 vˈɛɜ bˈaː xˌoŋ xˌoŋ sˈaɜw."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_14 / studio / string

```json
{"text": "Mã vé 3006.", "expected": "Mã vé ba không không sáu.", "got": "Mã vé ba nghìn không trăm lẻ sáu.", "got_phonemes": "mˈaː5 vˈɛɜ bˈaː ŋˈi2n xˌoŋ tʃˈam lˈɛ4 sˈaɜw.", "expected_phonemes": ["mˈaː5 vˈɛɜ bˈaː xˌoŋ xˌoŋ sˈaɜw."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_14 / studio / post_g2p

```json
{"text": "Mã vé 3006.", "expected": "Mã vé ba không không sáu.", "got": "Mã vé ba nghìn không trăm lẻ sáu.", "got_phonemes": "mˈaː5 vˈɛɜ bˈaː ŋˈi2n xˌoŋ tʃˈam lˈɛ4 sˈaɜw.", "expected_phonemes": ["mˈaː5 vˈɛɜ bˈaː xˌoŋ xˌoŋ sˈaɜw."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_15 / nghe_ngay / string

```json
{"text": "Mã AB12.", "expected": ["Mã ây bi một hai.", "Mã a bê một hai."], "got": "Mã a bê mười hai.", "got_phonemes": "mˈaː5 ˈaː bˈe mˈyə2j hˈaːj.", "expected_phonemes": ["mˈaː5 ˈəɪ bˈi mˈo6t̪ hˈaːj.", "mˈaː5 ˈaː bˈe mˈo6t̪ hˈaːj."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_15 / nghe_ngay / post_g2p

```json
{"text": "Mã AB12.", "expected": ["Mã ây bi một hai.", "Mã a bê một hai."], "got": "Mã a bê mười hai.", "got_phonemes": "mˈaː5 ˈaː bˈe mˈyə2j hˈaːj.", "expected_phonemes": ["mˈaː5 ˈəɪ bˈi mˈo6t̪ hˈaːj.", "mˈaː5 ˈaː bˈe mˈo6t̪ hˈaːj."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_15 / studio / string

```json
{"text": "Mã AB12.", "expected": ["Mã ây bi một hai.", "Mã a bê một hai."], "got": "Mã a bê mười hai.", "got_phonemes": "mˈaː5 ˈaː bˈe mˈyə2j hˈaːj.", "expected_phonemes": ["mˈaː5 ˈəɪ bˈi mˈo6t̪ hˈaːj.", "mˈaː5 ˈaː bˈe mˈo6t̪ hˈaːj."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_15 / studio / post_g2p

```json
{"text": "Mã AB12.", "expected": ["Mã ây bi một hai.", "Mã a bê một hai."], "got": "Mã a bê mười hai.", "got_phonemes": "mˈaː5 ˈaː bˈe mˈyə2j hˈaːj.", "expected_phonemes": ["mˈaː5 ˈəɪ bˈi mˈo6t̪ hˈaːj.", "mˈaː5 ˈaː bˈe mˈo6t̪ hˈaːj."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_16 / nghe_ngay / string

```json
{"text": "Mã CD34.", "expected": ["Mã xi đi ba bốn.", "Mã xê đê ba bốn."], "got": "Mã xê đê ba mươi bốn.", "got_phonemes": "mˈaː5 sˈe ɗˈe bˈaː mˈyəj bˈoɜn.", "expected_phonemes": ["mˈaː5 sˈi ɗˈi bˈaː bˈoɜn.", "mˈaː5 sˈe ɗˈe bˈaː bˈoɜn."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_16 / nghe_ngay / post_g2p

```json
{"text": "Mã CD34.", "expected": ["Mã xi đi ba bốn.", "Mã xê đê ba bốn."], "got": "Mã xê đê ba mươi bốn.", "got_phonemes": "mˈaː5 sˈe ɗˈe bˈaː mˈyəj bˈoɜn.", "expected_phonemes": ["mˈaː5 sˈi ɗˈi bˈaː bˈoɜn.", "mˈaː5 sˈe ɗˈe bˈaː bˈoɜn."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_16 / studio / string

```json
{"text": "Mã CD34.", "expected": ["Mã xi đi ba bốn.", "Mã xê đê ba bốn."], "got": "Mã xê đê ba mươi bốn.", "got_phonemes": "mˈaː5 sˈe ɗˈe bˈaː mˈyəj bˈoɜn.", "expected_phonemes": ["mˈaː5 sˈi ɗˈi bˈaː bˈoɜn.", "mˈaː5 sˈe ɗˈe bˈaː bˈoɜn."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_16 / studio / post_g2p

```json
{"text": "Mã CD34.", "expected": ["Mã xi đi ba bốn.", "Mã xê đê ba bốn."], "got": "Mã xê đê ba mươi bốn.", "got_phonemes": "mˈaː5 sˈe ɗˈe bˈaː mˈyəj bˈoɜn.", "expected_phonemes": ["mˈaː5 sˈi ɗˈi bˈaː bˈoɜn.", "mˈaː5 sˈe ɗˈe bˈaː bˈoɜn."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_17 / nghe_ngay / string

```json
{"text": "Mã ZX90.", "expected": ["Mã dét ích chín không.", "Mã zi éc chín không."], "got": "Mã dét ích chín mươi.", "got_phonemes": "mˈaː5 zˈɛɜt̪ ˈiɜc tʃˈiɜn mˈyəj.", "expected_phonemes": ["mˈaː5 zˈɛɜt̪ ˈiɜc tʃˈiɜn xˌoŋ.", "mˈaː5 zˈaɪ ˈɛɜc tʃˈiɜn xˌoŋ."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_17 / nghe_ngay / post_g2p

```json
{"text": "Mã ZX90.", "expected": ["Mã dét ích chín không.", "Mã zi éc chín không."], "got": "Mã dét ích chín mươi.", "got_phonemes": "mˈaː5 zˈɛɜt̪ ˈiɜc tʃˈiɜn mˈyəj.", "expected_phonemes": ["mˈaː5 zˈɛɜt̪ ˈiɜc tʃˈiɜn xˌoŋ.", "mˈaː5 zˈaɪ ˈɛɜc tʃˈiɜn xˌoŋ."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_17 / studio / string

```json
{"text": "Mã ZX90.", "expected": ["Mã dét ích chín không.", "Mã zi éc chín không."], "got": "Mã dét ích chín mươi.", "got_phonemes": "mˈaː5 zˈɛɜt̪ ˈiɜc tʃˈiɜn mˈyəj.", "expected_phonemes": ["mˈaː5 zˈɛɜt̪ ˈiɜc tʃˈiɜn xˌoŋ.", "mˈaː5 zˈaɪ ˈɛɜc tʃˈiɜn xˌoŋ."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_17 / studio / post_g2p

```json
{"text": "Mã ZX90.", "expected": ["Mã dét ích chín không.", "Mã zi éc chín không."], "got": "Mã dét ích chín mươi.", "got_phonemes": "mˈaː5 zˈɛɜt̪ ˈiɜc tʃˈiɜn mˈyəj.", "expected_phonemes": ["mˈaː5 zˈɛɜt̪ ˈiɜc tʃˈiɜn xˌoŋ.", "mˈaː5 zˈaɪ ˈɛɜc tʃˈiɜn xˌoŋ."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_18 / nghe_ngay / string

```json
{"text": "Phòng A101.", "expected": ["Phòng a một không một.", "Phòng ây một không một.", "Phòng a một trăm linh một."], "got": "Phòng a một trăm lẻ một.", "got_phonemes": "fˈɔ2ŋ ˈaː mˈo6t̪ tʃˈam lˈɛ4 mˈo6t̪.", "expected_phonemes": ["fˈɔ2ŋ ˈaː mˈo6t̪ xˌoŋ mˈo6t̪.", "fˈɔ2ŋ ˈəɪ mˈo6t̪ xˌoŋ mˈo6t̪.", "fˈɔ2ŋ ˈaː mˈo6t̪ tʃˈam lˈiɲ mˈo6t̪."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_18 / nghe_ngay / post_g2p

```json
{"text": "Phòng A101.", "expected": ["Phòng a một không một.", "Phòng ây một không một.", "Phòng a một trăm linh một."], "got": "Phòng a một trăm lẻ một.", "got_phonemes": "fˈɔ2ŋ ˈaː mˈo6t̪ tʃˈam lˈɛ4 mˈo6t̪.", "expected_phonemes": ["fˈɔ2ŋ ˈaː mˈo6t̪ xˌoŋ mˈo6t̪.", "fˈɔ2ŋ ˈəɪ mˈo6t̪ xˌoŋ mˈo6t̪.", "fˈɔ2ŋ ˈaː mˈo6t̪ tʃˈam lˈiɲ mˈo6t̪."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_18 / studio / string

```json
{"text": "Phòng A101.", "expected": ["Phòng a một không một.", "Phòng ây một không một.", "Phòng a một trăm linh một."], "got": "Phòng a một trăm lẻ một.", "got_phonemes": "fˈɔ2ŋ ˈaː mˈo6t̪ tʃˈam lˈɛ4 mˈo6t̪.", "expected_phonemes": ["fˈɔ2ŋ ˈaː mˈo6t̪ xˌoŋ mˈo6t̪.", "fˈɔ2ŋ ˈəɪ mˈo6t̪ xˌoŋ mˈo6t̪.", "fˈɔ2ŋ ˈaː mˈo6t̪ tʃˈam lˈiɲ mˈo6t̪."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_18 / studio / post_g2p

```json
{"text": "Phòng A101.", "expected": ["Phòng a một không một.", "Phòng ây một không một.", "Phòng a một trăm linh một."], "got": "Phòng a một trăm lẻ một.", "got_phonemes": "fˈɔ2ŋ ˈaː mˈo6t̪ tʃˈam lˈɛ4 mˈo6t̪.", "expected_phonemes": ["fˈɔ2ŋ ˈaː mˈo6t̪ xˌoŋ mˈo6t̪.", "fˈɔ2ŋ ˈəɪ mˈo6t̪ xˌoŋ mˈo6t̪.", "fˈɔ2ŋ ˈaː mˈo6t̪ tʃˈam lˈiɲ mˈo6t̪."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_19 / nghe_ngay / string

```json
{"text": "Mã 007.", "expected": "Mã không không bảy.", "got": "Mã 007.", "got_phonemes": "mˈaː5 xˌoŋ xˌoŋ bˈa4j.", "expected_phonemes": ["mˈaː5 xˌoŋ xˌoŋ bˈa4j."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_19 / studio / string

```json
{"text": "Mã 007.", "expected": "Mã không không bảy.", "got": "Mã 007.", "got_phonemes": "mˈaː5 xˌoŋ xˌoŋ bˈa4j.", "expected_phonemes": ["mˈaː5 xˌoŋ xˌoŋ bˈa4j."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_20 / nghe_ngay / string

```json
{"text": "Mã 0000.", "expected": "Mã không không không không.", "got": "Mã 0000.", "got_phonemes": "mˈaː5 xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["mˈaː5 xˌoŋ xˌoŋ xˌoŋ xˌoŋ."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_20 / studio / string

```json
{"text": "Mã 0000.", "expected": "Mã không không không không.", "got": "Mã 0000.", "got_phonemes": "mˈaː5 xˌoŋ xˌoŋ xˌoŋ xˌoŋ.", "expected_phonemes": ["mˈaː5 xˌoŋ xˌoŋ xˌoŋ xˌoŋ."], "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### abbrev_vi_09 / nghe_ngay / string

```json
{"text": "Tại Q.1.", "expected": "Tại quận một.", "got": "Tại quận 1.", "got_phonemes": "t̪ˈaː6j kwˈə6n mˈo6t̪.", "expected_phonemes": ["t̪ˈaː6j kwˈə6n mˈo6t̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_09 / studio / string

```json
{"text": "Tại Q.1.", "expected": "Tại quận một.", "got": "Tại quận 1.", "got_phonemes": "t̪ˈaː6j kwˈə6n mˈo6t̪.", "expected_phonemes": ["t̪ˈaː6j kwˈə6n mˈo6t̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_10 / nghe_ngay / string

```json
{"text": "Tại P.2.", "expected": "Tại phường hai.", "got": "Tại phường 2.", "got_phonemes": "t̪ˈaː6j fˈyə2ŋ hˈaːj.", "expected_phonemes": ["t̪ˈaː6j fˈyə2ŋ hˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_10 / studio / string

```json
{"text": "Tại P.2.", "expected": "Tại phường hai.", "got": "Tại phường 2.", "got_phonemes": "t̪ˈaː6j fˈyə2ŋ hˈaːj.", "expected_phonemes": ["t̪ˈaː6j fˈyə2ŋ hˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_12 / nghe_ngay / string

```json
{"text": "Đọc VD. này.", "expected": "Đọc ví dụ này.", "got": "Đọc <en>V D</en>. này.", "got_phonemes": "ɗˈɔ6k vˈiː dˈiː. nˈa2j.", "expected_phonemes": ["ɗˈɔ6k vˈiɜ zˈu6 nˈa2j."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_12 / nghe_ngay / post_g2p

```json
{"text": "Đọc VD. này.", "expected": "Đọc ví dụ này.", "got": "Đọc <en>V D</en>. này.", "got_phonemes": "ɗˈɔ6k vˈiː dˈiː. nˈa2j.", "expected_phonemes": ["ɗˈɔ6k vˈiɜ zˈu6 nˈa2j."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_12 / studio / string

```json
{"text": "Đọc VD. này.", "expected": "Đọc ví dụ này.", "got": "Đọc <en>V D</en>. này.", "got_phonemes": "ɗˈɔ6k vˈiː dˈiː. nˈa2j.", "expected_phonemes": ["ɗˈɔ6k vˈiɜ zˈu6 nˈa2j."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_12 / studio / post_g2p

```json
{"text": "Đọc VD. này.", "expected": "Đọc ví dụ này.", "got": "Đọc <en>V D</en>. này.", "got_phonemes": "ɗˈɔ6k vˈiː dˈiː. nˈa2j.", "expected_phonemes": ["ɗˈɔ6k vˈiɜ zˈu6 nˈa2j."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_13 / nghe_ngay / string

```json
{"text": "Xem tr. 5.", "expected": "Xem trang năm.", "got": "Xem tr. năm.", "got_phonemes": "sˈɛm tˌiːˈɑːɹ, nˈam.", "expected_phonemes": ["sˈɛm tʃˈaːŋ nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_13 / nghe_ngay / post_g2p

```json
{"text": "Xem tr. 5.", "expected": "Xem trang năm.", "got": "Xem tr. năm.", "got_phonemes": "sˈɛm tˌiːˈɑːɹ, nˈam.", "expected_phonemes": ["sˈɛm tʃˈaːŋ nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_13 / studio / string

```json
{"text": "Xem tr. 5.", "expected": "Xem trang năm.", "got": "Xem tr. năm.", "got_phonemes": "sˈɛm tˌiːˈɑːɹ, nˈam.", "expected_phonemes": ["sˈɛm tʃˈaːŋ nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_13 / studio / post_g2p

```json
{"text": "Xem tr. 5.", "expected": "Xem trang năm.", "got": "Xem tr. năm.", "got_phonemes": "sˈɛm tˌiːˈɑːɹ, nˈam.", "expected_phonemes": ["sˈɛm tʃˈaːŋ nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_17 / nghe_ngay / string

```json
{"text": "Học CĐ.", "expected": "Học cao đẳng.", "got": "Học CĐ.", "got_phonemes": "hˈɔ6k sˈe ɗˈe.", "expected_phonemes": ["hˈɔ6k kˈaːw ɗˈa4ŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_17 / nghe_ngay / post_g2p

```json
{"text": "Học CĐ.", "expected": "Học cao đẳng.", "got": "Học CĐ.", "got_phonemes": "hˈɔ6k sˈe ɗˈe.", "expected_phonemes": ["hˈɔ6k kˈaːw ɗˈa4ŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_17 / studio / string

```json
{"text": "Học CĐ.", "expected": "Học cao đẳng.", "got": "Học CĐ.", "got_phonemes": "hˈɔ6k sˈe ɗˈe.", "expected_phonemes": ["hˈɔ6k kˈaːw ɗˈa4ŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_17 / studio / post_g2p

```json
{"text": "Học CĐ.", "expected": "Học cao đẳng.", "got": "Học CĐ.", "got_phonemes": "hˈɔ6k sˈe ɗˈe.", "expected_phonemes": ["hˈɔ6k kˈaːw ɗˈa4ŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_19 / nghe_ngay / string

```json
{"text": "Tìm SĐT.", "expected": "Tìm số điện thoại.", "got": "Tìm SĐT.", "got_phonemes": "t̪ˈi2m ˈɛɜt̪ ɗˈe t̪ˈe.", "expected_phonemes": ["t̪ˈi2m sˈoɜ ɗˈiɛ6n twˈaː6j."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_19 / nghe_ngay / post_g2p

```json
{"text": "Tìm SĐT.", "expected": "Tìm số điện thoại.", "got": "Tìm SĐT.", "got_phonemes": "t̪ˈi2m ˈɛɜt̪ ɗˈe t̪ˈe.", "expected_phonemes": ["t̪ˈi2m sˈoɜ ɗˈiɛ6n twˈaː6j."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_19 / studio / string

```json
{"text": "Tìm SĐT.", "expected": "Tìm số điện thoại.", "got": "Tìm SĐT.", "got_phonemes": "t̪ˈi2m ˈɛɜt̪ ɗˈe t̪ˈe.", "expected_phonemes": ["t̪ˈi2m sˈoɜ ɗˈiɛ6n twˈaː6j."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_19 / studio / post_g2p

```json
{"text": "Tìm SĐT.", "expected": "Tìm số điện thoại.", "got": "Tìm SĐT.", "got_phonemes": "t̪ˈi2m ˈɛɜt̪ ɗˈe t̪ˈe.", "expected_phonemes": ["t̪ˈi2m sˈoɜ ɗˈiɛ6n twˈaː6j."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_05 / nghe_ngay / string

```json
{"text": "Gặp CEO.", "expected": ["Gặp xi i ô.", "Gặp giám đốc điều hành."], "got": "Gặp <en>C E O</en>.", "got_phonemes": "ɣˈa6p sˈiː ˈiː ˈoʊ.", "expected_phonemes": ["ɣˈa6p sˈi ˈi ˈo.", "ɣˈa6p zˈaːɜm ɗˈoɜk ɗˈiɛ2w hˈe-2ɲ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_05 / nghe_ngay / post_g2p

```json
{"text": "Gặp CEO.", "expected": ["Gặp xi i ô.", "Gặp giám đốc điều hành."], "got": "Gặp <en>C E O</en>.", "got_phonemes": "ɣˈa6p sˈiː ˈiː ˈoʊ.", "expected_phonemes": ["ɣˈa6p sˈi ˈi ˈo.", "ɣˈa6p zˈaːɜm ɗˈoɜk ɗˈiɛ2w hˈe-2ɲ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_05 / studio / string

```json
{"text": "Gặp CEO.", "expected": ["Gặp xi i ô.", "Gặp giám đốc điều hành."], "got": "Gặp <en>C E O</en>.", "got_phonemes": "ɣˈa6p sˈiː ˈiː ˈoʊ.", "expected_phonemes": ["ɣˈa6p sˈi ˈi ˈo.", "ɣˈa6p zˈaːɜm ɗˈoɜk ɗˈiɛ2w hˈe-2ɲ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_05 / studio / post_g2p

```json
{"text": "Gặp CEO.", "expected": ["Gặp xi i ô.", "Gặp giám đốc điều hành."], "got": "Gặp <en>C E O</en>.", "got_phonemes": "ɣˈa6p sˈiː ˈiː ˈoʊ.", "expected_phonemes": ["ɣˈa6p sˈi ˈi ˈo.", "ɣˈa6p zˈaːɜm ɗˈoɜk ɗˈiɛ2w hˈe-2ɲ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_07 / nghe_ngay / string

```json
{"text": "Đỏ vs. xanh.", "expected": ["Đỏ với xanh.", "Đỏ đấu với xanh.", "Đỏ versus xanh."], "got": "Đỏ vs. xanh.", "got_phonemes": "ɗˈɔ4 vˌiːˈɛs, sˈe-ɲ.", "expected_phonemes": ["ɗˈɔ4 vˌəːɜj sˈe-ɲ.", "ɗˈɔ4 ɗˈəɜw vˌəːɜj sˈe-ɲ.", "ɗˈɔ4 vˈɜːsᵻz sˈe-ɲ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_07 / nghe_ngay / post_g2p

```json
{"text": "Đỏ vs. xanh.", "expected": ["Đỏ với xanh.", "Đỏ đấu với xanh.", "Đỏ versus xanh."], "got": "Đỏ vs. xanh.", "got_phonemes": "ɗˈɔ4 vˌiːˈɛs, sˈe-ɲ.", "expected_phonemes": ["ɗˈɔ4 vˌəːɜj sˈe-ɲ.", "ɗˈɔ4 ɗˈəɜw vˌəːɜj sˈe-ɲ.", "ɗˈɔ4 vˈɜːsᵻz sˈe-ɲ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_07 / studio / string

```json
{"text": "Đỏ vs. xanh.", "expected": ["Đỏ với xanh.", "Đỏ đấu với xanh.", "Đỏ versus xanh."], "got": "Đỏ vs. xanh.", "got_phonemes": "ɗˈɔ4 vˌiːˈɛs, sˈe-ɲ.", "expected_phonemes": ["ɗˈɔ4 vˌəːɜj sˈe-ɲ.", "ɗˈɔ4 ɗˈəɜw vˌəːɜj sˈe-ɲ.", "ɗˈɔ4 vˈɜːsᵻz sˈe-ɲ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_07 / studio / post_g2p

```json
{"text": "Đỏ vs. xanh.", "expected": ["Đỏ với xanh.", "Đỏ đấu với xanh.", "Đỏ versus xanh."], "got": "Đỏ vs. xanh.", "got_phonemes": "ɗˈɔ4 vˌiːˈɛs, sˈe-ɲ.", "expected_phonemes": ["ɗˈɔ4 vˌəːɜj sˈe-ɲ.", "ɗˈɔ4 ɗˈəɜw vˌəːɜj sˈe-ɲ.", "ɗˈɔ4 vˈɜːsᵻz sˈe-ɲ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_08 / nghe_ngay / string

```json
{"text": "Gắn CPU.", "expected": ["Gắn xi pi iu.", "Gắn xê pê u."], "got": "Gắn <en>C P U</en>.", "got_phonemes": "ɣˈaɜn sˈiː pˈiː jˈuː.", "expected_phonemes": ["ɣˈaɜn sˈi pˈi ˈiw.", "ɣˈaɜn sˈe pˈe ˈu."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_08 / nghe_ngay / post_g2p

```json
{"text": "Gắn CPU.", "expected": ["Gắn xi pi iu.", "Gắn xê pê u."], "got": "Gắn <en>C P U</en>.", "got_phonemes": "ɣˈaɜn sˈiː pˈiː jˈuː.", "expected_phonemes": ["ɣˈaɜn sˈi pˈi ˈiw.", "ɣˈaɜn sˈe pˈe ˈu."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_08 / studio / string

```json
{"text": "Gắn CPU.", "expected": ["Gắn xi pi iu.", "Gắn xê pê u."], "got": "Gắn <en>C P U</en>.", "got_phonemes": "ɣˈaɜn sˈiː pˈiː jˈuː.", "expected_phonemes": ["ɣˈaɜn sˈi pˈi ˈiw.", "ɣˈaɜn sˈe pˈe ˈu."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_08 / studio / post_g2p

```json
{"text": "Gắn CPU.", "expected": ["Gắn xi pi iu.", "Gắn xê pê u."], "got": "Gắn <en>C P U</en>.", "got_phonemes": "ɣˈaɜn sˈiː pˈiː jˈuː.", "expected_phonemes": ["ɣˈaɜn sˈi pˈi ˈiw.", "ɣˈaɜn sˈe pˈe ˈu."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_09 / nghe_ngay / string

```json
{"text": "Gắn GPU.", "expected": ["Gắn gi pi iu.", "Gắn gi pê u."], "got": "Gắn <en>G P U</en>.", "got_phonemes": "ɣˈaɜn dʒˈiː pˈiː jˈuː.", "expected_phonemes": ["ɣˈaɜn zˈi pˈi ˈiw.", "ɣˈaɜn zˈi pˈe ˈu."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_09 / nghe_ngay / post_g2p

```json
{"text": "Gắn GPU.", "expected": ["Gắn gi pi iu.", "Gắn gi pê u."], "got": "Gắn <en>G P U</en>.", "got_phonemes": "ɣˈaɜn dʒˈiː pˈiː jˈuː.", "expected_phonemes": ["ɣˈaɜn zˈi pˈi ˈiw.", "ɣˈaɜn zˈi pˈe ˈu."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_09 / studio / string

```json
{"text": "Gắn GPU.", "expected": ["Gắn gi pi iu.", "Gắn gi pê u."], "got": "Gắn <en>G P U</en>.", "got_phonemes": "ɣˈaɜn dʒˈiː pˈiː jˈuː.", "expected_phonemes": ["ɣˈaɜn zˈi pˈi ˈiw.", "ɣˈaɜn zˈi pˈe ˈu."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_09 / studio / post_g2p

```json
{"text": "Gắn GPU.", "expected": ["Gắn gi pi iu.", "Gắn gi pê u."], "got": "Gắn <en>G P U</en>.", "got_phonemes": "ɣˈaɜn dʒˈiː pˈiː jˈuː.", "expected_phonemes": ["ɣˈaɜn zˈi pˈi ˈiw.", "ɣˈaɜn zˈi pˈe ˈu."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_10 / nghe_ngay / string

```json
{"text": "Đọc PDF.", "expected": ["Đọc pi đi ép.", "Đọc pê đê ép."], "got": "Đọc <en>P D F</en>.", "got_phonemes": "ɗˈɔ6k pˈiː dˈiː ˈɛf.", "expected_phonemes": ["ɗˈɔ6k pˈi ɗˈi ˈɛɜp.", "ɗˈɔ6k pˈe ɗˈe ˈɛɜp."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_10 / nghe_ngay / post_g2p

```json
{"text": "Đọc PDF.", "expected": ["Đọc pi đi ép.", "Đọc pê đê ép."], "got": "Đọc <en>P D F</en>.", "got_phonemes": "ɗˈɔ6k pˈiː dˈiː ˈɛf.", "expected_phonemes": ["ɗˈɔ6k pˈi ɗˈi ˈɛɜp.", "ɗˈɔ6k pˈe ɗˈe ˈɛɜp."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_10 / studio / string

```json
{"text": "Đọc PDF.", "expected": ["Đọc pi đi ép.", "Đọc pê đê ép."], "got": "Đọc <en>P D F</en>.", "got_phonemes": "ɗˈɔ6k pˈiː dˈiː ˈɛf.", "expected_phonemes": ["ɗˈɔ6k pˈi ɗˈi ˈɛɜp.", "ɗˈɔ6k pˈe ɗˈe ˈɛɜp."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_10 / studio / post_g2p

```json
{"text": "Đọc PDF.", "expected": ["Đọc pi đi ép.", "Đọc pê đê ép."], "got": "Đọc <en>P D F</en>.", "got_phonemes": "ɗˈɔ6k pˈiː dˈiː ˈɛf.", "expected_phonemes": ["ɗˈɔ6k pˈi ɗˈi ˈɛɜp.", "ɗˈɔ6k pˈe ɗˈe ˈɛɜp."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_11 / nghe_ngay / string

```json
{"text": "Mở USB.", "expected": ["Mở iu ét bi.", "Mở u ét bê."], "got": "Mở <en>U S B</en>.", "got_phonemes": "mˈəː4 jˈuː ˈɛs bˈiː.", "expected_phonemes": ["mˈəː4 ˈiw ˈɛɜt̪ bˈi.", "mˈəː4 ˈu ˈɛɜt̪ bˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_11 / nghe_ngay / post_g2p

```json
{"text": "Mở USB.", "expected": ["Mở iu ét bi.", "Mở u ét bê."], "got": "Mở <en>U S B</en>.", "got_phonemes": "mˈəː4 jˈuː ˈɛs bˈiː.", "expected_phonemes": ["mˈəː4 ˈiw ˈɛɜt̪ bˈi.", "mˈəː4 ˈu ˈɛɜt̪ bˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_11 / studio / string

```json
{"text": "Mở USB.", "expected": ["Mở iu ét bi.", "Mở u ét bê."], "got": "Mở <en>U S B</en>.", "got_phonemes": "mˈəː4 jˈuː ˈɛs bˈiː.", "expected_phonemes": ["mˈəː4 ˈiw ˈɛɜt̪ bˈi.", "mˈəː4 ˈu ˈɛɜt̪ bˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_11 / studio / post_g2p

```json
{"text": "Mở USB.", "expected": ["Mở iu ét bi.", "Mở u ét bê."], "got": "Mở <en>U S B</en>.", "got_phonemes": "mˈəː4 jˈuː ˈɛs bˈiː.", "expected_phonemes": ["mˈəː4 ˈiw ˈɛɜt̪ bˈi.", "mˈəː4 ˈu ˈɛɜt̪ bˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_12 / nghe_ngay / string

```json
{"text": "Dùng GPS.", "expected": ["Dùng gi pi ét.", "Dùng gi pê ét."], "got": "Dùng <en>G P S</en>.", "got_phonemes": "zˈu2ŋ dʒˈiː pˈiː ˈɛs.", "expected_phonemes": ["zˈu2ŋ zˈi pˈi ˈɛɜt̪.", "zˈu2ŋ zˈi pˈe ˈɛɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_12 / nghe_ngay / post_g2p

```json
{"text": "Dùng GPS.", "expected": ["Dùng gi pi ét.", "Dùng gi pê ét."], "got": "Dùng <en>G P S</en>.", "got_phonemes": "zˈu2ŋ dʒˈiː pˈiː ˈɛs.", "expected_phonemes": ["zˈu2ŋ zˈi pˈi ˈɛɜt̪.", "zˈu2ŋ zˈi pˈe ˈɛɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_12 / studio / string

```json
{"text": "Dùng GPS.", "expected": ["Dùng gi pi ét.", "Dùng gi pê ét."], "got": "Dùng <en>G P S</en>.", "got_phonemes": "zˈu2ŋ dʒˈiː pˈiː ˈɛs.", "expected_phonemes": ["zˈu2ŋ zˈi pˈi ˈɛɜt̪.", "zˈu2ŋ zˈi pˈe ˈɛɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_12 / studio / post_g2p

```json
{"text": "Dùng GPS.", "expected": ["Dùng gi pi ét.", "Dùng gi pê ét."], "got": "Dùng <en>G P S</en>.", "got_phonemes": "zˈu2ŋ dʒˈiː pˈiː ˈɛs.", "expected_phonemes": ["zˈu2ŋ zˈi pˈi ˈɛɜt̪.", "zˈu2ŋ zˈi pˈe ˈɛɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_13 / nghe_ngay / string

```json
{"text": "Tăng FPS.", "expected": ["Tăng ép pi ét.", "Tăng ép pê ét."], "got": "Tăng <en>F P S</en>.", "got_phonemes": "t̪ˈaŋ ˈɛf pˈiː ˈɛs.", "expected_phonemes": ["t̪ˈaŋ ˈɛɜp pˈi ˈɛɜt̪.", "t̪ˈaŋ ˈɛɜp pˈe ˈɛɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_13 / nghe_ngay / post_g2p

```json
{"text": "Tăng FPS.", "expected": ["Tăng ép pi ét.", "Tăng ép pê ét."], "got": "Tăng <en>F P S</en>.", "got_phonemes": "t̪ˈaŋ ˈɛf pˈiː ˈɛs.", "expected_phonemes": ["t̪ˈaŋ ˈɛɜp pˈi ˈɛɜt̪.", "t̪ˈaŋ ˈɛɜp pˈe ˈɛɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_13 / studio / string

```json
{"text": "Tăng FPS.", "expected": ["Tăng ép pi ét.", "Tăng ép pê ét."], "got": "Tăng <en>F P S</en>.", "got_phonemes": "t̪ˈaŋ ˈɛf pˈiː ˈɛs.", "expected_phonemes": ["t̪ˈaŋ ˈɛɜp pˈi ˈɛɜt̪.", "t̪ˈaŋ ˈɛɜp pˈe ˈɛɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_13 / studio / post_g2p

```json
{"text": "Tăng FPS.", "expected": ["Tăng ép pi ét.", "Tăng ép pê ét."], "got": "Tăng <en>F P S</en>.", "got_phonemes": "t̪ˈaŋ ˈɛf pˈiː ˈɛs.", "expected_phonemes": ["t̪ˈaŋ ˈɛɜp pˈi ˈɛɜt̪.", "t̪ˈaŋ ˈɛɜp pˈe ˈɛɜt̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_14 / nghe_ngay / string

```json
{"text": "Chơi RPG.", "expected": ["Chơi a pi gi.", "Chơi rờ pê gi."], "got": "Chơi <en>R P G</en>.", "got_phonemes": "tʃˈəːj ˈɑːɹ pˈiː dʒˈiː.", "expected_phonemes": ["tʃˈəːj ˈaː pˈi zˈi.", "tʃˈəːj ɹˈəː2 pˈe zˈi."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_14 / nghe_ngay / post_g2p

```json
{"text": "Chơi RPG.", "expected": ["Chơi a pi gi.", "Chơi rờ pê gi."], "got": "Chơi <en>R P G</en>.", "got_phonemes": "tʃˈəːj ˈɑːɹ pˈiː dʒˈiː.", "expected_phonemes": ["tʃˈəːj ˈaː pˈi zˈi.", "tʃˈəːj ɹˈəː2 pˈe zˈi."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_14 / studio / string

```json
{"text": "Chơi RPG.", "expected": ["Chơi a pi gi.", "Chơi rờ pê gi."], "got": "Chơi <en>R P G</en>.", "got_phonemes": "tʃˈəːj ˈɑːɹ pˈiː dʒˈiː.", "expected_phonemes": ["tʃˈəːj ˈaː pˈi zˈi.", "tʃˈəːj ɹˈəː2 pˈe zˈi."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_14 / studio / post_g2p

```json
{"text": "Chơi RPG.", "expected": ["Chơi a pi gi.", "Chơi rờ pê gi."], "got": "Chơi <en>R P G</en>.", "got_phonemes": "tʃˈəːj ˈɑːɹ pˈiː dʒˈiː.", "expected_phonemes": ["tʃˈəːj ˈaː pˈi zˈi.", "tʃˈəːj ɹˈəː2 pˈe zˈi."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_15 / nghe_ngay / string

```json
{"text": "Tăng EXP.", "expected": ["Tăng i éc pi.", "Tăng e ích pê.", "Tăng kinh nghiệm."], "got": "Tăng <en>E X P</en>.", "got_phonemes": "t̪ˈaŋ ˈiː ˈɛks pˈiː.", "expected_phonemes": ["t̪ˈaŋ ˈi ˈɛɜc pˈi.", "t̪ˈaŋ ˈɛ ˈiɜc pˈe.", "t̪ˈaŋ kˈiɲ ŋˈiɛ6m."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_15 / nghe_ngay / post_g2p

```json
{"text": "Tăng EXP.", "expected": ["Tăng i éc pi.", "Tăng e ích pê.", "Tăng kinh nghiệm."], "got": "Tăng <en>E X P</en>.", "got_phonemes": "t̪ˈaŋ ˈiː ˈɛks pˈiː.", "expected_phonemes": ["t̪ˈaŋ ˈi ˈɛɜc pˈi.", "t̪ˈaŋ ˈɛ ˈiɜc pˈe.", "t̪ˈaŋ kˈiɲ ŋˈiɛ6m."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_15 / studio / string

```json
{"text": "Tăng EXP.", "expected": ["Tăng i éc pi.", "Tăng e ích pê.", "Tăng kinh nghiệm."], "got": "Tăng <en>E X P</en>.", "got_phonemes": "t̪ˈaŋ ˈiː ˈɛks pˈiː.", "expected_phonemes": ["t̪ˈaŋ ˈi ˈɛɜc pˈi.", "t̪ˈaŋ ˈɛ ˈiɜc pˈe.", "t̪ˈaŋ kˈiɲ ŋˈiɛ6m."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_15 / studio / post_g2p

```json
{"text": "Tăng EXP.", "expected": ["Tăng i éc pi.", "Tăng e ích pê.", "Tăng kinh nghiệm."], "got": "Tăng <en>E X P</en>.", "got_phonemes": "t̪ˈaŋ ˈiː ˈɛks pˈiː.", "expected_phonemes": ["t̪ˈaŋ ˈi ˈɛɜc pˈi.", "t̪ˈaŋ ˈɛ ˈiɜc pˈe.", "t̪ˈaŋ kˈiɲ ŋˈiɛ6m."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_16 / nghe_ngay / string

```json
{"text": "Đọc FAQ.", "expected": ["Đọc ép ây kiu.", "Đọc câu hỏi thường gặp."], "got": "Đọc <en>F A Q</en>.", "got_phonemes": "ɗˈɔ6k ˈɛf ˈeɪ kjˈuː.", "expected_phonemes": ["ɗˈɔ6k ˈɛɜp ˈəɪ kˈiw.", "ɗˈɔ6k kˈə1w hˈɔ4j tˈyə2ŋ ɣˈa6p."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_16 / nghe_ngay / post_g2p

```json
{"text": "Đọc FAQ.", "expected": ["Đọc ép ây kiu.", "Đọc câu hỏi thường gặp."], "got": "Đọc <en>F A Q</en>.", "got_phonemes": "ɗˈɔ6k ˈɛf ˈeɪ kjˈuː.", "expected_phonemes": ["ɗˈɔ6k ˈɛɜp ˈəɪ kˈiw.", "ɗˈɔ6k kˈə1w hˈɔ4j tˈyə2ŋ ɣˈa6p."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_16 / studio / string

```json
{"text": "Đọc FAQ.", "expected": ["Đọc ép ây kiu.", "Đọc câu hỏi thường gặp."], "got": "Đọc <en>F A Q</en>.", "got_phonemes": "ɗˈɔ6k ˈɛf ˈeɪ kjˈuː.", "expected_phonemes": ["ɗˈɔ6k ˈɛɜp ˈəɪ kˈiw.", "ɗˈɔ6k kˈə1w hˈɔ4j tˈyə2ŋ ɣˈa6p."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_16 / studio / post_g2p

```json
{"text": "Đọc FAQ.", "expected": ["Đọc ép ây kiu.", "Đọc câu hỏi thường gặp."], "got": "Đọc <en>F A Q</en>.", "got_phonemes": "ɗˈɔ6k ˈɛf ˈeɪ kjˈuː.", "expected_phonemes": ["ɗˈɔ6k ˈɛɜp ˈəɪ kˈiw.", "ɗˈɔ6k kˈə1w hˈɔ4j tˈyə2ŋ ɣˈa6p."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_18 / nghe_ngay / string

```json
{"text": "Nghe DJ.", "expected": ["Nghe đi giây.", "Nghe đê giây."], "got": "Nghe <en>D J</en>.", "got_phonemes": "ŋˈɛ dˈiː dʒˈeɪ.", "expected_phonemes": ["ŋˈɛ ɗˈi zˈəɪ.", "ŋˈɛ ɗˈe zˈəɪ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_18 / nghe_ngay / post_g2p

```json
{"text": "Nghe DJ.", "expected": ["Nghe đi giây.", "Nghe đê giây."], "got": "Nghe <en>D J</en>.", "got_phonemes": "ŋˈɛ dˈiː dʒˈeɪ.", "expected_phonemes": ["ŋˈɛ ɗˈi zˈəɪ.", "ŋˈɛ ɗˈe zˈəɪ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_18 / studio / string

```json
{"text": "Nghe DJ.", "expected": ["Nghe đi giây.", "Nghe đê giây."], "got": "Nghe <en>D J</en>.", "got_phonemes": "ŋˈɛ dˈiː dʒˈeɪ.", "expected_phonemes": ["ŋˈɛ ɗˈi zˈəɪ.", "ŋˈɛ ɗˈe zˈəɪ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_18 / studio / post_g2p

```json
{"text": "Nghe DJ.", "expected": ["Nghe đi giây.", "Nghe đê giây."], "got": "Nghe <en>D J</en>.", "got_phonemes": "ŋˈɛ dˈiː dʒˈeɪ.", "expected_phonemes": ["ŋˈɛ ɗˈi zˈəɪ.", "ŋˈɛ ɗˈe zˈəɪ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_19 / nghe_ngay / string

```json
{"text": "Bật AC.", "expected": ["Bật ây xi.", "Bật a xê."], "got": "Bật AC.", "got_phonemes": "bˈə6t̪ ˈaːɜc.", "expected_phonemes": ["bˈə6t̪ ˈəɪ sˈi.", "bˈə6t̪ ˈaː sˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_19 / nghe_ngay / post_g2p

```json
{"text": "Bật AC.", "expected": ["Bật ây xi.", "Bật a xê."], "got": "Bật AC.", "got_phonemes": "bˈə6t̪ ˈaːɜc.", "expected_phonemes": ["bˈə6t̪ ˈəɪ sˈi.", "bˈə6t̪ ˈaː sˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_19 / studio / string

```json
{"text": "Bật AC.", "expected": ["Bật ây xi.", "Bật a xê."], "got": "Bật AC.", "got_phonemes": "bˈə6t̪ ˈaːɜc.", "expected_phonemes": ["bˈə6t̪ ˈəɪ sˈi.", "bˈə6t̪ ˈaː sˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_19 / studio / post_g2p

```json
{"text": "Bật AC.", "expected": ["Bật ây xi.", "Bật a xê."], "got": "Bật AC.", "got_phonemes": "bˈə6t̪ ˈaːɜc.", "expected_phonemes": ["bˈə6t̪ ˈəɪ sˈi.", "bˈə6t̪ ˈaː sˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### japanese_04 / nghe_ngay / string

```json
{"text": "Yuki-sama xếp khay.", "expected": ["Yu-ki-xa-ma xếp khay.", "Yư-ki-xa-ma xếp khay."], "got": "Giu-ki-xa-ma xếp khay.", "got_phonemes": "zˈu kˈi sˈaː mˈaː sˈeɜp xˈaj.", "expected_phonemes": ["jˈuː kˈi sˈaː mˈaː sˈeɜp xˈaj.", "ˈiˈy kˈi sˈaː mˈaː sˈeɜp xˈaj."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_04 / nghe_ngay / post_g2p

```json
{"text": "Yuki-sama xếp khay.", "expected": ["Yu-ki-xa-ma xếp khay.", "Yư-ki-xa-ma xếp khay."], "got": "Giu-ki-xa-ma xếp khay.", "got_phonemes": "zˈu kˈi sˈaː mˈaː sˈeɜp xˈaj.", "expected_phonemes": ["jˈuː kˈi sˈaː mˈaː sˈeɜp xˈaj.", "ˈiˈy kˈi sˈaː mˈaː sˈeɜp xˈaj."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_04 / studio / string

```json
{"text": "Yuki-sama xếp khay.", "expected": ["Yu-ki-xa-ma xếp khay.", "Yư-ki-xa-ma xếp khay."], "got": "Giu-ki-xa-ma xếp khay.", "got_phonemes": "zˈu kˈi sˈaː mˈaː sˈeɜp xˈaj.", "expected_phonemes": ["jˈuː kˈi sˈaː mˈaː sˈeɜp xˈaj.", "ˈiˈy kˈi sˈaː mˈaː sˈeɜp xˈaj."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_04 / studio / post_g2p

```json
{"text": "Yuki-sama xếp khay.", "expected": ["Yu-ki-xa-ma xếp khay.", "Yư-ki-xa-ma xếp khay."], "got": "Giu-ki-xa-ma xếp khay.", "got_phonemes": "zˈu kˈi sˈaː mˈaː sˈeɜp xˈaj.", "expected_phonemes": ["jˈuː kˈi sˈaː mˈaː sˈeɜp xˈaj.", "ˈiˈy kˈi sˈaː mˈaː sˈeɜp xˈaj."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_12 / nghe_ngay / string

```json
{"text": "Sensei xem phiếu.", "expected": ["Xen-xê xem phiếu.", "Sen-sê xem phiếu."], "got": "xen-xây xem phiếu.", "got_phonemes": "sˈɛn sˈəɪ sˈɛm fˈiɛɜw.", "expected_phonemes": ["sˈɛn sˈe sˈɛm fˈiɛɜw.", "sˈɛn sˈe sˈɛm fˈiɛɜw."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_12 / nghe_ngay / post_g2p

```json
{"text": "Sensei xem phiếu.", "expected": ["Xen-xê xem phiếu.", "Sen-sê xem phiếu."], "got": "xen-xây xem phiếu.", "got_phonemes": "sˈɛn sˈəɪ sˈɛm fˈiɛɜw.", "expected_phonemes": ["sˈɛn sˈe sˈɛm fˈiɛɜw.", "sˈɛn sˈe sˈɛm fˈiɛɜw."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_12 / studio / string

```json
{"text": "Sensei xem phiếu.", "expected": ["Xen-xê xem phiếu.", "Sen-sê xem phiếu."], "got": "xen-xây xem phiếu.", "got_phonemes": "sˈɛn sˈəɪ sˈɛm fˈiɛɜw.", "expected_phonemes": ["sˈɛn sˈe sˈɛm fˈiɛɜw.", "sˈɛn sˈe sˈɛm fˈiɛɜw."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_12 / studio / post_g2p

```json
{"text": "Sensei xem phiếu.", "expected": ["Xen-xê xem phiếu.", "Sen-sê xem phiếu."], "got": "xen-xây xem phiếu.", "got_phonemes": "sˈɛn sˈəɪ sˈɛm fˈiɛɜw.", "expected_phonemes": ["sˈɛn sˈe sˈɛm fˈiɛɜw.", "sˈɛn sˈe sˈɛm fˈiɛɜw."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_13 / nghe_ngay / string

```json
{"text": "Kouhai xem phiếu.", "expected": ["Cô-hai xem phiếu.", "Kô-hai xem phiếu."], "got": "Câu-hai xem phiếu.", "got_phonemes": "kˈə1w hˈaːj sˈɛm fˈiɛɜw.", "expected_phonemes": ["kˈo hˈaːj sˈɛm fˈiɛɜw.", "kˈaːˈo hˈaːj sˈɛm fˈiɛɜw."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_13 / nghe_ngay / post_g2p

```json
{"text": "Kouhai xem phiếu.", "expected": ["Cô-hai xem phiếu.", "Kô-hai xem phiếu."], "got": "Câu-hai xem phiếu.", "got_phonemes": "kˈə1w hˈaːj sˈɛm fˈiɛɜw.", "expected_phonemes": ["kˈo hˈaːj sˈɛm fˈiɛɜw.", "kˈaːˈo hˈaːj sˈɛm fˈiɛɜw."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_13 / studio / string

```json
{"text": "Kouhai xem phiếu.", "expected": ["Cô-hai xem phiếu.", "Kô-hai xem phiếu."], "got": "Câu-hai xem phiếu.", "got_phonemes": "kˈə1w hˈaːj sˈɛm fˈiɛɜw.", "expected_phonemes": ["kˈo hˈaːj sˈɛm fˈiɛɜw.", "kˈaːˈo hˈaːj sˈɛm fˈiɛɜw."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_13 / studio / post_g2p

```json
{"text": "Kouhai xem phiếu.", "expected": ["Cô-hai xem phiếu.", "Kô-hai xem phiếu."], "got": "Câu-hai xem phiếu.", "got_phonemes": "kˈə1w hˈaːj sˈɛm fˈiɛɜw.", "expected_phonemes": ["kˈo hˈaːj sˈɛm fˈiɛɜw.", "kˈaːˈo hˈaːj sˈɛm fˈiɛɜw."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_14 / nghe_ngay / string

```json
{"text": "Arigatou, xin nhận.", "expected": ["A-ri-ga-tô, xin nhận.", "A-ri-ga-tou, xin nhận."], "got": "a-ri-ga-tâu, xin nhận.", "got_phonemes": "ˈaː ɹˈi ɣˈaː t̪ˈə1w, sˈin ɲˈə6n.", "expected_phonemes": ["ˈaː ɹˈi ɣˈaː t̪ˈo, sˈin ɲˈə6n.", "ˈaː ɹˈi ɣˈaː tˈuː, sˈin ɲˈə6n."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_14 / nghe_ngay / post_g2p

```json
{"text": "Arigatou, xin nhận.", "expected": ["A-ri-ga-tô, xin nhận.", "A-ri-ga-tou, xin nhận."], "got": "a-ri-ga-tâu, xin nhận.", "got_phonemes": "ˈaː ɹˈi ɣˈaː t̪ˈə1w, sˈin ɲˈə6n.", "expected_phonemes": ["ˈaː ɹˈi ɣˈaː t̪ˈo, sˈin ɲˈə6n.", "ˈaː ɹˈi ɣˈaː tˈuː, sˈin ɲˈə6n."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_14 / studio / string

```json
{"text": "Arigatou, xin nhận.", "expected": ["A-ri-ga-tô, xin nhận.", "A-ri-ga-tou, xin nhận."], "got": "a-ri-ga-tâu, xin nhận.", "got_phonemes": "ˈaː ɹˈi ɣˈaː t̪ˈə1w, sˈin ɲˈə6n.", "expected_phonemes": ["ˈaː ɹˈi ɣˈaː t̪ˈo, sˈin ɲˈə6n.", "ˈaː ɹˈi ɣˈaː tˈuː, sˈin ɲˈə6n."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_14 / studio / post_g2p

```json
{"text": "Arigatou, xin nhận.", "expected": ["A-ri-ga-tô, xin nhận.", "A-ri-ga-tou, xin nhận."], "got": "a-ri-ga-tâu, xin nhận.", "got_phonemes": "ˈaː ɹˈi ɣˈaː t̪ˈə1w, sˈin ɲˈə6n.", "expected_phonemes": ["ˈaː ɹˈi ɣˈaː t̪ˈo, sˈin ɲˈə6n.", "ˈaː ɹˈi ɣˈaː tˈuː, sˈin ɲˈə6n."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_15 / nghe_ngay / string

```json
{"text": "Ohayou, mời vào.", "expected": ["Ô-ha-yô, mời vào.", "O-ha-yo, mời vào."], "got": "ô-ha-giâu, mời vào.", "got_phonemes": "ˈo hˈaː zˈə1w, mˈəː2j vˈaː2w.", "expected_phonemes": ["ˈo hˈaː ˈiˈo, mˈəː2j vˈaː2w.", "ˈo hˈaː jˈoʊ, mˈəː2j vˈaː2w."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_15 / nghe_ngay / post_g2p

```json
{"text": "Ohayou, mời vào.", "expected": ["Ô-ha-yô, mời vào.", "O-ha-yo, mời vào."], "got": "ô-ha-giâu, mời vào.", "got_phonemes": "ˈo hˈaː zˈə1w, mˈəː2j vˈaː2w.", "expected_phonemes": ["ˈo hˈaː ˈiˈo, mˈəː2j vˈaː2w.", "ˈo hˈaː jˈoʊ, mˈəː2j vˈaː2w."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_15 / studio / string

```json
{"text": "Ohayou, mời vào.", "expected": ["Ô-ha-yô, mời vào.", "O-ha-yo, mời vào."], "got": "ô-ha-giâu, mời vào.", "got_phonemes": "ˈo hˈaː zˈə1w, mˈəː2j vˈaː2w.", "expected_phonemes": ["ˈo hˈaː ˈiˈo, mˈəː2j vˈaː2w.", "ˈo hˈaː jˈoʊ, mˈəː2j vˈaː2w."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_15 / studio / post_g2p

```json
{"text": "Ohayou, mời vào.", "expected": ["Ô-ha-yô, mời vào.", "O-ha-yo, mời vào."], "got": "ô-ha-giâu, mời vào.", "got_phonemes": "ˈo hˈaː zˈə1w, mˈəː2j vˈaː2w.", "expected_phonemes": ["ˈo hˈaː ˈiˈo, mˈəː2j vˈaː2w.", "ˈo hˈaː jˈoʊ, mˈəː2j vˈaː2w."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_20 / nghe_ngay / string

```json
{"text": "Onee-chan đến.", "expected": ["Ô-nê-chan đến.", "O-nê-chan đến."], "got": "ô-ne-chan đến.", "got_phonemes": "ˈo nˈɛ tʃˈaːn ɗˌeɜn.", "expected_phonemes": ["ˈo nˈe tʃˈaːn ɗˌeɜn.", "ˈo nˈe tʃˈaːn ɗˌeɜn."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_20 / nghe_ngay / post_g2p

```json
{"text": "Onee-chan đến.", "expected": ["Ô-nê-chan đến.", "O-nê-chan đến."], "got": "ô-ne-chan đến.", "got_phonemes": "ˈo nˈɛ tʃˈaːn ɗˌeɜn.", "expected_phonemes": ["ˈo nˈe tʃˈaːn ɗˌeɜn.", "ˈo nˈe tʃˈaːn ɗˌeɜn."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_20 / studio / string

```json
{"text": "Onee-chan đến.", "expected": ["Ô-nê-chan đến.", "O-nê-chan đến."], "got": "ô-ne-chan đến.", "got_phonemes": "ˈo nˈɛ tʃˈaːn ɗˌeɜn.", "expected_phonemes": ["ˈo nˈe tʃˈaːn ɗˌeɜn.", "ˈo nˈe tʃˈaːn ɗˌeɜn."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_20 / studio / post_g2p

```json
{"text": "Onee-chan đến.", "expected": ["Ô-nê-chan đến.", "O-nê-chan đến."], "got": "ô-ne-chan đến.", "got_phonemes": "ˈo nˈɛ tʃˈaːn ɗˌeɜn.", "expected_phonemes": ["ˈo nˈe tʃˈaːn ɗˌeɜn.", "ˈo nˈe tʃˈaːn ɗˌeɜn."], "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### symbol_03 / nghe_ngay / string

```json
{"text": "Mã #5.", "expected": ["Mã thăng năm.", "Mã số năm."], "got": "Mã số 5.", "got_phonemes": "mˈaː5 sˈoɜ nˈam.", "expected_phonemes": ["mˈaː5 tˈaŋ nˈam.", "mˈaː5 sˈoɜ nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_03 / studio / string

```json
{"text": "Mã #5.", "expected": ["Mã thăng năm.", "Mã số năm."], "got": "Mã số 5.", "got_phonemes": "mˈaː5 sˈoɜ nˈam.", "expected_phonemes": ["mˈaː5 tˈaŋ nˈam.", "mˈaː5 sˈoɜ nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_04 / nghe_ngay / string

```json
{"text": "Ký hiệu %.", "expected": "Ký hiệu phần trăm.", "got": "Ký hiệu %.", "got_phonemes": "kˈiɜ hˈiɛ6w fˈə2n tʃˈam.", "expected_phonemes": ["kˈiɜ hˈiɛ6w fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_04 / studio / string

```json
{"text": "Ký hiệu %.", "expected": "Ký hiệu phần trăm.", "got": "Ký hiệu %.", "got_phonemes": "kˈiɜ hˈiɛ6w fˈə2n tʃˈam.", "expected_phonemes": ["kˈiɜ hˈiɛ6w fˈə2n tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_05 / nghe_ngay / string

```json
{"text": "Tính 2 + 3.", "expected": "Tính hai cộng ba.", "got": "Tính 2 + 3.", "got_phonemes": "t̪ˈiɜɲ hˈaːj kˈo6ŋ bˈaː.", "expected_phonemes": ["t̪ˈiɜɲ hˈaːj kˈo6ŋ bˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_06 / nghe_ngay / string

```json
{"text": "Tính 2 = 2.", "expected": "Tính hai bằng hai.", "got": "Tính 2 bằng 2.", "got_phonemes": "t̪ˈiɜɲ hˈaːj bˈa2ŋ hˈaːj.", "expected_phonemes": ["t̪ˈiɜɲ hˈaːj bˈa2ŋ hˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_07 / nghe_ngay / string

```json
{"text": "Trà / cà phê.", "expected": ["Trà hoặc cà phê.", "Trà trên cà phê."], "got": "Trà, cà phê.", "got_phonemes": "tʃˈaː2, kˈaː2 fˈe.", "expected_phonemes": ["tʃˈaː2 hwˌa6c kˈaː2 fˈe.", "tʃˈaː2 tʃˈen kˈaː2 fˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_07 / nghe_ngay / post_g2p

```json
{"text": "Trà / cà phê.", "expected": ["Trà hoặc cà phê.", "Trà trên cà phê."], "got": "Trà, cà phê.", "got_phonemes": "tʃˈaː2, kˈaː2 fˈe.", "expected_phonemes": ["tʃˈaː2 hwˌa6c kˈaː2 fˈe.", "tʃˈaː2 tʃˈen kˈaː2 fˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_07 / studio / string

```json
{"text": "Trà / cà phê.", "expected": ["Trà hoặc cà phê.", "Trà trên cà phê."], "got": "Trà, cà phê.", "got_phonemes": "tʃˈaː2, kˈaː2 fˈe.", "expected_phonemes": ["tʃˈaː2 hwˌa6c kˈaː2 fˈe.", "tʃˈaː2 tʃˈen kˈaː2 fˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_07 / studio / post_g2p

```json
{"text": "Trà / cà phê.", "expected": ["Trà hoặc cà phê.", "Trà trên cà phê."], "got": "Trà, cà phê.", "got_phonemes": "tʃˈaː2, kˈaː2 fˈe.", "expected_phonemes": ["tʃˈaː2 hwˌa6c kˈaː2 fˈe.", "tʃˈaː2 tʃˈen kˈaː2 fˈe."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_08 / nghe_ngay / string

```json
{"text": "Tính 3 × 4.", "expected": "Tính ba nhân bốn.", "got": "Tính 3 nhân 4.", "got_phonemes": "t̪ˈiɜɲ bˈaː ɲˈən bˈoɜn.", "expected_phonemes": ["t̪ˈiɜɲ bˈaː ɲˈən bˈoɜn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_09 / nghe_ngay / string

```json
{"text": "Khay → hộp.", "expected": ["Khay sang hộp.", "Khay đến hộp.", "Khay chuyển thành hộp."], "got": "Khay thành hộp.", "got_phonemes": "xˈaj tˈe-2ɲ hˈo6p.", "expected_phonemes": ["xˈaj sˈaːŋ hˈo6p.", "xˈaj ɗˌeɜn hˈo6p.", "xˈaj tʃwˈiɛ4n tˈe-2ɲ hˈo6p."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_09 / nghe_ngay / post_g2p

```json
{"text": "Khay → hộp.", "expected": ["Khay sang hộp.", "Khay đến hộp.", "Khay chuyển thành hộp."], "got": "Khay thành hộp.", "got_phonemes": "xˈaj tˈe-2ɲ hˈo6p.", "expected_phonemes": ["xˈaj sˈaːŋ hˈo6p.", "xˈaj ɗˌeɜn hˈo6p.", "xˈaj tʃwˈiɛ4n tˈe-2ɲ hˈo6p."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_09 / studio / string

```json
{"text": "Khay → hộp.", "expected": ["Khay sang hộp.", "Khay đến hộp.", "Khay chuyển thành hộp."], "got": "Khay, hộp.", "got_phonemes": "xˈaj, hˈo6p.", "expected_phonemes": ["xˈaj sˈaːŋ hˈo6p.", "xˈaj ɗˌeɜn hˈo6p.", "xˈaj tʃwˈiɛ4n tˈe-2ɲ hˈo6p."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_09 / studio / post_g2p

```json
{"text": "Khay → hộp.", "expected": ["Khay sang hộp.", "Khay đến hộp.", "Khay chuyển thành hộp."], "got": "Khay, hộp.", "got_phonemes": "xˈaj, hˈo6p.", "expected_phonemes": ["xˈaj sˈaːŋ hˈo6p.", "xˈaj ɗˌeɜn hˈo6p.", "xˈaj tʃwˈiɛ4n tˈe-2ɲ hˈo6p."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_10 / nghe_ngay / string

```json
{"text": "Xếp hạng ★★★.", "expected": ["Xếp hạng ba sao.", "Xếp hạng sao sao sao."], "got": "Xếp hạng .", "got_phonemes": "sˈeɜp hˈaː6ŋ.", "expected_phonemes": ["sˈeɜp hˈaː6ŋ bˈaː sˈaːw.", "sˈeɜp hˈaː6ŋ sˈaːw sˈaːw sˈaːw."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_10 / nghe_ngay / post_g2p

```json
{"text": "Xếp hạng ★★★.", "expected": ["Xếp hạng ba sao.", "Xếp hạng sao sao sao."], "got": "Xếp hạng .", "got_phonemes": "sˈeɜp hˈaː6ŋ.", "expected_phonemes": ["sˈeɜp hˈaː6ŋ bˈaː sˈaːw.", "sˈeɜp hˈaː6ŋ sˈaːw sˈaːw sˈaːw."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_10 / studio / string

```json
{"text": "Xếp hạng ★★★.", "expected": ["Xếp hạng ba sao.", "Xếp hạng sao sao sao."], "got": "Xếp hạng .", "got_phonemes": "sˈeɜp hˈaː6ŋ.", "expected_phonemes": ["sˈeɜp hˈaː6ŋ bˈaː sˈaːw.", "sˈeɜp hˈaː6ŋ sˈaːw sˈaːw sˈaːw."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_10 / studio / post_g2p

```json
{"text": "Xếp hạng ★★★.", "expected": ["Xếp hạng ba sao.", "Xếp hạng sao sao sao."], "got": "Xếp hạng .", "got_phonemes": "sˈeɜp hˈaː6ŋ.", "expected_phonemes": ["sˈeɜp hˈaː6ŋ bˈaː sˈaːw.", "sˈeɜp hˈaː6ŋ sˈaːw sˈaːw sˈaːw."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_11 / nghe_ngay / string

```json
{"text": "La ♪ la.", "expected": ["La la.", "La, la."], "got": "La ♪ la.", "got_phonemes": "lˈaː lˈaː.", "expected_phonemes": ["lˈaː lˈaː.", "lˈaː, lˈaː."], "note": "Nốt nhạc chỉ ngữ điệu, không thêm lời."}
```

### symbol_11 / studio / string

```json
{"text": "La ♪ la.", "expected": ["La la.", "La, la."], "got": "La ♪ la.", "got_phonemes": "lˈaː lˈaː.", "expected_phonemes": ["lˈaː lˈaː.", "lˈaː, lˈaː."], "note": "Nốt nhạc chỉ ngữ điệu, không thêm lời."}
```

### symbol_12 / nghe_ngay / string

```json
{"text": "Tính 5 − 2.", "expected": "Tính năm trừ hai.", "got": "Tính năm − hai.", "got_phonemes": "t̪ˈiɜɲ nˈam hˈaːj.", "expected_phonemes": ["t̪ˈiɜɲ nˈam tʃˈy2 hˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_12 / nghe_ngay / post_g2p

```json
{"text": "Tính 5 − 2.", "expected": "Tính năm trừ hai.", "got": "Tính năm − hai.", "got_phonemes": "t̪ˈiɜɲ nˈam hˈaːj.", "expected_phonemes": ["t̪ˈiɜɲ nˈam tʃˈy2 hˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_12 / studio / string

```json
{"text": "Tính 5 − 2.", "expected": "Tính năm trừ hai.", "got": "Tính năm − hai.", "got_phonemes": "t̪ˈiɜɲ nˈam hˈaːj.", "expected_phonemes": ["t̪ˈiɜɲ nˈam tʃˈy2 hˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_12 / studio / post_g2p

```json
{"text": "Tính 5 − 2.", "expected": "Tính năm trừ hai.", "got": "Tính năm − hai.", "got_phonemes": "t̪ˈiɜɲ nˈam hˈaːj.", "expected_phonemes": ["t̪ˈiɜɲ nˈam tʃˈy2 hˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_13 / nghe_ngay / string

```json
{"text": "Tính 6 ÷ 3.", "expected": "Tính sáu chia ba.", "got": "Tính 6 ÷ 3.", "got_phonemes": "t̪ˈiɜɲ sˈaɜw tʃˈiə bˈaː.", "expected_phonemes": ["t̪ˈiɜɲ sˈaɜw tʃˈiə bˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_14 / nghe_ngay / string

```json
{"text": "Điểm ≥ 5.", "expected": "Điểm lớn hơn hoặc bằng năm.", "got": "Điểm ≥ 5.", "got_phonemes": "ɗˈiɛ4m lˈəːɜn hˈəːn hwˌa6c bˈa2ŋ nˈam.", "expected_phonemes": ["ɗˈiɛ4m lˈəːɜn hˈəːn hwˌa6c bˈa2ŋ nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_15 / nghe_ngay / string

```json
{"text": "Điểm ≤ 8.", "expected": "Điểm nhỏ hơn hoặc bằng tám.", "got": "Điểm ≤ 8.", "got_phonemes": "ɗˈiɛ4m ɲˈɔ4 hˈəːn hwˌa6c bˈa2ŋ t̪ˈaːɜm.", "expected_phonemes": ["ɗˈiɛ4m ɲˈɔ4 hˈəːn hwˌa6c bˈa2ŋ t̪ˈaːɜm."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_16 / nghe_ngay / string

```json
{"text": "Điểm ≠ 0.", "expected": "Điểm khác không.", "got": "Điểm không phải là 0.", "got_phonemes": "ɗˈiɛ4m xˌoŋ fˌaː4j lˌaː2 xˌoŋ.", "expected_phonemes": ["ɗˈiɛ4m xˈaːɜc xˌoŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_16 / nghe_ngay / post_g2p

```json
{"text": "Điểm ≠ 0.", "expected": "Điểm khác không.", "got": "Điểm không phải là 0.", "got_phonemes": "ɗˈiɛ4m xˌoŋ fˌaː4j lˌaː2 xˌoŋ.", "expected_phonemes": ["ɗˈiɛ4m xˈaːɜc xˌoŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_16 / studio / string

```json
{"text": "Điểm ≠ 0.", "expected": "Điểm khác không.", "got": "Điểm không phải là 0.", "got_phonemes": "ɗˈiɛ4m xˌoŋ fˌaː4j lˌaː2 xˌoŋ.", "expected_phonemes": ["ɗˈiɛ4m xˈaːɜc xˌoŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_16 / studio / post_g2p

```json
{"text": "Điểm ≠ 0.", "expected": "Điểm khác không.", "got": "Điểm không phải là 0.", "got_phonemes": "ɗˈiɛ4m xˌoŋ fˌaː4j lˌaː2 xˌoŋ.", "expected_phonemes": ["ɗˈiɛ4m xˈaːɜc xˌoŋ."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_17 / nghe_ngay / string

```json
{"text": "Mức ±2.", "expected": "Mức cộng trừ hai.", "got": "Mức ±2.", "got_phonemes": "mˈyɜc kˈo6ŋ tʃˈy2 hˈaːj.", "expected_phonemes": ["mˈyɜc kˈo6ŋ tʃˈy2 hˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_17 / studio / string

```json
{"text": "Mức ±2.", "expected": "Mức cộng trừ hai.", "got": "Mức ±2.", "got_phonemes": "mˈyɜc kˈo6ŋ tʃˈy2 hˈaːj.", "expected_phonemes": ["mˈyɜc kˈo6ŋ tʃˈy2 hˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_18 / nghe_ngay / string

```json
{"text": "Ký hiệu ©.", "expected": "Ký hiệu bản quyền.", "got": "Ký hiệu ©.", "got_phonemes": "kˈiɜ hˈiɛ6w bˈaː4n kwˈiɛ2n.", "expected_phonemes": ["kˈiɜ hˈiɛ6w bˈaː4n kwˈiɛ2n."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_18 / studio / string

```json
{"text": "Ký hiệu ©.", "expected": "Ký hiệu bản quyền.", "got": "Ký hiệu ©.", "got_phonemes": "kˈiɜ hˈiɛ6w bˈaː4n kwˈiɛ2n.", "expected_phonemes": ["kˈiɜ hˈiɛ6w bˈaː4n kwˈiɛ2n."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_19 / nghe_ngay / string

```json
{"text": "Tính 2:1.", "expected": ["Tính hai chia một.", "Tính hai trên một."], "got": "Tính 2:1.", "got_phonemes": "t̪ˈiɜɲ hˈaːj tʃˈen mˈo6t̪.", "expected_phonemes": ["t̪ˈiɜɲ hˈaːj tʃˈiə mˈo6t̪.", "t̪ˈiɜɲ hˈaːj tʃˈen mˈo6t̪."], "note": "Quy ước là phép tính hoặc tỉ số."}
```

### symbol_19 / studio / string

```json
{"text": "Tính 2:1.", "expected": ["Tính hai chia một.", "Tính hai trên một."], "got": "Tính 2:1.", "got_phonemes": "t̪ˈiɜɲ hˈaːj tʃˈen mˈo6t̪.", "expected_phonemes": ["t̪ˈiɜɲ hˈaːj tʃˈiə mˈo6t̪.", "t̪ˈiɜɲ hˈaːj tʃˈen mˈo6t̪."], "note": "Quy ước là phép tính hoặc tỉ số."}
```

### symbol_20 / nghe_ngay / string

```json
{"text": "Nhãn A&B.", "expected": ["Nhãn a và bê.", "Nhãn ây và bi."], "got": "Nhãn A en B.", "got_phonemes": "ɲˈaː5n ˈaː ˈɛn bˈe.", "expected_phonemes": ["ɲˈaː5n ˈaː vˌaː2 bˈe.", "ɲˈaː5n ˈəɪ vˌaː2 bˈi."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_20 / nghe_ngay / post_g2p

```json
{"text": "Nhãn A&B.", "expected": ["Nhãn a và bê.", "Nhãn ây và bi."], "got": "Nhãn A en B.", "got_phonemes": "ɲˈaː5n ˈaː ˈɛn bˈe.", "expected_phonemes": ["ɲˈaː5n ˈaː vˌaː2 bˈe.", "ɲˈaː5n ˈəɪ vˌaː2 bˈi."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_20 / studio / string

```json
{"text": "Nhãn A&B.", "expected": ["Nhãn a và bê.", "Nhãn ây và bi."], "got": "Nhãn A en B.", "got_phonemes": "ɲˈaː5n ˈaː ˈɛn bˈe.", "expected_phonemes": ["ɲˈaː5n ˈaː vˌaː2 bˈe.", "ɲˈaː5n ˈəɪ vˌaː2 bˈi."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_20 / studio / post_g2p

```json
{"text": "Nhãn A&B.", "expected": ["Nhãn a và bê.", "Nhãn ây và bi."], "got": "Nhãn A en B.", "got_phonemes": "ɲˈaː5n ˈaː ˈɛn bˈe.", "expected_phonemes": ["ɲˈaː5n ˈaː vˌaː2 bˈe.", "ɲˈaː5n ˈəɪ vˌaː2 bˈi."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### url_email_01 / nghe_ngay / string

```json
{"text": "Mở https://example.com.", "expected": ["Mở hát tê tê pê ét hai chấm gạch chéo gạch chéo example chấm com.", "Mở example chấm com."], "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 hˈaːɜt̪ t̪ˈe t̪ˈe pˈe ˈɛɜt̪ hˈaːj tʃˈəɜm ɣˈe-6c tʃˈɛɜw ɣˈe-6c tʃˈɛɜw ɛɡzˈæmpəl tʃˈəɜm kˈɔm.", "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm kˈɔm."], "note": "Cho phép bỏ giao thức khi đọc URL, tên miền giữ spelling đa ngữ."}
```

### url_email_01 / nghe_ngay / post_g2p

```json
{"text": "Mở https://example.com.", "expected": ["Mở hát tê tê pê ét hai chấm gạch chéo gạch chéo example chấm com.", "Mở example chấm com."], "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 hˈaːɜt̪ t̪ˈe t̪ˈe pˈe ˈɛɜt̪ hˈaːj tʃˈəɜm ɣˈe-6c tʃˈɛɜw ɣˈe-6c tʃˈɛɜw ɛɡzˈæmpəl tʃˈəɜm kˈɔm.", "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm kˈɔm."], "note": "Cho phép bỏ giao thức khi đọc URL, tên miền giữ spelling đa ngữ."}
```

### url_email_01 / studio / string

```json
{"text": "Mở https://example.com.", "expected": ["Mở hát tê tê pê ét hai chấm gạch chéo gạch chéo example chấm com.", "Mở example chấm com."], "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 hˈaːɜt̪ t̪ˈe t̪ˈe pˈe ˈɛɜt̪ hˈaːj tʃˈəɜm ɣˈe-6c tʃˈɛɜw ɣˈe-6c tʃˈɛɜw ɛɡzˈæmpəl tʃˈəɜm kˈɔm.", "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm kˈɔm."], "note": "Cho phép bỏ giao thức khi đọc URL, tên miền giữ spelling đa ngữ."}
```

### url_email_01 / studio / post_g2p

```json
{"text": "Mở https://example.com.", "expected": ["Mở hát tê tê pê ét hai chấm gạch chéo gạch chéo example chấm com.", "Mở example chấm com."], "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 hˈaːɜt̪ t̪ˈe t̪ˈe pˈe ˈɛɜt̪ hˈaːj tʃˈəɜm ɣˈe-6c tʃˈɛɜw ɣˈe-6c tʃˈɛɜw ɛɡzˈæmpəl tʃˈəɜm kˈɔm.", "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm kˈɔm."], "note": "Cho phép bỏ giao thức khi đọc URL, tên miền giữ spelling đa ngữ."}
```

### url_email_02 / nghe_ngay / string

```json
{"text": "Mở http://example.org.", "expected": ["Mở hát tê tê pê hai chấm gạch chéo gạch chéo example chấm org.", "Mở example chấm org."], "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 hˈaːɜt̪ t̪ˈe t̪ˈe pˈe hˈaːj tʃˈəɜm ɣˈe-6c tʃˈɛɜw ɣˈe-6c tʃˈɛɜw ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ.", "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_02 / nghe_ngay / post_g2p

```json
{"text": "Mở http://example.org.", "expected": ["Mở hát tê tê pê hai chấm gạch chéo gạch chéo example chấm org.", "Mở example chấm org."], "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 hˈaːɜt̪ t̪ˈe t̪ˈe pˈe hˈaːj tʃˈəɜm ɣˈe-6c tʃˈɛɜw ɣˈe-6c tʃˈɛɜw ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ.", "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_02 / studio / string

```json
{"text": "Mở http://example.org.", "expected": ["Mở hát tê tê pê hai chấm gạch chéo gạch chéo example chấm org.", "Mở example chấm org."], "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 hˈaːɜt̪ t̪ˈe t̪ˈe pˈe hˈaːj tʃˈəɜm ɣˈe-6c tʃˈɛɜw ɣˈe-6c tʃˈɛɜw ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ.", "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_02 / studio / post_g2p

```json
{"text": "Mở http://example.org.", "expected": ["Mở hát tê tê pê hai chấm gạch chéo gạch chéo example chấm org.", "Mở example chấm org."], "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 hˈaːɜt̪ t̪ˈe t̪ˈe pˈe hˈaːj tʃˈəɜm ɣˈe-6c tʃˈɛɜw ɣˈe-6c tʃˈɛɜw ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ.", "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_03 / nghe_ngay / string

```json
{"text": "Mở www.example.net.", "expected": ["Mở vê kép vê kép vê kép chấm example chấm net.", "Mở example chấm net."], "got": "Mở www.example.net.", "got_phonemes": "mˈəː4 vˈe kˈɛɜp vˈe kˈɛɜp vˈe kˈɛɜp tʃˈəɜm ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪.", "expected_phonemes": ["mˈəː4 vˈe kˈɛɜp vˈe kˈɛɜp vˈe kˈɛɜp tʃˈəɜm ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪.", "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_03 / studio / string

```json
{"text": "Mở www.example.net.", "expected": ["Mở vê kép vê kép vê kép chấm example chấm net.", "Mở example chấm net."], "got": "Mở www.example.net.", "got_phonemes": "mˈəː4 vˈe kˈɛɜp vˈe kˈɛɜp vˈe kˈɛɜp tʃˈəɜm ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪.", "expected_phonemes": ["mˈəː4 vˈe kˈɛɜp vˈe kˈɛɜp vˈe kˈɛɜp tʃˈəɜm ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪.", "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_04 / nghe_ngay / string

```json
{"text": "Mở example.com/a.", "expected": "Mở example chấm com gạch chéo a.", "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm kˈɔm ɣˈe-6c tʃˈɛɜw ˈaː."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_04 / nghe_ngay / post_g2p

```json
{"text": "Mở example.com/a.", "expected": "Mở example chấm com gạch chéo a.", "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm kˈɔm ɣˈe-6c tʃˈɛɜw ˈaː."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_04 / studio / string

```json
{"text": "Mở example.com/a.", "expected": "Mở example chấm com gạch chéo a.", "got": "Mở example.com, a.", "got_phonemes": "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm kˈɔm, ˈaː.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm kˈɔm ɣˈe-6c tʃˈɛɜw ˈaː."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_04 / studio / post_g2p

```json
{"text": "Mở example.com/a.", "expected": "Mở example chấm com gạch chéo a.", "got": "Mở example.com, a.", "got_phonemes": "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm kˈɔm, ˈaː.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm kˈɔm ɣˈe-6c tʃˈɛɜw ˈaː."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_05 / nghe_ngay / string

```json
{"text": "Mở example.org/b.", "expected": ["Mở example chấm org gạch chéo bê.", "Mở example chấm org gạch chéo bi."], "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ ɣˈe-6c tʃˈɛɜw bˈe.", "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ ɣˈe-6c tʃˈɛɜw bˈi."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_05 / nghe_ngay / post_g2p

```json
{"text": "Mở example.org/b.", "expected": ["Mở example chấm org gạch chéo bê.", "Mở example chấm org gạch chéo bi."], "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ ɣˈe-6c tʃˈɛɜw bˈe.", "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ ɣˈe-6c tʃˈɛɜw bˈi."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_05 / studio / string

```json
{"text": "Mở example.org/b.", "expected": ["Mở example chấm org gạch chéo bê.", "Mở example chấm org gạch chéo bi."], "got": "Mở example.org, b.", "got_phonemes": "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm ˈɔ ɹˈəː2 ɣˈəː2, bˈe.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ ɣˈe-6c tʃˈɛɜw bˈe.", "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ ɣˈe-6c tʃˈɛɜw bˈi."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_05 / studio / post_g2p

```json
{"text": "Mở example.org/b.", "expected": ["Mở example chấm org gạch chéo bê.", "Mở example chấm org gạch chéo bi."], "got": "Mở example.org, b.", "got_phonemes": "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm ˈɔ ɹˈəː2 ɣˈəː2, bˈe.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ ɣˈe-6c tʃˈɛɜw bˈe.", "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ ɣˈe-6c tʃˈɛɜw bˈi."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_06 / nghe_ngay / string

```json
{"text": "Mở https://example.net/5.", "expected": ["Mở example chấm net gạch chéo năm.", "Mở hát tê tê pê ét hai chấm gạch chéo gạch chéo example chấm net gạch chéo năm."], "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪ ɣˈe-6c tʃˈɛɜw nˈam.", "mˈəː4 hˈaːɜt̪ t̪ˈe t̪ˈe pˈe ˈɛɜt̪ hˈaːj tʃˈəɜm ɣˈe-6c tʃˈɛɜw ɣˈe-6c tʃˈɛɜw ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪ ɣˈe-6c tʃˈɛɜw nˈam."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_06 / nghe_ngay / post_g2p

```json
{"text": "Mở https://example.net/5.", "expected": ["Mở example chấm net gạch chéo năm.", "Mở hát tê tê pê ét hai chấm gạch chéo gạch chéo example chấm net gạch chéo năm."], "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪ ɣˈe-6c tʃˈɛɜw nˈam.", "mˈəː4 hˈaːɜt̪ t̪ˈe t̪ˈe pˈe ˈɛɜt̪ hˈaːj tʃˈəɜm ɣˈe-6c tʃˈɛɜw ɣˈe-6c tʃˈɛɜw ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪ ɣˈe-6c tʃˈɛɜw nˈam."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_06 / studio / string

```json
{"text": "Mở https://example.net/5.", "expected": ["Mở example chấm net gạch chéo năm.", "Mở hát tê tê pê ét hai chấm gạch chéo gạch chéo example chấm net gạch chéo năm."], "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪ ɣˈe-6c tʃˈɛɜw nˈam.", "mˈəː4 hˈaːɜt̪ t̪ˈe t̪ˈe pˈe ˈɛɜt̪ hˈaːj tʃˈəɜm ɣˈe-6c tʃˈɛɜw ɣˈe-6c tʃˈɛɜw ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪ ɣˈe-6c tʃˈɛɜw nˈam."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_06 / studio / post_g2p

```json
{"text": "Mở https://example.net/5.", "expected": ["Mở example chấm net gạch chéo năm.", "Mở hát tê tê pê ét hai chấm gạch chéo gạch chéo example chấm net gạch chéo năm."], "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪ ɣˈe-6c tʃˈɛɜw nˈam.", "mˈəː4 hˈaːɜt̪ t̪ˈe t̪ˈe pˈe ˈɛɜt̪ hˈaːj tʃˈəɜm ɣˈe-6c tʃˈɛɜw ɣˈe-6c tʃˈɛɜw ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪ ɣˈe-6c tʃˈɛɜw nˈam."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_07 / nghe_ngay / string

```json
{"text": "Mở https://example.com?q=2.", "expected": "Mở example chấm com hỏi kiu bằng hai.", "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm kˈɔm hˈɔ4j kˈiw bˈa2ŋ hˈaːj."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_07 / nghe_ngay / post_g2p

```json
{"text": "Mở https://example.com?q=2.", "expected": "Mở example chấm com hỏi kiu bằng hai.", "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm kˈɔm hˈɔ4j kˈiw bˈa2ŋ hˈaːj."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_07 / studio / string

```json
{"text": "Mở https://example.com?q=2.", "expected": "Mở example chấm com hỏi kiu bằng hai.", "got": "Mở đường dẫn bằng hai.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n bˈa2ŋ hˈaːj.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm kˈɔm hˈɔ4j kˈiw bˈa2ŋ hˈaːj."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_07 / studio / post_g2p

```json
{"text": "Mở https://example.com?q=2.", "expected": "Mở example chấm com hỏi kiu bằng hai.", "got": "Mở đường dẫn bằng hai.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n bˈa2ŋ hˈaːj.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm kˈɔm hˈɔ4j kˈiw bˈa2ŋ hˈaːj."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_08 / nghe_ngay / string

```json
{"text": "Mở https://example.org/#top.", "expected": "Mở example chấm org gạch chéo thăng top.", "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ ɣˈe-6c tʃˈɛɜw tˈaŋ tˈɑːp."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_08 / nghe_ngay / post_g2p

```json
{"text": "Mở https://example.org/#top.", "expected": "Mở example chấm org gạch chéo thăng top.", "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ ɣˈe-6c tʃˈɛɜw tˈaŋ tˈɑːp."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_08 / studio / string

```json
{"text": "Mở https://example.org/#top.", "expected": "Mở example chấm org gạch chéo thăng top.", "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ ɣˈe-6c tʃˈɛɜw tˈaŋ tˈɑːp."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_08 / studio / post_g2p

```json
{"text": "Mở https://example.org/#top.", "expected": "Mở example chấm org gạch chéo thăng top.", "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ ɣˈe-6c tʃˈɛɜw tˈaŋ tˈɑːp."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_09 / nghe_ngay / string

```json
{"text": "Mở https://example.net/a-b.", "expected": "Mở example chấm net gạch chéo a gạch ngang bê.", "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪ ɣˈe-6c tʃˈɛɜw ˈaː ɣˈe-6c ŋˈaːŋ bˈe."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_09 / nghe_ngay / post_g2p

```json
{"text": "Mở https://example.net/a-b.", "expected": "Mở example chấm net gạch chéo a gạch ngang bê.", "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪ ɣˈe-6c tʃˈɛɜw ˈaː ɣˈe-6c ŋˈaːŋ bˈe."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_09 / studio / string

```json
{"text": "Mở https://example.net/a-b.", "expected": "Mở example chấm net gạch chéo a gạch ngang bê.", "got": "Mở đường dẫn, a-b.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n, ˈaː bˈe.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪ ɣˈe-6c tʃˈɛɜw ˈaː ɣˈe-6c ŋˈaːŋ bˈe."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_09 / studio / post_g2p

```json
{"text": "Mở https://example.net/a-b.", "expected": "Mở example chấm net gạch chéo a gạch ngang bê.", "got": "Mở đường dẫn, a-b.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n, ˈaː bˈe.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪ ɣˈe-6c tʃˈɛɜw ˈaː ɣˈe-6c ŋˈaːŋ bˈe."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_10 / nghe_ngay / string

```json
{"text": "Mở https://example.com/a_b.", "expected": "Mở example chấm com gạch chéo a gạch dưới bê.", "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm kˈɔm ɣˈe-6c tʃˈɛɜw ˈaː ɣˈe-6c zˈyəɜj bˈe."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_10 / nghe_ngay / post_g2p

```json
{"text": "Mở https://example.com/a_b.", "expected": "Mở example chấm com gạch chéo a gạch dưới bê.", "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm kˈɔm ɣˈe-6c tʃˈɛɜw ˈaː ɣˈe-6c zˈyəɜj bˈe."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_10 / studio / string

```json
{"text": "Mở https://example.com/a_b.", "expected": "Mở example chấm com gạch chéo a gạch dưới bê.", "got": "Mở đường dẫn, a_b.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n, ˈaː bˈe.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm kˈɔm ɣˈe-6c tʃˈɛɜw ˈaː ɣˈe-6c zˈyəɜj bˈe."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_10 / studio / post_g2p

```json
{"text": "Mở https://example.com/a_b.", "expected": "Mở example chấm com gạch chéo a gạch dưới bê.", "got": "Mở đường dẫn, a_b.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n, ˈaː bˈe.", "expected_phonemes": ["mˈəː4 ɛɡzˈæmpəl tʃˈəɜm kˈɔm ɣˈe-6c tʃˈɛɜw ˈaː ɣˈe-6c zˈyəɜj bˈe."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_11 / nghe_ngay / string

```json
{"text": "Gửi an@example.com.", "expected": ["Gửi an a còng example chấm com.", "Gửi an át example chấm com."], "got": "Gửi an@example.com.", "got_phonemes": "ɣˈy4j ˈaːn ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm kˈɔm.", "expected_phonemes": ["ɣˈy4j ˈaːn ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm kˈɔm.", "ɣˈy4j ˈaːn ˈaːɜt̪ ɛɡzˈæmpəl tʃˈəɜm kˈɔm."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_11 / studio / string

```json
{"text": "Gửi an@example.com.", "expected": ["Gửi an a còng example chấm com.", "Gửi an át example chấm com."], "got": "Gửi an@example.com.", "got_phonemes": "ɣˈy4j ˈaːn ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm kˈɔm.", "expected_phonemes": ["ɣˈy4j ˈaːn ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm kˈɔm.", "ɣˈy4j ˈaːn ˈaːɜt̪ ɛɡzˈæmpəl tʃˈəɜm kˈɔm."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_12 / nghe_ngay / string

```json
{"text": "Gửi binh@example.org.", "expected": ["Gửi binh a còng example chấm org.", "Gửi binh át example chấm org."], "got": "Gửi binh@example.org.", "got_phonemes": "ɣˈy4j bˈiɲ ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm ˈɔ ɹˈəː2 ɣˈəː2.", "expected_phonemes": ["ɣˈy4j bˈiɲ ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ.", "ɣˈy4j bˈiɲ ˈaːɜt̪ ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_12 / nghe_ngay / post_g2p

```json
{"text": "Gửi binh@example.org.", "expected": ["Gửi binh a còng example chấm org.", "Gửi binh át example chấm org."], "got": "Gửi binh@example.org.", "got_phonemes": "ɣˈy4j bˈiɲ ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm ˈɔ ɹˈəː2 ɣˈəː2.", "expected_phonemes": ["ɣˈy4j bˈiɲ ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ.", "ɣˈy4j bˈiɲ ˈaːɜt̪ ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_12 / studio / string

```json
{"text": "Gửi binh@example.org.", "expected": ["Gửi binh a còng example chấm org.", "Gửi binh át example chấm org."], "got": "Gửi binh@example.org.", "got_phonemes": "ɣˈy4j bˈiɲ ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm ˈɔ ɹˈəː2 ɣˈəː2.", "expected_phonemes": ["ɣˈy4j bˈiɲ ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ.", "ɣˈy4j bˈiɲ ˈaːɜt̪ ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_12 / studio / post_g2p

```json
{"text": "Gửi binh@example.org.", "expected": ["Gửi binh a còng example chấm org.", "Gửi binh át example chấm org."], "got": "Gửi binh@example.org.", "got_phonemes": "ɣˈy4j bˈiɲ ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm ˈɔ ɹˈəː2 ɣˈəː2.", "expected_phonemes": ["ɣˈy4j bˈiɲ ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ.", "ɣˈy4j bˈiɲ ˈaːɜt̪ ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_13 / nghe_ngay / string

```json
{"text": "Gửi chi@example.net.", "expected": ["Gửi chi a còng example chấm net.", "Gửi chi át example chấm net."], "got": "Gửi chi@example.net.", "got_phonemes": "ɣˈy4j tʃˈi ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪.", "expected_phonemes": ["ɣˈy4j tʃˈi ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪.", "ɣˈy4j tʃˈi ˈaːɜt̪ ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_13 / studio / string

```json
{"text": "Gửi chi@example.net.", "expected": ["Gửi chi a còng example chấm net.", "Gửi chi át example chấm net."], "got": "Gửi chi@example.net.", "got_phonemes": "ɣˈy4j tʃˈi ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪.", "expected_phonemes": ["ɣˈy4j tʃˈi ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪.", "ɣˈy4j tʃˈi ˈaːɜt̪ ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_14 / nghe_ngay / string

```json
{"text": "Gửi a.b@example.com.", "expected": "Gửi a chấm bê a còng example chấm com.", "got": "Gửi a.b@example.com.", "got_phonemes": "ɣˈy4j ˈaː tʃˈəɜm bˈe ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm kˈɔm.", "expected_phonemes": ["ɣˈy4j ˈaː tʃˈəɜm bˈe ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm kˈɔm."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_14 / studio / string

```json
{"text": "Gửi a.b@example.com.", "expected": "Gửi a chấm bê a còng example chấm com.", "got": "Gửi a.b@example.com.", "got_phonemes": "ɣˈy4j ˈaː tʃˈəɜm bˈe ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm kˈɔm.", "expected_phonemes": ["ɣˈy4j ˈaː tʃˈəɜm bˈe ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm kˈɔm."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_15 / nghe_ngay / string

```json
{"text": "Gửi a_b@example.org.", "expected": "Gửi a gạch dưới bê a còng example chấm org.", "got": "Gửi a_b@example.org.", "got_phonemes": "ɣˈy4j ˈaː ɣˈe-6c zˈyəɜj bˈe ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm ˈɔ ɹˈəː2 ɣˈəː2.", "expected_phonemes": ["ɣˈy4j ˈaː ɣˈe-6c zˈyəɜj bˈe ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_15 / nghe_ngay / post_g2p

```json
{"text": "Gửi a_b@example.org.", "expected": "Gửi a gạch dưới bê a còng example chấm org.", "got": "Gửi a_b@example.org.", "got_phonemes": "ɣˈy4j ˈaː ɣˈe-6c zˈyəɜj bˈe ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm ˈɔ ɹˈəː2 ɣˈəː2.", "expected_phonemes": ["ɣˈy4j ˈaː ɣˈe-6c zˈyəɜj bˈe ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_15 / studio / string

```json
{"text": "Gửi a_b@example.org.", "expected": "Gửi a gạch dưới bê a còng example chấm org.", "got": "Gửi a_b@example.org.", "got_phonemes": "ɣˈy4j ˈaː ɣˈe-6c zˈyəɜj bˈe ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm ˈɔ ɹˈəː2 ɣˈəː2.", "expected_phonemes": ["ɣˈy4j ˈaː ɣˈe-6c zˈyəɜj bˈe ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_15 / studio / post_g2p

```json
{"text": "Gửi a_b@example.org.", "expected": "Gửi a gạch dưới bê a còng example chấm org.", "got": "Gửi a_b@example.org.", "got_phonemes": "ɣˈy4j ˈaː ɣˈe-6c zˈyəɜj bˈe ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm ˈɔ ɹˈəː2 ɣˈəː2.", "expected_phonemes": ["ɣˈy4j ˈaː ɣˈe-6c zˈyəɜj bˈe ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_16 / nghe_ngay / string

```json
{"text": "Gửi a-b@example.net.", "expected": "Gửi a gạch ngang bê a còng example chấm net.", "got": "Gửi a-b@example.net.", "got_phonemes": "ɣˈy4j ˈaː ɣˈe-6c nˈoɜj bˈe ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪.", "expected_phonemes": ["ɣˈy4j ˈaː ɣˈe-6c ŋˈaːŋ bˈe ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_16 / nghe_ngay / post_g2p

```json
{"text": "Gửi a-b@example.net.", "expected": "Gửi a gạch ngang bê a còng example chấm net.", "got": "Gửi a-b@example.net.", "got_phonemes": "ɣˈy4j ˈaː ɣˈe-6c nˈoɜj bˈe ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪.", "expected_phonemes": ["ɣˈy4j ˈaː ɣˈe-6c ŋˈaːŋ bˈe ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_16 / studio / string

```json
{"text": "Gửi a-b@example.net.", "expected": "Gửi a gạch ngang bê a còng example chấm net.", "got": "Gửi a-b@example.net.", "got_phonemes": "ɣˈy4j ˈaː ɣˈe-6c nˈoɜj bˈe ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪.", "expected_phonemes": ["ɣˈy4j ˈaː ɣˈe-6c ŋˈaːŋ bˈe ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_16 / studio / post_g2p

```json
{"text": "Gửi a-b@example.net.", "expected": "Gửi a gạch ngang bê a còng example chấm net.", "got": "Gửi a-b@example.net.", "got_phonemes": "ɣˈy4j ˈaː ɣˈe-6c nˈoɜj bˈe ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪.", "expected_phonemes": ["ɣˈy4j ˈaː ɣˈe-6c ŋˈaːŋ bˈe ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_17 / nghe_ngay / string

```json
{"text": "Gửi an+test@example.com.", "expected": "Gửi an cộng test a còng example chấm com.", "got": "Gửi an và test@example.com.", "got_phonemes": "ɣˈy4j ˈaːn vˌaː2 tˈɛst ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm kˈɔm.", "expected_phonemes": ["ɣˈy4j ˈaːn kˈo6ŋ tˈɛst ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm kˈɔm."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_17 / nghe_ngay / post_g2p

```json
{"text": "Gửi an+test@example.com.", "expected": "Gửi an cộng test a còng example chấm com.", "got": "Gửi an và test@example.com.", "got_phonemes": "ɣˈy4j ˈaːn vˌaː2 tˈɛst ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm kˈɔm.", "expected_phonemes": ["ɣˈy4j ˈaːn kˈo6ŋ tˈɛst ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm kˈɔm."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_17 / studio / string

```json
{"text": "Gửi an+test@example.com.", "expected": "Gửi an cộng test a còng example chấm com.", "got": "Gửi an cộng test@example.com.", "got_phonemes": "ɣˈy4j ˈaːn kˈo6ŋ tˈɛst ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm kˈɔm.", "expected_phonemes": ["ɣˈy4j ˈaːn kˈo6ŋ tˈɛst ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm kˈɔm."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_18 / nghe_ngay / string

```json
{"text": "Gửi a12@example.org.", "expected": "Gửi a một hai a còng example chấm org.", "got": "Gửi a12 example.org.", "got_phonemes": "ɣˈy4j ˈaː mˈyə2j hˈaːj ɛɡzˈæmpəl tʃˈəɜm ˈɔ ɹˈəː2 ɣˈəː2.", "expected_phonemes": ["ɣˈy4j ˈaː mˈo6t̪ hˈaːj ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_18 / nghe_ngay / post_g2p

```json
{"text": "Gửi a12@example.org.", "expected": "Gửi a một hai a còng example chấm org.", "got": "Gửi a12 example.org.", "got_phonemes": "ɣˈy4j ˈaː mˈyə2j hˈaːj ɛɡzˈæmpəl tʃˈəɜm ˈɔ ɹˈəː2 ɣˈəː2.", "expected_phonemes": ["ɣˈy4j ˈaː mˈo6t̪ hˈaːj ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_18 / studio / string

```json
{"text": "Gửi a12@example.org.", "expected": "Gửi a một hai a còng example chấm org.", "got": "Gửi a12 example.org.", "got_phonemes": "ɣˈy4j ˈaː mˈyə2j hˈaːj ɛɡzˈæmpəl tʃˈəɜm ˈɔ ɹˈəː2 ɣˈəː2.", "expected_phonemes": ["ɣˈy4j ˈaː mˈo6t̪ hˈaːj ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_18 / studio / post_g2p

```json
{"text": "Gửi a12@example.org.", "expected": "Gửi a một hai a còng example chấm org.", "got": "Gửi a12 example.org.", "got_phonemes": "ɣˈy4j ˈaː mˈyə2j hˈaːj ɛɡzˈæmpəl tʃˈəɜm ˈɔ ɹˈəː2 ɣˈəː2.", "expected_phonemes": ["ɣˈy4j ˈaː mˈo6t̪ hˈaːj ˈaː kˈɔ2ŋ ɛɡzˈæmpəl tʃˈəɜm ˈɔːɹɡ."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_19 / nghe_ngay / string

```json
{"text": "Mở https://sub.example.com.", "expected": "Mở sub chấm example chấm com.", "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 sˈʌb tʃˈəɜm ɛɡzˈæmpəl tʃˈəɜm kˈɔm."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_19 / nghe_ngay / post_g2p

```json
{"text": "Mở https://sub.example.com.", "expected": "Mở sub chấm example chấm com.", "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 sˈʌb tʃˈəɜm ɛɡzˈæmpəl tʃˈəɜm kˈɔm."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_19 / studio / string

```json
{"text": "Mở https://sub.example.com.", "expected": "Mở sub chấm example chấm com.", "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 sˈʌb tʃˈəɜm ɛɡzˈæmpəl tʃˈəɜm kˈɔm."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_19 / studio / post_g2p

```json
{"text": "Mở https://sub.example.com.", "expected": "Mở sub chấm example chấm com.", "got": "Mở đường dẫn.", "got_phonemes": "mˈəː4 ɗˈyə2ŋ zˈə5n.", "expected_phonemes": ["mˈəː4 sˈʌb tʃˈəɜm ɛɡzˈæmpəl tʃˈəɜm kˈɔm."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_20 / nghe_ngay / string

```json
{"text": "Mở ftp://example.net.", "expected": ["Mở ép tê pê hai chấm gạch chéo gạch chéo example chấm net.", "Mở example chấm net."], "got": "Mở ftp:example.net.", "got_phonemes": "mˈəː4 ˌɛftˌiːpˈiː, ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪.", "expected_phonemes": ["mˈəː4 ˈɛɜp t̪ˈe pˈe hˈaːj tʃˈəɜm ɣˈe-6c tʃˈɛɜw ɣˈe-6c tʃˈɛɜw ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪.", "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_20 / nghe_ngay / post_g2p

```json
{"text": "Mở ftp://example.net.", "expected": ["Mở ép tê pê hai chấm gạch chéo gạch chéo example chấm net.", "Mở example chấm net."], "got": "Mở ftp:example.net.", "got_phonemes": "mˈəː4 ˌɛftˌiːpˈiː, ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪.", "expected_phonemes": ["mˈəː4 ˈɛɜp t̪ˈe pˈe hˈaːj tʃˈəɜm ɣˈe-6c tʃˈɛɜw ɣˈe-6c tʃˈɛɜw ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪.", "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_20 / studio / string

```json
{"text": "Mở ftp://example.net.", "expected": ["Mở ép tê pê hai chấm gạch chéo gạch chéo example chấm net.", "Mở example chấm net."], "got": "Mở ftp:example.net.", "got_phonemes": "mˈəː4 ˌɛftˌiːpˈiː, ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪.", "expected_phonemes": ["mˈəː4 ˈɛɜp t̪ˈe pˈe hˈaːj tʃˈəɜm ɣˈe-6c tʃˈɛɜw ɣˈe-6c tʃˈɛɜw ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪.", "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_20 / studio / post_g2p

```json
{"text": "Mở ftp://example.net.", "expected": ["Mở ép tê pê hai chấm gạch chéo gạch chéo example chấm net.", "Mở example chấm net."], "got": "Mở ftp:example.net.", "got_phonemes": "mˈəː4 ˌɛftˌiːpˈiː, ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪.", "expected_phonemes": ["mˈəː4 ˈɛɜp t̪ˈe pˈe hˈaːj tʃˈəɜm ɣˈe-6c tʃˈɛɜw ɣˈe-6c tʃˈɛɜw ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪.", "mˈəː4 ɛɡzˈæmpəl tʃˈəɜm nˈɛɜt̪."], "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### vocalization_01 / nghe_ngay / post_g2p

```json
{"text": "Aaaa!", "expected": ["a… a!", "a... a!", "a!"], "got": "a… a!", "got_phonemes": "ˈaː, ˈaː!", "expected_phonemes": ["ɐ, ɐ!", "ɐ, ɐ!", "ɐ!"], "note": "Nhiều cách ghi tiếng kéo dài hợp lý; chấp nhận âm rút gọn hoặc tách âm có dấu nghỉ."}
```

### vocalization_01 / studio / post_g2p

```json
{"text": "Aaaa!", "expected": ["a… a!", "a... a!", "a!"], "got": "a… a!", "got_phonemes": "ˈaː, ˈaː!", "expected_phonemes": ["ɐ, ɐ!", "ɐ, ɐ!", "ɐ!"], "note": "Nhiều cách ghi tiếng kéo dài hợp lý; chấp nhận âm rút gọn hoặc tách âm có dấu nghỉ."}
```

### vocalization_02 / nghe_ngay / string

```json
{"text": "Áaaaa!", "expected": ["á… a!", "á... a!", "á!"], "got": "á… á!", "got_phonemes": "ˈaːɜ, ˈaːɜ!", "expected_phonemes": ["ˈaːɜ, ˈaː!", "ˈaːɜ, ˈaː!", "ˈaːɜ!"], "note": "Nhiều cách ghi tiếng kéo dài hợp lý; chấp nhận âm rút gọn hoặc tách âm có dấu nghỉ."}
```

### vocalization_02 / nghe_ngay / post_g2p

```json
{"text": "Áaaaa!", "expected": ["á… a!", "á... a!", "á!"], "got": "á… á!", "got_phonemes": "ˈaːɜ, ˈaːɜ!", "expected_phonemes": ["ˈaːɜ, ˈaː!", "ˈaːɜ, ˈaː!", "ˈaːɜ!"], "note": "Nhiều cách ghi tiếng kéo dài hợp lý; chấp nhận âm rút gọn hoặc tách âm có dấu nghỉ."}
```

### vocalization_02 / studio / string

```json
{"text": "Áaaaa!", "expected": ["á… a!", "á... a!", "á!"], "got": "á… á!", "got_phonemes": "ˈaːɜ, ˈaːɜ!", "expected_phonemes": ["ˈaːɜ, ˈaː!", "ˈaːɜ, ˈaː!", "ˈaːɜ!"], "note": "Nhiều cách ghi tiếng kéo dài hợp lý; chấp nhận âm rút gọn hoặc tách âm có dấu nghỉ."}
```

### vocalization_02 / studio / post_g2p

```json
{"text": "Áaaaa!", "expected": ["á… a!", "á... a!", "á!"], "got": "á… á!", "got_phonemes": "ˈaːɜ, ˈaːɜ!", "expected_phonemes": ["ˈaːɜ, ˈaː!", "ˈaːɜ, ˈaː!", "ˈaːɜ!"], "note": "Nhiều cách ghi tiếng kéo dài hợp lý; chấp nhận âm rút gọn hoặc tách âm có dấu nghỉ."}
```

### vocalization_03 / nghe_ngay / post_g2p

```json
{"text": "Oooo!", "expected": ["o… o!", "o... o!", "ô!"], "got": "o… o_!", "got_phonemes": "ˈo, ˈɔ!", "expected_phonemes": ["ˈo, ˈo!", "ˈo, ˈo!", "ˈo!"], "note": "Nhiều cách ghi tiếng kéo dài hợp lý; chấp nhận âm rút gọn hoặc tách âm có dấu nghỉ."}
```

### vocalization_03 / studio / post_g2p

```json
{"text": "Oooo!", "expected": ["o… o!", "o... o!", "ô!"], "got": "o… o_!", "got_phonemes": "ˈo, ˈɔ!", "expected_phonemes": ["ˈo, ˈo!", "ˈo, ˈo!", "ˈo!"], "note": "Nhiều cách ghi tiếng kéo dài hợp lý; chấp nhận âm rút gọn hoặc tách âm có dấu nghỉ."}
```

### vocalization_05 / nghe_ngay / post_g2p

```json
{"text": "Eeee!", "expected": ["e… e!", "e... e!", "e!"], "got": "e… e!", "got_phonemes": "ˈɛ, ˈɛ!", "expected_phonemes": ["ˈiː, ˈiː!", "ˈiː, ˈiː!", "ˈiː!"], "note": "Nhiều cách ghi tiếng kéo dài hợp lý; chấp nhận âm rút gọn hoặc tách âm có dấu nghỉ."}
```

### vocalization_05 / studio / post_g2p

```json
{"text": "Eeee!", "expected": ["e… e!", "e... e!", "e!"], "got": "e… e!", "got_phonemes": "ˈɛ, ˈɛ!", "expected_phonemes": ["ˈiː, ˈiː!", "ˈiː, ˈiː!", "ˈiː!"], "note": "Nhiều cách ghi tiếng kéo dài hợp lý; chấp nhận âm rút gọn hoặc tách âm có dấu nghỉ."}
```

### vocalization_07 / nghe_ngay / post_g2p

```json
{"text": "Uuuu!", "expected": ["u… u!", "u... u!", "u!"], "got": "u… u!", "got_phonemes": "ˈu, ˈu!", "expected_phonemes": ["jˈuː, jˈuː!", "jˈuː, jˈuː!", "jˈuː!"], "note": "Nhiều cách ghi tiếng kéo dài hợp lý; chấp nhận âm rút gọn hoặc tách âm có dấu nghỉ."}
```

### vocalization_07 / studio / post_g2p

```json
{"text": "Uuuu!", "expected": ["u… u!", "u... u!", "u!"], "got": "u… u!", "got_phonemes": "ˈu, ˈu!", "expected_phonemes": ["jˈuː, jˈuː!", "jˈuː, jˈuː!", "jˈuː!"], "note": "Nhiều cách ghi tiếng kéo dài hợp lý; chấp nhận âm rút gọn hoặc tách âm có dấu nghỉ."}
```

### vocalization_16 / nghe_ngay / string

```json
{"text": "Hihihi!", "expected": "hi hi hi!", "got": "hy hy hy!", "got_phonemes": "hˈi hˈi hˈi!", "expected_phonemes": ["hˈi hˈi hˈi!"], "note": "Nhiều cách ghi tiếng kéo dài hợp lý; chấp nhận âm rút gọn hoặc tách âm có dấu nghỉ."}
```

### vocalization_16 / studio / string

```json
{"text": "Hihihi!", "expected": "hi hi hi!", "got": "hy hy hy!", "got_phonemes": "hˈi hˈi hˈi!", "expected_phonemes": ["hˈi hˈi hˈi!"], "note": "Nhiều cách ghi tiếng kéo dài hợp lý; chấp nhận âm rút gọn hoặc tách âm có dấu nghỉ."}
```

### vocalization_19 / nghe_ngay / post_g2p

```json
{"text": "Aaaa...!?", "expected": ["a… a…!?", "a... a...!?", "a!"], "got": "a… a...?", "got_phonemes": "ˈaː, ˈaː?", "expected_phonemes": ["ɐ, ɐ!", "ɐ, ɐ!", "ɐ!"], "note": "Nhiều cách ghi tiếng kéo dài hợp lý; chấp nhận âm rút gọn hoặc tách âm có dấu nghỉ."}
```

### vocalization_19 / studio / post_g2p

```json
{"text": "Aaaa...!?", "expected": ["a… a…!?", "a... a...!?", "a!"], "got": "a… a...?", "got_phonemes": "ˈaː, ˈaː?", "expected_phonemes": ["ɐ, ɐ!", "ɐ, ɐ!", "ɐ!"], "note": "Nhiều cách ghi tiếng kéo dài hợp lý; chấp nhận âm rút gọn hoặc tách âm có dấu nghỉ."}
```

### vocalization_20 / nghe_ngay / string

```json
{"text": "[thở dài]", "expected": ["hầy.", "hầy…", "hầy..."], "got": "[thở dài]", "got_phonemes": "tˈəː4 zˈaː2j.", "expected_phonemes": ["hˈəɪ2.", "hˈəɪ2.", "hˈəɪ2."], "note": "Cue thở dài được đọc bằng từ thường của Studio."}
```

### vocalization_20 / nghe_ngay / post_g2p

```json
{"text": "[thở dài]", "expected": ["hầy.", "hầy…", "hầy..."], "got": "[thở dài]", "got_phonemes": "tˈəː4 zˈaː2j.", "expected_phonemes": ["hˈəɪ2.", "hˈəɪ2.", "hˈəɪ2."], "note": "Cue thở dài được đọc bằng từ thường của Studio."}
```

### game_01 / nghe_ngay / string

```json
{"text": "Đạt Lv.5.", "expected": ["Đạt cấp năm.", "Đạt le vồ năm.", "Đạt level năm."], "got": "Đạt le-vồ 5.", "got_phonemes": "ɗˈaː6t̪ lˈɛ vˈo2 nˈam.", "expected_phonemes": ["ɗˈaː6t̪ kˈəɜp nˈam.", "ɗˈaː6t̪ lˈɛ vˈo2 nˈam.", "ɗˈaː6t̪ lˈɛvəl nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_01 / studio / string

```json
{"text": "Đạt Lv.5.", "expected": ["Đạt cấp năm.", "Đạt le vồ năm.", "Đạt level năm."], "got": "Đạt le-vồ 5.", "got_phonemes": "ɗˈaː6t̪ lˈɛ vˈo2 nˈam.", "expected_phonemes": ["ɗˈaː6t̪ kˈəɜp nˈam.", "ɗˈaː6t̪ lˈɛ vˈo2 nˈam.", "ɗˈaː6t̪ lˈɛvəl nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_02 / nghe_ngay / string

```json
{"text": "Đạt Lv.10.", "expected": ["Đạt cấp mười.", "Đạt le vồ mười.", "Đạt level mười."], "got": "Đạt le-vồ 10.", "got_phonemes": "ɗˈaː6t̪ lˈɛ vˈo2 mˈyə2j.", "expected_phonemes": ["ɗˈaː6t̪ kˈəɜp mˈyə2j.", "ɗˈaː6t̪ lˈɛ vˈo2 mˈyə2j.", "ɗˈaː6t̪ lˈɛvəl mˈyə2j."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_02 / studio / string

```json
{"text": "Đạt Lv.10.", "expected": ["Đạt cấp mười.", "Đạt le vồ mười.", "Đạt level mười."], "got": "Đạt le-vồ 10.", "got_phonemes": "ɗˈaː6t̪ lˈɛ vˈo2 mˈyə2j.", "expected_phonemes": ["ɗˈaː6t̪ kˈəɜp mˈyə2j.", "ɗˈaː6t̪ lˈɛ vˈo2 mˈyə2j.", "ɗˈaː6t̪ lˈɛvəl mˈyə2j."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_05 / nghe_ngay / string

```json
{"text": "Thưởng x2.", "expected": ["Thưởng nhân hai.", "Thưởng gấp hai."], "got": "Thưởng nhân 2.", "got_phonemes": "tˈyə4ŋ ɲˈən hˈaːj.", "expected_phonemes": ["tˈyə4ŋ ɲˈən hˈaːj.", "tˈyə4ŋ ɣˈəɜp hˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_05 / studio / string

```json
{"text": "Thưởng x2.", "expected": ["Thưởng nhân hai.", "Thưởng gấp hai."], "got": "Thưởng nhân 2.", "got_phonemes": "tˈyə4ŋ ɲˈən hˈaːj.", "expected_phonemes": ["tˈyə4ŋ ɲˈən hˈaːj.", "tˈyə4ŋ ɣˈəɜp hˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_06 / nghe_ngay / string

```json
{"text": "Thưởng ×3.", "expected": ["Thưởng nhân ba.", "Thưởng gấp ba."], "got": "Thưởng nhân 3.", "got_phonemes": "tˈyə4ŋ ɲˈən bˈaː.", "expected_phonemes": ["tˈyə4ŋ ɲˈən bˈaː.", "tˈyə4ŋ ɣˈəɜp bˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_07 / nghe_ngay / string

```json
{"text": "Thưởng 4x.", "expected": ["Thưởng nhân bốn.", "Thưởng gấp bốn."], "got": "Thưởng 4 lần.", "got_phonemes": "tˈyə4ŋ bˈoɜn lˈə2n.", "expected_phonemes": ["tˈyə4ŋ ɲˈən bˈoɜn.", "tˈyə4ŋ ɣˈəɜp bˈoɜn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_07 / nghe_ngay / post_g2p

```json
{"text": "Thưởng 4x.", "expected": ["Thưởng nhân bốn.", "Thưởng gấp bốn."], "got": "Thưởng 4 lần.", "got_phonemes": "tˈyə4ŋ bˈoɜn lˈə2n.", "expected_phonemes": ["tˈyə4ŋ ɲˈən bˈoɜn.", "tˈyə4ŋ ɣˈəɜp bˈoɜn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_07 / studio / string

```json
{"text": "Thưởng 4x.", "expected": ["Thưởng nhân bốn.", "Thưởng gấp bốn."], "got": "Thưởng 4 lần.", "got_phonemes": "tˈyə4ŋ bˈoɜn lˈə2n.", "expected_phonemes": ["tˈyə4ŋ ɲˈən bˈoɜn.", "tˈyə4ŋ ɣˈəɜp bˈoɜn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_07 / studio / post_g2p

```json
{"text": "Thưởng 4x.", "expected": ["Thưởng nhân bốn.", "Thưởng gấp bốn."], "got": "Thưởng 4 lần.", "got_phonemes": "tˈyə4ŋ bˈoɜn lˈə2n.", "expected_phonemes": ["tˈyə4ŋ ɲˈən bˈoɜn.", "tˈyə4ŋ ɣˈəɜp bˈoɜn."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_08 / nghe_ngay / string

```json
{"text": "Cộng +10 STR.", "expected": ["Cộng mười sức mạnh.", "Cộng cộng mười ét tê rờ.", "Cộng cộng mười ét ti a."], "got": "Cộng +10 <en>S T R</en>.", "got_phonemes": "kˈo6ŋ kˈo6ŋ mˈyə2j ˈɛs tˈiː ˈɑːɹ.", "expected_phonemes": ["kˈo6ŋ mˈyə2j sˈyɜc mˈe-6ɲ.", "kˈo6ŋ kˈo6ŋ mˈyə2j ˈɛɜt̪ t̪ˈe ɹˈəː2.", "kˈo6ŋ kˈo6ŋ mˈyə2j ˈɛɜt̪ t̪ˈi ˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_08 / nghe_ngay / post_g2p

```json
{"text": "Cộng +10 STR.", "expected": ["Cộng mười sức mạnh.", "Cộng cộng mười ét tê rờ.", "Cộng cộng mười ét ti a."], "got": "Cộng +10 <en>S T R</en>.", "got_phonemes": "kˈo6ŋ kˈo6ŋ mˈyə2j ˈɛs tˈiː ˈɑːɹ.", "expected_phonemes": ["kˈo6ŋ mˈyə2j sˈyɜc mˈe-6ɲ.", "kˈo6ŋ kˈo6ŋ mˈyə2j ˈɛɜt̪ t̪ˈe ɹˈəː2.", "kˈo6ŋ kˈo6ŋ mˈyə2j ˈɛɜt̪ t̪ˈi ˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_08 / studio / string

```json
{"text": "Cộng +10 STR.", "expected": ["Cộng mười sức mạnh.", "Cộng cộng mười ét tê rờ.", "Cộng cộng mười ét ti a."], "got": "Cộng cộng mười <en>S T R</en>.", "got_phonemes": "kˈo6ŋ kˈo6ŋ mˈyə2j ˈɛs tˈiː ˈɑːɹ.", "expected_phonemes": ["kˈo6ŋ mˈyə2j sˈyɜc mˈe-6ɲ.", "kˈo6ŋ kˈo6ŋ mˈyə2j ˈɛɜt̪ t̪ˈe ɹˈəː2.", "kˈo6ŋ kˈo6ŋ mˈyə2j ˈɛɜt̪ t̪ˈi ˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_08 / studio / post_g2p

```json
{"text": "Cộng +10 STR.", "expected": ["Cộng mười sức mạnh.", "Cộng cộng mười ét tê rờ.", "Cộng cộng mười ét ti a."], "got": "Cộng cộng mười <en>S T R</en>.", "got_phonemes": "kˈo6ŋ kˈo6ŋ mˈyə2j ˈɛs tˈiː ˈɑːɹ.", "expected_phonemes": ["kˈo6ŋ mˈyə2j sˈyɜc mˈe-6ɲ.", "kˈo6ŋ kˈo6ŋ mˈyə2j ˈɛɜt̪ t̪ˈe ɹˈəː2.", "kˈo6ŋ kˈo6ŋ mˈyə2j ˈɛɜt̪ t̪ˈi ˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_09 / nghe_ngay / string

```json
{"text": "Cộng +5 DEX.", "expected": ["Cộng năm khéo léo.", "Cộng cộng năm đê e ích.", "Cộng cộng năm đi i éc."], "got": "Cộng +5 <en>D E X</en>.", "got_phonemes": "kˈo6ŋ kˈo6ŋ nˈam dˈiː ˈiː ˈɛks.", "expected_phonemes": ["kˈo6ŋ nˈam xˈɛɜw lˈɛɜw.", "kˈo6ŋ kˈo6ŋ nˈam ɗˈe ˈɛ ˈiɜc.", "kˈo6ŋ kˈo6ŋ nˈam ɗˈi ˈi ˈɛɜc."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_09 / nghe_ngay / post_g2p

```json
{"text": "Cộng +5 DEX.", "expected": ["Cộng năm khéo léo.", "Cộng cộng năm đê e ích.", "Cộng cộng năm đi i éc."], "got": "Cộng +5 <en>D E X</en>.", "got_phonemes": "kˈo6ŋ kˈo6ŋ nˈam dˈiː ˈiː ˈɛks.", "expected_phonemes": ["kˈo6ŋ nˈam xˈɛɜw lˈɛɜw.", "kˈo6ŋ kˈo6ŋ nˈam ɗˈe ˈɛ ˈiɜc.", "kˈo6ŋ kˈo6ŋ nˈam ɗˈi ˈi ˈɛɜc."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_09 / studio / string

```json
{"text": "Cộng +5 DEX.", "expected": ["Cộng năm khéo léo.", "Cộng cộng năm đê e ích.", "Cộng cộng năm đi i éc."], "got": "Cộng cộng năm <en>D E X</en>.", "got_phonemes": "kˈo6ŋ kˈo6ŋ nˈam dˈiː ˈiː ˈɛks.", "expected_phonemes": ["kˈo6ŋ nˈam xˈɛɜw lˈɛɜw.", "kˈo6ŋ kˈo6ŋ nˈam ɗˈe ˈɛ ˈiɜc.", "kˈo6ŋ kˈo6ŋ nˈam ɗˈi ˈi ˈɛɜc."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_09 / studio / post_g2p

```json
{"text": "Cộng +5 DEX.", "expected": ["Cộng năm khéo léo.", "Cộng cộng năm đê e ích.", "Cộng cộng năm đi i éc."], "got": "Cộng cộng năm <en>D E X</en>.", "got_phonemes": "kˈo6ŋ kˈo6ŋ nˈam dˈiː ˈiː ˈɛks.", "expected_phonemes": ["kˈo6ŋ nˈam xˈɛɜw lˈɛɜw.", "kˈo6ŋ kˈo6ŋ nˈam ɗˈe ˈɛ ˈiɜc.", "kˈo6ŋ kˈo6ŋ nˈam ɗˈi ˈi ˈɛɜc."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_10 / nghe_ngay / string

```json
{"text": "Cộng +3 INT.", "expected": ["Cộng ba trí tuệ.", "Cộng cộng ba i en tê.", "Cộng cộng ba ai en ti."], "got": "Cộng +3 <en>I N T</en>.", "got_phonemes": "kˈo6ŋ kˈo6ŋ bˈaː ˈaɪ ˈɛn tˈiː.", "expected_phonemes": ["kˈo6ŋ bˈaː tʃˈiɜ t̪wˈe6.", "kˈo6ŋ kˈo6ŋ bˈaː ˈi ˈɛn t̪ˈe.", "kˈo6ŋ kˈo6ŋ bˈaː ˈaːj ˈɛn t̪ˈi."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_10 / nghe_ngay / post_g2p

```json
{"text": "Cộng +3 INT.", "expected": ["Cộng ba trí tuệ.", "Cộng cộng ba i en tê.", "Cộng cộng ba ai en ti."], "got": "Cộng +3 <en>I N T</en>.", "got_phonemes": "kˈo6ŋ kˈo6ŋ bˈaː ˈaɪ ˈɛn tˈiː.", "expected_phonemes": ["kˈo6ŋ bˈaː tʃˈiɜ t̪wˈe6.", "kˈo6ŋ kˈo6ŋ bˈaː ˈi ˈɛn t̪ˈe.", "kˈo6ŋ kˈo6ŋ bˈaː ˈaːj ˈɛn t̪ˈi."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_10 / studio / string

```json
{"text": "Cộng +3 INT.", "expected": ["Cộng ba trí tuệ.", "Cộng cộng ba i en tê.", "Cộng cộng ba ai en ti."], "got": "Cộng cộng ba <en>I N T</en>.", "got_phonemes": "kˈo6ŋ kˈo6ŋ bˈaː ˈaɪ ˈɛn tˈiː.", "expected_phonemes": ["kˈo6ŋ bˈaː tʃˈiɜ t̪wˈe6.", "kˈo6ŋ kˈo6ŋ bˈaː ˈi ˈɛn t̪ˈe.", "kˈo6ŋ kˈo6ŋ bˈaː ˈaːj ˈɛn t̪ˈi."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_10 / studio / post_g2p

```json
{"text": "Cộng +3 INT.", "expected": ["Cộng ba trí tuệ.", "Cộng cộng ba i en tê.", "Cộng cộng ba ai en ti."], "got": "Cộng cộng ba <en>I N T</en>.", "got_phonemes": "kˈo6ŋ kˈo6ŋ bˈaː ˈaɪ ˈɛn tˈiː.", "expected_phonemes": ["kˈo6ŋ bˈaː tʃˈiɜ t̪wˈe6.", "kˈo6ŋ kˈo6ŋ bˈaː ˈi ˈɛn t̪ˈe.", "kˈo6ŋ kˈo6ŋ bˈaː ˈaːj ˈɛn t̪ˈi."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_11 / nghe_ngay / string

```json
{"text": "Máu 3/4.", "expected": ["Máu ba trên bốn.", "Máu ba phần tư."], "got": "Máu 3 trên 4.", "got_phonemes": "mˈaɜw bˈaː tʃˈen bˈoɜn.", "expected_phonemes": ["mˈaɜw bˈaː tʃˈen bˈoɜn.", "mˈaɜw bˈaː fˈə2n t̪ˈy."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_11 / studio / string

```json
{"text": "Máu 3/4.", "expected": ["Máu ba trên bốn.", "Máu ba phần tư."], "got": "Máu 3 trên 4.", "got_phonemes": "mˈaɜw bˈaː tʃˈen bˈoɜn.", "expected_phonemes": ["mˈaɜw bˈaː tʃˈen bˈoɜn.", "mˈaɜw bˈaː fˈə2n t̪ˈy."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_12 / nghe_ngay / string

```json
{"text": "Mana 1/2.", "expected": ["Mana một trên hai.", "Mana một phần hai.", "Ma-na một trên hai."], "got": "Mana 1 trên 2.", "got_phonemes": "mˈɑːnə mˈo6t̪ tʃˈen hˈaːj.", "expected_phonemes": ["mˈɑːnə mˈo6t̪ tʃˈen hˈaːj.", "mˈɑːnə mˈo6t̪ fˈə2n hˈaːj.", "mˈaː nˈaː mˈo6t̪ tʃˈen hˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_12 / studio / string

```json
{"text": "Mana 1/2.", "expected": ["Mana một trên hai.", "Mana một phần hai.", "Ma-na một trên hai."], "got": "Mana 1 trên 2.", "got_phonemes": "mˈɑːnə mˈo6t̪ tʃˈen hˈaːj.", "expected_phonemes": ["mˈɑːnə mˈo6t̪ tʃˈen hˈaːj.", "mˈɑːnə mˈo6t̪ fˈə2n hˈaːj.", "mˈaː nˈaː mˈo6t̪ tʃˈen hˈaːj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_13 / nghe_ngay / string

```json
{"text": "Tỉ số 2:1.", "expected": ["Tỉ số hai một.", "Tỉ số hai trên một."], "got": "Tỉ số 2 1.", "got_phonemes": "t̪ˈi4 sˈoɜ hˈaːj mˈo6t̪.", "expected_phonemes": ["t̪ˈi4 sˈoɜ hˈaːj mˈo6t̪.", "t̪ˈi4 sˈoɜ hˈaːj tʃˈen mˈo6t̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_13 / studio / string

```json
{"text": "Tỉ số 2:1.", "expected": ["Tỉ số hai một.", "Tỉ số hai trên một."], "got": "Tỉ số 2 1.", "got_phonemes": "t̪ˈi4 sˈoɜ hˈaːj mˈo6t̪.", "expected_phonemes": ["t̪ˈi4 sˈoɜ hˈaːj mˈo6t̪.", "t̪ˈi4 sˈoɜ hˈaːj tʃˈen mˈo6t̪."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_14 / nghe_ngay / string

```json
{"text": "HP +20.", "expected": "Hát pê cộng hai mươi.", "got": "hát pê +20.", "got_phonemes": "hˈaːɜt̪ pˈe kˈo6ŋ hˈaːj mˈyəj.", "expected_phonemes": ["hˈaːɜt̪ pˈe kˈo6ŋ hˈaːj mˈyəj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_15 / nghe_ngay / string

```json
{"text": "MP -5.", "expected": ["Em pê trừ năm.", "Em pi trừ năm."], "got": "mờ pê trừ 5.", "got_phonemes": "mˈəː2 pˈe tʃˈy2 nˈam.", "expected_phonemes": ["ˈɛm pˈe tʃˈy2 nˈam.", "ˈɛm pˈi tʃˈy2 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_15 / nghe_ngay / post_g2p

```json
{"text": "MP -5.", "expected": ["Em pê trừ năm.", "Em pi trừ năm."], "got": "mờ pê trừ 5.", "got_phonemes": "mˈəː2 pˈe tʃˈy2 nˈam.", "expected_phonemes": ["ˈɛm pˈe tʃˈy2 nˈam.", "ˈɛm pˈi tʃˈy2 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_15 / studio / string

```json
{"text": "MP -5.", "expected": ["Em pê trừ năm.", "Em pi trừ năm."], "got": "mờ pê trừ 5.", "got_phonemes": "mˈəː2 pˈe tʃˈy2 nˈam.", "expected_phonemes": ["ˈɛm pˈe tʃˈy2 nˈam.", "ˈɛm pˈi tʃˈy2 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_15 / studio / post_g2p

```json
{"text": "MP -5.", "expected": ["Em pê trừ năm.", "Em pi trừ năm."], "got": "mờ pê trừ 5.", "got_phonemes": "mˈəː2 pˈe tʃˈy2 nˈam.", "expected_phonemes": ["ˈɛm pˈe tʃˈy2 nˈam.", "ˈɛm pˈi tʃˈy2 nˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_16 / nghe_ngay / string

```json
{"text": "ATK 100.", "expected": ["A tê ca một trăm.", "Ây ti cây một trăm.", "Tấn công một trăm."], "got": "<en>A T K</en> một trăm.", "got_phonemes": "ˈeɪ tˈiː kˈeɪ mˈo6t̪ tʃˈam.", "expected_phonemes": ["ˈaː t̪ˈe kˈaː mˈo6t̪ tʃˈam.", "ˈəɪ t̪ˈi kˈəɪ mˈo6t̪ tʃˈam.", "t̪ˈəɜn kˈoŋ mˈo6t̪ tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_16 / nghe_ngay / post_g2p

```json
{"text": "ATK 100.", "expected": ["A tê ca một trăm.", "Ây ti cây một trăm.", "Tấn công một trăm."], "got": "<en>A T K</en> một trăm.", "got_phonemes": "ˈeɪ tˈiː kˈeɪ mˈo6t̪ tʃˈam.", "expected_phonemes": ["ˈaː t̪ˈe kˈaː mˈo6t̪ tʃˈam.", "ˈəɪ t̪ˈi kˈəɪ mˈo6t̪ tʃˈam.", "t̪ˈəɜn kˈoŋ mˈo6t̪ tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_16 / studio / string

```json
{"text": "ATK 100.", "expected": ["A tê ca một trăm.", "Ây ti cây một trăm.", "Tấn công một trăm."], "got": "<en>A T K</en> một trăm.", "got_phonemes": "ˈeɪ tˈiː kˈeɪ mˈo6t̪ tʃˈam.", "expected_phonemes": ["ˈaː t̪ˈe kˈaː mˈo6t̪ tʃˈam.", "ˈəɪ t̪ˈi kˈəɪ mˈo6t̪ tʃˈam.", "t̪ˈəɜn kˈoŋ mˈo6t̪ tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_16 / studio / post_g2p

```json
{"text": "ATK 100.", "expected": ["A tê ca một trăm.", "Ây ti cây một trăm.", "Tấn công một trăm."], "got": "<en>A T K</en> một trăm.", "got_phonemes": "ˈeɪ tˈiː kˈeɪ mˈo6t̪ tʃˈam.", "expected_phonemes": ["ˈaː t̪ˈe kˈaː mˈo6t̪ tʃˈam.", "ˈəɪ t̪ˈi kˈəɪ mˈo6t̪ tʃˈam.", "t̪ˈəɜn kˈoŋ mˈo6t̪ tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_17 / nghe_ngay / string

```json
{"text": "DEF 50.", "expected": ["Đê e ép năm mươi.", "Đi i ép năm mươi.", "Phòng thủ năm mươi."], "got": "<en>D E F</en> năm mươi.", "got_phonemes": "dˈiː ˈiː ˈɛf nˈam mˈyəj.", "expected_phonemes": ["ɗˈe ˈɛ ˈɛɜp nˈam mˈyəj.", "ɗˈi ˈi ˈɛɜp nˈam mˈyəj.", "fˈɔ2ŋ tˈu4 nˈam mˈyəj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_17 / nghe_ngay / post_g2p

```json
{"text": "DEF 50.", "expected": ["Đê e ép năm mươi.", "Đi i ép năm mươi.", "Phòng thủ năm mươi."], "got": "<en>D E F</en> năm mươi.", "got_phonemes": "dˈiː ˈiː ˈɛf nˈam mˈyəj.", "expected_phonemes": ["ɗˈe ˈɛ ˈɛɜp nˈam mˈyəj.", "ɗˈi ˈi ˈɛɜp nˈam mˈyəj.", "fˈɔ2ŋ tˈu4 nˈam mˈyəj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_17 / studio / string

```json
{"text": "DEF 50.", "expected": ["Đê e ép năm mươi.", "Đi i ép năm mươi.", "Phòng thủ năm mươi."], "got": "<en>D E F</en> năm mươi.", "got_phonemes": "dˈiː ˈiː ˈɛf nˈam mˈyəj.", "expected_phonemes": ["ɗˈe ˈɛ ˈɛɜp nˈam mˈyəj.", "ɗˈi ˈi ˈɛɜp nˈam mˈyəj.", "fˈɔ2ŋ tˈu4 nˈam mˈyəj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_17 / studio / post_g2p

```json
{"text": "DEF 50.", "expected": ["Đê e ép năm mươi.", "Đi i ép năm mươi.", "Phòng thủ năm mươi."], "got": "<en>D E F</en> năm mươi.", "got_phonemes": "dˈiː ˈiː ˈɛf nˈam mˈyəj.", "expected_phonemes": ["ɗˈe ˈɛ ˈɛɜp nˈam mˈyəj.", "ɗˈi ˈi ˈɛɜp nˈam mˈyəj.", "fˈɔ2ŋ tˈu4 nˈam mˈyəj."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_18 / nghe_ngay / string

```json
{"text": "EXP +100.", "expected": ["Kinh nghiệm cộng một trăm.", "E ích pê cộng một trăm.", "I éc pi cộng một trăm."], "got": "<en>E X P</en> +100.", "got_phonemes": "ˈiː ˈɛks pˈiː kˈo6ŋ mˈo6t̪ tʃˈam.", "expected_phonemes": ["kˈiɲ ŋˈiɛ6m kˈo6ŋ mˈo6t̪ tʃˈam.", "ˈɛ ˈiɜc pˈe kˈo6ŋ mˈo6t̪ tʃˈam.", "ˈi ˈɛɜc pˈi kˈo6ŋ mˈo6t̪ tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_18 / nghe_ngay / post_g2p

```json
{"text": "EXP +100.", "expected": ["Kinh nghiệm cộng một trăm.", "E ích pê cộng một trăm.", "I éc pi cộng một trăm."], "got": "<en>E X P</en> +100.", "got_phonemes": "ˈiː ˈɛks pˈiː kˈo6ŋ mˈo6t̪ tʃˈam.", "expected_phonemes": ["kˈiɲ ŋˈiɛ6m kˈo6ŋ mˈo6t̪ tʃˈam.", "ˈɛ ˈiɜc pˈe kˈo6ŋ mˈo6t̪ tʃˈam.", "ˈi ˈɛɜc pˈi kˈo6ŋ mˈo6t̪ tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_18 / studio / string

```json
{"text": "EXP +100.", "expected": ["Kinh nghiệm cộng một trăm.", "E ích pê cộng một trăm.", "I éc pi cộng một trăm."], "got": "<en>E X P</en> cộng một trăm.", "got_phonemes": "ˈiː ˈɛks pˈiː kˈo6ŋ mˈo6t̪ tʃˈam.", "expected_phonemes": ["kˈiɲ ŋˈiɛ6m kˈo6ŋ mˈo6t̪ tʃˈam.", "ˈɛ ˈiɜc pˈe kˈo6ŋ mˈo6t̪ tʃˈam.", "ˈi ˈɛɜc pˈi kˈo6ŋ mˈo6t̪ tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_18 / studio / post_g2p

```json
{"text": "EXP +100.", "expected": ["Kinh nghiệm cộng một trăm.", "E ích pê cộng một trăm.", "I éc pi cộng một trăm."], "got": "<en>E X P</en> cộng một trăm.", "got_phonemes": "ˈiː ˈɛks pˈiː kˈo6ŋ mˈo6t̪ tʃˈam.", "expected_phonemes": ["kˈiɲ ŋˈiɛ6m kˈo6ŋ mˈo6t̪ tʃˈam.", "ˈɛ ˈiɜc pˈe kˈo6ŋ mˈo6t̪ tʃˈam.", "ˈi ˈɛɜc pˈi kˈo6ŋ mˈo6t̪ tʃˈam."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_19 / nghe_ngay / string

```json
{"text": "Tăng 10% ATK.", "expected": ["Tăng mười phần trăm tấn công.", "Tăng mười phần trăm a tê ca."], "got": "Tăng 10% <en>A T K</en>.", "got_phonemes": "t̪ˈaŋ mˈyə2j fˈə2n tʃˈam ˈeɪ tˈiː kˈeɪ.", "expected_phonemes": ["t̪ˈaŋ mˈyə2j fˈə2n tʃˈam t̪ˈəɜn kˈoŋ.", "t̪ˈaŋ mˈyə2j fˈə2n tʃˈam ˈaː t̪ˈe kˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_19 / nghe_ngay / post_g2p

```json
{"text": "Tăng 10% ATK.", "expected": ["Tăng mười phần trăm tấn công.", "Tăng mười phần trăm a tê ca."], "got": "Tăng 10% <en>A T K</en>.", "got_phonemes": "t̪ˈaŋ mˈyə2j fˈə2n tʃˈam ˈeɪ tˈiː kˈeɪ.", "expected_phonemes": ["t̪ˈaŋ mˈyə2j fˈə2n tʃˈam t̪ˈəɜn kˈoŋ.", "t̪ˈaŋ mˈyə2j fˈə2n tʃˈam ˈaː t̪ˈe kˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_19 / studio / string

```json
{"text": "Tăng 10% ATK.", "expected": ["Tăng mười phần trăm tấn công.", "Tăng mười phần trăm a tê ca."], "got": "Tăng 10% <en>A T K</en>.", "got_phonemes": "t̪ˈaŋ mˈyə2j fˈə2n tʃˈam ˈeɪ tˈiː kˈeɪ.", "expected_phonemes": ["t̪ˈaŋ mˈyə2j fˈə2n tʃˈam t̪ˈəɜn kˈoŋ.", "t̪ˈaŋ mˈyə2j fˈə2n tʃˈam ˈaː t̪ˈe kˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_19 / studio / post_g2p

```json
{"text": "Tăng 10% ATK.", "expected": ["Tăng mười phần trăm tấn công.", "Tăng mười phần trăm a tê ca."], "got": "Tăng 10% <en>A T K</en>.", "got_phonemes": "t̪ˈaŋ mˈyə2j fˈə2n tʃˈam ˈeɪ tˈiː kˈeɪ.", "expected_phonemes": ["t̪ˈaŋ mˈyə2j fˈə2n tʃˈam t̪ˈəɜn kˈoŋ.", "t̪ˈaŋ mˈyə2j fˈə2n tʃˈam ˈaː t̪ˈe kˈaː."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_20 / nghe_ngay / string

```json
{"text": "Hạng S+.", "expected": ["Hạng ét cộng.", "Hạng ét plus."], "got": "Hạng S+.", "got_phonemes": "hˈaː6ŋ ˈɛɜt̪ kˈo6ŋ.", "expected_phonemes": ["hˈaː6ŋ ˈɛɜt̪ kˈo6ŋ.", "hˈaː6ŋ ˈɛɜt̪ plˈʌs."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_20 / studio / string

```json
{"text": "Hạng S+.", "expected": ["Hạng ét cộng.", "Hạng ét plus."], "got": "Hạng S cộng.", "got_phonemes": "hˈaː6ŋ ˈɛɜt̪ kˈo6ŋ.", "expected_phonemes": ["hˈaː6ŋ ˈɛɜt̪ kˈo6ŋ.", "hˈaː6ŋ ˈɛɜt̪ plˈʌs."], "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

# TN benchmark

Text before engine phonemization; no audio accuracy claim.

| Category | N | Nghe ngay | Studio |
|---|---:|---:|---:|
| cardinal_small | 20 | 100.00% | 100.00% |
| cardinal_large | 20 | 50.00% | 50.00% |
| decimal | 20 | 35.00% | 35.00% |
| ordinal | 20 | 0.00% | 0.00% |
| roman | 20 | 85.00% | 85.00% |
| date | 20 | 10.00% | 10.00% |
| time | 20 | 5.00% | 5.00% |
| range | 20 | 5.00% | 5.00% |
| percentage | 20 | 0.00% | 0.00% |
| currency | 20 | 30.00% | 30.00% |
| unit | 20 | 0.00% | 0.00% |
| phone_code | 20 | 0.00% | 0.00% |
| abbrev_vi | 20 | 70.00% | 70.00% |
| abbrev_en | 20 | 35.00% | 35.00% |
| english | 20 | 100.00% | 100.00% |
| japanese | 20 | 70.00% | 70.00% |
| symbol | 20 | 10.00% | 40.00% |
| url_email | 20 | 0.00% | 0.00% |
| vocalization | 20 | 85.00% | 90.00% |
| punctuation | 20 | 100.00% | 100.00% |
| uppercase | 20 | 100.00% | 100.00% |
| game | 20 | 0.00% | 10.00% |
| **Overall** | 440 | 40.45% | 42.50% |

## Mismatches

### cardinal_large_06 / nghe_ngay

```json
{"text": "Phiếu ghi 1000000.", "expected": "Phiếu ghi một triệu.", "got": "Phiếu ghi 1000000.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_06 / studio

```json
{"text": "Phiếu ghi 1000000.", "expected": "Phiếu ghi một triệu.", "got": "Phiếu ghi 1000000.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_07 / nghe_ngay

```json
{"text": "Phiếu ghi 2000000.", "expected": "Phiếu ghi hai triệu.", "got": "Phiếu ghi 2000000.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_07 / studio

```json
{"text": "Phiếu ghi 2000000.", "expected": "Phiếu ghi hai triệu.", "got": "Phiếu ghi 2000000.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_08 / nghe_ngay

```json
{"text": "Phiếu ghi 10000000.", "expected": "Phiếu ghi mười triệu.", "got": "Phiếu ghi 10000000.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_08 / studio

```json
{"text": "Phiếu ghi 10000000.", "expected": "Phiếu ghi mười triệu.", "got": "Phiếu ghi 10000000.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_09 / nghe_ngay

```json
{"text": "Phiếu ghi 100000000.", "expected": "Phiếu ghi một trăm triệu.", "got": "Phiếu ghi 100000000.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_09 / studio

```json
{"text": "Phiếu ghi 100000000.", "expected": "Phiếu ghi một trăm triệu.", "got": "Phiếu ghi 100000000.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_10 / nghe_ngay

```json
{"text": "Phiếu ghi 1000000000.", "expected": ["Phiếu ghi một tỷ.", "Phiếu ghi một tỉ."], "got": "Phiếu ghi 1000000000.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_10 / studio

```json
{"text": "Phiếu ghi 1000000000.", "expected": ["Phiếu ghi một tỷ.", "Phiếu ghi một tỉ."], "got": "Phiếu ghi 1000000000.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_11 / nghe_ngay

```json
{"text": "Phiếu ghi 2000000000.", "expected": ["Phiếu ghi hai tỷ.", "Phiếu ghi hai tỉ."], "got": "Phiếu ghi 2000000000.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_11 / studio

```json
{"text": "Phiếu ghi 2000000000.", "expected": ["Phiếu ghi hai tỷ.", "Phiếu ghi hai tỉ."], "got": "Phiếu ghi 2000000000.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_12 / nghe_ngay

```json
{"text": "Phiếu ghi 10000000000.", "expected": ["Phiếu ghi mười tỷ.", "Phiếu ghi mười tỉ."], "got": "Phiếu ghi 10000000000.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_12 / studio

```json
{"text": "Phiếu ghi 10000000000.", "expected": ["Phiếu ghi mười tỷ.", "Phiếu ghi mười tỉ."], "got": "Phiếu ghi 10000000000.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_18 / nghe_ngay

```json
{"text": "Phiếu ghi 3200000.", "expected": "Phiếu ghi ba triệu hai trăm nghìn.", "got": "Phiếu ghi 3200000.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_18 / studio

```json
{"text": "Phiếu ghi 3200000.", "expected": "Phiếu ghi ba triệu hai trăm nghìn.", "got": "Phiếu ghi 3200000.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_19 / nghe_ngay

```json
{"text": "Phiếu ghi 45000000.", "expected": "Phiếu ghi bốn mươi lăm triệu.", "got": "Phiếu ghi 45000000.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_19 / studio

```json
{"text": "Phiếu ghi 45000000.", "expected": "Phiếu ghi bốn mươi lăm triệu.", "got": "Phiếu ghi 45000000.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_20 / nghe_ngay

```json
{"text": "Phiếu ghi 1200000000.", "expected": ["Phiếu ghi một tỷ hai trăm triệu.", "Phiếu ghi một tỉ hai trăm triệu."], "got": "Phiếu ghi 1200000000.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### cardinal_large_20 / studio

```json
{"text": "Phiếu ghi 1200000000.", "expected": ["Phiếu ghi một tỷ hai trăm triệu.", "Phiếu ghi một tỉ hai trăm triệu."], "got": "Phiếu ghi 1200000000.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_01 / nghe_ngay

```json
{"text": "Mức là 1,5.", "expected": "Mức là một phẩy năm.", "got": "Mức là 1,5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_01 / studio

```json
{"text": "Mức là 1,5.", "expected": "Mức là một phẩy năm.", "got": "Mức là 1,5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_02 / nghe_ngay

```json
{"text": "Mức là 2.5.", "expected": "Mức là hai phẩy năm.", "got": "Mức là 2.5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_02 / studio

```json
{"text": "Mức là 2.5.", "expected": "Mức là hai phẩy năm.", "got": "Mức là 2.5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_03 / nghe_ngay

```json
{"text": "Mức là 0,25.", "expected": "Mức là không phẩy hai năm.", "got": "Mức là 0,25.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_03 / studio

```json
{"text": "Mức là 0,25.", "expected": "Mức là không phẩy hai năm.", "got": "Mức là 0,25.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_04 / nghe_ngay

```json
{"text": "Mức là 0.75.", "expected": "Mức là không phẩy bảy năm.", "got": "Mức là 0.75.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_04 / studio

```json
{"text": "Mức là 0.75.", "expected": "Mức là không phẩy bảy năm.", "got": "Mức là 0.75.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_05 / nghe_ngay

```json
{"text": "Mức là 3,14.", "expected": "Mức là ba phẩy một bốn.", "got": "Mức là 3,14.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_05 / studio

```json
{"text": "Mức là 3,14.", "expected": "Mức là ba phẩy một bốn.", "got": "Mức là 3,14.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_06 / nghe_ngay

```json
{"text": "Mức là 6.28.", "expected": "Mức là sáu phẩy hai tám.", "got": "Mức là 6.28.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_06 / studio

```json
{"text": "Mức là 6.28.", "expected": "Mức là sáu phẩy hai tám.", "got": "Mức là 6.28.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_07 / nghe_ngay

```json
{"text": "Mức là 10,01.", "expected": "Mức là mười phẩy không một.", "got": "Mức là 10,01.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_07 / studio

```json
{"text": "Mức là 10,01.", "expected": "Mức là mười phẩy không một.", "got": "Mức là 10,01.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_08 / nghe_ngay

```json
{"text": "Mức là 12.05.", "expected": "Mức là mười hai phẩy không năm.", "got": "Mức là 12.05.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_08 / studio

```json
{"text": "Mức là 12.05.", "expected": "Mức là mười hai phẩy không năm.", "got": "Mức là 12.05.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_09 / nghe_ngay

```json
{"text": "Mức là -1,5.", "expected": "Mức là âm một phẩy năm.", "got": "Mức là âm 1,5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_09 / studio

```json
{"text": "Mức là -1,5.", "expected": "Mức là âm một phẩy năm.", "got": "Mức là âm 1,5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_10 / nghe_ngay

```json
{"text": "Mức là -2.5.", "expected": "Mức là âm hai phẩy năm.", "got": "Mức là âm 2.5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_10 / studio

```json
{"text": "Mức là -2.5.", "expected": "Mức là âm hai phẩy năm.", "got": "Mức là âm 2.5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_15 / nghe_ngay

```json
{"text": "Cân 1.234,5 kg.", "expected": ["Cân một nghìn hai trăm ba mươi bốn phẩy năm ki lô gam.", "Cân một nghìn hai trăm ba mươi tư phẩy năm ki lô gam."], "got": "Cân 1.234,5 kg.", "note": "Hai dấu phân cách theo kiểu Việt."}
```

### decimal_15 / studio

```json
{"text": "Cân 1.234,5 kg.", "expected": ["Cân một nghìn hai trăm ba mươi bốn phẩy năm ki lô gam.", "Cân một nghìn hai trăm ba mươi tư phẩy năm ki lô gam."], "got": "Cân 1.234,5 kg.", "note": "Hai dấu phân cách theo kiểu Việt."}
```

### decimal_16 / nghe_ngay

```json
{"text": "Cân 1,234.5 kg.", "expected": ["Cân một nghìn hai trăm ba mươi bốn phẩy năm ki lô gam.", "Cân một nghìn hai trăm ba mươi tư phẩy năm ki lô gam."], "got": "Cân 1,234.5 kg.", "note": "Hai dấu phân cách theo kiểu Anh."}
```

### decimal_16 / studio

```json
{"text": "Cân 1,234.5 kg.", "expected": ["Cân một nghìn hai trăm ba mươi bốn phẩy năm ki lô gam.", "Cân một nghìn hai trăm ba mươi tư phẩy năm ki lô gam."], "got": "Cân 1,234.5 kg.", "note": "Hai dấu phân cách theo kiểu Anh."}
```

### decimal_19 / nghe_ngay

```json
{"text": "Mức là 0,001.", "expected": "Mức là không phẩy không không một.", "got": "Mức là 0,001.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### decimal_19 / studio

```json
{"text": "Mức là 0,001.", "expected": "Mức là không phẩy không không một.", "got": "Mức là 0,001.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_01 / nghe_ngay

```json
{"text": "Lượt thứ 1.", "expected": ["Lượt thứ nhất.", "Lượt thứ một."], "got": "Lượt thứ 1.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_01 / studio

```json
{"text": "Lượt thứ 1.", "expected": ["Lượt thứ nhất.", "Lượt thứ một."], "got": "Lượt thứ 1.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_02 / nghe_ngay

```json
{"text": "Lượt thứ 2.", "expected": "Lượt thứ hai.", "got": "Lượt thứ 2.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_02 / studio

```json
{"text": "Lượt thứ 2.", "expected": "Lượt thứ hai.", "got": "Lượt thứ 2.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_03 / nghe_ngay

```json
{"text": "Lượt thứ 3.", "expected": "Lượt thứ ba.", "got": "Lượt thứ 3.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_03 / studio

```json
{"text": "Lượt thứ 3.", "expected": "Lượt thứ ba.", "got": "Lượt thứ 3.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_04 / nghe_ngay

```json
{"text": "Lượt thứ 4.", "expected": ["Lượt thứ tư.", "Lượt thứ bốn."], "got": "Lượt thứ 4.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_04 / studio

```json
{"text": "Lượt thứ 4.", "expected": ["Lượt thứ tư.", "Lượt thứ bốn."], "got": "Lượt thứ 4.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_05 / nghe_ngay

```json
{"text": "Lượt thứ 5.", "expected": "Lượt thứ năm.", "got": "Lượt thứ 5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_05 / studio

```json
{"text": "Lượt thứ 5.", "expected": "Lượt thứ năm.", "got": "Lượt thứ 5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_06 / nghe_ngay

```json
{"text": "Lượt thứ 6.", "expected": "Lượt thứ sáu.", "got": "Lượt thứ 6.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_06 / studio

```json
{"text": "Lượt thứ 6.", "expected": "Lượt thứ sáu.", "got": "Lượt thứ 6.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_07 / nghe_ngay

```json
{"text": "Lượt thứ 7.", "expected": "Lượt thứ bảy.", "got": "Lượt thứ 7.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_07 / studio

```json
{"text": "Lượt thứ 7.", "expected": "Lượt thứ bảy.", "got": "Lượt thứ 7.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_08 / nghe_ngay

```json
{"text": "Lượt thứ 8.", "expected": "Lượt thứ tám.", "got": "Lượt thứ 8.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_08 / studio

```json
{"text": "Lượt thứ 8.", "expected": "Lượt thứ tám.", "got": "Lượt thứ 8.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_09 / nghe_ngay

```json
{"text": "Lượt thứ 9.", "expected": "Lượt thứ chín.", "got": "Lượt thứ 9.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_09 / studio

```json
{"text": "Lượt thứ 9.", "expected": "Lượt thứ chín.", "got": "Lượt thứ 9.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_10 / nghe_ngay

```json
{"text": "Lượt thứ 10.", "expected": "Lượt thứ mười.", "got": "Lượt thứ 10.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_10 / studio

```json
{"text": "Lượt thứ 10.", "expected": "Lượt thứ mười.", "got": "Lượt thứ 10.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_11 / nghe_ngay

```json
{"text": "Vị trí thứ 11.", "expected": "Vị trí thứ mười một.", "got": "Vị trí thứ 11.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_11 / studio

```json
{"text": "Vị trí thứ 11.", "expected": "Vị trí thứ mười một.", "got": "Vị trí thứ 11.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_12 / nghe_ngay

```json
{"text": "Vị trí thứ 12.", "expected": "Vị trí thứ mười hai.", "got": "Vị trí thứ 12.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_12 / studio

```json
{"text": "Vị trí thứ 12.", "expected": "Vị trí thứ mười hai.", "got": "Vị trí thứ 12.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_13 / nghe_ngay

```json
{"text": "Vị trí thứ 14.", "expected": ["Vị trí thứ mười bốn.", "Vị trí thứ mười tư."], "got": "Vị trí thứ 14.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_13 / studio

```json
{"text": "Vị trí thứ 14.", "expected": ["Vị trí thứ mười bốn.", "Vị trí thứ mười tư."], "got": "Vị trí thứ 14.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_14 / nghe_ngay

```json
{"text": "Vị trí thứ 15.", "expected": "Vị trí thứ mười lăm.", "got": "Vị trí thứ 15.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_14 / studio

```json
{"text": "Vị trí thứ 15.", "expected": "Vị trí thứ mười lăm.", "got": "Vị trí thứ 15.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_15 / nghe_ngay

```json
{"text": "Vị trí thứ 20.", "expected": "Vị trí thứ hai mươi.", "got": "Vị trí thứ 20.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_15 / studio

```json
{"text": "Vị trí thứ 20.", "expected": "Vị trí thứ hai mươi.", "got": "Vị trí thứ 20.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_16 / nghe_ngay

```json
{"text": "Vị trí thứ 21.", "expected": "Vị trí thứ hai mươi mốt.", "got": "Vị trí thứ 21.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_16 / studio

```json
{"text": "Vị trí thứ 21.", "expected": "Vị trí thứ hai mươi mốt.", "got": "Vị trí thứ 21.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_17 / nghe_ngay

```json
{"text": "Vị trí thứ 24.", "expected": ["Vị trí thứ hai mươi bốn.", "Vị trí thứ hai mươi tư."], "got": "Vị trí thứ 24.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_17 / studio

```json
{"text": "Vị trí thứ 24.", "expected": ["Vị trí thứ hai mươi bốn.", "Vị trí thứ hai mươi tư."], "got": "Vị trí thứ 24.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_18 / nghe_ngay

```json
{"text": "Vị trí thứ 25.", "expected": "Vị trí thứ hai mươi lăm.", "got": "Vị trí thứ 25.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_18 / studio

```json
{"text": "Vị trí thứ 25.", "expected": "Vị trí thứ hai mươi lăm.", "got": "Vị trí thứ 25.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_19 / nghe_ngay

```json
{"text": "Vị trí thứ 100.", "expected": "Vị trí thứ một trăm.", "got": "Vị trí thứ 100.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_19 / studio

```json
{"text": "Vị trí thứ 100.", "expected": "Vị trí thứ một trăm.", "got": "Vị trí thứ 100.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_20 / nghe_ngay

```json
{"text": "Vị trí thứ 101.", "expected": ["Vị trí thứ một trăm linh một.", "Vị trí thứ một trăm lẻ một."], "got": "Vị trí thứ 101.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### ordinal_20 / studio

```json
{"text": "Vị trí thứ 101.", "expected": ["Vị trí thứ một trăm linh một.", "Vị trí thứ một trăm lẻ một."], "got": "Vị trí thứ 101.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### roman_17 / nghe_ngay

```json
{"text": "Chữ V in đậm.", "expected": ["Chữ vê in đậm.", "Chữ vi in đậm."], "got": "Chữ V in đậm.", "note": "Không đọc thành năm."}
```

### roman_17 / studio

```json
{"text": "Chữ V in đậm.", "expected": ["Chữ vê in đậm.", "Chữ vi in đậm."], "got": "Chữ V in đậm.", "note": "Không đọc thành năm."}
```

### roman_18 / nghe_ngay

```json
{"text": "Chữ X in nhỏ.", "expected": ["Chữ ích in nhỏ.", "Chữ éc in nhỏ.", "Chữ ét in nhỏ."], "got": "Chữ X in nhỏ.", "note": "Không đọc thành mười."}
```

### roman_18 / studio

```json
{"text": "Chữ X in nhỏ.", "expected": ["Chữ ích in nhỏ.", "Chữ éc in nhỏ.", "Chữ ét in nhỏ."], "got": "Chữ X in nhỏ.", "note": "Không đọc thành mười."}
```

### roman_20 / nghe_ngay

```json
{"text": "Ông X ký phiếu.", "expected": ["Ông ích ký phiếu.", "Ông X ký phiếu."], "got": "Ông <en>X</en> ký phiếu.", "note": "Ẩn danh, không phải số La Mã."}
```

### roman_20 / studio

```json
{"text": "Ông X ký phiếu.", "expected": ["Ông ích ký phiếu.", "Ông X ký phiếu."], "got": "Ông <en>X</en> ký phiếu.", "note": "Ẩn danh, không phải số La Mã."}
```

### date_01 / nghe_ngay

```json
{"text": "Ngày 1/2/2026.", "expected": "Ngày một tháng hai năm hai nghìn không trăm hai mươi sáu.", "got": "Ngày 1/2/2026.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_01 / studio

```json
{"text": "Ngày 1/2/2026.", "expected": "Ngày một tháng hai năm hai nghìn không trăm hai mươi sáu.", "got": "Ngày 1/2/2026.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_02 / nghe_ngay

```json
{"text": "Ngày 02/03/2025.", "expected": "Ngày hai tháng ba năm hai nghìn không trăm hai mươi lăm.", "got": "Ngày 02/03/2025.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_02 / studio

```json
{"text": "Ngày 02/03/2025.", "expected": "Ngày hai tháng ba năm hai nghìn không trăm hai mươi lăm.", "got": "Ngày 02/03/2025.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_03 / nghe_ngay

```json
{"text": "Ngày 15/4/2024.", "expected": "Ngày mười lăm tháng tư năm hai nghìn không trăm hai mươi bốn.", "got": "Ngày 15/4/2024.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_03 / studio

```json
{"text": "Ngày 15/4/2024.", "expected": "Ngày mười lăm tháng tư năm hai nghìn không trăm hai mươi bốn.", "got": "Ngày 15/4/2024.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_04 / nghe_ngay

```json
{"text": "Ngày 20/5/2023.", "expected": "Ngày hai mươi tháng năm năm hai nghìn không trăm hai mươi ba.", "got": "Ngày 20/5/2023.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_04 / studio

```json
{"text": "Ngày 20/5/2023.", "expected": "Ngày hai mươi tháng năm năm hai nghìn không trăm hai mươi ba.", "got": "Ngày 20/5/2023.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_05 / nghe_ngay

```json
{"text": "Ngày 30/6/2022.", "expected": "Ngày ba mươi tháng sáu năm hai nghìn không trăm hai mươi hai.", "got": "Ngày 30/6/2022.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_05 / studio

```json
{"text": "Ngày 30/6/2022.", "expected": "Ngày ba mươi tháng sáu năm hai nghìn không trăm hai mươi hai.", "got": "Ngày 30/6/2022.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_06 / nghe_ngay

```json
{"text": "Ngày 31/7/2123.", "expected": "Ngày ba mươi mốt tháng bảy năm hai nghìn một trăm hai mươi ba.", "got": "Ngày 31/7/2123.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_06 / studio

```json
{"text": "Ngày 31/7/2123.", "expected": "Ngày ba mươi mốt tháng bảy năm hai nghìn một trăm hai mươi ba.", "got": "Ngày 31/7/2123.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_07 / nghe_ngay

```json
{"text": "Ngày 8/8/2020.", "expected": "Ngày tám tháng tám năm hai nghìn không trăm hai mươi.", "got": "Ngày 8/8/2020.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_07 / studio

```json
{"text": "Ngày 8/8/2020.", "expected": "Ngày tám tháng tám năm hai nghìn không trăm hai mươi.", "got": "Ngày 8/8/2020.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_08 / nghe_ngay

```json
{"text": "Ngày 9/9/2019.", "expected": "Ngày chín tháng chín năm hai nghìn không trăm mười chín.", "got": "Ngày 9/9/2019.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_08 / studio

```json
{"text": "Ngày 9/9/2019.", "expected": "Ngày chín tháng chín năm hai nghìn không trăm mười chín.", "got": "Ngày 9/9/2019.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_09 / nghe_ngay

```json
{"text": "Ngày 10/10/2018.", "expected": "Ngày mười tháng mười năm hai nghìn không trăm mười tám.", "got": "Ngày 10/10/2018.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_09 / studio

```json
{"text": "Ngày 10/10/2018.", "expected": "Ngày mười tháng mười năm hai nghìn không trăm mười tám.", "got": "Ngày 10/10/2018.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_10 / nghe_ngay

```json
{"text": "Ngày 11/11/2347.", "expected": "Ngày mười một tháng mười một năm hai nghìn ba trăm bốn mươi bảy.", "got": "Ngày 11/11/2347.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_10 / studio

```json
{"text": "Ngày 11/11/2347.", "expected": "Ngày mười một tháng mười một năm hai nghìn ba trăm bốn mươi bảy.", "got": "Ngày 11/11/2347.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_11 / nghe_ngay

```json
{"text": "Ngày 12/12/2458.", "expected": "Ngày mười hai tháng mười hai năm hai nghìn bốn trăm năm mươi tám.", "got": "Ngày 12/12/2458.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_11 / studio

```json
{"text": "Ngày 12/12/2458.", "expected": "Ngày mười hai tháng mười hai năm hai nghìn bốn trăm năm mươi tám.", "got": "Ngày 12/12/2458.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_12 / nghe_ngay

```json
{"text": "Ngày 29/2/2024.", "expected": "Ngày hai mươi chín tháng hai năm hai nghìn không trăm hai mươi bốn.", "got": "Ngày 29/2/2024.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_12 / studio

```json
{"text": "Ngày 29/2/2024.", "expected": "Ngày hai mươi chín tháng hai năm hai nghìn không trăm hai mươi bốn.", "got": "Ngày 29/2/2024.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_13 / nghe_ngay

```json
{"text": "Ngày 1-3-2026.", "expected": "Ngày một tháng ba năm hai nghìn không trăm hai mươi sáu.", "got": "Ngày 1-3-2026.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_13 / studio

```json
{"text": "Ngày 1-3-2026.", "expected": "Ngày một tháng ba năm hai nghìn không trăm hai mươi sáu.", "got": "Ngày 1-3-2026.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_14 / nghe_ngay

```json
{"text": "Ngày 2.4.2026.", "expected": "Ngày hai tháng tư năm hai nghìn không trăm hai mươi sáu.", "got": "Ngày 2.4.2026.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_14 / studio

```json
{"text": "Ngày 2.4.2026.", "expected": "Ngày hai tháng tư năm hai nghìn không trăm hai mươi sáu.", "got": "Ngày 2.4.2026.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_15 / nghe_ngay

```json
{"text": "Ngày 2026-05-03.", "expected": "Ngày ba tháng năm năm hai nghìn không trăm hai mươi sáu.", "got": "Ngày 2026-05-03.", "note": "Định dạng ISO, năm đi trước."}
```

### date_15 / studio

```json
{"text": "Ngày 2026-05-03.", "expected": "Ngày ba tháng năm năm hai nghìn không trăm hai mươi sáu.", "got": "Ngày 2026-05-03.", "note": "Định dạng ISO, năm đi trước."}
```

### date_16 / nghe_ngay

```json
{"text": "Hẹn ngày 4/6.", "expected": "Hẹn ngày bốn tháng sáu.", "got": "Hẹn ngày 4 tháng 6.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_16 / studio

```json
{"text": "Hẹn ngày 4/6.", "expected": "Hẹn ngày bốn tháng sáu.", "got": "Hẹn ngày 4 tháng 6.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_17 / nghe_ngay

```json
{"text": "Hẹn ngày 5-7.", "expected": "Hẹn ngày năm tháng bảy.", "got": "Hẹn ngày 5 đến 7.", "note": "Có tiền tố ngày, ưu tiên ngày tháng."}
```

### date_17 / studio

```json
{"text": "Hẹn ngày 5-7.", "expected": "Hẹn ngày năm tháng bảy.", "got": "Hẹn ngày 5 đến 7.", "note": "Có tiền tố ngày, ưu tiên ngày tháng."}
```

### date_18 / nghe_ngay

```json
{"text": "Tháng 8/2026.", "expected": "Tháng tám năm hai nghìn không trăm hai mươi sáu.", "got": "Tháng 8 năm 2026.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### date_18 / studio

```json
{"text": "Tháng 8/2026.", "expected": "Tháng tám năm hai nghìn không trăm hai mươi sáu.", "got": "Tháng 8 năm 2026.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_01 / nghe_ngay

```json
{"text": "Hẹn lúc 7:00.", "expected": ["Hẹn lúc bảy giờ.", "Hẹn lúc bảy giờ không phút."], "got": "Hẹn lúc 7:00.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_01 / studio

```json
{"text": "Hẹn lúc 7:00.", "expected": ["Hẹn lúc bảy giờ.", "Hẹn lúc bảy giờ không phút."], "got": "Hẹn lúc 7:00.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_02 / nghe_ngay

```json
{"text": "Hẹn lúc 07:05.", "expected": ["Hẹn lúc bảy giờ năm phút.", "Hẹn lúc bảy giờ linh năm phút."], "got": "Hẹn lúc 07:05.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_02 / studio

```json
{"text": "Hẹn lúc 07:05.", "expected": ["Hẹn lúc bảy giờ năm phút.", "Hẹn lúc bảy giờ linh năm phút."], "got": "Hẹn lúc 07:05.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_03 / nghe_ngay

```json
{"text": "Hẹn lúc 8:15.", "expected": "Hẹn lúc tám giờ mười lăm phút.", "got": "Hẹn lúc 8:15.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_03 / studio

```json
{"text": "Hẹn lúc 8:15.", "expected": "Hẹn lúc tám giờ mười lăm phút.", "got": "Hẹn lúc 8:15.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_04 / nghe_ngay

```json
{"text": "Hẹn lúc 9:30.", "expected": ["Hẹn lúc chín giờ ba mươi phút.", "Hẹn lúc chín giờ rưỡi."], "got": "Hẹn lúc 9:30.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_04 / studio

```json
{"text": "Hẹn lúc 9:30.", "expected": ["Hẹn lúc chín giờ ba mươi phút.", "Hẹn lúc chín giờ rưỡi."], "got": "Hẹn lúc 9:30.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_05 / nghe_ngay

```json
{"text": "Hẹn lúc 10:45.", "expected": "Hẹn lúc mười giờ bốn mươi lăm phút.", "got": "Hẹn lúc 10:45.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_05 / studio

```json
{"text": "Hẹn lúc 10:45.", "expected": "Hẹn lúc mười giờ bốn mươi lăm phút.", "got": "Hẹn lúc 10:45.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_06 / nghe_ngay

```json
{"text": "Hẹn lúc 12:00.", "expected": ["Hẹn lúc mười hai giờ.", "Hẹn lúc mười hai giờ không phút."], "got": "Hẹn lúc 12:00.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_06 / studio

```json
{"text": "Hẹn lúc 12:00.", "expected": ["Hẹn lúc mười hai giờ.", "Hẹn lúc mười hai giờ không phút."], "got": "Hẹn lúc 12:00.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_07 / nghe_ngay

```json
{"text": "Hẹn lúc 13:20.", "expected": "Hẹn lúc mười ba giờ hai mươi phút.", "got": "Hẹn lúc 13:20.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_07 / studio

```json
{"text": "Hẹn lúc 13:20.", "expected": "Hẹn lúc mười ba giờ hai mươi phút.", "got": "Hẹn lúc 13:20.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_08 / nghe_ngay

```json
{"text": "Hẹn lúc 18:40.", "expected": "Hẹn lúc mười tám giờ bốn mươi phút.", "got": "Hẹn lúc 18:40.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_08 / studio

```json
{"text": "Hẹn lúc 18:40.", "expected": "Hẹn lúc mười tám giờ bốn mươi phút.", "got": "Hẹn lúc 18:40.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_09 / nghe_ngay

```json
{"text": "Hẹn lúc 23:00.", "expected": "Hẹn lúc hai mươi ba giờ.", "got": "Hẹn lúc 23:00.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_09 / studio

```json
{"text": "Hẹn lúc 23:00.", "expected": "Hẹn lúc hai mươi ba giờ.", "got": "Hẹn lúc 23:00.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_10 / nghe_ngay

```json
{"text": "Hẹn lúc 00:00.", "expected": ["Hẹn lúc không giờ.", "Hẹn lúc không giờ không phút."], "got": "Hẹn lúc 00:00.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_10 / studio

```json
{"text": "Hẹn lúc 00:00.", "expected": ["Hẹn lúc không giờ.", "Hẹn lúc không giờ không phút."], "got": "Hẹn lúc 00:00.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_11 / nghe_ngay

```json
{"text": "Hẹn lúc 7h.", "expected": "Hẹn lúc bảy giờ.", "got": "Hẹn lúc 7h.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_11 / studio

```json
{"text": "Hẹn lúc 7h.", "expected": "Hẹn lúc bảy giờ.", "got": "Hẹn lúc 7h.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_12 / nghe_ngay

```json
{"text": "Hẹn lúc 8h05.", "expected": ["Hẹn lúc tám giờ năm phút.", "Hẹn lúc tám giờ linh năm phút."], "got": "Hẹn lúc 8h05.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_12 / studio

```json
{"text": "Hẹn lúc 8h05.", "expected": ["Hẹn lúc tám giờ năm phút.", "Hẹn lúc tám giờ linh năm phút."], "got": "Hẹn lúc 8h05.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_13 / nghe_ngay

```json
{"text": "Hẹn lúc 9h30.", "expected": ["Hẹn lúc chín giờ ba mươi phút.", "Hẹn lúc chín giờ rưỡi."], "got": "Hẹn lúc 9h30.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_13 / studio

```json
{"text": "Hẹn lúc 9h30.", "expected": ["Hẹn lúc chín giờ ba mươi phút.", "Hẹn lúc chín giờ rưỡi."], "got": "Hẹn lúc 9h30.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_14 / nghe_ngay

```json
{"text": "Hẹn lúc 10h45.", "expected": "Hẹn lúc mười giờ bốn mươi lăm phút.", "got": "Hẹn lúc 10h45.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_14 / studio

```json
{"text": "Hẹn lúc 10h45.", "expected": "Hẹn lúc mười giờ bốn mươi lăm phút.", "got": "Hẹn lúc 10h45.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_16 / nghe_ngay

```json
{"text": "Đồng hồ 01:02:03.", "expected": "Đồng hồ một giờ hai phút ba giây.", "got": "Đồng hồ 01:02:03.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_16 / studio

```json
{"text": "Đồng hồ 01:02:03.", "expected": "Đồng hồ một giờ hai phút ba giây.", "got": "Đồng hồ 01:02:03.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_17 / nghe_ngay

```json
{"text": "Đồng hồ 12:34:56.", "expected": ["Đồng hồ mười hai giờ ba mươi bốn phút năm mươi sáu giây.", "Đồng hồ mười hai giờ ba mươi tư phút năm mươi sáu giây."], "got": "Đồng hồ 12:34:56.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_17 / studio

```json
{"text": "Đồng hồ 12:34:56.", "expected": ["Đồng hồ mười hai giờ ba mươi bốn phút năm mươi sáu giây.", "Đồng hồ mười hai giờ ba mươi tư phút năm mươi sáu giây."], "got": "Đồng hồ 12:34:56.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_18 / nghe_ngay

```json
{"text": "Hẹn lúc 7 AM.", "expected": "Hẹn lúc bảy giờ sáng.", "got": "Hẹn lúc bảy AM.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_18 / studio

```json
{"text": "Hẹn lúc 7 AM.", "expected": "Hẹn lúc bảy giờ sáng.", "got": "Hẹn lúc bảy AM.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_19 / nghe_ngay

```json
{"text": "Hẹn lúc 8 PM.", "expected": "Hẹn lúc tám giờ tối.", "got": "Hẹn lúc tám <en>P M</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_19 / studio

```json
{"text": "Hẹn lúc 8 PM.", "expected": "Hẹn lúc tám giờ tối.", "got": "Hẹn lúc tám <en>P M</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_20 / nghe_ngay

```json
{"text": "Hẹn lúc 3:15 PM.", "expected": "Hẹn lúc ba giờ mười lăm phút chiều.", "got": "Hẹn lúc 3:15 <en>P M</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### time_20 / studio

```json
{"text": "Hẹn lúc 3:15 PM.", "expected": "Hẹn lúc ba giờ mười lăm phút chiều.", "got": "Hẹn lúc 3:15 <en>P M</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_01 / nghe_ngay

```json
{"text": "Cần 1-2 hạt.", "expected": ["Cần một đến hai hạt.", "Cần một hai hạt."], "got": "Cần 1 đến 2 hạt.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_01 / studio

```json
{"text": "Cần 1-2 hạt.", "expected": ["Cần một đến hai hạt.", "Cần một hai hạt."], "got": "Cần 1 đến 2 hạt.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_02 / nghe_ngay

```json
{"text": "Cần 3~5 túi.", "expected": "Cần ba đến năm túi.", "got": "Cần 3 đến 5 túi.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_02 / studio

```json
{"text": "Cần 3~5 túi.", "expected": "Cần ba đến năm túi.", "got": "Cần 3 đến 5 túi.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_03 / nghe_ngay

```json
{"text": "Cần 6–8 khay.", "expected": "Cần sáu đến tám khay.", "got": "Cần 6, 8 khay.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_03 / studio

```json
{"text": "Cần 6–8 khay.", "expected": "Cần sáu đến tám khay.", "got": "Cần 6, 8 khay.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_04 / nghe_ngay

```json
{"text": "Cần 10—12 cốc.", "expected": "Cần mười đến mười hai cốc.", "got": "Cần 10, 12 cốc.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_04 / studio

```json
{"text": "Cần 10—12 cốc.", "expected": "Cần mười đến mười hai cốc.", "got": "Cần 10, 12 cốc.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_05 / nghe_ngay

```json
{"text": "Cần 20 - 30 que.", "expected": "Cần hai mươi đến ba mươi que.", "got": "Cần 20 đến 30 que.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_05 / studio

```json
{"text": "Cần 20 - 30 que.", "expected": "Cần hai mươi đến ba mươi que.", "got": "Cần 20 đến 30 que.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_06 / nghe_ngay

```json
{"text": "Cần 40 ~ 50 lá.", "expected": "Cần bốn mươi đến năm mươi lá.", "got": "Cần 40 đến 50 lá.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_06 / studio

```json
{"text": "Cần 40 ~ 50 lá.", "expected": "Cần bốn mươi đến năm mươi lá.", "got": "Cần 40 đến 50 lá.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_07 / nghe_ngay

```json
{"text": "Cần 100-200 viên.", "expected": "Cần một trăm đến hai trăm viên.", "got": "Cần 100 đến 200 viên.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_07 / studio

```json
{"text": "Cần 100-200 viên.", "expected": "Cần một trăm đến hai trăm viên.", "got": "Cần 100 đến 200 viên.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_08 / nghe_ngay

```json
{"text": "Cần 2-4 kg.", "expected": "Cần hai đến bốn ki lô gam.", "got": "Cần 2 đến 4 kg.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_08 / studio

```json
{"text": "Cần 2-4 kg.", "expected": "Cần hai đến bốn ki lô gam.", "got": "Cần 2 đến 4 kg.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_09 / nghe_ngay

```json
{"text": "Cần 5~7 km.", "expected": "Cần năm đến bảy ki lô mét.", "got": "Cần 5 đến 7 km.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_09 / studio

```json
{"text": "Cần 5~7 km.", "expected": "Cần năm đến bảy ki lô mét.", "got": "Cần 5 đến 7 km.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_10 / nghe_ngay

```json
{"text": "Cần 8–10 cm.", "expected": "Cần tám đến mười xen ti mét.", "got": "Cần 8, 10 cm.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_10 / studio

```json
{"text": "Cần 8–10 cm.", "expected": "Cần tám đến mười xen ti mét.", "got": "Cần 8, 10 cm.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_11 / nghe_ngay

```json
{"text": "Tuổi 18-20.", "expected": "Tuổi mười tám đến hai mươi.", "got": "Tuổi 18 đến 20.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_11 / studio

```json
{"text": "Tuổi 18-20.", "expected": "Tuổi mười tám đến hai mươi.", "got": "Tuổi 18 đến 20.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_12 / nghe_ngay

```json
{"text": "Trang 21-25.", "expected": "Trang hai mươi mốt đến hai mươi lăm.", "got": "Trang 21 đến 25.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_12 / studio

```json
{"text": "Trang 21-25.", "expected": "Trang hai mươi mốt đến hai mươi lăm.", "got": "Trang 21 đến 25.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_13 / nghe_ngay

```json
{"text": "Chương 2-3.", "expected": "Chương hai đến ba.", "got": "Chương 2 đến 3.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_13 / studio

```json
{"text": "Chương 2-3.", "expected": "Chương hai đến ba.", "got": "Chương 2 đến 3.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_14 / nghe_ngay

```json
{"text": "Mức 0,5-1,5.", "expected": "Mức không phẩy năm đến một phẩy năm.", "got": "Mức 0,5-1,5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_14 / studio

```json
{"text": "Mức 0,5-1,5.", "expected": "Mức không phẩy năm đến một phẩy năm.", "got": "Mức 0,5-1,5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_15 / nghe_ngay

```json
{"text": "Mức 1.5~2.5.", "expected": "Mức một phẩy năm đến hai phẩy năm.", "got": "Mức 1.5 đến 2.5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_15 / studio

```json
{"text": "Mức 1.5~2.5.", "expected": "Mức một phẩy năm đến hai phẩy năm.", "got": "Mức 1.5 đến 2.5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_17 / nghe_ngay

```json
{"text": "Nhiệt độ -5–0 °C.", "expected": "Nhiệt độ âm năm đến không độ xê.", "got": "Nhiệt độ âm 5, 0 °C.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_17 / studio

```json
{"text": "Nhiệt độ -5–0 °C.", "expected": "Nhiệt độ âm năm đến không độ xê.", "got": "Nhiệt độ âm 5, 0 °C.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_18 / nghe_ngay

```json
{"text": "Giờ mở 8-10 giờ.", "expected": "Giờ mở tám đến mười giờ.", "got": "Giờ mở 8 đến 10 giờ.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_18 / studio

```json
{"text": "Giờ mở 8-10 giờ.", "expected": "Giờ mở tám đến mười giờ.", "got": "Giờ mở 8 đến 10 giờ.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_19 / nghe_ngay

```json
{"text": "Giá 10-20 đồng.", "expected": "Giá mười đến hai mươi đồng.", "got": "Giá 10 đến 20 đồng.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_19 / studio

```json
{"text": "Giá 10-20 đồng.", "expected": "Giá mười đến hai mươi đồng.", "got": "Giá 10 đến 20 đồng.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_20 / nghe_ngay

```json
{"text": "Tỉ lệ 30~40%.", "expected": "Tỉ lệ ba mươi đến bốn mươi phần trăm.", "got": "Tỉ lệ 30 đến 40%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### range_20 / studio

```json
{"text": "Tỉ lệ 30~40%.", "expected": "Tỉ lệ ba mươi đến bốn mươi phần trăm.", "got": "Tỉ lệ 30 đến 40%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_01 / nghe_ngay

```json
{"text": "Mức đạt 0%.", "expected": "Mức đạt không phần trăm.", "got": "Mức đạt 0%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_01 / studio

```json
{"text": "Mức đạt 0%.", "expected": "Mức đạt không phần trăm.", "got": "Mức đạt 0%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_02 / nghe_ngay

```json
{"text": "Mức đạt 1%.", "expected": "Mức đạt một phần trăm.", "got": "Mức đạt 1%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_02 / studio

```json
{"text": "Mức đạt 1%.", "expected": "Mức đạt một phần trăm.", "got": "Mức đạt 1%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_03 / nghe_ngay

```json
{"text": "Mức đạt 2%.", "expected": "Mức đạt hai phần trăm.", "got": "Mức đạt 2%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_03 / studio

```json
{"text": "Mức đạt 2%.", "expected": "Mức đạt hai phần trăm.", "got": "Mức đạt 2%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_04 / nghe_ngay

```json
{"text": "Mức đạt 5%.", "expected": "Mức đạt năm phần trăm.", "got": "Mức đạt 5%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_04 / studio

```json
{"text": "Mức đạt 5%.", "expected": "Mức đạt năm phần trăm.", "got": "Mức đạt 5%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_05 / nghe_ngay

```json
{"text": "Mức đạt 10%.", "expected": "Mức đạt mười phần trăm.", "got": "Mức đạt 10%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_05 / studio

```json
{"text": "Mức đạt 10%.", "expected": "Mức đạt mười phần trăm.", "got": "Mức đạt 10%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_06 / nghe_ngay

```json
{"text": "Mức đạt 15%.", "expected": "Mức đạt mười lăm phần trăm.", "got": "Mức đạt 15%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_06 / studio

```json
{"text": "Mức đạt 15%.", "expected": "Mức đạt mười lăm phần trăm.", "got": "Mức đạt 15%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_07 / nghe_ngay

```json
{"text": "Mức đạt 20%.", "expected": "Mức đạt hai mươi phần trăm.", "got": "Mức đạt 20%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_07 / studio

```json
{"text": "Mức đạt 20%.", "expected": "Mức đạt hai mươi phần trăm.", "got": "Mức đạt 20%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_08 / nghe_ngay

```json
{"text": "Mức đạt 25%.", "expected": "Mức đạt hai mươi lăm phần trăm.", "got": "Mức đạt 25%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_08 / studio

```json
{"text": "Mức đạt 25%.", "expected": "Mức đạt hai mươi lăm phần trăm.", "got": "Mức đạt 25%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_09 / nghe_ngay

```json
{"text": "Mức đạt 30%.", "expected": "Mức đạt ba mươi phần trăm.", "got": "Mức đạt 30%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_09 / studio

```json
{"text": "Mức đạt 30%.", "expected": "Mức đạt ba mươi phần trăm.", "got": "Mức đạt 30%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_10 / nghe_ngay

```json
{"text": "Mức đạt 50%.", "expected": "Mức đạt năm mươi phần trăm.", "got": "Mức đạt 50%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_10 / studio

```json
{"text": "Mức đạt 50%.", "expected": "Mức đạt năm mươi phần trăm.", "got": "Mức đạt 50%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_11 / nghe_ngay

```json
{"text": "Mức đạt 75%.", "expected": "Mức đạt bảy mươi lăm phần trăm.", "got": "Mức đạt 75%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_11 / studio

```json
{"text": "Mức đạt 75%.", "expected": "Mức đạt bảy mươi lăm phần trăm.", "got": "Mức đạt 75%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_12 / nghe_ngay

```json
{"text": "Mức đạt 99%.", "expected": "Mức đạt chín mươi chín phần trăm.", "got": "Mức đạt 99%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_12 / studio

```json
{"text": "Mức đạt 99%.", "expected": "Mức đạt chín mươi chín phần trăm.", "got": "Mức đạt 99%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_13 / nghe_ngay

```json
{"text": "Mức đạt 100%.", "expected": "Mức đạt một trăm phần trăm.", "got": "Mức đạt 100%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_13 / studio

```json
{"text": "Mức đạt 100%.", "expected": "Mức đạt một trăm phần trăm.", "got": "Mức đạt 100%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_14 / nghe_ngay

```json
{"text": "Mức đạt 150%.", "expected": "Mức đạt một trăm năm mươi phần trăm.", "got": "Mức đạt 150%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_14 / studio

```json
{"text": "Mức đạt 150%.", "expected": "Mức đạt một trăm năm mươi phần trăm.", "got": "Mức đạt 150%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_15 / nghe_ngay

```json
{"text": "Mức đạt 0,5%.", "expected": "Mức đạt không phẩy năm phần trăm.", "got": "Mức đạt 0,5%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_15 / studio

```json
{"text": "Mức đạt 0,5%.", "expected": "Mức đạt không phẩy năm phần trăm.", "got": "Mức đạt 0,5%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_16 / nghe_ngay

```json
{"text": "Mức đạt 1.5%.", "expected": "Mức đạt một phẩy năm phần trăm.", "got": "Mức đạt 1.5%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_16 / studio

```json
{"text": "Mức đạt 1.5%.", "expected": "Mức đạt một phẩy năm phần trăm.", "got": "Mức đạt 1.5%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_17 / nghe_ngay

```json
{"text": "Mức đạt 12,5%.", "expected": "Mức đạt mười hai phẩy năm phần trăm.", "got": "Mức đạt 12,5%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_17 / studio

```json
{"text": "Mức đạt 12,5%.", "expected": "Mức đạt mười hai phẩy năm phần trăm.", "got": "Mức đạt 12,5%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_18 / nghe_ngay

```json
{"text": "Mức đạt 2.25%.", "expected": "Mức đạt hai phẩy hai năm phần trăm.", "got": "Mức đạt 2.25%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_18 / studio

```json
{"text": "Mức đạt 2.25%.", "expected": "Mức đạt hai phẩy hai năm phần trăm.", "got": "Mức đạt 2.25%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_19 / nghe_ngay

```json
{"text": "Mức đạt 25 %.", "expected": "Mức đạt hai mươi lăm phần trăm.", "got": "Mức đạt hai mươi lăm %.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_19 / studio

```json
{"text": "Mức đạt 25 %.", "expected": "Mức đạt hai mươi lăm phần trăm.", "got": "Mức đạt hai mươi lăm %.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_20 / nghe_ngay

```json
{"text": "Mức giảm -5%.", "expected": "Mức giảm âm năm phần trăm.", "got": "Mức giảm trừ 5%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### percentage_20 / studio

```json
{"text": "Mức giảm -5%.", "expected": "Mức giảm âm năm phần trăm.", "got": "Mức giảm trừ 5%.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_04 / nghe_ngay

```json
{"text": "Giá 20.000đ.", "expected": "Giá hai mươi nghìn đồng.", "got": "Giá 20.000đ.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_04 / studio

```json
{"text": "Giá 20.000đ.", "expected": "Giá hai mươi nghìn đồng.", "got": "Giá 20.000đ.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_05 / nghe_ngay

```json
{"text": "Giá 50.000₫.", "expected": "Giá năm mươi nghìn đồng.", "got": "Giá năm mươi nghìn₫.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_05 / studio

```json
{"text": "Giá 50.000₫.", "expected": "Giá năm mươi nghìn đồng.", "got": "Giá năm mươi nghìn₫.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_07 / nghe_ngay

```json
{"text": "Giá $5.", "expected": ["Giá năm đô la.", "Giá năm đô."], "got": "Giá 5 đô la.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_07 / studio

```json
{"text": "Giá $5.", "expected": ["Giá năm đô la.", "Giá năm đô."], "got": "Giá 5 đô la.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_08 / nghe_ngay

```json
{"text": "Giá 10$.", "expected": ["Giá mười đô la.", "Giá mười đô."], "got": "Giá 10 đô la.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_08 / studio

```json
{"text": "Giá 10$.", "expected": ["Giá mười đô la.", "Giá mười đô."], "got": "Giá 10 đô la.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_09 / nghe_ngay

```json
{"text": "Giá $1.50.", "expected": ["Giá một phẩy năm không đô la.", "Giá một đô la năm mươi xu."], "got": "Giá 1.50 đô la.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_09 / studio

```json
{"text": "Giá $1.50.", "expected": ["Giá một phẩy năm không đô la.", "Giá một đô la năm mươi xu."], "got": "Giá 1.50 đô la.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_10 / nghe_ngay

```json
{"text": "Giá 20 USD.", "expected": ["Giá hai mươi đô la Mỹ.", "Giá hai mươi đô la.", "Giá hai mươi u ét đê."], "got": "Giá hai mươi <en>U S D</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_10 / studio

```json
{"text": "Giá 20 USD.", "expected": ["Giá hai mươi đô la Mỹ.", "Giá hai mươi đô la.", "Giá hai mươi u ét đê."], "got": "Giá hai mươi <en>U S D</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_11 / nghe_ngay

```json
{"text": "Giá USD 30.", "expected": ["Giá ba mươi đô la Mỹ.", "Giá ba mươi đô la.", "Giá u ét đê ba mươi."], "got": "Giá <en>U S D</en> ba mươi.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_11 / studio

```json
{"text": "Giá USD 30.", "expected": ["Giá ba mươi đô la Mỹ.", "Giá ba mươi đô la.", "Giá u ét đê ba mươi."], "got": "Giá <en>U S D</en> ba mươi.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_12 / nghe_ngay

```json
{"text": "Giá 100 USD.", "expected": ["Giá một trăm đô la Mỹ.", "Giá một trăm đô la."], "got": "Giá một trăm <en>U S D</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_12 / studio

```json
{"text": "Giá 100 USD.", "expected": ["Giá một trăm đô la Mỹ.", "Giá một trăm đô la."], "got": "Giá một trăm <en>U S D</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_13 / nghe_ngay

```json
{"text": "Giá ¥500.", "expected": ["Giá năm trăm yên.", "Giá yên năm trăm."], "got": "Giá ¥500.", "note": "Quy ước ¥ là yên Nhật trong benchmark."}
```

### currency_13 / studio

```json
{"text": "Giá ¥500.", "expected": ["Giá năm trăm yên.", "Giá yên năm trăm."], "got": "Giá ¥500.", "note": "Quy ước ¥ là yên Nhật trong benchmark."}
```

### currency_14 / nghe_ngay

```json
{"text": "Giá 1000¥.", "expected": "Giá một nghìn yên.", "got": "Giá 1000¥.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_14 / studio

```json
{"text": "Giá 1000¥.", "expected": "Giá một nghìn yên.", "got": "Giá 1000¥.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_17 / nghe_ngay

```json
{"text": "Giá 300 JPY.", "expected": ["Giá ba trăm yên Nhật.", "Giá ba trăm yên."], "got": "Giá ba trăm <en>J P Y</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_17 / studio

```json
{"text": "Giá 300 JPY.", "expected": ["Giá ba trăm yên Nhật.", "Giá ba trăm yên."], "got": "Giá ba trăm <en>J P Y</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_18 / nghe_ngay

```json
{"text": "Giá €10.", "expected": ["Giá mười ơ rô.", "Giá mười euro."], "got": "Giá €10.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_18 / studio

```json
{"text": "Giá €10.", "expected": ["Giá mười ơ rô.", "Giá mười euro."], "got": "Giá €10.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_19 / nghe_ngay

```json
{"text": "Giá 20 EUR.", "expected": ["Giá hai mươi ơ rô.", "Giá hai mươi euro."], "got": "Giá hai mươi <en>E U R</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_19 / studio

```json
{"text": "Giá 20 EUR.", "expected": ["Giá hai mươi ơ rô.", "Giá hai mươi euro."], "got": "Giá hai mươi <en>E U R</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_20 / nghe_ngay

```json
{"text": "Giá £5.", "expected": "Giá năm bảng Anh.", "got": "Giá £5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### currency_20 / studio

```json
{"text": "Giá £5.", "expected": "Giá năm bảng Anh.", "got": "Giá £5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_01 / nghe_ngay

```json
{"text": "Dài 2 km.", "expected": ["Dài hai ki lô mét.", "Dài hai cây số."], "got": "Dài 2 km.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_01 / studio

```json
{"text": "Dài 2 km.", "expected": ["Dài hai ki lô mét.", "Dài hai cây số."], "got": "Dài 2 km.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_02 / nghe_ngay

```json
{"text": "Nặng 3 kg.", "expected": ["Nặng ba ki lô gam.", "Nặng ba ký."], "got": "Nặng 3 kg.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_02 / studio

```json
{"text": "Nặng 3 kg.", "expected": ["Nặng ba ki lô gam.", "Nặng ba ký."], "got": "Nặng 3 kg.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_03 / nghe_ngay

```json
{"text": "Rộng 4 m².", "expected": "Rộng bốn mét vuông.", "got": "Rộng 4 m².", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_03 / studio

```json
{"text": "Rộng 4 m².", "expected": "Rộng bốn mét vuông.", "got": "Rộng 4 m².", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_04 / nghe_ngay

```json
{"text": "Nóng 25 °C.", "expected": ["Nóng hai mươi lăm độ xê.", "Nóng hai mươi lăm độ C."], "got": "Nóng hai mươi lăm °C.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_04 / studio

```json
{"text": "Nóng 25 °C.", "expected": ["Nóng hai mươi lăm độ xê.", "Nóng hai mươi lăm độ C."], "got": "Nóng hai mươi lăm °C.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_05 / nghe_ngay

```json
{"text": "Dài 5 cm.", "expected": "Dài năm xen ti mét.", "got": "Dài 5 cm.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_05 / studio

```json
{"text": "Dài 5 cm.", "expected": "Dài năm xen ti mét.", "got": "Dài 5 cm.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_06 / nghe_ngay

```json
{"text": "Dày 6 mm.", "expected": "Dày sáu mi li mét.", "got": "Dày 6 mm.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_06 / studio

```json
{"text": "Dày 6 mm.", "expected": "Dày sáu mi li mét.", "got": "Dày 6 mm.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_07 / nghe_ngay

```json
{"text": "Cao 7 m.", "expected": "Cao bảy mét.", "got": "Cao 7 m.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_07 / studio

```json
{"text": "Cao 7 m.", "expected": "Cao bảy mét.", "got": "Cao 7 m.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_08 / nghe_ngay

```json
{"text": "Chứa 8 m³.", "expected": "Chứa tám mét khối.", "got": "Chứa 8 m³.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_08 / studio

```json
{"text": "Chứa 8 m³.", "expected": "Chứa tám mét khối.", "got": "Chứa 8 m³.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_09 / nghe_ngay

```json
{"text": "Cân 9 g.", "expected": "Cân chín gam.", "got": "Cân 9 g.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_09 / studio

```json
{"text": "Cân 9 g.", "expected": "Cân chín gam.", "got": "Cân 9 g.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_10 / nghe_ngay

```json
{"text": "Liều 10 mg.", "expected": "Liều mười mi li gam.", "got": "Liều 10 mg.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_10 / studio

```json
{"text": "Liều 10 mg.", "expected": "Liều mười mi li gam.", "got": "Liều 10 mg.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_11 / nghe_ngay

```json
{"text": "Rót 2 l.", "expected": "Rót hai lít.", "got": "Rót 2 l.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_11 / studio

```json
{"text": "Rót 2 l.", "expected": "Rót hai lít.", "got": "Rót 2 l.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_12 / nghe_ngay

```json
{"text": "Rót 250 ml.", "expected": "Rót hai trăm năm mươi mi li lít.", "got": "Rót 250 ml.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_12 / studio

```json
{"text": "Rót 250 ml.", "expected": "Rót hai trăm năm mươi mi li lít.", "got": "Rót 250 ml.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_13 / nghe_ngay

```json
{"text": "Chạy 60 km/h.", "expected": ["Chạy sáu mươi ki lô mét trên giờ.", "Chạy sáu mươi cây số một giờ."], "got": "Chạy 60 km/h.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_13 / studio

```json
{"text": "Chạy 60 km/h.", "expected": ["Chạy sáu mươi ki lô mét trên giờ.", "Chạy sáu mươi cây số một giờ."], "got": "Chạy 60 km/h.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_14 / nghe_ngay

```json
{"text": "Tốc độ 5 m/s.", "expected": "Tốc độ năm mét trên giây.", "got": "Tốc độ 5 m/s.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_14 / studio

```json
{"text": "Tốc độ 5 m/s.", "expected": "Tốc độ năm mét trên giây.", "got": "Tốc độ 5 m/s.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_15 / nghe_ngay

```json
{"text": "Đèn 12 W.", "expected": "Đèn mười hai oát.", "got": "Đèn 12 W.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_15 / studio

```json
{"text": "Đèn 12 W.", "expected": "Đèn mười hai oát.", "got": "Đèn 12 W.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_16 / nghe_ngay

```json
{"text": "Nguồn 220 V.", "expected": "Nguồn hai trăm hai mươi vôn.", "got": "Nguồn 220 V.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_16 / studio

```json
{"text": "Nguồn 220 V.", "expected": "Nguồn hai trăm hai mươi vôn.", "got": "Nguồn 220 V.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_17 / nghe_ngay

```json
{"text": "Nhịp 50 Hz.", "expected": "Nhịp năm mươi héc.", "got": "Nhịp 50 Hz.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_17 / studio

```json
{"text": "Nhịp 50 Hz.", "expected": "Nhịp năm mươi héc.", "got": "Nhịp 50 Hz.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_18 / nghe_ngay

```json
{"text": "Kho 2 GB.", "expected": ["Kho hai ghi ga bai.", "Kho hai gi ga bai."], "got": "Kho 2 <en>G B</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_18 / studio

```json
{"text": "Kho 2 GB.", "expected": ["Kho hai ghi ga bai.", "Kho hai gi ga bai."], "got": "Kho 2 <en>G B</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_19 / nghe_ngay

```json
{"text": "Mức 30 dB.", "expected": "Mức ba mươi đề xi ben.", "got": "Mức ba mươi db.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_19 / studio

```json
{"text": "Mức 30 dB.", "expected": "Mức ba mươi đề xi ben.", "got": "Mức ba mươi db.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_20 / nghe_ngay

```json
{"text": "Diện tích 1 ha.", "expected": "Diện tích một héc ta.", "got": "Diện tích 1 ha.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### unit_20 / studio

```json
{"text": "Diện tích 1 ha.", "expected": "Diện tích một héc ta.", "got": "Diện tích 1 ha.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### phone_code_01 / nghe_ngay

```json
{"text": "Số thử 0900123456.", "expected": "Số thử không chín không không một hai ba bốn năm sáu.", "got": "Số thử 0900123456.", "note": "Số giả dùng thử; đọc từng chữ số, không gọi điện."}
```

### phone_code_01 / studio

```json
{"text": "Số thử 0900123456.", "expected": "Số thử không chín không không một hai ba bốn năm sáu.", "got": "Số thử 0900123456.", "note": "Số giả dùng thử; đọc từng chữ số, không gọi điện."}
```

### phone_code_02 / nghe_ngay

```json
{"text": "Số thử 0910234567.", "expected": "Số thử không chín một không hai ba bốn năm sáu bảy.", "got": "Số thử 0910234567.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_02 / studio

```json
{"text": "Số thử 0910234567.", "expected": "Số thử không chín một không hai ba bốn năm sáu bảy.", "got": "Số thử 0910234567.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_03 / nghe_ngay

```json
{"text": "Số thử 0920345678.", "expected": "Số thử không chín hai không ba bốn năm sáu bảy tám.", "got": "Số thử 0920345678.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_03 / studio

```json
{"text": "Số thử 0920345678.", "expected": "Số thử không chín hai không ba bốn năm sáu bảy tám.", "got": "Số thử 0920345678.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_04 / nghe_ngay

```json
{"text": "Số thử 0930456789.", "expected": "Số thử không chín ba không bốn năm sáu bảy tám chín.", "got": "Số thử 0930456789.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_04 / studio

```json
{"text": "Số thử 0930456789.", "expected": "Số thử không chín ba không bốn năm sáu bảy tám chín.", "got": "Số thử 0930456789.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_05 / nghe_ngay

```json
{"text": "Số thử 0940567890.", "expected": "Số thử không chín bốn không năm sáu bảy tám chín không.", "got": "Số thử 0940567890.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_05 / studio

```json
{"text": "Số thử 0940567890.", "expected": "Số thử không chín bốn không năm sáu bảy tám chín không.", "got": "Số thử 0940567890.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_06 / nghe_ngay

```json
{"text": "Số thử 0900 111 222.", "expected": "Số thử không chín không không một một một hai hai hai.", "got": "Số thử 0900 111 222.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_06 / studio

```json
{"text": "Số thử 0900 111 222.", "expected": "Số thử không chín không không một một một hai hai hai.", "got": "Số thử 0900 111 222.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_07 / nghe_ngay

```json
{"text": "Số thử +84 900 123 456.", "expected": "Số thử cộng tám bốn chín không không một hai ba bốn năm sáu.", "got": "Số thử +84 900 123 456.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_07 / studio

```json
{"text": "Số thử +84 900 123 456.", "expected": "Số thử cộng tám bốn chín không không một hai ba bốn năm sáu.", "got": "Số thử cộng 84 900 123 456.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_08 / nghe_ngay

```json
{"text": "Mã PIN 0123.", "expected": ["Mã pin không một hai ba.", "Mã pi ai en không một hai ba."], "got": "Mã pin 0123.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_08 / studio

```json
{"text": "Mã PIN 0123.", "expected": ["Mã pin không một hai ba.", "Mã pi ai en không một hai ba."], "got": "Mã pin 0123.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_09 / nghe_ngay

```json
{"text": "Mã PIN 0005.", "expected": ["Mã pin không không không năm.", "Mã pi ai en không không không năm."], "got": "Mã pin 0005.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_09 / studio

```json
{"text": "Mã PIN 0005.", "expected": ["Mã pin không không không năm.", "Mã pi ai en không không không năm."], "got": "Mã pin 0005.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_10 / nghe_ngay

```json
{"text": "Mã OTP 654321.", "expected": ["Mã ô ti pi sáu năm bốn ba hai một.", "Mã ô tê pê sáu năm bốn ba hai một."], "got": "Mã <en>O T P</en> sáu trăm năm mươi bốn nghìn ba trăm hai mươi mốt.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_10 / studio

```json
{"text": "Mã OTP 654321.", "expected": ["Mã ô ti pi sáu năm bốn ba hai một.", "Mã ô tê pê sáu năm bốn ba hai một."], "got": "Mã <en>O T P</en> sáu trăm năm mươi bốn nghìn ba trăm hai mươi mốt.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_11 / nghe_ngay

```json
{"text": "Mã OTP 100200.", "expected": ["Mã ô ti pi một không không hai không không.", "Mã ô tê pê một không không hai không không."], "got": "Mã <en>O T P</en> một trăm nghìn hai trăm.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_11 / studio

```json
{"text": "Mã OTP 100200.", "expected": ["Mã ô ti pi một không không hai không không.", "Mã ô tê pê một không không hai không không."], "got": "Mã <en>O T P</en> một trăm nghìn hai trăm.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_12 / nghe_ngay

```json
{"text": "Mã vé 0017.", "expected": "Mã vé không không một bảy.", "got": "Mã vé 0017.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_12 / studio

```json
{"text": "Mã vé 0017.", "expected": "Mã vé không không một bảy.", "got": "Mã vé 0017.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_13 / nghe_ngay

```json
{"text": "Mã vé 0204.", "expected": "Mã vé không hai không bốn.", "got": "Mã vé 0204.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_13 / studio

```json
{"text": "Mã vé 0204.", "expected": "Mã vé không hai không bốn.", "got": "Mã vé 0204.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_14 / nghe_ngay

```json
{"text": "Mã vé 3006.", "expected": "Mã vé ba không không sáu.", "got": "Mã vé ba nghìn không trăm lẻ sáu.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_14 / studio

```json
{"text": "Mã vé 3006.", "expected": "Mã vé ba không không sáu.", "got": "Mã vé ba nghìn không trăm lẻ sáu.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_15 / nghe_ngay

```json
{"text": "Mã AB12.", "expected": ["Mã ây bi một hai.", "Mã a bê một hai."], "got": "Mã a bê mười hai.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_15 / studio

```json
{"text": "Mã AB12.", "expected": ["Mã ây bi một hai.", "Mã a bê một hai."], "got": "Mã a bê mười hai.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_16 / nghe_ngay

```json
{"text": "Mã CD34.", "expected": ["Mã xi đi ba bốn.", "Mã xê đê ba bốn."], "got": "Mã xê đê ba mươi bốn.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_16 / studio

```json
{"text": "Mã CD34.", "expected": ["Mã xi đi ba bốn.", "Mã xê đê ba bốn."], "got": "Mã xê đê ba mươi bốn.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_17 / nghe_ngay

```json
{"text": "Mã ZX90.", "expected": ["Mã dét ích chín không.", "Mã zi éc chín không."], "got": "Mã dét ích chín mươi.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_17 / studio

```json
{"text": "Mã ZX90.", "expected": ["Mã dét ích chín không.", "Mã zi éc chín không."], "got": "Mã dét ích chín mươi.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_18 / nghe_ngay

```json
{"text": "Phòng A101.", "expected": ["Phòng a một không một.", "Phòng ây một không một.", "Phòng a một trăm linh một."], "got": "Phòng a một trăm lẻ một.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_18 / studio

```json
{"text": "Phòng A101.", "expected": ["Phòng a một không một.", "Phòng ây một không một.", "Phòng a một trăm linh một."], "got": "Phòng a một trăm lẻ một.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_19 / nghe_ngay

```json
{"text": "Mã 007.", "expected": "Mã không không bảy.", "got": "Mã 007.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_19 / studio

```json
{"text": "Mã 007.", "expected": "Mã không không bảy.", "got": "Mã 007.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_20 / nghe_ngay

```json
{"text": "Mã 0000.", "expected": "Mã không không không không.", "got": "Mã 0000.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### phone_code_20 / studio

```json
{"text": "Mã 0000.", "expected": "Mã không không không không.", "got": "Mã 0000.", "note": "Mã giả tự đặt; đọc từng chữ số, giữ số không đầu; không liên hệ số này."}
```

### abbrev_vi_09 / nghe_ngay

```json
{"text": "Tại Q.1.", "expected": "Tại quận một.", "got": "Tại quận 1.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_09 / studio

```json
{"text": "Tại Q.1.", "expected": "Tại quận một.", "got": "Tại quận 1.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_10 / nghe_ngay

```json
{"text": "Tại P.2.", "expected": "Tại phường hai.", "got": "Tại phường 2.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_10 / studio

```json
{"text": "Tại P.2.", "expected": "Tại phường hai.", "got": "Tại phường 2.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_12 / nghe_ngay

```json
{"text": "Đọc VD. này.", "expected": "Đọc ví dụ này.", "got": "Đọc <en>V D</en>. này.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_12 / studio

```json
{"text": "Đọc VD. này.", "expected": "Đọc ví dụ này.", "got": "Đọc <en>V D</en>. này.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_13 / nghe_ngay

```json
{"text": "Xem tr. 5.", "expected": "Xem trang năm.", "got": "Xem tr. năm.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_13 / studio

```json
{"text": "Xem tr. 5.", "expected": "Xem trang năm.", "got": "Xem tr. năm.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_17 / nghe_ngay

```json
{"text": "Học CĐ.", "expected": "Học cao đẳng.", "got": "Học CĐ.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_17 / studio

```json
{"text": "Học CĐ.", "expected": "Học cao đẳng.", "got": "Học CĐ.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_19 / nghe_ngay

```json
{"text": "Tìm SĐT.", "expected": "Tìm số điện thoại.", "got": "Tìm SĐT.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_vi_19 / studio

```json
{"text": "Tìm SĐT.", "expected": "Tìm số điện thoại.", "got": "Tìm SĐT.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_05 / nghe_ngay

```json
{"text": "Gặp CEO.", "expected": ["Gặp xi i ô.", "Gặp giám đốc điều hành."], "got": "Gặp <en>C E O</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_05 / studio

```json
{"text": "Gặp CEO.", "expected": ["Gặp xi i ô.", "Gặp giám đốc điều hành."], "got": "Gặp <en>C E O</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_07 / nghe_ngay

```json
{"text": "Đỏ vs. xanh.", "expected": ["Đỏ với xanh.", "Đỏ đấu với xanh.", "Đỏ versus xanh."], "got": "Đỏ vs. xanh.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_07 / studio

```json
{"text": "Đỏ vs. xanh.", "expected": ["Đỏ với xanh.", "Đỏ đấu với xanh.", "Đỏ versus xanh."], "got": "Đỏ vs. xanh.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_08 / nghe_ngay

```json
{"text": "Gắn CPU.", "expected": ["Gắn xi pi iu.", "Gắn xê pê u."], "got": "Gắn <en>C P U</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_08 / studio

```json
{"text": "Gắn CPU.", "expected": ["Gắn xi pi iu.", "Gắn xê pê u."], "got": "Gắn <en>C P U</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_09 / nghe_ngay

```json
{"text": "Gắn GPU.", "expected": ["Gắn gi pi iu.", "Gắn gi pê u."], "got": "Gắn <en>G P U</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_09 / studio

```json
{"text": "Gắn GPU.", "expected": ["Gắn gi pi iu.", "Gắn gi pê u."], "got": "Gắn <en>G P U</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_10 / nghe_ngay

```json
{"text": "Đọc PDF.", "expected": ["Đọc pi đi ép.", "Đọc pê đê ép."], "got": "Đọc <en>P D F</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_10 / studio

```json
{"text": "Đọc PDF.", "expected": ["Đọc pi đi ép.", "Đọc pê đê ép."], "got": "Đọc <en>P D F</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_11 / nghe_ngay

```json
{"text": "Mở USB.", "expected": ["Mở iu ét bi.", "Mở u ét bê."], "got": "Mở <en>U S B</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_11 / studio

```json
{"text": "Mở USB.", "expected": ["Mở iu ét bi.", "Mở u ét bê."], "got": "Mở <en>U S B</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_12 / nghe_ngay

```json
{"text": "Dùng GPS.", "expected": ["Dùng gi pi ét.", "Dùng gi pê ét."], "got": "Dùng <en>G P S</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_12 / studio

```json
{"text": "Dùng GPS.", "expected": ["Dùng gi pi ét.", "Dùng gi pê ét."], "got": "Dùng <en>G P S</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_13 / nghe_ngay

```json
{"text": "Tăng FPS.", "expected": ["Tăng ép pi ét.", "Tăng ép pê ét."], "got": "Tăng <en>F P S</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_13 / studio

```json
{"text": "Tăng FPS.", "expected": ["Tăng ép pi ét.", "Tăng ép pê ét."], "got": "Tăng <en>F P S</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_14 / nghe_ngay

```json
{"text": "Chơi RPG.", "expected": ["Chơi a pi gi.", "Chơi rờ pê gi."], "got": "Chơi <en>R P G</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_14 / studio

```json
{"text": "Chơi RPG.", "expected": ["Chơi a pi gi.", "Chơi rờ pê gi."], "got": "Chơi <en>R P G</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_15 / nghe_ngay

```json
{"text": "Tăng EXP.", "expected": ["Tăng i éc pi.", "Tăng e ích pê.", "Tăng kinh nghiệm."], "got": "Tăng <en>E X P</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_15 / studio

```json
{"text": "Tăng EXP.", "expected": ["Tăng i éc pi.", "Tăng e ích pê.", "Tăng kinh nghiệm."], "got": "Tăng <en>E X P</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_16 / nghe_ngay

```json
{"text": "Đọc FAQ.", "expected": ["Đọc ép ây kiu.", "Đọc câu hỏi thường gặp."], "got": "Đọc <en>F A Q</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_16 / studio

```json
{"text": "Đọc FAQ.", "expected": ["Đọc ép ây kiu.", "Đọc câu hỏi thường gặp."], "got": "Đọc <en>F A Q</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_18 / nghe_ngay

```json
{"text": "Nghe DJ.", "expected": ["Nghe đi giây.", "Nghe đê giây."], "got": "Nghe <en>D J</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_18 / studio

```json
{"text": "Nghe DJ.", "expected": ["Nghe đi giây.", "Nghe đê giây."], "got": "Nghe <en>D J</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_19 / nghe_ngay

```json
{"text": "Bật AC.", "expected": ["Bật ây xi.", "Bật a xê."], "got": "Bật AC.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### abbrev_en_19 / studio

```json
{"text": "Bật AC.", "expected": ["Bật ây xi.", "Bật a xê."], "got": "Bật AC.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### japanese_04 / nghe_ngay

```json
{"text": "Yuki-sama xếp khay.", "expected": ["Yu-ki-xa-ma xếp khay.", "Yư-ki-xa-ma xếp khay."], "got": "Giu-ki-xa-ma xếp khay.", "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_04 / studio

```json
{"text": "Yuki-sama xếp khay.", "expected": ["Yu-ki-xa-ma xếp khay.", "Yư-ki-xa-ma xếp khay."], "got": "Giu-ki-xa-ma xếp khay.", "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_12 / nghe_ngay

```json
{"text": "Sensei xem phiếu.", "expected": ["Xen-xê xem phiếu.", "Sen-sê xem phiếu."], "got": "xen-xây xem phiếu.", "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_12 / studio

```json
{"text": "Sensei xem phiếu.", "expected": ["Xen-xê xem phiếu.", "Sen-sê xem phiếu."], "got": "xen-xây xem phiếu.", "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_13 / nghe_ngay

```json
{"text": "Kouhai xem phiếu.", "expected": ["Cô-hai xem phiếu.", "Kô-hai xem phiếu."], "got": "Câu-hai xem phiếu.", "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_13 / studio

```json
{"text": "Kouhai xem phiếu.", "expected": ["Cô-hai xem phiếu.", "Kô-hai xem phiếu."], "got": "Câu-hai xem phiếu.", "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_14 / nghe_ngay

```json
{"text": "Arigatou, xin nhận.", "expected": ["A-ri-ga-tô, xin nhận.", "A-ri-ga-tou, xin nhận."], "got": "a-ri-ga-tâu, xin nhận.", "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_14 / studio

```json
{"text": "Arigatou, xin nhận.", "expected": ["A-ri-ga-tô, xin nhận.", "A-ri-ga-tou, xin nhận."], "got": "a-ri-ga-tâu, xin nhận.", "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_15 / nghe_ngay

```json
{"text": "Ohayou, mời vào.", "expected": ["Ô-ha-yô, mời vào.", "O-ha-yo, mời vào."], "got": "ô-ha-giâu, mời vào.", "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_15 / studio

```json
{"text": "Ohayou, mời vào.", "expected": ["Ô-ha-yô, mời vào.", "O-ha-yo, mời vào."], "got": "ô-ha-giâu, mời vào.", "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_20 / nghe_ngay

```json
{"text": "Onee-chan đến.", "expected": ["Ô-nê-chan đến.", "O-nê-chan đến."], "got": "ô-ne-chan đến.", "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### japanese_20 / studio

```json
{"text": "Onee-chan đến.", "expected": ["Ô-nê-chan đến.", "O-nê-chan đến."], "got": "ô-ne-chan đến.", "note": "Gốc ja cố định; phiên âm thực dụng theo âm tiết, không tự đổi nghĩa hoặc dịch kính ngữ."}
```

### symbol_03 / nghe_ngay

```json
{"text": "Mã #5.", "expected": ["Mã thăng năm.", "Mã số năm."], "got": "Mã số 5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_03 / studio

```json
{"text": "Mã #5.", "expected": ["Mã thăng năm.", "Mã số năm."], "got": "Mã số 5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_04 / nghe_ngay

```json
{"text": "Ký hiệu %.", "expected": "Ký hiệu phần trăm.", "got": "Ký hiệu %.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_04 / studio

```json
{"text": "Ký hiệu %.", "expected": "Ký hiệu phần trăm.", "got": "Ký hiệu %.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_05 / nghe_ngay

```json
{"text": "Tính 2 + 3.", "expected": "Tính hai cộng ba.", "got": "Tính 2 + 3.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_06 / nghe_ngay

```json
{"text": "Tính 2 = 2.", "expected": "Tính hai bằng hai.", "got": "Tính 2 bằng 2.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_07 / nghe_ngay

```json
{"text": "Trà / cà phê.", "expected": ["Trà hoặc cà phê.", "Trà trên cà phê."], "got": "Trà, cà phê.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_07 / studio

```json
{"text": "Trà / cà phê.", "expected": ["Trà hoặc cà phê.", "Trà trên cà phê."], "got": "Trà, cà phê.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_08 / nghe_ngay

```json
{"text": "Tính 3 × 4.", "expected": "Tính ba nhân bốn.", "got": "Tính 3 nhân 4.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_09 / nghe_ngay

```json
{"text": "Khay → hộp.", "expected": ["Khay sang hộp.", "Khay đến hộp.", "Khay chuyển thành hộp."], "got": "Khay thành hộp.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_09 / studio

```json
{"text": "Khay → hộp.", "expected": ["Khay sang hộp.", "Khay đến hộp.", "Khay chuyển thành hộp."], "got": "Khay, hộp.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_10 / nghe_ngay

```json
{"text": "Xếp hạng ★★★.", "expected": ["Xếp hạng ba sao.", "Xếp hạng sao sao sao."], "got": "Xếp hạng .", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_10 / studio

```json
{"text": "Xếp hạng ★★★.", "expected": ["Xếp hạng ba sao.", "Xếp hạng sao sao sao."], "got": "Xếp hạng .", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_11 / nghe_ngay

```json
{"text": "La ♪ la.", "expected": ["La la.", "La, la."], "got": "La ♪ la.", "note": "Nốt nhạc chỉ ngữ điệu, không thêm lời."}
```

### symbol_11 / studio

```json
{"text": "La ♪ la.", "expected": ["La la.", "La, la."], "got": "La ♪ la.", "note": "Nốt nhạc chỉ ngữ điệu, không thêm lời."}
```

### symbol_12 / nghe_ngay

```json
{"text": "Tính 5 − 2.", "expected": "Tính năm trừ hai.", "got": "Tính năm − hai.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_12 / studio

```json
{"text": "Tính 5 − 2.", "expected": "Tính năm trừ hai.", "got": "Tính năm − hai.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_13 / nghe_ngay

```json
{"text": "Tính 6 ÷ 3.", "expected": "Tính sáu chia ba.", "got": "Tính 6 ÷ 3.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_14 / nghe_ngay

```json
{"text": "Điểm ≥ 5.", "expected": "Điểm lớn hơn hoặc bằng năm.", "got": "Điểm ≥ 5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_15 / nghe_ngay

```json
{"text": "Điểm ≤ 8.", "expected": "Điểm nhỏ hơn hoặc bằng tám.", "got": "Điểm ≤ 8.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_16 / nghe_ngay

```json
{"text": "Điểm ≠ 0.", "expected": "Điểm khác không.", "got": "Điểm không phải là 0.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_16 / studio

```json
{"text": "Điểm ≠ 0.", "expected": "Điểm khác không.", "got": "Điểm không phải là 0.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_17 / nghe_ngay

```json
{"text": "Mức ±2.", "expected": "Mức cộng trừ hai.", "got": "Mức ±2.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_17 / studio

```json
{"text": "Mức ±2.", "expected": "Mức cộng trừ hai.", "got": "Mức ±2.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_18 / nghe_ngay

```json
{"text": "Ký hiệu ©.", "expected": "Ký hiệu bản quyền.", "got": "Ký hiệu ©.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_18 / studio

```json
{"text": "Ký hiệu ©.", "expected": "Ký hiệu bản quyền.", "got": "Ký hiệu ©.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_19 / nghe_ngay

```json
{"text": "Tính 2:1.", "expected": ["Tính hai chia một.", "Tính hai trên một."], "got": "Tính 2:1.", "note": "Quy ước là phép tính hoặc tỉ số."}
```

### symbol_19 / studio

```json
{"text": "Tính 2:1.", "expected": ["Tính hai chia một.", "Tính hai trên một."], "got": "Tính 2:1.", "note": "Quy ước là phép tính hoặc tỉ số."}
```

### symbol_20 / nghe_ngay

```json
{"text": "Nhãn A&B.", "expected": ["Nhãn a và bê.", "Nhãn ây và bi."], "got": "Nhãn A en B.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### symbol_20 / studio

```json
{"text": "Nhãn A&B.", "expected": ["Nhãn a và bê.", "Nhãn ây và bi."], "got": "Nhãn A en B.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### url_email_01 / nghe_ngay

```json
{"text": "Mở https://example.com.", "expected": ["Mở hát tê tê pê ét hai chấm gạch chéo gạch chéo example chấm com.", "Mở example chấm com."], "got": "Mở đường dẫn.", "note": "Cho phép bỏ giao thức khi đọc URL, tên miền giữ spelling đa ngữ."}
```

### url_email_01 / studio

```json
{"text": "Mở https://example.com.", "expected": ["Mở hát tê tê pê ét hai chấm gạch chéo gạch chéo example chấm com.", "Mở example chấm com."], "got": "Mở đường dẫn.", "note": "Cho phép bỏ giao thức khi đọc URL, tên miền giữ spelling đa ngữ."}
```

### url_email_02 / nghe_ngay

```json
{"text": "Mở http://example.org.", "expected": ["Mở hát tê tê pê hai chấm gạch chéo gạch chéo example chấm org.", "Mở example chấm org."], "got": "Mở đường dẫn.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_02 / studio

```json
{"text": "Mở http://example.org.", "expected": ["Mở hát tê tê pê hai chấm gạch chéo gạch chéo example chấm org.", "Mở example chấm org."], "got": "Mở đường dẫn.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_03 / nghe_ngay

```json
{"text": "Mở www.example.net.", "expected": ["Mở vê kép vê kép vê kép chấm example chấm net.", "Mở example chấm net."], "got": "Mở www.example.net.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_03 / studio

```json
{"text": "Mở www.example.net.", "expected": ["Mở vê kép vê kép vê kép chấm example chấm net.", "Mở example chấm net."], "got": "Mở www.example.net.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_04 / nghe_ngay

```json
{"text": "Mở example.com/a.", "expected": "Mở example chấm com gạch chéo a.", "got": "Mở đường dẫn.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_04 / studio

```json
{"text": "Mở example.com/a.", "expected": "Mở example chấm com gạch chéo a.", "got": "Mở example.com, a.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_05 / nghe_ngay

```json
{"text": "Mở example.org/b.", "expected": ["Mở example chấm org gạch chéo bê.", "Mở example chấm org gạch chéo bi."], "got": "Mở đường dẫn.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_05 / studio

```json
{"text": "Mở example.org/b.", "expected": ["Mở example chấm org gạch chéo bê.", "Mở example chấm org gạch chéo bi."], "got": "Mở example.org, b.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_06 / nghe_ngay

```json
{"text": "Mở https://example.net/5.", "expected": ["Mở example chấm net gạch chéo năm.", "Mở hát tê tê pê ét hai chấm gạch chéo gạch chéo example chấm net gạch chéo năm."], "got": "Mở đường dẫn.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_06 / studio

```json
{"text": "Mở https://example.net/5.", "expected": ["Mở example chấm net gạch chéo năm.", "Mở hát tê tê pê ét hai chấm gạch chéo gạch chéo example chấm net gạch chéo năm."], "got": "Mở đường dẫn.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_07 / nghe_ngay

```json
{"text": "Mở https://example.com?q=2.", "expected": "Mở example chấm com hỏi kiu bằng hai.", "got": "Mở đường dẫn.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_07 / studio

```json
{"text": "Mở https://example.com?q=2.", "expected": "Mở example chấm com hỏi kiu bằng hai.", "got": "Mở đường dẫn bằng hai.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_08 / nghe_ngay

```json
{"text": "Mở https://example.org/#top.", "expected": "Mở example chấm org gạch chéo thăng top.", "got": "Mở đường dẫn.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_08 / studio

```json
{"text": "Mở https://example.org/#top.", "expected": "Mở example chấm org gạch chéo thăng top.", "got": "Mở đường dẫn.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_09 / nghe_ngay

```json
{"text": "Mở https://example.net/a-b.", "expected": "Mở example chấm net gạch chéo a gạch ngang bê.", "got": "Mở đường dẫn.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_09 / studio

```json
{"text": "Mở https://example.net/a-b.", "expected": "Mở example chấm net gạch chéo a gạch ngang bê.", "got": "Mở đường dẫn, a-b.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_10 / nghe_ngay

```json
{"text": "Mở https://example.com/a_b.", "expected": "Mở example chấm com gạch chéo a gạch dưới bê.", "got": "Mở đường dẫn.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_10 / studio

```json
{"text": "Mở https://example.com/a_b.", "expected": "Mở example chấm com gạch chéo a gạch dưới bê.", "got": "Mở đường dẫn, a_b.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_11 / nghe_ngay

```json
{"text": "Gửi an@example.com.", "expected": ["Gửi an a còng example chấm com.", "Gửi an át example chấm com."], "got": "Gửi an@example.com.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_11 / studio

```json
{"text": "Gửi an@example.com.", "expected": ["Gửi an a còng example chấm com.", "Gửi an át example chấm com."], "got": "Gửi an@example.com.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_12 / nghe_ngay

```json
{"text": "Gửi binh@example.org.", "expected": ["Gửi binh a còng example chấm org.", "Gửi binh át example chấm org."], "got": "Gửi binh@example.org.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_12 / studio

```json
{"text": "Gửi binh@example.org.", "expected": ["Gửi binh a còng example chấm org.", "Gửi binh át example chấm org."], "got": "Gửi binh@example.org.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_13 / nghe_ngay

```json
{"text": "Gửi chi@example.net.", "expected": ["Gửi chi a còng example chấm net.", "Gửi chi át example chấm net."], "got": "Gửi chi@example.net.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_13 / studio

```json
{"text": "Gửi chi@example.net.", "expected": ["Gửi chi a còng example chấm net.", "Gửi chi át example chấm net."], "got": "Gửi chi@example.net.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_14 / nghe_ngay

```json
{"text": "Gửi a.b@example.com.", "expected": "Gửi a chấm bê a còng example chấm com.", "got": "Gửi a.b@example.com.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_14 / studio

```json
{"text": "Gửi a.b@example.com.", "expected": "Gửi a chấm bê a còng example chấm com.", "got": "Gửi a.b@example.com.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_15 / nghe_ngay

```json
{"text": "Gửi a_b@example.org.", "expected": "Gửi a gạch dưới bê a còng example chấm org.", "got": "Gửi a_b@example.org.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_15 / studio

```json
{"text": "Gửi a_b@example.org.", "expected": "Gửi a gạch dưới bê a còng example chấm org.", "got": "Gửi a_b@example.org.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_16 / nghe_ngay

```json
{"text": "Gửi a-b@example.net.", "expected": "Gửi a gạch ngang bê a còng example chấm net.", "got": "Gửi a-b@example.net.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_16 / studio

```json
{"text": "Gửi a-b@example.net.", "expected": "Gửi a gạch ngang bê a còng example chấm net.", "got": "Gửi a-b@example.net.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_17 / nghe_ngay

```json
{"text": "Gửi an+test@example.com.", "expected": "Gửi an cộng test a còng example chấm com.", "got": "Gửi an và test@example.com.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_17 / studio

```json
{"text": "Gửi an+test@example.com.", "expected": "Gửi an cộng test a còng example chấm com.", "got": "Gửi an cộng test@example.com.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_18 / nghe_ngay

```json
{"text": "Gửi a12@example.org.", "expected": "Gửi a một hai a còng example chấm org.", "got": "Gửi a12 example.org.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_18 / studio

```json
{"text": "Gửi a12@example.org.", "expected": "Gửi a một hai a còng example chấm org.", "got": "Gửi a12 example.org.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_19 / nghe_ngay

```json
{"text": "Mở https://sub.example.com.", "expected": "Mở sub chấm example chấm com.", "got": "Mở đường dẫn.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_19 / studio

```json
{"text": "Mở https://sub.example.com.", "expected": "Mở sub chấm example chấm com.", "got": "Mở đường dẫn.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_20 / nghe_ngay

```json
{"text": "Mở ftp://example.net.", "expected": ["Mở ép tê pê hai chấm gạch chéo gạch chéo example chấm net.", "Mở example chấm net."], "got": "Mở ftp:example.net.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### url_email_20 / studio

```json
{"text": "Mở ftp://example.net.", "expected": ["Mở ép tê pê hai chấm gạch chéo gạch chéo example chấm net.", "Mở example chấm net."], "got": "Mở ftp:example.net.", "note": "Địa chỉ ví dụ thuộc example.com/org/net; cần còn thông tin tên miền và các ký hiệu cần đọc."}
```

### vocalization_02 / nghe_ngay

```json
{"text": "Áaaaa!", "expected": ["á… a!", "á... a!", "á!"], "got": "á… á!", "note": "Nhiều cách ghi tiếng kéo dài hợp lý; chấp nhận âm rút gọn hoặc tách âm có dấu nghỉ."}
```

### vocalization_02 / studio

```json
{"text": "Áaaaa!", "expected": ["á… a!", "á... a!", "á!"], "got": "á… á!", "note": "Nhiều cách ghi tiếng kéo dài hợp lý; chấp nhận âm rút gọn hoặc tách âm có dấu nghỉ."}
```

### vocalization_16 / nghe_ngay

```json
{"text": "Hihihi!", "expected": "hi hi hi!", "got": "hy hy hy!", "note": "Nhiều cách ghi tiếng kéo dài hợp lý; chấp nhận âm rút gọn hoặc tách âm có dấu nghỉ."}
```

### vocalization_16 / studio

```json
{"text": "Hihihi!", "expected": "hi hi hi!", "got": "hy hy hy!", "note": "Nhiều cách ghi tiếng kéo dài hợp lý; chấp nhận âm rút gọn hoặc tách âm có dấu nghỉ."}
```

### vocalization_20 / nghe_ngay

```json
{"text": "[thở dài]", "expected": ["hầy.", "hầy…", "hầy..."], "got": "[thở dài]", "note": "Cue thở dài được đọc bằng từ thường của Studio."}
```

### game_01 / nghe_ngay

```json
{"text": "Đạt Lv.5.", "expected": ["Đạt cấp năm.", "Đạt le vồ năm.", "Đạt level năm."], "got": "Đạt le-vồ 5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_01 / studio

```json
{"text": "Đạt Lv.5.", "expected": ["Đạt cấp năm.", "Đạt le vồ năm.", "Đạt level năm."], "got": "Đạt le-vồ 5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_02 / nghe_ngay

```json
{"text": "Đạt Lv.10.", "expected": ["Đạt cấp mười.", "Đạt le vồ mười.", "Đạt level mười."], "got": "Đạt le-vồ 10.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_02 / studio

```json
{"text": "Đạt Lv.10.", "expected": ["Đạt cấp mười.", "Đạt le vồ mười.", "Đạt level mười."], "got": "Đạt le-vồ 10.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_03 / nghe_ngay

```json
{"text": "Đạt LV 20.", "expected": ["Đạt cấp hai mươi.", "Đạt le vồ hai mươi.", "Đạt level hai mươi."], "got": "Đạt le-vồ hai mươi.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_03 / studio

```json
{"text": "Đạt LV 20.", "expected": ["Đạt cấp hai mươi.", "Đạt le vồ hai mươi.", "Đạt level hai mươi."], "got": "Đạt le-vồ hai mươi.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_04 / nghe_ngay

```json
{"text": "Đạt level 7.", "expected": ["Đạt level bảy.", "Đạt le vồ bảy."], "got": "Đạt le-vồ bảy.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_04 / studio

```json
{"text": "Đạt level 7.", "expected": ["Đạt level bảy.", "Đạt le vồ bảy."], "got": "Đạt le-vồ bảy.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_05 / nghe_ngay

```json
{"text": "Thưởng x2.", "expected": ["Thưởng nhân hai.", "Thưởng gấp hai."], "got": "Thưởng nhân 2.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_05 / studio

```json
{"text": "Thưởng x2.", "expected": ["Thưởng nhân hai.", "Thưởng gấp hai."], "got": "Thưởng nhân 2.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_06 / nghe_ngay

```json
{"text": "Thưởng ×3.", "expected": ["Thưởng nhân ba.", "Thưởng gấp ba."], "got": "Thưởng nhân 3.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_07 / nghe_ngay

```json
{"text": "Thưởng 4x.", "expected": ["Thưởng nhân bốn.", "Thưởng gấp bốn."], "got": "Thưởng 4 lần.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_07 / studio

```json
{"text": "Thưởng 4x.", "expected": ["Thưởng nhân bốn.", "Thưởng gấp bốn."], "got": "Thưởng 4 lần.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_08 / nghe_ngay

```json
{"text": "Cộng +10 STR.", "expected": ["Cộng mười sức mạnh.", "Cộng cộng mười ét tê rờ.", "Cộng cộng mười ét ti a."], "got": "Cộng +10 <en>S T R</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_08 / studio

```json
{"text": "Cộng +10 STR.", "expected": ["Cộng mười sức mạnh.", "Cộng cộng mười ét tê rờ.", "Cộng cộng mười ét ti a."], "got": "Cộng cộng mười <en>S T R</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_09 / nghe_ngay

```json
{"text": "Cộng +5 DEX.", "expected": ["Cộng năm khéo léo.", "Cộng cộng năm đê e ích.", "Cộng cộng năm đi i éc."], "got": "Cộng +5 <en>D E X</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_09 / studio

```json
{"text": "Cộng +5 DEX.", "expected": ["Cộng năm khéo léo.", "Cộng cộng năm đê e ích.", "Cộng cộng năm đi i éc."], "got": "Cộng cộng năm <en>D E X</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_10 / nghe_ngay

```json
{"text": "Cộng +3 INT.", "expected": ["Cộng ba trí tuệ.", "Cộng cộng ba i en tê.", "Cộng cộng ba ai en ti."], "got": "Cộng +3 <en>I N T</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_10 / studio

```json
{"text": "Cộng +3 INT.", "expected": ["Cộng ba trí tuệ.", "Cộng cộng ba i en tê.", "Cộng cộng ba ai en ti."], "got": "Cộng cộng ba <en>I N T</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_11 / nghe_ngay

```json
{"text": "Máu 3/4.", "expected": ["Máu ba trên bốn.", "Máu ba phần tư."], "got": "Máu 3 trên 4.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_11 / studio

```json
{"text": "Máu 3/4.", "expected": ["Máu ba trên bốn.", "Máu ba phần tư."], "got": "Máu 3 trên 4.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_12 / nghe_ngay

```json
{"text": "Mana 1/2.", "expected": ["Mana một trên hai.", "Mana một phần hai.", "Ma-na một trên hai."], "got": "Mana 1 trên 2.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_12 / studio

```json
{"text": "Mana 1/2.", "expected": ["Mana một trên hai.", "Mana một phần hai.", "Ma-na một trên hai."], "got": "Mana 1 trên 2.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_13 / nghe_ngay

```json
{"text": "Tỉ số 2:1.", "expected": ["Tỉ số hai một.", "Tỉ số hai trên một."], "got": "Tỉ số 2 1.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_13 / studio

```json
{"text": "Tỉ số 2:1.", "expected": ["Tỉ số hai một.", "Tỉ số hai trên một."], "got": "Tỉ số 2 1.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_14 / nghe_ngay

```json
{"text": "HP +20.", "expected": "Hát pê cộng hai mươi.", "got": "hát pê +20.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_15 / nghe_ngay

```json
{"text": "MP -5.", "expected": ["Em pê trừ năm.", "Em pi trừ năm."], "got": "mờ pê trừ 5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_15 / studio

```json
{"text": "MP -5.", "expected": ["Em pê trừ năm.", "Em pi trừ năm."], "got": "mờ pê trừ 5.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_16 / nghe_ngay

```json
{"text": "ATK 100.", "expected": ["A tê ca một trăm.", "Ây ti cây một trăm.", "Tấn công một trăm."], "got": "<en>A T K</en> một trăm.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_16 / studio

```json
{"text": "ATK 100.", "expected": ["A tê ca một trăm.", "Ây ti cây một trăm.", "Tấn công một trăm."], "got": "<en>A T K</en> một trăm.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_17 / nghe_ngay

```json
{"text": "DEF 50.", "expected": ["Đê e ép năm mươi.", "Đi i ép năm mươi.", "Phòng thủ năm mươi."], "got": "<en>D E F</en> năm mươi.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_17 / studio

```json
{"text": "DEF 50.", "expected": ["Đê e ép năm mươi.", "Đi i ép năm mươi.", "Phòng thủ năm mươi."], "got": "<en>D E F</en> năm mươi.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_18 / nghe_ngay

```json
{"text": "EXP +100.", "expected": ["Kinh nghiệm cộng một trăm.", "E ích pê cộng một trăm.", "I éc pi cộng một trăm."], "got": "<en>E X P</en> +100.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_18 / studio

```json
{"text": "EXP +100.", "expected": ["Kinh nghiệm cộng một trăm.", "E ích pê cộng một trăm.", "I éc pi cộng một trăm."], "got": "<en>E X P</en> cộng một trăm.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_19 / nghe_ngay

```json
{"text": "Tăng 10% ATK.", "expected": ["Tăng mười phần trăm tấn công.", "Tăng mười phần trăm a tê ca."], "got": "Tăng 10% <en>A T K</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_19 / studio

```json
{"text": "Tăng 10% ATK.", "expected": ["Tăng mười phần trăm tấn công.", "Tăng mười phần trăm a tê ca."], "got": "Tăng 10% <en>A T K</en>.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_20 / nghe_ngay

```json
{"text": "Hạng S+.", "expected": ["Hạng ét cộng.", "Hạng ét plus."], "got": "Hạng S+.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

### game_20 / studio

```json
{"text": "Hạng S+.", "expected": ["Hạng ét cộng.", "Hạng ét plus."], "got": "Hạng S cộng.", "note": "Câu trung tính tự đặt; đọc theo thói quen tiếng Việt phổ biến."}
```

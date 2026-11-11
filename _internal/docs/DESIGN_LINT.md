# design_lint - đo thiết kế trên ảnh đã vẽ

Việc 10 của bản soát thiết kế 10-11. Các cổng cũ kiểm luật trên mã nguồn (regex: đúng token, đúng hàm) và so ảnh hôm nay
với ảnh vàng hôm qua (Roborazzi). Ảnh vàng xấu thì test vẫn xanh; không phép đo nào chạy trên ảnh đã vẽ của Android.
`scripts/design_lint.py` đo chính điểm ảnh của cả ba nền tảng, và đọc cây UI mà bộ chụp ghi cạnh ảnh.

## Chạy

Từ `_internal`:

```
runtime/.venv/Scripts/python.exe -X utf8 scripts/design_lint.py                       # Android + Qt (nếu đã có build/d2shots)
runtime/.venv/Scripts/python.exe -X utf8 scripts/design_lint.py --web <thư mục ảnh gallery>
runtime/.venv/Scripts/python.exe -X utf8 scripts/design_lint.py --json out.json --audit-cases
runtime/.venv/Scripts/python.exe -X utf8 scripts/design_lint.py --android mobile/android/app/build/design_lint --qt desktop_qt/build/d2shots --json fresh.json
```

- Ảnh Android: `mobile/android/app/src/test/snapshots/*.png` (Roborazzi, 3 px / dp).
- Ảnh/cây vừa chụp: `mobile/android/app/build/design_lint/*.{png,tree.json}`. Dùng `--android` như trên để đo bước 2;
  ảnh vàng trong `src/test/snapshots` dành cho bước 1, không ghép với cây của khung mới.
- Ảnh Qt: `desktop_qt/build/d2shots/*.png` (WidthTests, px logic = dp). Không có trong repo: dựng bằng `build.bat` hay check
  `qt-tests` của cổng phát hành; `--qt <thư mục>` để đọc chỗ khác.
- Ảnh web: `npm run gallery:shots` rồi `--web <thư mục>`; cổng phát hành chưa chụp web cho máy này.
- Mặc định chỉ BÁO CÁO (exit 0 khi đo được); `--strict` thoát 1 khi còn ảnh đỏ, ngoại lệ thừa hoặc ảnh thiếu cây UI.
  Lỗi đo / không có ảnh: exit 2. `--no-trees` chỉ chạy bước 1; không phải bằng chứng xanh của luật cây.
- `--workers 1..4`, tối đa bốn tiến trình, dùng chung cho lượt ảnh và lượt cây. Thời gian và số đỏ từng luật nằm trong báo cáo JSON; không tính thời gian dựng/chụp.

## Luật

Luật trên ảnh (bước 1, không cần đổi app). Nền của từng hàng là trung vị hàng; "mực" là điểm khác nền hàng > 40 (tổng ba
kênh). Dải = các hàng có mực liền nhau; cụm = cột mực tách nhau >= 8 dp.

| Luật | Đo gì | Đỏ khi |
|---|---|---|
| R4 | rãnh công tắc (khối bo tròn 18-40 dp, rộng 1,4-2,2 lần cao, có núm `--switch-thumb`) | rãnh bật lệch `--focus` ΔE >= 3 (rãnh `--switch-off` là công tắc tắt) |
| R4 | nút nền `--accent` (khối hổ phách đặc, mép thẳng, rộng >= 1,5 cao; tính cả hổ phách mờ của nút bị vô hiệu, không tính `--accent-soft`) | > 1 nút một màn; cao ngoài 44-56 dp trên cả ba nền tảng theo yêu cầu soát 10-11 |
| R5 | lưới lựa chọn: hàng >= 3 ô cùng cỡ, bước đều, rồi hàng sau ít ô hơn (thẳng cột hay căn giữa) | hàng cuối thiếu ô |
| R6 | mép trái các dải chữ trong mỗi vùng (tách vùng ở cột đổi màu trên >= 80 % chiều cao) | > 3 trục (mép mực cách nhau <= 3 dp là một trục: lề chữ cái 1-3 dp); hay một dòng căn giữa cạnh >= 2 dòng căn lề |
| R7 | neo trong nhóm trạng thái (`design_lint_groups.json`): đỉnh/mép trái bìa, tâm x/y nút phát, thanh tiến độ, đỉnh/mép trái/cao nút chính, cao ảnh | lệch mốc chung của nhóm > 1 dp |
| R8 | mép sheet (nền hàng đổi giữa hai mặt tràn ngang cao >= 24 dp), đáy màn, mảnh dòng còn lại (dải <= 6 dp toàn chấm) | mép cắt qua dòng chữ (trừ dòng mờ < 35 % độ đậm, tức nằm trong dải mờ) |
| R10 | dải ngang không mực trên nền màn; khổ >= 600 dp: dải dọc không mực | > 40 % chiều cao / bề ngang |

Luật trên cây UI (bước 2, `scripts/design_lint_tree.py`):

| Luật | Đỏ khi |
|---|---|
| R1 | nhóm anh em có `selected` không thuộc tab một hàng, choice (2-5 mục một hàng), hay list (mỗi dòng một mục), hoặc không chọn đúng một mục; vai native RadioButton được chuẩn hoá thành choice/list theo hình học, vai thiếu là đỏ |
| R3 | khe dọc giữa hai khối anh em liền nhau cùng cột ngoài {0, 4, 8, 12, 16, 24, 32, 48, 64} ± 0,5 dp; khe > 64 vẫn đỏ |
| R8 | mép cắt xuyên hộp một dòng chữ; hai hộp chữ chồng nhau kể cả nút nổi nằm trong hộp đọc; bỏ quan hệ cha-con của cùng nội dung |
| R9 | cặp ảnh `design_lint_parity.json` (gắn id của `ui_parity_pairs.json`): cùng nhãn mà khác vai / kiểu / số dòng / token chữ hoặc nền, hay cao lệch > 4 dp |
| R11 | cỡ chữ ngoài {12, 14, 16, 18, 20, 24, 32} hay dưới 12; >= 2 hàng bấm được cùng cha trong một cột mà tên hàng khác cỡ / đậm / màu |
| R14 | chữ hiện trên nút / tab / mục menu / hộp chọn quá 4 chữ (bỏ số và đơn vị: dB, Hz, MB, %, phút...), hay không có cả chữ lẫn mô tả trợ năng; nút chỉ có biểu tượng thì mô tả trợ năng không bị đếm chữ, hàng danh sách mang dữ liệu không xét |

Cây UI do bộ chụp ghi, đơn vị dp, gốc toạ độ là góc ảnh:

- Android: `vn.abook.player.ui.snapshot.captureRoboImage` (thay import của hàm Roborazzi, gọi y như cũ) chụp rồi ghi
  cặp `app/build/design_lint/<tên ảnh>.png` + `.tree.json` từ cây ngữ nghĩa chưa gộp của đúng cửa sổ: hộp đầy đủ + phần còn thấy,
  vai, chữ, cỡ chữ sp, độ đậm, màu nếu API cung cấp, số dòng và hộp từng dòng, chọn / bật, bấm được. Việc verify ảnh vàng vẫn chạy như cũ.
- Qt: `qtUiTree.save(path, item)` (`desktop_qt/tests/uitree.h`) sau mỗi lần lưu ảnh `build/d2shots/<tên>.png`, ghi
  `<tên>.tree.json` cạnh ảnh: hộp, `Accessible.role`, chữ, font, `lineCount`, hộp từng dòng, màu, `checked` / `selected` / `current`.

Cặp mới có SHA-256 của PNG; sai băm là lỗi đo. `tree_coverage` báo ảnh có/thiếu sidecar theo nền tảng;
`tree_measurements` đếm số nút thật có từng trường. Thiếu cây hoặc thiếu trường là **chưa đo**, không phải luật xanh.
R9 chỉ ghép nhãn chung đã quan sát; kiểu `filled`/`underline`/`plain` và nền được đo bổ sung từ vùng điểm ảnh của điều khiển.
Màu không khớp token ở ΔE < 3 giữ nguyên hex. Web chưa có cây nên chỉ có luật ảnh.

## Ngoại lệ

`scripts/design_lint_exceptions.json`: mỗi mục đúng ba khoá `image` (`<nền tảng>/<tệp>`, không mẫu), `rule`, `reason`.
Không có ngưỡng nới chung. Ảnh hết đỏ thì máy báo "ngoại lệ thừa" (chế độ chặn coi là FAIL) - xoá mục ấy. Chỉ ảnh đã quét
mới bị xét thừa (chạy thiếu Qt thì ngoại lệ Qt không tính).

## Nghiệm thu

`scripts/design_lint_audit_cases.json` ghi các ảnh mà soát 10-11 chỉ ra lỗi cùng luật phải bắt; `--audit-cases` in bảng
luật -> ảnh -> đỏ?. Trên cây trước khi sửa mọi dòng phải đỏ; sau các việc 1-9 của báo cáo dòng ấy phải xanh và được xoá.
Kiểm lực hai phía bằng ảnh giả / cây giả ở `tests/test_design_lint.py` (ảnh tốt xanh, ảnh hỏng cố ý đỏ, từng luật).

Giới hạn đã biết của phép đo trên ảnh: chữ bị cắt ở mép một vùng cuộn mà dưới đó là khoảng trống (không phải mép sheet hay
đáy màn) chỉ thấy được trên cây UI (R8 cây); khổ rộng mà khung nội dung chỉ dồn trái 20-35 % không vượt ngưỡng 40 % của R10;
popover hẹp trên nền khác màu chưa có mép sheet tràn ngang nên R8 ảnh không xét.

## Cổng phát hành

Check `design-lint` của `scripts/release_gate.py` chạy sau `android-unit` và `qt-tests`, ở chế độ báo cáo
(`DESIGN_LINT_BLOCKS = False`): số ảnh đỏ theo luật vào bảng gate, không chặn. Lead bật chặn sau khi `dev/design1` gộp.
Gate ưu tiên cặp Android vừa chụp trong build; khi chưa có thì báo cáo trên ảnh vàng và ghi rõ độ phủ cây bằng 0.
Chế độ chặn còn từ chối thiếu Android/Qt hoặc thiếu cây; ảnh web cần chỉ định bằng `--web` khi đo cả ba nền tảng.

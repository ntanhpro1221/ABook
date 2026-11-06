# Cân bằng giọng

Quyết định chủ sách 06-11: “bỏ hết trừ cân bằng tốc độ”. Mỗi preset là một giọng nguyên bản.
Không đổi cao độ, formant, quãng giọng hay biên độ theo cảm xúc, tuổi hoặc vai người kể.
Hai nhân vật chung preset có cùng chất giọng. Chỉ giữ khoảng nghỉ cấu trúc: thoại 170 ms, nội tâm 210 ms, kể 230 ms, cuối đoạn 380 ms, đổi cảnh 1500 ms, cuối chương 0 ms. Không bù theo cảm xúc/cường độ/lời dẫn thoại; không thu lại câu. Trần im lặng mép 0,35 s và nội bộ 0,65 s giữ nguyên.

## Hằng số

Nguồn duy nhất: `abook/assets/voice_balance.json`, hợp đồng version 2.
Khoá là `<engine>@<version>/<preset>`, ví dụ `vieneu@3.8.3/Ngọc Linh`.
Mỗi bản ghi VieNeu chỉ có `r`, `o_db`, `ref_lufs`.
Supertonic thêm `engine_speed` vì máy đọc tự điều khiển tốc độ; `r = 1`.
Khoá thiếu, khoá có hậu tố biến thể hoặc trường ngoài hợp đồng đều là lỗi.
Không có chuyển đổi dữ liệu hoặc hỗ trợ khoá cũ. Dự án cần được tạo sạch sau khi đổi policy hash.

Tốc độ WSOLA = `x * r`. Không thay số `r` trong lượt cân bằng độ to này.
WSOLA giữ nguyên thuật toán và biên tốc độ; tiếng bật hơi chuyên biệt giữ hợp đồng số mẫu riêng.

Gain câu (dB) = `L_lufs + o_db - ref_lufs`.
Không đo câu để đổi gain, không phụ thuộc chương hay sách, không có line offset.
Nhãn soft/normal/loud, cảm xúc, cường độ và người kể không làm đổi gain.
Trần đỉnh câu vẫn có quyền hạ cả câu để tránh quá mức; phần hạ được ghi trong `peak_limited_db`.
Ghép các phần đã áp gain không áp lại gain lần nữa.

`ref_lufs` là mức trung bình bản thô sau tempo. Nó là neo kỹ thuật, không phải đích cảm nhận.
`o_db` được khớp bằng ISO 532-1 stationary, cùng meter được vendored trong `abook/_vendor/zwicker`.
RMS, K-weighted và A-weighted chỉ là số tham khảo trong báo cáo; không tham gia fit.

## Phân vai

Phân tích cả sách xong mới phân vai. Khi ấy đã biết số câu và chương xuất hiện của từng người.
Nhân vật có tên và NPC cục bộ được xếp theo số câu giảm dần, rồi tên để phân xử bằng nhau.
Preset chưa dùng được cấp trước preset đã dùng; trong nhóm còn trống dùng phái và hạng do chủ sách
ghi trong `voice_rank.json`. Không dùng tuổi để biến đổi hoặc chọn bậc âm thanh.
Giọng người kể và các người kể khác được giữ riêng. Giọng đã ghim được giữ chỗ trước lượt phân vai.
Khi hết preset, giảm trùng người cùng chương và cân số người đang dùng preset.
Nhóm vô danh được phân sau các nhân vật có danh tính; không biết số câu của từng cá nhân bên trong nhóm.
Một người mới được thêm sau khi đã khoá sách chỉ dùng phần còn trống, không tự phân lại cả dàn vai.
Mai Anh không phân vai và không có hạng hay số đo mới trong lượt này.

## Bộ đo trung tính

`scripts/calibrate_voice_table.py:sentences()` dựng đúng 40 câu trung tính từ câu đo trong repo,
không lấy chữ của sách kiểm định. Mỗi câu có hai seed cố định 730001 và 730002.
Mọi giọng dùng cùng câu, ghép cặp theo câu. Model phải đúng revision và hash đã ghim.

WAV thô là kết quả preset nguyên bản từ `generate_one`, chưa qua tempo/gain của Studio.
Bộ fit áp WSOLA đúng một lần theo `r`, không thay phổ hoặc cao độ.
`scripts/fit_voice_constants.py` tìm gain đạt trung bình 73 phon và đo lại waveform sau khi nhân gain.
Sai số giữa phép tìm nghiệm và phép đo lại phải dưới 0,002 phon.
Khoảng tin cậy 95% lấy 2.000 bootstrap theo 40 câu; hai seed của một câu luôn đi cùng nhau.
SHA-256 của mọi take, danh sách câu, model và protocol nằm ngoài repo cùng bằng chứng fit.
`scripts/export_voice_constants.py` từ chối xuất nếu chưa đủ 80 take cho một khoá.
Sách tuyệt đối không được dùng để fit hằng số.

## Kiểm định sách và vòng hiệu chỉnh

Chỉ đọc SQLite nguồn với URI `mode=ro`; kiểm hash WAV trước và sau.
Bản kiểm định và sản phẩm dùng gain bảng và master cố định +5 dB cho mọi chương/mọi sách.
Mức này chọn từ bộ hiệu chuẩn 73 phon, dự đoán sau master khoảng 77,8 phon, trước khi đo sách.
Limiter true-peak FFmpeg `alimiter` chạy ở 4 lần sample rate, `level=false`, bù latency,
trần lấy từ `true_peak_db`; chỉ envelope quanh đỉnh được hạ, không hạ gain cả chương.
Kênh đồng hồ gain hằng nhỏ đi qua limiter liên kết để đo phần thời gian bị hạ và mức hạ lớn nhất;
kênh này bỏ trước mã hóa MP3. Báo cáo đếm giảm trên 0,001 dB (dung sai float/resample).
Không dùng loudnorm để đưa từng chương về cùng LUFS. Mốc câu và từ phải theo đúng MP3 đã xuất.
Độ lệch LUFS chương chỉ cảnh báo; các gate peak, clipping, dropout và mối nối vẫn giữ.

PASS cần độ trải trung bình giữa các giọng đủ ít nhất 12 câu <= 1,5 phon ở MỖI sách,
và mọi chương cách trung vị chương của sách <= 1,0 phon. Báo cáo CI 95%, giọng thưa,
độ trải chương, số dự đoán so với đo thật và thời gian detector. Không nới ngưỡng hay fit lại theo sách.

Hai sách đã PASS sau khi thay phép cân peak riêng từng chương bằng master cố định +5 dB:
Your Story trải giọng 0,414 phon / trải chương 0,481; Pain 0,876 / 0,826.
Đã gỡ kế hoạch target chương, bù giọng/chương theo sách, các vòng master lại, cache bản nền và journal công bố.
Sản phẩm chỉ đo MP3 cuối một lần, lưu `output/reports/levelQa.json`, cảnh báo và không sửa audio.
Checksum MP3 và mốc câu/giọng khóa phép đo; resume giữ cùng nguồn dùng lại báo cáo.
Receipt `.mp3.levels.json` chỉ lưu hash và mốc câu của MP3 cuối, cần cho chữ đọc theo; không chứa bù mức.
Nhãn volume vẫn nằm trong schema, prompt, ledger phân tích và kịch bản xuất để giữ dữ liệu huấn luyện/gold.
Detector không lọc bỏ câu chỉ vì nhãn volume: nhãn này không còn tác động âm thanh.

## Các nền tảng

Web, Qt và Android chỉ hiện tên preset; khi hai người chung giọng, giao diện nói họ sẽ nghe giống nhau.
Không còn nhãn hay điều khiển chỉnh trầm/sáng. Tài liệu parity sinh từ `scripts/ui_parity.py`
và `scripts/ui_parity_qt.py`.
Nghe ngay dùng bảng riêng tại `readaloud/loudness.py` và `readaloud/VoiceGain.kt`;
đã đo 34 giọng Turbo/Nano (trừ Mai Anh), mỗi giọng 40 câu × hai seed sau bước bù câu ngắn, cùng meter ISO và đích 73 phon. Hai nền tảng dùng cùng gain ISO, không làm tròn 0,1 dB như bảng LUFS cũ. Bảng LUFS vẫn là mốc bù clip và mức phát cho giọng chưa đo ISO. Không lấy mức Studio thay số đo của Turbo/Nano.

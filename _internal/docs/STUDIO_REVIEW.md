# "Việc cần anh" - người can thiệp vào sản xuất mà không chặn dây chuyền

Chủ sách, 27-09: *"quy trình sản xuất phải cho phép người dùng can thiệp ở mức sâu một cách dễ dàng, đơn giản, trên mọi
khía cạnh, tại mọi thời điểm mà có thể cần người dùng, thậm chí sort các phần cần can thiệp theo mức độ để người dùng can
thiệp ít nhất mà lại hiệu quả nhất, thậm chí đưa ra các option để chọn, mô tả vấn đề đang cần can thiệp. nhưng cũng không
phải theo dạng luôn bắt người dùng phải thao tác chọn chọn mới sang bước tiếp theo"*.

Vì sao cần: model không bao giờ đúng 100% (652/1.827 câu gold có hơn một người nói hợp lý; cảm xúc là cảm nhận), nhưng nó
BIẾT câu nào không chắc - bộ chấm đã hiệu chỉnh: tin cậy >= 0,95 đúng 100%, < 0,5 chỉ đúng 33% (ANALYSIS_RESEARCH.md).
Người duyệt đúng những câu ấy là cách rẻ nhất để đạt 100% với người nghe.

## Nguyên tắc

1. **Không bao giờ chặn.** Máy luôn tự quyết trước (lựa chọn tốt nhất của nó) và chạy tiếp; AGENTS.md cấm hỏi giữa job.
   Can thiệp là GHI ĐÈ đặt lên quyết định của máy, áp ở ranh giới an toàn gần nhất.
2. **Xếp theo lợi trên mỗi lần bấm**, không theo thứ tự thời gian: `lợi = số câu bị ảnh hưởng x khả năng máy sai x độ chói
   tai`, cộng thưởng **khẩn**: câu SẮP được thu âm đứng trước (sửa trước khi thu thì không tốn thu lại).
3. **Mỗi việc tự giải thích**: vấn đề là gì, vì sao máy nghi ngờ (bằng chứng: câu dẫn, hai nguồn bất đồng, độ tin cậy),
   các lựa chọn kèm độ tin cậy, lựa chọn đang áp, nghe thử (câu mẫu giọng, câu thu thử cách đọc tên).
4. **Gom việc giống nhau**: "Khổng Minh / Gia-cát Lượng là một người?" sửa một lần cho 300 câu; "giọng của Tào Tháo"
   là một việc, không phải 400 việc.
5. **Mọi khía cạnh**, mọi lúc: sau phân tích, sau phân vai, sau thu âm, cả khi sách đã xong (sửa rồi thu lại phần đổi).
6. **Chỉ thu lại phần bị đổi**, tất định: ghi đè gắn đúng câu (stable ID + băm văn bản), vào dấu vân tay stage như mọi
   thay đổi casting, nên dừng/chạy tiếp không đổi kết quả.
7. **Mỗi lần sửa là một nhãn**: xuất thành dòng kiểu gold -> dữ liệu học cho LoRA và bộ chấm, đúng chỗ model yếu nhất (học
   chủ động).

## Danh mục việc

| # | Khía cạnh | Máy nghi ngờ khi | Lựa chọn đưa ra | Áp bằng (đã có trong SQLite?) | Chi phí khi sửa |
|---|---|---|---|---|---|
| 1 | Giọng / giới / tuổi của nhân vật | độ tin cậy giới thấp; hai nhân vật dùng chung giọng (voice_pool_pressure); nhân vật chính mang giọng chung chung | preset + cao độ, nghe thử từng giọng; nam/nữ/chưa rõ; tuổi | `characters.locked_voice_key`, `locked` (giới), `locked_age` - CÓ | thu lại mọi câu của nhân vật |
| 2 | Bí danh: một người hay hai? | hai tên cùng giới, ít khi cùng cảnh, tên này chứa họ/tự của tên kia (Khổng Minh / Gia-cát Lượng, Vân-trường / Quan Vũ) | gộp vào X / để riêng | `character_aliases` - CÓ | thu lại câu của tên bị gộp |
| 3 | Ai nói câu này | tin cậy thấp; bộ chấm và LLM bất đồng; nhãn NPC mà chương có người được gọi tên sau đó; hai đoạn thoại liền nhau (đóng ngoặc -> mở ngoặc, không lời dẫn) cùng một người - 38/42 cặp như thế là máy sai (28-09) | 3 ứng viên hàng đầu + người kể + "người không tên" | bảng ghi đè theo câu - CHƯA | thu lại một câu |
| 4 | Loại đoạn: kể / thoại / nội tâm | "nói thầm", "khen thầm", ngoặc nhấn mạnh, thoại gạch ngang lạ | 3 loại | bảng ghi đè theo câu - CHƯA | thu lại một câu |
| 5 | Cảm xúc, cường độ, nhịp, âm lượng | critic bất đồng; luật host từ chối; tin cậy thấp | vài cảm xúc hàng đầu + nghe thử | bảng ghi đè theo câu - CHƯA | thu lại một câu |
| 6 | Cách đọc tên riêng | tin cậy phiên âm thấp; Whisper nghe tên khác xa (hàng chờ "Cần nghe lại") | 2-3 cách đọc, mỗi cách một câu thu thử | `pronunciations.locked` - CÓ | thu lại mọi câu có tên ấy |
| 7 | Lỗi chữ / văn bản nguồn lạ | Whisper lệch có hệ thống ở cùng một từ; từ không có trong từ điển | sửa chữ (chỉ `spoken_text`, không đụng nguồn) | ghi đè `spoken_text` - CHƯA | thu lại câu có chữ ấy |
| 8 | Bản thu lỗi | hàng chờ "Cần nghe lại" (hỏng, chưa kiểm được, tên lệch) | ổn / thu lại (seed khác) / đổi cách đọc | `listener_audio_acceptances` + danh sách đúc lại - CÓ | thu lại một câu |
| 9 | Truyện ngôi thứ nhất | tỉ lệ "tôi" trong lời kể cao | "tôi" là ai (gợi ý tên) | `voices.first_person_identity` - CÓ (27-09) | phân tích lại |

## Luồng dữ liệu

- Dây chuyền (worker) là nơi DUY NHẤT ghi SQLite của sách. Giao diện ghi YÊU CẦU vào file riêng cạnh sách (như
  `reviews.json` của hàng chờ "Cần nghe lại"); worker đọc và áp ở ranh giới an toàn, ghi `runtime_events` từng lần áp.
- Ghi đè theo câu khoá bằng `stable_id` + `text_sha256`: nguồn đổi thì ghi đè tự rơi (không áp nhầm câu khác).
- Câu chưa thu: áp ngay trước khi thu, không tốn gì. Câu đã thu: vào danh sách đúc lại của ranh giới kế tiếp (đúng cơ chế
  đúc lại đang có), chỉ các câu ấy, rồi dựng lại MP3 của chương.
- Việc được tính lại sau mỗi stage (phân tích, phân vai, thu chương); việc đã xử lý không hiện lại trừ khi bằng chứng đổi.

## Thứ tự làm

1. **Hộp việc chỉ đọc**: dựng danh mục việc 1-2-3-6-8 từ SQLite đang có (độ tin cậy, sổ nhân vật, bí danh, phiên âm, hàng
   chờ), xếp hạng, giải thích, nghe thử. Chưa sửa được, nhưng đo được: bao nhiêu việc, lợi dự kiến bao nhiêu.
2. **Sửa cấp nhân vật** (1, 2, 6): các cột ghim đã có - chỉ thiếu giao diện + đường áp ở ranh giới + đúc lại có chọn lọc.
   - **6 (cách đọc tên) XONG 27-09**: thẻ có câu đã thu để nghe, "Đúng rồi" hoặc gõ cách đọc khác -> `overrides.json`
     (`listener_overrides.py`, file là trạng thái mong muốn, áp lại không làm gì) -> dây chuyền áp lúc khởi động và ở mỗi
     ranh giới chương sau khi phân vai khoá (`pipeline._apply_listener_overrides`): ghim + đặt lại câu đã thu có tên ấy
     trong MỘT transaction (`ProjectDB.apply_listener_pronunciation`), chương đã qua được thu lại ở vòng sau, sách đã xong
     cũng vậy. `cli pronounce` đi cùng đường. Thử trên bản sao Tập 18: "Hailkes" Hain -> Hên-khơ đặt lại 23 câu đã thu ở 4
     chương (70 câu còn lại chưa thu, tự đọc cách mới).
   - **2 (bí danh) sửa được 28-09, bằng đường ghi đè nhóm câu của mục 3** (không cần bảng mới): "Gộp vào X" gán mọi câu
     của tên ít câu hơn cho tên nhiều câu hơn. Trước đó thẻ chỉ bắt cặp khi tên DÀI nói nhiều hơn - bỏ sót trường hợp
     thường gặp nhất (lô 18 cuốn 2: 0 thẻ -> 2 cặp thật, "Tiers" / "Sứa Hắc Ám Tiers", "Kati" / "St. Kati"). Chưa
     làm: ghi bí danh vào sổ nhân vật để câu của chương phân tích SAU tự về đúng người (đụng file khoá).
   - **1 (giới / giọng của nhân vật) sửa được 28-09**: thẻ "Nam hay nữ" và "Chung giọng" -> `overrides.json` mục
     `voices` (nhân vật -> giới, preset hay "để máy chọn", giọng phải tránh) -> `ProjectDB.apply_listener_voice` ở
     ranh giới chương, một transaction. Giọng mới do CHÍNH bộ cấp giọng của bước phân vai chọn, dựng lại từ trạng thái
     sách với mọi người khác giữ nguyên bậc giọng (`character_registry.book_allocator` + `listener_voice_choice`), nên
     không trùng bậc với người cùng chương; mọi câu của người ấy sang giọng mới cùng lúc (`assert_voice_stability` vẫn
     qua), câu đã thu được đặt lại; giới + giọng ghim (`locked`, `locked_voice_key`) cho lô sau. Giọng đang có đã đúng
     giới thì chỉ ghim giới, không thu lại câu nào. Thử trên bản sao lô 18: 9 thẻ giới; "Người Dân" (giọng nữ, 3 câu)
     -> nam: `manh_dung_f100`, đặt lại đúng 3 câu. Màn chọn giọng cụ thể (tab Nhân vật, nút
     "Đổi giọng", `webui/voice_picker.py`) XONG cùng ngày: mọi giọng dùng được, nghe thử, giọng máy gợi ý mỗi giới,
     người CÙNG CHƯƠNG đang dùng giọng gốc ấy - chọn thì POST /voice kèm `preset`, cùng đường áp.
3. **Sửa cấp câu** (3, 4, 5, 7): bảng ghi đè mới trong SQLite (thay đổi `database.py`/`pipeline.py` - kèm test crash/reopen
   như AGENTS.md đòi).
   - **3 (ai nói câu này) XONG 27-09**, không cần bảng mới: thẻ có một nút cho mỗi ứng viên + "Giữ" -> `overrides.json`
     `speakers` (mã câu + băm chữ) -> `ProjectDB.apply_listener_speaker`: câu mượn đúng nhãn và giọng sẵn có của người
     được chọn (`listener_overrides.speaker_target`, dùng chung với giao diện để từ chối tại chỗ), nên "một người một
     giọng" vẫn đúng; thu lại chỉ khi giọng đổi. Thử trên bản sao Tập 18: câu nội tâm chương 734 Người kể -> Nasdell,
     `assert_voice_stability` cả cuốn vẫn qua. Lưu ý: nội tâm hiện vẫn đọc bằng giọng người kể (`tts._spoken_row`), nên
     với câu nội tâm lần thu lại cho ra cùng giọng cho tới khi bản vá "nội tâm = giọng người nghĩ" được áp.
   - **Tab "Kịch bản" XONG 28-09** (`webui/casting_review.py`, `ui/src/studio/ScriptTab.tsx`): hộp việc chỉ đưa chỗ
     máy nghi, tab này cho duyệt CẢ chương - mọi câu thoại/nội tâm có chip người nói bấm đổi được, đi đúng đường ghi đè
     của mục 3 (không có đường ghi thứ hai). Chỗ nghi dùng chung tín hiệu với hộp việc (bộ chấm thứ hai, lượt đối đáp,
     lời gọi); câu "liền nhau cùng người" gợi ý người khác gần nhất vừa nói trước cặp ấy. Xác nhận "Đúng là X" cũng
     ghi thành yêu cầu (= nhãn cho vòng học, bước 4). Thử trên bản sao lô 18 cuốn 2: 43 chương, 31 chỗ nghi. Chương 725: hai
     chỗ nghi đều là lỗi thật (khán giả trầm trồ mà gán cho Louise đang thuyết minh), và đọc quanh chúng thấy thêm hai
     lỗi không tín hiệu nào bắt: câu giới thiệu của Louise gán cho người kể, câu Ali lắp bắp gán cho Louise - lý do tab
     này cần có cạnh hộp việc.
   - Trên đường làm, lộ một lỗi có sẵn: câu bị đặt lại vẫn giữ ứng viên vòng sửa `promoted` của bản thu đã bỏ, và
     recovery lần sau chết ("promoted candidate is not the current segment artifact"). Đã sửa: đặt lại câu xoá lịch sử
     vòng sửa của nó, trong một transaction (`tests/test_a_reset_line_forgets_its_repairs.py`).
   - **4 + 5 (loại đoạn, cảm xúc, cường độ) XONG 28-09**, không cần bảng mới: overrides.json `lines` (mã câu + băm
     chữ -> loại đoạn / cảm xúc / cường độ) -> `ProjectDB.apply_listener_line` ở ranh giới chương, TRƯỚC các yêu cầu
     "ai nói câu này" (lời kể thành lời thoại gán người nói ngay trong cùng lượt; Studio ghi cả hai trong một lần ghi
     file). Cường độ đi qua đúng phép hiệu chỉnh của khâu phân tích (`_calibrated_intensity`). Thành lời kể thì câu về
     người kể và giọng người kể. Giao diện: nhãn cách đọc trên từng câu ở tab Kịch bản.
4. **Vòng học**: xuất mọi lần sửa thành dòng kiểu gold, đưa vào dữ liệu LoRA/bộ chấm; đo model mới trên chính những câu
   người đã sửa.
   - **Xuất nhãn XONG 28-09** (`scripts/model_eval/listener_labels.py`): mọi quyết định của người nghe trong mọi dự án
     (người nói, cách đọc, giới/giọng, cách đọc tên) thành JSONL, kèm nhãn GỐC của máy lấy từ sự kiện áp đầu tiên (sau
     khi áp SQLite chỉ còn nhãn mới), `confirmed` khi người nghe giữ nhãn máy, và ba câu trước/sau làm ngữ cảnh. Nút
     "Chương này đúng" ở cuối mỗi chương trong tab Kịch bản sinh nhãn xác nhận hàng loạt (bản sao lô 18: một lần bấm =
     22 nhãn). Còn làm: đưa nhãn vào dữ liệu LoRA/bộ chấm và đo model trên chính các câu ấy.

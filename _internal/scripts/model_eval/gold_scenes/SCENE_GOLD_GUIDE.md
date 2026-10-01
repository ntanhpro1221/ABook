# Đáp án CẢNH cho nhạc nền (Pha 2 - docs/MUSIC_RESEARCH.md, khung ở docs/MUSIC_SELECTION_MODEL.md)

Mục đích: đo cách máy chia chương thành đoạn và đoán không khí từng đoạn - để chọn nhạc nền. Không dạy model (đáp án làm
theo nhu cầu, luật 20-09: vài chương mỗi thể loại, nói rõ dùng để làm gì).

## Đơn vị

- **Đoạn** = khúc liền mạch MỘT nhạc nền hợp suốt: cùng không khí, cùng nhịp, cùng chức năng. Dài tối thiểu ~1 phút đọc
  (~200 tiếng/âm tiết - giọng đọc ~3,5 tiếng/giây). Ngắn hơn thì là **điểm nhấn** của đoạn chứa nó, không phải đoạn riêng - nhạc nền
  không đổi bài vì một câu la hay một trận phục kích ba câu.
- Ngoại lệ: khúc ngắn ở CUỐI chương đổi hẳn không khí (cao trào treo) vẫn là đoạn - nhạc phải đổi theo.
- `start=soft` ở đầu ghi chú: ranh giới mở đoạn này là TUỲ - máy gộp hai đoạn cũng không tính sai (đổi sắc thái nhẹ,
  một nhạc nền vẫn hợp được). Ranh giới không ghi soft là BẮT BUỘC.
- **Điểm nhấn** (`accent`): biến cố ngắn đáng một dấu nhấn (trống, chiêng, ngắt nhạc) - ghi riêng, không cắt đoạn.
- Ranh giới đặt ở câu ĐẦU của đoạn mới. Tiêu đề chương thuộc đoạn đầu tiên. Chú thích cuối chương (▲, [1]...) là đoạn
  `chu_thich` - không nhạc.
- Thơ chen giữa ("Đời sau có thơ rằng") ~1 phút trở lên là đoạn riêng chức năng `tho_binh` (nhạc lắng, hay im). Thơ / câu
  đối NGẮN hơn: dòng `duck a-b` (hạ nhạc) trong đoạn chứa nó - khác `accent` (nhấn).
- LEO THANG trong cùng không khí (căng -> căng hơn) là `accent`; ĐỔI LOẠI không khí (ấm -> dữ, đánh -> khóc) mới là đoạn mới.
- Giữa chương, khúc 150-200 tiếng đổi hẳn không khí CẢ HAI phía được làm đoạn riêng, ghi `start=soft`.

## Thang chấm (theo cảm nhận NGƯỜI NGHE truyện, không theo từng câu)

- `V` vui/buồn: -2 rất buồn/khổ, 0 trung tính, +2 rất vui/ấm.
- `E` năng lượng: -2 lắng/mệt/tĩnh, 0 vừa, +2 dồn dập/hỗn loạn.
- `T` căng thẳng: -2 thả lỏng/an toàn, 0 bình thường, +2 hiểm nguy/hồi hộp tột độ.
- `gems`: nhãn chính, có thể thêm nhãn phụ `chính/phụ` (máy trúng một trong hai là đúng); `none` khi không có cảm xúc
  nhạc rõ (dặn dò, hành chính - nhạc nền trung tính hay im). Một trong wonder, transcendence, tenderness, nostalgia, peacefulness, power, joyful_activation, tension, sadness
  (nhãn đọc được - kỳ diệu, siêu thoát, dịu dàng, hoài niệm, bình yên, hùng tráng, hân hoan, căng thẳng, buồn).
- `function`: mo_dau, hanh_dong, doi_thoai, noi_tam, ta_canh, cao_trao, tho_binh, chuyen_canh, ket, chu_thich.
- `setting`: bối cảnh ngắn (chiến trường đêm, cung điện, quán rượu...) - cho trục phong cách.
- `music`: `co` (nên có nhạc), `nhe` (nhạc rất nhẹ / thưa), `im` (nên im lặng).
- `tone=mia` / `tone=hai` ở đầu ghi chú khi giọng văn châm biếm / hài - quyết định PHONG CÁCH nhạc dù V/E/T giống đoạn nghiêm.
- V chấm theo cảm nhận NGƯỜI NGHE về cảnh - tức màu nhạc cảnh cần (cảnh hài thì dương dù nhân vật đang đau); với cảnh
  nghiêm thì theo nhân vật tiêu điểm, không theo phe người đọc thích. (Đổi 02-10 theo người chấm B2.)
- Năng lượng nhảy >= 1,5 bậc và giữ (hài nhẹ -> hài náo loạn) cũng là đổi loại, kể cả cùng giọng.

## Dạng file

`gold_scenes/<truyện>/<chương>.txt`, chú thích bắt đầu bằng `#`; mỗi đoạn một dòng, các trường cách nhau bằng ` | `:

    scene 3-9 | V=-1 E=2 T=2 | gems=tension | function=hanh_dong | setting=chiến trường sông đêm, biển lửa | music=co | ghi chú
    accent 43-44 | Triệu Vân phục kích

    duck 117-121 | thơ ngắn - hạ nhạc

V/E/T cho phép nửa bậc (đáp án phân xử là trung bình hai người chấm). Số là `seq` của câu trong dây chuyền (cột thứ hai của bản xuất `seq kind speaker emotion text`).

## Soát

A: Claude soạn. B: agent soát đối kháng (được phép - ngoại lệ 20-09) - chỉ ra ranh giới lệch, thang lệch, nhãn sai; bất đồng
ghi vào `ADJUDICATION.md` cùng thư mục. Hai người chấm độc lập trên cùng chương còn cho biết độ ĐỒNG THUẬN - trần mà máy
không thể vượt.

## Phân xử (02-10)

Ranh giới cả hai người cùng đặt (lệch <= 20 giây) -> bắt buộc; nhảy thời gian / đổi nơi ghi rõ trong chữ -> bắt buộc; chỉ một người đặt -> `start=soft`; khúc ngắn hơn luật cho
phép -> bỏ (thành `accent` / `duck`). V/E/T = trung bình hai người. Bản riêng của từng người giữ ở `scratchpad` của lượt
chấm, độ đồng thuận ghi ở docs/MUSIC_RESEARCH.md - là TRẦN của mọi cách máy chia.

Độ đồng thuận hai người chấm (trước phân xử): lượt 1 (Tam quốc 050, Tắt đèn 020/021/024, hướng dẫn bản 1) Pk 0,15,
r V/E/T 0,46/0,73/0,79; lượt 2 (YMP 248, Lucien 351/381, hướng dẫn bản 2) Pk 0,13, r V/E/T 0,66/0,79/0,78.

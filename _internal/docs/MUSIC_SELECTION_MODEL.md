# Mô hình chọn nhạc nền cho sách nói

Chủ sách 02-10: "chọn nhạc không chỉ có cảm xúc mà còn nhiều yếu tố nữa như là nhịp độ, phong cách, năng lượng... phải xây
dựng một bộ lý thuyết logic gốc vững chắc, hợp lý, dễ dùng". File này là bộ lý thuyết ấy: nhạc nền được tả bằng những
trục nào, đoạn văn được tả bằng chính những trục ấy, ghép theo luật nào, người dùng chỉnh ở đâu. Cách đo từng trục và kết
quả đo nằm ở `MUSIC_RESEARCH.md`; file này là KHUNG - không đổi theo từng lượt đo, chỉ đổi khi lý thuyết sai.

## 1. Gốc lý thuyết

- **Nhạc nền phim là họ hàng gần nhất.** Gorbman (*Unheard Melodies*, 1987) rút ra các nguyên tắc của nhạc nền cổ điển:
  *không lộ* (người xem không để ý tới nó như một thứ riêng), *nhường lời thoại*, *mang cảm xúc*, *dẫn dắt câu chuyện*,
  *liền mạch* và *thống nhất* (cùng chất liệu xuyên suốt tác phẩm). Sách nói còn khắt khe hơn phim: không có hình, giọng
  đọc là toàn bộ câu chuyện - nhạc chỉ được ở dưới giọng.
- **Nhạc và câu chuyện ghép theo sự tương hợp.** Mô hình tương hợp - liên tưởng (Cohen 2001): người nghe ghép nhạc với cảnh
  theo những đặc điểm CÙNG CẤU TRÚC (nhịp, cường độ, đường nét) và theo nghĩa liên tưởng (nhạc buồn -> cảnh buồn, đàn tranh
  -> cổ đại phương Đông). Vì vậy phải tả đoạn văn và bài nhạc trên CÙNG một bộ trục.
- **Cảm xúc nhạc cần ba trục, không phải hai.** Schimmack & Grob (2000), Eerola & Vuoskoski (2011, kiểm trên nhạc phim):
  vui-buồn (valence), năng lượng (energy arousal), căng thẳng (tension arousal) - "dồn dập vì hào hứng" và "dồn dập vì sợ"
  khác nhau ở trục căng thẳng. Bộ nhạc phim dùng để đo (MUSIC_RESEARCH.md) chấm đúng ba trục này.
- **Nhãn cảm xúc riêng của âm nhạc.** GEMS (Zentner, Grandjean & Scherer 2008) - 9 cảm xúc mà nhạc khơi lên: kỳ diệu, siêu
  thoát, dịu dàng, hoài niệm, bình yên, hùng tráng, hân hoan, căng thẳng, buồn. Dùng làm NHÃN cho người dùng đọc và sửa
  (dễ hiểu hơn toạ độ), mỗi nhãn ứng một vùng trên ba trục.

## 2. Bảy trục mô tả (đoạn văn và bài nhạc dùng chung)

| # | Trục | Ý nghĩa | Bài nhạc: đo bằng | Đoạn văn: suy từ |
|---|---|---|---|---|
| 1 | **Vui - buồn** | sắc thái dễ chịu / khó chịu | model cảm xúc nhạc (Pha 1) + nhãn người gắn | cảm xúc từng câu, gộp theo đoạn (music_scenes.py) |
| 2 | **Năng lượng** | mạnh - nhẹ, sôi động - lắng | độ to trung bình, mật độ nốt, model | cường độ câu, mật độ hành động, nhịp đọc nhanh/chậm |
| 3 | **Căng thẳng** | hồi hộp, đe doạ vs. thả lỏng | model + nhãn (Suspenseful, Eerie...) | sợ / giận / bất ngờ, câu hỏi dồn, nguy hiểm trong cảnh |
| 4 | **Nhịp độ** | nhanh - chậm (BPM, mật độ phách) | dò nhịp (BPM), mật độ khởi âm | nhịp kể: câu ngắn dồn dập, hành động liên tiếp vs. tả cảnh dài |
| 5 | **Phong cách / thế giới** | văn hoá, thời đại, nhạc cụ (cổ phong phương Đông, giao hưởng, trung cổ, hiện đại, điện tử, ma mị...) | nhạc cụ, thể loại, model chữ-nhạc | THỂ LOẠI của cuốn (tiên hiệp, LN dị giới, Tam quốc...) + bối cảnh cảnh (cung điện, quán rượu, chiến trường) |
| 6 | **Chức năng cảnh** | thiết lập bối cảnh, đối thoại, hành động, nội tâm, cao trào, chuyển cảnh, kết | (bài: hợp chức năng nào - xem trục 7) | tỉ lệ thoại / kể / nội tâm, vị trí trong chương, đổi không khí |
| 7 | **Độ hợp làm nền** | nhường giọng: không lời, giai điệu không nổi, ít năng lượng ở dải 300 Hz-3 kHz của giọng nói, cường độ ổn định, lặp liền được | dò giọng hát, độ nổi giai điệu, phổ dải giọng, biến thiên độ to, điểm lặp | (đoạn: cần nền "trong" bao nhiêu - đối thoại dày cần nền trong hơn tả cảnh) |

Trục 1-3 là cảm xúc (GEMS là nhãn đọc được của chúng); 4 là nhịp; 5 là thế giới; 6 là vai trò của nhạc trong cảnh; 7 là
điều kiện để nhạc không phá giọng đọc.

## 3. Luật ghép

**Bước 1 - LỌC CỨNG** (vi phạm là loại, không bù được bằng điểm khác):
- có lời hát (trục 7) - lời át giọng đọc;
- giấy phép không cho dùng (chỉ CC0 / CC BY ở kho chung);
- phong cách KHÔNG tương thích thế giới của cuốn (trục 5): truyện tiên hiệp không dùng rock điện tử; bảng tương thích
  phong cách x thể loại là dữ liệu, sửa được;
- độ hợp làm nền dưới ngưỡng;
- quá ngắn mà không lặp liền được.

**Bước 2 - KHOẢNG CÁCH CÓ TRỌNG SỐ** trên các trục còn lại: cảm xúc 3 trục (nặng nhất), nhịp độ, năng lượng, độ hợp chức
năng cảnh. Trọng số là tham số, đặt ban đầu theo lý thuyết (cảm xúc > nhịp > năng lượng), tinh chỉnh bằng đo đạc.

**Bước 3 - LUẬT CẢ CUỐN** (Gorbman: liền mạch, thống nhất):
- *thống nhất*: ưu tiên bài trong bảng màu của cuốn - một tập nhỏ bài / nhạc cụ chọn cho cả cuốn, cảnh mới lấy từ đó trước;
- *liền mạch*: đoạn kề nhau gần không khí thì giữ bài đang chơi; đổi bài có chi phí; trần số lần đổi nhạc mỗi giờ;
- *không lặp nhàm*: bài vừa dùng bị trừ điểm trong vài đoạn kế.

**Bước 4 - IM LẶNG LÀ MỘT LỰA CHỌN**: không bài nào đủ gần -> im lặng; chức năng cảnh có thể đòi im lặng (theo mức "mật độ
nhạc" của cuốn - ví dụ đối thoại riêng tư dài). Im lặng tốt hơn nhạc sai.

**Bước 5 - GIẢI THÍCH ĐƯỢC**: mỗi lựa chọn kèm lý do ngắn bằng chữ ("buồn · chậm · cổ phong · hợp nền"), để người dùng hiểu
và sửa đúng chỗ.

## 4. Dễ dùng - người dùng chỉnh ở ba tầng

| Tầng | Chỉnh gì | Mặc định |
|---|---|---|
| Cả cuốn | **Phong cách nhạc** (danh sách thế giới - trục 5), **mức nhạc** (to/nhỏ dưới giọng), **mật độ nhạc** (ít / vừa / nhiều - bao nhiêu phần cuốn có nhạc), bật/tắt | máy đoán phong cách từ thể loại; mức đo bằng Whisper (Pha 4); mật độ "vừa"; BẬT |
| Từng đoạn | **nhãn không khí** (9 nhãn GEMS tiếng Việt), **cường độ**, **chức năng cảnh**, chia lại / gộp đoạn, **ghim bài** hay **im lặng** | máy tự gán |
| Từng bài | bỏ bài (không dùng lại cho cuốn này), thêm bài của mình | - |

Sửa ở tầng trên thì máy chọn lại phần dưới; ghim ở tầng dưới thì luôn được giữ. Như sửa cách đọc tên hay giọng nhân vật.

## 5. Dữ liệu - mỗi trục lưu thế nào

- **Bài nhạc** (danh mục): mỗi trục một con số hoặc nhãn + nguồn gốc của nó (người gắn / model / đo âm học) + độ tin.
- **Đoạn văn** (`music_plan.json`): mỗi trục + lý do; lựa chọn của người dùng ở `music_overrides.json`.
- Định dạng giữ ổn định qua các lần đổi thuật toán - lựa chọn của người dùng không mất.

## 6. Hiện trạng so với khung

Đường cơ sở (01-10) mới có: trục 1-2 (hai chiều), lọc có lời, phạt lặp, giữ bài ở đoạn kề, im lặng khi xa. CHƯA có: trục 3
(căng thẳng - đo được rồi, chưa dùng), 4 (nhịp), 5 (phong cách theo thể loại - vì thế lo18 truyện huyền huyễn ra "Americana"),
6 (chức năng cảnh), bảng màu cả cuốn, trần đổi nhạc, lý do bằng chữ, mật độ nhạc. Nghiên cứu (MUSIC_RESEARCH.md) đo từng trục
trước khi đưa vào app.

# Giọng local chọn theo số đo

`readaloud/local_engine.py` là khung chung: `synthesize`, `voices`, `capabilities`, `resource_needs`, `forget`.
Adapter của mỗi model/tầng bọc nhà cung cấp; VieNeu Turbo/Nano, Supertonic và ZeroTTS cùng đi qua khung này.
ZeroTTS dùng lại mô-đun tải thêm của Studio, không đóng gói thêm runtime. Nhà cung cấp mới đăng ký trong `ReadAloud`
và báo các khúc PCM qua `model.unit_made`. Android có cùng hợp đồng `LocalEngine` và adapter hai engine trên điện thoại.

## Phép đo và luật chọn

- Bốn câu trung tính cố định trong `engine_pick.SENTENCES`, trùng `MachineVoicePick.SENTENCES` trên Android.
- Mỗi model dùng giọng đầu tiên của danh sách, bỏ model trước khi đo; một câu khởi động không tính vào RTF.
- Desktop: RTF = tổng thời gian sinh các khúc / tổng thời lượng PCM các khúc. Không gồm căn chữ/đóng gói WAV.
  Android: RTF gồm toàn bộ lời gọi tổng hợp và đóng gói clip. Không so điểm tốc độ giữa hai máy/nền tảng.
- RAM đỉnh là RSS cả tiến trình trong lúc nạp/khởi động/tổng hợp, lấy mẫu mỗi 20 ms; desktop còn lưu phần RAM tăng thêm.
  Không cộng RAM của bộ nghe/chấm chạy sau đó. Đây là số mẫu của lượt thử, không phải cận trên cho mọi sách.
- CER: trung bình `1 - transcript_metrics(...)[0]` của ASR app trên từng câu, có chuẩn hoá chữ của app và chặn tối đa 1.
  Whisper CPU nếu có; bộ căn wav2vec2 CTC nếu có. Điểm tự nhiên dùng UTMOSv2 CPU khi đã cài.
- Giao diện đóng gói không có torch: helper `voice_pick_worker` chạy trong Python Studio đã cài, dùng cache của Studio,
  không tải model/runtime. Bộ nghe và UTMOS nạp tuần tự, nhả trước bộ kế; không giữ chúng cùng model tổng hợp.
- Android hiện không có ASR/UTMOS; hiện **chưa đo**, không gán 0 hoặc lấy điểm desktop.

Luật cho mặc định nghe trực tiếp: loại engine lỗi/số không hữu hạn; loại CER > 0,15 nếu đã đo;
loại RTF >= 0,8. Trong phần còn lại chọn tự nhiên nhất; chênh dưới 0,1 điểm coi như ngang,
rồi CER thấp hơn, RTF thấp hơn, mã engine theo thứ tự chữ. Không có bộ chấm thì xét CER; thiếu cả hai thì xét RTF.
Nếu một engine chấm hỏng còn engine khác có điểm, ưu tiên điểm đã đo. RAM được hiện để người dùng cân nhắc, chưa là gate.
Chưa đo/không engine đạt thì không tự ưu tiên hãng nào. Lựa chọn giọng riêng của người dùng luôn được giữ.
Trong bộ được chọn vẫn dùng giọng kể trung tính theo danh sách ưu tiên hiện có; số đo đại diện model, không phải mọi preset.

## Lưu và giao diện

`voice-pick.json` cạnh tuỳ chọn (Android: filesDir), ghi atomic; không đồng bộ sang máy khác.
Số đo gắn máy, model mark và giọng đã thử; thay model/gỡ engine thì số cũ không tham gia chọn.
Đo lại giữ override; người dùng chọn engine khác hoặc bấm **Theo số đo** để trở lại tự động.
Desktop và Android: Cài đặt → Giọng đọc → Bộ giọng → **Giọng theo máy**, nhãn **Máy chọn** / **Bạn chọn**,
hiện số của từng engine, bấm **Thử lại**. Khi tải thêm giọng, đo lại những engine đã tải.
Không có kết quả hay kết quả trên máy khác không được dùng để mặc định theo tên hãng.

Đường desktop: `GET /api/readaloud/voice-pick`, `POST .../measure`, `POST .../choose` (`engine: ""` = tự động).
Android gọi lõi qua `VoiceSource`; mọi phép đo chạy CPU tuần tự, nền, không phát ra loa.

# Bìa thư viện Nhạc

Hàng bài, tấm chi tiết và bài đang phát dùng cùng bìa trên web, Android và Qt. Bìa là nội dung trang trí; tên bài cạnh nó là tên truy cập.

## Bìa nguồn

`art` trong mảnh bài có `url`, `sha1`, `w`, `h`, `source` (URL ảnh gốc), `landing`, `credit` và `rights`. Không suy giấy phép ảnh từ giấy phép nhạc.
Jamendo lấy ảnh album qua meta của trang bài công khai; FMA lấy ảnh album của trang bài. Những nguồn khác chỉ nhận ảnh riêng của bài/album,
không nhận logo hay avatar. [OpenGameArt FAQ](https://opengameart.org/content/faq) nói preview không mặc nhiên thuộc giấy phép của tài sản nhạc;
chỉ ảnh được nộp trong phần file tải của bài mới được nhận. Ghi nguồn ảnh theo trang gốc, không tự coi người sáng tác nhạc là tác giả ảnh.

`scripts/music_art_catalog.py --catalog <bản gốc> --out <thư mục ngoài Git>` chuẩn bị bản sao **không ký** và không đăng.
Nó kiểm mảnh theo SHA-256 của manifest và so revision công khai, giới hạn một request/giây, có cache để chạy tiếp;
gặp HTTP 429 thì dừng request đó, gặp chặn liên tiếp bốn lần thì ngừng nguồn. Không đăng nhập hay đọc thông tin xác thực.

Ảnh được sửa hướng EXIF, đặt lên lề giấy ấm và thu về JPEG 512×512. Giữ trọn bố cục thay vì cắt giữa vì bìa album có thể chứa hình hoặc ghi công
ở sát mép. Alpha đặt trên cùng nền trước khi nén. Byte ảnh chuẩn hoá quyết định tên `art/<sha1>.jpg`; bản sao giữ URL ảnh gốc và lời ghi công.
Các ảnh chỉ nằm ngoài repo, trong bộ static assets của Worker mà Lead sẽ duyệt/đăng cùng danh mục; `_headers` cho phép tải ảnh CORS và cache bất biến.
`art/ATTRIBUTION.json` giữ từng bản ghi nguồn; `art-discovery.json` ngoài thư mục đăng ghi cả các bài không lấy được và lý do.

Manifest mới giữ nguyên ô chọn nhạc và mọi metadata âm thanh; chỉ hash của mảnh, revision và dấu giờ thay đổi. `sign_catalog.py` của luồng Music
ký byte manifest bằng Ed25519; app đối chiếu khoá công khai có sẵn rồi kiểm hash mảnh. Chỉ Lead/luồng Music ký và đăng sau khi đối chiếu thế hệ hiện tại.

## Bìa sinh phiên bản 1

Đầu ra chuẩn là 96×96 RGB, row-major, không alpha/chữ. Mọi phép tính pixel là số nguyên. Web và Qt cùng dùng
`desktop_qt/qml/MusicArtRaster.mjs`; Android dùng `MusicArtwork.kt`. `tests/fixtures/music_art/cases.json` chứa seed, SHA-256 RGB và BMP.
Seed nhận link, phong cách, V/A lượng tử 0..200 và cảm xúc cao nhất (hoà điểm: thứ tự mã). Hash UTF-16 xác định vị trí hoạ tiết;
phần thấp của seed giữ bảng màu và nhóm năng lượng. Nhóm sợ/căng thẳng/giận hoặc V thấp dùng xanh đậm; hoài niệm/dịu dàng dùng tím trầm;
vui/V cao dùng vàng ấm; dân gian/mộc dùng xanh lá trầm; còn lại dùng xanh ngọc. Năng lượng thấp có đĩa lớn và đường cong êm.
Không dựa vào font, ngày giờ, ngẫu nhiên hay trình điều khiển đồ hoạ. Hash so byte RGB trước khi màn hình nội suy; không so PNG chụp màn hình
vì DPI, góc bo, nén và màu màn hình khác nhau. Web/Qt còn so cả BMP xác định từng byte.

## Tải và mất mạng

Ảnh sinh xuất hiện trước; ảnh thật thay vào khi giải mã xong, hỏng thì giữ ảnh sinh. Web dùng IntersectionObserver, danh sách ảo,
hàng tải ba việc, CacheStorage và SHA-1. Android chỉ tải khi hàng được compose, dùng coroutine nền, Semaphore ba việc, LRU cho ảnh giải mã
và file cache atomic. Qt dùng Image bất đồng bộ và provider riêng có pool ba luồng, SHA-1 và QSaveFile. Cả ba giới hạn ảnh thật 512 KiB;
native kiểm kích thước giải mã tối đa 512. Không có tải ảnh hay đọc đĩa đồng bộ trong lượt vẽ hàng.

Tắt mạng vẫn vẽ được bìa sinh từ metadata đã có; ảnh thật đã cache được dùng trước request. Bộ đệm của hệ điều hành/trình duyệt có thể bị dọn như
các cache khác của app. Bìa không ảnh hưởng phát nhạc, chọn bài, dữ liệu phân tích hay quality implementation hash.

Kiểm: `test_music_art.py`, `MusicArt*.test.*`, `MusicArtworkTest`, `MusicArtTests`, `MusicLibraryScreenTest`, `tst_music_library.qml`;
`MusicArtOnDeviceTest` chỉ chạy trên emulator riêng với danh mục giả 2.387 bài và ảnh cache đã kiểm hash, ghi phân bố FrameMetrics sau lượt làm ấm.

# ABook

Ứng dụng sách nói tiếng Việt: **làm** sách nói có phân vai và cảm xúc từ các chương truyện `.txt` ngay trên máy tính
Windows của bạn, rồi **nghe** trên máy tính, điện thoại Android hay trình duyệt của bất kỳ thiết bị nào trong nhà. Mỗi cuốn
làm xong là một file `.abook` (bìa, văn bản đọc theo, âm thanh, nhân vật) - gửi sang máy khác là nghe được.

Làm sách chạy hoàn toàn trên máy của bạn: văn bản truyện và âm thanh không bị gửi lên dịch vụ nào, không cần tài khoản.

## Tính năng chính

- **Nghe**: thư viện xếp theo bộ truyện, văn bản chạy theo lời đọc, chế độ đọc sách, ảnh bìa (tìm bìa trên mạng khi bạn
  bấm), hẹn giờ ngủ, dấu trang, lịch sử nghe, xuất MP3 có tag. Một cuốn có thể có nhiều hồ sơ nghe: mỗi người trong
  nhà một chỗ nghe riêng, hay nghe lại từ đầu mà vẫn giữ lần trước.
- **Làm sách nói (Studio)**: đọc cả truyện để nhận ra lời thoại, ai đang nói và cảm xúc từng câu; mỗi nhân vật một giọng
  riêng giữ nguyên suốt cuốn; thu từng câu rồi tự nghe lại bằng nhận dạng giọng nói và thu lại câu lệch. Truyện kể ngôi
  thứ nhất: Studio hỏi "tôi" là ai.
- **Bạn là người duyệt cuối**: hộp **"Việc cần duyệt"** chỉ ra những chỗ máy không chắc (ai nói câu này, hai tên là một
  người, nam hay nữ, cách đọc một tên...), xếp theo lợi trên mỗi lần bấm. Tab **Kịch bản** cho sửa người nói, loại câu,
  cảm xúc và chữ đem đọc của từng câu; tab Nhân vật cho đổi giọng và sửa cách đọc mọi tên riêng (mục "Cách đọc tên");
  tab **Cần nghe lại** cho nghe những câu máy tự kiểm
  không chắc và bấm "Cần thu lại" để thu một bản mới. Máy vẫn tự quyết và chạy tiếp - không bắt ai chờ.
- **Mọi máy trong nhà làm việc cùng nhau**: điện thoại nghe thẳng thư viện máy tính không cần tải (hoặc tải về nghe khi
  không có mạng); chỗ đang nghe và dấu trang đi hai chiều; thấy và điều khiển máy khác đang phát, **"Nghe ở đây"** chuyển
  sang máy mình đúng chương, đúng giây. Nối qua Wi-Fi, hoặc Bluetooth khi không chung Wi-Fi - điện thoại tự chọn đường.
  Máy tính nghe được thư viện của máy tính khác; điện thoại nghe được thư viện của điện thoại khác.
- **Nghe trong trình duyệt** của iPhone, iPad, TV hay máy bất kỳ: mở `http://<tên hoặc địa chỉ máy tính>:47630`. Ở ngoài
  nhà thì dùng địa chỉ Tailscale của máy tính (Cài đặt ghi rõ địa chỉ nào dùng trong nhà, địa chỉ nào dùng khi ở ngoài).

Thay đổi của từng bản phát hành: [`_internal/docs/CHANGELOG.md`](_internal/docs/CHANGELOG.md).

## Yêu cầu máy

| để | cần |
|---|---|
| nghe trên máy tính | Windows 10 hoặc 11, 64-bit |
| làm sách (Studio) | thêm card đồ hoạ **NVIDIA** (đã thử trên RTX 5060 8 GB), ổ đĩa trống từ 30 GB, mạng để tải Studio lần đầu |
| nghe trên điện thoại | Android 7.0 trở lên |
| nghe trong trình duyệt | trình duyệt bất kỳ, cùng mạng với máy tính - hoặc cùng mạng Tailscale khi ở ngoài nhà |

Không có card NVIDIA vẫn cài và nghe được bình thường; chỉ phần làm sách cần nó.

## Cài đặt

### Máy tính (Windows)

1. Tải `ABook_<phiên bản>_x64-setup.exe` ở trang [Releases](https://github.com/ntanhpro1221/ABook/releases/latest)
   và chạy. Bộ cài khoảng 30 MB, không cần quyền quản trị, không cài Python hay gì khác vào máy.
2. Mở **ABook** từ Start Menu. Bấm đúp một file `.abook` là mở cuốn sách đó.
3. Muốn làm sách nói: vào **Studio → Dự án → "Cài Studio"**. Studio tải một lần khoảng 15-20 GB (Python, thư viện, Ollama
   và các model) vào một thư mục riêng, không đụng tới thứ đã cài trên máy (máy đã có Ollama thì Ollama ấy giữ nguyên).
   Mất mạng hay tắt máy giữa chừng thì bấm "Cài tiếp".

**Cập nhật**: app tự tìm bản mới mỗi lần mở; có bản mới thì bấm "Cập nhật và mở lại" trong Cài đặt (gói có chữ ký, sai
chữ ký thì không cài). Bản mới cần phần Studio khác thì thẻ "Cập nhật Studio" hiện ra và chỉ tải lại đúng phần ấy.

**Gỡ**: gỡ ABook trong Cài đặt Windows gỡ luôn Studio. Sách đã làm, chỗ đang nghe và tuỳ chọn được giữ lại
(`%LOCALAPPDATA%\ABook`) trừ khi bạn tích ô xoá dữ liệu trong bộ gỡ.

### Điện thoại (Android)

1. Tải file `.apk` ở cùng trang Releases và cài (Android sẽ hỏi cho phép cài ứng dụng từ nguồn này).
2. Ghép với máy tính - một lần là đủ:
   - Trên máy tính: **Cài đặt** → bật **"Cho phép điện thoại kết nối qua Wi-Fi"** → bấm **"Ghép thiết bị mới"** để
     hiện mã 6 số.
   - Trên điện thoại: tab **Tải sách** → chọn máy tính tìm thấy → gõ mã 6 số.
3. Không chung Wi-Fi (ra khỏi nhà, máy tính cắm dây mạng...): ghép hai máy trong Cài đặt Bluetooth của Android, bật
   Bluetooth trên máy tính, rồi trên điện thoại vào **Tải sách → "Không chung Wi-Fi? Kết nối qua Bluetooth"**. Điện thoại
   đã ghép qua Wi-Fi mà máy tính có Bluetooth thì tự chuyển sang Bluetooth khi rời Wi-Fi, không phải ghép lại. Mạng
   riêng như Tailscale, ZeroTier, NetBird cũng dùng được.

Sau khi ghép, sách trên máy tính hiện ngay trong Thư viện điện thoại (nhãn "Máy tính") để nghe thẳng hoặc tải về.

**Trên xe**: ABook có trong Android Auto - chọn cuốn, chọn chương ngay trên màn hình xe. App cài từ file APK thì trong
Android Auto bật chế độ nhà phát triển (chạm nhiều lần vào số phiên bản) rồi bật "Nguồn không xác định".

### Thiết bị khác

- **Trình duyệt** (iPhone, iPad, TV, máy tính không cài ABook): mở `http://<máy tính>:47630` rồi gõ mã 6 số như trên.
  Thiết bị chỉ nghe được sách, không thấy Studio hay thư mục trên máy tính - trừ khi bạn bật **"Cho phép điều khiển sản
  xuất từ thiết bị đã ghép"** trong Cài đặt và cho riêng thiết bị ấy quyền đó.
- **Máy tính khác có ABook**: Cài đặt → **"Máy tính khác"** → "Tìm máy trong mạng" → gõ mã 6 số đang hiện trên máy kia.
- **Điện thoại khác**: trên máy có sách, Tải sách → bật **"Cho máy khác nghe thư viện này"** → "Ghép máy mới"; trên máy
  kia, Tải sách → "Thiết bị khác" → **"Ghép thiết bị"**.

## Làm một cuốn sách nói

1. Studio → Dự án → **Dự án mới**, chọn các chương `.txt` của truyện (hoặc cả thư mục). Chương xếp theo tên file.
2. Chọn giọng kể chuyện và mức chất lượng; truyện kể ngôi thứ nhất thì trả lời "Tôi là ai?" (Studio gợi ý cả những
   chương đổi người kể).
3. Bấm bắt đầu. Studio đọc cả truyện trước để phân vai thống nhất cho cả cuốn, rồi thu từng chương. Sách hiện trong Thư
   viện ngay khi chương đầu tiên thu xong - không cần chờ cả cuốn.
4. Trong lúc chạy, mở **"Việc cần duyệt"** khi rảnh: mỗi thẻ nói rõ máy đang nghi điều gì, sửa bằng một cú bấm; câu đã
   thu bị ảnh hưởng tự thu lại. Sách đã xong vẫn sửa được: trang dự án hiện nút **"Áp dụng N thay đổi"**, bấm là chỉ thu
   lại những câu bị ảnh hưởng.

Có thể đóng app hay tắt máy bất kỳ lúc nào; mở lại là làm tiếp từ chỗ dừng. Riêng giai đoạn **phân tích** (trước khi
chương đầu tiên được thu) nên để chạy liền một mạch: dừng giữa chừng rồi chạy tiếp có thể cho ra cách phân vai khác. Cần
máy rảnh một lúc thì bấm **"Tạm dừng"** thay vì "Dừng": sách đứng yên và làm tiếp đúng chỗ, an toàn cả lúc phân tích.
Máy tính xách tay rút sạc thì Studio tự tạm dừng (chạy pin làm sách rất chậm mà hao pin) và tự làm tiếp khi cắm lại; tắt
ở Cài đặt → Studio.

**Truyện dài, làm nhiều đợt**: khi thư mục truyện có chương mới (truyện còn ra tiếp, hay lần đầu chỉ làm vài chục chương),
trang dự án hiện nút **"Làm tiếp cuốn này"**. Phần mới ("Tên · Phần 2") giữ nguyên giọng của mọi nhân vật đã gặp, cách
đọc tên và những gì đã sửa ở "Việc cần duyệt"; trong Thư viện các phần đứng chung một bộ và nghe hết phần này thì được
mời nghe tiếp phần sau.

## Trạng thái

ABook đang ở giai đoạn alpha: dùng hằng ngày được, nhưng còn thay đổi nhiều giữa các bản. Model phân tích của Studio
(`abook-analyzer`, tự huấn luyện trên nền Qwen3) đoán đúng người nói khoảng hai phần ba số câu thoại ở truyện mạng và
light novel khó - đó là lý do có "Việc cần duyệt" và tab Kịch bản.

## Dành cho người phát triển

Mã nguồn, test và tài liệu kỹ thuật nằm trong `_internal/`:

- [`_internal/docs/PIPELINE_OVERVIEW.md`](_internal/docs/PIPELINE_OVERVIEW.md) - dây chuyền làm sách: phân tích, phân vai,
  thu âm, kiểm tra bằng nhận dạng giọng nói, an toàn và phục hồi.
- [`_internal/docs/PACKAGING.md`](_internal/docs/PACKAGING.md) - app Windows (Tauri), Studio, tự cập nhật.
- [`_internal/docs/RELEASING.md`](_internal/docs/RELEASING.md) - quy trình phát hành.
- [`_internal/docs/LLM_EVAL.md`](_internal/docs/LLM_EVAL.md) - đo và huấn luyện model phân tích.
- `AGENTS.md` - quy tắc làm việc trên mã nguồn (file bị khoá, không dừng giữa pha phân tích).

Dây chuyền cũng chạy không cần giao diện, từ thư mục `_internal` có môi trường Studio:

```powershell
.\runtime\.venv\Scripts\python.exe -m ebook_reader.cli create `
  --source-dir "D:\Books\Truyen" --range 000..099 `
  --output-root "C:\Users\<user>\Audiobooks" --title "Tên sách" `
  --profile high_quality --start --json

.\runtime\.venv\Scripts\python.exe -m ebook_reader.cli status "<project-root>" --json
.\runtime\.venv\Scripts\python.exe -m ebook_reader.cli stop "<project-root>" --timeout 60 --json
.\runtime\.venv\Scripts\python.exe -m ebook_reader.cli run "<project-root>" --json
```

Thêm `--dry-run` vào `create` để xem trước số file, file đầu/cuối và đường dẫn project mà không ghi gì. `status`, `report`,
`log` và `create --dry-run` chỉ đọc.

## Giấy phép

ABook phát hành theo giấy phép MIT - xem [`_internal/LICENSE`](_internal/LICENSE). Thành phần bên thứ ba (thư viện,
font, model) giữ giấy phép riêng, liệt kê ở [`_internal/docs/THIRD_PARTY.md`](_internal/docs/THIRD_PARTY.md).

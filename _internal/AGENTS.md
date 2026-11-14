# AGENTS.md — ABook

Đọc file này trước khi sửa code. Không tạo tài liệu agent song song; cập nhật trực tiếp file này khi invariant hoặc kiến trúc thay đổi.

## Mục tiêu

Ứng dụng Windows local nhận nhiều chapter `.txt` hoặc một folder chứa TXT của cùng một book, phân tích toàn book để giữ nhân vật/giọng/cách phát âm đồng bộ, rồi tạo MP3 theo từng chapter nguồn.

Yêu cầu bắt buộc:

- workflow GUI mở shortcut **ABook** ở root hoặc trong Start Menu; workflow tự động dùng
  `python -m abook.cli`/entrypoint `abook-headless` và tuyệt đối không điều khiển cửa sổ;
- không hỏi người dùng trong lúc job đang chạy;
- settings, model, voice mapping, seed và threshold bị khóa theo book;
- dependency trực tiếp được pin; setup nâng cấp phải tái sử dụng runtime, không `uv venv --clear`;
- runtime đã tồn tại nhưng thiếu dependency Python phải dùng nhánh repair `pip install -e .` nhẹ;
  không cài lại PyTorch, không pull lại model và không chạy full setup cho trường hợp này.
- tận dụng tối đa tài nguyên trong giới hạn an toàn, tự nhường foreground và tự tăng lại;
- giả định GUI/worker/máy có thể bị đóng bất kỳ lúc nào;
- lỗi nghiêm trọng phải giữ nguyên checkpoint đã commit, dừng và gửi Windows notification;
- tuyệt đối không chèn im lặng để thay nội dung TTS thất bại.

Máy đích hiện tại: Ryzen 9845HX, RTX 5060 Laptop, RAM 32 GB. Không hard-code batch hoặc VRAM theo một máy duy nhất.

## Luồng bắt buộc

```text
import + natural sort TXT
→ segment toàn book
→ Qwen phân tích toàn book, checkpoint theo batch
→ hoà giải nhãn cục bộ + cách đọc tên
→ lượt người nói từng câu (`speaker_pass.py`, nếu sách có cặp model), checkpoint theo chương
→ character registry theo speaker name + pronunciation
→ khóa voice mapping/preset/seed/settings
→ unload LLM
→ từng chapter: TTS → unload TTS → Whisper → repair → FFmpeg verify
→ chapter MP3
→ reports + M3U8
```

Không đổi sang phân tích cuốn chiếu nếu người dùng chưa thay đổi ưu tiên đồng bộ toàn truyện.

## Invariant an toàn

- Public Corpus overlap reviews must pin the repository path, exact file-byte SHA-256 and every approved eight-word shingle hash. Only individually classified contextual coincidences (category i) may be reviewed. Generic file reviews cannot waive Corpus matches; changed bytes (including line endings) or new matching shingles must block again. Keep story excerpts outside Git and use original examples in prompts and fixtures.
- The public Corpus index is private runtime data under `ABOOK_RUNTIME/cache/public_leak_index`. Store hashes and numeric metadata only. Its algorithm version must change with inventory, chapter preprocessing, tokenization, shingling, book identity or common-book rules (including imported credit rules). Validate checksums before using cached postings; retain common shingles so deletions can cross the three-book threshold. Publish immutable shard generations before atomically replacing the manifest; never treat corrupt cache data or unreadable chapters as an empty Corpus.

- Stored project paths are untrusted. Every source/audio/artifact path must pass `book_paths.inside` using the actual book folder before filesystem access; UNC/device paths and relative paths fail before I/O. New projects copy selected TXT files into `sources/`; do not migrate or allow external stored sources. Validate imported workbooks before opening, listening-only import, or merge into an existing book.
- Locked model paths are untrusted too: only the current runtime permits model reads/hashes. An old absolute path may supply a validated `models/` suffix without probing its old location; UNC/device paths and relative/traversal suffixes fail before I/O. Continuation links may identify sibling books within the current library, never an arbitrary external folder.
- Continuation never discovers sources from stored paths. `source_hint.json` holds a display/picker hint only; open a fresh file/folder picker, filter `next_chapters` over the user's selection (uploads for remote Studio), then copy selected TXT files into the new book's `sources/<chapter>/` before use. Loading a plan must not probe the hinted directory.
- Pairing strings carry the complete SHA-256 TLS certificate fingerprint. Manual codes require comparing the first four groups on both devices, then pinning that certificate before sending the code, including Bluetooth tunnels. Discovery never establishes identity. Do not use code-derived HMAC or TOFU. Standalone browser pairing is closed because page JavaScript cannot verify the TLS certificate; native clients perform verification.
- UI API bodies require `application/json`, including empty bodies, and browser Origin/Sec-Fetch-Site checks apply with and without the session token, including `--dev`.
- Nhạc nền đổi chương phải khám phá mốc của đúng sách/chương mới, kể cả khi chương cũ im. Không được bỏ đồng bộ chỉ vì `cues`/bài đang phát/danh sách phát cũ rỗng trước khi đối chiếu identity sách/chương. Khi giọng vẫn đang tạm dừng, nhạc cũng phải giữ dừng; mốc trả về muộn không được khôi phục nhạc chương cũ. Kiểm bằng `ChapterMusicTest` + `ChapterMusicEdgeTest` (JVM), `MusicTests::chapterMusicMatrix` + các ô biên kề nó (Qt) và `chapterMusic.dom.test.tsx` (web); sáu chế độ mang cùng nghĩa ở cả ba nền, sửa một nền thì sửa cả ba.
- Cập nhật Studio dùng `_busy_elsewhere()` và khoá hàng đợi để từ chối khi sách đang chạy/khởi động/tạm dừng; kiểm lại ngay trước thay runtime, không dừng sách để cập nhật.
- Bộ gỡ Windows đọc `preferences.json.libraryRoot` trước mọi xoá đệ quy trong hook; không đọc được vị trí thì giữ dữ liệu. Chế độ nâng cấp truyền bằng cờ rõ ràng từ callback GUI trước PageReinstall hoặc `/UPDATE`, không suy tên bộ cài.
- Thư viện tuỳ chọn giải trong staging riêng; chỉ công bố `lib.next` có dấu hoàn tất. Caller dùng chung phải giữ khoá đích xuyên suốt tải, giải và commit, rồi kiểm lại dưới khoá.
- Studio đối chiếu hash distribution với `uv.lock` đi kèm app; dependency Git đối chiếu commit đầy đủ và không tự tải build dependency chưa ghim. Marker hoàn tất chỉ ghi sau verify và checkpoint.
- **Trong lúc pha phân tích chạy, đừng chạy việc nặng nào khác trên máy** — kể cả `pytest`.
  Phân tích của dự án này tái lập hoàn hảo: alpha.48, .49 và .51 giống nhau **từng byte**.
  alpha.52 lệch **54 phân vai** so với cả ba, và hình dạng là *một* nhóm lệch ở thứ 45/201 rồi
  lan ra 57 nhóm phía sau, vì registry nhân vật mang cái lệch ấy đi tiếp. Lúc nhóm 45 chạy thì
  tôi đang chạy một lượt pytest đầy đủ. Chưa chứng minh được nhân quả (một quan sát, không phải
  thí nghiệm), nhưng chờ thì tốn **không gì cả**, còn đoán sai thì tốn cả một quỹ đạo phân tích.
  Chi tiết: `docs/VERSIONS.md`.
- `interactive_prompts=false`; pipeline/worker không mở prompt hoặc `QMessageBox`.
- CLI `status`/`report`/`log` và `create --dry-run` là read-only: không mkdir, migrate SQLite, recovery,
  dọn lease hay chạm file control; SQLite đang chạy phải được đọc bằng URI `mode=ro`, không dùng `immutable=1` vì có WAL.
- Background start chỉ gửi `READY` sau khi worker đã giữ `.worker.lock`, nạp settings khóa và xác minh toàn bộ source.
  State/control JSON ghi atomic trong `runtime/background`; recovery tuyệt đối không xóa `.part` trong namespace này.
  Ghi state khi worker còn sống chỉ thử một lần, hỏng thì hẹn backoff từ sau lần ghi và tiếp tục rút sự kiện/chuyển control; chỉ ghi kết thúc mới chờ retry.
- Background identity gồm project path + instance token + PID + process create-time. Force-stop phải khóa launch ownership,
  đối chiếu lại đủ identity ngay trước khi kill/ghi state và từ chối nếu một instance mới đã thay thế instance được yêu cầu.
- Hai tiến trình tạo cùng title/manifest phải serialize bằng OS creation lock xuyên suốt bước chọn project root,
  ghi settings và initialize SQLite; profile khác nhau không được ghi chéo settings/DB.
- Lượt "người nói từng câu" (`speaker_pass.py`) là nguồn `segments.speaker` của câu thoại/nội tâm trước casting; kind và câu kể
  luôn giữ của model phân tích. Mỗi chương commit một transaction (CAS theo speaker cũ), chương dở làm lại từ đầu chương;
  nhãn trong đề là nhãn của CHÍNH lượt này (tuần tự), không bao giờ là nhãn của model phân tích. Digest model người nói khoá
  theo sách, đổi giữa chừng thì fail-closed. Đề phải trùng mã đo từng byte (`tests/test_speaker_pass_prompts.py`) - sửa
  `speaker_pass.py` là đổi hash khoá. Ledger `analysis_candidates` vẫn giữ projection của model phân tích (lượt ghi sau
  analysis, cùng tiền lệ speaker repair của casting).
- Mọi process nền trên Windows dùng `pythonw`/`CREATE_NO_WINDOW`, redirect stdio UTF-8 vào log; POSIX dùng session riêng.
- SQLite là source of truth; không dùng existence/mtime làm bằng chứng hoàn tất.
- Phát tiếp/mở lại sách phải giữ đúng con trỏ nghe, không tự lùi theo thời gian tạm dừng (Android/Qt/web). Chỉ thao tác tua/nghe lại rõ ràng của người nghe mới được phát lại nội dung đã nghe. Qt pause phải tính cả đuôi mờ đã phát và con trỏ thiết bị tại lúc commit, không lưu lại con trỏ trước `awaitPull`.
- QA nội dung phải chặn cụm đọc lặp cục bộ dù điểm CER/WER toàn đoạn vẫn đạt. Giữ `repeated_content` trong sổ decode/audio gate; cứu tên riêng hoặc ngữ cảnh ghép-3 không được xoá cờ này. Lượt thu thay thế dùng lịch seed hữu hạn, tất định có sẵn và phải qua hai lượt giải mã.
- ProjectDB chỉ tạo schema đầy đủ cho DB trống, hoặc mở đúng schema hiện hành. DB khác phiên bản/thiếu cấu trúc bị từ chối
  trước kết nối ghi; không backup nâng cấp, ALTER hay chuyển rows cũ. Danh sách backup của Store chỉ nhận snapshot qua cùng gate
  chỉ đọc; API quan sát giữ `mode=ro`/`query_only` để chẩn đoán dự án lỗi.
  Schema đầy đủ gồm `character_exposure` của dự án nối tiếp; continuation chỉ ghi dữ liệu, không tạo thêm bảng khi gieo.
- Với chính sách hẹn ngủ, app KHÔNG BAO GIỜ tự hẹn/tự dừng khi người nghe không yêu cầu. Lâu không tương tác không phải yêu cầu hẹn ngủ. Chỉ hẹn khi người nghe yêu cầu: hẹn phút, hết chương, hoặc lịch đêm do chính người nghe bật (mặc định tắt). Lịch đêm đợi máy rảnh: Android cần màn tắt và bốn cửa sổ nằm yên khi có cảm biến; desktop cần thời gian rảnh toàn OS. Tín hiệu còn thức huỷ hẹn theo lịch, không huỷ hẹn tay. Không khôi phục hẹn theo lịch từ đĩa; hẹn tay gắn đúng sách/hồ sơ. Hẹn giờ đứng vì tạm dừng tới 30 phút thì tự bỏ (Android/Qt/web cùng hằng số); đang dừng thì vòng đếm và cảm biến của hẹn giờ ngừng. Không đọc, xoá hay migrate khoá cũ của tính năng đã gỡ.
- Android: `Store.writeAtomic` sync dữ liệu trước rename, không xoá đích trước; JSON hồ sơ hỏng phải giữ ở `.corrupt-…`.
  Playback service teardown and Close sync only a small final-place journal without taking Store's monitor, then drain both writer queues on a process-owned background executor with one timeout. Cold Store initialization replays that journal before publishing root; deleted/moved profiles must not be resurrected. Never flush/join on the player looper. Service/widget initialization and widget rendering perform Store I/O in the background; player snapshots and prepared-queue installation stay on main.
  Phản hồi âm/rung native đi qua `Feedback.kt` và công tắc `ListenPrefs`: hẹn lại phát hai nốt xác nhận cùng lượt rung, cả khi màn tắt; báo sắp hết chỉ một nốt, hết hẹn im cả âm/rung. Qt/web giữ cùng bảng nốt và ngoại lệ khi đang phát trong DESIGN 5.3/5.4.
  Adopt/rekey cùng phiên bản ghi journal trước đổi thư mục và hoàn tất liên kết/fingerprints khi mở lại.
  Pending đồng bộ giữ đúng `(bookId, recordId, revision)` và snapshot; ACK cũ không gỡ revision mới.
  Chỗ nghe ReadAloud giữ `last.anchor` (đoạn, offset code point, vân tay chữ chương), ưu tiên khi văn bản còn khớp; Kotlin/TypeScript/Python cùng hợp đồng.
  Retake từ điện thoại có operation_id bền trước gửi; `book_wishes` giữ receipt và dấu giờ cũ khi retry, không đổi seed thêm lần nữa.
- Dữ liệu peer: kiểm mã sách Android tại native trước I/O và trước thêm tiền tố peer; `bookDir` phải là con trực tiếp của `books/`.
  Máy đã ghép lưu `addresses` tối đa 8 mục `{address,lastSuccess}`; host/cổng chỉ là chi tiết lần ghép, không bù route thiếu từ các trường ấy.
  Chỉ học địa chỉ từ TLS khớp vân tay đã ghim (discovery chỉ là gợi ý); thử đường trước HTTP, không replay POST khi chưa biết kết quả.
  Chọn TLS gộp theo identity, cache lỗi 2 giây (xoá khi đổi mạng/discover đã xác thực), tối đa 2 tác vụ I/O mỗi peer và 32 peer giữ trong bộ chọn;
  DNS kẹt giữ slot của chính peer đó, không xếp hàng vô hạn hay chặn peer khác. Đường ưu tiên đi trước 150 ms; đủ ngân sách hai lane cho cả 8 địa chỉ (tối đa 6,15 giây).
  Biên đọc chuẩn hoá từng record địa chỉ, bỏ kiểu sai và dấu giờ không hữu hạn/âm, gộp trùng trước trần 8; giữ bản dữ liệu hỏng trước ghi phần hợp lệ và báo ghép lại máy không còn địa chỉ.
  Discovery Android thu tối đa 64 gợi ý UDP mỗi lượt trước xác minh TLS; bộ xác minh chung tối đa 2 I/O và 16 tác vụ chờ, quá trần thì bỏ gợi ý, không chặn vòng nhận UDP.
  Đường file gói qua kiểm tra từ vựng chung hai nền trước canonical/resolve/stat (cấm UNC, drive/ADS, backslash, tầng rỗng/dot,
  tên thiết bị Windows, hậu tố chấm/khoảng trắng), rồi kiểm containment theo thành phần. Manifest mạng phải qua cùng gate trước ghi.
- Cổng sync: desktop tối đa 32 kết nối/8 mỗi nguồn, keep-alive rỗi 30 giây; Android 8 worker/6 mỗi nguồn,
  thêm tối đa 16 socket chờ 30 giây chỉ cho địa chỉ vừa xác thực trong 5 phút (địa chỉ không thay token từng request).
  Nguồn lạ vượt trần bị đóng trước TLS; trả slot cả khi worker chưa khởi động được. Deadline header/TLS 30 giây;
  thân gói sửa desktop và thân Android đã xác thực dùng 30 giây + cỡ/16 KiB/s cùng timeout recv và trần byte.
  Nguồn chưa xác thực giữ deadline 30 giây; huỷ deadline trước trả lời để không cắt stream audio dài.
  GET bị đóng trước response hoặc nhận 503 thử lại tối đa hai lần (200/800 ms), không replay POST hay bỏ kiểm pin.
- Tải từ peer: `peer_limits.py` và `PeerTransfer.kt` giữ cùng trần byte (JSON/chữ 16 MiB, lỗi 64 KiB, bìa 8 MiB, WAV 64 MiB,
  audio chương 8 GiB, nhạc 2 GiB; job 64 GiB/20.000 file). Kiểm byte trước ghi, đo chỗ trống từng khối; quá trần thì bỏ phần dở,
  mất mạng/huỷ giữ phần dở khi cỡ đã biết, chỉ nối tiếp khi ETag khớp và máy kia xác nhận Range. File nhỏ dùng temporary riêng,
  sync rồi rename, không xoá target cũ.
  Đường ghi giữ nguyên `share.json` hỏng cùng bản `.corrupt-*`, chặn writer thay vì dựng danh sách rỗng; lỗi đọc cũng phải báo lên.
  Chẩn đoán chỉ đọc/validate, không tạo bản corrupt, không gọi init/recovery; Store lạnh báo chưa sẵn.
  Init Store/LibraryServer tuần tự dưới khoá, công bố root/context sau recovery; ghim filesDir canonical đầu tiên, thư mục khác thì log và bỏ qua.
- Phán quyết nghe của Studio nằm trong `reviews.json`, gắn với `stable_id` và checksum bản thu `wav_sha256`; bản thu đổi thì
  phán quyết cũ vào lịch sử, không được che câu chưa nghe ở hàng nghe lại hoặc hộp việc. Không ghi phán quyết này vào SQLite.
- Xuất `.abook` phải đối chiếu checksum của byte thực ghi trước khi công bố gói; nguồn đổi giữa băm và ghi thì báo lỗi và dọn
  file dở. Xuất cả bộ dùng cùng job nền có tiến độ/huỷ/nối lại như một cuốn; huỷ M4B phải thu hồi FFmpeg trước khi dọn file dở.
- WAV/MP3 luôn ghi `.part`, validate + checksum rồi atomic replace.
- Tín hiệu câu phải có mép yên: đo RMS cửa sổ đầu/cuối theo `SEGMENT_EDGE_WINDOW_SECONDS` và
  `SEGMENT_EDGE_MAX_RMS` trong `audio_io.py`, sau gain khóa của bản thu. Lỗi `TTS_ACTIVE_ONSET` /
  `TTS_ACTIVE_OFFSET` đi qua vòng seed retry có sẵn trước khi signal-passed; không vuốt/cắt mép
  của audio thật để lách gate. Tone giả trong bài thử/preview phải tự sinh có envelope yên.
- MP3 phải được FFmpeg decode toàn bộ trước khi commit.
- TTS retry theo thứ tự: seed VieNeu khác → chia nhỏ an toàn nếu câu đủ dài → `failed`; câu cảm thán
  ngắn không được split vì sẽ làm sai nội dung.
  Ngoại lệ đã duyệt F1: hai hạt khác nhau cùng có `repeated_content` với cùng cụm >= 2 âm tiết
  (so đúng bằng phép gộp thanh của ASR), hoặc F4 báo thời lượng bất thường, thì ứng viên kế tiếp
  tách tại dấu câu giữa các lần xuất hiện trong lời đọc đã materialize. Không đổi chữ, không
  chạm câu <= 2 từ, không cắt span cách đọc ghim. SQLite dựng lại bằng chứng trước vòng ứng viên;
  thiếu bằng chứng không được nhận provenance `repeat_alias_v1`. F0 cấm đề cử ngoại lệ nếu có cụm lặp.
- **Một preset là một giọng nguyên bản** (chủ sách 06-11: “bỏ hết trừ cân bằng tốc độ”). Không đổi F0,
  formant, register hay gain theo tuổi/cảm xúc/volume/vai người kể. Chỉ giữ WSOLA và khoảng nghỉ cấu trúc, không bù nghỉ theo cảm xúc hay lời dẫn thoại.
- Khoá bảng `engine@version/preset`; VieNeu chỉ có `r`, `o_db`, `ref_lufs`. Gain câu = `L + o_db - ref_lufs`,
  thêm trần đỉnh an toàn; không line offset, không RMS/LUFS đo từng câu để đặt gain. Không đổi `r` khi fit độ to.
  Metadata QA `seconds_per_syllable` của F4 là trung vị đóng băng theo preset ở x=1 từ bản chụp
  đã dùng trong thiết kế; chỉ đo tỉ lệ cho câu 5-12 âm tiết, không điều khiển giọng/ngân sách frame.
  Giọng chưa đo không mang metric này; không fit lại từ DB sách đang thu. Đổi `r` phải đo lại hằng này.
- Sau phân tích toàn sách, cấp preset chưa dùng cho vai nhiều câu trước vai ít câu. Chọn bằng phái và hạng
  chủ sách; trẻ con (cả bé trai) tự chọn từ pool nữ nguyên bản, giọng người nghe ghim vẫn được ưu tiên.
  Casting và kiểm giọng trước xuất dùng chung `preset_fits_person`. Hết preset thì dùng chung và nghe cùng giọng; không tạo thang bậc phụ.
- Schema và prompt phân tích vẫn giữ emotion/intensity/volume để giữ gold và dữ liệu huấn luyện.
  Mọi số độ to phải fit bằng bộ 40 câu trung tính × hai seed, ISO 532-1 stationary; sách chỉ là dữ liệu test.
- Chỉ gỡ vòng hiệu chỉnh sách sau khi cả hai sách kiểm định đạt đúng 1,5 phon giữa giọng và ±1,0 phon
  giữa chương với trung vị sách. Nếu không đạt, giữ vòng cũ, không tune trên sách hay nới ngưỡng.
- Ngân sách frame VieNeu và giới hạn validation phải lấy từ cùng `segment_duration_policy`; codec VieNeu v3
  dùng 3.840 sample/frame ở 48 kHz. Mọi tổ hợp kind/pace/độ dài phải có headroom validation được test.
- Chỉ có `narration`/`dialogue`/`thought`; từ tượng thanh và cụm cảm thán giữ nguyên trong câu đọc bình thường.
  Không audio nào được cắt để lách validation; kết quả quá dài phải retry hoặc `failed`.
- Chương còn dòng `failed` nhưng đủ WAV thật vẫn được ghép, giữ trạng thái `warning`, ghi rõ dòng lỗi và không ghi QA `pass`.
  Dòng thiếu audio giải mã được hay sai băm thì chặn chương, nêu đúng dòng; không chèn im lặng thay lời đọc.
- Chương có MP3 nghe được, kể cả `warning/Cần nghe lại`, phải giữ kịch bản có mốc gắn checksum MP3 trước khi đặt lại câu.
  Mọi đường sửa dùng chung `database.heard_chapter` và `_mark_listener_redo_conn`; MP3 mới không được dùng bản chụp của MP3 cũ.
- Ngoại lệ giọng người kể theo chương/đoạn lưu xuất xứ câu trong `chapter_teller_lines` cùng transaction đổi giọng/đặt lại câu.
  Hoàn tác hoặc chọn người kể khác phải đối chiếu lại cả những câu đã áp, giữ người nghĩ ban đầu và ưu tiên sửa từng câu của người nghe.
- Trong mode `teller`, lớp giọng chương áp cho `NARRATOR` ở mọi kind và nội tâm chưa rõ người nghĩ;
  giữ nguyên speaker/character của câu, kể cả NULL, và giữ provenance để hoàn tác cả profile ban đầu chưa có.
  Mode A+ mặc định căn giọng dẫn cả cuốn theo giới “tôi” khi chưa thu và narratorAuto; người kể được khai riêng theo chương/đoạn và khác giới giọng dẫn sau căn dùng giọng riêng của họ
  cho mọi câu NARRATOR hoặc nội tâm chưa rõ chủ thể. Sửa chữ hoặc chọn owner NARRATOR không phải chọn preset dẫn;
  lựa chọn preset dẫn rõ ràng và lựa chọn người nói có tên vẫn được ưu tiên. Trích giữa câu chỉ sửa tên/nhãn cục bộ khi có khung câu kể và thiếu bằng chứng
  lượt nói: ngôi 1–2, tiếng kêu/cười, đáp lễ hoặc cue phát ngôn gần cụm trích. Khung giải nghĩa tên/thuật ngữ và khung
  hướng dẫn cách nói được xét riêng; speech tag vẫn có quyền riêng. Đây là heuristic đã đo, không bảo đảm giữ mọi thoại thật.
- Trước khi xuất `.abook` từ dự án, `voice_integrity` kiểm owner/giọng chương, giới, signal và mọi mảnh split trên
  các chương có audio, kể cả xuất `partial`/cả bộ. Sai/thiếu bằng chứng chặn xuất; kiểm chỉ đọc, không sửa DB hay gọi model.
  Nội tâm của chính “tôi” ở A+ dùng profile dẫn với identity giữ nguyên và provenance; nội tâm khác giữ giọng riêng.
  Giọng dẫn khác giới người kể chương cần được chọn rõ hoặc sửa trước khi xuất.
- Retry cùng chữ/giọng giữ bản thu tốt nhất trong SQLite và trên đĩa đến khi bản tốt hơn checkpoint. Lượt thử ghi file riêng;
  hết lượt vẫn `failed` kèm lý do và bản thu đã giữ. Đổi chữ/cách đọc/giọng là vô hiệu bản thu, không phải retry.
  Hạng `_usable_take_rank`: bậc tín hiệu trước, rồi (chỉ ở `high_quality`) bậc "cổng HQ cấm" (lệch tốc độ, đọc lặp), rồi các cờ mềm -
  trong cùng bậc tín hiệu, bản HQ cho qua luôn thắng bản HQ cấm, để câu có bản đạt không ra `failed`.
- Cổng ngắt trong từ đo WAV sau tempo/gain bằng CTC, chỉ bật cho giọng có thước riêng trong `voice_balance`. Không đổi sampling hay chữ khi sinh lại.
  Budget một lần và seed được reserve bền trong `artifacts` trước inference, gắn policy/chữ đọc/giọng/lượt thu tay; sinh lại là hàm thuần của (đầu vào, seed đã reserve).
  Crash, thiếu bộ nhớ hay lỗi đĩa không tiêu lượt: chạy lại đúng seed, lỗi môi trường không hết thì `CriticalResourceStop` và giữ reservation; audio không đạt hoặc lỗi tất định của máy đọc/chia câu mới là phán quyết `failed` cuối của seed.
  "Lỗi môi trường" là OSError/MemoryError (qua cả `__cause__` và `__context__`, kể cả context bị ẩn) hay lỗi tạm thời có tên (`MACHINE_FAULT_MARKERS`: CUDA error, connection reset...).
  TypeError/KeyError/AttributeError/NameError/AssertionError, UnsafeBookPath (kể cả `_book_file` bọc lại) và ngoại lệ chưa phân loại là fatal: không tiêu seed, không ghi phán quyết vào sổ phiên, không đánh dấu câu `failed`.
  Chỉ lỗi chất lượng/TTS được ném rõ bằng `AudioQualityError` mới phán quyết seed; lỗi engine được bọc thì thử lại ba lần cùng seed (`AudioQualityError from exc`, ghi sổ phiên):
  câu đi tiếp sang seed kế/chia câu/`failed`; một câu lỗi tất định không được dừng cả cuốn hay làm resume kẹt.
  Mọi lượt gọi tổng hợp giữ `take_session` trong artifacts: snapshot đầu lượt, path/seed đặt chỗ và kết quả từng take. Resume khôi phục snapshot rồi phát lại cùng lượt gọi và cùng các phép kiểm high_quality; take đã xong đọc lại theo checksum, take dở dùng lại seed đã đặt chỗ. Recovery xếp take dở vào `failed + quality_pending`, nên vòng chapter phải gọi lại mọi session còn mở (`_owed_take_session`), cả câu không có cổng, và giữ đúng round của lượt clarity.
  OOM trực tiếp, có cause hoặc context dùng chung `_without_memory_pressure` trên đường chính, ứng viên, sinh lại qua cổng và chia nhỏ: tối đa ba lần cùng take; ngân sách tài nguyên tách khỏi ngân sách chất lượng, hết thì `CriticalResourceStop` và giữ lượt dở.
  Mẫu đầu và mẫu sinh lại giữ đường riêng, ứng viên ASR cũng vậy: chọn bằng `_usable_take_rank`, bản sinh lại chỉ thay `wav_path` của ứng viên khi tốt hơn; signal của incumbent không bị đụng. `signal_json.word_break_gate` giữ phép đo của bản được chọn và lịch sử trước/sau.
- Chia câu chỉ dùng lời đọc đã materialize cùng span nguồn/lời đọc; không áp phát âm lại lên kết quả thay thế.
- Xuất `.abook` âm thanh so toàn bộ chương nguồn, giải mã, băm và đủ dòng phụ đề. Thiếu chương phải từ chối trừ khi chọn
  `partial` rõ ràng; manifest, CLI và kết quả UI cùng ghi N/M và tên chương thiếu. `bookfile verify` kiểm lại giao ước này.
- ASR mismatch dài bất thường chỉ được dùng để kết tội TTS khi transcript có thể tồn tại trong thời lượng WAV;
  transcript vượt tốc độ từ vật lý phải được đánh dấu là Whisper hallucination và không kích hoạt repair TTS.
- Mỗi lượt Whisper trực tiếp, lặp-ngắn, beam và greedy phải ghi evidence riêng theo đúng checksum WAV/policy.
  Lặp-ngắn chỉ được thay kết quả trực tiếp khi nó chuyển verdict thành `pass`; một kết quả lặp vẫn lỗi không được
  ghi đè transcript/similarity/WER trực tiếp tốt hơn. Evidence decode không được dùng thay final segment gate.
- Mỗi pronunciation tiếng Anh đã khóa và thực sự được thay trong `spoken_text` phải tạo anchor theo đúng ID/occurrence.
  ASR chỉ được chấp nhận spelling nguồn, spoken-form token, dạng ghép token xác định, hoặc token có **chuỗi phoneme
  tiếng Việt bằng đúng** spoken form (`gi` và `d` cùng là /z/ nên `Giôn` và `dôn` là một âm). Đây vẫn là phép so bằng,
  không phải ngưỡng khoảng cách: `Lucy` vẫn không thể thỏa anchor của `Lucien`. Tuyệt đối không fuzzy-alias tên khác.
  Tất cả occurrence phải gắn đúng vị trí bằng alignment toàn câu ở từng direct/repeat/beam/greedy decode; không được
  lấy một homograph ở vị trí khác để lấp tên bị sai. `ASR_INCONCLUSIVE` vẫn giữ precedence.
- Anchor tên riêng **không có quyền chặn publish**. Whisper là model đa ngữ thiên lệch tiếng Anh: nó viết `Giô-en`
  đọc đúng thành "joanne" và `Ai-vân` thành "ivan", nên chính tả nó chọn **không phải bằng chứng về cách phát âm**.
  Anchor không khớp sinh evidence review; quyền fail thuộc về similarity/WER cấp câu, đo trên text canonical.
  Trong metric canonical, anchor không khớp phải được canonical hóa ở **cả hai vế** để một bất đồng về tên không bị
  tính lỗi hai lần — trước đây nó vừa bị anchor bắt vừa làm phồng WER, đẩy câu ngắn vượt ngưỡng chỉ vì cái tên.
  Anchor bị bỏ hẳn khỏi transcript (`delete_anchor`) vẫn tính là lỗi. Miễn trừ này chỉ hợp lệ khi còn đủ nội dung
  thường để tự đứng vững: dưới `CANONICAL_ANCHOR_WAIVER_MIN_ORDINARY_TOKENS` token thường thì anchor giữ nguyên
  quyền hard-fail, vì bỏ tên khỏi "Anh Lucy" là không còn gì để kiểm. Repair vẫn chạy đủ vòng; chỉ trạng thái cuối
  đổi từ `failed` thành publish kèm `ASR_LOCKED_NAME_ANCHOR_REVIEW`. Caller không truyền ngưỡng canonical thì giữ
  nguyên hành vi hard-fail cũ.
- ASR repair phải giữ nguyên speaker, voice profile và `spoken_text`; chế độ `clarity` chỉ hạ sampling variance.
  Mọi cách đọc khóa (kể cả nguồn analysis/listener) và phép TN đổi chữ mang thêm alias theo occurrence:
  spelling nguồn, cách đọc khóa và chuỗi thực gửi giọng. Alias mới không hạ một pass theo luật cũ;
  chỉ cứu mismatch khi các token thường còn nguyên, không dùng việc khớp tên để tha lỗi từ khác.
  "Còn nguyên" cho alias cho phép lệch thanh và đúng cặp phương ngữ theo giọng khóa, vẫn giữ nguyên
  chất nguyên âm/phụ âm cuối, thứ tự và số token. So tên thêm cách viết Latin của Whisper theo
  `voice_profile -> voice_catalog.region`: Bắc r/d/gi/z, Nam r/z tách d/gi/j/y; vùng chưa biết không
  nhận thêm phép gấp vùng. Phép gấp chỉ thêm đường khớp tên, không thay `_segmental_phonemes` của câu.
  Chỉ y là nguyên âm đơn mới gấp i; neo giữ đ riêng khỏi d/r/gi qua `_normalize_anchor_transcript`;
  đường `diacritic_folded_exact` gấp đ->d như cũ (`_plain_folded_token`), key vùng mới thì không.
  Giữ đ chỉ ở token so tên. Token thường trong alignment và mọi nhánh metric canonical (cả
  `fold_tone=False` lẫn guard alias theo vùng) gấp đ->d theo chuẩn câu cũ; không siết PASS cũ
  khi Whisper viết d thay đ ngoài tên. Kiểm bằng `test_asrjudge.py` và replay cùng bộ 524/13.468 đoạn.
  Guard alias nhận từng cặp token qua luật câu cũ HOẶC luật vùng; không nối đ->d với d/gi/r.
  Cờ provenance của token thường chặn gấp vùng trên d do bỏ gạch, nên ra/đa và giá/đã vẫn trượt.
  Đường so tên vùng chỉ bỏ thanh, giữ mũ/móc/breve và chuỗi nguyên âm kể cả khi G2P làm mất khác biệt.
  Thành phần giữ chữ có dấu đến khi tách nhánh: chỉ nhánh component cũ được nhận bản bỏ toàn dấu.
  Không ghép một phép gấp phụ âm mới với lệch nguyên âm (Ha-rư/Há dù phải trượt); các tương đương
  Latin/Hán-Việt và phép bỏ dấu đã có trước 8c90dc47b vẫn giữ đường riêng.
  Ngoại lệ duy nhất cho nguyên âm là romaji (asrjudge3): token chữ Latin trần, không phải
  `valid_syllable` (không thanh/mũ/móc), so với thành phần tên phiên âm >= 2 âm tiết thì được đọc
  bằng chính `romanization.romanized_reading(..., "ja")` (Joshi Kun -> Giô-si Cun; giọng Nam đọc
  thêm z như r) rồi so TỪNG âm tiết với cách đọc khoá sau `_name_spelling_key`: nguyên âm phải
  trùng hết. Luật app ra u/e (Haru -> Ha-ru) nên không tha Ha-rư/Phư/A-ca-nê; token có dấu
  (Há dù) không bao giờ vào đường này; tên không có cách đọc Nhật (Josie) giữ như cũ.
  Đường vùng cho token dính chữ cũng so TỪNG âm tiết (asrjudge4, `_regional_syllables_match`):
  cắt span thành đúng một mảnh cho mỗi âm tiết khoá, mỗi mảnh khớp `_name_spelling_key`; chỉ được
  bỏ phụ âm cuối trùng phụ âm đầu âm tiết sau (Sát-ta/sata). Không so key nối liền: nối làm gi+e
  thành "gie" nên Fuze từng qua Phu-gi-e, Shizai qua Xi-gi-ai (mất cả âm tiết gi).
  Nhánh component cũ gồm cả đ->d cùng bỏ dấu như integ168 (An-đê-ra-ban/Ande ra bàn,
  Phư-di-ê-đa/Phư Di Eda); đây là miễn trừ cũ, không đưa đ->d vào key vùng mới.
  `repair_syllabic_gi` chỉ thêm đường so tên, không đổi cách đo câu. Giữ `spelling_alias_evidence` trong
  bằng chứng decode kể cả khi hàm bọc giữ PASS cũ; dữ liệu này không đổi phán quyết.
  Alias chỉ truy vết, không tự bảo vệ chữ khỏi TN và làm thay đổi chuỗi nói cũ. Luật anchor tiếng Anh
  bắt buộc và quyền review khi không khớp vẫn giữ nguyên.
  WAV clarity chỉ được commit `verified` khi beam và greedy đều `pass`. Repair round phải nằm trong signal checkpoint
  để crash/resume không bỏ qua lượt xác nhận kép hoặc vượt quá `asr.repair_rounds`.
- Mỗi WAV clarity phải được ghi vào candidate path bất biến riêng; không được thay file hoặc con trỏ SQLite của artifact
  đang giữ trước khi candidate qua đủ beam + greedy. Final quality-check, CAS đổi con trỏ segment và trạng thái `promoted`
  phải commit trong cùng một transaction. Candidate hỏng/mất file phải thành terminal `invalid`; hết budget phải đóng gate
  trên đúng checksum incumbent và giữ nguyên audio incumbent.
- Vocalization cực ngắn/kéo dài phải được chuẩn hóa thành âm tiết tiếng Việt ổn định. Output chạm đúng trần frame
  của VieNeu phải đi tiếp qua signal/Whisper validation, không được tự động coi là audio sai chỉ từ sample count.
  Không gộp chữ đã qua `vietnamese_syllable.valid_syllable` (cứu/lưu/soóc/goòng). Chuỗi kéo dài a/ă/â,
  e/ê, o/ô/ơ giữ chữ có mũ/móc và thanh; ư không gộp với u. Cặp hai nguyên âm phải giống nhau sau bỏ
  thanh mới được gộp trước G2P. Tiếng kêu chỉ có ă/â/y dùng a/ơ/i để đọc được,
  giữ thanh. Python/Kotlin cùng ca parity JNI; namespace clip `shouts2`. Chữ truyện hiển thị không đổi.
  Nếu endpoint vẫn còn hoạt động ở đúng trần thì phải repair kể cả Whisper nhận đúng; không fade/cắt waveform để lách.
- Câu một hoặc hai từ có tối đa tám ký tự đọc được phải dùng ngân sách cực ngắn 24 frame. Nếu câu đó đã chạm
  trần frame rồi bị Whisper xác nhận lệch hoặc endpoint còn hoạt động, repair tiếp theo phải giảm xuống 12 frame để
  chặn VieNeu đọc thêm; câu chỉ có một ký tự đọc được giảm xuống 6 frame. Cap repair phải checkpoint riêng trong
  SQLite, giữ qua các vòng ASR, failure và resume, rồi chỉ xóa sau khi ASR pass; không áp dụng giảm repair cho lần tạo đầu.
- TTS circuit breaker chỉ đếm failure hoàn toàn liên tiếp cùng signature và phải reset sau một segment thành công.
- Mọi kết thúc với `BookStatus.ERROR` phải gửi `finished.ok=false`; nhánh `completed_with_errors` gửi đúng
  một Windows notification nếu policy cho phép, đồng thời giữ nguyên checkpoint/chapter đã commit.
- Không giữ TTS và Whisper đồng thời trên GPU khi không cần.
- Trên Windows, sau khi unload VieNeu hoặc Whisper phải trim working set của worker để các trang model
  không còn dùng được trả về hệ điều hành trước khi nạp model kế tiếp.
- Sau mỗi attempt VieNeu đã trả waveform hoặc lỗi, phải thu hồi object rác và CUDA allocator cache tại ranh giới an toàn.
- RAM critical đơn lẻ phải unload model/cache rồi đo cưỡng bức lại; chỉ chuyển book sang `critical_stop` và gửi notification
  nếu lần đo sau thu hồi vẫn critical. Critical SSD hoặc nhiệt GPU vẫn dừng ngay.
- Khi foreground pressure xuất hiện: hoàn thành đơn vị inference hiện tại, checkpoint, ngừng cấp việc mới, giảm tải/unload nếu cần.
- Không kill CUDA giữa kernel chỉ để nhường tài nguyên.
- Khi resume, settings hash và voice mapping phải giữ nguyên.
- TXT phải được decode từ đúng byte đã hash; ưu tiên BOM/UTF-8/CP1258 và chỉ thử UTF-16 không BOM khi có NUL heuristic.
- Nhập TXT/DOCX/PDF giữ chữ mặc định: phần mở đầu, trang tên và lời chú đều được giữ; suy đoán tên sách không được tiêu thụ dòng chữ.
  Byte TXT hỏng phải báo bạn lưu lại UTF-8/tải lại, không thay bằng ký tự replacement. Chia TXT dùng chung `_txt_cuts`/`txt_starts`
  cho Studio và màn Thêm sách; Kotlin cùng hợp đồng fixture. DOCX giữ dấu gọi/lời chú, đọc trạng thái cuối của tracked moves,
  nhận kế thừa style/outline có chặn vòng lặp. PDF chỉ đề xuất bỏ đọc dòng mép trang, chữ nguồn vẫn còn; đề xuất chắc chắn
  (lặp y hệt đa số trang, số trang trần theo thứ tự) bật sẵn và tắt được. Nguồn máy tính phải khớp fingerprint của preview
  trước/sau parse khi thêm; staging Android giữ tên gốc riêng với tên đĩa để sort/đặt tên/checksum không lệch.
- Pronunciation confidence được lưu trong SQLite; cùng một text đã chuyển cách đọc phải được dùng cho TTS và expected ASR.
- Pronunciation chỉ được lưu theo **từng từ**. Entry nhiều từ phải được tách thành một entry cho mỗi từ;
  không tách được (số từ hai vế lệch nhau) thì bỏ hẳn, vì các từ vẫn có đề xuất riêng trong cùng batch.
  Mỗi từ tách ra phải qua đúng bộ lọc như khi đứng một mình. Lý do: entry đã khóa được khóa theo
  `normalized_surface` của chính nó, nên `Lucien Evans` và `Lucien` không bao giờ đụng nhau — một lần chạy
  thật đã khóa cùng một nhân vật thành cả `Lu-si-en` lẫn `Lư-xi-ên`, và người nghe nghe ra hai cái tên khác nhau.
- Chuẩn hóa pronunciation phải validate và checkpoint theo từng tên. Kết quả hợp lệ không được bỏ chỉ vì tên khác
  trong batch lỗi; resume chỉ xử lý phần chưa khóa. Lỗi ranh giới âm tiết có thể sửa cơ học an toàn như
  `A-der-on → A-đe-ron`; nếu không sửa được, retry chỉ tên lỗi với feedback cụ thể, không gửi lại nguyên prompt/batch.
- Trước khi finalize casting, mọi token tên Latin viết hoa (kể cả chỉ xuất hiện một lần) phải qua bước chuẩn hóa tên:
  VieNeu giữ chữ Anh/tên Tây theo `readaloud/english_policy.py`; dữ liệu mặc định ở `english_policy.json` dùng chung với Kotlin.
  Viết tắt theo bảng chung `english_policy.json`: cách đọc chủ sách, khai triển từ Việt, VN theo câu văn/mã, KTX theo ngữ cảnh tàu và AI theo ngữ cảnh đại từ.
  Các mặt chữ cần ngữ cảnh không được tự khóa thành một cách đọc chung khi lập bảng tên; quyết định ở từng occurrence.
  Mã ngắn chưa rõ đọc từng chữ Anh qua `<en>`, provenance `auto`; từ Anh HOA phải đưa vào máy đọc ở dạng thường. VieNeu dùng bảng dự phòng Nhật
  `readaloud/japanese_policy.json` và asset từ vựng chung với Kotlin, namespace `jp-fallback6`. Tên Latin phải tách hết bằng bảng âm:
  ít nhất hai âm tiết cho dự phòng mới khi gốc cuốn đã là Nhật; chưa rõ gốc cần kính ngữ dính hoặc cặp romaji viết hoa.
  Từ Nhật quen, kính ngữ và cách đọc tên đã được luật cũ chấp nhận có đường riêng; bộ lọc tên không được xoá cách đọc ấy chỉ vì thiếu âm tiết.
  Viết tắt, số và từ mượn đã được xử lý giữ quyền trên output; HOA ngắn không tự thành tên Nhật nhờ đổi hoa thường.
  Từ Việt/từ Anh được bảo vệ; một tên cục bộ không tự nâng gốc cả cuốn. Tiếng kêu, kéo dài và nói lắp chạy trước tên Nhật,
  giữ mảnh âm đã đọc qua bước direct English; mảnh tên còn nguyên cùng token vẫn theo policy Nhật, không phân tích lại âm đã phát.
  Cách đọc người nghe vẫn áp cuối. Khóa tự động theo thành phần; khi materialize,
  hàng Nhật tự động không được che cách đọc người nghe của thành phần và không được đưa kết quả phiên âm qua TN Nhật lần nữa.
  Tên Hàn giữ đường hiện có;
  tên còn mơ hồ tiếp tục đường hiện có. Từ Việt hợp lệ không được phiên âm chỉ vì có trong từ điển Anh; detector chỉ đọc ở
  `scripts/audit_english_homographs.py`. Cách đọc người nghe đặt rõ vẫn thắng. Đổi luật phải đổi namespace cache VieNeu và quality hash;
  không viết lại dự án cũ. Kết quả chuyên biệt hợp lệ phải `locked=1` trong SQLite để cùng một tên
  không đổi cách đọc theo giọng, chapter, confidence threshold hoặc lần resume.
  VieNeu đọc tên Nhật tự động bằng âm vị sea-g2p thường: MỖI âm tiết một từ ngữ âm, trọng âm riêng (`jp-fallback6`, 11-11). KHÔNG nối âm vị
  của tên thành một từ: bản nối (`jp-fallback5`) nuốt âm tiết ở cả hai engine - đo 34 câu x 6 seed, thước CTC đã hiệu chỉnh theo tai chủ sách
  (44/50 ô): Turbo sai tên 46,9 % khi nối / 24,0 % khi tách, Nano 57,8 % / 13,5 %; Whisper-large và PhoWhisper cùng chiều. Dính âm tiết
  không phụ âm đầu vào âm tiết trước ("lai") cũng hỏng đúng chỗ ấy. Đừng cài lại phép nối nếu chưa có số đo mới thắng bản tách.
  Trên desktop có CTC, `readaloud/japanese_audio.py` rút phần năng lượng thấp >=120 ms nằm hoàn toàn trong từng từ Nhật tự động về 80 ms,
  giữ 5 ms crossfade và hai mép thấp năng lượng. Chỉ dùng span CTC đầy đủ với confidence >=0,7; thiếu model/căn yếu thì giữ audio.
  Studio áp sau tempo, trước signal/ASR QA và ghi evidence vào metrics; Nghe ngay áp trước ghép khúc/căn mốc chữ.
  Cache VieNeu desktop mang `jp-name-audio1` cùng trạng thái có CTC. Android chưa có CTC nên không rút lặng, không suy số đo desktop sang Android.
- `readaloud/phoneme_policy.py` sửa ở biên phoneme chung của Studio/Nghe ngay/Kotlin: âm tiết `gi` phải còn nguyên âm `/i/`,
  và `o` của tên đã qua lượt chuẩn hoá đầu không được lượt sau đổi thành tên chữ `ô`. Từ cảm thán/hỏi Anh ngắn,
  có từ điển và không trùng âm tiết Việt, giữ trọng âm mạnh/nguyên âm kéo dài trước `?!`; không thêm từ, đổi dấu câu hay chia riêng để đọc.
  Từ có ở cả hai từ điển của sea-g2p (do, sang, bay, to...) giữ âm Việt khi bảng điểm học từ kho nhận nó là chữ Việt
  (`restore_vietnamese`, bảng `readaloud/shared_words.json` = `vieneu/SharedWords.kt`, cách học và trần: `docs/SHARED_WORDS.md`):
  chỉ dòng âm vị đổi, chuỗi nói giữ nguyên từng byte; chữ viết Hoa giữa câu không bao giờ đổi. KHÔNG vá bảng bằng tay hay thêm
  luật riêng cho một ca: thêm nhãn rồi học lại, sau đó chạy `scripts/build_shared_words.py` để chép sang Kotlin.
  Studio chỉ thấy khúc chữ thường nên `generate_one` phải bọc `infer` trong `sentence_case`.
  Luật này nằm trong quality hash và namespace cache; test qua cả JNI thật và hai đường Python. Cả chuỗi đầy đủ và tiền tố dùng để
  xác định span tên Nhật phải qua cùng luật sửa phoneme trước khi nối, để `gi`/`o` không làm sai phép so tiền tố.
  Chỉ 72 từ mà từ điển Việt của sea-g2p đọc thành âm tiết thanh ngang nằm trong bảng (cat -> "cát", pa -> "pà" thì không:
  âm "Việt" của chúng là đoán dấu). Văn bản truyện và nhãn huấn luyện không vào repo.
  Gate chữ `tests/test_g2pgate.py` giữ token/tên thật và mã băm sách; câu nguồn hiệu chỉnh phải ở ngoài repo.
  Khi lớp/ngôn ngữ đã được cuốn xác nhận, cách đọc ấy phải sống qua cả lớp chữ và lượt sea-g2p thứ hai.
  Sửa âm tiết phiên âm chỉ lấy âm Việt từ chính sea-g2p (thử dấu sắc hợp lệ rồi bỏ đúng thanh thử), không tự tạo IPA;
  chỉ sửa đúng vị trí âm tiết đã sinh, không lan sang từ Anh trùng chữ. Ruling theo occurrence phải mang vị trí qua
  normalizer số/đơn vị; các khoảng giữa tên chuẩn hoá cùng nhau, cue giữ ranh giới fragment. Chỉ dùng ánh xạ khi
  khớp chuỗi chuẩn hoá đầy đủ và chunk đang đọc, tiêu thụ occurrence theo thứ tự. Thẻ Anh nhiều từ vẫn đếm từng
  vị trí whitespace khi tra ruling. Namespace hiện tại `direct-en9`.
- Mọi normalized speaker name dùng đúng một character và một voice profile trên toàn sách; cùng tên không được
  đổi preset theo chapter, cảm xúc hoặc khi resume. Không hợp nhất hai tên khác nhau vì đổi tên/thân phận/chuyển sinh.
  Chỉ gom các DẠNG VIẾT của cùng một tên (`character_registry.canonical_speaker_names`, một hàm dùng chung cho dây
  chuyền và công cụ đo `scripts/model_eval/voice_identity.py`): rơi dấu, "tên + họ bịa" (tên kiểu Âu, chữ đầu), tên
  vắng mặt trong sách, và tên gọi kiểu Việt/Hán Việt ("DU" -> "CHU DU": nhãn một chữ là chữ CUỐI của đúng một tên
  nhiều chữ mà mọi chữ là âm tiết tiếng Việt; tên kiểu Âu thì chữ cuối là họ chung cả nhà, không gom; tên đích mở bằng
  chữ xưng hô thì không làm đích - "CHỊ DẬU" là vợ anh Dậu, không phải "Dậu"). Lượt cuối chỉ
  đổi CHỮ hiển thị, một tên thành một tên: tên sách không viết như thế mà bỏ dấu ra khớp đúng một cách viết tên trong
  sách -> cách của sách ("HOANG CAI" -> "HOÀNG CÁI"). Luật gom mới phải qua `voice_identity.py --gold-check`: không được
  nhập hai người của đáp án làm một. Văn bản cả cuốn không bao giờ `unicodedata.normalize` một lần - CPython chậm vượt
  tuyến tính trên chuỗi dài (21 giây cho 11 triệu ký tự); chuẩn hoá từng dòng hay từng ký tự khác nhau.
- Không dùng cue phi ngôn ngữ thử nghiệm của VieNeu và không thay identity giọng để giả lập cảm xúc.
  Cảm xúc không đổi waveform hay khoảng nghỉ; ghép theo break_ms cấu trúc.
- Chuẩn hóa các cách viết như `haizzzzz`, `hừmmmm` hoặc `[thở dài]` chỉ được áp dụng lên `spoken_text` dùng chung cho
  TTS và expected ASR; văn bản nguồn, hash và segment đã checkpoint không được sửa.
- **Biến thể pitch là nguyên nhân hỏng chất lượng lớn nhất đo được, không phải preset hay vùng miền.**
  Trên 597 segment của ba lần chạy: `pitch = 0` fail **2,8%** với WER trung vị `0,050`; `pitch ≠ 0` fail
  **9,4%** với WER trung vị `0,154` — tệ hơn 3,4× và 3×. UTMOSv2 nói cùng một điều một cách độc lập: dịch
  `-1` bán âm làm mất `0,33`–`1,17` MOS tuỳ preset. Người nghe tiếng Việt còn **không nhận ra đó là giọng
  của preset gốc nữa**, nên pitch không chỉ hạ độ tự nhiên mà đổi luôn nhận diện giọng.
  Đừng đổ lỗi cho một preset khi số liệu chỉ vào biến thể pitch của nó: `Xuân Vĩnh`
  ở `pitch 0` fail **0/13**, còn các biến thể `-1/+1/+2` của chính nó fail 25–33%.
- Whisper sai **thanh điệu** tiếng Việt ở mọi segment, cả đạt lẫn fail — verified median `0,000` nhưng p99
  `0,362`, so với median `0,296` của segment fail, và có segment đạt với tỉ lệ `1,000`. Hai phân bố không
  tách nhau, nên chênh lệch thanh **không mang tín hiệu** về chất lượng take. Content gate vì thế gấp thanh
  ra khỏi phép đo và lấy kết quả tốt hơn giữa hai cách đọc, để phép gấp **không bao giờ** làm fail thứ mà
  so chữ đã cho qua. Hệ quả phải nói rõ: ASR gate không còn phát hiện lỗi thanh của TTS — nhưng nó vốn cũng
  chưa từng phát hiện được, vì không phân biệt nổi lỗi thanh của TTS với lỗi thanh của ASR.
- Miễn trừ anchor tên riêng phải **theo tỉ lệ**, không theo số token tuyệt đối: tên không được chiếm đa số
  những gì đang kiểm, và phải còn ít nhất hai token thường. `Giô-en cười trừ` còn 2 token thường trên tên
  2 token nên vẫn kiểm được; `Anh Lu-si-en` chỉ còn `anh` trên tên 3 token nên anchor giữ quyền hard-fail.
- Giọng miền Trung **không bao giờ được phân vai**, kể cả cho NPC, kể cả qua nhánh fallback khi pool cạn.
  Tiếng Trung là phương ngữ khó hiểu nhất với người nghe hai miền còn lại, và hệ thanh điệu của nó lệch xa
  nhất so với chính tả chuẩn miền Bắc mà audiobook đọc từ đó; đo trên audio đã commit, preset Trung sai thanh
  ở **từ thường** chứ không phải ở tên riêng (`khốn kiếp` → `khôn kiêp`), mà thanh điệu mang nghĩa từ vựng.
  Preset vẫn nằm trong catalog vì VieNeu có chúng và sách cũ có thể đã khóa chúng — chỉ là không được cast.
  Mọi đường dẫn tới preset đều phải tôn trọng `CASTING_REGIONS`; một fallback quét cả catalog sẽ đưa chúng
  quay lại sách.
- Preset được phân bổ theo giới tính và ưu tiên dùng hết pool phù hợp trước khi tái sử dụng. Trong cùng mức sử dụng,
  bảng hạng người nghe đi trước các thước đo; giọng ngang bậc hoặc chưa xếp mới phân xử theo các thước đo và thứ tự cũ.
- `voice_catalog.preset_eligible` là cửa dùng giọng theo vai: preset được chủ sách xếp trong `assets/voice_rank.json`
  được dùng cho đúng vai ấy bất kể style catalog; tin tức chưa được xếp vẫn bị loại. Vùng miền và lệnh cấm phân vai
  vẫn giữ nguyên khi tự chọn. `never_auto` cấm tự chọn ở cả hai vai và cả dự phòng; danh sách chọn tay vẫn giữ các giọng ấy.
  Bảng hạng ưu tiên hơn thứ tự catalog; mặc định nữ là Ngọc Linh, nam là Đức Trí. Hạng dẫn nữ đầu gồm Ngọc Linh và Kim Thanh ngang nhau.
- NPC có nhãn cục bộ được giữ identity riêng trong phạm vi chapter/batch; NPC không phân biệt được
  ít nhất phải tách pool nam, nữ và chưa rõ giới tính.
- Nhãn NPC cục bộ trùng chính xác với tên nhân vật trong cùng chapter phải được hợp nhất trước khi
  phân vai, tránh cùng một người bị khóa hai giọng khác nhau.
- Tên trong lời gọi trực tiếp như `Anh Lucien!` hoặc `Iven, ...` là addressee, không phải bằng chứng về speaker.
  Nếu analysis vẫn gán tên đó làm người nói, validation phải tách thành NPC cục bộ `người gọi <tên>`, áp dụng
  nhất quán cho cùng local speaker trong batch. Repair marker chỉ được dùng tạm trong validation; projection speaker
  đã sửa mới là dữ liệu được candidate ledger và critic khóa.
- Segment mới dùng gain hằng số của preset, không có chênh lệch theo vai hay nhãn volume.
  Sample peak cap vẫn bắt buộc sau khi áp gain.
- Cân mức câu giữ `min(loudness_gain, peak_safe_gain)`. Master chương dùng đúng +5 dB từ hiệu chuẩn
  cho mọi chương/mọi sách, không lấy LUFS hay peak chương để chọn gain. Limiter true-peak oversample 4 lần,
  không auto-level, chỉ hạ envelope quanh đỉnh theo `true_peak_db`; báo cáo phần thời gian và mức hạ lớn nhất.
  LUFS chương là chẩn đoán, không hard-fail theo một target chung.
- `segment_endpoint_floor_dbfs` đo trên WAV **đã cân mức** nên phải dịch theo anchor loudness; còn
  `segment_active_floor_dbfs` đo trên waveform **trước gain** nên phải giữ nguyên. Trộn hai cái này lại sẽ âm thầm
  làm gate "endpoint còn hoạt động ở trần frame" mất độ nhạy.
- Truyện kể ngôi thứ nhất: `voices.first_person_identity` (câu hỏi "'Tôi' là ai?" lúc tạo sách, `cli create
  --first-person`) được đưa vào prompt phân tích MỖI batch (`analysis._narrator_line`) và vào dấu vân tay sổ ứng viên
  (`_analysis_policy_fingerprint`); không đặt thì prompt và dấu vân tay y hệt trước, để sách cũ resume nguyên vẹn. Đo
  27-09 trên chương ngôi thứ nhất YMP 248: model tinh chỉnh 34,0% -> 89,4% người nói - không có dòng ấy, lời của người
  kể bị gán cho chính người đang nói chuyện với anh ta (không mang nhãn đại từ nào, nên `resolve_first_person_labels`
  sau phân tích không cứu được). Máy chỉ ĐOÁN truyện nào kể ngôi thứ nhất (`first_person.py`), tên người kể do người
  dùng chọn từ gợi ý - đoán tên từ văn bản thô từng ra "Portal".
- Ngoặc kéo dài qua nhiều paragraph phải giữ độ sâu lồng nhau. Dấu ngoặc chỉ tạo `kind_hint`;
  generator và critic quyết kind theo ngữ nghĩa, không có khóa dialogue/thought chỉ từ hint.
  Nội tâm giữ danh tính người nghĩ. A+ mặc định căn giọng dẫn cùng giới người kể “tôi” khi
  narratorAuto, chưa có bản thu và người nghe chưa chọn giọng dẫn; tránh preset nhân vật đang giữ.
  Nội tâm có đánh dấu của chính người kể “tôi” dùng profile giọng dẫn; nội tâm người khác/ngôi ba
  giữ giọng người nghĩ. Ngoại lệ chương/đoạn khác giới so với giọng dẫn SAU căn A+ dùng giọng nhân vật ấy.
  Các thay đổi tự động chỉ áp câu chưa thu, không sửa speaker/character/kind; SQLite giữ profile gốc để hoàn tác.
  Lựa chọn rõ `mode=teller` áp cả người kể cùng giới và chỉ đổi lớp giọng lời dẫn, giữ identity,
  lưu provenance và reset audio trong cùng transaction. SQLite là thẩm quyền sau crash/reopen.
- Lời dẫn chỉ có thẩm quyền khi chủ thể gắn với động từ phát ngôn thật; hành động, phản ứng,
  ý định chưa nói và phép so sánh không đủ. Cue generic yếu không đè nhãn chắc, không làm neo
  lan theo đoạn; mention do app suy ra có phạm vi paragraph. Chuỗi thoại liền nhau của đúng hai
  người có thể hồi phục phase khi ít nhất một lời gọi xác định duy nhất một thứ tự xen kẽ.
  Đây là heuristic, không phải bằng chứng mọi lượt đều đổi người. Tự giới thiệu, trả lời tên
  (kể cả nhiều câu và câu trả lời tiếp câu hỏi tên), trích lồng và tên người con trong nhãn quan
  hệ không được làm neo. Câu kể xen giữa hoặc lời dẫn cùng paragraph làm ngắt chuỗi;
  stage lời dẫn không tự lan ABAB. Trích thuật ngữ không có cue
  rõ phải có đủ hai nửa câu kể cùng paragraph, kể cả ngoài mép batch; một hành động nối tiếp
  không đủ để tước identity. Nhãn quan hệ giữ đầy đủ vai và không fuzzy-snap vào tên của người khác.
- Với profile `high_quality`, batching phải giữ nguyên source unit gồm các segment cùng paragraph và phần tiếp nối của
  cùng một ngoặc kép ngoài qua nhiều paragraph. Source unit không quá cap 5 segment không được chia lại khi retry; unit
  vượt cap mới được hard-split hữu hạn. Lời dẫn narration cùng paragraph phải đi chung với lượt thoại để attribution không
  bị cắt khỏi speaker.
- Whisper phải nhận WAV đã đọc/resample trong process; không truyền đường dẫn cho API Whisper vì bản
  dependency hiện tại sẽ gọi FFmpeg subprocess cho từng segment và gây nháy console trên Windows.
- Recovery xóa `.part`, reset stage dở và chỉ reuse artifact có checksum + validation hợp lệ.
- Project `completed` được fast-path nếu toàn bộ chapter/full-book MP3 còn decode + checksum hợp lệ.
- Dừng cưỡng bức phải kết thúc process con trước process worker để không bỏ lại FFmpeg/Ollama helper.
- Ollama ẩn phải ghi stdout/stderr vào `runtime/logs/ollama-server.log`; không bỏ mất bằng `DEVNULL`.
- Lỗi transport Ollama (`ConnectionError`, `Timeout`, `ChunkedEncodingError`) tuyệt đối không được kết thúc cả book.
  Kết nối chết trước khi nhận được ký tự response nào là replay an toàn: request được gửi lại tối đa
  `OLLAMA_TRANSPORT_RECONNECT_ATTEMPTS` lần trong cùng attempt đã reserve, có backoff và vẫn tôn trọng wall timeout
  cùng stop request. Khi đã nhận một phần response thì không được replay vì stream không còn tái lập được.
  Transport fault thoát ra khỏi lớp replay trong lượt director critic bền phải tiêu đúng attempt đã reserve giống hệt
  một lần crash sau reserve, ghi event `ANALYSIS_CRITIC_TRANSPORT_FAULT`, rồi để vòng lặp durable đọc lại candidate và
  đi tiếp; hết ngân sách thì rơi vào nhánh terminal/split thông thường, không raise xuyên pipeline.
- Stream Ollama kết thúc thiếu `done=true` phải chia đôi batch hiện tại và chạy batch con; không retry nguyên
  batch lớn nhiều lần. Segment chỉ còn một phần tử mới dùng retry thông thường.
- Phản hồi Ollama đã kết thúc nhưng thiếu ID segment bắt buộc được retry theo policy; nếu batch nhiều phần tử
  vẫn thiếu sau các lần retry, phải chia đôi batch và tiếp tục. Chỉ được kết luận lỗi bắt buộc khi batch đơn
  không thể tạo đủ kết quả hợp lệ.
- Phản hồi analysis đúng schema vẫn phải qua semantic delivery gate trước checkpoint. Emotion `happy` mâu thuẫn
  hoặc cả batch bị co về `neutral/intensity=0/normal` dù có nhiều cue cảm xúc rõ ràng
  phải bị từ chối; gate ghi đúng cue đã khớp và gửi feedback cụ thể
  vào lần retry và chia đôi batch nếu vẫn sai. Nhãn đồng nhất đơn thuần không đủ để kết tội một batch hợp lệ.
- Một segment có đúng signature `neutral/intensity=0/pace=normal/volume=normal` và cue cảm xúc mạnh phải bị
  từ chối riêng ở mọi `kind`, kể cả khi batch đã chia xuống dưới ngưỡng dominance hoặc singleton. Với dialogue/thought,
  `neutral` vẫn bị từ chối khi có cue trực tiếp, trừ trường hợp thật sự có cả affect dương và âm; cue nằm đúng phạm vi
  phủ định/ngăn cấm không được tính là mâu thuẫn.
- Narration có đồng thời bằng chứng tổn thương hô hấp nghiêm trọng và suy giảm ý thức không được checkpoint thành
  `neutral/intensity=0`; một mô tả thể chất hoặc quan sát lâm sàng đơn lẻ không đủ để kích hoạt rule này.
- Hai cue narration nguồn hẹp `narration_recalled_persistent_fear` và `narration_stunned_blank_mind` phải khóa
  nguyên `kind=narration` và lần lượt chỉ cho phép emotion `afraid` hoặc `surprised`. Predicate nguồn dùng chung với
  DB replay là thẩm quyền duy nhất; không lan cue từ hàng xóm, không tự sửa output model và không dùng khóa này để
  bỏ qua director critic.
- Rule `narration_sleep_paralysis_helplessness` chỉ được kích hoạt cho grammar nguồn allowlist: đúng tiền tố
  `giống như mấy lần`, đúng chủ thể trực tiếp, hoặc `giống như <đúng chủ thể>`; sau đó phải có liền mạch
  bóng đè -> nhận thức đang mơ -> muốn thoát -> bất lực điều khiển cơ thể, cùng một chủ thể và không có phủ định,
  giả định, lời trích, meta, affect đối nghịch hoặc trạng thái đã giải quyết. Rule khóa đồng thời
  `kind=narration` và `emotion=afraid`; câu kể ngôi ba “cậu biết... muốn...” không phải thought trực tiếp.
- Rule affect nguồn hẹp phải chạy trước semantic cue chung. Constraint deterministic đã phát hiện phải được tích lũy trong
  suốt retry của cùng target group, không được ghi đè bởi lỗi của lần sau hoặc chuyển thành feedback tự do.
- Mọi `allowed_emotions` source-authoritative từ host affect/physical-collapse phải khóa schema generator ở lần retry theo
  đúng ID bằng `segments.items.oneOf`; nhiều host constraint cùng ID phải lấy giao và giao rỗng phải fail-closed trước HTTP.
  `allowed_emotions` của `SEMANTIC_DELIVERY_MISMATCH` chỉ là advisory và tuyệt đối không được thu hẹp schema emotion.
- Khi một target group bị chia, toàn bộ feedback typed đã tích lũy của group cha phải được lọc theo `stable_id` rồi chuyển
  vào đúng group con trong cùng lượt phân tích. Không được để split làm mất constraint của câu đã sửa; source unit
  high-quality vẫn giữ nguyên tử theo invariant batching ở trên.
- `DIRECTOR_FIELD_MISMATCH` phải gửi lại cho generator projection advisory canonical của critic, nhưng chỉ cho các field
  delivery allowlist `emotion|intensity|pace|volume`; không chuyển kind, speaker, source text, quote hoặc rationale.
  Projection này không phải host lock và không được thu hẹp schema. Retry sinh lại từ đầu nên giá trị đã sửa phải được giữ
  qua các lượt/split; correction mới chỉ ghi đè đúng field nó thay đổi, còn field critic vừa đồng ý phải tiếp tục được nhắc.
- Semantic cue chung chỉ được dùng `allowed_emotions` source-derived làm lựa chọn retry advisory khi chính candidate
  `emotion=neutral` bị từ chối. Tập lựa chọn phải hợp deterministic từ cue trực tiếp không bị phủ định/meta/lịch sử và
  không có affect đối nghịch, không chứa source/cue/rationale trong payload. Đây không phải host whitelist, semantic lock
  hay exact-membership gate: model vẫn phải chọn delivery tốt nhất và candidate sửa xong vẫn qua đủ validation + critic.
- Ba cue nhận thức mơ hồ `thất thần|bàng hoàng|hỗn loạn` thuộc lớp nội bộ `disoriented`: chúng là bằng chứng chống
  `happy` sai nhưng không được coi là cue trực tiếp để từ chối `neutral`, không tạo `allowed_emotions` và không tự ép
  thành `afraid`/`surprised`. Cue sợ hãi rõ ràng cùng xuất hiện vẫn được xét độc lập theo contract `afraid`.
- Với narration/NARRATOR chỉ có đúng cue active `disoriented`, không có dấu hỏi/cảm thán và candidate tiết chế
  `neutral`, intensity `0|1`, pace/volume `normal`, host được phép giữ candidate trước critic tự-review suy diễn
  `afraid` kèm ít nhất một escalation intensity hoặc pace. Override compatibility chỉ được phủ tập con
  `emotion,intensity,pace`; mọi cue affect khác, delta `kind/speaker/volume`, intensity không tăng, pace không thành
  `fast` hoặc emotion khác `afraid` đều phải fail-closed. Raw verdict/delta vẫn lưu đầy đủ; SQLite phải dựng lại exact
  rule từ source text/hash, source kind, candidate, critic và partition khi critic completion, reopen và commit.
- Candidate qua rule affect nguồn hẹp phải mang semantic lock source-bound vào critic row và durable clearance. Với lock một
  field, critic correction chỉ được host override khi có delta duy nhất trên field khóa và giá trị đề xuất nằm ngoài tập host
  cho phép. Riêng rule bảo vệ cả source kind và emotion được phép compose hai override đúng hai field đó; mọi raw verdict/delta
  vẫn phải lưu và `intensity/pace/speaker/volume` không được che. Không delta được host suy là agreement; mọi delta chưa được
  lock bao phủ hoặc đổi giữa hai giá trị đều được host cho phép phải fail-closed. Chỉ cần một verdict trong payload critic sai
  protocol thì toàn payload là `critic_invalid` và retry nguyên durable candidate, không lưu nửa batch thành rejected evidence.
- Profile `high_quality` bắt buộc chạy một lượt director critic thứ hai trên candidate analysis bất biến. Critic không
  được thấy confidence, notes hoặc personality tự chấm của generator; response phải có đúng schema, đúng một verdict
  cho mọi ID và khớp chính xác candidate hash. Critic dùng cùng model chỉ là self-review có tương quan, không phải model
  độc lập, nên không bao giờ được vượt qua semantic gate tất định. Field delta chỉ có thể thành pass qua structural lock,
  semantic/source-kind lock hoặc compatibility override `disoriented` hẹp đã mô tả và được DB replay độc lập ở trên.
- Director critic cho source `kind_hint=thought` chỉ nhận `previous_context_only`: giữ đúng source trước liền kề để hiểu
  lời dẫn/attribution nhưng bắt buộc để `next_text` rỗng, ngăn sự kiện tương lai cho mượn emotion/intensity/pace/volume
  vào suy nghĩ hiện tại. Generator vẫn nhận adjacent context; narration/dialogue critic thông thường vẫn dùng
  `adjacent_context`.
- Director critic cho source narration đứng ngay trước source thought ở paragraph kế tiếp phải dùng
  `narration_precedes_next_paragraph_thought`: giữ previous source nhưng xóa `next_text` để thought tương lai không cho
  mượn câu hỏi, kind hoặc affect vào target. Đây chỉ là context mask: generator vẫn nhận adjacent context, policy không tự
  tạo `host_locked_fields`, semantic clearance, feedback constraint hay source-kind override. Raw critic verdict/delta vẫn
  phải được lưu và mọi dissent chưa có authority độc lập vẫn fail-closed. Semantic lock nguồn khác vẫn được compose bình
  thường. SQLite phải tính lại context hash từ current + neighbor stable ID, text SHA, chapter, seq, paragraph và kind ở
  allocate/reopen/critic completion/commit; policy, neighbor hoặc lock/override bị chèn sửa phải bị từ chối.
- `kind_hint=dialogue|thought` không tạo host kind lock hoặc source-kind override. SQLite phải chấp nhận
  kind ngữ nghĩa khác hint khi candidate/critic đồng ý và vẫn kiểm source/context/hash như thường;
  khóa dialogue chỉ dựa trên hint phải bị từ chối. Các khóa narration có predicate ngữ nghĩa độc lập vẫn giữ.
- Director critic cho narration là lời dẫn ngay trước source thought cùng chapter và paragraph phải dùng
  `narration_before_thought_previous_only`: giữ previous source nhưng xóa `next_text` từ immutable original context.
  Source parser sở hữu bất biến `kind=narration`: generator vẫn nhận đủ adjacent context nhưng validation/feedback phải
  dùng chính immutable original context để từ chối relabel thành thought trước khi cấp candidate. Critic row mang
  kind-only host lock tách biệt semantic clearance; nếu critic vẫn đổi kind thì evidence phải giữ nguyên verdict/delta thô
  và chỉ được override đúng field `kind`. Override bền phải khóa stable ID + SHA-256 của target và thought kế tiếp;
  SQLite tính lại hash từ text related khi allocate/reopen/accept/commit. Mọi delta emotion/intensity/pace/speaker/volume
  chưa có semantic lock riêng vẫn unresolved và fail-closed; kind-only context lock không làm tăng semantic-lock count.
- Model không được sở hữu `notes` hoặc `personality_hint` được commit. Host phải tạo note canonical chỉ từ delivery cuối
  sau repair; personality model phải rỗng và segment note không được chứa marker điều khiển. Marker repair chỉ là state tạm
  trong một lượt validation và phải bị xóa trước candidate. Candidate ledger + critic khóa projection analysis đã chấp nhận;
  bước casting sau đó chỉ được phép reconcile speaker bằng phép biến đổi source-derived, deterministic và được khóa bằng
  fingerprint stage riêng. SQLite phải tính lại và từ chối note/personality/marker không canonical khi allocate, reopen,
  direct update và commit. Speaker repair không được sao chép note từ segment khác, và character registry không được dùng
  prose delivery làm personality hoặc dùng marker legacy làm quyền điều khiển identity.
- Tiêu đề chương chỉ được nhận diện bằng source metadata đầu chapter và grammar tiêu đề độc lập. Host phải khóa delivery
  tiêu đề về narrator trung tính cùng confidence candidate `0.95`, không gửi ngữ cảnh hàng xóm cho row đó và vẫn giữ
  nguyên proposal/confidence/verdict thô để audit. Critic confidence vẫn phải qua floor nhưng chỉ là evidence thô cho row
  cấu trúc; derived/validated/commit confidence của tiêu đề đã khóa phải luôn giữ đúng `0.95`, kể cả khi critic hoặc cap thấp hơn.
  Content row mới tính confidence commit bằng `min(generator, critic, cap)`.
  Structural override chỉ được phép cho đúng row đã khóa; mọi content row vẫn chịu critic bình thường. Mỗi verdict critic
  phải trích nguyên văn bằng chứng không rỗng từ chính text cùng ID, không được lấy bằng chứng từ row lân cận. Multi-row
  phải dùng canonical ordered per-ID source-anchor map: schema `items.oneOf` khóa từng nhánh vào exact ID + enum anchor,
  host kiểm exact membership và durable contract khóa map hash + tổng anchor count, không dùng union/substr tự do.
  Singleton có toàn bộ target dài từ 1 đến giới hạn quote phải khóa schema và contract vào exact
  full target + source hash. Singleton dài hơn giới hạn quote phải dùng tập source anchor deterministic, nguyên văn và không
  vượt giới hạn; schema chỉ chấp nhận đúng một anchor trong enum, còn contract bền phải khóa source hash, hash tập anchor và
  số anchor. Không được tự cắt, nối, chuẩn hóa hoặc chấp nhận một substring ngoài enum. Critic model không trả boolean accept:
  host suy agreement chỉ khi cả sáu delivery field không có delta, và evidence compatibility phải lưu accept đúng bằng kết
  quả host-derived đó.
- Với analysis bắt buộc ở profile `high_quality`, mọi content candidate dưới `low_confidence_threshold` phải bị từ chối
  bằng feedback số typed trước critic/candidate ledger. Prompt generator luôn phải mang đúng floor; schema áp floor trực tiếp
  cho batch không có tiêu đề, còn batch trộn tiêu đề+nội dung phải giữ proposal confidence thô của tiêu đề và dùng host gate
  để áp floor lên content. Tiêu đề cấu trúc được normalize trước gate này. Confidence được commit phải nằm trên ngưỡng khóa
  và không vượt cap của director. Contract critic phải khóa đúng floor/cap trong schema + prompt, evidence policy + target hash
  + anchor-set hoặc per-ID anchor-map hash/count;
  confidence dưới floor, rationale lỗi và evidence quote lỗi phải có reason host-derived riêng trong durable outcome.
  Model name + digest Ollama phải được
  khóa bền ở cấp book, kiểm tra lại trước và sau mọi request generator, critic và pronunciation; tag/digest đổi giữa
  request hoặc giữa hai lần resume phải fail-closed. Project high-quality legacy đã có analysis checkpoint nhưng chưa có
  critic contract không được trộn dữ liệu cũ/mới; phải tạo project sạch.
- Batch được critic chấp nhận, event evidence và pronunciation proposal đã validate phải commit trong cùng một transaction
  SQLite với CAS trên ID, source hash và trạng thái segment. Crash không được để lại batch analyzed thiếu event hoặc thiếu
  pronunciation; retry critic/schema giữ nguyên candidate hash, còn singleton persistent failure phải dừng hữu hạn.
- Candidate analysis high-quality phải có hai identity tách biệt: hash projection delivery mà critic nhìn thấy và hash
  acceptance envelope đầy đủ gồm source, metadata, confidence và pronunciation. Intent critic phải được reserve bền trước
  HTTP; mọi attempt, generator contract và kết quả phải re-hash khi đọc. Crash sau reserve tiêu attempt hiện tại, crash sau
  `critic_accepted` phải commit lại đúng envelope mà không gọi model, còn candidate projection lặp lại không được reset budget.
- Policy/group/context fingerprint của ledger phải khóa model digest, system/schema version, source hash và metadata ngữ cảnh
  mà host dùng (stable ID, chapter, paragraph, kind và hàng xóm). Parent candidate và lịch sử child attempt phải liên tục,
  khớp trạng thái; SQLite phải tự đối chiếu lại source role/seq/paragraph/kind/text của structural row. Mismatch/tamper phải
  fail-closed trước request hoặc commit. Chỉ cần ledger analysis đã có candidate là analysis đã bắt đầu, kể cả mọi segment
  còn `pending`; casting fingerprint đổi sau điểm đó phải yêu cầu project sạch.
- GUI chỉ cung cấp một lệnh **Dừng**; đây không phải một chế độ an toàn riêng. Lệnh Dừng yêu cầu worker
  kết thúc ở ranh giới gần nhất, còn đóng cửa sổ được phép kết thúc worker ngay.
- Tính an toàn phải đến từ transaction SQLite, file `.part` + atomic replace, checksum và recovery:
  app/worker bị kill ở bất kỳ thời điểm nào cũng không làm mất artifact đã commit; phần dở được reset khi resume.

## Cấu trúc source

```text
ABook.lnk
README.md
_internal/
├── ABook.vbs          # launcher thật; shortcut root/Start Menu trỏ trực tiếp vào đây
├── AGENTS.md          # tài liệu dành cho agent/lập trình viên
├── app.py
├── abook/      # Python package chính
├── tests/
├── scripts/            # setup và system check
├── docs/               # test report và third-party notices
├── runtime/            # được tạo khi cài: venv + model cache
├── pyproject.toml
└── LICENSE
```

Tên kỹ thuật duy nhất là `abook`; tên hiển thị là `ABook`; thư mục dự án là `D:\Novels\ABook`, repo `ntanhpro1221/ABook` từ 28-09. Không đưa file kỹ thuật mới ra root nếu không thật sự cần cho người dùng.

Module chính:

- `desktop.py`: cửa sổ app mặc định (`app.py`) - giao diện web (`webui/`) trong Qt WebEngine; mở kèm file `.abook`
  thì nhập (`webui/packages.py`) và mở cuốn ấy, lần mở thứ hai chuyển file qua khoá một phiên bản. Phục vụ bản dựng
  `webui/static/` (npm run build trong `ui/`, không commit).
- `gui.py`: giao diện cũ (`app.py --classic`), UI/controller, không chứa model logic.
- `worker.py`: process, heartbeat, watchdog, exception boundary.
- `cli.py`: CLI headless create/run/resume/status/stop/log/validate/report/doctor/test; nhánh quan sát là read-only.
- `background_runner.py`: supervisor ẩn, handshake, process identity, persistent stop request và event log.
- `pipeline.py`: orchestration và state transition.
- `database.py`: schema/transaction API.
- `analysis.py`: Qwen structured analysis.
- `speaker_pass.py`: lượt "người nói từng câu" (B41) sau khi phân tích xong cả sách và sau hai lượt hoà giải, ngay TRƯỚC character registry/casting (đúng thứ tự lượt đo): hỏi lại
  người nói của từng câu `dialogue`/`thought` bằng model đi cặp (`abook-speaker:v2`); dựng đề trùng từng byte với mã đo
  (`tests/fixtures/speaker_pass`). Khoá model + digest + tokenizer theo sách (`speaker_pass_state`), commit theo chương
  (`speaker_pass_chapters`), nhãn gốc của model phân tích giữ ở `speaker_pass_labels`.
- `character_registry.py`: canonical speaker name và voice mapping; không hợp nhất identity khác tên.
- `tts.py`: VieNeu preset adapter, tempo và deterministic retry.
- `asr.py`: Whisper và transcript metrics.
- `audio_io.py`: validation, atomic audio, playlist.
- `resource_manager.py`: resource snapshot/decision.
- `recovery.py`: integrity/checksum recovery.
- `notifier.py`: Windows notifications.
- `process_utils.py`: kết thúc an toàn cây process worker/native helper.
- `scripts/start_windows.ps1`: hiện một console ngay khi khởi động, báo tiến độ trong lúc kiểm tra runtime/nạp GUI,
  mở app bằng `pythonw.exe` và tự đóng console theo ready marker do GUI ghi sau khi cửa sổ đã render;
  mọi output được append vào `runtime/logs/startup.log`; lỗi được bắt ở boundary ngoài cùng và console
  phải giữ mở cho tới khi người dùng chủ động nhấn phím/đóng cửa sổ.
- GUI giữ một `QLocalServer` theo user session để khóa single-instance; lần mở sau gửi lệnh kích hoạt cửa sổ
  đang chạy rồi thoát sạch, không tạo thêm tray icon hoặc worker controller.

## Quy tắc thay đổi

- Normalize chapter input to NFC per line after invisible-marker removal and before segmentation or stable IDs. Preserve raw source bytes and checksums. Normalize TTS/Reader tokens and reading maps at comparison boundaries; desktop and Android share the reading cache rule version.
- Redo compares selected chapter content and locked creation choices before reusing an unstarted project. Restarting interrupted analysis copies selected sources before moving the draft to recoverable trash, restores it if creation fails, and preserves the display-only source hint. The fresh project owns its source copies.

- Tuỳ chọn âm thanh khi nghe thuộc thiết bị: mặc định dùng chung; `Riêng sách này` sao chép bộ hiện tại theo mã sách, tắt thì dùng lại bộ chung. Bao gồm tốc độ/âm lượng và DSP; không sửa bản thu, preset TTS hoặc evidence QA.
- Âm sắc khi nghe có kho preset riêng của người nghe, mặc định toàn app và tuỳ chọn riêng sách. `abook/webui/assets/tone_presets.json` là nguồn duy nhất của tần số, Q và bảy đường cong có sẵn; `scripts/gen_tone_presets.py` sinh hằng native và bảng tên tường minh trước khi sinh ui_strings. Không dùng preset hệ thống Android. Tắt bỏ qua bộ lọc và giữ nguyên PCM; preset cá nhân có bản nháp bền, CRUD/hoàn tác/thứ tự riêng, chỉ hỏi lưu các thay đổi khi rời trang. Không chuyển dữ liệu preset cũ.
- Bỏ khoảng lặng mặc định tắt, đo PCM nguồn trước gain/EQ trên mọi kênh. Chỉ rút quãng dài hơn thời lượng chọn, giữ hai mép và ít nhất 1,5 s (nhịp ngăn cảnh TTS). Đồng hồ, phụ đề và anchor dùng thời gian nguồn ở con trỏ đã nghe, không dùng tổng khung giải mã trước; tua/đổi nguồn đặt lại bản đồ. Web chỉ tua qua quãng đã quét, live clip chưa quét giữ nguyên.
- UI copy lives in `ui_strings/vi.json`; design token values live in `ui_design/tokens.json` and are checked against `docs/DESIGN.md`.
  Run `scripts/prepare_ui.py` before building web, Compose or Qt. Never edit generated `UiStrings.kt`, `strings.xml`,
  `strings.generated.ts`, `UiStrings.js`, `uistrings.generated.h`, `Tokens.kt`, `Theme.qml` or generated token declarations by hand.
  New handwritten UI copy fails the shared build gate. Every exact exception in `ui_strings/exceptions.json` needs a reason;
  every remaining Qt wording candidate needs its own explanation in `ui_strings/qt_wording_review.json`.

- Database/recovery change phải có crash/reopen test.
- Resource policy change phải test bằng snapshot giả lập.
- Pipeline change phải có mock adapter để test không cần model.
- Không đổi model revision hoặc tải model trong một job đang chạy.
- Không tuyên bố chất lượng/hiệu năng RTX 5060 nếu chưa test trên máy thật.
- Khi throughput xung đột với toàn vẹn output, chọn toàn vẹn output.
- Không đưa lại tên, lịch sử hoặc mô tả của các prototype/gói generate tạm vào source hay tài liệu.

## Quy trình dev: chạy thật và tự đánh giá

Mỗi phiên bản là một tag Git kèm một lần chạy thật; lịch sử lý do nằm ở `docs/VERSIONS.md`, không phải ở
commit message. Output audio của từng phiên bản được giữ lại ngoài repo tại
`D:\Novels\Audiobooks\_versions\<tag>\` để nghe đối chiếu và **không bao giờ được commit**.


Dev **không** mở GUI để thử. Vòng lặp chuẩn là headless, tự đọc log và tự chấm output:

```text
cli create --profile high_quality  →  scripts/run_book_job.py <project-root>
→ đọc JSONL message stream + cli status/report
→ chấm audio bằng scripts/audit_audiobook.py
→ sửa code → tạo project sạch → chạy lại
```

- `scripts/run_book_job.py` chạy `run_worker` trong process hiện tại và in mọi message dạng JSONL.
  Trên Windows phải reconfigure stdout/stderr sang UTF-8 trước khi in, vì tên nhân vật và log tiếng Việt
  sẽ làm luồng cp1252 chết và giết luôn thread drain.
- App **tự khởi động Ollama ẩn** bằng `ollama serve` + `CREATE_NO_WINDOW`, log vào `runtime/logs/ollama-server.log`.
  Không bao giờ mở Ollama desktop app. Nếu thấy icon Ollama ở system tray thì đó là do một lệnh `ollama`
  thủ công (ví dụ `ollama list`) đã kích hoạt stub tự khởi động `ollama app.exe --hide --fast-startup` của Windows,
  chứ không phải app này. Bằng chứng phân biệt: server do app khởi động luôn ghi dòng
  `--- ABook started Ollama at <thời điểm> ---` vào `runtime/logs/ollama-server.log`.
- Đổi bất kỳ file nào trong `QUALITY_IMPLEMENTATION_FILES` sẽ đổi quality-policy hash và làm project đang dở
  không resume được. Đây là hành vi đúng: sửa code xong thì tạo project sạch, đừng cố resume.
- Iterate bằng project nhỏ (2–3 chapter) để có audio nhanh, chỉ mở rộng phạm vi khi chất lượng đã ổn.

## Throughput

Đo ngày 2026-08-31 trong lúc chạy thật: GPU **14–18%**, VRAM **1,30/8,15 GB**, CPU **0,8/32 core**, đĩa
**99% idle**. Không tài nguyên nào bão hoà, mà vẫn mất ~6,7s cho ~7,4s audio. Nguyên nhân là VieNeu decode
**tự hồi quy từng frame**, tức latency-bound — thêm CPU hay đĩa không giúp gì.

- Nâng utilization của decode tự hồi quy **chỉ có thể** bằng cách cho nhiều câu chạy đồng thời.
- Nhưng `_set_generation_seed` seed **global cho cả process**, nên batching trong cùng process hoặc chạy
  nhiều luồng sẽ làm audio của một câu phụ thuộc vào hàng xóm trong batch, phá tính tất định khi resume và
  phá mô hình immutable candidate. **Không được nới lỏng chỗ này để lấy tốc độ.**
- Hướng hợp lệ duy nhất là song song theo **tiến trình**: mỗi process con có global RNG riêng và xử lý đúng
  một segment tại một thời điểm, nên audio giống hệt bản đơn luồng. Chỉ process cha được ghi SQLite;
  process con chỉ làm phần thuần hàm rồi trả metrics.
- Đĩa và CPU đang rảnh, nên **đừng** tối ưu fsync, checksum hay số lần ghi `.part` — chúng không phải nút
  thắt và chúng là thứ giữ artifact an toàn khi crash.

Chi tiết số đo, ranh giới thiết kế và test bắt buộc: `docs/THROUGHPUT.md`.

## Dependency, model và tool

Người dev project chịu trách nhiệm luôn cả stack: pin thư viện, revision model và tool ngoài.
`docs/DEPENDENCIES.md` giữ đánh giá rủi ro từng package; `scripts/check_dependency_updates.py`
là bước kiểm read-only chạy mỗi phiên bản (nó không bao giờ tự khởi động Ollama).

- `QUALITY_IMPLEMENTATION_FILES` bao gồm `../pyproject.toml` và `../uv.lock`, nên **mọi thay đổi
  dependency đều đổi quality-policy hash**. Nâng cấp luôn là một sự kiện phiên bản: nâng → project sạch
  → chạy lại → so audio → tag.
- **Không sửa bất kỳ file nào trong `QUALITY_IMPLEMENTATION_FILES` khi đang có job chạy**, kể cả chỉ đổi
  dòng `version` của `pyproject.toml`. Pipeline tính hash một lần lúc khởi tạo nên job đang chạy không chết
  ngay, nhưng lần resume kế tiếp sẽ bị từ chối.
- **`git merge` của một nhánh cũng là "sửa file", dù bạn không gõ vào file nào.** Ngày 05/09/2026 tôi merge
  `dev/alpha13` vào production để lấy một script trong `scripts/` — merge nhánh lấy **cả nhánh**, và nó kéo
  theo `analysis.py` đang nằm chờ trên đó. alpha.46 đang chạy dở. Không segment nào bị ghi sai hash (pipeline
  tính một lần lúc khởi tạo, đúng như dòng trên), nhưng chương 3 lúc ấy đang `failed` và **cần một lần
  `resume` để xuất** — mà resume thì sẽ bị từ chối. Đổi một script an toàn suýt mất một chương.
  - Muốn lấy một commit khi đang có job chạy: **`git cherry-pick` commit đó**, đừng merge nhánh.
  - Hoặc tốt hơn: đừng để việc chạm file bị khoá nằm chung nhánh với việc merge được.
  - Cách kiểm tra sau khi merge, mất một giây:
    `git diff --stat <trước> HEAD -- _internal/abook/` — phải rỗng.
  - Cách kiểm chứng job vẫn còn nguyên vẹn: tính lại `quality_policy_hash(build_quality_policy(settings))`
    từ `settings_json` của project và so với `generation_policy_hash` trong bảng `segments`.
- Chỉ nâng khi có lý do. `numpy`, `librosa`, `transformers`, `huggingface-hub`, `torch*` và `timm` ràng buộc
  với UTMOSv2/Whisper và với cache revision đã khóa; `vieneu` quyết định audio. WORLD/Praat đã bỏ khỏi sản phẩm.
- `vieneu` 3.3.0 chuyển engine mặc định sang ONNX Runtime và đẩy torch xuống extra `legacy`; tham số `style`
  cũng đã bị deprecate. Mọi ngân sách frame hiện tại được đo trên engine torch cũ, nên đây là migration
  thật sự chứ không phải bump pin.
- Thư viện Python của VieNeu **không có** tham số tốc độ đọc (tính năng 0.5–3.0 chỉ có trong desktop app).
  Nhãn `pace` chỉ là metadata phân tích; không đổi tham số sinh, ngân sách frame hay QA. Mọi câu dùng band normal chung và sàn âm tiết chung; WSOLA chỉ theo `x * r` của bảng giọng.

## Đánh giá chất lượng audio

`scripts/audit_audiobook.py` là công cụ chấm khách quan cho output đã commit. Nó đọc SQLite + MP3 chương
và báo cáo các trục mà tai người nghe thật sự nhận ra, ngoài các gate đã có trong pipeline:

- tốc độ đọc (âm tiết/giây) theo từng segment, và độ lệch giữa các segment trong cùng một chương;
- khoảng lặng thực tế tại mối nối so với `break_ms` dự kiến, gồm cả phần câm mà TTS tự sinh ở đầu/cuối segment;
- độ đồng đều loudness giữa các segment và giữa narration với dialogue;
- phân bố preset theo nhân vật để phát hiện nhân vật bị trộn giọng.

Ngưỡng review của công cụ này là *chẩn đoán*, không phải gate publish. Muốn biến một phát hiện thành gate thì
phải thêm vào đúng module (`audio_io.py` cho tín hiệu chương, `pipeline.py` cho vòng repair) kèm test.

## Kiểm tra trước khi bàn giao

Từ thư mục `_internal`:

```text
python -m compileall -q abook tests scripts
python -m pytest
```

- Trên Windows/PowerShell, luôn gọi một interpreter tường minh rồi truyền toàn bộ test path trong cùng một
  invocation (có thể dùng array + splatting). Không bao giờ đặt các path `test_*.py` thành những câu lệnh trần
  ở các dòng riêng vì Windows sẽ mở `OpenWith.exe`/“Pick an app” cho từng file.

Definition of done:

- test liên quan pass;
- các mục root hiện cho người dùng vẫn chỉ có `ABook.lnk`, `README.md`, `_internal`; metadata Git ẩn được phép trong checkout;
- không tạo prompt giữa job;
- kill ở ranh giới bất kỳ không làm hỏng artifact đã commit;
- resume giữ settings và voice mapping;
- lỗi nghiêm trọng checkpoint + notification;
- cập nhật README hoặc `_internal/docs/TEST_REPORT.md` khi hành vi/test thay đổi.

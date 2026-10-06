
## Đọc `QUALITY_IMPLEMENTATION_FILES` từ code, đừng tin bản chép tay

Danh sách file bị khoá **không** phải 14 file như các bản tóm tắt vẫn chép. Đọc thẳng:

```bash
_internal/runtime/.venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'_internal'); from abook.quality_policy import QUALITY_IMPLEMENTATION_FILES; print(*QUALITY_IMPLEMENTATION_FILES, sep='\n')"
```

Ngày 2026-09-06 nó trả về **22** mục. Những cái hay bị bỏ sót khỏi bản chép tay:
`recovery.py`, `expression.py`, `quality_policy.py`, và cả bốn file `*_contract.py`
(`asr_contract.py`, `tts_contract.py`, `perceptual_contract.py`, `audio_transform_contract.py`,
`runtime_contract.py`).

Tôi đã sửa `recovery.py` ngay trong production vì bản chép tay không có nó, tưởng là an toàn.
Nó **không** an toàn: hash đổi từ `b63e95be` sang `365ad7ee`, và nếu để nguyên thì lần
`resume` sau của alpha.48 bị từ chối — tức mất sạch bằng chứng QA audio của cả quyển.

**Cách kiểm chắc chắn, trước mọi commit đụng vào `_internal/abook/`:**

```bash
_internal/runtime/.venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'_internal'); from abook.quality_policy import quality_implementation_hash; print(quality_implementation_hash())"
```

Chạy trước và sau khi sửa. Hash đổi thì bản sửa ấy **phải** nằm ở nhánh dev và chờ hết run,
bất kể file đó có trong danh sách bạn nhớ hay không. Hàm đọc file từ đĩa mỗi lần gọi, nên
phép thử này luôn nói sự thật còn trí nhớ thì không.

## Đừng `stop` giữa pha phân tích — đó là đổi quyển sách, không phải tạm nghỉ

Đã chứng minh bằng thí nghiệm có đối chứng (2026-09-07, xem `VERSIONS.md`). Cùng code, cùng
nguồn, cùng cách đọc gieo sẵn; biến duy nhất là một lần `stop`/`resume` ở 620/948:

| | nhân vật | đoạn khác người nói |
|---|---|---|
| chạy liền mạch | **23** | — |
| dừng rồi resume | **19** | 18, toàn bộ **sau** mốc bị ngắt |

Chuỗi hệ quả: người nói khác → sổ nhân vật khác → casting khác → **seed khác → audio khác** →
mọi phán quyết của chủ sách trên những đoạn ấy **hết hiệu lực**.

**Quy tắc:**

- **Trong pha phân tích:** đừng dừng. Nếu buộc phải dừng (máy cần tắt, sửa lỗi chặn đường),
  hãy coi như **mất toàn bộ pha phân tích** và tạo project mới, đừng resume rồi tin rằng nó
  là cùng một quyển sách.
- **Sau pha phân tích:** dừng thoải mái. Tổng hợp resume trung thành — chương 1–4 của
  alpha.51 trùng khít alpha.48 từng byte.
- **Muốn biết đang ở pha nào:** `SELECT COUNT(*) FROM segments WHERE status='pending'`. Khác 0
  nghĩa là phân tích chưa xong.
- **Cần máy rảnh một lúc giữa pha phân tích:** TẠM DỪNG, đừng dừng (từ 29-09: nút "Tạm dừng" ở
  trang dự án, hay `background_runner.request_pause(project, True)`). Worker vẫn sống, đứng ở
  checkpoint kế (`Pipeline._wait_pause_or_stop`) rồi làm tiếp đúng chỗ - không có resume nào,
  nên vẫn là cùng một quyển sách. Supervisor cũng tự tạm dừng khi máy xách tay chạy pin quá
  60 giây (`abook/power_source.py`). Treo tiến trình từ ngoài (người gác pin của máy
  chủ sách) cũng an toàn cùng lý do - **nhưng chỉ khi dưới 30 phút** (xem dưới).

**Vì sao (kiểm 06-10, `D:/Novels/LLM_Train/resume_determinism/AUDIT.md`):** có hai nguyên nhân.
(1) Phía app: resume dựng lại khác lượt thử, số đếm nhân vật, góp ý mang sang. Đã sửa ở 0.4.31
(sổ câu trả lời `analysis_responses` + checkpoint `analysis_state`; test CPU `test_analysis_replay.py`).
(2) Phía Ollama: cùng một request, byte y hệt, mà trả lời khác sau khi model được nạp lại, vì bộ
đệm prompt của llama-server làm phép tính bắt đầu ở chỗ khác. Mọi lần nạp lại đều đổi sách: dừng,
crash, `keep_alive` 30 phút hết hạn (**tạm dừng quá 30 phút** cũng vậy - không có ping giữ model
khi đang tạm dừng), app khác trên máy dỡ/nạp model. Bản sửa (2) đang chờ số A/B trên GPU
(`dev/cache-lineage`, tắt mặc định).

Điều này áp cả cho crash: alpha.50 chết vì `PermissionError` giữa pha phân tích, resume, và
ra một quyển sách khác — 6/10 chương thay vì 8/10 như alpha.51. Nhưng (AUDIT 06-10) alpha.50
đã lệch từ đoạn 560, **83 đoạn trước lần crash**, ngay lúc model bị nạp lại vì một thứ ngoài app,
không có stop nào. "Mọi khác biệt đều sau mốc ngắt" trong `VERSIONS.md` là sai với alpha.50.

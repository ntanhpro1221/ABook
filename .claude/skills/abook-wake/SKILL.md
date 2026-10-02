---
name: abook-wake
description: Thủ tục khi phiên ABook thức dậy - sau khi máy khởi động lại (Windows Update, hết pin), sau khi nén ngữ cảnh, hay khi nghi việc nền đã chết. Kiểm reboot, thả lại việc rời (gác pin, giữ êm quạt, hàng GPU, chuỗi nhạc, chuông), đặt lại ngưỡng nén, rồi làm tiếp việc app + việc model.
---

# Thức dậy ở dự án ABook

Mục tiêu: không việc nền nào nằm chết, không ngồi chờ. Làm theo thứ tự; bước nào đã ổn thì bỏ qua.

Ba phiên theo luồng (bộ nhớ `session-lanes`): Lead (đầu mối duy nhất với chủ sách, giữ chuông và ngưỡng nén), Model
(DUY NHẤT thả việc GPU), Music. Mỗi phiên chỉ thả lại việc rời của luồng mình. Phiên Lead được tác vụ hẹn giờ
`abook-watchdog` của app đánh thức mỗi giờ và ngay khi app mở lại sau reboot (mở phiên KHÔNG tự làm Claude chạy).

## 1. Có khởi động lại không?

PowerShell: `(Get-CimInstance Win32_OperatingSystem).LastBootUpTime`. Mới hơn lần thả việc rời cuối (xem
`_internal/runtime/detached_runs.log`) = mọi việc rời đã chết -> làm đủ bước 2-5. Không thì chỉ kiểm từng việc còn sống
(`Get-CimInstance Win32_Process` lọc theo dòng lệnh).

## 2. Kết nối và ngưỡng nén

- `set_remote_control("self", true)` - mở lại app là mất Remote Control.
- Vừa nén ngữ cảnh: đặt lại `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` = `60` trong `D:/Novels/ABook/.claude/settings.local.json`
  (đã hạ xuống để tự nén).

## 3. Thả lại việc rời (PowerShell, `WorkingDirectory D:/Novels/ABook/_internal`)

Luôn thả bằng `Start-Process pythonw scripts/run_detached.py <lệnh>` - gọi `python.exe run_detached.py` từ Bash sẽ CHẶN
chờ việc con (02-10 làm thả trùng). Dòng lệnh thả không được chứa chữ `gpu_queue_` (làm hàng sau chờ mãi).

1. Người gác pin `runtime/power_guard.py` và bộ giữ êm quạt `runtime/quiet_keeper.py` (venv pythonw).
   Ollama KHÔNG tự chạy sau reboot: script GPU nào không tự gọi `ollama_up.py` sẽ đứng chờ model -> bật Ollama ẩn bằng
   `_internal/scripts/model_eval/ollama_up.py` (không gọi CLI `ollama`, nó mở app khay) trước khi thả hàng GPU (việc của phiên Model).
2. Hàng GPU: script hàng đang dở trong scratchpad của phiên / `D:/Novels/LLM_Train` - các script đều bỏ qua phần đã đo,
   thả lại là chạy tiếp. Mọi việc GPU qua MỘT hàng; không sửa script bash đang chạy.
3. Việc đám mây dở (Modal `finish_one`, Kaggle) - kiểm trạng thái trước, không thả trùng.
4. Chuỗi nhạc `D:/Novels/LLM_Train/music/run_music_chain.sh` nếu chưa có dấu `HET_MUSIC_CHAIN`.

## 4. Chuông

Bash `run_in_background`, từ `D:/Novels/ABook/_internal`:
- A: `runtime/.venv/Scripts/python.exe scripts/heartbeat_event.py` (reo khi việc rời xong / hỏng / chạy pin).
- B: `runtime/.venv/Scripts/python.exe scripts/heartbeat_timeout.py --hours 2` (đặt lại bằng `--reset` mỗi lần A reo).
Mỗi lần A reo: xử lý sự kiện, thả lại A, đặt lại B.

## 5. Đánh thức cấp dưới (chỉ phiên Lead)

Sau reboot: SendMessage cho Model và Music "máy vừa khởi động lại lúc ..., chạy abook-wake cho luồng của bạn rồi báo
Lead". Mỗi lần thức: `get_usage(session_id)` từng phiên con (> ~50% thì nhắn ghi trạng thái), `list_events` khi cần
xem chúng làm gì.

## 6. Làm tiếp - không ngồi chờ

- Đọc `app-backlog` trong bộ nhớ: việc app ĐANG LÀM. Đọc `work-efficiency`: cách chia việc cho agent.
- Agent nền dở dang: `SendMessage` cho nó chạy tiếp thay vì thả agent mới.
- Luôn có 1 việc app + 1 việc model/nghiên cứu chạy song song. Báo chủ sách ngắn, tiếng Việt.

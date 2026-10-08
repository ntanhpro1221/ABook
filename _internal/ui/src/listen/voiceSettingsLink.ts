// Cuộn tới một chỗ trong Cài đặt › Giọng đọc sau khi đã chuyển sang trang Cài đặt: nút "Tải giọng VieNeu" ở khối báo mất mạng (PlayerViews) và nút
// "Tải giọng chạy trên máy" trong hộp chọn giọng trực tuyến (OnlineVoicePrompt) cùng đi đường này. `anchor`: mã của phần tử cần tới
// (mặc định đầu mục Giọng đọc; "vieneu-module" = thẻ tải giọng VieNeu).
export function revealVoiceSettings(anchor = "voices"): void {
  let tries = 0;
  const reveal = () => {
    const target = document.getElementById(anchor);
    if (target) {
      target.scrollIntoView({ block: "start" });
      // Danh sách giọng phía trên hiện ra SAU (hỏi máy xong mới dựng): chỗ cần tới bị đẩy xuống - cuộn lại vài lần cho tới khi trang yên.
      for (const wait of [250, 600, 1200]) setTimeout(() => target.scrollIntoView({ block: "start" }), wait);
    } else if (tries++ < 20) setTimeout(reveal, 50);
  };
  setTimeout(reveal, 0);
}

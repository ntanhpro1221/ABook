/** Liên kết ra ngoài app (trang mã nguồn, giấy phép nhạc...). Cửa sổ app Windows (Tauri) nuốt `target="_blank"` nên bấm vào
 *  không thấy gì: ở đó máy chủ mở bằng trình duyệt mặc định (`/api/open-url`). Trình duyệt thường và Android không đăng ký
 *  gì, `<a target="_blank">` chạy như cũ. */
type Opener = (url: string) => Promise<void>;

let opener: Opener | null = null;

/** Máy tính đăng ký cách mở qua máy chủ khi chạy trong cửa sổ app; `null` để trở lại hành vi của trình duyệt. */
export function setExternalOpener(next: Opener | null): void {
  opener = next;
}

/** Dùng làm `onClick` của `<a href target="_blank">`: nhờ máy chủ mở, hỏng thì để trình duyệt tự mở như thường. */
export function openExternal(url: string, event?: { preventDefault(): void }): void {
  if (!opener) return;
  event?.preventDefault();
  opener(url).catch(() => {
    window.open(url, "_blank", "noopener,noreferrer");
  });
}

// Sách "Trên máy khác" nghe thẳng: chương chưa tải mà máy kia tắt thì trình phát báo lỗi và dừng. Máy kia trả lời lại (bật lại, có mạng
// lại) thì tự thử MỘT lần - người nghe không phải đoán lúc nào bấm "Thử lại" (soát a27 lỗi 3).

/** Hỏi `reachable` mỗi `everyMs` tới khi nó trả true thì gọi `onBack` một lần rồi thôi; quá `giveUpMs` thì thôi hỏi. Lỗi khi hỏi = chưa
 *  trả lời. Trả hàm dừng (đổi cuốn, gạt lời báo, phát lại được). */
export function watchUntilBack(
  reachable: () => Promise<boolean>,
  onBack: () => void,
  { everyMs = 5000, giveUpMs = 30 * 60_000 }: { everyMs?: number; giveUpMs?: number } = {},
): () => void {
  let stopped = false;
  let timer = 0;
  const started = Date.now();
  const stop = () => {
    stopped = true;
    window.clearTimeout(timer);
  };
  const tick = () => {
    if (stopped) return;
    if (Date.now() - started > giveUpMs) return stop();
    void reachable()
      .catch(() => false)
      .then((back) => {
        if (stopped) return;
        if (back) {
          stop();
          onBack();
        } else timer = window.setTimeout(tick, everyMs);
      });
  };
  timer = window.setTimeout(tick, everyMs);
  return stop;
}

/** Cuốn đang nạp trong trình phát là sách của máy khác mà đã rời Thư viện (bỏ ghép máy ấy): trình phát đóng, đừng giữ một cuốn không
 *  mở lại được (soát a27 lỗi 11). `books` chưa có (chưa hỏi xong) thì chưa kết luận; sách của chính máy này không bao giờ bị đóng ở đây. */
export function leftWithPeer(book: { id: string; remote?: unknown } | null | undefined, books: readonly { id: string }[] | undefined): boolean {
  return Boolean(book?.remote) && books !== undefined && !books.some((item) => item.id === book!.id);
}

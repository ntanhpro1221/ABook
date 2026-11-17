/** Lưu một tuỳ chọn người dùng đổi dồn dập (âm lượng khi kéo, lần hẹn giờ cuối khi giữ nút +/-): gom các lần đổi liền nhau (gửi
 *  `delay` ms sau lần đổi cuối), mỗi lúc chỉ MỘT lần gửi đang bay - lần đổi đến khi nó còn bay thì gửi bản mới nhất ngay khi nó về.
 *  `apply` nhận bản máy chủ trả về chỉ khi không còn lần lưu nào mới hơn đang chờ: phản hồi muộn không kéo mốc lùi về số cũ.
 *  Lỗi lưu thì im lặng: phiên này vẫn dùng giá trị đã chọn. Qt: Api.qml `rememberLastSleep` (cùng luật). */
export interface LatestSave<T> {
  /** Nhớ `value` là bản mới nhất cần lưu. Trả về lời hứa xong khi không còn lần lưu nào chờ / đang bay (bản này hay bản mới hơn đã về). */
  save(value: T): Promise<void>;
  /** Còn lần lưu chờ gửi / đang bay. */
  readonly pending: boolean;
}

export function latestSave<T, R = unknown>(send: (value: T) => Promise<R>, { delay = 800, apply }: { delay?: number; apply?: (saved: R) => void } = {}): LatestSave<T> {
  let queued: { value: T } | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let flying = false;
  let waiting: (() => void)[] = [];
  const busy = () => queued !== null || flying || timer !== undefined;
  const settle = () => {
    if (busy()) return;
    const done = waiting;
    waiting = [];
    done.forEach(resolve => resolve());
  };
  const start = () => {
    timer = undefined;
    if (flying || !queued) return;
    const { value } = queued;
    queued = null;
    flying = true;
    void send(value)
      .then(saved => { if (!queued && timer === undefined) apply?.(saved); }, () => undefined)
      .finally(() => {
        flying = false;
        if (queued && timer === undefined) start();
        settle();
      });
  };
  return {
    save(value) {
      queued = { value };
      if (timer !== undefined) clearTimeout(timer);
      timer = setTimeout(start, delay);
      return new Promise(resolve => waiting.push(resolve));
    },
    get pending() { return busy(); },
  };
}

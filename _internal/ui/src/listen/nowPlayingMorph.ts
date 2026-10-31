// Mở / đóng màn Đang nghe kiểu "container transform": cả màn nở ra từ khung thanh phát nhỏ (đóng thì thu về đúng khung ấy), còn những phần có ở
// cả hai nơi - bìa, tên chương, tên sách, nút phát - bay riêng từ chỗ cũ sang chỗ mới, đổi cỡ và đổi màu dần. Chủ sách 26-10 (video mở Đang nghe):
// "toàn bộ cửa sổ mới được phóng ra từ dòng thu nhỏ... bìa, tên, tên chương, nút play... sẽ lerp (scale, move, fade màu)". Không mờ cả màn.
// Chạy bằng Web Animations trên chính các phần tử (không View Transition: WebView điện thoại chụp ảnh tài liệu mất 70-140 ms, chạm là đứng hình).
import { EASE, prefersReducedMotion } from "@/shared/motion";

/** Thời lượng nở / thu (ms). Màn che trang bên dưới, gỡ màn khi đóng xong đều tính theo hai số này. */
export const MORPH = { open: 420, close: 340 } as const;

/** Phần chung của thanh phát nhỏ và màn Đang nghe, gắn bằng `data-np` ở cả hai nơi. Thanh phát nhỏ mang `data-np-source`. */
export const MORPH_PARTS = ["cover", "chapter", "book", "play"] as const;
export type MorphPart = (typeof MORPH_PARTS)[number];
// Chữ co giãn đều theo chiều cao dòng, neo mép trái - khung chữ hai nơi rộng khác nhau (cột hẹp / cả bề ngang) nhưng chữ đều bắt đầu từ mép trái.
const TEXT: ReadonlySet<MorphPart> = new Set(["chapter", "book"]);
const COLORS = ["color", "backgroundColor"] as const;

type Box = Pick<DOMRect, "left" | "top" | "width" | "height" | "right" | "bottom">;

/** Khung cắt của màn lúc còn là thanh nhỏ: `inset()` theo toạ độ của chính màn, bo theo góc của thanh. */
export function barClip(screen: Box, bar: Box, radius = 0): string {
  const px = (value: number) => `${Math.round(value * 100) / 100}px`;
  return `inset(${px(bar.top - screen.top)} ${px(screen.right - bar.right)} ${px(screen.bottom - bar.bottom)} ${px(bar.left - screen.left)} round ${px(radius)})`;
}

/** Biến hình đưa phần tử từ hộp `to` (chỗ thật) về trông như hộp `from`, neo góc trên trái. Chữ: một tỉ lệ theo chiều cao, không méo chữ. */
export function partTransform(part: MorphPart, from: Box, to: Box): string {
  const sx = from.width / to.width, sy = from.height / to.height;
  const scale = TEXT.has(part) ? `scale(${sy})` : `scale(${sx}, ${sy})`;
  return `translate(${from.left - to.left}px, ${from.top - to.top}px) ${scale}`;
}

const usable = (box: Box) => box.width > 0 && box.height > 0;

/** Phần riêng của màn (thanh đầu, thanh tua, các nút phụ...): những khối không chứa phần chung nào, đi xuống tới sát phần chung - khối nào
 *  chứa phần chung thì xét các con của nó, để phần chung không bị kéo theo. */
export function unsharedBlocks(root: Element, shared: ReadonlySet<Element>): Element[] {
  const found: Element[] = [];
  for (const child of root.children) {
    if (shared.has(child)) continue;
    if ([...shared].some((part) => child.contains(part))) found.push(...unsharedBlocks(child, shared));
    else found.push(child);
  }
  return found;
}

export interface Morph {
  /** Thêm các phần chung vừa dựng (ruột màn điện thoại dựng hoãn một nhịp): bay cùng nhịp với màn, không bắt đầu lại từ đầu. */
  parts(): void;
  cancel(): void;
}

/** Nở (`open`) hay thu (`close`) màn `screen` theo thanh phát nhỏ đang có trên trang. Không có thanh (chưa dựng, ẩn, cao 0) hay không có Web
 *  Animations thì trả null - chỗ gọi dùng đường dự phòng CSS của nó. */
export function morphNowPlaying(screen: HTMLElement, direction: "open" | "close", doc: Document = screen.ownerDocument): Morph | null {
  const bar = doc.querySelector<HTMLElement>("[data-np-source]");
  // Xin giảm chuyển động: không bay, không nở - đường CSS (--motion-amount = 0) chỉ còn hiện ra ngắn.
  if (!bar || typeof screen.animate !== "function" || prefersReducedMotion()) return null;
  const screenBox = screen.getBoundingClientRect(), barBox = bar.getBoundingClientRect();
  if (!usable(screenBox) || !usable(barBox)) return null;
  const view = doc.defaultView;
  const opening = direction === "open";
  const timing: KeyframeAnimationOptions = {
    duration: opening ? MORPH.open : MORPH.close,
    easing: opening ? EASE.standard : "cubic-bezier(0.3, 0, 0, 1)",
    fill: "forwards",
  };
  const order = <T,>(small: T, large: T) => (opening ? [small, large] : [large, small]);
  const radius = Number.parseFloat(view?.getComputedStyle(bar).borderTopLeftRadius ?? "") || 0;
  // Nền cũng đổi dần từ màu thanh sang màu màn (nền pha màu bìa), không đổi phắt ở khung đầu.
  const ground = (style: CSSStyleDeclaration | undefined) => style?.backgroundColor && !/rgba\([^)]*,\s*0\)$|transparent/.test(style.backgroundColor) ? style.backgroundColor : null;
  const barGround = ground(view?.getComputedStyle(bar)), screenGround = ground(view?.getComputedStyle(screen));
  const frame = screen.animate({
    clipPath: order(barClip(screenBox, barBox, radius), "inset(0px 0px 0px 0px round 0px)"),
    ...(barGround && screenGround ? { backgroundColor: order(barGround, screenGround) } : {}),
  }, timing);
  const running: Animation[] = [frame];
  const done = new Set<Element>();
  const shared = new Set<Element>();
  // Phần riêng của màn không có chỗ trên thanh nhỏ: nhô lên và lớn dần khi khung đã nở được một phần (đóng thì lùi xuống, khuất trước khi khung
  // thu nhỏ). Lúc phần chung còn bay ngang qua chỗ của chúng thì chúng chưa hiện - không có lớp nào đè lên bìa đang bay.
  const rise = Math.max(24, Math.min(96, (barBox.top - screenBox.top) * 0.12));
  const hidden = { opacity: 0, transform: `translateY(${rise}px) scale(0.92)` }, shown = { opacity: 1, transform: "none" };
  const blocks = () => {
    for (const block of unsharedBlocks(screen, shared)) {
      if (done.has(block) || !(block instanceof HTMLElement) || !usable(block.getBoundingClientRect())) continue;
      done.add(block);
      const frames = opening ? [hidden, { ...hidden, offset: 0.4 }, { ...shown, offset: 0.85 }, shown] : [shown, { ...hidden, offset: 0.35 }, hidden];
      const animation = block.animate(frames.map((keyframe) => ({ transformOrigin: "50% 100%", ...keyframe })), timing);
      if (frame.currentTime !== null) animation.currentTime = frame.currentTime;
      running.push(animation);
    }
  };
  const parts = () => {
    for (const part of MORPH_PARTS) {
      const from = bar.querySelector<HTMLElement>(`[data-np="${part}"]`), to = screen.querySelector<HTMLElement>(`[data-np="${part}"]`);
      if (!from || !to || done.has(to)) continue;
      const a = from.getBoundingClientRect(), b = to.getBoundingClientRect();
      if (!usable(a) || !usable(b)) continue;
      done.add(to);
      shared.add(to);
      const small = view?.getComputedStyle(from), large = view?.getComputedStyle(to);
      const look = (style: CSSStyleDeclaration | undefined) => Object.fromEntries(COLORS.map((key) => [key, style?.[key] ?? ""]).filter(([, value]) => value));
      const animation = to.animate(order(
        { transformOrigin: "0 0", transform: partTransform(part, a, b), ...look(small) },
        { transformOrigin: "0 0", transform: "none", ...look(large) },
      ), timing);
      // Ruột dựng muộn: vào đúng nhịp đang chạy của màn.
      if (frame.currentTime !== null) animation.currentTime = frame.currentTime;
      running.push(animation);
    }
    // Chưa thấy phần chung nào (ruột màn chưa dựng) thì chưa chia khối: cả cột sẽ bị coi là phần riêng, kéo cả bìa lẫn tên theo.
    if (shared.size) blocks();
  };
  parts();
  // Mở xong thì trả mọi thứ về CSS (hover, đổi giao diện sáng / tối...); đóng xong thì giữ khung cuối tới khi màn được gỡ.
  if (opening) void frame.finished.then(() => { for (const animation of running) animation.cancel(); }, () => undefined);
  return {
    parts,
    cancel: () => { for (const animation of running) animation.cancel(); },
  };
}

import { Component, createElement, createRef, isValidElement, type ElementType, type HTMLAttributes, type ReactNode, type Ref } from "react";
import { captureMotionSnapshot, holdMotionSnapshot, removeMotionSnapshot, settleMotionSnapshot, EASE, MOTION, prefersReducedMotion, viewTransitionRunning } from "./motion";

/** Bỏ clock/%/giá trị ô nhập khỏi dấu đổi nội dung. Tiến độ vẫn chạy bằng Progress, không chụp lại theo từng tick. */
export function motionSignature(element: HTMLElement): string {
  const parts: string[] = [];
  const visit = (node: Element) => {
    if (node !== element && node.hasAttribute("data-motion-region")) { parts.push("region"); return; }
    if (node.matches("input, textarea, select, [role=progressbar], [role=timer], [data-motion-live], [inert], .motion-snapshot")) return;
    parts.push(node.tagName, ...["id", "href", "src", "data-state", "class", "d", "points"].map((name) => node.getAttribute(name) ?? ""));
    for (const child of Array.from(node.childNodes)) {
      if (child.nodeType === 3) parts.push((child.textContent ?? "").replace(/\d[\d\s.,:%–/\-]*/g, "#").trim());
      else if (child.nodeType === 1) visit(child as Element);
    }
  };
  visit(element);
  return parts.join("|");
}

type Props = HTMLAttributes<HTMLElement> & { as?: "div" | "section" | "ul" | "ol" | "p" | "span" | "li" | "label" | "button"; htmlFor?: string; type?: "button" | "submit" | "reset"; disabled?: boolean; children?: ReactNode; motionKey?: unknown; elementRef?: Ref<HTMLElement>; followScroll?: boolean; fadeThrough?: boolean;
  /** Thứ tự của mục đang chọn trong hàng tab/lọc điều khiển vùng này: đổi sang mục bên phải thì nội dung trượt vào từ phải, bên trái thì từ trái. */
  slideIndex?: number };
type Snapshot = { clone?: HTMLElement; signature: string; height: number; display?: string; margins?: [number, number]; focus?: HTMLElement } | null;

/** So sánh cây React trước commit: polling/đồng hồ/ô nhập không được clone cả vùng DOM mỗi nhịp.
 * Vùng con có MotionRegion tự lo chuyển cảnh; vùng cha không chụp lại cùng thay đổi ấy. */
export function contentSignature(value: unknown, depth = 0): string {
  if (value == null || typeof value === "boolean" || typeof value === "function" || depth > 24) return "";
  if (typeof value === "string") return value.replace(/\d[\d\s.,:%–/\-]*/g, "#");
  if (typeof value === "number") return "#";
  if (Array.isArray(value)) return value.map((item) => contentSignature(item, depth + 1)).join("|");
  if (isValidElement<Record<string, unknown>>(value)) {
    if (value.type === MotionRegion) return `region:${value.key ?? ""}`;
    const type = typeof value.type === "string" ? value.type : (value.type as { displayName?: string; name?: string }).displayName ?? (value.type as { name?: string }).name ?? String(value.type);
    if (["input", "textarea", "select"].includes(type) || value.props["data-motion-live"] !== undefined || ["progressbar", "timer"].includes(String(value.props.role))) return type;
    return `${type}:${value.key ?? ""}:${contentSignature(value.props, depth + 1)}`;
  }
  if (typeof value === "object") return Object.entries(value).filter(([key]) => !["style", "ref", "elementRef", "value", "defaultValue"].includes(key) && !key.startsWith("on")).map(([key, item]) => `${key}:${contentSignature(item, depth + 1)}`).join(";");
  return "";
}

/** Crossfade đúng vùng thay đổi, giữ hình cũ (inert) qua commit, không dựng lại component/effect.
 * Height chỉ tween khi bố cục thực sự đổi; reduced chỉ fade. Ô đang gõ không bị chụp theo từng phím.
 * motionKey dùng cho vùng có tìm kiếm: chỉ đổi khi kết quả/pha đổi, không theo nội dung ô gõ. */
export class MotionRegion extends Component<Props> {
  readonly box = createRef<HTMLElement>();
  private animation: Animation | null = null;
  private clone: HTMLElement | undefined;
  private clearExit: (() => void) | undefined;
  private clearHidden: ((restoreFocus?: boolean) => void) | undefined;
  private hiddenFocus: HTMLElement | undefined;
  private generation = 0;
  getSnapshotBeforeUpdate(previous: Props): Snapshot {
    const box = this.box.current;
    if (!box || viewTransitionRunning()) return null;
    if (this.props.motionKey !== undefined && JSON.stringify(previous.motionKey) === JSON.stringify(this.props.motionKey)) return null;
    if (this.props.motionKey === undefined && contentSignature(previous.children) === contentSignature(this.props.children)) return null;
    const active = box.ownerDocument.activeElement;
    const focus = box.contains(active) ? active as HTMLElement : this.hiddenFocus && (active === box.parentElement || active === box.ownerDocument.body) ? this.hiddenFocus : undefined;
    this.clearHidden?.(false);
    ++this.generation;
    this.animation?.cancel();
    removeMotionSnapshot(this.clone);
    const surface = box.closest('[data-state="open"]:is([role="dialog"], [role="alertdialog"], [role="menu"], [role="listbox"])');
    const floorZ = surface ? Math.max(51, (parseInt(getComputedStyle(surface).zIndex) || 50) + 1) : 39;
    // Chọn host TRƯỚC khi đo/đặt ảnh: fixed dùng toạ độ viewport sẽ lệch khi đưa vào surface có transform.
    // Vùng trang giữ ảnh fixed trên body; chỉ surface cần hệ toạ độ cục bộ.
    const host = surface ? (surface !== box ? surface : box.offsetParent) : undefined;
    const clone = captureMotionSnapshot(box, box.ownerDocument, floorZ, host && host !== box.ownerDocument.body ? host as HTMLElement : undefined, true, this.props.followScroll);
    const computed = box.style ? getComputedStyle(box) : undefined;
    return { clone, signature: motionSignature(box), height: box.getBoundingClientRect().height, display: computed?.display,
      margins: [parseFloat(computed?.marginTop ?? "0") || 0, parseFloat(computed?.marginBottom ?? "0") || 0],
      focus };
  }
  componentDidUpdate(previous: Props, _state: unknown, snapshot: Snapshot) {
    const box = this.box.current;
    if (!box || !snapshot) {
      if (this.clearExit) { ++this.generation; this.animation?.cancel(); this.clearExit?.(); }
      return;
    }
    this.clone = snapshot.clone;
    if (snapshot.signature === motionSignature(box) && this.props.motionKey === undefined) { this.clearExit?.(); removeMotionSnapshot(this.clone); this.clone = undefined; return; }
    this.clone = settleMotionSnapshot(box, this.clone);
    ++this.generation;
    this.animation?.cancel();
    this.clearHidden?.();
    this.clearExit?.();
    const generation = ++this.generation;
    const to = box.getBoundingClientRect().height;
    const empty = !box.children.length && !box.textContent;
    const slide = !empty && this.clone && !prefersReducedMotion() && typeof previous.slideIndex === "number" && typeof this.props.slideIndex === "number"
      ? Math.sign(this.props.slideIndex - previous.slideIndex) : 0;
    if (empty && snapshot.height > 0) {
      const { height, overflow, display, marginTop, marginBottom } = box.style;
      box.setAttribute("data-motion-exit", "");
      box.style.height = `${snapshot.height}px`;
      box.style.overflow = "clip";
      box.style.display = snapshot.display === "inline" ? "inline-block" : snapshot.display ?? "";
      box.style.marginTop = `${snapshot.margins?.[0] ?? 0}px`;
      box.style.marginBottom = `${snapshot.margins?.[1] ?? 0}px`;
      const timer = window.setTimeout(() => finish(), MOTION.medium + 80);
      this.clearExit = () => {
        window.clearTimeout(timer);
        box.removeAttribute("data-motion-exit");
        box.style.height = height; box.style.overflow = overflow;
        box.style.display = display; box.style.marginTop = marginTop; box.style.marginBottom = marginBottom;
        this.clearExit = undefined;
      };
    }
    const finish = () => { restore?.(); if (generation === this.generation) { this.clearHidden?.(); this.clearExit?.(); } };
    const duration = slide ? MOTION.slow : prefersReducedMotion() ? MOTION.fast : MOTION.medium;
    const through = !slide && this.props.fadeThrough && Math.abs(to - snapshot.height) > 1;
    // Cây mới chỉ hiện khi ảnh cũ đã mờ hết (fastOut) - hiện sớm hơn là hai lớp chữ chồng nhau ~60-100 ms (emu138 VỪA 1).
    // Reduced vẫn có đủ thời gian fade vào, không tween chiều cao.
    const revealAt = Math.min(MOTION.fastOut, duration * .75);
    let frames: Keyframe[] = empty ? [{ opacity: 1 }, { opacity: 0 }] : through
      ? [{ opacity: 0, offset: 0 }, { opacity: 0, offset: revealAt / duration }, { opacity: 1, offset: 1 }]
      : [{ opacity: 0.45 }, { opacity: 1 }];
    if (!prefersReducedMotion() && Math.abs(to - snapshot.height) > 1) {
      frames[0].height = `${snapshot.height}px`; frames[frames.length - 1].height = `${to}px`;
      if (empty) for (const [index, name] of ["marginTop", "marginBottom"].entries()) {
        if (snapshot.margins?.[index]) { frames[0][name] = `${snapshot.margins[index]}px`; frames[frames.length - 1][name] = "0px"; }
      }
    }
    let restore: (() => void) | undefined;
    if (slide && this.clone) ({ frames, restore } = this.slideFrames(box, this.clone, slide, frames, duration));
    this.animation = box.animate?.(frames, { duration, easing: through ? "linear" : EASE.standard }) ?? null;
    if (this.animation) {
      this.animation.onfinish = finish;
      this.animation.oncancel = finish;
      if (through) this.hideUntilReveal(box, snapshot.focus, this.animation, revealAt);
    } else finish();
    if (!through && snapshot.focus && (box.ownerDocument.activeElement === box.parentElement || box.ownerDocument.activeElement === box.ownerDocument.body)) {
      const target = snapshot.focus.isConnected ? snapshot.focus : box.querySelector<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), [tabindex="0"]');
      target?.focus({ preventScroll: true });
    }
  }
  /** Đổi tab: ảnh cũ trượt hẳn ra phía bên kia, cây mới trượt vào từ phía mục vừa chọn - như lật trang, cùng một nhịp (chủ sách 25-10:
   *  "phần content ở dưới phải lướt sang thế chỗ"). Cả hai bị cắt trong khung của vùng, không tràn ra lề hay tạo cuộn ngang. */
  private slideFrames(box: HTMLElement, clone: HTMLElement, slide: number, frames: Keyframe[], duration: number) {
    const width = box.getBoundingClientRect().width;
    const cut = (left: number, right: number) => `inset(-100vh ${right}px -100vh ${left}px)`;
    holdMotionSnapshot(clone, duration + 80);
    clone.animate?.([
      { transform: "translateX(0px)", clipPath: cut(0, 0) },
      { transform: `translateX(${-slide * width}px)`, clipPath: slide > 0 ? cut(width, 0) : cut(0, width) },
    ], { duration, easing: EASE.standard, fill: "forwards" });
    const sliding: Keyframe[] = [
      { transform: `translateX(${slide * width}px)`, clipPath: slide > 0 ? cut(0, width) : cut(width, 0) },
      { transform: "translateX(0px)", clipPath: cut(0, 0) },
    ];
    if (frames[0].height !== undefined) { sliding[0].height = frames[0].height; sliding[1].height = frames[frames.length - 1].height; }
    // Phần trượt ngoài khung vẫn tính vào vùng cuộn của tổ tiên: chặn ngang ở cha trong lúc trượt, trả lại khi xong.
    const parents = [box.parentElement, clone.parentElement === box.ownerDocument.body ? null : clone.parentElement].filter((parent): parent is HTMLElement => Boolean(parent));
    const kept = parents.map((parent) => parent.style.overflowX);
    for (const parent of parents) parent.style.overflowX = "clip";
    return { frames: sliding, restore: () => parents.forEach((parent, index) => { parent.style.overflowX = kept[index]; }) };
  }
  private hideUntilReveal(box: HTMLElement, previousFocus: HTMLElement | undefined, animation: Animation, revealAt: number) {
    const doc = box.ownerDocument;
    const active = doc.activeElement as HTMLElement | null;
    const focused = box.contains(active) ? active! : previousFocus;
    // Park outside the inert tree, including when React just removed the old control.
    const park = box.parentElement;
    const tabIndex = park?.getAttribute("tabindex") ?? null;
    let parked = false;
    const parkFocus = () => {
      if (!park) return;
      if (tabIndex === null) park.setAttribute("tabindex", "-1");
      park.focus({ preventScroll: true }); parked = true;
    };
    if (focused && (box.contains(active) || active === doc.body || active === park)) parkFocus();
    this.hiddenFocus = focused;
    box.setAttribute("inert", ""); box.setAttribute("aria-hidden", "true");
    const block = (event: Event) => { event.preventDefault(); event.stopImmediatePropagation(); if (event.type === "focusin") parkFocus(); };
    const events = ["click", "dblclick", "pointerdown", "keydown", "focusin"];
    events.forEach(type => box.addEventListener(type, block, true));
    let frame = 0;
    this.clearHidden = (restoreFocus = true) => {
      cancelAnimationFrame(frame);
      events.forEach(type => box.removeEventListener(type, block, true));
      box.toggleAttribute("inert", Boolean(this.props.inert));
      const hidden = this.props["aria-hidden"];
      if (hidden == null) box.removeAttribute("aria-hidden"); else box.setAttribute("aria-hidden", String(hidden));
      if (restoreFocus && parked && doc.activeElement === park && box.isConnected && !box.closest("[inert]")) {
        const target = focused?.isConnected && box.contains(focused) ? focused : box.querySelector<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]');
        target?.focus({ preventScroll: true });
      }
      if (parked && park && tabIndex === null) park.removeAttribute("tabindex");
      this.hiddenFocus = undefined;
      this.clearHidden = undefined;
    };
    const check = () => {
      // Follow the animation clock, so pausing it never exposes an invisible tree.
      if (typeof animation.currentTime === "number" && animation.currentTime > revealAt) this.clearHidden?.();
      else frame = requestAnimationFrame(check);
    };
    frame = requestAnimationFrame(check);
  }
  componentWillUnmount() { ++this.generation; this.animation?.cancel(); this.clearHidden?.(false); this.clearExit?.(); removeMotionSnapshot(this.clone); }
  render() {
    const { as: Tag = "div", motionKey: _key, elementRef, followScroll: _followScroll, fadeThrough: _fadeThrough, slideIndex: _slideIndex, ...props } = this.props;
    return createElement(Tag as ElementType, { ...props, ref: (element: HTMLElement | null) => {
      this.box.current = element;
      if (typeof elementRef === "function") elementRef(element);
      else if (elementRef) elementRef.current = element;
    }, "data-motion-region": "" });
  }
}

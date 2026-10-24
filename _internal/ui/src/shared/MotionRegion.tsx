import { Component, createElement, createRef, isValidElement, type ElementType, type HTMLAttributes, type ReactNode, type Ref } from "react";
import { captureMotionSnapshot, removeMotionSnapshot, settleMotionSnapshot, EASE, MOTION, prefersReducedMotion, viewTransitionRunning } from "./motion";

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

type Props = HTMLAttributes<HTMLElement> & { as?: "div" | "section" | "ul" | "ol" | "p" | "span" | "li" | "label" | "button"; htmlFor?: string; type?: "button" | "submit" | "reset"; disabled?: boolean; children?: ReactNode; motionKey?: unknown; elementRef?: Ref<HTMLElement> };
type Snapshot = { clone?: HTMLElement; signature: string; height: number; display?: string; margins?: [number, number] } | null;

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
  private generation = 0;
  getSnapshotBeforeUpdate(previous: Props): Snapshot {
    const box = this.box.current;
    if (!box || viewTransitionRunning()) return null;
    if (this.props.motionKey !== undefined && JSON.stringify(previous.motionKey) === JSON.stringify(this.props.motionKey)) return null;
    if (this.props.motionKey === undefined && contentSignature(previous.children) === contentSignature(this.props.children)) return null;
    removeMotionSnapshot(this.clone);
    const surface = box.closest('[data-state="open"]:is([role="dialog"], [role="alertdialog"], [role="menu"], [role="listbox"])');
    const floorZ = surface ? Math.max(51, (parseInt(getComputedStyle(surface).zIndex) || 50) + 1) : 39;
    // Chọn host TRƯỚC khi đo/đặt ảnh: fixed dùng toạ độ viewport sẽ lệch khi đưa vào surface có transform.
    // Vùng trang giữ ảnh fixed trên body; chỉ surface cần hệ toạ độ cục bộ.
    const host = surface ? (surface !== box ? surface : box.offsetParent) : undefined;
    const clone = captureMotionSnapshot(box, box.ownerDocument, floorZ, host && host !== box.ownerDocument.body ? host as HTMLElement : undefined, true);
    const computed = box.style ? getComputedStyle(box) : undefined;
    return { clone, signature: motionSignature(box), height: box.getBoundingClientRect().height, display: computed?.display,
      margins: [parseFloat(computed?.marginTop ?? "0") || 0, parseFloat(computed?.marginBottom ?? "0") || 0] };
  }
  componentDidUpdate(_previous: Props, _state: unknown, snapshot: Snapshot) {
    const box = this.box.current;
    if (!box || !snapshot) return;
    this.clone = snapshot.clone;
    if (snapshot.signature === motionSignature(box) && this.props.motionKey === undefined) { removeMotionSnapshot(this.clone); this.clone = undefined; return; }
    this.clone = settleMotionSnapshot(box, this.clone);
    this.animation?.cancel();
    this.clearExit?.();
    const generation = ++this.generation;
    const to = box.getBoundingClientRect().height;
    const empty = box.matches(":empty");
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
    const finish = () => { if (generation === this.generation) this.clearExit?.(); };
    const frames: Keyframe[] = [{ opacity: 0.45 }, { opacity: 1 }];
    if (!prefersReducedMotion() && Math.abs(to - snapshot.height) > 1) {
      frames[0].height = `${snapshot.height}px`; frames[1].height = `${to}px`;
      if (empty) for (const [index, name] of ["marginTop", "marginBottom"].entries()) {
        if (snapshot.margins?.[index]) { frames[0][name] = `${snapshot.margins[index]}px`; frames[1][name] = "0px"; }
      }
    }
    this.animation = box.animate?.(frames, { duration: prefersReducedMotion() ? MOTION.fast : MOTION.medium, easing: EASE.standard }) ?? null;
    if (this.animation) this.animation.onfinish = finish;
  }
  componentWillUnmount() { ++this.generation; this.animation?.cancel(); this.clearExit?.(); removeMotionSnapshot(this.clone); }
  render() {
    const { as: Tag = "div", motionKey: _key, elementRef, ...props } = this.props;
    return createElement(Tag as ElementType, { ...props, ref: (element: HTMLElement | null) => {
      this.box.current = element;
      if (typeof elementRef === "function") elementRef(element);
      else if (elementRef) elementRef.current = element;
    }, "data-motion-region": "" });
  }
}

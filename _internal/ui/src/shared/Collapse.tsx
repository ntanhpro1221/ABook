// Mục gấp / mở có chuyển động (a120). Chủ app 23-10: "cài đặt hay gì đó mà trong nó có nhiều đầu mục quá thì foldout chúng lại… chứ để hết
// một trang dài ơi là dài" - và không chỗ nào bật tắt cứng. `Collapse`: phần thân kéo cao / khép lại (styles.css .motion-collapse, lưới 0fr <-> 1fr,
// không đo chiều cao). `Fold`: một khối có đầu bấm được (tên + một dòng tóm tắt + mũi tên), nhớ gấp / mở theo từng khối trên máy này.
import { DisclosureRow } from "./DisclosureRow";
import { useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "./cn";
import { EASE, MOTION, markArrival, pageSettling, prefersReducedMotion } from "./motion";

/** Bọc phần trang phụ thuộc một lượt tải (thường là cả trang, để đầu trang ngoài LoadingCrossfade cũng tính). Lượt dữ liệu đầu về thì mở
 *  cửa sổ ổn định (motion.ts pageSettling): thứ tới cùng lượt ấy hiện tại chỗ, không mọc từ 0 (đo 25-10: lưới Thư viện trôi 110 px trong
 *  90 ms lúc mở app trên máy tính). Đánh dấu ngay lúc dựng, trước khi con dựng. */
export function ArrivalScope({ loading, children }: { loading: boolean; children: ReactNode }) {
  const was = useRef(loading);
  if (was.current && !loading) markArrival();
  useLayoutEffect(() => { was.current = loading; });
  return children;
}

/** Thân gấp / mở. Gập thì ra khỏi Tab và trình đọc màn hình (inert ngay, visibility khi khép xong) - vẫn dựng sẵn để mở ra không chờ. */
export function Collapse({ open, id, children, className, appear = false, onOpened }: { onOpened?: (element: HTMLElement) => void; open: boolean; id?: string; children: ReactNode; className?: string; appear?: boolean }) {
  const box = useRef<HTMLDivElement>(null);
  const animation = useRef<Animation | null>(null);
  const previous = useRef(open);
  // Nội dung có sẵn lúc trang mới vào (quay lại Thư viện đã có sách) không mọc từ 0: khung trang đang hiện vào rồi, mọc thêm là trang cao
  // dần và chỗ cuộn trôi (video 25-10 "mở tab thư viện bị giật"). Chỉ nội dung tới SAU lúc ấy mới mở ra.
  const from = useRef<number | null>(appear && open && !pageSettling() ? 0 : null);
  const opened = useRef(onOpened);
  opened.current = onOpened;
  if (previous.current !== open) {
    from.current = box.current?.getBoundingClientRect().height ?? 0;
    previous.current = open;
  }
  useLayoutEffect(() => {
    const element = box.current;
    if (!element || from.current === null) return;
    const start = from.current;
    from.current = null;
    animation.current?.cancel();
    const height = open ? element.firstElementChild?.getBoundingClientRect().height ?? 0 : 0;
    const reduced = prefersReducedMotion();
    // Réduit: giữ bố cục cũ khi đang mờ ra; chỉ thu lại sau fade, không tween height.
    if (reduced && !open) element.style.height = `${start}px`;
    const current = element.animate?.(reduced ? [{ opacity: open ? 0 : 1 }, { opacity: open ? 1 : 0 }] : [{ height: `${start}px` }, { height: `${height}px` }], {
      duration: reduced ? MOTION.fast : open ? MOTION.medium : MOTION.mediumOut,
      easing: open ? EASE.standard : EASE.accelerate,
    }) ?? null;
    animation.current = current;
    const finish = () => { element.style.height = ""; if (open) opened.current?.(element); };
    if (current) current.onfinish = finish;
    else finish();
    return () => { current?.cancel(); element.style.height = ""; };
  }, [open]);
  return (
    <div ref={box} id={id} className="motion-collapse" data-state={open ? "open" : "closed"} inert={!open}>
      <div className={cn("flow-root", className)}>{children}</div>
    </div>
  );
}

const FOLD_PREFIX = "abook.fold.";

/** Trạng thái gấp / mở đã nhớ của một khối (localStorage; không đọc / ghi được thì theo mặc định). */
export function readFold(key: string, fallback: boolean, storage: Pick<Storage, "getItem"> | undefined = safeStorage()): boolean {
  try {
    const value = storage?.getItem(FOLD_PREFIX + key);
    return value === "1" ? true : value === "0" ? false : fallback;
  } catch {
    return fallback;
  }
}

export function writeFold(key: string, open: boolean, storage: Pick<Storage, "setItem"> | undefined = safeStorage()): void {
  try {
    storage?.setItem(FOLD_PREFIX + key, open ? "1" : "0");
  } catch {
    /* không lưu được thì lần sau theo mặc định */
  }
}

function safeStorage(): Storage | undefined {
  try {
    return typeof localStorage === "undefined" ? undefined : localStorage;
  } catch {
    return undefined;
  }
}

/** Gấp / mở có nhớ: `key` riêng cho từng khối ("devices.storage"…). */
export function useFold(key: string, defaultOpen = false): [boolean, (open: boolean) => void] {
  const [saved, setSaved] = useState(() => ({ key, open: readFold(key, defaultOpen) }));
  const open = saved.key === key ? saved.open : readFold(key, defaultOpen);
  if (saved.key !== key) setSaved({ key, open });
  return [
    open,
    (value: boolean) => {
      setSaved({ key, open: value });
      writeFold(key, value);
    },
  ];
}

/** Khối gấp / mở trong một màn dài: đầu là nút (tên, một dòng tóm tắt giá trị hiện tại, mũi tên xoay), thân là `Collapse`. Mặc định gập -
 *  phần ít dùng không chiếm chỗ; mở rồi thì lần sau vẫn mở. `heading`: cấp tiêu đề cho trình đọc màn hình (mặc định h2). */
export function Fold({
  storageKey,
  title,
  summary,
  icon,
  defaultOpen = false,
  heading = "h2",
  className,
  bodyClassName,
  flat,
  onOpened,
  children,
}: {
  storageKey: string;
  title: ReactNode;
  summary?: ReactNode;
  icon?: ReactNode;
  defaultOpen?: boolean;
  heading?: "h2" | "h3";
  className?: string;
  bodyClassName?: string;
  /** Không khung: đầu mục và nội dung thẳng mép nội dung của trang (mục nằm trong một tab đã phẳng - không khung lồng khung). */
  flat?: boolean;
  onOpened?: (element: HTMLElement) => void;
  children: ReactNode;
}) {
  const [open, setOpen] = useFold(storageKey, defaultOpen);
  const id = useId();
  const Heading = heading;
  return (
    <section className={cn("min-w-0", !flat && "rounded-2xl border border-line bg-panel", className)}>
      <Heading className="m-0">
        <DisclosureRow title={title} summary={summary} icon={icon} expanded={open} controls={id} onClick={() => setOpen(!open)} className={flat ? undefined : "px-4"} />
      </Heading>
      <Collapse open={open} onOpened={onOpened} id={id} className={cn(flat ? "pb-2" : "px-4 pb-4", bodyClassName)}>
        {children}
      </Collapse>
    </section>
  );
}

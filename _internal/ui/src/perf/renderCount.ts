// Đếm số lần MỖI component vẽ lại, theo tên - cho các bài đo hiệu năng (src/perf/*.perf.dom.test.tsx, docs/PERF_WEB.md).
// Cắm vào móc của React DevTools: react-dom gọi `onCommitFiberRoot` sau mỗi lần commit. Phải nạp TRƯỚC react-dom (import đầu tiên của file đo):
// react-dom chỉ tìm móc lúc mô-đun của nó chạy.
//
// Một fiber "vừa vẽ" khi mới dựng (không có alternate) hay mang cờ PerformedWork; nhánh mà React bỏ qua cả cây (con trỏ child không đổi so
// với alternate) không đi xuống - cờ cũ ở đó là của lần vẽ trước (cùng luật với DevTools: didFiberRender / bailout).

type Fiber = {
  tag: number;
  type: unknown;
  flags: number;
  child: Fiber | null;
  sibling: Fiber | null;
  alternate: Fiber | null;
};

const PERFORMED_WORK = 1;
/** FunctionComponent, ForwardRef, SimpleMemoComponent: nơi thân hàm của component thật sự chạy. MemoComponent (14) có fiber con riêng cho thân. */
const COMPONENT_TAGS = new Set([0, 11, 15]);

const counts = new Map<string, number>();
let commits = 0;

function nameOf(fiber: Fiber): string {
  const type = fiber.type as { displayName?: string; name?: string; render?: { name?: string } } | null;
  return type?.displayName || type?.name || type?.render?.name || "(vô danh)";
}

function walk(first: Fiber | null): void {
  for (let fiber = first; fiber; fiber = fiber.sibling) {
    const previous = fiber.alternate;
    if (COMPONENT_TAGS.has(fiber.tag) && (previous === null || (fiber.flags & PERFORMED_WORK) !== 0)) {
      const name = nameOf(fiber);
      counts.set(name, (counts.get(name) ?? 0) + 1);
    }
    if (previous === null || fiber.child !== previous.child) walk(fiber.child);
  }
}

const hook = {
  supportsFiber: true,
  renderers: new Map(),
  inject(renderer: unknown) {
    hook.renderers.set(hook.renderers.size + 1, renderer);
    return hook.renderers.size;
  },
  checkDCE() {},
  onScheduleFiberRoot() {},
  onCommitFiberUnmount() {},
  onPostCommitFiberRoot() {},
  onCommitFiberRoot(_id: number, root: { current: Fiber }) {
    commits++;
    const current = root.current;
    // Gốc: lần dựng đầu thì cả cây mới; sau đó so với alternate như mọi fiber.
    if (current.alternate === null || current.child !== current.alternate.child) walk(current.child);
  },
};

(globalThis as { __REACT_DEVTOOLS_GLOBAL_HOOK__?: unknown }).__REACT_DEVTOOLS_GLOBAL_HOOK__ = hook;

/** Xoá số đếm (đầu mỗi pha đo). */
export function resetRenders(): void {
  counts.clear();
  commits = 0;
}

/** Số lần vẽ của component `name` từ lần xoá gần nhất. */
export function renders(name: string): number {
  return counts.get(name) ?? 0;
}

/** Tổng số lần vẽ mọi component và số commit từ lần xoá gần nhất. */
export function renderTotals(): { components: number; commits: number } {
  let components = 0;
  for (const value of counts.values()) components += value;
  return { components, commits };
}

/** Mười component vẽ nhiều nhất - in kèm số đo để thấy ai gánh. */
export function topRenders(limit = 10): [string, number][] {
  return [...counts].sort((a, b) => b[1] - a[1]).slice(0, limit);
}

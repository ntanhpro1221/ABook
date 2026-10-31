// Đồ nghề chung của các bài đo hiệu năng web (docs/PERF_WEB.md): dựng một cây trong happy-dom, đo thời gian và số lần vẽ của từng pha,
// IntersectionObserver giả để "cuộn" danh sách ảo hoá (shared/Windowed) tới khối bất kỳ, và cửa hàng nhỏ cho các hook giả (chỉ component
// đăng ký mới vẽ lại - như truy vấn / context thật, không vẽ lại cả cây từ gốc).
import { renders, renderTotals, resetRenders, topRenders } from "./renderCount";
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { useSyncExternalStore } from "react";

/** Một giá trị đổi được từ bài đo; hook giả đọc nó qua `use()`. */
export class Store<T> {
  private listeners = new Set<() => void>();
  constructor(public value: T) {}
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => void this.listeners.delete(listener);
  };
  set(value: T): void {
    this.value = value;
    this.listeners.forEach((listener) => listener());
  }
  use(): T {
    return useSyncExternalStore(this.subscribe, () => this.value);
  }
}

/** IntersectionObserver giả: ghi lại mọi phần tử được quan sát; `showOnly` báo cho từng observer phần tử nào đang "trong khung". */
export class FakeIntersections {
  static all = new Set<FakeIntersections>();
  targets = new Set<Element>();
  constructor(private callback: IntersectionObserverCallback) {
    FakeIntersections.all.add(this);
  }
  observe(target: Element) {
    this.targets.add(target);
  }
  unobserve(target: Element) {
    this.targets.delete(target);
  }
  disconnect() {
    this.targets.clear();
    FakeIntersections.all.delete(this);
  }
  takeRecords() {
    return [];
  }
  /** Báo trạng thái mọi phần tử đang quan sát: `visible(element)` đúng thì đang trong khung. */
  static report(visible: (element: Element) => boolean) {
    for (const observer of FakeIntersections.all) {
      const entries = [...observer.targets].map((target) => ({ target, isIntersecting: visible(target) }) as IntersectionObserverEntry);
      if (entries.length) observer.callback(entries, observer as unknown as IntersectionObserver);
    }
  }
}

export function installFakes(): void {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  (globalThis as { IntersectionObserver: unknown }).IntersectionObserver = FakeIntersections;
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, {
    configurable: true,
    value: function* (this: CSSStyleDeclaration) {
      for (let i = 0; i < this.length; i++) yield this.item(i);
    },
  });
  HTMLElement.prototype.animate = function () {
    return { cancel() {}, finish() {}, onfinish: null, finished: Promise.resolve() } as unknown as Animation;
  };
  HTMLElement.prototype.scrollTo = function () {};
}

export interface Phase {
  name: string;
  ms: number;
  /** Số lần vẽ của component đang theo dõi (vd ChapterRow). */
  watched: number;
  /** Tổng số lần vẽ mọi component. */
  components: number;
  commits: number;
  /** Ảnh chuyển cảnh (MotionRegion chụp lại một vùng để mờ chéo) và số nút DOM trong các ảnh ấy. */
  snapshots: number;
  snapshotNodes: number;
  top: [string, number][];
}

/** Một phiên đo: dựng `node` vào một khung mới, mỗi `phase` đo thời gian + số lần vẽ. */
export class Bench {
  root: Root;
  host: HTMLElement;
  phases: Phase[] = [];
  constructor(
    readonly title: string,
    readonly watch: string,
  ) {
    this.host = document.createElement("main");
    this.host.style.overflowY = "auto";
    document.body.append(this.host);
    this.root = createRoot(this.host);
  }

  async phase(name: string, run: () => void | Promise<void>, repeat = 1): Promise<Phase> {
    resetRenders();
    let snapshots = 0;
    let snapshotNodes = 0;
    const watcher = new MutationObserver((records) => {
      for (const record of records) for (const node of record.addedNodes) {
        if (node instanceof HTMLElement && node.classList.contains("motion-snapshot")) {
          snapshots++;
          snapshotNodes += node.getElementsByTagName("*").length;
        }
      }
    });
    watcher.observe(document.body, { childList: true, subtree: true });
    const started = performance.now();
    for (let i = 0; i < repeat; i++) await act(async () => void (await run()));
    const ms = (performance.now() - started) / repeat;
    await act(async () => {});
    watcher.disconnect();
    const totals = renderTotals();
    const phase = {
      name,
      ms: Math.round(ms * 10) / 10,
      watched: renders(this.watch) / repeat,
      components: totals.components / repeat,
      commits: totals.commits / repeat,
      snapshots: snapshots / repeat,
      snapshotNodes: snapshotNodes / repeat,
      top: topRenders(6),
    };
    this.phases.push(phase);
    return phase;
  }

  mount(node: ReactNode) {
    return this.phase("dựng", () => this.root.render(node));
  }

  /** Số nút DOM trong khung (cả portal ngoài khung không tính). */
  nodes(): number {
    return this.host.getElementsByTagName("*").length;
  }

  report(extra: Record<string, number> = {}): void {
    const lines = [`\n[perf] ${this.title} (theo dõi: ${this.watch})`];
    for (const [key, value] of Object.entries(extra)) lines.push(`  ${key}: ${value}`);
    for (const phase of this.phases) {
      lines.push(
        `  ${phase.name.padEnd(34)} ${String(phase.ms).padStart(8)} ms  ${this.watch} ${String(phase.watched).padStart(6)}  mọi component ${String(phase.components).padStart(6)}  commit ${phase.commits}  ảnh chuyển cảnh ${phase.snapshots} (${phase.snapshotNodes} nút)`,
      );
      lines.push(`      ${phase.top.map(([name, count]) => `${name}×${count}`).join(", ")}`);
    }
    console.log(lines.join("\n"));
    // Một dòng máy đọc cho scripts/perf_web.mjs (chạy nhiều lần, lấy trung vị).
    console.log(`[perf-json] ${JSON.stringify({ title: this.title, watch: this.watch, extra, phases: this.phases.map(({ top: _top, ...phase }) => phase) })}`);
  }

  async unmount() {
    await act(() => this.root.unmount());
    this.host.remove();
  }
}

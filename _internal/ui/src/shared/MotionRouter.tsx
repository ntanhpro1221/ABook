// Keep hash history and its index, and animate the outgoing/incoming page with
// geometry. Root tabs slide in their visual order; parent links reverse push
// motion even when navigate(parent) creates a PUSH history entry. Book artwork
// flies separately while the new page loads. No document View Transition.
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { Router, UNSAFE_createHashHistory, type Location, type NavigationType } from "react-router";
import { enterPage, leavePage, navMotion } from "./motion";
import { installBackOrder } from "./backOrder";
import { dismissTopLayer } from "@/shared/backLayers";
import { captureBookCover, landBookCover } from "./bookCoverFlight";

type RouterState = { action: NavigationType; location: Location };

/** Browser Back khôi phục slot trước khi đóng lớp; POP bù không đóng thêm lớp bên dưới. */
export function layerHistoryGuard(dismiss: () => boolean, go: (delta: number) => void) {
  let restoring = false;
  return (action: "POP" | "PUSH" | "REPLACE", from: number, to: number): boolean => {
    if (restoring && action === "POP") { restoring = false; return true; }
    if (action !== "POP" || to >= from || !dismiss()) return false;
    restoring = true;
    go(from - to);
    return true;
  };
}

/** Vị trí trong lịch sử react-router ghi vào history.state (`idx`) - như shared/backLayers.historyIndex. */
function historyIndex(): number {
  const idx = (window.history.state as { idx?: unknown } | null)?.idx;
  return typeof idx === "number" ? idx : 0;
}

export function MotionHashRouter({ children }: { children: ReactNode }) {
  const historyRef = useRef<ReturnType<typeof UNSAFE_createHashHistory> | null>(null);
  historyRef.current ??= UNSAFE_createHashHistory({ v5Compat: true });
  const history = historyRef.current;
  const [state, setState] = useState<RouterState>({ action: history.action, location: history.location });
  const now = useRef({ pathname: history.location.pathname, search: history.location.search, idx: historyIndex() });
  const latest = useRef(0);
  const coverBack = useRef(false);
  const guard = useRef<ReturnType<typeof layerHistoryGuard> | null>(null);
  guard.current ??= layerHistoryGuard(() => dismissTopLayer(), (delta) => history.go(delta));
  useLayoutEffect(() => {
    const cleanup = installBackOrder();
    const escape = (event: KeyboardEvent) => {
      // Esc của bộ gõ đang soạn chữ (IME) chỉ huỷ chữ đang soạn - không đóng hộp / lớp đang mở (mất cả phần đã gõ).
      if (event.key !== "Escape" || event.defaultPrevented || event.isComposing) return;
      if (dismissTopLayer(document, undefined, undefined, undefined, false)) {
        event.preventDefault(); event.stopImmediatePropagation();
      }
    };
    document.addEventListener("keydown", escape, true);
    return () => { cleanup(); captureBookCover("", ""); document.removeEventListener("keydown", escape, true); };
  }, []);
  useLayoutEffect(
    () =>
      history.listen(({ action, location }) => {
        const to = { pathname: location.pathname, search: location.search, idx: historyIndex() };
        if (guard.current?.(action, now.current.idx, to.idx)) return;
        const nav = navMotion(action, now.current, to);
        captureBookCover(now.current.pathname, to.pathname);
        coverBack.current = nav === "back";
        now.current = to;
        // Bấm liên tiếp: mọi lần chờ cùng một lần mờ và chỉ lần cuối được áp - lần cũ xong muộn không đè vị trí mới hơn.
        const id = ++latest.current;
        const update = () => { if (id === latest.current) setState({ action, location }); };
        if (nav === "none") update();
        else void leavePage(nav).then(update);
      }),
    [history],
  );
  useLayoutEffect(() => enterPage(undefined, () => landBookCover(coverBack.current)), [state]);
  return (
    <Router location={state.location} navigationType={state.action} navigator={history}>
      {children}
    </Router>
  );
}

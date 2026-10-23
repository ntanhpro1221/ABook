// HashRouter có chuyển trang (a120 - chủ app: "đóng mở các màn hình… quá xấu, thậm chí là không có"). Như HashRouter của react-router (cùng
// lịch sử hash, cùng `idx` trong history.state mà android/backLayers đọc), chỉ khác: mỗi lần đổi trang chạy trong một View Transition -
// trang cũ lùi sang một bên và mờ, trang mới tới từ phía kia (sâu vào / lùi ra), hay mờ qua (ngang hàng: tab, nhóm cài đặt). Router khai báo
// (HashRouter) không nhận `viewTransition` - chỉ router dữ liệu có. Không có API thì đổi thẳng và usePageEnter làm hiện dần như trước.
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { Router, UNSAFE_createHashHistory, type Location, type NavigationType } from "react-router";
import { navMotion, withViewTransition } from "./motion";
import { installBackOrder } from "./backOrder";
import { dismissTopLayer } from "@/android/backLayers";

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

/** Vị trí trong lịch sử react-router ghi vào history.state (`idx`) - như android/backLayers.historyIndex. */
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
  const guard = useRef<ReturnType<typeof layerHistoryGuard> | null>(null);
  guard.current ??= layerHistoryGuard(() => dismissTopLayer(), (delta) => history.go(delta));
  useLayoutEffect(() => {
    const cleanup = installBackOrder();
    const escape = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      if (dismissTopLayer(document, undefined, undefined, undefined, false)) {
        event.preventDefault(); event.stopImmediatePropagation();
      }
    };
    document.addEventListener("keydown", escape, true);
    return () => { cleanup(); document.removeEventListener("keydown", escape, true); };
  }, []);
  useLayoutEffect(
    () =>
      history.listen(({ action, location }) => {
        const to = { pathname: location.pathname, search: location.search, idx: historyIndex() };
        if (guard.current?.(action, now.current.idx, to.idx)) return;
        const nav = navMotion(action, now.current, to);
        now.current = to;
        const update = () => setState({ action, location });
        if (nav === "none") update();
        else withViewTransition(update, nav);
      }),
    [history],
  );
  return (
    <Router location={state.location} navigationType={state.action} navigator={history}>
      {children}
    </Router>
  );
}

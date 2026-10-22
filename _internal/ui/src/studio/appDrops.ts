/**
 * Cửa sổ app (Tauri): HTML5 không nhận file thả vào (WebView2 giao cho vỏ), nên vỏ đọc đường dẫn thật và phát `abook-drag` vào trang
 * (shell/src-tauri/src/main.rs): `state` là "enter" (đang kéo ngang cửa sổ), "leave" hoặc "drop" (kèm `paths`). Thư viện (desktop/httpSource) và
 * màn tạo sách Studio cùng nghe sự kiện này qua hàm này - một nơi.
 */
export function watchAppDropPaths({ hover, drop }: { hover: (on: boolean) => void; drop: (paths: string[]) => void }): () => void {
  const listener = (event: Event) => {
    const detail = (event as CustomEvent<{ state?: string; paths?: string[] }>).detail;
    if (detail?.state === "enter") hover(true);
    else if (detail?.state === "leave") hover(false);
    else if (detail?.state === "drop") {
      hover(false);
      drop(detail.paths ?? []);
    }
  };
  window.addEventListener("abook-drag", listener);
  return () => window.removeEventListener("abook-drag", listener);
}

import "@/styles.css";
import { entry } from "./entries";
import { runEntry } from "./run";
import { galleryState } from "./state";
import type { Theme } from "./entries";

// Khung app của một mục: dựng mục vào #root, rồi báo ra `window.__gallery` cho script chụp (ready, errors, missing).

declare global {
  interface Window {
    __gallery?: { ready: boolean; errors: string[]; missing: string[]; known: string[]; id: string };
  }
}

export async function startFrame(id: string, theme: Theme): Promise<void> {
  const report = () => (window.__gallery = { ready: galleryState.ready, errors: galleryState.errors, missing: [...galleryState.missing], known: [...galleryState.known], id });
  report();
  const item = entry(id);
  const root = document.getElementById("root")!;
  if (!item) {
    root.textContent = `Không có mục trưng bày “${id}”. Xem danh mục ở gallery.html#/`;
    galleryState.errors.push(`unknown entry ${id}`);
    galleryState.ready = true;
    report();
    return;
  }
  document.title = `${item.title} · ABook`;
  await runEntry(item, theme, root);
  report();
}

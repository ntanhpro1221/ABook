import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { ENTRIES, FRAMES, entry, type Entry, type Theme } from "./entries";
import "./gallery.css";

// Mục lục (#/) và khung xem một mục (#/<mục>?theme=dark): khung app nằm trong iframe đúng khổ (điện thoại 412x915, máy tính 1440x900),
// thu nhỏ cho vừa cửa sổ - bên trong là trang `?frame=<mục>` mà script chụp mở thẳng.

function parseHash(): { id: string; theme: Theme } {
  const raw = window.location.hash.replace(/^#\/?/, "");
  const [path, query = ""] = raw.split("?");
  return { id: path, theme: new URLSearchParams(query).get("theme") === "dark" ? "dark" : "light" };
}

export function frameUrl(id: string, theme: Theme): string {
  return `?frame=${encodeURIComponent(id).replace(/%2F/g, "/")}&theme=${theme}`;
}

const href = (id: string, theme: Theme) => `#/${id}${theme === "dark" ? "?theme=dark" : ""}`;

function ThemeSwitch({ id, theme }: { id: string; theme: Theme }) {
  return (
    <span className="g-switch" role="group" aria-label="Chủ đề">
      {(["light", "dark"] as const).map((value) => (
        <a key={value} href={href(id, value)} aria-current={value === theme ? "true" : undefined}>
          {value === "light" ? "Sáng" : "Tối"}
        </a>
      ))}
    </span>
  );
}

function List({ theme }: { theme: Theme }) {
  const platforms = [
    { key: "desktop" as const, label: "Máy tính (Nghe + Studio)" },
  ];
  return (
    <main className="g-index">
      <header className="g-bar">
        <h1>ABook · Phòng trưng bày</h1>
        <span className="g-muted">{ENTRIES.length} mục · dữ liệu giả, đồng hồ cố định 21:15 24-10-2026</span>
        <ThemeSwitch id="" theme={theme} />
      </header>
      {platforms.map((platform) => {
        const items = ENTRIES.filter((item) => item.platform === platform.key);
        const groups = [...new Set(items.map((item) => item.group))];
        return (
          <section key={platform.key}>
            <h2>
              {platform.label} <span className="g-muted">{FRAMES[platform.key].width}×{FRAMES[platform.key].height}</span>
            </h2>
            <div className="g-groups">
              {groups.map((group) => (
                <div key={group} className="g-group">
                  <h3>{group}</h3>
                  <ul>
                    {items
                      .filter((item) => item.group === group)
                      .map((item) => (
                        <li key={item.id}>
                          <a href={href(item.id, theme)}>{item.title}</a> <code>#/{item.id}</code>
                        </li>
                      ))}
                  </ul>
                </div>
              ))}
            </div>
          </section>
        );
      })}
    </main>
  );
}

function useWindowSize() {
  const [size, setSize] = useState({ width: window.innerWidth, height: window.innerHeight });
  useEffect(() => {
    const update = () => setSize({ width: window.innerWidth, height: window.innerHeight });
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);
  return size;
}

function Viewer({ item, theme }: { item: Entry; theme: Theme }) {
  const frame = FRAMES[item.platform];
  const size = useWindowSize();
  const scale = Math.min(1, (size.width - 32) / frame.width, (size.height - 80) / frame.height);
  const index = ENTRIES.indexOf(item);
  const prev = ENTRIES[index - 1];
  const next = ENTRIES[index + 1];
  return (
    <main className="g-viewer">
      <header className="g-bar">
        <a href={href("", theme)}>← Mục lục</a>
        <strong>{item.title}</strong>
        <span className="g-muted">
          {item.group} · <code>#/{item.id}</code>
        </span>
        <span className="g-spacer" />
        {prev && <a href={href(prev.id, theme)}>‹ Trước</a>}
        {next && <a href={href(next.id, theme)}>Sau ›</a>}
        <ThemeSwitch id={item.id} theme={theme} />
        <a href={frameUrl(item.id, theme)} target="_blank" rel="noreferrer">
          Mở riêng
        </a>
      </header>
      <div className="g-stage">
        <div style={{ width: frame.width * scale, height: frame.height * scale, position: "relative" }}>
          <iframe
            key={`${item.id}-${theme}`}
            title={item.title}
            src={frameUrl(item.id, theme)}
            width={frame.width}
            height={frame.height}
            style={{ position: "absolute", left: 0, top: 0, transform: `scale(${scale})`, transformOrigin: "top left" }}
          />
        </div>
      </div>
    </main>
  );
}

function Gallery() {
  const [place, setPlace] = useState(parseHash);
  useEffect(() => {
    const update = () => setPlace(parseHash());
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  const item = place.id ? entry(place.id) : undefined;
  document.documentElement.dataset.galleryTheme = place.theme;
  if (place.id && !item) return <main className="g-index">Không có mục “{place.id}”. <a href="#/">Về mục lục</a></main>;
  return item ? <Viewer item={item} theme={place.theme} /> : <List theme={place.theme} />;
}

export function startIndex(): void {
  // Danh mục cho scripts/gallery_shots.mjs (đọc từ trang này thay vì chép lại danh sách).
  (window as { __galleryEntries?: unknown }).__galleryEntries = ENTRIES.map(({ id, platform, group, title }) => ({ id, platform, group, title, ...FRAMES[platform] }));
  createRoot(document.getElementById("root")!).render(<Gallery />);
}

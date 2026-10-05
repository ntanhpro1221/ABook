import { Clapperboard, Download, Library, Pause, Plus, Settings } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router";
import { useRestoreLastListening } from "@/listen/LibraryScreen";
import { useNowPlaying } from "@/listen/player";
import { NowPlaying, PlayerBar } from "@/listen/PlayerViews";
import { BookCover } from "@/shared/BookCover";
import { cn } from "@/shared/cn";
import { useMediaQuery } from "@/shared/media";
import { usePageEnter } from "@/shared/motion";
import { APP_TITLE } from "@/shared/title";
import { formatPercent } from "@/shared/format";
import { Progress, Vu } from "@/shared/ui";
import { useAppInfo, useLibrary } from "@/studio/data";
import { usePrecastInvites } from "@/studio/PrecastReview";
import { HandOffButton, RemoteBars, ThisPlayerReporter } from "./RemotePhone";

// Máy tính = phía Nghe (giống hệt trình phát Android) + Studio sản xuất. Thanh bên tách hai khu rõ ràng.

function Brand() {
  return (
    <div className="flex items-center gap-2.5 px-2">
      <div className="grid size-9 place-items-center rounded-xl bg-accent text-accent-ink shadow-card">
        <span className="flex h-4 items-end gap-[3px]">
          <span className="h-2 w-[3px] rounded-sm bg-current" />
          <span className="h-4 w-[3px] rounded-sm bg-current" />
          <span className="h-3 w-[3px] rounded-sm bg-current" />
          <span className="h-[10px] w-[3px] rounded-sm bg-current" />
        </span>
      </div>
      <div className="text-[15px] font-bold tracking-tight">ABook</div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mt-6">
      <div className="mb-1.5 px-2.5 text-xs font-semibold uppercase tracking-[0.08em] text-fg-2">{title}</div>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

const NAV = "flex h-9 items-center gap-3 rounded-lg px-2.5 text-sm transition-colors";
const NAV_ACTIVE = "bg-nav-active font-semibold text-fg shadow-[0_0_0_1px_var(--nav-active-ring)] [&>svg]:text-accent-text";
const NAV_IDLE = "font-medium text-fg-2 hover:bg-hover hover:text-fg";

/** Mục thanh bên sáng cả khi đang ở trang con của nó (trang sách thuộc Thư viện, trang dự án thuộc Dự án). */
function NavItem({ to, icon: Icon, match, children }: { to: string; icon: typeof Library; match: (path: string) => boolean; children: ReactNode }) {
  const { pathname } = useLocation();
  const { setExpanded } = useNowPlaying();
  const active = match(pathname);
  return (
    <NavLink
      to={to}
      onClick={() => setExpanded(false)}
      aria-current={active ? "page" : undefined}
      className={cn(NAV, active ? NAV_ACTIVE : NAV_IDLE)}
    >
      <Icon className="size-[18px]" />
      {children}
    </NavLink>
  );
}

/** Màn hẹp (Studio từ xa trên điện thoại - webui/remote_studio.py): thanh bên nhường chỗ cho thanh tab dưới đáy. */
function TabItem({ to, icon: Icon, match, children }: { to: string; icon: typeof Library; match: (path: string) => boolean; children: ReactNode }) {
  const { pathname } = useLocation();
  const { setExpanded } = useNowPlaying();
  const active = match(pathname);
  return (
    <NavLink
      to={to}
      onClick={() => setExpanded(false)}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex min-w-0 flex-1 flex-col items-center gap-1 py-2 text-[11px] font-medium",
        active ? "text-accent-text" : "text-fg-2",
      )}
    >
      <Icon className="size-5" />
      <span className="truncate">{children}</span>
    </NavLink>
  );
}

function Producing() {
  const { pathname } = useLocation();
  const { data } = useLibrary({ live: pathname.startsWith("/studio") });
  const navigate = useNavigate();
  usePrecastInvites(data?.books);
  const live = (data?.books ?? []).filter((book) => book.running || book.starting);
  if (!live.length) return null;
  return (
    <div className="mt-2 space-y-1">
      {live.map((book) => (
        <button
          key={book.id}
          type="button"
          onClick={() => navigate(`/studio/${book.id}`)}
          className="flex w-full items-center gap-2.5 rounded-lg p-2 text-left hover:bg-hover"
        >
          <BookCover title={book.title} part={book.series?.part} size="xs" image={book.cover} className="size-8 rounded-md" />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 truncate text-xs font-medium">
              {book.paused ? (
                <Pause className="size-3 shrink-0 text-warning" aria-label="Đang tạm dừng" />
              ) : (
                <Vu className="h-2 text-accent" />
              )}
              <span className="truncate">{book.title}</span>
            </div>
            <div className="mt-1 flex items-center gap-2">
              <Progress value={book.progress.overall} running={!book.paused} size="xs" className="flex-1" />
              <span className="tabular text-[11px] text-fg-2">{book.starting ? "…" : formatPercent(book.progress.overall)}</span>
            </div>
          </div>
        </button>
      ))}
    </div>
  );
}

/** App Windows đóng gói có bản mới: nhắc ở thanh bên, bấm mở Cài đặt (mục "Cập nhật" nằm trên cùng). */
function UpdateNotice() {
  const { data: info } = useAppInfo();
  const navigate = useNavigate();
  const { setExpanded } = useNowPlaying();
  if (!info?.update || info.remote) return null;
  return (
    <button
      type="button"
      onClick={() => {
        setExpanded(false);
        navigate("/settings");
      }}
      className="mb-2 flex w-full items-center gap-2.5 rounded-lg border border-line bg-panel p-2.5 text-left hover:bg-hover"
    >
      <Download className="size-4 shrink-0 text-accent-text" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-semibold">Có ABook {info.update.version}</span>
        <span className="block text-xs text-fg-2">Bấm để cập nhật</span>
      </span>
    </button>
  );
}

const TITLES: [RegExp, string][] = [
  [/^\/$/, "Thư viện"],
  [/^\/book\//, "Sách"],
  [/^\/studio\/new/, "Tạo sách nói"],
  [/^\/studio\/.+/, "Dự án"],
  [/^\/studio$/, "Studio"],
  [/^\/settings/, "Cài đặt"],
];

export function Shell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const { expanded, setExpanded } = useNowPlaying();
  // Studio từ xa: thanh "Đang phát trên điện thoại" là việc của chính máy tính, cổng từ xa không mở đường ấy.
  const info = useAppInfo().data;
  const remote = Boolean(info?.remote);
  // Chỉ nghe (trình duyệt của iPhone, TV... đã ghép, máy tính chưa cho điều khiển sản xuất): không có Studio để vào.
  const listenOnly = Boolean(info?.listenOnly);
  useRestoreLastListening();

  // Bấm mục thanh bên khi màn "Đang nghe" đang mở: trang mới phải hiện ra, không bị lớp phủ che.
  const expandedNow = useRef(expanded);
  expandedNow.current = expanded;
  useEffect(() => {
    // Chỉ thu "Đang nghe" khi nó đang mở: gọi thừa sẽ chạy một View Transition rỗng mỗi lần chuyển trang.
    if (expandedNow.current) setExpanded(false);
  }, [pathname, setExpanded]);
  const main = useRef<HTMLElement | null>(null);
  // Dưới md (768px) là bố cục điện thoại: thanh tab dưới đáy, màn "Đang nghe" xếp dọc. Thanh phát đầy đủ cần ~1024px.
  const phoneWidth = useMediaQuery("(max-width: 767px)");
  const compactBar = useMediaQuery("(max-width: 1023px)");
  usePageEnter(main, pathname);

  // Tên chung theo đường dẫn; màn nào biết tên cụ thể (sách, chương, dự án) thì `usePageTitle` ghi đè sau đó.
  useLayoutEffect(() => {
    const title = TITLES.find(([pattern]) => pattern.test(pathname))?.[1];
    document.title = title ? `${title} · ${APP_TITLE}` : APP_TITLE;
  }, [pathname]);

  return (
    <div className="flex h-full">
      <aside className="hidden w-[236px] shrink-0 flex-col border-r border-line bg-sunken px-3 pb-4 pt-5 md:flex">
        <Brand />
        <nav aria-label="Điều hướng">
          <Section title="Nghe">
            <NavItem to="/" icon={Library} match={(path) => path === "/" || path.startsWith("/book/")}>
              Thư viện
            </NavItem>
          </Section>
          {!listenOnly && (
            <Section title="Studio">
              <NavItem to="/studio" icon={Clapperboard} match={(path) => path.startsWith("/studio") && path !== "/studio/new"}>
                Dự án
              </NavItem>
              <NavItem to="/studio/new" icon={Plus} match={(path) => path === "/studio/new"}>
                Tạo sách nói
              </NavItem>
              <Producing />
            </Section>
          )}
        </nav>
        <div className="mt-auto">
          <UpdateNotice />
          <NavItem to="/settings" icon={Settings} match={(path) => path.startsWith("/settings")}>
            Cài đặt
          </NavItem>
        </div>
      </aside>
      <div className="relative flex min-w-0 flex-1 flex-col">
        <main ref={main} className="min-h-0 flex-1 overflow-y-auto" inert={expanded}>
          {children}
        </main>
        {/* Màn "Đang nghe" phủ kín cột này: mọi thứ nằm dưới nó cũng ra khỏi cây trợ năng và Tab (inert), không chỉ khuất mắt. */}
        {!remote && <div className="contents" inert={expanded}><RemoteBars /></div>}
        {!remote && <ThisPlayerReporter />}
        {/* Cửa sổ hẹp (trình duyệt điện thoại nghe thư viện máy tính, soát UX 29-09): thanh phát gọn như app Android -
            thanh đầy đủ ở 375px chồng các nút lên nhau; các nút phụ vẫn có ở màn "Đang nghe". */}
        <div className="contents" inert={expanded}>
          <PlayerBar compact={compactBar} notices extra={remote ? undefined : <HandOffButton />} />
        </div>
        <nav aria-label="Điều hướng" inert={expanded} className="flex border-t border-line bg-sunken pb-[env(safe-area-inset-bottom)] md:hidden">
          <TabItem to="/" icon={Library} match={(path) => path === "/" || path.startsWith("/book/")}>
            Thư viện
          </TabItem>
          {!listenOnly && (
            <TabItem to="/studio" icon={Clapperboard} match={(path) => path.startsWith("/studio") && path !== "/studio/new"}>
              Dự án
            </TabItem>
          )}
          {!listenOnly && (
            <TabItem to="/studio/new" icon={Plus} match={(path) => path === "/studio/new"}>
              Tạo sách
            </TabItem>
          )}
          <TabItem to="/settings" icon={Settings} match={(path) => path.startsWith("/settings")}>
            Cài đặt
          </TabItem>
        </nav>
        {/* Cùng nút "Phát trên thiết bị khác" như thanh dưới: cửa sổ hẹp dùng thanh gọn không có nó (soát UX 05-10). */}
        <NowPlaying mobile={phoneWidth} actions={remote ? undefined : <HandOffButton className="max-sm:size-11" />} />
      </div>
    </div>
  );
}

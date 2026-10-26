import { Clapperboard, Clock, Download, Library, PanelLeftClose, PanelLeftOpen, Pause, Settings } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { useRestoreLastListening } from "@/listen/LibraryScreen";
import { useNowPlaying } from "@/listen/player";
import { NowPlaying, PlayerBar } from "@/listen/PlayerViews";
import { readerEditing } from "./readerEditing";
import { ShortcutsHost } from "@/listen/Shortcuts";
import { BookCover } from "@/shared/BookCover";
import { cn } from "@/shared/cn";
import { useMediaQuery } from "@/shared/media";
import { pageFocusKey, useLayoutChangeFade, usePageEnter, usePageFocus } from "@/shared/motion";
import { AnimatedRows, MotionPresence } from "@/shared/MotionPresence";
import { MotionRegion } from "@/shared/MotionRegion";
import { APP_TITLE } from "@/shared/title";
import { formatPercent } from "@/shared/format";
import { ContentSkeleton, IconButton, InlineError, OfflineStrip, Progress, Vu } from "@/shared/ui";
import { useAppInfo, useLibrary } from "@/studio/data";
import { usePrecastInvites } from "@/studio/PrecastReview";
import { PeerBar } from "./PeerBar";
import { HandOffButton, RemoteBars, ThisPlayerReporter } from "./RemotePhone";
import { TitleBar } from "./TitleBar";
import { windowChrome } from "./windowChrome";

// Cùng ba điểm đến với điện thoại; dự án đang làm nằm ngay dưới Studio.

function Brand() {
  return (
    <div className="flex items-center gap-2.5 px-2">
      <div className="grid size-9 place-items-center rounded-cover bg-accent text-accent-ink shadow-card">
        <span className="flex h-4 items-end gap-[3px]">
          <span className="h-2 w-[3px] rounded-full bg-current" />
          <span className="h-4 w-[3px] rounded-full bg-current" />
          <span className="h-3 w-[3px] rounded-full bg-current" />
          <span className="h-[10px] w-[3px] rounded-full bg-current" />
        </span>
      </div>
      <div className="text-[0.9375rem] font-bold tracking-tight">ABook</div>
    </div>
  );
}

const NAV = "sidebar-link flex h-10 items-center gap-3 rounded-control px-2 text-sm";
// Mục đang mở: nền trung tính nhạt + chữ đậm thường (DESIGN 6 "Điều hướng"). Không dấu tích - dấu tích là của lựa chọn trong danh sách chọn.
const NAV_ACTIVE = "bg-hover font-semibold text-fg";
const NAV_IDLE = "font-medium text-fg-2 hover:bg-hover hover:text-fg";

/** Mục thanh bên sáng cả khi ở trang con: sách thuộc Thư viện, dự án thuộc Studio. `ink`: mực icon bắt đầu bao nhiêu phần 24 trong ô
 *  (đo getBBox: Library 3, Clapperboard 1,03, Settings 2,04) - icon kéo ra chừng ấy để mực mọi mục thẳng mép logo, chữ vẫn chung một cột. */
function NavItem({ to, icon: Icon, ink, match, children }: { to: string; icon: typeof Library; ink: number; match: (path: string) => boolean; children: ReactNode }) {
  const shift = `calc(clamp(1.125rem, 0.75rlh, 1.96875rem) * ${ink} / 24)`;
  const { pathname } = useLocation();
  const { setExpanded } = useNowPlaying();
  const active = match(pathname);
  return (
    <Link
      to={to}
      data-sidebar-top
      onClick={() => setExpanded(false)}
      aria-current={active ? "page" : undefined}
      aria-label={typeof children === "string" ? children : undefined}
      className={cn(NAV, active ? NAV_ACTIVE : NAV_IDLE)}
    >
      <Icon className="glyph" style={{ marginLeft: `calc(-1 * ${shift})`, marginRight: shift }} />
      <span data-sidebar-label>{children}</span>
    </Link>
  );
}

/** Màn hẹp (Studio từ xa trên điện thoại - webui/remote_studio.py): thanh bên nhường chỗ cho thanh tab dưới đáy. */
function TabItem({ to, icon: Icon, match, children }: { to: string; icon: typeof Library; match: (path: string) => boolean; children: ReactNode }) {
  const { pathname } = useLocation();
  const { setExpanded } = useNowPlaying();
  const active = match(pathname);
  return (
    <Link
      to={to}
      onClick={() => setExpanded(false)}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex min-w-0 flex-1 flex-col items-center gap-1 py-2 text-[0.6875rem] font-medium transition-colors duration-(--motion-medium) ease-standard",
        active ? "text-accent-text" : "text-fg-2",
      )}
    >
      {/* Tab vừa chọn: biểu tượng nhún nhẹ lên (transform), màu chuyển dần - không đổi màu tức thì. */}
      <Icon className={cn("motion-tab-icon size-5 transition-transform duration-(--motion-medium) ease-decelerate", active && "-translate-y-px scale-110")} />
      <span className="truncate">{children}</span>
    </Link>
  );
}

export function Producing() {
  const { pathname } = useLocation();
  const { data, isLoading, isError, refetch } = useLibrary({ live: pathname.startsWith("/studio") });
  const navigate = useNavigate();
  const { setExpanded } = useNowPlaying();
  usePrecastInvites(data?.books);
  const live = (data?.books ?? []).filter((book) => book.running || book.starting || book.queuePosition != null)
    .sort((a, b) => (a.queuePosition ?? 0) - (b.queuePosition ?? 0));
  return (
    <MotionRegion className="ml-3 space-y-1" motionKey={[isLoading, isError && !data, live.length > 3]}>
      {isLoading ? <ContentSkeleton count={2} label="Đang tải tiến độ" className="px-2 py-3" /> : isError && !data ? <InlineError message="Bạn hãy thử tải lại tiến độ." onRetry={() => void refetch()} /> : null}
      <AnimatedRows className="mt-2" items={live.slice(0, 3)} keyOf={(book) => book.id}>{(book) => (
        <button
          key={book.id}
          type="button"
          onClick={() => { setExpanded(false); navigate(`/studio/${book.id}`); }}
          aria-current={pathname === `/studio/${book.id}` ? "page" : undefined}
          className={cn("sidebar-link flex w-full items-center gap-2.5 rounded-control p-2 text-left hover:bg-hover", pathname === `/studio/${book.id}` ? "bg-hover text-fg" : "text-fg-2")}
        >
          <BookCover title={book.title} part={book.series?.part} size="xs" image={book.cover} className="size-8 rounded-control" />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 truncate text-xs font-medium">
              <MotionRegion as="span" className="flex size-3 shrink-0 items-center justify-center">{book.queuePosition != null ? <Clock className="size-3" aria-label={`Đang chờ ${book.queuePosition}`} /> : book.paused || book.stopping ? (
                <Pause className="size-3 shrink-0 text-warning" aria-label={book.stopping ? "Đang dừng" : "Đang tạm dừng"} />
              ) : (
                <Vu className="h-2.5 gap-px text-accent [&>span]:w-[2px]" />
              )}</MotionRegion>
              <span className="truncate">{book.title}</span>
            </div>
            <div className="mt-1 flex items-center gap-2">
              <Progress value={book.progress.overall} tone={book.queuePosition != null ? "muted" : "accent"} size="xs" className="flex-1" label={`Tiến độ: ${book.title}`} />
              <MotionRegion as="span" motionKey={book.queuePosition ?? (book.starting ? "starting" : formatPercent(book.progress.overall))} className="tabular w-8 shrink-0 text-right text-[0.6875rem] text-fg-2">{book.queuePosition != null ? "Chờ" : book.starting ? "…" : formatPercent(book.progress.overall)}</MotionRegion>
            </div>
          </div>
        </button>
      )}</AnimatedRows>
      <MotionPresence open={live.length > 3}><Link to="/studio" className="sidebar-link flex min-h-8 items-center px-2 text-xs text-accent-text" onClick={() => setExpanded(false)}>Xem tất cả</Link></MotionPresence>
    </MotionRegion>
  );
}

/** App Windows đóng gói có bản mới: nhắc ở thanh bên, bấm mở Cài đặt (mục "Cập nhật" nằm trên cùng). */
export function UpdateNotice() {
  const { data: info } = useAppInfo();
  const navigate = useNavigate();
  const { setExpanded } = useNowPlaying();
  return <MotionPresence open={Boolean(info?.update && !info.remote)}>{info?.update && !info.remote && (
    <MotionRegion as="button" motionKey={info.update.version}
      type="button"
      onClick={() => {
        setExpanded(false);
        navigate("/settings/advanced");
      }}
      className="mb-2 flex w-full items-center gap-2.5 py-2.5 text-left hover:bg-hover"
    >
      <Download className="size-4 shrink-0 text-accent-text" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[0.8125rem] font-semibold">Có ABook {info.update.version}</span>
        <span className="block text-xs text-fg-2">Bấm để cập nhật</span>
      </span>
    </MotionRegion>
  )}</MotionPresence>;
}

const TITLES: [RegExp, string][] = [
  [/^\/$/, "Thư viện"],
  [/^\/book\//, "Sách"],
  [/^\/studio\/new/, "Tạo sách nói"],
  [/^\/studio\/.+/, "Dự án"],
  [/^\/studio$/, "Studio"],
  [/^\/settings/, "Cài đặt"],
];

export function DesktopSidebar({ listenOnly = false, collapsed = false }: { listenOnly?: boolean; collapsed?: boolean }) {
  return (
    <aside className="desktop-sidebar hidden w-[236px] shrink-0 flex-col border-r border-line bg-sunken px-3 pb-4 pt-5 md:flex" data-collapsed={collapsed}>
      <div data-sidebar-brand><Brand /></div>
      <nav aria-label="Điều hướng chính" className="mt-8 space-y-2">
        <NavItem to="/" icon={Library} ink={3} match={(path) => path === "/" || path.startsWith("/book/")}>
          Thư viện
        </NavItem>
        <MotionPresence open={!listenOnly}>
          <NavItem to="/studio" icon={Clapperboard} ink={1.03} match={(path) => path.startsWith("/studio")}>
            Studio
          </NavItem>
          <div data-sidebar-extra><Producing /></div>
        </MotionPresence>
      </nav>
      <div className="mt-auto pt-8">
        <div data-sidebar-extra><UpdateNotice /></div>
        <NavItem to="/settings" icon={Settings} ink={2.04} match={(path) => path.startsWith("/settings")}>
          Cài đặt
        </NavItem>
      </div>
    </aside>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const chrome = windowChrome();
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem("abook-sidebar-collapsed") === "1"; } catch { return false; }
  });
  const toggleSidebar = () => setCollapsed(value => !value);
  useEffect(() => {
    if (!chrome) return;
    try { localStorage.setItem("abook-sidebar-collapsed", collapsed ? "1" : "0"); } catch { /* Storage may be disabled. */ }
  }, [chrome, collapsed]);
  useEffect(() => {
    if (!chrome) return;
    const shortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === "b" && !(event.target instanceof Element && event.target.closest("input,textarea,[contenteditable='true']"))) {
        event.preventDefault(); setCollapsed(value => !value);
      }
    };
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, [chrome]);
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
  usePageFocus(main, pageFocusKey(pathname));
  // Kéo cửa sổ qua mốc bố cục (thanh bên <-> tab dưới, thanh phát đầy đủ <-> gọn): bố cục mới hiện dần thay vì nhảy một cú.
  const shell = useRef<HTMLDivElement | null>(null);
  useLayoutChangeFade(shell, `${phoneWidth}:${compactBar}`);

  // Tên chung theo đường dẫn; màn nào biết tên cụ thể (sách, chương, dự án) thì `usePageTitle` ghi đè sau đó.
  useLayoutEffect(() => {
    const title = TITLES.find(([pattern]) => pattern.test(pathname))?.[1];
    document.title = title ? `${title} · ${APP_TITLE}` : APP_TITLE;
  }, [pathname]);

  return (
    <div ref={shell} className={cn("flex h-full", chrome && "desktop-chrome-shell")}>
      <TitleBar toggle={<IconButton size="sm" label={collapsed ? "Mở rộng  (Ctrl+B)" : "Thu gọn  (Ctrl+B)"} icon={collapsed ? PanelLeftOpen : PanelLeftClose} onClick={toggleSidebar} />} />
      {/* Người dùng bàn phím: Tab đầu tiên tới đây, bỏ qua thanh bên để vào thẳng nội dung. Màn "Đang nghe" mở thì nội dung bên dưới bị khoá (inert) - không hiện. */}
      {!expanded && (
        <button
          type="button"
          onClick={() => main.current?.focus()}
          className="fixed left-[calc(env(safe-area-inset-left)+0.75rem)] top-[calc(env(safe-area-inset-top)+0.75rem)] z-[60] -translate-y-[200%] rounded-control bg-accent px-4 py-2 text-sm font-semibold text-accent-ink shadow-float focus:translate-y-0"
        >
          Tới nội dung
        </button>
      )}
      <ShortcutsHost remote={remote} />
      <DesktopSidebar listenOnly={listenOnly} collapsed={Boolean(chrome && collapsed)} />
      <div className="desktop-content relative flex min-w-0 flex-1 flex-col">
        <OfflineStrip />
        <PeerBar />
        <main ref={main} tabIndex={-1} className="page-motion min-h-0 flex-1 overflow-y-auto outline-none" inert={expanded}>
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
          <MotionRegion className={cn("flex min-w-0 overflow-hidden transition-[flex-grow] duration-(--motion-medium) [&>a]:flex-1", listenOnly ? "flex-[0]" : "flex-1")} motionKey={listenOnly}>
          {!listenOnly && (
            <TabItem to="/studio" icon={Clapperboard} match={(path) => path.startsWith("/studio")}>
              Studio
            </TabItem>
          )}
          </MotionRegion>
          <TabItem to="/settings" icon={Settings} match={(path) => path.startsWith("/settings")}>
            Cài đặt
          </TabItem>
        </nav>
        {/* Cùng nút "Phát trên thiết bị khác" như thanh dưới: cửa sổ hẹp dùng thanh gọn không có nó (soát UX 05-10). */}
        <NowPlaying mobile={phoneWidth} actions={remote ? undefined : <HandOffButton className="max-sm:size-11" />} edit={readerEditing(info)} />
      </div>
    </div>
  );
}

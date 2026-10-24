import { Clapperboard, Download, Library, Pause, Plus, Settings } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router";
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
import { Progress, Vu } from "@/shared/ui";
import { useAppInfo, useLibrary } from "@/studio/data";
import { usePrecastInvites } from "@/studio/PrecastReview";
import { PeerBar } from "./PeerBar";
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
      <div className="text-[0.9375rem] font-bold tracking-tight">ABook</div>
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

const NAV = "flex h-9 items-center gap-3 rounded-lg px-2.5 text-sm transition-[background-color,color,box-shadow] duration-(--motion-medium) ease-standard";
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
      <Icon className="glyph" />
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
        "flex min-w-0 flex-1 flex-col items-center gap-1 py-2 text-[0.6875rem] font-medium transition-colors duration-(--motion-medium) ease-standard",
        active ? "text-accent-text" : "text-fg-2",
      )}
    >
      {/* Tab vừa chọn: biểu tượng nhún nhẹ lên (transform), màu chuyển dần - không đổi màu tức thì. */}
      <Icon className={cn("motion-tab-icon size-5 transition-transform duration-(--motion-medium) ease-decelerate", active && "-translate-y-px scale-110")} />
      <span className="truncate">{children}</span>
    </NavLink>
  );
}

export function Producing() {
  const { pathname } = useLocation();
  const { data } = useLibrary({ live: pathname.startsWith("/studio") });
  const navigate = useNavigate();
  usePrecastInvites(data?.books);
  const live = (data?.books ?? []).filter((book) => book.running || book.starting);
  return (
    <MotionRegion className="mt-2 space-y-1">
      <AnimatedRows items={live} keyOf={(book) => book.id}>{(book) => (
        <button
          key={book.id}
          type="button"
          onClick={() => navigate(`/studio/${book.id}`)}
          className="flex w-full items-center gap-2.5 rounded-lg p-2 text-left hover:bg-hover"
        >
          <BookCover title={book.title} part={book.series?.part} size="xs" image={book.cover} className="size-8 rounded-md" />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 truncate text-xs font-medium">
              <MotionRegion as="span" className="grid size-3 shrink-0 place-items-center">{book.paused || book.stopping ? (
                <Pause className="size-3 shrink-0 text-warning" aria-label={book.stopping ? "Đang dừng" : "Đang tạm dừng"} />
              ) : (
                <Vu className="h-2 text-accent" />
              )}</MotionRegion>
              <span className="truncate">{book.title}</span>
            </div>
            <div className="mt-1 flex items-center gap-2">
              <Progress value={book.progress.overall} running={!book.paused && !book.stopping} size="xs" className="flex-1" label={`Tiến độ: ${book.title}`} />
              <MotionRegion as="span" motionKey={book.starting ? "starting" : formatPercent(book.progress.overall)} className="tabular text-[0.6875rem] text-fg-2">{book.starting ? "…" : formatPercent(book.progress.overall)}</MotionRegion>
            </div>
          </div>
        </button>
      )}</AnimatedRows>
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
      className="mb-2 flex w-full items-center gap-2.5 rounded-lg border border-line bg-panel p-2.5 text-left hover:bg-hover"
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
    <div ref={shell} className="flex h-full">
      {/* Người dùng bàn phím: Tab đầu tiên tới đây, bỏ qua thanh bên để vào thẳng nội dung. Màn "Đang nghe" mở thì nội dung bên dưới bị khoá (inert) - không hiện. */}
      {!expanded && (
        <button
          type="button"
          onClick={() => main.current?.focus()}
          className="fixed left-3 top-3 z-[60] -translate-y-[200%] rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-ink shadow-float focus:translate-y-0"
        >
          Tới nội dung
        </button>
      )}
      <ShortcutsHost remote={remote} />
      <aside className="hidden w-[236px] shrink-0 flex-col border-r border-line bg-sunken px-3 pb-4 pt-5 md:flex">
        <Brand />
        <nav aria-label="Điều hướng">
          <Section title="Nghe">
            <NavItem to="/" icon={Library} match={(path) => path === "/" || path.startsWith("/book/")}>
              Thư viện
            </NavItem>
          </Section>
          <MotionPresence open={!listenOnly}>
            <Section title="Studio">
              <NavItem to="/studio" icon={Clapperboard} match={(path) => path.startsWith("/studio") && path !== "/studio/new"}>
                Dự án
              </NavItem>
              <NavItem to="/studio/new" icon={Plus} match={(path) => path === "/studio/new"}>
                Tạo sách nói
              </NavItem>
              <Producing />
            </Section>
          </MotionPresence>
        </nav>
        <div className="mt-auto">
          <UpdateNotice />
          <NavItem to="/settings" icon={Settings} match={(path) => path.startsWith("/settings")}>
            Cài đặt
          </NavItem>
        </div>
      </aside>
      <div className="relative flex min-w-0 flex-1 flex-col">
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
          <MotionRegion className={cn("flex min-w-0 overflow-hidden transition-[flex-grow] duration-(--motion-medium) [&>a]:flex-1", listenOnly ? "flex-[0]" : "flex-[2]")} motionKey={listenOnly}>
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

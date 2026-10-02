import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Cast, Laptop, Loader2, MonitorSmartphone, MonitorSpeaker, Pause, Play, Smartphone, Speaker, Tv, X } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useClockReader } from "@/listen/clock";
import { usePlayer } from "@/listen/player";
import { Back15, Forward15 } from "@/listen/PlayerViews";
import { useListenBook, useSource } from "@/listen/source";
import { BookCover } from "@/shared/BookCover";
import { cn } from "@/shared/cn";
import type { CoverImage } from "@/shared/cover";
import { formatClock } from "@/shared/format";
import { IconButton, Tooltip } from "@/shared/ui";
import { api } from "@/studio/api";

// Điều khiển điện thoại đang phát từ máy tính (PLAYER_RESEARCH #12, kiểu Spotify Connect trong mạng nhà).
// Hợp đồng với server: webui/server.py (remote_view, remote_send) và webui/sync.py (Remote). Điện thoại báo trạng thái
// mỗi khi đổi và ít nhất 25 giây một lần; giữa hai lần báo, vị trí được nội suy theo đồng hồ và tốc độ phát.
// Loa / TV trong mạng nhà (DLNA, webui/cast.py - 01-10) là "máy" cùng danh sách: máy tính này phục vụ audio và hỏi
// thiết bị mỗi giây, nên chúng đi cùng thanh "Đang phát trên…" và nút "Phát trên…".

export interface RemotePhone {
  device: string;
  name: string;
  /** Máy gì - chỉ để chọn biểu tượng. */
  kind: "phone" | "computer" | "speaker" | "tv" | "media";
  /** Điện thoại báo lên máy tính này, máy đã ghép ở "Máy tính khác" (máy tính / điện thoại chia sẻ thư viện), hay loa /
   *  TV trong mạng nhà (phát mọi cuốn của máy này). */
  via: "remote" | "peer" | "cast";
  /** Loa / TV (`via` cast): "dlna" (UPnP) hay "gcast" (Chromecast, Google TV, loa Nest - webui/gcast.py). Cast chỉ phát 1x. */
  protocol?: "dlna" | "gcast";
  /** Cuốn ấy ở máy này (sách của chính máy này, hoặc cuốn ảo "Trên <máy kia>") - "Nghe trên máy này" mở đúng nó. */
  localBookId: string | null;
  bookId: string;
  bookTitle: string;
  chapterId: number | null;
  chapterTitle: string;
  position: number;
  duration: number;
  playing: boolean;
  buffering: boolean;
  rate: number;
  /** Sách đã tải xong về điện thoại (nghe được cả khi mất mạng). */
  books: string[];
  /** Điện thoại nghe thẳng được mọi cuốn của máy tính (stream play) - bản app cũ thì chỉ cuốn đã tải. */
  stream: boolean;
  acks: { id: string; ok: boolean; message: string }[];
  /** Số giây kể từ lần điện thoại báo cuối. */
  age: number;
  /** Máy tính có cuốn này trong thư viện. */
  known: boolean;
  cover: CoverImage | null;
}

interface RemoteView {
  phones: RemotePhone[];
  receivedAt: number;
}

type RemoteCommand =
  | { action: "play" | "pause" | "toggle" | "next" | "previous" | "stop" }
  | { action: "skip" | "seek"; seconds: number }
  | { action: "jump"; chapterId: number; seconds: number }
  | { action: "rate"; rate: number }
  | { action: "load"; bookId: string; chapterId: number; seconds: number };

type Ack = { id: string; ok: boolean; message: string };

const DEVICE_ICONS = { phone: Smartphone, computer: Laptop, speaker: Speaker, tv: Tv, media: MonitorSpeaker } as const;

export function DeviceIcon({ kind, className }: { kind: RemotePhone["kind"]; className?: string }) {
  const Icon = DEVICE_ICONS[kind] ?? Smartphone;
  return <Icon className={className} />;
}

const SKIP_SECONDS = 15;

export function useRemotePhones() {
  return useQuery({
    queryKey: ["remote"],
    queryFn: async (): Promise<RemoteView> => ({ ...(await api<{ phones: RemotePhone[] }>("/api/remote")), receivedAt: Date.now() }),
    // Loa / TV rảnh không đáng hỏi dồn: chỉ máy đang có sách (hay điện thoại, máy đã ghép đang nối) mới cần 1,5 giây.
    refetchInterval: (query) => (query.state.data?.phones.some((phone) => phone.via !== "cast" || phone.bookId) ? 1500 : 5000),
  });
}

/** Vị trí điện thoại lúc này: lần báo cuối cộng thời gian đã trôi (nếu đang phát). */
export function phonePosition(phone: RemotePhone, receivedAt: number, now = Date.now()): number {
  if (!phone.playing || phone.buffering) return phone.position;
  const elapsed = phone.age + Math.max(0, now - receivedAt) / 1000;
  const at = phone.position + elapsed * phone.rate;
  return phone.duration > 0 ? Math.min(at, phone.duration) : at;
}

export function useRemoteCommand() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ device, command }: { device: string; command: RemoteCommand }) =>
      api<{ id: string }>(`/api/remote/${device}`, { method: "POST", body: command }),
    onMutate: ({ device, command }) => {
      // Nút phải đổi ngay dưới tay người bấm; trạng thái thật về sau một lượt mạng (điện thoại báo lại sau ~0,3 giây).
      client.setQueryData<RemoteView>(["remote"], (view) => {
        if (!view) return view;
        const now = Date.now();
        return {
          receivedAt: now,
          phones: view.phones.map((phone) => {
            if (phone.device !== device) return phone;
            const here = phonePosition(phone, view.receivedAt, now);
            const base = { ...phone, age: 0, position: here };
            if (command.action === "toggle") return { ...base, playing: !phone.playing };
            if (command.action === "pause") return { ...base, playing: false };
            if (command.action === "play") return { ...base, playing: true };
            if (command.action === "skip") return { ...base, position: Math.max(0, here + command.seconds) };
            return base;
          }),
        };
      });
    },
    onSuccess: () => {
      window.setTimeout(() => void client.invalidateQueries({ queryKey: ["remote"] }), 700);
    },
    onError: (error: Error) => {
      toast.error(error.message);
      void client.invalidateQueries({ queryKey: ["remote"] });
    },
  });
}

/**
 * Lỗi điện thoại báo về cho một lệnh (chưa tải chương, chưa nghe cuốn nào...) - mỗi lỗi hiện một lần. Điện thoại gửi
 * lại kết quả lệnh trong 20 giây, nên những gì đã có ở lần tải đầu là của trang trước: không báo lại.
 */
function useFailedCommands(view: RemoteView | undefined) {
  const seen = useRef<Set<string> | null>(null);
  useEffect(() => {
    if (!view) return;
    const primed = seen.current !== null;
    seen.current ??= new Set();
    for (const phone of view.phones) {
      for (const ack of phone.acks) {
        if (!ack.id || seen.current.has(ack.id)) continue;
        seen.current.add(ack.id);
        if (primed && !ack.ok) toast.error(`${phone.name}: ${ack.message || "không làm được lệnh này"}`);
      }
    }
  }, [view]);
}

/** Thông báo nổi (góc dưới phải) đứng trên thanh phát; có thanh điện thoại thì phải đứng cao thêm từng ấy. */
function useToastsAbove(bars: number) {
  useLayoutEffect(() => {
    const root = document.documentElement;
    if (bars) root.style.setProperty("--toast-bottom", `${96 + 57 * bars}px`);
    else root.style.removeProperty("--toast-bottom");
    return () => {
      root.style.removeProperty("--toast-bottom");
    };
  }, [bars]);
}

function useTicking(active: boolean) {
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setTick((value) => value + 1), 500);
    return () => window.clearInterval(timer);
  }, [active]);
}

/** Tên giao thức cạnh tên thiết bị: chỉ Google Cast cần nói (DLNA là loa, TV thông thường). */
export function protocolLabel(phone: Pick<RemotePhone, "protocol">): string | null {
  return phone.protocol === "gcast" ? "Google Cast" : null;
}

function RemoteBar({ phone, receivedAt, onDismiss }: { phone: RemotePhone; receivedAt: number; onDismiss: () => void }) {
  const command = useRemoteCommand();
  const player = usePlayer();
  const source = useSource();
  const [moving, setMoving] = useState(false);
  useTicking(phone.playing);
  const at = phonePosition(phone, receivedAt);
  const share = phone.duration > 0 ? Math.min(100, (at / phone.duration) * 100) : 0;
  const send = (next: RemoteCommand) => command.mutate({ device: phone.device, command: next });

  // Chuyển sang nghe trên máy tính: dừng điện thoại, mở đúng chương, đúng giây ở đây.
  const listenHere = async () => {
    if (phone.chapterId === null) return;
    setMoving(true);
    try {
      const here = phonePosition(phone, receivedAt);
      // Google Cast: dừng hẳn để màn hình TV / loa về như cũ; DLNA và điện thoại chỉ cần tạm dừng.
      send({ action: phone.protocol === "gcast" ? "stop" : "pause" });
      const book = await source.book(phone.localBookId ?? phone.bookId);
      player.play(book, book.chapters ?? [], phone.chapterId, here);
      onDismiss();
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setMoving(false);
    }
  };

  return (
    <section aria-label={`Đang phát trên ${phone.name}`} className="relative z-20 shrink-0 border-t border-line bg-accent-soft/60">
      <div
        className="absolute inset-x-0 top-0 h-[2px] bg-accent transition-[width] duration-500 ease-linear"
        style={{ width: `${share}%` }}
        aria-hidden
      />
      <div className="flex h-14 items-center gap-3 px-4">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <BookCover title={phone.bookTitle} image={phone.cover} size="xs" className="size-9 shrink-0 rounded-md" />
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-accent-text">
              <DeviceIcon kind={phone.kind} className="size-3.5 shrink-0" />
              <span className="truncate">
                {phone.playing ? "Đang phát trên" : "Đang dừng trên"} {phone.name}
                {protocolLabel(phone) && <span className="font-normal text-fg-3"> · {protocolLabel(phone)}</span>}
              </span>
            </div>
            <div className="truncate text-sm">
              <span className="font-medium">{phone.chapterTitle}</span>
              <span className="text-fg-2"> · {phone.bookTitle}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <IconButton label={`Lùi ${SKIP_SECONDS} giây trên ${phone.name}`} icon={Back15} size="sm" onClick={() => send({ action: "skip", seconds: -SKIP_SECONDS })} />
          <button
            type="button"
            onClick={() => send({ action: "toggle" })}
            aria-label={phone.playing ? `Tạm dừng trên ${phone.name}` : `Phát tiếp trên ${phone.name}`}
            className="grid size-9 place-items-center rounded-full bg-fg text-bg shadow-card transition-transform hover:scale-105 active:scale-95"
          >
            {phone.buffering && phone.playing ? (
              <Loader2 className="size-4 animate-spin" />
            ) : phone.playing ? (
              <Pause className="size-4" fill="currentColor" strokeWidth={0} />
            ) : (
              <Play className="size-4 translate-x-[1px]" fill="currentColor" strokeWidth={0} />
            )}
          </button>
          <IconButton label={`Tới ${SKIP_SECONDS} giây trên ${phone.name}`} icon={Forward15} size="sm" onClick={() => send({ action: "skip", seconds: SKIP_SECONDS })} />
        </div>
        <div className="hidden w-28 text-right text-xs tabular text-fg-2 md:block">
          {formatClock(at)} / {formatClock(phone.duration)}
        </div>
        <div className="flex shrink-0 items-center justify-end gap-1 md:flex-1">
          {phone.known && (
            <Tooltip label={`Dừng ${phone.name}, nghe tiếp ở máy này đúng chỗ ấy`}>
              <button
                type="button"
                onClick={() => void listenHere()}
                disabled={moving}
                aria-label="Nghe trên máy này"
                className="inline-flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg px-2 text-xs font-medium text-fg hover:bg-hover disabled:opacity-50"
              >
                {moving ? <Loader2 className="size-4 animate-spin" /> : <Laptop className="size-4" />}
                <span className="hidden lg:inline">Nghe trên máy này</span>
              </button>
            </Tooltip>
          )}
          <IconButton label="Ẩn" icon={X} size="sm" onClick={onDismiss} />
        </div>
      </div>
    </section>
  );
}

/**
 * Thanh "Đang phát trên <điện thoại>" nằm trên thanh phát. Ẩn một thanh thì nó quay lại khi điện thoại sang cuốn khác,
 * hoặc phát lại sau một lần dừng (một buổi nghe mới) - còn dừng rồi để yên trên bàn thì không đáng chiếm chỗ. "Nghe trên
 * máy tính" cũng ẩn thanh và dừng điện thoại, nên chuyển ngược về điện thoại là thanh hiện lại.
 */
export function RemoteBars() {
  const { data } = useRemotePhones();
  const client = useQueryClient();
  const [dismissed, setDismissed] = useState<Record<string, { bookId: string; playing: boolean }>>({});
  useFailedCommands(data);
  // Loa / TV không giữ chỗ nghe - máy này lưu thay (webui/cast.py): đổi chương, phát / dừng thì thẻ "Đang nghe dở" và
  // trang sách đọc lại ngay, không đợi nhịp 30 giây của thư viện.
  const casting = (data?.phones ?? [])
    .filter((phone) => phone.via === "cast" && phone.bookId)
    .map((phone) => `${phone.device}|${phone.bookId}|${phone.chapterId}|${phone.playing}`)
    .join(",");
  useEffect(() => {
    if (!casting) return;
    const timer = window.setTimeout(() => {
      void client.invalidateQueries({ queryKey: ["listen", "library"] });
      void client.invalidateQueries({ queryKey: ["listen", "book"] });
    }, 600);
    return () => window.clearTimeout(timer);
  }, [casting, client]);
  useEffect(() => {
    const paused = (data?.phones ?? []).filter((phone) => !phone.playing && dismissed[phone.device]?.playing);
    if (!paused.length) return;
    setDismissed((current) => {
      const next = { ...current };
      for (const phone of paused) next[phone.device] = { ...next[phone.device], playing: false };
      return next;
    });
  }, [data, dismissed]);
  const hidden = (phone: RemotePhone) => {
    const mark = dismissed[phone.device];
    return !!mark && mark.bookId === phone.bookId && (mark.playing || !phone.playing);
  };
  const visible = (data?.phones ?? []).filter((phone) => phone.bookId && phone.chapterId !== null && !hidden(phone));
  useToastsAbove(visible.length);
  if (!data || !visible.length) return null;
  return (
    <>
      {visible.map((phone) => (
        <RemoteBar
          key={phone.device}
          phone={phone}
          receivedAt={data.receivedAt}
          onDismiss={() => setDismissed((current) => ({ ...current, [phone.device]: { bookId: phone.bookId, playing: phone.playing } }))}
        />
      ))}
    </>
  );
}

const MENU_ITEM = "flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[highlighted]:bg-hover";

/**
 * "Phát trên…" ở thanh phát máy tính: máy nào nghe được cuốn đang phát - điện thoại đang kết nối (nghe thẳng, hoặc đã
 * tải), máy đã ghép (chỉ sách của chính nó), loa / TV trong mạng nhà (mọi cuốn của máy này). Một máy: một nút; nhiều máy:
 * một danh sách, mở ra thì tìm lại loa / TV ngay (thiết bị vừa bật không phải đợi nhịp tìm 30 giây).
 */
export function HandOffButton({ className }: { className?: string }) {
  const { data } = useRemotePhones();
  const command = useRemoteCommand();
  const player = usePlayer();
  const readPosition = useClockReader();
  const track = player.track;
  const book = useListenBook(track?.bookId);
  // Máy đã ghép chỉ phát được sách của CHÍNH nó - cuốn ảo "Trên <máy ấy>" - host đổi mã cuốn sang mã của máy kia.
  const owner = typeof book.data?.remote === "object" && book.data?.remote ? book.data.remote.device : undefined;
  const targets = track
    ? (data?.phones ?? []).filter((candidate) =>
        candidate.via === "cast" ||
        (candidate.via === "peer" ? candidate.device === owner : candidate.stream || candidate.books.includes(track.bookId)))
    : [];
  if (!targets.length || !track) return null;
  // Không cần thông báo "đã chuyển": thanh "Đang phát trên <máy>" hiện ra sau một lượt mạng chính là lời xác nhận. Loa /
  // TV mất vài giây (tải chương, đợi chạy rồi mới tua tới đúng chỗ) nên có dòng "Đang mở…" tới lúc ấy.
  const handOff = (target: RemotePhone) => {
    const seconds = readPosition().time;
    const wasPlaying = player.playing;
    player.pause();
    const waiting = target.via === "cast" ? toast.loading(`Đang mở trên ${target.name}…`) : undefined;
    command.mutate(
      { device: target.device, command: { action: "load", bookId: track.bookId, chapterId: track.chapterId, seconds } },
      {
        // Máy kia đã nhận thì đóng hẳn trình phát ở đây (nó lưu chỗ trước khi đóng). Chỉ dừng thì lúc rời trang nó lưu lại
        // chỗ cũ đè lên chỗ máy kia đã nghe tới - gặp 01-10 với loa giả lập: loa dừng ở 0:56, tải lại trang thành 0:19.
        onSuccess: () => player.close(),
        // Loa / TV từ chối (tắt nguồn, bị chiếm...): lời báo lỗi hiện từ useRemoteCommand; nghe tiếp ở máy này thay vì để im lặng.
        onError: () => {
          if (wasPlaying) player.resume();
        },
        onSettled: () => waiting !== undefined && toast.dismiss(waiting),
      },
    );
  };
  if (targets.length === 1) {
    const [only] = targets;
    return (
      <IconButton
        label={`Phát trên ${only.name}${protocolLabel(only) ? ` (${protocolLabel(only)})` : ""}`}
        icon={only.via === "cast" ? Cast : MonitorSmartphone}
        size="sm"
        className={cn(className)}
        onClick={() => handOff(only)}
      />
    );
  }
  return (
    <DropdownMenu.Root
      onOpenChange={(open) => {
        if (open) void api("/api/cast/scan", { method: "POST" }).catch(() => undefined);
      }}
    >
      <Tooltip label="Phát trên thiết bị khác">
        <DropdownMenu.Trigger
          aria-label="Phát trên thiết bị khác"
          className={cn(
            "inline-flex size-8 shrink-0 items-center justify-center rounded-lg text-fg-2 transition-colors hover:bg-hover hover:text-fg data-[state=open]:bg-hover data-[state=open]:text-fg",
            className,
          )}
        >
          <Cast className="size-[18px]" strokeWidth={2} />
        </DropdownMenu.Trigger>
      </Tooltip>
      <DropdownMenu.Portal>
        <DropdownMenu.Content side="top" align="end" sideOffset={8} collisionPadding={12} className="z-50 min-w-56 max-w-80 rounded-xl border border-line bg-panel p-1.5 shadow-float">
          <DropdownMenu.Label className="px-2 pb-1 pt-0.5 text-xs font-medium text-fg-3">Phát trên</DropdownMenu.Label>
          {targets.map((target) => (
            <DropdownMenu.Item key={target.device} onSelect={() => handOff(target)} className={MENU_ITEM}>
              <DeviceIcon kind={target.kind} className="size-4 shrink-0 text-fg-2" />
              <span className="min-w-0 flex-1 truncate">{target.name}</span>
              {protocolLabel(target) && <span className="shrink-0 text-xs text-fg-3">{protocolLabel(target)}</span>}
              {target.bookId && target.playing && <span className="shrink-0 text-xs text-fg-3">đang phát</span>}
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

/**
 * Trình phát của CHÍNH máy tính này cho máy đã ghép (mạng trạm bước 4): báo trạng thái lên host - host giữ cho
 * GET /sync/v1/player - và nhận lệnh bằng "hỏi dài" 25 giây, đúng cách điện thoại báo máy tính (Remote.kt). Kết quả lệnh
 * gửi lại 20 giây trong `acks`. Đổi bài / phát / dừng / tốc độ thì báo ngay (gộp 300 ms); tua xa (lệch quá 3 giây so với
 * đồng hồ bên kia nội suy) cũng báo. Đồng bộ tắt: host trả `idle`, hỏi lại sau 20 giây.
 */
export function ThisPlayerReporter() {
  const player = usePlayer();
  const readClock = useClockReader();
  const source = useSource();
  const latest = useRef({ player, readClock, source });
  latest.current = { player, readClock, source };
  const acks = useRef<{ at: number; ack: Ack }[]>([]);
  const reported = useRef({ at: 0, position: 0, playing: false, rate: 1 });
  const reportRef = useRef<(wait: number) => Promise<unknown>>(async () => undefined);
  // Mã lệnh đã làm (host giao lại lệnh chưa thấy kết quả - mỗi mã chỉ làm một lần).
  const handled = useRef(new Map<string, number>());

  useEffect(() => {
    let alive = true;
    const snapshot = () => {
      const { player: now, readClock: clock } = latest.current;
      const track = now.track;
      const { time, duration } = clock();
      reported.current = { at: Date.now(), position: time, playing: now.playing, rate: now.rate };
      if (!track) return {};
      return {
        bookId: track.bookId, bookTitle: track.bookTitle, chapterId: track.chapterId, chapterTitle: track.chapterTitle,
        position: time, duration, playing: now.playing, buffering: now.buffering, rate: now.rate,
      };
    };
    const post = (wait: number) => {
      const now = Date.now();
      acks.current = acks.current.filter((entry) => now - entry.at < 20_000);
      return api<{ commands: (RemoteCommand & { id: string })[]; idle?: boolean }>("/api/player/report", {
        method: "POST",
        body: { state: snapshot(), acks: acks.current.map((entry) => entry.ack), wait },
      });
    };
    // MỌI lần báo đều có thể mang lệnh về (host giao lệnh cho lần báo nào tới trước) - lần báo ngay (wait 0) cũng phải
    // làm lệnh nó nhận, không thì lệnh ấy mất.
    const report = async (wait: number) => {
      const reply = await post(wait);
      await handle(reply.commands ?? []);
      return reply;
    };
    reportRef.current = report;
    const apply = async (command: RemoteCommand): Promise<string | null> => {
      const { player: now, source: books } = latest.current;
      const loaded = !!now.track;
      switch (command.action) {
        case "play":
        case "toggle":
          if (!loaded) return "Máy tính chưa mở cuốn nào - chọn sách trên máy tính trước";
          if (command.action === "toggle") now.toggle();
          else now.resume();
          return null;
        case "pause":
          now.pause();
          return null;
        case "skip":
          if (loaded) now.skip(command.seconds);
          return null;
        case "seek":
          if (loaded) now.seek(command.seconds);
          return null;
        case "next":
          if (loaded) now.next();
          return null;
        case "previous":
          if (loaded) now.previous();
          return null;
        case "jump":
          if (loaded) now.jumpTo(command.chapterId, command.seconds);
          return null;
        case "rate":
          now.setRate(command.rate);
          return null;
        case "load":
          try {
            const book = await books.book(command.bookId);
            now.play(book, book.chapters ?? [], command.chapterId, command.seconds);
            return null;
          } catch {
            return "Máy tính không có cuốn này";
          }
        default:
          return "Máy tính chưa hiểu lệnh này - cập nhật ABook trên máy tính";
      }
    };
    const handle = async (commands: (RemoteCommand & { id: string })[]) => {
      const now = Date.now();
      for (const [id, at] of handled.current) if (now - at > 60_000) handled.current.delete(id);
      const fresh = commands.filter((command) => !handled.current.has(command.id));
      for (const command of fresh) {
        handled.current.set(command.id, Date.now());
        const problem = await apply(command);
        acks.current.push({ at: Date.now(), ack: { id: command.id, ok: problem === null, message: problem ?? "" } });
      }
      if (fresh.length) window.setTimeout(() => void report(0).catch(() => undefined), 400);
    };
    const pause = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));
    void (async () => {
      let backoff = 3000;
      while (alive) {
        try {
          const reply = await report(25);
          backoff = 3000;
          if (reply.idle) {
            await pause(20_000);
            continue;
          }
        } catch {
          // Host đóng lại (cập nhật, thoát): thử lại thưa dần.
          await pause(backoff);
          backoff = Math.min(backoff * 2, 60_000);
        }
      }
    })();
    const drift = window.setInterval(() => {
      const last = reported.current;
      const { player: now, readClock: clock } = latest.current;
      if (!now.track) return;
      const expected = last.position + (last.playing ? ((Date.now() - last.at) / 1000) * last.rate : 0);
      if (Math.abs(clock().time - expected) > 3) void report(0).catch(() => undefined);
    }, 2000);
    return () => {
      alive = false;
      window.clearInterval(drift);
    };
  }, []);

  const key = `${player.track?.bookId}|${player.track?.chapterId}|${player.playing}|${player.rate}`;
  useEffect(() => {
    const timer = window.setTimeout(() => void reportRef.current(0).catch(() => undefined), 300);
    return () => window.clearTimeout(timer);
  }, [key]);
  return null;
}

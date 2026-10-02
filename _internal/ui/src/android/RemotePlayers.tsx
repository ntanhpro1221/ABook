import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Cast, Laptop, Loader2, MonitorSpeaker, Pause, Play, Smartphone, Speaker, Tv, X } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useClockReader } from "@/listen/clock";
import { usePlayer } from "@/listen/player";
import { Back15, Forward15 } from "@/listen/PlayerViews";
import { useSource } from "@/listen/source";
import { formatClock } from "@/shared/format";
import { IconButton } from "@/shared/ui";
import { EbookLibrary, type RemotePlayer, type RemotePlayerCommand } from "./plugins";

// Điện thoại xem và điều khiển trình phát ở máy khác (mạng trạm bước 4): máy tính chính và mọi thiết bị ghép trả trình
// phát ở /sync/v1/player (RemotePlayers.kt). Chỉ hỏi khi app đang hiện; có máy đang phát thì 2 giây một lần, không thì 8
// giây. Giữa hai lần hỏi, vị trí nội suy theo đồng hồ và tốc độ như máy tính làm với điện thoại. Loa / TV máy tính chính
// thấy trong mạng nhà (`via` cast, 01-10) đứng cùng danh sách: điều khiển qua máy tính, máy tính phục vụ audio.

const KIND_ICONS = { computer: Laptop, phone: Smartphone, speaker: Speaker, tv: Tv, media: MonitorSpeaker } as const;

function KindIcon({ kind, className }: { kind: RemotePlayer["kind"]; className?: string }) {
  const Icon = KIND_ICONS[kind] ?? Smartphone;
  return <Icon className={className} />;
}

/** Cạnh tên thiết bị: chỉ Google Cast cần nói (DLNA là loa, TV thông thường). */
function protocolLabel(remote: RemotePlayer): string | null {
  return remote.protocol === "gcast" ? "Google Cast" : null;
}

interface PlayersView {
  players: RemotePlayer[];
  receivedAt: number;
}

function useVisible(): boolean {
  const [visible, setVisible] = useState(document.visibilityState === "visible");
  useEffect(() => {
    const follow = () => setVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", follow);
    return () => document.removeEventListener("visibilitychange", follow);
  }, []);
  return visible;
}

export function useRemotePlayers() {
  const visible = useVisible();
  return useQuery({
    queryKey: ["remote-players"],
    queryFn: async (): Promise<PlayersView> => ({ ...(await EbookLibrary.remotePlayers()), receivedAt: Date.now() }),
    enabled: visible,
    refetchInterval: (query) => (query.state.data?.players.some((player) => player.state?.playing) ? 2000 : 8000),
  });
}

function positionOf(player: RemotePlayer, receivedAt: number, now = Date.now()): number {
  const state = player.state ?? {};
  const position = state.position ?? 0;
  if (!state.playing || state.buffering) return position;
  const at = position + (player.age + Math.max(0, now - receivedAt) / 1000) * (state.rate ?? 1);
  return state.duration ? Math.min(at, state.duration) : at;
}

function useRemotePlayerCommand() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ device, command }: { device: string; command: RemotePlayerCommand }) =>
      EbookLibrary.remoteCommand({ device, command }),
    onMutate: ({ device, command }) => {
      client.setQueryData<PlayersView>(["remote-players"], (view) => {
        if (!view) return view;
        const now = Date.now();
        return {
          receivedAt: now,
          players: view.players.map((player) => {
            if (player.device !== device || !player.state) return player;
            const here = positionOf(player, view.receivedAt, now);
            const state = { ...player.state, position: here };
            if (command.action === "toggle") state.playing = !player.state.playing;
            if (command.action === "pause") state.playing = false;
            if (command.action === "play") state.playing = true;
            if (command.action === "skip") state.position = Math.max(0, here + command.seconds);
            return { ...player, age: 0, state };
          }),
        };
      });
    },
    onSuccess: () => window.setTimeout(() => void client.invalidateQueries({ queryKey: ["remote-players"] }), 800),
    onError: (error: Error) => {
      toast.error(error.message);
      void client.invalidateQueries({ queryKey: ["remote-players"] });
    },
  });
}

function useTicking(active: boolean) {
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setTick((value) => value + 1), 500);
    return () => window.clearInterval(timer);
  }, [active]);
}

function RemotePlayerBar({ remote, receivedAt, onDismiss }: { remote: RemotePlayer; receivedAt: number; onDismiss: () => void }) {
  const command = useRemotePlayerCommand();
  const player = usePlayer();
  const source = useSource();
  const [moving, setMoving] = useState(false);
  const state = remote.state ?? {};
  useTicking(!!state.playing);
  const at = positionOf(remote, receivedAt);
  const share = state.duration ? Math.min(100, (at / state.duration) * 100) : 0;
  const send = (next: RemotePlayerCommand) => command.mutate({ device: remote.device, command: next });

  // Nghe tiếp ở điện thoại: dừng máy kia, mở đúng cuốn (nghe thẳng nếu chưa tải), đúng chương, đúng giây.
  const listenHere = async () => {
    if (state.chapterId == null) return;
    setMoving(true);
    try {
      const here = positionOf(remote, receivedAt);
      send({ action: "pause" });
      const book = await source.book(remote.localBookId);
      player.play(book, book.chapters ?? [], state.chapterId, here);
      onDismiss();
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setMoving(false);
    }
  };

  return (
    <section aria-label={`Đang phát trên ${remote.name}`} className="relative shrink-0 border-t border-line bg-accent-soft/60">
      <div className="absolute inset-x-0 top-0 h-[2px] bg-accent transition-[width] duration-500 ease-linear" style={{ width: `${share}%` }} aria-hidden />
      <div className="flex items-center gap-2 px-3 py-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-accent-text">
            <KindIcon kind={remote.kind} className="size-3.5 shrink-0" />
            <span className="truncate">
              {state.playing ? "Đang phát trên" : "Đang dừng trên"} {remote.name}
              {protocolLabel(remote) && <span className="font-normal text-fg-3"> · {protocolLabel(remote)}</span>}
            </span>
          </div>
          <div className="truncate text-sm">
            <span className="font-medium">{state.chapterTitle}</span>
            <span className="text-fg-2"> · {formatClock(at)}</span>
          </div>
        </div>
        <button type="button" aria-label={`Lùi 15 giây trên ${remote.name}`} onClick={() => send({ action: "skip", seconds: -15 })}
          className="grid size-10 place-items-center rounded-full text-fg active:bg-hover">
          <Back15 className="size-5" />
        </button>
        <button
          type="button"
          onClick={() => send({ action: "toggle" })}
          aria-label={state.playing ? `Tạm dừng trên ${remote.name}` : `Phát tiếp trên ${remote.name}`}
          className="grid size-10 place-items-center rounded-full bg-fg text-bg active:scale-95"
        >
          {state.buffering && state.playing ? (
            <Loader2 className="size-4 animate-spin" />
          ) : state.playing ? (
            <Pause className="size-4" fill="currentColor" strokeWidth={0} />
          ) : (
            <Play className="size-4 translate-x-[1px]" fill="currentColor" strokeWidth={0} />
          )}
        </button>
        <button type="button" aria-label={`Tới 15 giây trên ${remote.name}`} onClick={() => send({ action: "skip", seconds: 15 })}
          className="grid size-10 place-items-center rounded-full text-fg active:bg-hover">
          <Forward15 className="size-5" />
        </button>
        {remote.known && (
          <button type="button" onClick={() => void listenHere()} disabled={moving}
            className="h-9 shrink-0 rounded-lg px-2 text-xs font-medium text-fg active:bg-hover disabled:opacity-50">
            {moving ? <Loader2 className="size-4 animate-spin" /> : "Nghe ở đây"}
          </button>
        )}
        <button type="button" aria-label="Ẩn" onClick={onDismiss} className="grid size-9 place-items-center rounded-full text-fg-2 active:bg-hover">
          <X className="size-4" />
        </button>
      </div>
    </section>
  );
}

/**
 * "Đang phát trên <máy>" ngay trên thanh phát của điện thoại. Ẩn một thanh thì nó quay lại khi máy ấy sang cuốn khác hoặc
 * phát lại sau một lần dừng - như thanh điện thoại trên máy tính (desktop/RemotePhone.tsx).
 */
export function RemotePlayerBars() {
  const { data } = useRemotePlayers();
  const [dismissed, setDismissed] = useState<Record<string, { bookId: string; playing: boolean }>>({});
  const seen = useState(() => new Set<string>())[0];
  useEffect(() => {
    // Lệnh máy kia không làm được: báo đúng một lần.
    for (const remote of data?.players ?? []) {
      for (const ack of remote.acks ?? []) {
        if (!ack.id || seen.has(ack.id)) continue;
        seen.add(ack.id);
        if (!ack.ok) toast.error(`${remote.name}: ${ack.message || "không làm được lệnh này"}`);
      }
    }
  }, [data, seen]);
  const visible = (data?.players ?? []).filter((remote) => {
    const state = remote.state;
    if (!state?.bookId || state.chapterId == null) return false;
    const mark = dismissed[remote.device];
    return !(mark && mark.bookId === state.bookId && (mark.playing || !state.playing));
  });
  if (!data || !visible.length) return null;
  return (
    <>
      {visible.map((remote) => (
        <RemotePlayerBar
          key={remote.device}
          remote={remote}
          receivedAt={data.receivedAt}
          onDismiss={() =>
            setDismissed((current) => ({ ...current, [remote.device]: { bookId: remote.state?.bookId ?? "", playing: !!remote.state?.playing } }))
          }
        />
      ))}
    </>
  );
}

/**
 * "Phát trên <máy>" ở màn đang nghe của điện thoại: chuyển cuốn đang nghe sang máy giữ nó - máy tính chính (sách của nó,
 * đã tải hay nghe thẳng) hoặc thiết bị ghép (sách `p<key>_...` của thiết bị ấy) - hay sang loa / TV máy tính chính thấy
 * (sách của máy tính), đúng chương, đúng giây, rồi dừng ở điện thoại. Một nơi: một nút; nhiều nơi: một menu. Thanh "Đang
 * phát trên <máy>" hiện lên sau một lượt mạng là lời xác nhận.
 */
export function PhoneHandOffButton() {
  const { data } = useRemotePlayers();
  const player = usePlayer();
  const readClock = useClockReader();
  const client = useQueryClient();
  const track = player.track;
  if (!track || !data) return null;
  const peer = /^p([0-9a-f]{8})_/.exec(track.bookId)?.[1];
  const owner = data.players.find((remote) => remote.device === (peer ?? "main"));
  // Loa / TV: điện thoại tự chọn đường (RemotePlayers.kt) - sách đã có trên điện thoại thì phát thẳng ("dlna:"), sách
  // nghe thẳng từ máy tính thì nhờ máy tính ("cast:"); không đường nào được thì lời báo nói lý do.
  const speakers = data.players.filter((remote) => remote.via === "cast");
  const targets = [...(owner ? [owner] : []), ...speakers];
  if (!targets.length) return null;
  const handOff = async (target: RemotePlayer) => {
    const seconds = readClock().time;
    // Loa / TV mất vài giây (máy tính đưa chương, TV tải rồi mới tua tới đúng chỗ): có dòng "Đang mở…" tới lúc ấy.
    const waiting = target.via === "cast" ? toast.loading(`Đang mở trên ${target.name}…`) : undefined;
    try {
      await EbookLibrary.remoteCommand({
        device: target.device,
        command: { action: "load", bookId: track.bookId, chapterId: track.chapterId, seconds },
      });
      player.pause();
      window.setTimeout(() => void client.invalidateQueries({ queryKey: ["remote-players"] }), 800);
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      if (waiting !== undefined) toast.dismiss(waiting);
    }
  };
  if (targets.length === 1) {
    const [only] = targets;
    return (
      <IconButton label={`Phát trên ${only.name}${protocolLabel(only) ? ` (${protocolLabel(only)})` : ""}`} icon={only.via === "cast" ? Cast : KIND_ICONS[only.kind] ?? Smartphone}
        size="sm" onClick={() => void handOff(only)} />
    );
  }
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger
        aria-label="Phát trên thiết bị khác"
        className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg text-fg-2 active:bg-hover data-[state=open]:bg-hover data-[state=open]:text-fg"
      >
        <Cast className="size-[18px]" strokeWidth={2} />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content side="top" align="end" sideOffset={8} collisionPadding={12} className="z-50 min-w-56 max-w-[calc(100vw-24px)] rounded-xl border border-line bg-panel p-1.5 shadow-float">
          <DropdownMenu.Label className="px-2 pb-1 pt-0.5 text-xs font-medium text-fg-3">Phát trên</DropdownMenu.Label>
          {targets.map((target) => (
            <DropdownMenu.Item
              key={target.device}
              onSelect={() => void handOff(target)}
              className="flex h-11 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[highlighted]:bg-hover"
            >
              <KindIcon kind={target.kind} className="size-4 shrink-0 text-fg-2" />
              <span className="min-w-0 flex-1 truncate">{target.name}</span>
              {protocolLabel(target) && <span className="shrink-0 text-xs text-fg-3">{protocolLabel(target)}</span>}
              {target.state?.bookId && target.state.playing && <span className="shrink-0 text-xs text-fg-3">đang phát</span>}
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

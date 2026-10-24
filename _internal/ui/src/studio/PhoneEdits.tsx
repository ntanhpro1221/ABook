import { MoreInfo } from "@/shared/SettingsNav";
import { MotionRegion } from "@/shared/MotionRegion";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Link2, RotateCcw, Smartphone, X } from "lucide-react";
import { useState } from "react";
import { toast } from "@/shared/toast";
import { formatWhen } from "@/shared/format";
import { Button, Dialog, IconButton } from "@/shared/ui";
import { KIND_ICON } from "./ApplyChanges";
import { api } from "./api";
import { UNDO_MS, useWhenApplied } from "./decisions";
import { pollDelay, retryUnlessGone } from "./polling";

// Hộp thư thay đổi từ điện thoại (docs/EDITING.md, P2b; webui/edits_inbox.py). Điện thoại đã ghép gửi phần sửa của cuốn về máy tính:
// tên sách, bìa, tên nhân vật, tên chương, nhạc áp NGAY (không qua đây); còn những việc cần Studio - đổi giọng, cách đọc, người
// nói, thu lại - từ thiết bị chưa được điều khiển sản xuất từ xa thì nằm ở đây chờ chủ máy "Áp dụng" hay "Bỏ qua" từng việc, từng
// thiết bị. KHÔNG BAO GIỜ tự áp. "Áp dụng" chỉ biến việc thành yêu cầu trong "Áp dụng N thay đổi" - chưa thu lại gì.

interface InboxItem {
  id: string;
  kind: keyof typeof KIND_ICON | "alias";
  label: string;
  chapter?: string;
  /** Số câu cùng một lần bấm (gán người nói cả nhóm, thu lại cả chương). */
  lines: number;
  /** Máy này đã đổi khác SAU lúc máy kia sửa: “Áp dụng tất cả” không lấy việc này - chủ máy chọn từng việc. */
  conflict?: string;
}

interface InboxDevice {
  id: string;
  name: string;
  at: number;
  items: InboxItem[];
}

interface RecentPush {
  at: number;
  device: string;
  name: string;
  applied: number;
  skipped: number;
  requests: number;
  waiting: number;
  conflicts: string[];
}

export interface EditsInbox {
  devices: InboxDevice[];
  waiting: number;
  recent: RecentPush[];
  /** Khay “đã bỏ qua”: việc bạn bỏ qua nằm lại đây để khôi phục (điện thoại đã trừ chúng khỏi máy nó nên bỏ nhầm là mất). */
  skipped: InboxDevice[];
}

type Verb = "apply" | "skip" | "restore";
interface Reply {
  requests?: number;
  skipped?: number;
  removed?: number;
  restored?: number;
  held?: number;
  dropped?: { label: string }[];
}

function useInbox(bookId: string, enabled = true) {
  return useQuery({
    queryKey: ["edits-inbox", bookId],
    queryFn: () => api<EditsInbox>(`/api/books/${bookId}/edits-inbox`),
    enabled: enabled && Boolean(bookId),
    retry: retryUnlessGone,
    refetchInterval: (query) => pollDelay(15_000, query.state),
  });
}

/** Số việc từ điện thoại đang chờ chủ máy duyệt (cho số trên tab "Việc cần duyệt"). */
export function useInboxCount(bookId: string, enabled = true) {
  const { data } = useInbox(bookId, enabled);
  return data?.waiting ?? 0;
}

/** Một dòng kể lần gửi gần đây: máy tính đã làm gì với phần sửa điện thoại gửi về. */
export function describePush(push: RecentPush): string {
  const parts: string[] = [];
  if (push.applied) parts.push(`${push.applied} thay đổi đã áp`);
  if (push.requests) parts.push(`${push.requests} việc đã thành yêu cầu`);
  if (push.waiting) parts.push(`${push.waiting} việc đang chờ duyệt`);
  if (push.skipped) parts.push(`${push.skipped} không còn chỗ trong sách (bỏ qua)`);
  return `${push.name} · ${formatWhen(push.at)}: ${parts.join(", ") || "không có gì mới"}`;
}

/** Lời dưới toast "Áp dụng" một việc từ hộp thư: điều đã xảy ra, rồi lúc nào máy làm (`when` = `useWhenApplied`: sách đang chạy thì máy tự áp từ
 *  chương sau - không có nút "Áp dụng thay đổi" nào để bấm; soát a83 B12). */
export function applyNote({ skipped, held, dropped = [] }: { skipped: number; held: number; dropped?: string[] }, when: string): string {
  // Nói rõ việc nào không áp được (câu đã đổi chữ, người chưa có giọng...), không chỉ một con số.
  const which = dropped.length ? `: ${dropped.slice(0, 3).join("; ")}${dropped.length > 3 ? `; và ${dropped.length - 3} việc nữa` : ""}` : "";
  return [
    skipped ? `${skipped} việc không còn khớp với sách nên bị bỏ qua${which}.` : `Chưa thu lại gì. ${when}`,
    held ? `${held} việc máy này đã đổi khác sau đó vẫn chờ bạn chọn từng việc.` : "",
  ]
    .filter(Boolean)
    .join(" ");
}

export function PhoneEdits({ bookId }: { bookId: string }) {
  const client = useQueryClient();
  const when = useWhenApplied(bookId);
  const { data } = useInbox(bookId);
  const [busy, setBusy] = useState<string | null>(null);
  const [confirmSkipAll, setConfirmSkipAll] = useState<InboxDevice | null>(null);
  if (!data || (!data.devices.length && !data.recent.length && !data.skipped?.length)) return <MotionRegion />;

  const decide = async (verb: Verb, device: InboxDevice, item?: InboxItem) => {
    setBusy(`${device.id}:${item?.id ?? "all"}`);
    try {
      const reply = await api<Reply>(`/api/books/${bookId}/edits-inbox/${verb}`, {
        method: "POST",
        body: { device: device.id, ...(item ? { items: [item.id] } : {}) },
      });
      if (verb === "apply") {
        const made = reply.requests ?? 0;
        const skipped = reply.skipped ?? 0;
        const held = reply.held ?? 0;
        toast.success(made ? `Đã ghi ${made} việc vào “Áp dụng thay đổi”` : "Không có việc nào ghi được", {
          description: applyNote({ skipped, held, dropped: (reply.dropped ?? []).map((row) => row.label) }, when),
        });
      } else if (verb === "restore") {
        toast.success("Đã khôi phục", { description: "Việc này chờ bạn quyết lại ở trên." });
      } else {
        // Bỏ qua không mất hẳn: việc nằm ở khay “Đã bỏ qua” và bấm Khôi phục ngay trên thông báo được.
        toast("Đã bỏ qua", {
          description: "Không có gì thay đổi trong sách. Bạn khôi phục lại được ở mục “Đã bỏ qua” bên dưới.",
          duration: UNDO_MS,
          action: { label: "Khôi phục", onClick: () => void decide("restore", device, item) },
        });
      }
      await client.invalidateQueries();
    } catch (error) {
      toast.error("Chưa làm được", { description: (error as Error).message });
    } finally {
      setBusy(null);
    }
  };

  return (
    <MotionRegion as="section" aria-label="Yêu cầu thiết bị" className="mb-5 rounded-2xl border border-line bg-panel p-4">
      <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
        <Smartphone className="size-4 text-fg-3" /> Yêu cầu thiết bị{data.waiting ? ` (${data.waiting} việc chờ duyệt)` : ""}
      </h2>
      {data.devices.length > 0 && (
        <div className="mt-1 text-sm text-fg-2">
          <p>Áp dụng để đưa vào hàng chờ; bỏ qua vẫn khôi phục được.</p>
          <MoreInfo label="Đã áp dụng">Tên sách, bìa, tên nhân vật, tên chương và nhạc nền đã áp ngay. Yêu cầu trong hàng chờ chưa thu lại; khôi phục việc bỏ qua ở “Đã bỏ qua”.</MoreInfo>
        </div>
      )}
      {data.devices.map((device) => (
        <div key={device.id} className="mt-3">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="min-w-0 flex-1 truncate text-sm font-medium">
              {device.name} <span className="font-normal text-fg-3">· gửi {formatWhen(device.at)}</span>
            </h3>
            <Button size="sm" variant="primary" icon={Check} loading={busy === `${device.id}:all`} disabled={busy !== null} onClick={() => void decide("apply", device)}>
              Áp dụng tất cả
            </Button>
            <Button size="sm" variant="ghost" icon={X} disabled={busy !== null} onClick={() => setConfirmSkipAll(device)}>
              Bỏ qua tất cả
            </Button>
          </div>
          <ul className="mt-2 divide-y divide-line overflow-hidden rounded-xl border border-line">
            {device.items.map((item) => {
              const Icon = item.kind === "alias" ? Link2 : (KIND_ICON[item.kind] ?? Check);
              return (
                <li key={item.id} className="flex items-start gap-3 px-3 py-2 text-sm">
                  <Icon className="mt-0.5 size-4 shrink-0 text-fg-3" />
                  <span className="min-w-0 flex-1 text-pretty">
                    {item.label}
                    {item.chapter && <span className="text-fg-3"> · {item.chapter}</span>}
                    {item.conflict && <span className="mt-0.5 block text-xs text-warning">{item.conflict}</span>}
                  </span>
                  <IconButton size="sm" icon={Check} label="Áp dụng việc này" className="-my-1.5" disabled={busy !== null} onClick={() => void decide("apply", device, item)} />
                  <IconButton size="sm" icon={X} label="Bỏ qua việc này" className="-my-1.5 -mr-1.5" disabled={busy !== null} onClick={() => void decide("skip", device, item)} />
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      {(data.skipped?.length ?? 0) > 0 && (
        <details className="mt-3 text-sm text-fg-2">
          <summary className="cursor-pointer select-none">Đã bỏ qua ({data.skipped.reduce((sum, device) => sum + device.items.length, 0)})</summary>
          {data.skipped.map((device) => (
            <div key={device.id} className="mt-2">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="min-w-0 flex-1 truncate text-sm font-medium text-fg">{device.name}</h3>
                <Button size="sm" variant="ghost" icon={RotateCcw} disabled={busy !== null} onClick={() => void decide("restore", device)}>
                  Khôi phục tất cả
                </Button>
              </div>
              <ul className="mt-1 divide-y divide-line overflow-hidden rounded-xl border border-line">
                {device.items.map((item) => (
                  <li key={item.id} className="flex items-start gap-3 px-3 py-2 text-sm">
                    <span className="min-w-0 flex-1 text-pretty">
                      {item.label}
                      {item.chapter && <span className="text-fg-3"> · {item.chapter}</span>}
                    </span>
                    <IconButton size="sm" icon={RotateCcw} label="Khôi phục việc này" className="-my-1.5 -mr-1.5" disabled={busy !== null} onClick={() => void decide("restore", device, item)} />
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </details>
      )}
      {data.recent.length > 0 && (
        <details className="mt-3 text-sm text-fg-2">
          <summary className="cursor-pointer select-none">Gửi gần đây ({data.recent.length})</summary>
          <ul className="mt-2 space-y-2">
            {data.recent.map((push) => (
              <li key={`${push.device}:${push.at}`} className="text-pretty">
                {describePush(push)}
                {push.conflicts.map((line) => (
                  <span key={line} className="mt-0.5 block text-xs text-fg-3">
                    {line}
                  </span>
                ))}
              </li>
            ))}
          </ul>
        </details>
      )}
      <Dialog
        open={confirmSkipAll !== null}
        onOpenChange={(open) => !open && setConfirmSkipAll(null)}
        width="max-w-md"
        title={`Bỏ qua mọi việc từ ${confirmSkipAll?.name ?? "máy này"}?`}
        description={`Bỏ ${confirmSkipAll?.items.length ?? 0} việc khỏi hàng chờ, khôi phục được ở “Đã bỏ qua”.`}
      >
        <div className="dialog-actions">
          <Button variant="ghost" onClick={() => setConfirmSkipAll(null)}>
            Thôi
          </Button>
          <Button
            variant="primary"
            onClick={() => {
              const device = confirmSkipAll;
              setConfirmSkipAll(null);
              if (device) void decide("skip", device);
            }}
          >
            Bỏ qua tất cả
          </Button>
        </div>
      </Dialog>
    </MotionRegion>
  );
}

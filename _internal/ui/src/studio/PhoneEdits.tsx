import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Link2, Smartphone, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { formatWhen } from "@/shared/format";
import { Button, IconButton } from "@/shared/ui";
import { KIND_ICON } from "./ApplyChanges";
import { api } from "./api";

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
}

function useInbox(bookId: string, enabled = true) {
  return useQuery({
    queryKey: ["edits-inbox", bookId],
    queryFn: () => api<EditsInbox>(`/api/books/${bookId}/edits-inbox`),
    enabled: enabled && Boolean(bookId),
    refetchInterval: 15_000,
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

export function PhoneEdits({ bookId }: { bookId: string }) {
  const client = useQueryClient();
  const { data } = useInbox(bookId);
  const [busy, setBusy] = useState<string | null>(null);
  if (!data || (!data.devices.length && !data.recent.length)) return null;

  const decide = async (verb: "apply" | "skip", device: InboxDevice, item?: InboxItem) => {
    setBusy(`${device.id}:${item?.id ?? "all"}`);
    try {
      const reply = await api<{ requests?: number; skipped?: number; removed?: number }>(`/api/books/${bookId}/edits-inbox/${verb}`, {
        method: "POST",
        body: { device: device.id, ...(item ? { items: [item.id] } : {}) },
      });
      if (verb === "apply") {
        const made = reply.requests ?? 0;
        const skipped = reply.skipped ?? 0;
        toast.success(made ? `Đã ghi ${made} việc vào “Áp dụng thay đổi”` : "Không có việc nào ghi được", {
          description: skipped ? `${skipped} việc không còn khớp với sách nên bị bỏ qua.` : "Chưa thu lại gì - bấm “Áp dụng thay đổi” khi muốn máy làm.",
        });
      } else {
        toast("Đã bỏ qua", { description: "Không có gì thay đổi trong sách." });
      }
      await client.invalidateQueries();
    } catch (error) {
      toast.error("Chưa làm được", { description: (error as Error).message });
    } finally {
      setBusy(null);
    }
  };

  return (
    <section aria-label="Thay đổi từ máy khác" className="mb-5 rounded-2xl border border-line bg-panel p-4">
      <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
        <Smartphone className="size-4 text-fg-3" /> Thay đổi từ máy khác{data.waiting ? ` (${data.waiting} việc chờ duyệt)` : ""}
      </h2>
      {data.devices.length > 0 && (
        <p className="mt-1 text-pretty text-sm text-fg-2">
          Điện thoại hay máy tính đã ghép chưa được điều khiển sản xuất nên những việc dưới đây chờ bạn quyết - chưa có gì được làm. “Áp dụng” biến việc thành yêu
          cầu trong “Áp dụng thay đổi” (chưa thu lại gì); “Bỏ qua” bỏ hẳn. Tên sách, bìa, tên nhân vật, tên chương và nhạc nền máy ấy gửi
          thì đã áp ngay.
        </p>
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
            <Button size="sm" variant="ghost" icon={X} disabled={busy !== null} onClick={() => void decide("skip", device)}>
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
                  </span>
                  <IconButton size="sm" icon={Check} label="Áp dụng việc này" className="-my-1.5" disabled={busy !== null} onClick={() => void decide("apply", device, item)} />
                  <IconButton size="sm" icon={X} label="Bỏ qua việc này" className="-my-1.5 -mr-1.5" disabled={busy !== null} onClick={() => void decide("skip", device, item)} />
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      {data.recent.length > 0 && (
        <details className="mt-3 text-sm text-fg-2">
          <summary className="cursor-pointer select-none">Điện thoại đã gửi gần đây ({data.recent.length})</summary>
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
    </section>
  );
}

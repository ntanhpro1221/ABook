import { S } from "../shared/strings.generated";
import { MoreInfo } from "@/shared/SettingsNav";
import { MotionRegion } from "@/shared/MotionRegion";
import { SectionHeading } from "@/shared/SectionHeading";
import { AnimatedRows, MotionPresence, Reveal } from "@/shared/MotionPresence";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Link2, RotateCcw, Smartphone, X } from "lucide-react";
import { useState } from "react";
import { toast, toastDone } from "@/shared/toast";
import { formatWhen } from "@/shared/format";
import { DialogActions, Button, Dialog, IconButton } from "@/shared/ui";
import { KIND_ICON } from "./ApplyChanges";
import { api } from "./api";
import { UNDO_MS } from "./decisions";
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
  if (push.applied) parts.push(S.s_0_thay_doi_da_ap_3059b99c(push.applied));
  if (push.requests) parts.push(S.s_0_viec_da_thanh_yeu_cau_40a3ca0a(push.requests));
  if (push.waiting) parts.push(S.s_0_viec_dang_cho_duyet_c4cdff82(push.waiting));
  if (push.skipped) parts.push(S.s_0_khong_con_cho_trong_sach_bo_qua_473df6a6(push.skipped));
  return `${push.name} · ${formatWhen(push.at)}: ${parts.join(", ") || S.s_khong_co_gi_moi_40f1e53d}`;
}

/** Lời cảnh báo của toast "Áp dụng" một việc từ hộp thư: việc nào không còn khớp (bị bỏ qua) và việc nào vẫn chờ bạn chọn. Không có gì để cảnh báo thì không gọi. */
export function applyNote({ skipped, held, dropped = [] }: { skipped: number; held: number; dropped?: string[] }): string {
  // Nói rõ việc nào không áp được (câu đã đổi chữ, người chưa có giọng...), không chỉ một con số.
  const which = dropped.length ? `: ${dropped.slice(0, 3).join("; ")}${dropped.length > 3 ? S.s_va_0_viec_nua_b0e7d66c(dropped.length - 3) : ""}` : "";
  return [
    skipped ? S.s_0_viec_khong_con_khop_voi_sach_nen_bi_bo_q_b5b9c7e6(skipped, which) : "",
    held ? S.s_0_viec_may_nay_da_doi_khac_sau_do_van_cho_a8cbff95(held) : "",
  ]
    .filter(Boolean)
    .join(" ");
}

export function PhoneEdits({ bookId }: { bookId: string }) {
  const client = useQueryClient();
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
        toastDone(made ? S.s_da_ghi_0_viec_vao_ap_dung_thay_doi_195f34fc(made) : S.s_chua_ghi_duoc_viec_nao_25a1794a, skipped || held ? applyNote({ skipped, held, dropped: (reply.dropped ?? []).map((row) => row.label) }) : undefined);
      } else if (verb === "restore") {
        toast.success(S.s_da_khoi_phuc_e60855c0);
      } else {
        // Bỏ qua không mất hẳn: việc nằm ở khay “Đã bỏ qua” và bấm Khôi phục ngay trên thông báo được.
        toast(S.s_da_bo_qua_df41794e, {
          duration: UNDO_MS,
          action: { label: S.s_khoi_phuc_c652d9c0, onClick: () => void decide("restore", device, item) },
        });
      }
      await client.invalidateQueries();
    } catch (error) {
      toast.error(S.s_chua_lam_duoc_8b442a06, { description: (error as Error).message });
    } finally {
      setBusy(null);
    }
  };

  return (
    <MotionRegion as="section" aria-label={S.s_yeu_cau_thiet_bi_26f11a4f} className="mb-5 py-4">
      <SectionHeading className="gap-2">
        <Smartphone className="size-4 text-fg-3" />{S.s_yeu_cau_thiet_bi_bf94d986}{data.waiting ? S.s_0_viec_cho_duyet_212109d9(data.waiting) : ""}
      </SectionHeading>
      {data.devices.length > 0 && (
        <div className="mt-1 text-sm text-fg-2">
          <p>{S.s_ap_dung_de_dua_vao_hang_cho_bo_qua_van_kho_b65a72a7}</p>
          <MoreInfo label={S.s_da_ap_dung_0e69eb72}>{S.s_ten_sach_bia_ten_nhan_vat_ten_chuong_va_nh_da8df954}</MoreInfo>
        </div>
      )}
      {/* Áp dụng / Bỏ qua / Khôi phục: hàng (và cả máy khi hết việc) khép / mở tại chỗ; data-motion-live - cả khung không mờ lại theo từng hàng. */}
      <div data-motion-live="">
      <AnimatedRows items={data.devices} keyOf={(device) => device.id}>
      {(device) => (
        <div className="pt-3">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="min-w-0 flex-1 truncate text-sm font-medium">
              {device.name} <span className="font-normal text-fg-3">{S.s_gui_665940fe}{formatWhen(device.at)}</span>
            </h3>
            <Button size="sm" variant="primary" icon={Check} loading={busy === `${device.id}:all`} disabled={busy !== null} onClick={() => void decide("apply", device)}>{S.s_ap_dung_tat_ca_068378e0}</Button>
            <Button size="sm" variant="ghost" icon={X} disabled={busy !== null} onClick={() => setConfirmSkipAll(device)}>{S.s_bo_qua_tat_ca_e736ef1f}</Button>
          </div>
          <AnimatedRows className="mt-2 divide-y divide-line overflow-hidden" items={device.items} keyOf={(item) => item.id}>
            {(item) => {
              const Icon = item.kind === "alias" ? Link2 : (KIND_ICON[item.kind] ?? Check);
              return (
                <MotionRegion className="flex items-start gap-3 py-2 text-sm">
                  <Icon className="mt-line-icon size-4 shrink-0 text-fg-3" />
                  <span className="min-w-0 flex-1 text-pretty">
                    {item.label}
                    {item.chapter && <span className="text-fg-3"> · {item.chapter}</span>}
                    {item.conflict && <span className="mt-1 block text-xs text-warning">{item.conflict}</span>}
                  </span>
                  <IconButton size="sm" icon={Check} label={S.s_ap_dung_viec_nay_76d8752a} className="-my-2" disabled={busy !== null} onClick={() => void decide("apply", device, item)} />
                  <IconButton size="sm" icon={X} label={S.s_bo_qua_viec_nay_e6b2362b} className="-my-2 -mr-2" disabled={busy !== null} onClick={() => void decide("skip", device, item)} />
                </MotionRegion>
              );
            }}
          </AnimatedRows>
        </div>
      )}
      </AnimatedRows>
      </div>
      <MotionPresence open={(data.skipped?.length ?? 0) > 0}>
        <details className="mt-3 text-sm text-fg-2">
          <summary className="cursor-pointer select-none">{S.s_da_bo_qua_7f216d1a}{data.skipped.reduce((sum, device) => sum + device.items.length, 0)})</summary>
          <div data-motion-live="">
          <AnimatedRows items={data.skipped ?? []} keyOf={(device) => device.id}>
          {(device) => (
            <div className="pt-2">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="min-w-0 flex-1 truncate text-sm font-medium text-fg">{device.name}</h3>
                <Button size="sm" variant="ghost" icon={RotateCcw} disabled={busy !== null} onClick={() => void decide("restore", device)}>{S.s_khoi_phuc_tat_ca_cc961492}</Button>
              </div>
              <AnimatedRows className="mt-1 divide-y divide-line overflow-hidden" items={device.items} keyOf={(item) => item.id}>
                {(item) => (
                  <div className="flex items-start gap-3 py-2 text-sm">
                    <span className="min-w-0 flex-1 text-pretty">
                      {item.label}
                      <Reveal when={item.chapter}><span className="text-fg-3"> · {item.chapter}</span></Reveal>
                    </span>
                    <IconButton size="sm" icon={RotateCcw} label={S.s_khoi_phuc_viec_nay_8da3e2a8} className="-my-2 -mr-2" disabled={busy !== null} onClick={() => void decide("restore", device, item)} />
                  </div>
                )}
              </AnimatedRows>
            </div>
          )}
          </AnimatedRows>
          </div>
        </details>
      </MotionPresence>
      {data.recent.length > 0 && (
        <details className="mt-3 text-sm text-fg-2">
          <summary className="cursor-pointer select-none">{S.s_gui_gan_day_954ffe00}{data.recent.length})</summary>
          <ul className="mt-2 space-y-2">
            {data.recent.map((push) => (
              <li key={`${push.device}:${push.at}`} className="text-pretty">
                {describePush(push)}
                {push.conflicts.map((line) => (
                  <span key={line} className="mt-1 block text-xs text-fg-3">
                    {line}
                  </span>
                ))}
              </li>
            ))}
          </ul>
        </details>
      )}
      <Dialog footer={<DialogActions>
          <Button variant="ghost" onClick={() => setConfirmSkipAll(null)}>{S.s_thoi_e68f9e88}</Button>
          <Button
            variant="primary"
            onClick={() => {
              const device = confirmSkipAll;
              setConfirmSkipAll(null);
              if (device) void decide("skip", device);
            }}
          >{S.s_bo_qua_tat_ca_e736ef1f}</Button>
        </DialogActions>}
        open={confirmSkipAll !== null}
        onOpenChange={(open) => !open && setConfirmSkipAll(null)}
        width="max-w-md"
        title={S.s_bo_qua_moi_viec_tu_0_c7084397(confirmSkipAll?.name ?? S.s_may_nay_e53e5d40)}
        description={S.s_bo_0_viec_khoi_hang_cho_khoi_phuc_duoc_o_d_49a337c4(confirmSkipAll?.items.length ?? 0)}
      >

      </Dialog>
    </MotionRegion>
  );
}

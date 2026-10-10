import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Cpu, Download, LoaderCircle, Square, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { cn } from "@/shared/cn";
import { Button, Progress } from "@/shared/ui";
import { api } from "./api";
import { useAppInfo, useStudioMissing } from "./data";
import { friendlySetupError } from "./errorText";
import { formatSize } from "./musicLocal";

// App Windows đóng gói chỉ mang phần nghe; Studio - thư viện dây chuyền + model, ~20 GB - tải khi người dùng bấm
// (webui/studio_setup.py). Bản dev không có thẻ này: Studio là runtime cạnh mã nguồn (`info.studio` = null).

interface SetupStep {
  id: string;
  label: string;
  hint: string;
  done: boolean;
}

interface SetupStatus {
  installed: boolean;
  /** Bước đã cài bằng bản cũ hơn bản app này mang (nhãn) - "Cập nhật Studio" chạy lại đúng các bước ấy. */
  outdated: string[];
  /** Bước đã cài mà file của nó mất (vd Ollama) - "Sửa Studio" tải lại đúng phần ấy. */
  damaged?: string[];
  running: boolean;
  step: string | null;
  steps: SetupStep[];
  progress: { done: number; total: number } | null;
  detail: string;
  error: string | null;
  gpu: { name: string; memory: number } | null;
  root: string;
}

/** Studio là gì và máy cần gì để cài - MỘT chỗ viết, thẻ "Cài Studio" ở màn Dự án và khối nhắc ở trình tạo sách nói dùng chung để hai nơi không lệch nhau. */
export const STUDIO_WHAT = "Studio là phần biến truyện chữ thành sách nói: model đọc hiểu truyện, giọng đọc, nghe lại để kiểm từng câu.";
export const STUDIO_NEEDS = "Cần card đồ hoạ NVIDIA, tải khoảng 20 GB, ổ đĩa trống 30 GB. Cài một lần; nghe sách không cần Studio.";

/** Khối nói thật với người đang tạo sách nói trên máy chưa có Studio (hay Studio cần cập nhật): cần gì, cài ở đâu, và dự án vẫn tạo được -
 *  nó chờ tới khi Studio sẵn sàng. Cùng chữ với thẻ "Cài Studio" ở màn Dự án (STUDIO_WHAT / STUDIO_NEEDS); nút dẫn tới thẻ ấy. Máy có
 *  Studio thì không hiện gì. */
export function StudioInstallNotice({ className }: { className?: string }) {
  const { data: info } = useAppInfo();
  const navigate = useNavigate();
  const studio = useStudioMissing();
  if (!studio.missing) return null;
  return (
    <section aria-label="Cần Studio" className={cn("flex flex-wrap items-start gap-3 rounded-xl border border-warning/40 bg-warning-soft p-4 text-sm", className)}>
      <Cpu className="mt-0.5 size-4 shrink-0 text-warning" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{studio.repair ? "Studio mất một phần, cần sửa trước khi làm sách" : studio.update ? "Studio cần cập nhật trước khi làm sách" : "Máy này chưa cài Studio"}</p>
        <p className="mt-1 text-[13px] leading-relaxed text-fg-2 text-pretty">
          {studio.update ? "" : `${STUDIO_WHAT} ${STUDIO_NEEDS} `}
          Vẫn tạo dự án được: dự án chờ tới khi {studio.repair ? "sửa" : studio.update ? "cập nhật" : "cài"} xong, các bước đã chọn ở đây được giữ nguyên.
        </p>
      </div>
      {!info?.remote && (
        <Button variant="secondary" size="sm" icon={Download} onClick={() => navigate("/studio")}>
          {studio.action}
        </Button>
      )}
    </section>
  );
}

/** Máy chưa cài Studio (hay Studio cài từ bản app cũ cần cập nhật): thẻ ở đầu màn Dự án - cần gì, từng bước, tiến độ,
 *  lỗi đọc được, bấm lại là làm tiếp. */
export function StudioSetupCard({ className }: { className?: string }) {
  const { data: info } = useAppInfo();
  const client = useQueryClient();
  const needed = Boolean(info?.studio && (!info.studio.installed || info.studio.outdated));
  const { data: status } = useQuery({
    queryKey: ["studio-setup"],
    queryFn: () => api<SetupStatus>("/api/studio/setup"),
    enabled: needed,
    refetchInterval: (query) => (query.state.data?.running ? 1000 : false),
  });
  const wasRunning = useRef(false);
  useEffect(() => {
    if (!status) return;
    if (wasRunning.current && !status.running) {
      if (status.installed && status.outdated.length === 0) {
        toast.success("Studio đã sẵn sàng", { description: "Giờ tạo và làm sách nói được trên máy này." });
        void client.invalidateQueries({ queryKey: ["app"] });
      } else if (status.error) {
        toast.error("Studio chưa xong", { description: friendlySetupError(status.error).summary });
      }
    }
    wasRunning.current = status.running;
  }, [status, client]);
  if (!needed || !status) return null;

  const call = async (path: string) => {
    try {
      client.setQueryData(["studio-setup"], await api<SetupStatus>(path, { method: "POST", body: {} }));
    } catch (error) {
      toast.error("Không cài được Studio", { description: (error as Error).message });
    }
  };
  const damaged = status.damaged ?? [];
  const repair = status.installed && damaged.length > 0;
  const stale = status.outdated.filter((label) => !damaged.includes(label));
  const update = status.installed && status.outdated.length > 0;
  const started = status.steps.some((step) => step.done);
  const current = status.steps.find((step) => step.id === status.step);
  const progress = status.progress && status.progress.total > 0 ? status.progress.done / status.progress.total : null;
  return (
    <section className={cn("rounded-2xl border border-line bg-panel p-5 sm:p-6", className)} aria-labelledby="studio-setup-title">
      <div className="flex flex-wrap items-start gap-4">
        <div className="grid size-11 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent-text">
          <Cpu className="size-5" />
        </div>
        <div className="min-w-0 flex-1">
          <h2 id="studio-setup-title" className="text-base font-semibold">
            {repair ? "Sửa Studio" : update ? "Cập nhật Studio" : "Cài Studio để làm sách nói trên máy này"}
          </h2>
          <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-fg-2 text-pretty">
            {repair
              ? `Studio trên máy này mất ${damaged.join(", ")} (file đã bị xoá hay hỏng) nên chưa làm sách được.${
                  stale.length > 0 ? ` Cũng cần cập nhật ${stale.join(", ")}.` : ""
                } Bấm Sửa Studio để tải lại đúng phần ấy; sách đã làm và chỗ đang nghe giữ nguyên.`
              : update
              ? `Bản ABook này làm sách bằng ${status.outdated.join(", ")} khác với bản Studio đang có - cập nhật rồi làm sách
                tiếp. Chỉ tải lại đúng phần ấy; sách đã làm và chỗ đang nghe giữ nguyên.`
              : `${STUDIO_WHAT} ${STUDIO_NEEDS} Mất mạng hay tắt máy giữa chừng thì bấm lại là làm tiếp.`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {status.running ? (
            <Button icon={Square} onClick={() => void call("/api/studio/setup/cancel")}>
              Dừng
            </Button>
          ) : (
            <Button variant="primary" icon={Download} onClick={() => void call("/api/studio/setup")}>
              {repair ? "Sửa Studio" : update ? "Cập nhật Studio" : started ? "Cài tiếp" : "Cài Studio"}
            </Button>
          )}
        </div>
      </div>

      {status.error && !status.running && (
        <div role="alert" className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-[13px] leading-relaxed text-danger">
          <p>{friendlySetupError(status.error).summary}</p>
          {friendlySetupError(status.error).detail && (
            <details className="mt-1 text-xs">
              <summary className="cursor-pointer select-none">Chi tiết</summary>
              <p className="mt-1 select-text break-words font-mono">{friendlySetupError(status.error).detail}</p>
            </details>
          )}
        </div>
      )}

      {(status.running || started) && (
        <ol className="mt-5 grid gap-x-8 gap-y-1.5 sm:grid-cols-2">
          {status.steps.map((step) => {
            const active = status.running && step.id === status.step;
            return (
              <li key={step.id} className="flex min-w-0 items-center gap-2.5 text-[13px]">
                {step.done ? (
                  <Check className="size-4 shrink-0 text-accent-text" aria-label="xong" />
                ) : active ? (
                  <LoaderCircle className="size-4 shrink-0 animate-spin text-accent-text motion-reduce:animate-none" aria-label="đang làm" />
                ) : (
                  <span className="size-4 shrink-0 rounded-full border border-line-strong" aria-hidden />
                )}
                <span className={cn("truncate", step.done ? "text-fg-2" : active ? "font-semibold" : "text-fg-2")}>{step.label}</span>
                <span className="truncate text-xs text-fg-3">{step.hint}</span>
              </li>
            );
          })}
        </ol>
      )}

      {status.running && current && (
        <div className="mt-4">
          <Progress value={progress ?? 0} running={progress === null} size="sm" label={`Tiến độ: ${current.label}`} />
          <div className="mt-1.5 flex justify-between gap-4 text-xs text-fg-2">
            <span className="truncate">{status.detail || current.label}</span>
            {status.progress && status.progress.total > 0 && (
              <span className="tabular shrink-0">
                {formatSize(status.progress.done)} / {formatSize(status.progress.total)}
              </span>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

/** Cài đặt > Studio (app đóng gói): Studio ở đâu, chạy trên card nào, và gỡ - bấm hai lần, vì gỡ là xoá 15-20 GB và
 *  cuốn đang làm dở phải làm lại sau khi cài lại. */
export function StudioSettings() {
  const { data: info } = useAppInfo();
  const client = useQueryClient();
  const navigate = useNavigate();
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const { data: status } = useQuery({
    queryKey: ["studio-setup"],
    queryFn: () => api<SetupStatus>("/api/studio/setup"),
    enabled: Boolean(info?.studio),
  });
  useEffect(() => {
    if (!armed) return;
    const timer = window.setTimeout(() => setArmed(false), 6000);
    return () => window.clearTimeout(timer);
  }, [armed]);
  if (!info?.studio || !status) return null;
  if (!status.installed) {
    return (
      <div className="mb-6 max-w-xl">
        <h3 className="text-sm font-semibold">Studio trên máy này</h3>
        <p className="mt-1 text-sm">Chưa cài.</p>
        <p className="mt-1 text-[13px] leading-relaxed text-fg-2 text-pretty">{STUDIO_NEEDS}</p>
        <Button className="mt-3" variant="primary" icon={Download} onClick={() => navigate("/studio")}>
          Cài Studio
        </Button>
      </div>
    );
  }
  const remove = async () => {
    if (!armed) {
      setArmed(true);
      return;
    }
    setArmed(false);
    setBusy(true);
    try {
      client.setQueryData(["studio-setup"], await api<SetupStatus>("/api/studio/setup", { method: "DELETE" }));
      toast.success("Đã gỡ Studio", { description: "Sách đã làm và chỗ đang nghe vẫn nguyên." });
      void client.invalidateQueries({ queryKey: ["app"] });
    } catch (error) {
      toast.error("Chưa gỡ được Studio", { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="mb-6 max-w-xl">
      <h3 className="text-sm font-semibold">Studio trên máy này</h3>
      <p className="mt-1 text-sm">Studio đã cài{status.gpu ? `, chạy trên ${status.gpu.name}` : ""}.</p>
      {status.outdated.length > 0 && (
        <p className="mt-1 text-[13px] text-fg-2">
          {status.damaged?.length ? `Mất ${status.damaged.join(", ")} (file đã bị xoá hay hỏng)` : `Cần cập nhật ${status.outdated.join(", ")}`} -{" "}
          <button type="button" onClick={() => navigate("/studio")} className="font-medium text-accent-text underline">
            {status.damaged?.length ? "Sửa Studio" : "Cập nhật Studio"}
          </button>
          .
        </p>
      )}
      <p className="mt-1 break-all text-[13px] text-fg-2">{status.root}</p>
      <Button className="mt-3" variant={armed ? "danger" : "secondary"} icon={Trash2} disabled={busy} onClick={() => void remove()}>
        {busy ? "Đang gỡ…" : armed ? "Bấm lần nữa để gỡ" : "Gỡ Studio"}
      </Button>
      <p className="mt-2 text-xs leading-relaxed text-fg-2 text-pretty">
        Gỡ là xoá thư viện và model (15-20 GB). Sách đã làm, chỗ đang nghe và dữ liệu app giữ nguyên; cuốn đang làm dở
        phải làm lại từ đầu sau khi cài lại.
      </p>
    </div>
  );
}

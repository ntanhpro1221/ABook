import { MotionRegion } from "@/shared/MotionRegion";
import { MotionPresence } from "@/shared/MotionPresence";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Clapperboard, Cpu, Download, LoaderCircle, Square, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "@/shared/toast";
import { cn } from "@/shared/cn";
import { peerPage } from "@/shared/peerStudio";
import { Button, Progress } from "@/shared/ui";
import { SettingsRow } from "@/shared/SettingsNav";
import { api } from "./api";
import { useAppInfo, useStudioMissing } from "./data";
import { friendlySetupError } from "./errorText";
import { formatSize } from "./musicLocal";
import { leftoverLine, type SetupLeftover } from "./setupLeftover";
import { noStudioLine, studioFit, type StudioFit, type StudioGpu } from "./studioFit";

// App Windows đóng gói chỉ mang phần nghe; Studio - thư viện dây chuyền + model, ~25 GB - tải khi người dùng bấm
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
  /** Card NVIDIA - máy chủ dò ngay khi được hỏi, trước khi bấm Cài (studio_setup.detected_gpu). */
  gpu: StudioGpu | null;
  root: string;
  /** Lượt cài của lần mở app trước (hay cửa sổ khác) còn chạy - không cài chồng lên nó (webui/install_lock.py). */
  leftover?: SetupLeftover | null;
}

const SETUP_QUERY = { queryKey: ["studio-setup"], queryFn: () => api<SetupStatus>("/api/studio/setup") };

/** Máy chưa cài Studio: card của máy có đủ để làm sách nói không (studioFit.ts). `null` khi chưa biết, máy đã cài, hay bản dev / Studio từ xa. */
export function useStudioFit(): StudioFit | null {
  const studio = useAppInfo().data?.studio;
  const needed = Boolean(studio && !studio.installed);
  const { data: status } = useQuery({ ...SETUP_QUERY, enabled: needed });
  return needed && status && !status.installed ? studioFit(status.gpu) : null;
}

/** Card NVIDIA của máy làm sách (cho ước lượng thời gian: chỉ máy cùng loại card đã đo mới được nói số đo). `null` khi chưa biết (bản dev, hay máy không có Studio). */
export function useStudioGpu(): StudioGpu | null {
  const studio = useAppInfo().data?.studio;
  const { data: status } = useQuery({ ...SETUP_QUERY, enabled: Boolean(studio) });
  return status?.gpu ?? null;
}

/** Máy tính đã ghép với máy này (Cài đặt > Thiết bị) - nơi mời tạo sách nói khi máy này không làm được. */
export function usePairedComputers(enabled: boolean): { id: string; name: string }[] {
  const { data } = useQuery({
    queryKey: ["computers"],
    queryFn: () => api<{ computers: { id: string; name: string; kind?: string }[] }>("/api/computers"),
    enabled,
  });
  return (data?.computers ?? []).filter((computer) => computer.kind !== "phone");
}

/** Studio là gì và máy cần gì để cài - MỘT chỗ viết, thẻ "Cài Studio" ở màn Dự án và khối nhắc ở trình tạo sách nói dùng chung để hai nơi không lệch nhau. */
export const STUDIO_WHAT = "Studio biến truyện chữ thành sách nói.";
// Thời gian một chương: số đo của dây chuyền trên card 8 GB của máy thử, phân tích + thu (docs/ANALYSIS_RESEARCH.md, mục máy Mac mini).
export const STUDIO_NEEDS =
  "NVIDIA từ 8 GB · tải ~25 GB · trống 35 GB · ~7–10 phút/chương.";

/** Máy thiếu cấu hình: nói thật, và nếu đã ghép máy tính khác thì mời tạo ở đó (Studio của máy ấy mở ngay trong app này -
 *  webui/peer_studio.py). Không mời "tạo rồi chờ cài xong": dự án ấy sẽ không bao giờ chạy trên máy này (soát a64). */
export function NoStudioHere({ fit, className }: { fit: StudioFit; className?: string }) {
  const remote = Boolean(useAppInfo().data?.remote);
  const peers = usePairedComputers(!remote);
  return (
    <MotionRegion>
    <section aria-label="Máy thiếu cấu hình" className={cn("flex flex-wrap items-start gap-3 py-4 text-sm", className)}>
      <Cpu className="mt-0.5 size-4 shrink-0 text-warning" />
      <div className="min-w-0 flex-1 basis-[16rem]">
        <p className="font-semibold text-pretty">Máy thiếu cấu hình</p>
        <p className="mt-1 text-[0.8125rem] leading-relaxed text-fg-2 text-pretty">
          {noStudioLine(fit.reason ?? "").replace(/\.$/, "")}; {peers.length
            ? "tạo trên máy đã ghép có Studio, sách xong nghe ở cả hai máy."
            : "cài Studio trên máy khác rồi ghép tại Cài đặt → Thiết bị."}
        </p>
      </div>
      {peers.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {peers.map((peer) => (
            <Button key={peer.id} variant="ghost" size="sm" icon={Clapperboard} onClick={() => window.location.assign(peerPage(window.location.search, peer.id, "/studio/new"))}>
              Tạo trên {peer.name}
            </Button>
          ))}
        </div>
      )}
    </section>
    </MotionRegion>
  );
}


/** Khối nói thật với người đang tạo sách nói trên máy chưa có Studio (hay Studio cần cập nhật): cần gì, cài ở đâu, và dự án vẫn tạo được -
 *  nó chờ tới khi Studio sẵn sàng. Cùng chữ với thẻ "Cài Studio" ở màn Dự án (STUDIO_WHAT / STUDIO_NEEDS); nút dẫn tới thẻ ấy. Máy có
 *  Studio thì không hiện gì. */
export function StudioInstallNotice({ className }: { className?: string }) {
  const { data: info } = useAppInfo();
  const navigate = useNavigate();
  const studio = useStudioMissing();
  const fit = useStudioFit();
  if (!studio.missing) return <MotionRegion />;
  if (fit?.level === "no") return <MotionRegion><NoStudioHere fit={fit} className={className} /></MotionRegion>;
  return (
    <MotionRegion>
    <section aria-label="Cần Studio" className={cn("flex flex-wrap items-start gap-3 py-4 text-sm", className)}>
      <Cpu className="mt-0.5 size-4 shrink-0 text-warning" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{studio.repair ? "Cần sửa Studio" : studio.update ? "Studio cần cập nhật" : "Chưa cài Studio"}</p>
        <p className="mt-1 text-[0.8125rem] leading-relaxed text-fg-2 text-pretty">
          Dự án giữ thiết lập và chờ Studio sẵn sàng.
        </p>
      </div>
      {!info?.remote && (
        <Button variant="ghost" size="sm" icon={Download} onClick={() => navigate("/studio")}>
          {studio.action}
        </Button>
      )}
    </section>
    </MotionRegion>
  );
}

/** Máy chưa cài Studio (hay Studio cài từ bản app cũ cần cập nhật): thẻ ở đầu màn Dự án - cần gì, từng bước, tiến độ,
 *  lỗi đọc được, bấm lại là làm tiếp. */
export function StudioSetupCard({ className }: { className?: string }) {
  const { data: info } = useAppInfo();
  const client = useQueryClient();
  const needed = Boolean(info?.studio && (!info.studio.installed || info.studio.outdated));
  const { data: status } = useQuery({
    ...SETUP_QUERY,
    enabled: needed,
    refetchInterval: (query) => (query.state.data?.running ? 1000 : query.state.data?.leftover ? 2000 : false),
  });
  const wasRunning = useRef(false);
  useEffect(() => {
    if (!status) return;
    if (wasRunning.current && !status.running) {
      if (status.installed && status.outdated.length === 0) {
        toast.success("Studio đã sẵn sàng");
        void client.invalidateQueries({ queryKey: ["app"] });
      } else if (status.error) {
        toast.error("Studio chưa xong", { description: friendlySetupError(status.error).summary });
      }
    }
    wasRunning.current = status.running;
  }, [status, client]);
  if (!needed || !status) return <MotionRegion />;

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
  // Card của máy, biết trước khi bấm Cài: máy không đủ thì nói thẳng và nút cài thành nút nhỏ "Vẫn cài" (soát a64).
  const fit = !status.installed ? studioFit(status.gpu) : null;
  const unfit = fit?.level === "no" && !status.running;
  return (
    <MotionRegion as="section" className={cn("py-5 sm:py-6", className)} aria-labelledby="studio-setup-title">
      {/* Màn hẹp: chữ chiếm cả hàng, nút xuống dưới - không ép chữ thành cột hẹp cạnh nút (soát a64, 390 px). */}
      <div className="flex flex-wrap items-start gap-4">
        <div className="grid size-11 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent-text">
          <Cpu className="size-5" />
        </div>
        <div className="min-w-0 flex-1 basis-[16rem]">
          <h2 id="studio-setup-title" className="text-base font-semibold">
            {repair ? "Sửa Studio" : update ? "Cập nhật Studio" : "Cài Studio"}
          </h2>
          <p className="mt-1 max-w-2xl text-[0.8125rem] leading-relaxed text-fg-2 text-pretty">
            {repair
              ? `Tải lại ${[...damaged, ...stale].join(", ")}; sách giữ nguyên.`
              : update
              ? `Cập nhật ${status.outdated.join(", ")}; sách giữ nguyên.`
              : `${STUDIO_NEEDS}`}
          </p>
          {fit && (
            <p className={cn("mt-2 max-w-2xl text-[0.8125rem] leading-relaxed text-pretty", fit.level === "no" ? "font-medium text-fg" : "text-fg-2")}>
              {fit.level === "no" ? noStudioLine(fit.reason ?? "") : fit.line}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {status.running ? (
            <Button icon={Square} onClick={() => void call("/api/studio/setup/cancel")}>
              Dừng
            </Button>
          ) : status.leftover ? (
            status.leftover.orphan ? (
              <Button icon={Square} onClick={() => void call("/api/studio/setup/cancel")}>
                Dừng lượt cũ
              </Button>
            ) : (
              <Button variant="primary" icon={Download} disabled>
                Cài tiếp
              </Button>
            )
          ) : unfit ? (
            <Button variant="ghost" size="sm" icon={Download} onClick={() => void call("/api/studio/setup")}>
              Vẫn cài
            </Button>
          ) : (
            <Button variant="primary" icon={Download} onClick={() => void call("/api/studio/setup")}>
              {repair ? "Sửa Studio" : update ? "Cập nhật Studio" : started ? "Cài tiếp" : "Cài Studio"}
            </Button>
          )}
        </div>
      </div>

      {status.leftover && !status.running && (
        <p role="status" className="mt-4 py-2 text-[0.8125rem] leading-relaxed text-pretty">
          {leftoverLine(status.leftover)}
        </p>
      )}

      {status.error && !status.running && !status.leftover && (
        <div role="alert" className="mt-4 py-2 text-[0.8125rem] leading-relaxed text-danger">
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
              <li key={step.id} className="flex min-w-0 items-center gap-2.5 text-[0.8125rem]">
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
    </MotionRegion>
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
  const { data: status } = useQuery({ ...SETUP_QUERY, enabled: Boolean(info?.studio) });
  useEffect(() => {
    if (!armed) return;
    const timer = window.setTimeout(() => setArmed(false), 6000);
    return () => window.clearTimeout(timer);
  }, [armed]);
  if (!info?.studio || !status) return <MotionRegion />;
  if (!status.installed) {
    const fit = studioFit(status.gpu);
    // Bấm là cài luôn rồi sang màn Dự án xem tiến độ - không phải bấm "Cài Studio" lần hai ở đó (soát a64).
    const install = async () => {
      setBusy(true);
      try {
        client.setQueryData(["studio-setup"], await api<SetupStatus>("/api/studio/setup", { method: "POST", body: {} }));
        navigate("/studio");
      } catch (error) {
        toast.error("Không cài được Studio", { description: (error as Error).message });
      } finally {
        setBusy(false);
      }
    };
    return (
      <MotionRegion as="div" className="max-w-xl py-3.5">
        <h3 className="text-[0.9375rem] font-medium">Studio trên máy này</h3>
        <p className="mt-1 text-sm">{status.running ? "Đang cài." : "Chưa cài."}</p>
        <p className="mt-1 text-[0.8125rem] leading-relaxed text-fg-2 text-pretty">{STUDIO_NEEDS}</p>
        <p className={cn("mt-1 text-[0.8125rem] leading-relaxed text-pretty", fit.level === "no" ? "font-medium text-fg" : "text-fg-2")}>
          {fit.level === "no" ? noStudioLine(fit.reason ?? "") : fit.line}
        </p>
        {status.running ? (
          <Button className="mt-3" variant="ghost" onClick={() => navigate("/studio")}>
            Xem tiến độ cài
          </Button>
        ) : fit.level === "no" ? (
          <Button className="mt-3" variant="ghost" size="sm" icon={Download} disabled={busy} onClick={() => void install()}>
            Vẫn cài
          </Button>
        ) : (
          <Button className="mt-3" variant="primary" icon={Download} disabled={busy} onClick={() => void install()}>
            Cài Studio
          </Button>
        )}
      </MotionRegion>
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
      toast.success("Đã gỡ Studio");
      void client.invalidateQueries({ queryKey: ["app"] });
    } catch (error) {
      toast.error("Chưa gỡ được Studio", { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  return (
    <MotionRegion as="div">
      <SettingsRow label="Studio trên máy này" hint={<>
        <p>Đã cài{status.gpu ? ` · ${status.gpu.name}` : ""}</p>
        <p className="mt-1 break-all">{status.root}</p>
      </>}>
        <Button size="sm" variant={armed ? "danger" : "ghost"} icon={Trash2} disabled={busy} onClick={() => void remove()}>
          {busy ? "Đang gỡ…" : armed ? "Xác nhận gỡ" : "Gỡ Studio"}
        </Button>
      </SettingsRow>
      {status.outdated.length > 0 && (
        <p className="mt-1 text-[0.8125rem] text-fg-2">
          {status.damaged?.length ? `Mất ${status.damaged.join(", ")} (file đã bị xoá hay hỏng)` : `Cần cập nhật ${status.outdated.join(", ")}`} -{" "}
          <button type="button" onClick={() => navigate("/studio")} className="font-medium text-accent-text underline">
            {status.damaged?.length ? "Sửa Studio" : "Cập nhật Studio"}
          </button>
          .
        </p>
      )}
      {/* Hậu quả của việc gỡ chỉ cần lúc đang xác nhận - không treo thường trực dưới nút. */}
      <MotionPresence open={armed}>
        <p className="pb-3 text-xs leading-snug text-fg-2 text-pretty">Xoá runtime/model (15–20 GB), giữ sách và hồ sơ; cuốn đang làm phải làm lại sau khi cài.</p>
      </MotionPresence>
    </MotionRegion>
  );
}

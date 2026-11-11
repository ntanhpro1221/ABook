import { S } from "../shared/strings.generated";
import { TickingValue } from "@/shared/TickingValue";
import { MotionRegion } from "@/shared/MotionRegion";
import { SectionHeading } from "@/shared/SectionHeading";
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
import { formatSize } from "@/shared/format";
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
export const STUDIO_WHAT = S.s_studio_bien_truyen_chu_thanh_sach_noi_59542b09;
// Thời gian một chương: số đo của dây chuyền trên card 8 GB của máy thử, phân tích + thu (docs/ANALYSIS_RESEARCH.md, mục máy Mac mini).
export const STUDIO_NEEDS =
  S.s_nvidia_tu_8_gb_tai_25_gb_trong_35_gb_710_p_26788445;

/** Máy thiếu cấu hình: nói thật, và nếu đã ghép máy tính khác thì mời tạo ở đó (Studio của máy ấy mở ngay trong app này -
 *  webui/peer_studio.py). Không mời "tạo rồi chờ cài xong": dự án ấy sẽ không bao giờ chạy trên máy này (soát a64). */
export function NoStudioHere({ fit, className }: { fit: StudioFit; className?: string }) {
  const remote = Boolean(useAppInfo().data?.remote);
  const peers = usePairedComputers(!remote);
  return (
    <MotionRegion>
    <section aria-label={S.s_may_thieu_cau_hinh_df5ae9ef} className={cn("flex flex-wrap items-start gap-3 py-4 text-sm", className)}>
      <Cpu className="mt-line-icon size-4 shrink-0 text-warning" />
      <div className="min-w-0 flex-1 basis-[16rem]">
        <p className="font-semibold text-pretty">{S.s_may_thieu_cau_hinh_df5ae9ef}</p>
        <p className="mt-1 text-[0.8125rem] leading-relaxed text-fg-2 text-pretty">
          {noStudioLine(fit.reason ?? "").replace(/\.$/, "")}; {peers.length
            ? S.s_tao_tren_may_da_ghep_co_studio_sach_xong_n_816bfc37
            : S.s_cai_studio_tren_may_khac_roi_ghep_tai_cai_ae8031d9}
        </p>
      </div>
      {peers.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {peers.map((peer) => (
            <Button key={peer.id} variant="ghost" size="sm" icon={Clapperboard} onClick={() => window.location.assign(peerPage(window.location.search, peer.id, "/studio/new"))}>{S.s_tao_tren_91f136e2}{peer.name}
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
    <section aria-label={S.s_can_studio_4b14a373} className={cn("flex flex-wrap items-start gap-3 py-4 text-sm", className)}>
      <Cpu className="mt-line-icon size-4 shrink-0 text-warning" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{studio.repair ? S.s_can_sua_studio_a65aa0f0 : studio.update ? S.s_studio_can_cap_nhat_c0338642 : S.s_chua_cai_studio_029df34a}</p>
        <p className="mt-1 text-[0.8125rem] leading-relaxed text-fg-2 text-pretty">{S.s_du_an_giu_thiet_lap_va_cho_studio_san_sang_e878c6ea}</p>
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
        toast.success(S.s_studio_da_san_sang_eb109553);
        void client.invalidateQueries({ queryKey: ["app"] });
      } else if (status.error) {
        toast.error(S.s_studio_chua_xong_6d0dab40, { description: friendlySetupError(status.error).summary });
      }
    }
    wasRunning.current = status.running;
  }, [status, client]);
  if (!needed || !status) return <MotionRegion />;

  const call = async (path: string) => {
    try {
      client.setQueryData(["studio-setup"], await api<SetupStatus>(path, { method: "POST", body: {} }));
    } catch (error) {
      toast.error(S.s_chua_cai_duoc_studio_ee5900df, { description: (error as Error).message });
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
        <div className="grid size-11 shrink-0 place-items-center rounded-cover bg-accent-soft text-accent-text">
          <Cpu className="size-5" />
        </div>
        <div className="min-w-0 flex-1 basis-[16rem]">
          <h2 id="studio-setup-title" className="text-base font-semibold">
            {repair ? S.s_sua_studio_2f99394d : update ? S.s_cap_nhat_studio_b3acc7e7 : S.s_cai_studio_5fdd3bd9}
          </h2>
          <p className="mt-1 max-w-2xl text-[0.8125rem] leading-relaxed text-fg-2 text-pretty">
            {repair
              ? S.s_tai_lai_0_sach_giu_nguyen_0ea0e553([...damaged, ...stale].join(", "))
              : update
              ? S.s_cap_nhat_0_sach_giu_nguyen_691dff0f(status.outdated.join(", "))
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
            <Button icon={Square} onClick={() => void call("/api/studio/setup/cancel")}>{S.s_dung_11554138}</Button>
          ) : status.leftover ? (
            status.leftover.orphan ? (
              <Button icon={Square} onClick={() => void call("/api/studio/setup/cancel")}>{S.s_dung_luot_cu_98c3e5d1}</Button>
            ) : (
              <Button variant="primary" icon={Download} disabled>{S.s_cai_tiep_f4243054}</Button>
            )
          ) : unfit ? (
            <Button variant="ghost" size="sm" icon={Download} onClick={() => void call("/api/studio/setup")}>{S.s_van_cai_ef098464}</Button>
          ) : (
            <Button variant="primary" icon={Download} onClick={() => void call("/api/studio/setup")}>
              {repair ? S.s_sua_studio_2f99394d : update ? S.s_cap_nhat_studio_b3acc7e7 : started ? S.s_cai_tiep_f4243054 : S.s_cai_studio_5fdd3bd9}
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
              <summary className="cursor-pointer select-none">{S.s_chi_tiet_e762d926}</summary>
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
                  <Check className="size-4 shrink-0 text-accent-text" aria-label={S.s_xong_a6f4543a} />
                ) : active ? (
                  <LoaderCircle className="size-4 shrink-0 animate-spin text-accent-text motion-reduce:animate-none" aria-label={S.s_dang_lam_e22cfa2e} />
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
          <Progress value={progress ?? 0} indeterminate={progress === null} running size="sm" label={S.s_tien_do_0_bebc77d0(current.label)} />
          <div className="mt-1.5 flex justify-between gap-4 text-xs text-fg-2">
            <TickingValue className="truncate">{status.detail || current.label}</TickingValue>
            {status.progress && status.progress.total > 0 && (
              <span data-motion-live className="tabular shrink-0">
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
        toast.error(S.s_chua_cai_duoc_studio_ee5900df, { description: (error as Error).message });
      } finally {
        setBusy(false);
      }
    };
    return (
      <MotionRegion as="div" className="max-w-xl py-3.5">
        <SectionHeading as="h3">{S.s_studio_tren_may_nay_e2fb04aa}</SectionHeading>
        <p className="mt-1 text-sm">{status.running ? S.s_dang_cai_4ea651d1 : S.s_chua_cai_6003057a}</p>
        <p className="mt-1 text-[0.8125rem] leading-relaxed text-fg-2 text-pretty">{STUDIO_NEEDS}</p>
        <p className={cn("mt-1 text-[0.8125rem] leading-relaxed text-pretty", fit.level === "no" ? "font-medium text-fg" : "text-fg-2")}>
          {fit.level === "no" ? noStudioLine(fit.reason ?? "") : fit.line}
        </p>
        {status.running ? (
          <Button className="mt-3" variant="ghost" onClick={() => navigate("/studio")}>{S.s_xem_tien_do_cai_42e94c00}</Button>
        ) : fit.level === "no" ? (
          <Button className="mt-3" variant="ghost" size="sm" icon={Download} disabled={busy} onClick={() => void install()}>{S.s_van_cai_ef098464}</Button>
        ) : (
          <Button className="mt-3" variant="primary" icon={Download} disabled={busy} onClick={() => void install()}>{S.s_cai_studio_5fdd3bd9}</Button>
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
      toast.success(S.s_da_go_studio_63706a8a);
      void client.invalidateQueries({ queryKey: ["app"] });
    } catch (error) {
      toast.error(S.s_chua_go_duoc_studio_1b3d65b8, { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  return (
    <MotionRegion as="div">
      <SettingsRow label={S.s_studio_tren_may_nay_e2fb04aa} hint={<>
        <p>{S.s_da_cai_e0159635}{status.gpu ? ` · ${status.gpu.name}` : ""}</p>
        <p className="mt-1 break-all">{status.root}</p>
      </>}>
        <Button size="sm" variant={armed ? "danger" : "ghost"} icon={Trash2} disabled={busy} onClick={() => void remove()}>
          {busy ? S.s_dang_go_eadfa314 : armed ? S.s_xac_nhan_go_80920dda : S.s_go_studio_832e6f10}
        </Button>
      </SettingsRow>
      {status.outdated.length > 0 && (
        <p className="mt-1 text-[0.8125rem] text-fg-2">
          {status.damaged?.length ? S.s_mat_0_file_da_bi_xoa_hay_hong_a1da54d6(status.damaged.join(", ")) : S.s_can_cap_nhat_0_ab9a2c84(status.outdated.join(", "))} -{" "}
          <button type="button" onClick={() => navigate("/studio")} className="font-medium text-accent-text underline">
            {status.damaged?.length ? S.s_sua_studio_2f99394d : S.s_cap_nhat_studio_b3acc7e7}
          </button>
          .
        </p>
      )}
      {/* Hậu quả của việc gỡ chỉ cần lúc đang xác nhận - không treo thường trực dưới nút. */}
      <MotionPresence open={armed}>
        <p className="pb-3 text-xs leading-snug text-fg-2 text-pretty">{S.s_xoa_runtime_model_1520_gb_giu_sach_va_ho_s_66d08224}</p>
      </MotionPresence>
    </MotionRegion>
  );
}

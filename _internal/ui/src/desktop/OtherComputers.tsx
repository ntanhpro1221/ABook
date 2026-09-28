import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Laptop, Radar, RefreshCw, Smartphone, Unplug } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { api } from "@/studio/api";
import { cn } from "@/shared/cn";
import { formatRelative } from "@/shared/format";
import { Button, IconButton, Skeleton } from "@/shared/ui";

// Máy tính khác (webui/remote_books.py): ghép bằng địa chỉ + mã 6 số đang hiện trên máy ấy - đúng mã điện thoại dùng - rồi
// thư viện của máy ấy hiện trong Thư viện của máy này ("Trên <máy>"). Chương tải về lần đầu nghe tới và được giữ lại, nên
// phần đã nghe vẫn nghe được khi máy kia tắt.

interface Computer {
  id: string;
  name: string;
  host: string;
  port: number;
  lastSeen?: number;
  error?: string;
}

interface ComputersView {
  name: string;
  computers: Computer[];
}

/** Máy tính ABook đang bật kết nối trong mạng (remote_books.discover - cùng cách điện thoại tìm máy tính). */
interface FoundComputer {
  name: string;
  host: string;
  port: number;
  paired: boolean;
  /** Điện thoại đang bật "Cho máy khác nghe thư viện này" (LibraryServer.kt) cũng trả lời. */
  kind?: "computer" | "phone";
}

export function OtherComputers() {
  const client = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["computers"], queryFn: () => api<ComputersView>("/api/computers") });
  const [address, setAddress] = useState("");
  const [code, setCode] = useState("");
  const done = (view: ComputersView) => {
    client.setQueryData(["computers"], view);
    void client.invalidateQueries({ queryKey: ["listen", "library"] });
  };
  const pair = useMutation({
    mutationFn: () => api<ComputersView>("/api/computers", { method: "POST", body: { address, code } }),
    onSuccess: (view) => {
      done(view);
      setCode("");
      toast.success("Đã ghép", { description: "Sách của máy ấy hiện trong Thư viện với nhãn “Trên <tên máy>”." });
    },
    onError: (error: Error) => toast.error("Chưa ghép được", { description: error.message }),
  });
  const refresh = useMutation({
    mutationFn: () => api<ComputersView>("/api/computers/refresh", { method: "POST" }),
    onSuccess: done,
  });
  const forget = useMutation({
    mutationFn: (id: string) => api<ComputersView>(`/api/computers/${id}`, { method: "DELETE" }),
    onSuccess: done,
  });
  const discover = useMutation({
    mutationFn: () => api<{ found: FoundComputer[] }>("/api/computers/discover"),
    onError: (error: Error) => toast.error("Không tìm được", { description: error.message }),
  });
  const codeInput = useRef<HTMLInputElement>(null);
  const choose = (found: FoundComputer) => {
    setAddress(`${found.host}:${found.port}`);
    codeInput.current?.focus();
  };
  if (isLoading || !data) return <Skeleton className="h-20" />;
  return (
    <div className="space-y-4">
      {data.computers.length > 0 && (
        <ul className="divide-y divide-line rounded-xl border border-line">
          {data.computers.map((computer) => (
            <li key={computer.id} className="flex items-center gap-3 px-3 py-2.5">
              <Laptop className="size-5 shrink-0 text-fg-2" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{computer.name}</div>
                <div className={cn("truncate text-xs", computer.error ? "text-danger" : "text-fg-2")}>
                  {computer.error
                    ? computer.error
                    : `${computer.host}:${computer.port}${computer.lastSeen ? ` · thấy ${formatRelative(computer.lastSeen)}` : ""}`}
                </div>
              </div>
              <IconButton label="Hỏi lại thư viện" icon={RefreshCw} size="sm" disabled={refresh.isPending} onClick={() => refresh.mutate()} />
              <IconButton label={`Thôi ghép ${computer.name}`} icon={Unplug} size="sm" onClick={() => forget.mutate(computer.id)} />
            </li>
          ))}
        </ul>
      )}
      <div className="space-y-2">
        <Button variant="secondary" icon={Radar} loading={discover.isPending} onClick={() => discover.mutate()}>
          Tìm máy trong mạng
        </Button>
        {discover.data &&
          (discover.data.found.length ? (
            <ul className="divide-y divide-line rounded-xl border border-line">
              {discover.data.found.map((found) => (
                <li key={`${found.host}:${found.port}`} className="flex items-center gap-3 px-3 py-2">
                  {found.kind === "phone" ? (
                    <Smartphone className="size-5 shrink-0 text-fg-2" aria-label="điện thoại" />
                  ) : (
                    <Laptop className="size-5 shrink-0 text-fg-2" aria-label="máy tính" />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{found.name}</div>
                    <div className="truncate text-xs text-fg-2">
                      {found.host}:{found.port}
                    </div>
                  </div>
                  {found.paired ? (
                    <span className="text-xs text-fg-2">Đã ghép</span>
                  ) : (
                    <Button size="sm" variant="ghost" onClick={() => choose(found)}>
                      Chọn
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs leading-relaxed text-fg-2 text-pretty">
              Không thấy máy nào. Trên máy kia, bật kết nối trong Cài đặt → Điện thoại và thiết bị; hai máy phải cùng mạng
              (qua Tailscale thì gõ địa chỉ Tailscale của máy kia).
            </p>
          ))}
      </div>
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          pair.mutate();
        }}
      >
        <label className="min-w-0 flex-1 text-xs text-fg-2" htmlFor="other-computer-address">
          Địa chỉ máy kia
          <input
            id="other-computer-address"
            value={address}
            onChange={(event) => setAddress(event.target.value)}
            placeholder="192.168.1.20"
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            className="mt-1 block h-9 w-full rounded-lg border border-line bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-accent"
          />
        </label>
        <label className="w-32 text-xs text-fg-2" htmlFor="other-computer-code">
          Mã 6 số
          <input
            id="other-computer-code"
            ref={codeInput}
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
            placeholder="123456"
            inputMode="numeric"
            autoComplete="off"
            className="tabular mt-1 block h-9 w-full rounded-lg border border-line bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-accent"
          />
        </label>
        <Button type="submit" size="md" variant="secondary" loading={pair.isPending} disabled={!address.trim() || code.replace(/\D/g, "").length !== 6}>
          Kết nối
        </Button>
      </form>
      <p className="text-xs leading-relaxed text-fg-3">
        Trên máy kia: Cài đặt → Điện thoại và thiết bị → bật “Cho phép điện thoại kết nối qua Wi-Fi” → “Ghép thiết bị mới”
        để lấy mã 6 số; địa chỉ máy ấy ghi ở dòng “Trình duyệt” ngay cạnh mã. Điện thoại Android: màn Tải sách → bật “Cho máy khác nghe thư viện này” → “Ghép máy mới”. Máy này tên
        “{data.name}” trong danh sách thiết bị đã ghép của máy kia.
      </p>
    </div>
  );
}

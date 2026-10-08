import { Layers, Plus, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/shared/cn";
import { formatNumber } from "@/shared/format";
import { Button } from "@/shared/ui";
import type { ScannedFile } from "@/studio/api";
import { addStart, moveStart, ranges, removeStart, startNumbers, volumeTitles, type VolumeProposal } from "@/studio/volumes";

const SOURCE_TEXT: Record<VolumeProposal["source"], string> = {
  folders: "mỗi thư mục là một tập",
  epubs: "mỗi file EPUB là một tập",
  headings: "các tiêu đề chương gọi tên tập",
};

function foldersIn(files: ScannedFile[]): number {
  return new Set(files.map((file) => file.path.slice(0, Math.max(file.path.lastIndexOf("/"), file.path.lastIndexOf("\\"))))).size;
}

/** Ô số chương của một chỗ cắt: gõ thoải mái, chỉ nhận khi rời ô / bấm Enter và số nằm giữa hai chỗ cắt bên cạnh. */
function NumberBox({ value, label, onCommit }: { value: number; label: string; onCommit: (value: number) => boolean }) {
  const [text, setText] = useState(String(value));
  const [bad, setBad] = useState(false);
  useEffect(() => {
    setText(String(value));
    setBad(false);
  }, [value]);
  const commit = () => {
    if (text.trim() === String(value)) return;
    const ok = /^\d+$/.test(text.trim()) && onCommit(Number(text.trim()));
    setBad(!ok);
    if (!ok) setText(String(value));
  };
  return (
    <input
      value={text}
      inputMode="numeric"
      aria-label={label}
      aria-invalid={bad}
      onChange={(event) => setText(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          commit();
        }
      }}
      className={cn(
        "h-8 w-16 rounded-lg border bg-bg px-2 text-center text-sm tabular-nums outline-none focus:border-accent",
        bad ? "border-danger" : "border-line",
      )}
    />
  );
}

/**
 * "Chia thành nhiều tập" (B7). Máy ĐỀ XUẤT chỗ cắt (thư mục / EPUB / tiêu đề "Tập N"); không bấm thì cả truyện vẫn là MỘT sách
 * (chủ sách 29-09: không bao giờ tự sửa nguồn). Bấm thì hiện danh sách tập: sửa chỗ cắt theo số chương (cột số ở danh sách
 * chương), thêm, bỏ. Tạo xong: tập 1 là sách thường, các tập sau là phần nối tiếp, tự chạy khi tập trước xong.
 */
export function VolumeSplit({
  ordered,
  excluded,
  files,
  proposal,
  title,
  value,
  onChange,
}: {
  /** Mọi chương theo thứ tự chia (kể cả chương đã bỏ tay) và các chương bỏ - chỗ cắt lưu theo đường dẫn nên sống sót qua việc bỏ chương. */
  ordered: ScannedFile[];
  excluded: string[];
  /** Các chương còn chọn, theo thứ tự chia: số chương ở đây là số ở cột đầu danh sách. */
  files: ScannedFile[];
  proposal: VolumeProposal | null | undefined;
  title: string;
  /** Đường dẫn chương đầu mỗi tập đang chọn; null = không chia. */
  value: string[] | null;
  onChange: (value: string[] | null) => void;
}) {
  const total = files.length;
  if (total < 2) return null;
  if (value === null) {
    if (!proposal) {
      return (
        <div className="mt-4">
          <Button size="sm" variant="ghost" icon={Layers} onClick={() => onChange([files[0].path])}>
            Chia thành nhiều phần
          </Button>
        </div>
      );
    }
    const shown = proposal.volumes.slice(0, 4);
    return (
      <div className="mt-4 flex gap-3 rounded-xl border border-line bg-panel p-4 text-sm">
        <Sparkles className="mt-0.5 size-4 shrink-0 text-accent-text" />
        <div className="min-w-0 flex-1">
          <p className="font-semibold">Gợi ý: truyện này có vẻ gồm {proposal.volumes.length} tập, làm thành {proposal.volumes.length} phần</p>
          <p className="mt-1 break-words text-fg-2">
            Máy thấy {SOURCE_TEXT[proposal.source]}:{" "}
            {shown.map((volume) => `${volume.label} (${formatNumber(volume.chapters)} chương)`).join(", ")}
            {proposal.volumes.length > shown.length ? ", …" : ""}. Hiện cả truyện được làm thành MỘT sách. Chia ra thì mỗi tập của
            truyện thành một phần, nối nhau như Làm tiếp: phần sau tự bắt đầu khi phần trước xong và mang giọng nhân vật, cách đọc tên
            sang. Chỗ cắt sửa được theo số chương.
          </p>
          <div className="mt-2.5 flex gap-2">
            <Button size="sm" variant="secondary" icon={Layers} onClick={() => onChange(proposal.volumes.map((volume) => volume.startPath))}>
              Chia thành nhiều phần
            </Button>
          </div>
        </div>
      </div>
    );
  }

  const starts = startNumbers(ordered, value, new Set(excluded));
  const parts = ranges(starts, total);
  const titles = volumeTitles(title || "Tên sách", parts.length);
  const proposed = new Map((proposal?.volumes ?? []).map((volume) => [volume.startPath, volume.label]));
  const commit = (next: number[] | null): boolean => {
    if (!next) return false;
    onChange(next.map((number) => files[number - 1].path));
    return true;
  };
  return (
    <section aria-labelledby="volumes-title" className="mt-4 rounded-xl border border-accent/40 bg-panel p-4 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="volumes-title" className="flex items-center gap-2 font-semibold">
          <Layers className="size-4 text-accent-text" /> {parts.length > 1 ? `Chia thành ${parts.length} phần` : "Chia thành mấy phần?"}
        </h3>
        <Button size="sm" variant="ghost" onClick={() => onChange(null)}>
          Không chia nữa
        </Button>
      </div>
      <p className="mt-1 text-fg-2">
        Mỗi phần là một sách trong Dự án: phần 1 như sách thường, phần sau nối tiếp, xếp hàng sau phần trước. Đổi “từ chương” để
        dời chỗ cắt.
        {parts.length === 1 && ` Hiện mới có một phần - điền chương mà phần 2 bắt đầu (từ chương 2 đến chương ${total}) ở ô dưới rồi bấm Thêm.`}
      </p>
      <ol className="mt-3 divide-y divide-line rounded-lg border border-line">
        {parts.map((part, index) => (
          <li key={part.start} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 px-3 py-2 sm:grid-cols-[minmax(0,1fr)_auto_90px_32px]">
            <div className="min-w-0">
              {/* Phần 1 giữ nguyên tên sách (là sách thường, như máy chủ đặt) - nên nói ra nó là phần 1; các phần sau đã có "· Phần N" trong tên. */}
              <div className="truncate font-medium max-sm:whitespace-normal max-sm:break-words">
                {titles[index]}
                {index === 0 && <span className="ml-2 text-xs font-normal text-fg-3">phần 1</span>}
              </div>
              <div className="truncate text-xs text-fg-2">
                {files[part.start - 1]?.firstLine || files[part.start - 1]?.name}
                {proposed.get(files[part.start - 1]?.path) ? ` · ${proposed.get(files[part.start - 1].path)}` : ""}
              </div>
              {foldersIn(files.slice(part.start - 1, part.end)) > 1 && (
                // Dây chuyền xếp chương theo TÊN file: chương của hai thư mục trong một tập thì xen nhau (máy chủ từ chối khi tạo).
                <div className="text-xs text-warning">Gồm chương của nhiều thư mục - thứ tự đọc có thể lệch. Dời chỗ cắt về ranh giới giữa hai thư mục.</div>
              )}
            </div>
            <label className="flex items-center gap-2 text-fg-2">
              từ chương
              {index === 0 ? (
                <span className="grid h-8 w-16 place-items-center tabular-nums text-fg">1</span>
              ) : (
                <NumberBox
                  value={part.start}
                  label={`Phần ${index + 1} bắt đầu từ chương`}
                  onCommit={(number) => commit(moveStart(starts, index, number, total))}
                />
              )}
            </label>
            <span className="tabular text-right text-xs text-fg-2 max-sm:col-start-1 max-sm:text-left">{formatNumber(part.chapters)} chương</span>
            {index > 0 ? (
              <button
                type="button"
                aria-label={`Bỏ chỗ cắt trước ${titles[index]}`}
                title="Gộp vào phần trước"
                onClick={() => commit(removeStart(starts, index))}
                className="grid size-8 place-items-center rounded-md text-fg-2 hover:bg-hover hover:text-danger"
              >
                <Trash2 className="size-4" />
              </button>
            ) : (
              <span />
            )}
          </li>
        ))}
      </ol>
      <AddCut starts={starts} total={total} onAdd={(number) => commit(addStart(starts, number, total))} />
    </section>
  );
}

function AddCut({ starts, total, onAdd }: { starts: number[]; total: number; onAdd: (number: number) => boolean }) {
  const [text, setText] = useState("");
  const [bad, setBad] = useState(false);
  const add = () => {
    const ok = /^\d+$/.test(text.trim()) && onAdd(Number(text.trim()));
    setBad(!ok);
    if (ok) setText("");
  };
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 text-fg-2">
      <span>Thêm chỗ cắt: phần mới bắt đầu từ chương</span>
      <input
        value={text}
        inputMode="numeric"
        aria-label="Thêm phần từ chương"
        aria-invalid={bad}
        placeholder={`từ 2 đến ${total}`}
        onChange={(event) => {
          setText(event.target.value);
          setBad(false);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            add();
          }
        }}
        className={cn(
          "h-8 w-28 rounded-lg border bg-bg px-2 text-center text-sm tabular-nums outline-none placeholder:text-fg-3 focus:border-accent",
          bad ? "border-danger" : "border-line",
        )}
      />
      <Button size="sm" variant="secondary" icon={Plus} disabled={!text.trim()} onClick={add}>
        Thêm
      </Button>
      {bad && (
        <span role="alert" className="text-danger">
          {starts.length >= 99 ? "Tối đa 99 phần." : "Chương này đã là chỗ cắt, hay không nằm trong 2 – " + total + "."}
        </span>
      )}
    </div>
  );
}

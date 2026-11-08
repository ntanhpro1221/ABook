import { S } from "../shared/strings.generated";
import { MoreInfo } from "@/shared/SettingsNav";
import { MotionRegion } from "@/shared/MotionRegion";
import { AnimatedRows } from "@/shared/MotionPresence";
import { Layers, Plus, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/shared/cn";
import { formatNumber } from "@/shared/format";
import { Button } from "@/shared/ui";
import type { ScannedFile } from "@/studio/api";
import { addStart, moveStart, ranges, removeStart, startNumbers, volumeTitles, type VolumeProposal } from "@/studio/volumes";

const SOURCE_TEXT: Record<VolumeProposal["source"], string> = {
  folders: S.s_moi_thu_muc_la_mot_tap_5f476863,
  epubs: S.s_moi_file_epub_la_mot_tap_42de53c4,
  headings: S.s_cac_tieu_de_chuong_goi_ten_tap_2ed33746,
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
        "h-8 w-16 rounded-control border bg-bg px-2 text-center text-sm tabular-nums outline-none focus:border-focus",
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
  if (total < 2) return <MotionRegion />;
  if (value === null) {
    if (!proposal) {
      return (
        <MotionRegion as="div" className="mt-4">
          <Button size="sm" variant="ghost" icon={Layers} onClick={() => onChange([files[0].path])}>{S.s_chia_thanh_nhieu_phan_af52ab82}</Button>
        </MotionRegion>
      );
    }
    const shown = proposal.volumes.slice(0, 4);
    return (
      <MotionRegion as="div" className="mt-4 flex gap-3 py-4 text-sm">
        <Sparkles className="mt-line-icon size-4 shrink-0 text-accent-text" />
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{S.s_chia_e1f5ebcd}{proposal.volumes.length}{S.s_phan_67dc9fc9}</p>
          <p className="mt-1 text-fg-2">{S.s_noi_cac_phan_giu_giong_va_cach_doc_ten_ae9d0eb0}</p>
          <MoreInfo>{S.s_may_thay_ed1e7e9f}{SOURCE_TEXT[proposal.source]}:{" "}
            {shown.map((volume) => S.s_0_1_chuong_a776ede8(volume.label, formatNumber(volume.chapters))).join(", ")}
            {proposal.volumes.length > shown.length ? ", …" : ""}.
            {" "}{S.s_chua_chia_thi_ca_truyen_la_mot_sach_moi_ph_5e6fe008}</MoreInfo>
          <div className="mt-2.5 flex gap-2">
            <Button size="sm" variant="ghost" icon={Layers} onClick={() => onChange(proposal.volumes.map((volume) => volume.startPath))}>{S.s_chia_thanh_nhieu_phan_af52ab82}</Button>
          </div>
        </div>
      </MotionRegion>
    );
  }

  const starts = startNumbers(ordered, value, new Set(excluded));
  const parts = ranges(starts, total);
  const titles = volumeTitles(title || S.s_ten_sach_d54846eb, parts.length);
  const proposed = new Map((proposal?.volumes ?? []).map((volume) => [volume.startPath, volume.label]));
  const commit = (next: number[] | null): boolean => {
    if (!next) return false;
    onChange(next.map((number) => files[number - 1].path));
    return true;
  };
  return (
    <MotionRegion as="section" aria-labelledby="volumes-title" className="mt-4 py-4 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="volumes-title" className="flex items-center gap-2 font-semibold">
          <Layers className="size-4 text-accent-text" /> {parts.length > 1 ? S.s_chia_thanh_0_phan_db0187a5(parts.length) : S.s_chia_thanh_may_phan_1bf1cf9e}
        </h3>
        <Button size="sm" variant="ghost" onClick={() => onChange(null)}>{S.s_khong_chia_nua_3d6b48ed}</Button>
      </div>
      <p className="mt-1 text-fg-2">{S.s_moi_phan_thanh_mot_sach_noi_tiep_chon_chuo_d7604c1a}</p>
      {/* Thêm / bỏ chỗ cắt: hàng của phần mở / khép tại chỗ (useListPresence), không mờ cả khung; đổi trong hàng thì hàng tự mờ qua.
          Hàng đang khép giữ số phần / tên cuối của nó. */}
      <div data-motion-live="">
      <AnimatedRows as="ol" className="mt-3 divide-y divide-line" items={parts.map((part, index) => ({ ...part, index, title: titles[index] }))} keyOf={(part) => String(part.start)}>
        {({ index, title, ...part }) => (
          <MotionRegion className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 py-2 sm:grid-cols-[minmax(0,1fr)_auto_90px_32px]">
            <div className="min-w-0">
              {/* Phần 1 giữ nguyên tên sách (là sách thường, như máy chủ đặt) - nên nói ra nó là phần 1; các phần sau đã có "· Phần N" trong tên. */}
              <div className="truncate font-medium max-sm:whitespace-normal max-sm:break-words">
                {title}
                {index === 0 && <span className="ml-2 text-xs font-normal text-fg-3">{S.s_phan_1_81023e6c}</span>}
              </div>
              <div className="truncate text-xs text-fg-2">
                {files[part.start - 1]?.firstLine || files[part.start - 1]?.name}
                {proposed.get(files[part.start - 1]?.path) ? ` · ${proposed.get(files[part.start - 1].path)}` : ""}
              </div>
              {foldersIn(files.slice(part.start - 1, part.end)) > 1 && (
                // Dây chuyền xếp chương theo TÊN file: chương của hai thư mục trong một tập thì xen nhau (máy chủ từ chối khi tạo).
                <div className="text-xs text-warning">{S.s_doi_cho_cat_ve_ranh_gioi_thu_muc_de_giu_th_b3f10724}</div>
              )}
            </div>
            <label className="flex items-center gap-2 text-fg-2">{S.s_tu_chuong_e2536d03}{index === 0 ? (
                <span className="grid h-8 w-16 place-items-center tabular-nums text-fg">1</span>
              ) : (
                <NumberBox
                  value={part.start}
                  label={S.s_phan_0_bat_dau_tu_chuong_970b282f(index + 1)}
                  onCommit={(number) => commit(moveStart(starts, index, number, total))}
                />
              )}
            </label>
            <span className="tabular text-right text-xs text-fg-2 max-sm:col-start-1 max-sm:text-left">{formatNumber(part.chapters)}{S.s_chuong_9e6a01dc}</span>
            {index > 0 ? (
              <button
                type="button"
                aria-label={S.s_bo_cho_cat_truoc_0_5082349b(title)}
                title={S.s_gop_vao_phan_truoc_b2b49634}
                onClick={() => commit(removeStart(starts, index))}
                className="grid size-8 place-items-center rounded-control text-fg-2 hover:bg-hover hover:text-danger"
              >
                <Trash2 className="size-4" />
              </button>
            ) : (
              <span />
            )}
          </MotionRegion>
        )}
      </AnimatedRows>
      </div>
      <AddCut starts={starts} total={total} onAdd={(number) => commit(addStart(starts, number, total))} />
    </MotionRegion>
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
    <MotionRegion>
    <div className="mt-3 flex flex-wrap items-center gap-2 text-fg-2">
      <span>{S.s_cat_tu_chuong_43026b03}</span>
      <input
        value={text}
        inputMode="numeric"
        aria-label={S.s_them_phan_tu_chuong_cba5b511}
        aria-invalid={bad}
        placeholder={S.s_tu_2_den_0_206d9e4a(total)}
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
          "h-8 w-28 rounded-control border bg-bg px-2 text-center text-sm tabular-nums outline-none placeholder:text-fg-3 focus:border-focus",
          bad ? "border-danger" : "border-line",
        )}
      />
      <Button size="sm" variant="ghost" icon={Plus} disabled={!text.trim()} onClick={add}>{S.s_them_dd92626f}</Button>
      {bad && (
        <span role="alert" className="text-danger">
          {starts.length >= 99 ? S.s_toi_da_99_phan_9661ebdc : S.s_chuong_nay_da_la_cho_cat_hay_khong_nam_tro_1005c9e5 + total + "."}
        </span>
      )}
    </div>
    </MotionRegion>
  );
}

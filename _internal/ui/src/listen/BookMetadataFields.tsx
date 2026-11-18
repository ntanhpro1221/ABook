import { useLayoutEffect, useRef, type TextareaHTMLAttributes } from "react";
import { S } from "@/shared/strings.generated";
import type { BookMetadata } from "./BookMetadata";

/** Ô chữ của người dùng không bao giờ cắt: cao theo nội dung (tên tác giả dài xuống dòng và ô cao thêm, như FormField của Qt và BookField của
 *  Android - UI_PARITY "Sửa sách"); `rows` là chiều cao tối thiểu. */
function GrowingTextarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const box = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    const element = box.current;
    if (!element) return;
    element.style.height = "auto";
    if (element.scrollHeight > 0) element.style.height = `${element.scrollHeight + element.offsetHeight - element.clientHeight}px`;
  }, [props.value]);
  return <textarea ref={box} {...props} />;
}

export function BookMetadataFields({ value, onChange }: { value: BookMetadata; onChange: (value: BookMetadata) => void }) {
  const input = "w-full rounded-control border border-line bg-bg px-3 py-2 text-sm outline-none focus:border-focus";
  const fields = [["author", S.s_tac_gia_0ec4731b], ["illustrator", S.s_bookmeta_illustrator], ["altTitles", S.s_bookmeta_alt_titles], ["genres", S.s_bookmeta_genres], ["summary", S.s_tom_tat_b4bb3064]] as const;
  return <div className="space-y-3">{fields.map(([key, label]) => <label key={key} className="block space-y-1 text-sm">
    <span>{label}</span>
    <GrowingTextarea aria-label={label} placeholder={key === "author" ? S.s_khong_ro_tac_gia_baaa8118 : undefined} rows={key === "summary" ? 6 : key === "altTitles" || key === "genres" ? 2 : 1} className={`${input} resize-none overflow-hidden`}
      value={Array.isArray(value[key]) ? value[key].join("\n") : value[key] ?? ""}
      onChange={event => onChange({ ...value, [key]: key === "altTitles" || key === "genres" ? event.target.value.split("\n") : event.target.value })} />
  </label>)}
    <label className="block space-y-1 text-sm"><span>{S.s_nguon_c76d57b3}</span><input aria-label={S.s_nguon_c76d57b3} className={input} value={value.source?.url ?? ""} onChange={event => onChange({ ...value, source: { url: event.target.value, site: value.source?.site ?? "" } })} /></label>
    <label className="block space-y-1 text-sm"><span>{S.s_bookmeta_source_site}</span><input aria-label={S.s_bookmeta_source_site} className={input} value={value.source?.site ?? ""} onChange={event => onChange({ ...value, source: { url: value.source?.url ?? "", site: event.target.value } })} /></label>
  </div>;
}

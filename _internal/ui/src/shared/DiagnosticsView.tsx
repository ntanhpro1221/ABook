import { S } from "./strings.generated";
import { useLayoutEffect, useRef } from "react";
import { emptyLogNote, failureDetails, logLines, summaryRows, workProgressRows, type DiagnosticsReport } from "./diagnostics";
import { MoreInfo } from "./SettingsNav";
import { useFadeScroller } from "./scrollFade";

/** Bản chẩn đoán của điện thoại cho người đọc: tóm tắt từng mục rồi nhật ký cuộn được (dòng mới nhất ở cuối, cuộn sẵn xuống đó). Dùng chung hộp
 *  "Chẩn đoán" của máy tính và màn Cài đặt → Chẩn đoán của điện thoại. */
export function DiagnosticsView({ report }: { report: DiagnosticsReport }) {
  const scrollFade = useFadeScroller<HTMLPreElement>();
  const rows = [...summaryRows(report), ...workProgressRows(report)];
  const app = logLines(report, "log");
  const cat = logLines(report, "logcat");
  const errors = failureDetails(report);
  return (
    <div className="space-y-4">
      {rows.length > 0 && (
        <dl className="divide-y divide-line text-sm">
          {rows.map((row) => (
            <div key={row.label} className="flex flex-wrap gap-x-4 gap-y-1 py-2">
              <dt className="w-44 shrink-0 text-fg-2">{row.label}</dt>
              <dd className="min-w-0 flex-1 [overflow-wrap:anywhere]">{row.value}</dd>
            </div>
          ))}
        </dl>
      )}
      {errors.length > 0 && <MoreInfo label={S.s_chi_tiet_ky_thuat_f27eb5f6}>
        <pre ref={scrollFade.ref} style={scrollFade.style} className="max-h-72 select-text overflow-auto whitespace-pre-wrap [overflow-wrap:anywhere]">{errors.map(row => `${row.label}: ${row.value}`).join("\n")}</pre>
      </MoreInfo>}
      <LogBox title={S.s_nhat_ky_cua_abook_0_dong_9a189053(app.length)} lines={app} empty={emptyLogNote(report, "log")} open />
      {(cat.length > 0 || report.logcat !== undefined) && <LogBox title={S.s_nhat_ky_he_thong_cua_app_0_dong_59b6a624(cat.length)} lines={cat} empty={emptyLogNote(report, "logcat")} />}
      {report.truncated && <p className="text-xs text-fg-3">{S.s_nhat_ky_dai_nen_da_cat_bot_phan_cu_nhat_ad1b7371}</p>}
    </div>
  );
}

function LogBox({ title, lines, empty, open }: { title: string; lines: string[]; empty: string; open?: boolean }) {
  const pre = useRef<HTMLPreElement | null>(null);
  const scrollFade = useFadeScroller(pre);
  // Cuộn sẵn xuống cuối mỗi lần đọc lại: dòng mới nhất là dòng cần xem trước.
  useLayoutEffect(() => {
    if (pre.current) pre.current.scrollTop = pre.current.scrollHeight;
  }, [lines]);
  return (
    <details open={open} className="">
      <summary className="cursor-pointer py-2 text-sm font-medium">{title}</summary>
      {lines.length ? (
        <pre
          ref={scrollFade.ref}
          style={scrollFade.style}
          tabIndex={0}
          aria-label={title}
          className="max-h-72 select-text overflow-auto border-t border-line py-2 text-caption leading-snug text-fg-2"
        >
          {lines.join("\n")}
        </pre>
      ) : (
        <p className="border-t border-line py-2 text-xs text-fg-3">{empty}</p>
      )}
    </details>
  );
}

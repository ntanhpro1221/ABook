import { emptyLogNote, logLines, summaryRows, type DiagnosticsReport } from "./diagnostics";

/** Bản chẩn đoán của điện thoại cho người đọc: tóm tắt từng mục rồi nhật ký cuộn được (dòng mới nhất ở cuối, cuộn sẵn xuống đó). Dùng chung hộp
 *  "Chẩn đoán" của máy tính và màn Cài đặt → Chẩn đoán của điện thoại. */
export function DiagnosticsView({ report }: { report: DiagnosticsReport }) {
  const rows = summaryRows(report);
  const app = logLines(report, "log");
  const cat = logLines(report, "logcat");
  return (
    <div className="space-y-4">
      {rows.length > 0 && (
        <dl className="divide-y divide-line rounded-xl border border-line text-sm">
          {rows.map((row) => (
            <div key={row.label} className="flex flex-wrap gap-x-4 gap-y-0.5 px-3 py-2">
              <dt className="w-44 shrink-0 text-fg-2">{row.label}</dt>
              <dd className="min-w-0 flex-1 [overflow-wrap:anywhere]">{row.value}</dd>
            </div>
          ))}
        </dl>
      )}
      <LogBox title={`Nhật ký của ABook (${app.length} dòng)`} lines={app} empty={emptyLogNote(report, "log")} open />
      {(cat.length > 0 || report.logcat !== undefined) && <LogBox title={`Nhật ký hệ thống của app (${cat.length} dòng)`} lines={cat} empty={emptyLogNote(report, "logcat")} />}
      {report.truncated && <p className="text-xs text-fg-3">Nhật ký dài nên đã cắt bớt phần cũ nhất.</p>}
    </div>
  );
}

function LogBox({ title, lines, empty, open }: { title: string; lines: string[]; empty: string; open?: boolean }) {
  return (
    <details open={open} className="rounded-xl border border-line">
      <summary className="cursor-pointer px-3 py-2 text-sm font-medium">{title}</summary>
      {lines.length ? (
        // Cuộn sẵn xuống cuối: dòng mới nhất là dòng cần xem trước.
        <pre
          ref={(node) => {
            if (node) node.scrollTop = node.scrollHeight;
          }}
          tabIndex={0}
          aria-label={title}
          className="max-h-72 select-text overflow-auto border-t border-line px-3 py-2 text-[0.6875rem] leading-snug text-fg-2"
        >
          {lines.join("\n")}
        </pre>
      ) : (
        <p className="border-t border-line px-3 py-2 text-xs text-fg-3">{empty}</p>
      )}
    </details>
  );
}

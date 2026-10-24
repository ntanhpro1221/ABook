import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { DiagnosticsView } from "./DiagnosticsView";
import { workProgressRows, type DiagnosticsReport } from "./diagnostics";

const job = (progress: Record<string, string>, id = "private-worker-id") => ({ id, state: "RUNNING", tags: ["BookDownloadWorker"], attempts: 0, stopReason: 0, progress });

describe("chi tiết chẩn đoán dùng chung", () => {
  it("lỗi thu thập chỉ nói ngắn ở tóm tắt, chi tiết nằm trong phần mở rộng", () => {
    const html = renderToStaticMarkup(<DiagnosticsView report={{ share: { error: "UninitializedPropertyAccessException: devicesFile" }, playback: { error: "" } }} />);
    expect(html.match(/<dl[^>]*>[\s\S]*?<\/dl>/)![0]).not.toContain("UninitializedPropertyAccessException");
    expect(html).toContain("Chi tiết kỹ thuật");
    expect(html).toContain("UninitializedPropertyAccessException: devicesFile");
    expect(html).toContain("chưa mở cuốn nào");
    expect(html).toContain("inert");
  });
  it("hiện tiến độ và pha riêng từng việc; tiến độ mới làm màn hình đổi", () => {
    const report: DiagnosticsReport = { work: [job({ done: "3", total: "10", phase: "download" }), { ...job({ done: "0", total: "2", phase: "encode" }, "second"), tags: ["M4bExportWorker"] }] };
    const html = renderToStaticMarkup(<DiagnosticsView report={report} />);
    for (const value of ["Việc 1", "Việc 2", "Tải sách", "Xuất M4B", "3/10", "0/2", "Pha: đang tải", "Pha: đang ghép âm thanh"]) expect(html).toContain(value);
    expect(html).not.toContain("private-worker-id");
    expect(renderToStaticMarkup(<DiagnosticsView report={{ work: [job({ done: "9", total: "10", phase: "verify" })] }} />)).toContain("9/10");
  });

  it("nhận thiếu pha hoặc số đếm; bỏ số sai và phần lỗi", () => {
    expect(workProgressRows({ work: [job({ phase: "prepare" }), job({ done: "2" }), job({ total: "5" }), job({ done: "NaN", total: "-1" }), job({})] }).map((row) => row.value)).toEqual([
      "Tải sách · đang chạy · Pha: đang chuẩn bị", "Tải sách · đang chạy · đã làm 2", "Tải sách · đang chạy · tổng 5",
    ]);
    expect(workProgressRows({ work: { error: "không đọc được" } })).toEqual([]);
    expect(workProgressRows({})).toEqual([]);
  });

  it("hiện phục hồi, thời điểm, bản giữ lại và chặn lưu", () => {
    const html = renderToStaticMarkup(<DiagnosticsView report={{ dataRecovery: { savingBlocked: true, notices: [{ kind: "recovered", at: 1700000000000, preservedFile: "state.json.corrupt-1700000000000-***", pending: true }] } }} />);
    for (const value of ["Phục hồi dữ liệu", "dữ liệu của bạn", "đã giữ bản cũ", "state.json.corrupt-", "chưa lưu cảnh báo", "2023"]) expect(html).toContain(value);
  });
});

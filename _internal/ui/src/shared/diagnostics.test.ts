import { describe, expect, it } from "vitest";
import { emptyLogNote, logLines, reportFileName, summaryRows, type DiagnosticsReport } from "./diagnostics";

// Bản chẩn đoán của điện thoại (Diagnostics.kt) đọc cho người: tóm tắt từng mục, phần lỗi nói "không đọc được", bản cũ thiếu mục thì bỏ mục.

const FULL: DiagnosticsReport = {
  schema: 1,
  app: { versionName: "0.4.133", versionCode: 4133, debug: false },
  device: { sdk: 34, release: "14", manufacturer: "OPPO", model: "CPH2573" },
  time: { epochMillis: Date.UTC(2026, 9, 23, 5, 7), timezone: "Asia/Ho_Chi_Minh" },
  battery: { percent: 63, charging: false },
  network: { connected: true, wifi: false, cellular: true, vpn: true, validated: true, metered: true },
  storage: { freeBytes: 12 * 1024 ** 3, totalBytes: 128 * 1024 ** 3 },
  notifications: { enabled: true },
  power: { ignoringBatteryOptimizations: false, backgroundRestricted: true, powerSave: false },
  playback: { bookTitle: "Tắt đèn", chapterId: 3, position: 125, playing: true },
  work: [
    { id: "a", state: "RUNNING", tags: ["Mp3ExportWorker"], attempts: 0, stopReason: -256, progress: {} },
    { id: "b", state: "ENQUEUED", tags: ["BookDownloadWorker"], attempts: 1, stopReason: -256, progress: {} },
    { id: "c", state: "FAILED", tags: ["M4bExportWorker"], attempts: 0, stopReason: 4, progress: {} },
  ],
  share: { running: true, pairedDevices: 2 },
  exitReasons: [{ reason: "LOW_MEMORY (hệ thống thiếu bộ nhớ)", code: 3, description: "", timestamp: Date.UTC(2026, 9, 22, 20, 0), importance: "CACHED", pssKb: 1, rssKb: 2 }],
  crashes: [{ name: "crash-1.txt", text: "x" }],
  log: ["dòng 1", "dòng 2"],
  logcat: ["I/x: y"],
};

const byLabel = (report: DiagnosticsReport) => Object.fromEntries(summaryRows(report).map((row) => [row.label, row.value]));

describe("summaryRows", () => {
  it("tóm tắt bản app, máy, pin, mạng, việc nền và lần tắt gần nhất", () => {
    const rows = byLabel(FULL);
    expect(rows["Bản ABook"]).toBe("0.4.133 (4133)");
    expect(rows["Điện thoại"]).toBe("OPPO CPH2573 · Android 14 (API 34)");
    expect(rows["Pin"]).toBe("63%");
    expect(rows["Mạng"]).toBe("di động + VPN · tính cước");
    expect(rows["Chỗ trống"]).toContain("12 GB");
    expect(rows["Thông báo"]).toBe("đang bật");
    expect(rows["Chạy nền"]).toBe("miễn tối ưu pin: không · bị hạn chế chạy nền");
    expect(rows["Đang nghe"]).toBe("Tắt đèn · chương 3 · 2 phút 5 giây · đang phát");
    expect(rows["Việc nền"]).toBe("1 đang chạy · 1 đang chờ · 1 hỏng");
    expect(rows["Cho máy khác nghe thư viện"]).toBe("đang bật · 2 máy đã ghép");
    expect(rows["Lần tắt gần nhất"]).toContain("LOW_MEMORY");
    expect(rows["Lần văng"]).toBe("1 lần được ghi lại");
  });

  it("phần lỗi nói không đọc được, phần thiếu thì bỏ mục, phần còn lại vẫn ra", () => {
    const rows = byLabel({ schema: 1, app: { versionName: "0.4.133" }, battery: { error: "SecurityException: x" }, network: { connected: false } });
    expect(rows["Pin"]).toBe("không đọc được (SecurityException: x)");
    expect(rows["Mạng"]).toBe("chưa có mạng");
    expect(rows["Bản ABook"]).toBe("0.4.133");
    expect(rows["Điện thoại"]).toBeUndefined();
    expect(rows["Việc nền"]).toBeUndefined();
  });

  it("chưa mở cuốn nào, không có việc nền, thư viện không chia sẻ", () => {
    const rows = byLabel({ playback: {}, work: [], share: { running: false, lastError: "Cổng 47630 đang bận" } });
    expect(rows["Đang nghe"]).toBe("chưa mở cuốn nào");
    expect(rows["Việc nền"]).toBe("không có việc nào");
    expect(rows["Cho máy khác nghe thư viện"]).toBe("đang tắt (Cổng 47630 đang bận)");
  });
});

describe("nhật ký và tên file", () => {
  it("logLines trả mảng dòng; phần lỗi hay thiếu thì rỗng kèm câu nói lý do", () => {
    expect(logLines(FULL)).toEqual(["dòng 1", "dòng 2"]);
    expect(logLines(FULL, "logcat")).toEqual(["I/x: y"]);
    expect(logLines({ log: { error: "IOException: x" } })).toEqual([]);
    expect(emptyLogNote({ log: { error: "IOException: x" } })).toBe("không đọc được (IOException: x)");
    expect(emptyLogNote({})).toBe("Chưa có dòng nào.");
  });

  it("tên file lưu có tên máy và giờ, không có ký tự Windows cấm", () => {
    const name = reportFileName("Pixel: của/tôi?", new Date(2026, 9, 23, 5, 7, 9));
    expect(name).toBe("abook-nhat-ky-Pixel-của-tôi-20261023-050709.json");
    expect(reportFileName("???", new Date(2026, 0, 2, 3, 4, 5))).toBe("abook-nhat-ky-dien-thoai-20260102-030405.json");
  });
});

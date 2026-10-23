import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

// Hộp "Chẩn đoán" của máy tính (desktop/PhoneDiagnostics.tsx): hiện tóm tắt + nhật ký của điện thoại đã ghép; lỗi nói rõ điện thoại cần bản mới hơn,
// hay điện thoại chưa bật chia sẻ / khác mạng.
vi.mock("@/studio/data", () => ({ pickFolder: vi.fn(), useAppInfo: () => ({ data: { dialogs: true } }) }));

import type { DiagnosticsReport } from "@/shared/diagnostics";
import { ApiError } from "@/studio/api";
import { OWN_DIAGNOSTICS_HINT, OWN_DIAGNOSTICS_MORE, OwnDiagnostics } from "./OwnDiagnostics";
import { DiagnosticsBody, NEEDS_NEWER_TITLE, failureView } from "./PhoneDiagnostics";

const report: DiagnosticsReport = {
  schema: 1,
  app: { versionName: "0.4.133", versionCode: 4133 },
  device: { sdk: 34, release: "14", manufacturer: "OPPO", model: "CPH2573" },
  battery: { percent: 41, charging: true },
  network: { connected: true, cellular: true, vpn: true, validated: true },
  work: [{ id: "a", state: "RUNNING", tags: ["Mp3ExportWorker"], attempts: 0, stopReason: -256, progress: {} }],
  exitReasons: [{ reason: "CRASH (văng)", code: 4, description: "", timestamp: 1_700_000_000_000, importance: "FOREGROUND", pssKb: 1, rssKb: 2 }],
  log: ["2026-10-23T05:07:09.000+0700 W Playback 12/main: lỗi phát", "dòng thứ hai"],
};

describe("hộp Chẩn đoán điện thoại", () => {
  it("hiện bản app, Android, pin, mạng, việc nền, lần chết gần nhất và nhật ký cuộn được", () => {
    const html = renderToStaticMarkup(<DiagnosticsBody report={report} />);
    for (const text of ["0.4.133 (4133)", "OPPO CPH2573 · Android 14", "41% · đang sạc", "di động + VPN", "1 đang chạy", "CRASH (văng)", "lỗi phát", "dòng thứ hai"]) {
      expect(html).toContain(text);
    }
    expect(html).toContain("Nhật ký của ABook (2 dòng)");
    expect(html).toContain("overflow-auto");
  });

  it("điện thoại bản cũ (404): nói cần bản ABook mới hơn, không đổ lỗi cho mạng", () => {
    const error = new ApiError(502, "Pixel: điện thoại cần bản ABook mới hơn (bản này chưa biết gửi nhật ký chẩn đoán)", { reason: "needs-newer" });
    expect(failureView(error).title).toBe(NEEDS_NEWER_TITLE);
    const html = renderToStaticMarkup(<DiagnosticsBody error={error} />);
    expect(html).toContain("Điện thoại cần bản ABook mới hơn");
    expect(html).toContain("Cập nhật ABook trên điện thoại");
    expect(html).not.toContain("Tailscale");
    expect(html).toContain('role="alert"');
  });

  it("không với tới điện thoại: câu của máy chủ kèm cách khắc phục (bật chia sẻ, cùng mạng)", () => {
    const error = new ApiError(502, "Không kết nối được máy Pixel");
    const html = renderToStaticMarkup(<DiagnosticsBody error={error} />);
    expect(html).toContain("Không kết nối được máy Pixel");
    expect(html).toContain("Cho máy khác nghe thư viện này");
    expect(html).toContain("Tailscale");
  });

  it("đang tải: khung chờ; chưa có gì thì không hiện gì", () => {
    expect(renderToStaticMarkup(<DiagnosticsBody loading />)).not.toBe("");
    expect(renderToStaticMarkup(<DiagnosticsBody />).replace(/<[^>]+>/g, "")).toBe("");
  });
});

describe("Gửi nhật ký của máy tính", () => {
  it("nói rõ gói có gì, không có gì và app không tự gửi đi", () => {
    const html = renderToStaticMarkup(<OwnDiagnostics />);
    expect(html).toContain("Gửi nhật ký");
    expect(OWN_DIAGNOSTICS_MORE).toContain("nhận ra được");
    expect(OWN_DIAGNOSTICS_HINT).toContain("Xem lại trước khi gửi");
    expect(OWN_DIAGNOSTICS_MORE).not.toContain("không có mật khẩu");
    expect(OWN_DIAGNOSTICS_HINT).toContain("bạn tự gửi đi");
    expect(html).toContain("Tìm hiểu thêm");
  });
});

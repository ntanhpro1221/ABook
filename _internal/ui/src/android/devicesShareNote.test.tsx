import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it, vi } from "vitest";

// Trang chia sẻ thư viện (DevicesScreen.SharePanel) nhắc "cho ABook chạy nền" như các khung xuất (soát a107 F5): chỉ khi đang chia sẻ; việc ẩn khi
// ABook đã được cho chạy nền là của BackgroundNote (backgroundNote.test.tsx). Plugin native là bản giả.
vi.mock("./plugins", () => ({ EbookLibrary: {}, EbookPlayer: {}, ReadAloud: {} }));
vi.mock("./BackgroundNote", () => ({
  BackgroundNote: (words: { note?: string; action?: string }) => <div data-testid="background-note" data-action={words.action}>{words.note}</div>,
}));

import { SharePanel } from "./DevicesScreen";

const status = (running: boolean) => ({ running, name: "Máy", port: 47630, addresses: [], pairing: null, blocked: false, devices: [], error: "" });

function render(running: boolean) {
  const client = new QueryClient();
  client.setQueryData(["share"], status(running));
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <SharePanel />
    </QueryClientProvider>,
  );
}

it("đang chia sẻ: có ghi chú chạy nền nói việc chia sẻ, không nói việc xuất", () => {
  const html = render(true);
  expect(html).toContain('data-testid="background-note"');
  expect(html).toContain("tạm dừng chia sẻ");
  expect(html).not.toContain("Xuất sách dài");
});

it("chưa bật chia sẻ: không nhắc", () => {
  expect(render(false)).not.toContain('data-testid="background-note"');
});

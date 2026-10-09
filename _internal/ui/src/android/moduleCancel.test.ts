import { beforeEach, describe, expect, it, vi } from "vitest";

// Nút Huỷ khi tải giọng VieNeu trên điện thoại (thẻ trong Cài đặt và khối lỗi của trình phát): cầu WebView → Kotlin `vieneuCancel` (VoiceModule.cancel).
// Thẻ chỉ hiện nút khi backend có `cancel`, nên điện thoại phải nối nó; phần dừng-giữ `.part`-tải tiếp có test JVM riêng (VieneuModuleTest, PinnedFilesTest).
const readAloud = vi.hoisted(() => ({ vieneuStatus: vi.fn(), vieneuStart: vi.fn(), vieneuMeasure: vi.fn(), vieneuRemove: vi.fn(), vieneuCancel: vi.fn(), voices: vi.fn() }));
vi.mock("./plugins", () => ({ ReadAloud: readAloud, EbookLibrary: {}, EbookPlayer: {} }));
vi.mock("@capacitor/core", () => ({ Capacitor: { convertFileSrc: (path: string) => path } }));

import { phoneVieneu } from "./androidSource";

beforeEach(() => vi.resetAllMocks());

describe("phoneVieneu.cancel", () => {
  it("asks the native core to stop and returns the status it answers with (cancelled, back to missing)", async () => {
    const status = { state: "missing", cancelled: true, cancellable: true };
    readAloud.vieneuCancel.mockResolvedValue(status);
    expect(phoneVieneu.cancel).toBeTypeOf("function");
    expect(await phoneVieneu.cancel!()).toBe(status);
    expect(readAloud.vieneuCancel).toHaveBeenCalledOnce();
  });
});

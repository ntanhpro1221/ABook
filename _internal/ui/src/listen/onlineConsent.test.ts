import { beforeEach, describe, expect, it } from "vitest";
import { askOnlineConsent, needsOnlineConsent, onlineConsentGiven, onlinePromptText, pendingConsent, spokenVoiceName } from "./onlineConsent";
import type { ReadAloudVoice } from "./readAloud";

const store = new Map<string, string>();
Object.defineProperty(globalThis, "localStorage", {
  configurable: true,
  value: {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => void store.set(key, value),
    removeItem: (key: string) => void store.delete(key),
  },
});

const hoaiMy: ReadAloudVoice = { id: "edge:vi-VN-HoaiMyNeural", name: "Hoài My (Edge)", provider: "edge", online: true, default: true };
const namMinh: ReadAloudVoice = { id: "edge:vi-VN-NamMinhNeural", name: "Nam Minh (Edge)", provider: "edge", online: true };
const device: ReadAloudVoice = { id: "device:an", name: "An", provider: "device", online: false };
const voices = [hoaiMy, namMinh, device];

beforeEach(() => store.clear());

describe("hỏi trước khi gửi chữ cho giọng trực tuyến", () => {
  it("giọng trực tuyến chưa đồng ý thì hỏi; giọng của máy thì không", () => {
    expect(needsOnlineConsent(hoaiMy)).toBe(true);
    expect(needsOnlineConsent(device)).toBe(false);
    expect(needsOnlineConsent(undefined)).toBe(false);
  });

  it("lời hỏi gọi tên giọng như người nghe gọi và nói rõ gửi cho ai", () => {
    expect(spokenVoiceName("Hoài My (Edge)")).toBe("Hoài My");
    expect(onlinePromptText(hoaiMy)).toBe(
      "Giọng Hoài My là giọng trực tuyến của Microsoft: chữ của đoạn đang đọc được gửi tới Microsoft để đọc.",
    );
    expect(onlinePromptText({ name: "Ai đó", provider: "lạ" })).toContain("dịch vụ ngoài");
    // Giọng dùng khóa của người nghe: nói cả chuyện dịch vụ có thể tính tiền vào tài khoản của họ.
    const banMai = onlinePromptText({ name: "Ban Mai", provider: "fpt" });
    expect(banMai).toContain("khóa FPT.AI của bạn");
    expect(banMai).toContain("tính tiền vào tài khoản của bạn");
  });

  it("'Nghe' nhớ đồng ý cho nhà cung cấp ấy - không bao giờ hỏi lại", async () => {
    const answer = askOnlineConsent(hoaiMy, voices);
    expect(pendingConsent()?.voice).toBe(hoaiMy);
    pendingConsent()!.answer(hoaiMy.id);
    await expect(answer).resolves.toBe(hoaiMy.id);
    expect(pendingConsent()).toBeNull();
    expect(onlineConsentGiven("edge")).toBe(true);
    expect(needsOnlineConsent(hoaiMy)).toBe(false);
    expect(needsOnlineConsent(namMinh)).toBe(false); // cùng Microsoft
  });

  it("'Chọn giọng khác' rồi chọn giọng của máy: dùng giọng ấy, chưa đồng ý gửi chữ đi", async () => {
    const answer = askOnlineConsent(hoaiMy, voices);
    pendingConsent()!.answer(device.id);
    await expect(answer).resolves.toBe(device.id);
    expect(needsOnlineConsent(hoaiMy)).toBe(true);
  });

  it("đóng hộp: không phát, lần sau hỏi lại; hộp mới mở thì hộp cũ coi như đóng", async () => {
    const first = askOnlineConsent(hoaiMy, voices);
    const second = askOnlineConsent(hoaiMy, voices);
    await expect(first).resolves.toBeNull();
    pendingConsent()!.answer(null);
    await expect(second).resolves.toBeNull();
    expect(needsOnlineConsent(hoaiMy)).toBe(true);
  });
});

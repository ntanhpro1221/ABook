import { describe, expect, it } from "vitest";
import { connectionRoute } from "./connectionRoute";

describe("đường đang nối trên cả hai nền", () => {
  it.each(["100.64.0.1:47630", "100.127.255.254:47630"])("nhận đúng Tailscale %s", (address) => {
    expect(connectionRoute(address)).toBe("Đang nối qua Tailscale");
  });
  it.each(["192.168.1.2:47630", "10.2.3.4:4000", "172.16.0.2:1234", "172.31.255.2:1234"])("nhận mạng nhà %s", (address) => {
    expect(connectionRoute(address)).toBe("Đang nối qua Wi-Fi nhà");
  });
  it.each(["100.63.255.255:47630", "100.128.0.1:47630", "172.32.0.2:47630", "[fd00::1]:47630", "may-ban.local:47630"])("che địa chỉ khác %s", (address) => {
    expect(connectionRoute(address)).toBe("Đang nối qua mạng");
  });
  it("Bluetooth và chưa có kết nối", () => {
    expect(connectionRoute("bluetooth")).toBe("Đang nối qua Bluetooth");
    expect(connectionRoute()).toBe("Chưa kết nối");
  });
});

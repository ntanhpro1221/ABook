import { describe, expect, it } from "vitest";
import { bluetoothAddress, deviceName, isBluetoothHost, routeLine, wakingLine, type PairedDevice } from "./computerRoutes";

const devices: PairedDevice[] = [
  { name: "Galaxy của An", address: "AA:BB:CC:DD:EE:FF", kind: "phone" },
  { name: "Máy bàn", address: "66:55:44:33:22:11", kind: "computer" },
];

describe("máy đã ghép đi đường nào", () => {
  it("máy ghép bằng địa chỉ Bluetooth hiện tên thiết bị, không hiện bt:… và cổng", () => {
    const computer = { host: "bt:AA:BB:CC:DD:EE:FF", port: 47630 };
    expect(isBluetoothHost(computer.host)).toBe(true);
    expect(bluetoothAddress(computer)).toBe("AA:BB:CC:DD:EE:FF");
    expect(routeLine(computer, devices)).toBe("Bluetooth · Galaxy của An");
  });

  it("thiết bị không còn trong danh sách đã ghép thì hiện địa chỉ", () => {
    expect(routeLine({ host: "bt:01:02:03:04:05:06", port: 47630 }, devices)).toBe("Bluetooth · 01:02:03:04:05:06");
    expect(deviceName([], "01:02:03:04:05:06")).toBe("01:02:03:04:05:06");
  });

  it("máy ghép Wi-Fi: chỉ địa chỉ; có Bluetooth dự phòng thì nói thêm", () => {
    expect(routeLine({ host: "192.168.1.20", port: 47630 }, devices)).toBe("192.168.1.20:47630");
    expect(bluetoothAddress({ host: "192.168.1.20", port: 47630 })).toBe("");
    expect(routeLine({ host: "192.168.1.20", port: 47630, bt: "aa:bb:cc:dd:ee:ff" }, devices)).toBe(
      "192.168.1.20:47630 · dự phòng Bluetooth · Galaxy của An",
    );
  });
});

describe("máy kia đang ngủ", () => {
  it("điện thoại: nói nó đang ngủ, mở ABook là trả lời ngay, và còn chờ bao lâu", () => {
    const waking = { since: 1000, until: 1300, via: "bluetooth" as const };
    expect(wakingLine({ kind: "phone", waking }, 1010)).toBe(
      "Điện thoại đang ngủ - mở ABook trên điện thoại để trả lời ngay · chờ thêm tối đa 5 phút",
    );
    expect(wakingLine({ kind: "phone", waking }, 1250)).toMatch(/chờ thêm tối đa 50 giây$/);
    expect(wakingLine({ kind: "phone", waking }, 1400)).toMatch(/tối đa 1 giây$/);
  });

  it("máy tính không ngủ kiểu điện thoại: chỉ nói chưa trả lời", () => {
    expect(wakingLine({ kind: "computer", waking: { since: 0, until: 60, via: "wifi" } }, 0)).toBe(
      "Máy kia chưa trả lời - mở ABook trên máy ấy · chờ thêm tối đa 60 giây",
    );
  });
});

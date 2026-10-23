/** Labels describe the successful route without exposing a device address. */
export function connectionRoute(address?: string): string {
  if (!address) return "Chưa kết nối";
  if (address === "bluetooth" || address.toLowerCase().startsWith("bt:")) return "Đang nối qua Bluetooth";
  const host = address.startsWith("[") ? address.slice(1, address.indexOf("]")) : address.split(":")[0];
  const parts = host.split(".").map(Number);
  if (parts.length === 4 && parts.every((part) => Number.isInteger(part) && part >= 0 && part <= 255)) {
    const [a, b] = parts;
    if (a === 100 && b >= 64 && b <= 127) return "Đang nối qua Tailscale";
    if (a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168)) return "Đang nối qua Wi-Fi nhà";
  }
  return "Đang nối qua mạng";
}

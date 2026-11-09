import { S } from "./strings.generated";
/** Labels describe the successful route without exposing a device address. */
export function connectionRoute(address?: string): string {
  if (!address) return S.s_chua_ket_noi_f3743a06;
  if (address === "bluetooth" || address.toLowerCase().startsWith("bt:")) return S.s_dang_noi_qua_bluetooth_fb6ba9e5;
  const host = address.startsWith("[") ? address.slice(1, address.indexOf("]")) : address.split(":")[0];
  const parts = host.split(".").map(Number);
  if (parts.length === 4 && parts.every((part) => Number.isInteger(part) && part >= 0 && part <= 255)) {
    const [a, b] = parts;
    if (a === 100 && b >= 64 && b <= 127) return S.s_dang_noi_qua_tailscale_7de36f5d;
    if (a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168)) return S.s_dang_noi_qua_wi_fi_nha_ebf18485;
  }
  return S.s_dang_noi_qua_mang_807811f3;
}

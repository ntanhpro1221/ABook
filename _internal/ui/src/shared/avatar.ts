export interface AvatarRef {
  kind: "pattern" | "image" | "voice";
  key?: string; file?: string; sha256?: string; initials?: string; color?: string; bits?: number;
}
export const AVATAR_COLORS = ["#805c38", "#675f48", "#73594c", "#4c6963", "#66607a", "#80565e"];
/** FNV-1a over NFC UTF-8, shared by Python, Kotlin and QML. */
export function avatarHash(name: string): number {
  let hash = 2166136261;
  for (const byte of new TextEncoder().encode(name.normalize("NFC"))) hash = Math.imul(hash ^ byte, 16777619) >>> 0;
  return hash;
}
export function avatarPattern(name: string): AvatarRef {
  const key = name.normalize("NFC");
  const number = avatarHash(key);
  const initials = key.replace(/_/g, " ").split(/\s+/).filter((word) => word && !/^[IVXLCDM]+$/.test(word))
    .slice(0, 2).map((word) => Array.from(word)[0]).join("").toUpperCase();
  return { kind: "pattern", key, initials, color: AVATAR_COLORS[number % AVATAR_COLORS.length], bits: number & 32767 };
}
export function voiceAvatarFile(name: string): string {
  return `voice-${avatarHash(name).toString(16).padStart(8, "0")}.webp`;
}
export function avatarCells(bits: number): { x: number; y: number }[] {
  const cells = [];
  for (let y = 0; y < 5; y++) for (let x = 0; x < 5; x++) {
    if (bits & (1 << (y * 3 + Math.min(x, 4 - x)))) cells.push({ x, y });
  }
  return cells;
}

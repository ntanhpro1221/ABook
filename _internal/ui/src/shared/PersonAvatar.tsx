import { createContext, useContext, useState } from "react";
import { mediaUrl } from "@/studio/api";
import { Presence } from "./MotionPresence";
import { avatarCells, avatarPattern, voiceAvatarFile, type AvatarRef } from "./avatar";
export const AvatarBook = createContext("");

/** Fixed dimensions and immutable URLs keep lazy decoding out of the layout path. */
export function PersonAvatar({ name, avatar, bookId, voice, size = 40, className = "" }: {
  name: string; avatar?: AvatarRef | null; bookId?: string; voice?: boolean; size?: number; className?: string;
}) {
  const [failed, setFailed] = useState("");
  const scopeBook = useContext(AvatarBook);
  bookId ||= scopeBook;
  const fallback = avatar?.kind === "pattern" ? avatar : avatarPattern(avatar?.key || name);
  const file = avatar?.file || (voice ? voiceAvatarFile(name) : "");
  const path = (avatar?.kind === "voice" || voice) && /^voice-[0-9a-f]{8}\.webp$/.test(file)
    ? `/media/voice-avatars/${file}`
    : bookId && /^avatars\/[0-9a-f]{64}\.webp$/.test(file) ? `/media/books/${encodeURIComponent(bookId)}/${file}` : "";
  const src = path ? mediaUrl(path) : "";
  return <span aria-hidden className={`relative inline-grid shrink-0 place-items-center overflow-hidden rounded-full ${className}`}
    style={{ width: size, height: size, backgroundColor: fallback.color }}>
    <svg viewBox="0 0 100 100" className="absolute inset-0 size-full" focusable="false">
      {avatarCells(fallback.bits || 0).map(({ x, y }) => <rect key={`${x}-${y}`} x={x * 20} y={y * 20} width="20" height="20" fill="#ffffff" opacity="0.10" />)}
      <text x="50" y="51" textAnchor="middle" dominantBaseline="central" fill="#ffffff" fontSize="30" fontWeight="700">{fallback.initials}</text>
    </svg>
    <Presence>{src && failed !== src && <img alt="" src={src} width={size} height={size} loading="lazy" decoding="async"
      className="absolute inset-0 size-full object-cover" onError={() => setFailed(src)} />}</Presence>
  </span>;
}

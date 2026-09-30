import { App } from "@capacitor/app";
import { useEffect, useState } from "react";

/**
 * Bản mới của app trên điện thoại. App Windows tự cập nhật (bộ cập nhật Tauri đọc latest.json); điện thoại cài APK tay, nên
 * không ai nhắc thì cứ ở bản cũ (hai nền tảng lệch nhau). Hỏi GitHub bản phát hành mới nhất (API công khai, tối đa một lần
 * mỗi ngày), so với bản đang cài, mời tải file APK của bản ấy - cài vẫn là người dùng bấm.
 */

export const RELEASES_API = "https://api.github.com/repos/ntanhpro1221/ABook/releases/latest";
const CACHE_KEY = "abook.release";
const TOLD_KEY = "abook.release.told";
const DAY_MS = 24 * 3600 * 1000;

export interface AppRelease {
  version: string;
  /** Trang phát hành trên GitHub. */
  page: string;
  /** File APK của bản ấy (tải thẳng), hay null khi bản ấy không có APK. */
  apk: string | null;
}

/** a > b theo từng số của "0.4.10" (bỏ "v" đầu; phần không phải số tính là 0) - so chuỗi thì "0.4.10" < "0.4.9". */
export function newer(a: string, b: string): boolean {
  const parts = (value: string) => value.replace(/^v/i, "").split(".").map((part) => Number.parseInt(part, 10) || 0);
  const left = parts(a);
  const right = parts(b);
  for (let index = 0; index < Math.max(left.length, right.length); index += 1) {
    const difference = (left[index] ?? 0) - (right[index] ?? 0);
    if (difference) return difference > 0;
  }
  return false;
}

/** Bản phát hành từ lời đáp của GitHub API (`releases/latest`); lời đáp lạ thì null. */
export function releaseFrom(json: unknown): AppRelease | null {
  if (!json || typeof json !== "object") return null;
  const data = json as { tag_name?: unknown; html_url?: unknown; assets?: unknown };
  if (typeof data.tag_name !== "string" || typeof data.html_url !== "string") return null;
  const assets = Array.isArray(data.assets) ? (data.assets as { name?: unknown; browser_download_url?: unknown }[]) : [];
  const apk = assets.find((asset) => typeof asset.name === "string" && asset.name.toLowerCase().endsWith(".apk"));
  return {
    version: data.tag_name.replace(/^v/i, ""),
    page: data.html_url,
    apk: apk && typeof apk.browser_download_url === "string" ? apk.browser_download_url : null,
  };
}

function remembered(): { at: number; release: AppRelease | null } | null {
  try {
    const value = JSON.parse(localStorage.getItem(CACHE_KEY) ?? "null");
    return value && typeof value.at === "number" ? value : null;
  } catch {
    return null;
  }
}

/** Bản mới nhất trên GitHub - nhớ 24 giờ; không có mạng thì dùng lần hỏi trước (hay null). */
export async function latestRelease(fetcher: typeof fetch = fetch, now = Date.now()): Promise<AppRelease | null> {
  const cached = remembered();
  if (cached && now - cached.at < DAY_MS) return cached.release;
  try {
    const reply = await fetcher(RELEASES_API, { headers: { Accept: "application/vnd.github+json" } });
    if (!reply.ok) return cached?.release ?? null;
    const release = releaseFrom(await reply.json());
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({ at: now, release }));
    } catch {
      // bộ nhớ trình duyệt bị chặn: lần sau hỏi lại
    }
    return release;
  } catch {
    return cached?.release ?? null;
  }
}

/** Đã nhắc bản này bằng thông báo nổi chưa (mỗi bản mới nhắc một lần; Cài đặt thì luôn hiện). */
export function toldAbout(version: string): boolean {
  try {
    return localStorage.getItem(TOLD_KEY) === version;
  } catch {
    return true;
  }
}

export function markTold(version: string): void {
  try {
    localStorage.setItem(TOLD_KEY, version);
  } catch {
    // không nhớ được thì lần sau nhắc lại - không sao
  }
}

/** Bản đang cài và bản mới hơn trên GitHub (nếu có). Ngoài app Android (trình duyệt) thì không hỏi gì. */
export function useAppUpdate(): { current: string | null; update: AppRelease | null } {
  const [current, setCurrent] = useState<string | null>(null);
  const [update, setUpdate] = useState<AppRelease | null>(null);
  useEffect(() => {
    let alive = true;
    void (async () => {
      let version: string | null = null;
      try {
        version = (await App.getInfo()).version;
      } catch {
        return;
      }
      if (!alive) return;
      setCurrent(version);
      const latest = await latestRelease();
      if (alive && latest && version && newer(latest.version, version)) setUpdate(latest);
    })();
    return () => {
      alive = false;
    };
  }, []);
  return { current, update };
}

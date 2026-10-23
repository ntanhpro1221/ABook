import { useQuery, type QueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { EbookLibrary } from "./plugins";

// "Bản lưu cũ": khi lưu sách ra file bị hỏng giữa chừng mà bản lưu trước cũng chưa trả lại được, app giữ bản trước trong bộ nhớ của nó
// (Kotlin OldSaves / BookSave, thư mục filesDir/ban-luu-cu). Cài đặt cho xem, lưu ra chỗ khác hay xoá; Thư viện báo một lần khi có file mới.

export interface OldSave {
  name: string;
  size: number;
  /** Lúc app giữ file này (giây). */
  modified: number;
}

export const OLD_SAVES_KEY = ["oldSaves"] as const;
const SEEN_KEY = "abook-old-saves-seen";

export function useOldSaves() {
  return useQuery({ queryKey: OLD_SAVES_KEY, queryFn: async () => (await EbookLibrary.listOldSaves()).files });
}

/** Tên sách trong tên file giữ phòng ("Tên sách 20260101-101010.abook" -> "Tên sách"). */
export function oldSaveTitle(name: string): string {
  return name.replace(/\.abook(proj)?$/, "").replace(/ \d{8}-\d{6}(?:-\d+)?$/, "").trim() || name;
}

/** Những file chưa từng báo cho người dùng. */
export function newOldSaves(files: OldSave[], seen: string[]): OldSave[] {
  const known = new Set(seen);
  return files.filter((file) => !known.has(file.name));
}

/** Câu báo một lần ở Thư viện. */
export function oldSaveNotice(fresh: OldSave[]): string {
  return fresh.length === 1
    ? `Có bản lưu cũ của “${oldSaveTitle(fresh[0].name)}” chưa trả lại được - mở trong Cài đặt`
    : `Có ${fresh.length} bản lưu cũ chưa trả lại được - mở trong Cài đặt`;
}

function loadSeen(): string[] {
  try {
    const value = JSON.parse(localStorage.getItem(SEEN_KEY) ?? "[]");
    return Array.isArray(value) ? value.filter((name): name is string => typeof name === "string") : [];
  } catch {
    return [];
  }
}

function saveSeen(names: string[]): void {
  try {
    localStorage.setItem(SEEN_KEY, JSON.stringify(names));
  } catch {
    // WebView không ghi được: lần mở sau báo lại - phiền hơn là bỏ sót
  }
}

/** Báo (một lần cho mỗi file) trên Thư viện: có bản lưu cũ app đang giữ hộ bạn. Gọi ở trang Thư viện; hỏi lại mỗi lần vào trang. */
export function useOldSaveNotice(): void {
  const { data } = useOldSaves();
  const navigate = useNavigate();
  useEffect(() => {
    if (!data) return;
    const fresh = newOldSaves(data, loadSeen());
    saveSeen(data.map((file) => file.name));
    if (!fresh.length) return;
    toast(oldSaveNotice(fresh), { id: "old-saves", duration: 12_000, action: { label: "Mở Cài đặt", onClick: () => navigate("/settings") } });
  }, [data, navigate]);
}

/** Bản lưu cũ vừa đổi (có file mới / đã xoá): hỏi lại danh sách. */
export function refreshOldSaves(client: QueryClient): Promise<void> {
  return client.invalidateQueries({ queryKey: OLD_SAVES_KEY });
}

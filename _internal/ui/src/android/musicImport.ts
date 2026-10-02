import type { ImportResult } from "@/studio/musicLocal";
import type { NativeMusicImport } from "@/studio/musicImport";
import { EbookLibrary } from "./plugins";

// "Nhập nhạc của tôi…" trên điện thoại: hộp chọn file của hệ thống (chọn nhiều bản một lúc) rồi lõi native (MusicStore.kt) nhập từng
// bản và báo tiến độ qua sự kiện "musicImport". Lời đáp cuối cùng có đúng JSON của `my_music_import` bên máy tính.

export const nativeMusicImport: NativeMusicImport = async (progress) => {
  const listener = await EbookLibrary.addListener("musicImport", (event) => progress(event.done, event.total));
  try {
    const answer = await EbookLibrary.pickMusic();
    if (!answer.picked) return null;
    const { picked: _picked, ...result } = answer;
    return result as ImportResult;
  } finally {
    await listener.remove();
  }
};

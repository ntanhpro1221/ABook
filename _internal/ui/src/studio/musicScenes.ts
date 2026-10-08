// Một mảnh nhạc "nối tiếp" (`continued`, music_select.choose): đoạn dài được cắt mảnh để nhạc biến đổi nhẹ, nhưng người nghe
// nghe MỘT bài chạy liền - nên tab Nhạc nền không bày nó như một lựa chọn riêng trùng bài mà ghi gọn "tiếp bài của đoạn trên".

interface SceneChoice {
  link: string | null;
  continued?: boolean;
  pinned?: boolean;
  silenced?: boolean;
}

/** Mảnh này chỉ chơi tiếp bài của đoạn trên (chưa bị ghim / để im lặng riêng) - hiện gọn, không đủ bộ nút. */
export function isContinuation(scene: SceneChoice): boolean {
  return Boolean(scene.continued && scene.link && !scene.pinned && !scene.silenced);
}

export const CONTINUED_NOTE = "↳ tiếp bài của đoạn trên";

/** Lời nút "Đổi bài": ở mảnh nối tiếp, ghim bài mới vào đây nên đổi từ chỗ này trở đi (các mảnh sau nối theo bài mới). */
export function swapButton(scene: SceneChoice): { text: string; title?: string } {
  return isContinuation(scene)
    ? { text: "Đổi từ đây", title: "Đổi bài từ chỗ này trở đi - các đoạn nối tiếp sau đó chơi theo bài mới; phần trên giữ nguyên" }
    : { text: "Đổi bài" };
}

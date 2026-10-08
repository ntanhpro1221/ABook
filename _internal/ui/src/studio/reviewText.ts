// Chữ của tab "Cần nghe lại" (soát UX a8 07-10), tách ra để kiểm bằng test.

/** "máy nghe khớp 15%" không nói khớp với cái gì - đây là độ khớp giữa điều máy nghe lại được và CHỮ CỦA CÂU. */
export function matchPhrase(percent: string): string {
  return `máy nghe lại khớp ${percent} với chữ của câu`;
}

/** Chữ của nút / ô sửa cách máy đọc một câu (không đụng chữ của sách) - "chữ đem đọc" là tiếng của người làm máy. */
export function spokenEditLabel(twins: number): string {
  return `Sửa cách máy đọc câu này${twins > 0 ? ` (còn ${twins} câu giống hệt)` : ""}`;
}

/** Dòng phím tắt chỉ có nghĩa khi đang nghe liền: ngoài lúc ấy O / R không làm gì nên không hiện. */
export function shortcutHint(continuous: boolean): string | null {
  return continuous ? "Đang nghe liền: bấm O nếu ổn, R nếu cần thu lại - rồi sang câu kế" : null;
}

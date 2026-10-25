// Độ dài dòng chữ đọc: DESIGN 7 - chữ đọc theo rộng ≤ 68 ký tự. Đo ký tự thật của từng dòng đã xuống dòng trong khối chữ đọc
// (.reading-surface p): dòng dài nhất của một đoạn nhiều dòng. Dùng: gallery_shots --probe scripts/probes/line_length.js
(() => {
  const out = [];
  let worst = 0;
  for (const p of document.querySelectorAll('.reading-surface p')) {
    const lines = new Map();
    const walker = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      for (let i = 0; i < node.data.length; i++) {
        const r = document.createRange(); r.setStart(node, i); r.setEnd(node, i + 1);
        const box = r.getClientRects()[0]; if (!box || !box.width) continue;
        const key = Math.round(box.top / 4);
        lines.set(key, (lines.get(key) ?? 0) + 1);
      }
    }
    // Dòng cuối của đoạn thường ngắn: chỉ xét đoạn có ít nhất hai dòng và lấy dòng dài nhất.
    if (lines.size < 2) continue;
    worst = Math.max(worst, ...lines.values());
  }
  if (worst > 68) out.push(`dòng chữ đọc dài ${worst} ký tự (chuẩn ≤ 68)`);
  return out;
})()

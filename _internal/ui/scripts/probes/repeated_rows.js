// Chữ kỹ thuật lặp trên từng hàng (V10, 25-10): một mảnh chữ giống hệt nhau ở gần như MỌI hàng anh em ("Chương 7 · Hoài My (Edge)" trên mọi chương) là
// thông tin của cả danh sách - nói MỘT lần ở đầu trang hay không nói. Dò: khối có >= 6 con nhìn thấy; mỗi dòng chữ (innerText) của một hàng, dòng có
// dấu "·" tách ra các mảnh; mảnh >= 6 ký tự giống hệt (không bỏ số) ở >= 80% các hàng (kể cả khi ở hàng khác nó nằm riêng một dòng) thì báo.
// Nút giống nhau ở mọi hàng (Nghe thử, Xoá) không bị báo vì không bao giờ nằm trong một dòng nối bằng "·". Tên model / engine trên màn nghe cũng báo.
// Dùng: gallery_shots --probe.
(() => {
  const out = [];
  const lines = (row) => (row.innerText || "").split("\n").map((line) => line.replace(/\s+/g, " ").trim()).filter(Boolean);
  const seen = new Set();
  for (const parent of document.querySelectorAll("body *")) {
    if (parent.closest('[aria-hidden="true"]')) continue;
    const kids = [...parent.children].filter((child) => child.getBoundingClientRect().height > 0);
    if (kids.length < 6) continue;
    const counts = new Map();
    const joined = new Set();
    for (const kid of kids) {
      const here = new Set();
      for (const line of lines(kid)) {
        const pieces = line.split(" · ").map((piece) => piece.trim());
        for (const piece of pieces) {
          if (piece.length < 6 || !/\p{L}/u.test(piece)) continue;
          here.add(piece);
          if (pieces.length > 1) joined.add(piece);
        }
      }
      for (const piece of here) counts.set(piece, (counts.get(piece) ?? 0) + 1);
    }
    for (const [piece, count] of counts) {
      if (!joined.has(piece) || count / kids.length < 0.8 || seen.has(piece)) continue;
      seen.add(piece);
      out.push(`lặp ở ${count}/${kids.length} hàng: "${piece}"`);
    }
  }
  const body = document.body.innerText;
  const engine = body.match(/\b(qwen[\w.:-]*|VieNeu|Supertonic|Edge TTS|ollama|gemma[\w.:-]*)\b/i);
  if (engine && !document.querySelector("[data-diagnostics]")) out.push(`tên model/engine hiện trên màn: "${engine[0]}"`);
  return out;
})()

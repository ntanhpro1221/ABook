// Biểu tượng trôi giữa khối chữ nhiều dòng: hàng flex căn giữa (items-center) có một svg nhỏ mà một câu chữ xuống >= 2 dòng
// (hay cả hàng >= 3 dòng) - biểu tượng phải thẳng dòng đầu. Cặp tên + dòng phụ hai dòng căn giữa là đúng. Dùng: gallery_shots --probe.
(() => {
  const out = [];
  for (const svg of document.querySelectorAll("svg")) {
    const box = svg.getBoundingClientRect();
    if (!box.width || box.width > 32 || svg.closest('[aria-hidden="true"][inert],.reading-surface')) continue;
    let icon = svg;
    const alone = (element) => [...element.childNodes].filter((node) => node.nodeType === 1 || node.data.trim()).length === 1;
    while (icon.parentElement && alone(icon.parentElement) && icon.parentElement.tagName !== "BUTTON") icon = icon.parentElement;
    const row = icon.parentElement;
    if (!row) continue;
    const style = getComputedStyle(row);
    if (!style.display.includes("flex") || style.flexDirection.startsWith("column") || style.alignItems !== "center") continue;
    const tops = [];
    let wrapped = false;
    const walker = document.createTreeWalker(row, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (!node.data.trim() || node.parentElement.closest("svg")) continue;
      const range = document.createRange(); range.selectNodeContents(node);
      const own = [...range.getClientRects()].filter((rect) => rect.width > 0 && rect.height > 6).map((rect) => rect.top);
      if (new Set(own.map((top) => Math.round(top / 6))).size >= 2) wrapped = true;
      tops.push(...own);
    }
    const lineHeight = parseFloat(style.lineHeight) || parseFloat(style.fontSize) * 1.4;
    const lines = tops.sort((a, b) => a - b).filter((top, index, all) => index === 0 || top - all[index - 1] > lineHeight * 0.6).length;
    if (wrapped || lines >= 3) out.push(`${(row.innerText || "").trim().slice(0, 60).replace(/\s+/g, " ")} (${lines} dòng)`);
  }
  return [...new Set(out)];
})()

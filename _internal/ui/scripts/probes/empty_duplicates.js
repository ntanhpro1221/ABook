// Trạng thái rỗng chỉ nói "chưa có" MỘT lần (D2, 25-10): tiêu đề của EmptyState (h3 đứng sau ô biểu tượng size-14) không được lặp lại như chữ của
// phần tử nhìn thấy nào khác ngoài khối rỗng - phụ đề đầu trang "Chưa có dự án" từng đứng ngay trên tiêu đề "Chưa có dự án". Dùng: gallery_shots --probe.
(() => {
  const out = [];
  const norm = (text) => text.replace(/\s+/g, " ").trim().toLowerCase();
  const visible = (element) => {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  };
  const titles = [...document.querySelectorAll("h3")].filter((heading) => heading.previousElementSibling && /\bsize-14\b/.test(heading.previousElementSibling.className));
  for (const title of titles) {
    const text = norm(title.textContent);
    if (!text) continue;
    const block = title.parentElement;
    for (const other of document.querySelectorAll("body *")) {
      if (other === title || block.contains(other) || other.contains(title) || other.children.length > 0 || !visible(other)) continue;
      if (other.closest('[aria-hidden="true"], [role="navigation"], nav')) continue;
      if (norm(other.textContent) === text) out.push(`"${title.textContent.trim()}" nói hai lần (${other.tagName.toLowerCase()}.${String(other.className).split(" ")[0]})`);
    }
  }
  return out;
})()

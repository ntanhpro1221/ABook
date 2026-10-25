// Khung viền quanh nhóm (DESIGN 4: không card / viền quanh nhóm, dùng khoảng trắng): phần tử KHÔNG phải điều khiển, có viền thật (>= 1 px, không trong suốt)
// ở cả bốn cạnh, bo >= 10 px, cao >= 56 px, trong cột trang (không trong hộp thoại / bảng trượt / menu). Báo tên lớp ngắn để lần ra thành phần.
// Dùng: gallery_shots --probe (hay measure.mjs).
(() => {
  const out = [];
  for (const element of document.querySelectorAll("main *")) {
    if (element.closest('[role="dialog"], [data-sheet], [role="menu"], [role="listbox"], [data-radix-popper-content-wrapper], [role="alert"], [role="status"], .motion-snapshot')) continue;
    if (element.matches("button, input, select, textarea, a, summary, [role=radio], [role=switch], [role=tab], img, svg")) continue;
    const style = getComputedStyle(element);
    const edges = ["Top", "Right", "Bottom", "Left"].map((side) => parseFloat(style[`border${side}Width`]) >= 1 && style[`border${side}Style`] !== "none" && !/rgba\(0, 0, 0, 0\)|transparent/.test(style[`border${side}Color`]));
    if (!edges.every(Boolean) || parseFloat(style.borderTopLeftRadius) < 10) continue;
    const box = element.getBoundingClientRect();
    if (box.height < 56 || box.width < 1) continue;
    out.push(`${element.tagName.toLowerCase()}.${String(element.className).split(" ").filter((name) => /^(rounded|border|bg-|p[xy]?-)/.test(name)).slice(0, 5).join(".")} ${Math.round(box.width)}x${Math.round(box.height)}`);
  }
  return out;
})()

// Vạch kẻ hàng thẳng mép nội dung (D7, 25-10): `.rows-inset` vẽ vạch từ --rows-inset vào trong; danh sách kéo lề âm (-mx-N) để nền rê chuột tràn ra ngoài
// mép nội dung, nên --rows-inset PHẢI bằng đúng phần tràn ấy - lệch thì vạch lấn ra ngoài (hay thụt vào trong) mép chữ. Dò: mép trái / phải của mỗi
// .rows-inset trừ --rows-inset phải trùng mép nội dung của cột trang (.page-x hay main, trừ đệm), sai số 0,5 px. Danh sách trong hộp thoại / bảng
// trượt / thanh bên (không thuộc cột trang) bỏ qua. Dùng: gallery_shots --probe.
(() => {
  const out = [];
  for (const list of document.querySelectorAll(".rows-inset")) {
    const column = list.closest(".page-x, main");
    if (!column || list.closest('[role="dialog"], [data-sheet], aside, nav')) continue;
    const rect = list.getBoundingClientRect();
    if (rect.width < 1) continue;
    const style = getComputedStyle(column);
    const box = column.getBoundingClientRect();
    const contentLeft = box.left + parseFloat(style.paddingLeft) + parseFloat(style.borderLeftWidth);
    const contentRight = box.right - parseFloat(style.paddingRight) - parseFloat(style.borderRightWidth);
    const probe = document.createElement("div");
    probe.style.cssText = "position:absolute;visibility:hidden;width:var(--rows-inset,0px)";
    list.append(probe);
    const inset = probe.getBoundingClientRect().width;
    probe.remove();
    const left = Math.round((rect.left + inset - contentLeft) * 10) / 10;
    const right = Math.round((contentRight - (rect.right - inset)) * 10) / 10;
    if (Math.abs(left) > 0.5 || Math.abs(right) > 0.5) out.push(`.rows-inset lệch mép nội dung: trái ${left} px, phải ${right} px (--rows-inset ${inset} px)`);
  }
  return out;
})()

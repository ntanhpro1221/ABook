// Select, hàng chọn và chrome của bảng đáy: gallery_shots --probe scripts/probes/controls140.js.
(() => {
  const out = [], phone = matchMedia("(max-width: 640px)").matches;
  const visible = el => el.getClientRects().length && !el.closest('[inert], [aria-hidden="true"], .motion-snapshot');
  for (const select of [...document.querySelectorAll("select")].filter(visible)) {
    const s = getComputedStyle(select), rect = select.getBoundingClientRect(), expected = phone || matchMedia("(pointer: coarse)").matches ? 48 : 40;
    if (!select.classList.contains("shared-select")) out.push(`Select riêng: ${select.getAttribute("aria-label") || select.id}`);
    if (Math.abs(rect.height - expected) > .5) out.push(`Select cao ${rect.height}, cần ${expected}: ${select.id}`);
    const context = document.createElement("canvas").getContext("2d"); context.font = `${s.fontStyle} ${s.fontWeight} ${s.fontSize} ${s.fontFamily}`;
    const longest = Math.max(...[...select.options].map(option => context.measureText(option.textContent).width));
    const needed = longest + parseFloat(s.paddingLeft) + parseFloat(s.paddingRight) + 2;
    if (rect.width + 1 < needed && select.parentElement.getBoundingClientRect().width > needed + 1) out.push(`Select cắt chữ dù đủ chỗ: ${select.id}, ${rect.width.toFixed(2)}/${needed.toFixed(2)}`);
  }
  for (const row of [...document.querySelectorAll('[aria-selected="true"], [aria-pressed="true"], [data-sheet-current], [aria-current="page"]')].filter(visible)) {
    const background = getComputedStyle(row).backgroundColor;
    if (/bg-accent-soft/.test(row.className) || background === "rgb(247, 234, 213)" || /rgba?\(233, 169, 69,? 0\.14\)/.test(background)) out.push(`Hàng chọn tô nền: ${row.textContent.trim().slice(0, 60)}`);
  }
  if (phone) for (const sheet of [...document.querySelectorAll('[role="dialog"][data-state="open"]')].filter(visible)) {
    if (!sheet.classList.contains("sheet-surface")) out.push("Hộp điện thoại chưa dùng Sheet");
    if (sheet.querySelectorAll('[data-sheet-handle]').length !== 1 || sheet.querySelectorAll('button[aria-label="Đóng"]').length !== 1 || sheet.querySelector(".lucide-x")) out.push("Bảng có nhiều cách đóng");
    const actions = sheet.querySelector(".surface-footer [data-dialog-actions]");
    if (actions) {
      if (actions.closest(".sheet-body")) out.push("Chân bảng nằm trong vùng cuộn");
      const bounds = actions.getBoundingClientRect(), width = bounds.width;
      for (const button of [...actions.querySelectorAll(":scope > button")].filter(visible)) {
        const r = button.getBoundingClientRect();
        if (Math.abs(r.width - width) > 1 || r.height < 48 || Math.abs(r.left - bounds.left) > 1 || Math.abs(r.right - bounds.right) > 1) out.push(`Nút chân bảng khác cỡ / lệch cột: ${button.textContent.trim()} ${r.width}×${r.height}/${width}`);
        const label = button.lastElementChild?.getBoundingClientRect();
        if (label && Math.abs(label.x + label.width / 2 - r.x - r.width / 2) > 1) out.push(`Nhãn chân bảng lệch tâm: ${button.textContent.trim()}`);
      }
      const buttons = [...actions.querySelectorAll(":scope > button")].filter(visible);
      const primary = buttons.find(button => button.dataset.variant === "primary");
      if (primary && primary !== buttons.at(-1)) out.push("Nút chính chưa ở cuối chân bảng");
    }
  }
  return out;
})()

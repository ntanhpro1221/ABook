// Một kiểu chọn cho tab trong trang lẫn bộ lọc (D12, 25-10): mục đang chọn của mọi hàng chữ-gạch-chân (TabsTrigger, FilterRow, bộ lọc Thư viện, "Thêm")
// là chữ `--fg` thường (text-fg) + gạch hổ phách; chữ hổ phách ở mục chọn từng làm tab và bộ lọc trông như hai app. Dò: nút có border-b-2 border-transparent
// đang chọn (aria-selected / aria-checked / aria-pressed / data-state=active / data-active) mà màu chữ khác màu text-fg thì báo. Dùng: gallery_shots --probe.
(() => {
  const out = [];
  const reference = document.createElement("span");
  reference.className = "text-fg";
  document.body.append(reference);
  const fg = getComputedStyle(reference).color;
  reference.remove();
  for (const button of document.querySelectorAll("button, [role=tab]")) {
    if (!/\bborder-b-2\b/.test(button.className) || !/\bborder-transparent\b/.test(button.className)) continue;
    const selected = button.getAttribute("aria-selected") === "true" || button.getAttribute("aria-checked") === "true" || button.getAttribute("aria-pressed") === "true" || button.dataset.state === "active" || button.hasAttribute("data-active");
    if (!selected) continue;
    const color = getComputedStyle(button).color;
    if (color !== fg) out.push(`mục chọn "${(button.textContent || "").trim().slice(0, 24)}" màu ${color}, khác chữ thường ${fg}`);
  }
  return out;
})()

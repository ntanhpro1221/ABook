// Icon đôi / trùng trong một menu: mỗi hàng MỘT icon (DESIGN 8) và icon khác nhau cho việc khác nhau. Dò mọi menu / bảng đang mở:
// (a) hàng có hai icon (đầu hàng và cuối hàng), (b) hai hàng dùng cùng một icon lucide. Dùng: gallery_shots --probe scripts/probes/menu_icons.js
(() => {
  const out = [];
  const icon = (svg) => [...svg.classList].find(c => c.startsWith('lucide-') && c !== 'lucide') ?? svg.getAttribute('data-icon');
  const rowSelector = '[role="menuitem"],[data-player-menu-row],[data-menu-row]';
  for (const menu of document.querySelectorAll('[role="menu"],[role="dialog"],[data-radix-popper-content-wrapper]')) {
    if (menu.querySelector('[role="dialog"],[role="menu"]') && menu.matches('[data-radix-popper-content-wrapper]')) continue;
    const rows = [...menu.querySelectorAll(rowSelector)].filter(row => row.getClientRects().length);
    const byIcon = new Map();
    for (const row of rows) {
      const svgs = [...row.querySelectorAll('svg')].filter(s => s.getClientRects().length);
      const names = svgs.map(icon).filter(Boolean);
      const label = (row.textContent || row.getAttribute('aria-label') || '').trim().slice(0, 30);
      if (names.length > 1 && new Set(names).size === 1) out.push(`hàng hai icon ${names[0]}: ${label}`);
      if (names.length) byIcon.set(names[0], [...(byIcon.get(names[0]) ?? []), label]);
    }
    for (const [name, labels] of byIcon) if (labels.length > 1) out.push(`cùng icon ${name}: ${labels.join(' | ')}`);
  }
  return [...new Set(out)];
})()

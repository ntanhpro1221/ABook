// Geometry in CSS pixels; METRICS records are evidence, the other probes remain unchanged.
(() => {
  const box = el => { const r = el.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height, right: r.right, bottom: r.bottom }; };
  const textBox = el => {
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (!node.textContent.trim() || node.parentElement.closest('svg')) continue;
      const range = document.createRange(); range.selectNodeContents(node);
      const r = range.getBoundingClientRect(); return { x: r.x, right: r.right };
    }
    return null;
  };
  const layers = [...document.querySelectorAll('[role="dialog"],[role="menu"]')].filter(el => el.getBoundingClientRect().width && !el.closest('[inert],[data-state="closed"]'));
  if (!layers.length && innerWidth <= 640) {
    const panel = document.querySelector('.now-playing [role="tabpanel"]');
    if (panel?.getBoundingClientRect().width) layers.push(panel);
  }
  const data = layers.map(el => {
    const rows = [...el.querySelectorAll('[role="menuitem"], [data-player-more] button, [data-player-menu-row], button[data-current]')].filter(row => row.getBoundingClientRect().height && row.textContent.trim());
    const handle = el.querySelector('[data-sheet-handle]');
    const r = box(el);
    const toggles = [...document.querySelectorAll(document.querySelector('.now-playing[data-state="open"]') ? '.now-playing [data-player-toggle]' : '[data-player-toggle]')];
    const controls = [...new Set(toggles.flatMap(button => [...button.parentElement.querySelectorAll('button')]))];
    const intersects = button => { const a = box(button); return a.w && r.x < a.right && r.right > a.x && r.y < a.bottom && r.bottom > a.y; };
    return { role: el.role, title: el.getAttribute('aria-label') || el.querySelector('h2')?.textContent, ...r, radii: [getComputedStyle(el).borderTopLeftRadius, getComputedStyle(el).borderBottomLeftRadius], scroll: [el.scrollWidth, el.clientWidth], handleDelta: handle ? Math.abs(box(handle).x + box(handle).w / 2 - r.x - r.w / 2) : null,
      rows: rows.map(row => { const svg = row.querySelector('svg'); const walker = document.createTreeWalker(row, NodeFilter.SHOW_TEXT); let node; while (walker.nextNode()) { if (walker.currentNode.textContent.trim() && !walker.currentNode.parentElement.closest('svg')) { node = walker.currentNode; break; } } const range = document.createRange(); if (node) range.selectNodeContents(node); return { label: row.textContent.trim(), ...box(row), icon: svg ? box(svg) : null, textX: node ? range.getBoundingClientRect().x : null }; }),
      steppers: [...el.querySelectorAll('button[aria-label$="5 phút"]')].map(button => ({ label: button.ariaLabel, ...box(button), icon: button.querySelector('svg') ? box(button.querySelector('svg')) : null })),
      selectedSpeed: el.querySelector('[data-current-choice]')?.textContent,
      content: el.querySelector('.sheet-body') ? { ...box(el.querySelector('.sheet-body')), scroll: [el.querySelector('.sheet-body').scrollWidth, el.querySelector('.sheet-body').clientWidth] } : null,
      close: [...el.querySelectorAll('button[aria-label="Đóng"]')].map(box),
      buttonDetails: [...el.querySelectorAll('button')].map(button => ({ label: button.ariaLabel || button.textContent.trim(), ...box(button), text: textBox(button), icons: [...button.querySelectorAll('svg')].map(box) })),
      actionButtons: [...el.querySelectorAll('[data-add-book-actions] > button')].map(button => {
        const text = [...button.childNodes].find(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
        const range = document.createRange(); if (text) range.selectNodeContents(text);
        return { label: button.textContent.trim(), ...box(button), textX: text ? range.getBoundingClientRect().x : null };
      }),
      grid: [...el.querySelectorAll('.grid > button')].map(button => ({ label: button.textContent.trim(), ...box(button) })),
      actions: [...el.querySelectorAll('[data-add-book-actions],.sheet-footer,.dialog-actions,input[aria-label]')].map(node => ({ label: node.getAttribute('aria-label') || node.textContent.trim(), ...box(node) })),
      transportControls: controls.map(button => ({ label: button.ariaLabel, ...box(button) })),
      transportRowOverlap: controls.filter(intersects).length,
      transportOverlap: toggles.filter(intersects).length };
  });
  return ['METRICS ' + JSON.stringify({ page: [document.documentElement.scrollWidth, document.documentElement.clientWidth], layers: data })];
})()

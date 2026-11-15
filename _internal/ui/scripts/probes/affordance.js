(() => {
  const visible = el => {
    if (!(el instanceof Element)) return false;
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 1 && r.height > 1 && r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth && s.visibility !== 'hidden' && s.display !== 'none' && Number(s.opacity) > 0.05 && (!el.parentElement || visible(el.parentElement));
  };
  const click = el => el.matches('button,a[href],input,select,textarea,[role=button],[role=link],[role=tab],[role=radio],[role=checkbox],[role=switch],[role=menuitem],[role=slider]') || Object.keys(el).some(k => k.startsWith('__reactProps$') && typeof el[k]?.onClick === 'function');
  const enabled = el => !el.matches(':disabled,[aria-disabled=true]');
  const exposed = el => {
    if (el.closest('[inert]')) return false;
    const r = el.getBoundingClientRect();
    const top = document.elementFromPoint(Math.max(0, Math.min(innerWidth - 1, r.left + r.width / 2)), Math.max(0, Math.min(innerHeight - 1, r.top + r.height / 2)));
    return !top || el.contains(top) || top.contains(el);
  };
  const accent = (el, color) => {
    const probe = document.createElement('span');
    probe.style.color = 'var(--accent-text)'; el.append(probe);
    const match = getComputedStyle(probe).color === color;
    probe.remove(); return match;
  };
  const nodes = [...document.querySelectorAll('body *')].filter(visible);
  const label = el => (el.getAttribute('aria-label') || el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 100);
  const ownNodes = root => [root, ...root.querySelectorAll('*')].filter(el => visible(el) && (el === root || (!click(el) && ![...parents(el, root)].some(click))));
  function* parents(el, stop) { for (let p = el.parentElement; p && p !== stop; p = p.parentElement) yield p; }
  const findings = [];
  const selectionCue = el => {
    if (!el.matches('[aria-selected=true],[aria-checked=true],[aria-pressed=true],[data-state=active]')) return false;
    const group = el.closest('[role=tablist],[role=radiogroup],[role=group],.choice-row');
    if (!group) return false;
    const r = el.getBoundingClientRect();
    return [...group.querySelectorAll('[data-sliding-indicator]')].some(mark => {
      if (!visible(mark)) return false;
      const m = mark.getBoundingClientRect();
      return m.width >= 4 && m.height >= 1 && Math.min(r.right,m.right)-Math.max(r.left,m.left) >= 4 && m.top <= r.bottom+2 && m.bottom >= r.top;
    });
  };
  const graphic = part => {
    if (!visible(part)) return false;
    const r = part.getBoundingClientRect(), s = getComputedStyle(part);
    const paintedShape = !part.textContent.trim() && part.matches('[aria-hidden=true]') && r.width >= 12 && r.height >= 3 &&
      !['transparent', 'rgba(0, 0, 0, 0)'].includes(s.backgroundColor);
    if (paintedShape) return true;
    if (r.width < 8 || r.height < 8) return false;
    if (part.matches('svg,img,canvas,[data-book-cover]') || s.backgroundImage !== 'none') return true;
    return part.matches('[role=img]') && [...part.children].some(bar => {
      const b=bar.getBoundingClientRect(), color=getComputedStyle(bar).backgroundColor;
      return b.width>=1 && b.height>=3 && !['transparent','rgba(0, 0, 0, 0)'].includes(color);
    });
  };
  const underlayCue = el => {
    if (el.textContent.trim() || getComputedStyle(el).position !== 'absolute') return false;
    const r=el.getBoundingClientRect();
    return [...el.parentElement.querySelectorAll('*')].some(part => {
      if (el.contains(part) || !graphic(part)) return false;
      const p=part.getBoundingClientRect();
      return p.left>=r.left-1 && p.top>=r.top-1 && p.right<=r.right+1 && p.bottom<=r.bottom+1 &&
        (getComputedStyle(part).pointerEvents==='none' || part.matches('[data-book-cover]'));
    });
  };
  for (const el of nodes.filter(el => click(el) && enabled(el) && exposed(el))) {
    if (el.matches('input,select,textarea,[role=slider]') || !label(el)) continue;
    const own = ownNodes(el);
    const box=el.getBoundingClientRect();
    if (Math.min(box.bottom, innerHeight)-Math.max(box.top, 0) < Math.min(24, box.height*.5)) continue;
    if (!el.textContent.trim() && box.width>=innerWidth*.95 && box.height>=innerHeight*.95) continue;
    const cue = selectionCue(el) || underlayCue(el) || own.some(part => {
      const s = getComputedStyle(part);
      return graphic(part) ||
        (s.textDecorationLine.includes('underline') && !['transparent', 'rgba(0, 0, 0, 0)'].includes(s.textDecorationColor)) ||
        (part.textContent?.trim() && accent(part, s.color)) ||
        /[›»→↗+]\s*$/.test(part.textContent?.trim() || '') ||
        ['Top', 'Right', 'Bottom', 'Left'].some(side => parseFloat(s[`border${side}Width`]) > 0 && !['transparent', 'rgba(0, 0, 0, 0)'].includes(s[`border${side}Color`])) ||
        (part === el && !['transparent', 'rgba(0, 0, 0, 0)'].includes(s.backgroundColor) && s.backgroundColor !== getComputedStyle(el.parentElement).backgroundColor);
    });
    if (!cue) findings.push(`AFFORDANCE_CLICK ${el.tagName.toLowerCase()} ${label(el)}`);
  }
  for (const el of nodes) {
    if (!exposed(el) || ![...el.childNodes].some(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim())) continue;
    if (accent(el, getComputedStyle(el).color) && ![el, ...parents(el, document.body)].some(p => click(p) && enabled(p))) findings.push(`AFFORDANCE_ACCENT ${el.tagName.toLowerCase()} ${label(el)}`);
  }
  return [...new Set(findings)];
})()

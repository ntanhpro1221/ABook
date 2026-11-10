export type InkLine = { left: number; top: number; right: number; bottom: number };

/** A single rounded contour around adjacent lines, matching Compose's ReadInk. */
export function sentenceOutline(lines: InkLine[], radius = 8): string {
  const solid = lines.filter(r => r.right > r.left && r.bottom > r.top);
  if (!solid.length) return '';
  const points: number[][] = [[solid[0].left, solid[0].top]];
  solid.forEach((r, i) => points.push([r.right, r.top], [r.right, solid[i + 1]?.top ?? r.bottom]));
  points.push([solid.at(-1)!.left, solid.at(-1)!.bottom]);
  for (let i = solid.length - 1; i > 0; i--) points.push([solid[i].left, solid[i].top], [solid[i - 1].left, solid[i].top]);
  const distinct = points.filter((p, i) => i === 0 || p[0] !== points[i - 1][0] || p[1] !== points[i - 1][1]);
  const vertices = distinct.filter(([x, y], i, all) => {
    const p = all[(i + all.length - 1) % all.length], n = all[(i + 1) % all.length];
    return !((p[0] === x && n[0] === x) || (p[1] === y && n[1] === y));
  });
  const corners = vertices.map(([x, y], i, all) => {
    const p = all[(i + all.length - 1) % all.length], n = all[(i + 1) % all.length];
    const before = Math.hypot(p[0] - x, p[1] - y), after = Math.hypot(n[0] - x, n[1] - y);
    const r = Math.min(radius, before / 2, after / 2);
    return [x + (p[0] - x) / before * r, y + (p[1] - y) / before * r, x, y,
      x + (n[0] - x) / after * r, y + (n[1] - y) / after * r];
  });
  const last = corners.at(-1)!;
  return `M${last[4]},${last[5]} ` + corners.map(c => `L${c[0]},${c[1]} Q${c[2]},${c[3]} ${c[4]},${c[5]}`).join(' ') + ' Z';
}

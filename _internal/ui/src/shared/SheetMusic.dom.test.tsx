// @vitest-environment happy-dom
import { act, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, it, vi } from 'vitest';
import { SheetMusic } from './SheetMusic';
import { SheetLink } from './SheetControls';

it('keeps the music range and commits only on confirmation, with a collapsible navigation row', async () => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const commits = vi.fn();
  const animation = vi.spyOn(HTMLElement.prototype, 'animate').mockImplementation(() => ({ cancel() {}, onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  const navigate = vi.fn();
  const host = document.createElement('div'); document.body.append(host);
  const root = createRoot(host);
  function Panel() {
    const [enabled, setEnabled] = useState(true);
    return <SheetMusic enabled={enabled} busy={false} level={-20} onToggle={setEnabled} onLevel={commits}>
      <SheetLink label="Chọn nhạc" onClick={navigate}/>
    </SheetMusic>;
  }
  try {
    await act(async () => root.render(<Panel/>));
    const slider = host.querySelector('[role="slider"]')!;
    expect(slider.getAttribute('aria-valuemin')).toBe('-40');
    expect(slider.getAttribute('aria-valuemax')).toBe('-6');
    expect(slider.getAttribute('aria-valuetext')).toBe('−20 dB');
    await act(async () => slider.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true })));
    expect(commits).toHaveBeenLastCalledWith(-19);
    const link = host.querySelector<HTMLButtonElement>('button[aria-label="Chọn nhạc"]')!;
    expect(link.querySelector('svg')).not.toBeNull();
    await act(async () => link.click()); expect(navigate).toHaveBeenCalledOnce();
    await act(async () => host.querySelector<HTMLButtonElement>('[role="switch"]')!.click());
    expect(host.querySelector('.motion-collapse')?.hasAttribute('inert')).toBe(true);
  } finally {
    await act(async () => root.unmount()); host.remove(); animation.mockRestore();
  }
});

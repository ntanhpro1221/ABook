// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { expect, it, vi } from 'vitest';
import { CoverEditor } from './CoverEditor';
import type { BookSummary } from './api';
import { MOTION } from '@/shared/motion';

const api = vi.hoisted(() => vi.fn());
vi.mock('./api', () => ({ api }));
vi.mock('@/shared/CoverSearch', () => ({ CoverSearchDialog: () => null }));
vi.mock('@/shared/media', () => ({ useMediaQuery: () => true }));

it('suggests a local image only while artwork is missing, including narrow screens', async () => {
  vi.useFakeTimers();
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const host = document.createElement('div'); document.body.append(host);
  const root = createRoot(host);
  const client = new QueryClient();
  const click = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(() => {});
  vi.spyOn(HTMLElement.prototype, 'animate').mockImplementation(() => ({
    cancel: vi.fn(), onfinish: null, finished: Promise.resolve(),
  }) as unknown as Animation);
  const draw = (cover: unknown) => act(() => root.render(<QueryClientProvider client={client}>
    <CoverEditor book={{ id: 'synthetic', title: 'Synthetic', cover } as BookSummary} />
  </QueryClientProvider>));
  try {
    await draw(null);
    expect(host.querySelector('[data-testid="studio-missing-cover"]')?.textContent).toBe('Chưa có bìa');
    const pick = host.querySelector<HTMLButtonElement>('button[aria-label="Chọn ảnh"]')!;
    expect(pick.textContent?.trim()).toBe('Chọn ảnh');
    await act(() => pick.click());
    expect(click).toHaveBeenCalledOnce();
    expect(api).not.toHaveBeenCalled();
    await draw({ url: '/cover.jpg', version: 1 });
    const closing = host.querySelector('[data-testid="studio-missing-cover"]');
    expect(closing?.getAttribute('aria-hidden')).toBe('true');
    expect(closing?.hasAttribute('inert')).toBe(true);
    await act(() => vi.advanceTimersByTime(MOTION.mediumOut + 100));
    expect(host.querySelector('[data-testid="studio-missing-cover"]')).toBeNull();
  } finally {
    await act(() => root.unmount()); client.clear(); host.remove(); vi.restoreAllMocks(); vi.useRealTimers();
  }
});

// @vitest-environment node
import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';

it('uses the shared solid switch in audio controls', () => {
  for (const name of ['AudioFxPanel', 'TonePage']) {
    const source = readFileSync(new URL(`../listen/${name}.tsx`, import.meta.url), 'utf8');
    expect(source).toContain("import { Switch } from '@/desktop/Switch'");
    expect(source).not.toContain('Switch.Root');
  }
  const css = readFileSync(new URL('../styles.css', import.meta.url), 'utf8');
  expect(css.match(/\.ui-switch\s*\{([^}]+)\}/)?.[1]).toContain('background: var(--switch-off)');
  expect(css).toContain('.ui-switch[data-state="checked"] { background: var(--switch-on); }');
});

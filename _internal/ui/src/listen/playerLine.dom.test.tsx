import { describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import * as nodeModule from 'node:module';
import cases from '../../../tests/fixtures/player_line/cases.json';
import { lineOf, peopleOf } from './LineWishes';
import { lineEditing } from '@/shared/capabilities';
import { postLineFix, type Delivery } from '@/studio/ScriptTab';
const transport = vi.hoisted(() => ({ requests: [] as { endpoint: string; body: unknown }[] }));
vi.mock('@/studio/api', async (importOriginal) => ({
  ...await importOriginal<typeof import('@/studio/api')>(),
  api: async (path: string, options: { body: unknown }) => {
    transport.requests.push({ endpoint: path.split('/').at(-1)!, body: options.body });
    return { requestedAt: 10 };
  },
}));

// Execute the actual dialog sender, including its seen fields, without replacing it with a fixture-built request.
const dialogSource = readFileSync(new URL('./LineWishes.tsx', import.meta.url), 'utf8');
// The host Node provides this API; this checkout's lightweight Node declarations omit it.
const { stripTypeScriptTypes } = nodeModule as unknown as { stripTypeScriptTypes(source: string): string };
function dialogSender(name: 'speaker' | 'retake', context: Record<string, unknown>) {
  const block = dialogSource.split(`const ${name} = useMutation({`)[1];
  const expression = block.match(/mutationFn: ([\s\S]*?),\r?\n    onSuccess:/)![1];
  const js = stripTypeScriptTypes(`const send = ${expression}; send;`);
  return runInNewContext(js, {
    ...context,
    api: async (path: string, options: { body: unknown }) => {
      transport.requests.push({ endpoint: path.split('/').at(-1)!, body: options.body });
      return { requestedAt: 10 };
    },
  }) as (person?: unknown) => Promise<unknown>;
}

describe('shared native/web player sentence identity', () => {
  for (const row of cases) it(row.name, async () => {
    const script = { chapterId: 1, timed: true, title: '', segments: [row.source] } as any;
    const people = peopleOf(row.cast as any, script, row.wishes as any);
    const line = lineOf(row.source as any, 0, [...people.here, ...people.others], (row.wishes.lines as any)[row.source.stableId ?? '']);
    expect(line.stableId).toBe(row.source.stableId ?? '');
    expect(line.textSha256).toBe(row.source.textSha256 ?? '');
    expect(line.text).toBe(row.source.text);
    expect(lineEditing({ toolchain: false, workshop: false, link: false }, Boolean((row as any).listenOnly))?.mode)
      .toBe((row as any).listenOnly ? 'blocked' : 'wish');
    for (const step of row.expectedSteps) {
      const body = step.body as Record<string, unknown>;
      if (step.endpoint === 'speaker') {
        expect(body.lines).toEqual([{ stableId: line.stableId, textSha256: line.textSha256 }]);
        const person = (row as any).person;
        expect(body.speaker).toBe(person.value);
        expect(body.newGender).toBe(person.newGender ?? '');
      } else if (step.endpoint === 'line') {
        expect(body.stableId).toBe(line.stableId);
        expect(body.textSha256).toBe(line.textSha256);
      }
    }
    if (row.name === 'pending-new-person') expect(people.others.some(person => person.value === 'Bình' && person.newGender === 'unknown')).toBe(true);
    if (row.action === 'speaker' || row.action === 'review') {
      transport.requests.length = 0;
      const send = dialogSender(row.action === 'speaker' ? 'speaker' : 'retake', {
        book: { id: 'book' }, script, ref: { stableId: line.stableId, textSha256: line.textSha256 },
        wish: (row.wishes.lines as any)[line.stableId],
      });
      await send((row as any).person);
      const actual = transport.requests.map(step => {
        if (step.endpoint !== 'review') return step;
        const { stableId, ...body } = step.body as Record<string, unknown>;
        return { endpoint: step.endpoint, body: { ...body, lines: [{ stableId }] } };
      });
      expect(actual).toEqual(row.expectedSteps);
    }
    if (row.action === 'delivery' || row.action === 'spoken') {
      const change: Delivery = {};
      if (row.action === 'spoken') change.spoken = (row as any).spoken;
      else {
        const target = (row as any).delivery;
        if (target.kind !== line.kind) change.kind = target.kind;
        if (target.emotion !== line.emotion) change.emotion = target.emotion;
        if (target.intensity !== line.intensity) change.intensity = target.intensity;
        if (line.kind === 'narration' && target.kind !== 'narration') {
          change.speaker = (row as any).person.value;
          if ((row as any).person.newGender) change.newGender = (row as any).person.newGender;
        }
      }
      transport.requests.length = 0;
      await postLineFix('book', { stableId: line.stableId, textSha256: line.textSha256 }, change, line.lineWish);
      expect(transport.requests).toEqual(row.expectedSteps);
    }
  });
});

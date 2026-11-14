import type { ReactNode } from 'react';
import { SheetSection, SheetSwitch } from './SheetControls';
import { Collapse } from './Collapse';
import { ValuePicker } from './ValuePicker';
import { signedNumber } from '@/listen/labels';
import { LEVEL_MIN_DB, LEVEL_MAX_DB, LEVEL_STEP_DB } from './musicLevels';
import { S } from './strings.generated';

export function SheetMusic({ enabled, busy, level, onToggle, onLevel, children }: {
  enabled: boolean; busy: boolean; level: number; onToggle: (value: boolean) => void;
  onLevel: (value: number) => void; children: ReactNode;
}) {
  return <SheetSection title={S.s_nhac_nen_271fb292}>
    <SheetSwitch label={S.s_bat_f26cbc4a} checked={enabled} disabled={busy} onChange={onToggle}/>
    <Collapse open={enabled}><div className="flex min-w-0 flex-col gap-2 [&_[data-player-menu-row]]:px-0">
      <ValuePicker dense label={S.s_muc_nhac_nen_a45588ff} spec={{ min: LEVEL_MIN_DB, max: LEVEL_MAX_DB, step: LEVEL_STEP_DB, typical: [-30, -20, -10] }} value={level} format={v=>`${signedNumber(v)} dB`} onChange={onLevel}/>
      {children}
    </div></Collapse>
  </SheetSection>;
}

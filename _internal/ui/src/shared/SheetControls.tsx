import type { ReactNode } from 'react';
import { ChevronRight } from 'lucide-react';
import { Switch } from '@/desktop/Switch';

/** Flat groups and rows shared by player sheets. */
export function SheetSection({ title, children, first = false }: { title: string; children: ReactNode; first?: boolean }) {
  return <section className={`flex min-w-0 flex-col gap-2 ${first ? '' : 'pt-4'}`} aria-label={title}>
    <h2 className="text-xs font-medium text-fg-2">{title}</h2>{children}
  </section>;
}
export function SheetSwitch({ label, checked, disabled, hint, onChange }: {
  label: string; checked: boolean; disabled?: boolean; hint?: string; onChange: (value: boolean) => void;
}) {
  return <label className="flex min-h-12 items-center justify-between gap-4 text-sm text-fg">
    <span className="min-w-0">{label}{hint && <span className="mt-1 block text-xs text-fg-2">{hint}</span>}</span>
    <Switch label={label} checked={checked} disabled={disabled} onCheckedChange={onChange}/>
  </label>;
}
export function SheetLink({ label, value, onClick }: { label: string; value?: ReactNode; onClick: () => void }) {
  return <button type="button" aria-label={label} onClick={onClick} className="press flex min-h-12 w-full items-center gap-3 rounded-control text-left text-sm text-fg hover:bg-hover">
    <span className="min-w-0 flex-1">{label}</span>
    {value && <span className="min-w-0 max-w-[55%] text-right text-fg-2">{value}</span>}
    <ChevronRight aria-hidden="true" className="ink-end [--icon-w:1rem] size-4 shrink-0 text-fg-2"/>
  </button>;
}

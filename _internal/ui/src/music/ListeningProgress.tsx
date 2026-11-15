import type { LibraryPreview } from "./preview";
import { formatClock } from "../shared/format";
import { S } from "../shared/strings.generated";
import { useState } from "react";
import * as Slider from "@radix-ui/react-slider";
import { TickingValue } from "../shared/TickingValue";

/** Uses the book seek control's track, thumb and keyboard/pointer primitive. */
export function ListeningProgress({ preview, label = S.s_music_seek }: { preview: LibraryPreview; label?: string }) {
  const [drag, setDrag] = useState<number | null>(null);
  const value = drag ?? preview.position;
  return <div className="w-full" data-motion-live data-testid="music-listening-progress">
    <Slider.Root min={0} max={preview.duration || 1} step={0.1} value={[Math.min(value, preview.duration || 1)]}
      disabled={!preview.duration} className="group relative flex h-11 w-full touch-none select-none items-center"
      onValueChange={([target]) => setDrag(target)} onValueCommit={([target]) => { preview.seek(target); setDrag(null); }}
      onPointerCancel={() => setDrag(null)} onKeyDown={event => event.stopPropagation()}>
      <Slider.Track className="relative h-1 grow overflow-hidden rounded-full bg-line-strong"><Slider.Range className="absolute h-full rounded-full bg-accent" /></Slider.Track>
      <Slider.Thumb aria-label={label} aria-valuetext={`${formatClock(value)} / ${formatClock(preview.duration)}`}
        className="block size-4 rounded-full bg-accent shadow focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" />
    </Slider.Root>
    <div className="flex justify-between text-xs text-fg-2" data-motion-live><TickingValue>{formatClock(value)}</TickingValue><TickingValue>{formatClock(preview.duration)}</TickingValue></div>
  </div>;
}

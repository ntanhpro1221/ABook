import * as Slider from "@radix-ui/react-slider";
import { useEffect, useState } from "react";
import { cn } from "./cn";
import { MotionPresence } from "./MotionPresence";
import { MotionRegion } from "./MotionRegion";
import { DEFAULT_LEVEL_DB, LEVEL_MAX_DB, LEVEL_MIN_DB, LEVEL_RESET, LEVEL_STEP_DB, LEVEL_TITLE, clampLevel, levelLabel, levelNumber } from "./musicLevels";
import { Button } from "./ui";

const THUMB_PX = 16;

/** Chỗ của một mức trên thanh, đúng như Radix đặt núm (núm nằm gọn trong thanh: lệch nửa núm ở hai đầu) - vạch "mặc định" đứng đúng dưới núm khi về mặc định. */
function markLeft(value: number): string {
  const percent = ((value - LEVEL_MIN_DB) / (LEVEL_MAX_DB - LEVEL_MIN_DB)) * 100;
  return `calc(${percent}% + ${(THUMB_PX / 2) * (1 - percent / 50)}px)`;
}

/** Thanh trượt "Mức nhạc nền" (shared/musicLevels.ts): tên vùng + số dB phía trên, vạch mặc định trên thanh, "Về mặc định" hiện dần khi rời
 *  mặc định (bấm đúp thanh cũng về). Mức tính ở máy chủ (gainDb từng bài) nên kéo chỉ đổi chữ, thả tay / mỗi bước phím mới lưu (`onChange`).
 *  Đang lưu (`saving`) vẫn kéo được; lưu xong thì hiện mức máy chủ trả về. Dùng ở tab Nhạc nền của Studio, hộp sửa sách và menu Nhạc nền. */
export function MusicLevelSlider({ value, disabled = false, saving = false, onChange, className }: {
  value: number;
  disabled?: boolean;
  saving?: boolean;
  onChange: (levelDb: number) => void;
  className?: string;
}) {
  const [moving, setMoving] = useState<number | null>(null);
  // Máy chủ trả đúng mức vừa thả thì thôi giữ chữ tạm; lần lưu cũ về muộn (đã kéo tiếp) không kéo núm lùi lại.
  useEffect(() => setMoving((held) => (held === value ? null : held)), [value]);
  useEffect(() => {
    if (!saving) setMoving(null);
  }, [saving]);
  const shown = clampLevel(moving ?? value);
  const commit = (next: number) => {
    setMoving(next === value ? null : next);
    if (next !== value) onChange(next);
  };
  return (
    <div data-music-level className={cn("w-full", className)}>
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <MotionRegion as="span" motionKey={levelLabel(shown)} className="min-w-0">{levelLabel(shown)}</MotionRegion>
        <span className="tabular shrink-0 text-xs text-fg-2">{levelNumber(shown)}</span>
      </div>
      <Slider.Root
        className="group relative flex h-8 w-full touch-none select-none items-center"
        min={LEVEL_MIN_DB}
        max={LEVEL_MAX_DB}
        step={LEVEL_STEP_DB}
        value={[shown]}
        disabled={disabled}
        onValueChange={([next]) => setMoving(next)}
        onValueCommit={([next]) => commit(next)}
        onDoubleClick={() => !disabled && commit(DEFAULT_LEVEL_DB)}
        // Phím mũi tên đổi mức, không tua sách (phím tắt của trình phát nằm ở cửa sổ).
        onKeyDown={(event) => event.stopPropagation()}
      >
        <Slider.Track className="relative h-1 grow overflow-hidden rounded-full bg-line-strong">
          <Slider.Range className="absolute h-full rounded-full bg-accent" />
        </Slider.Track>
        <span aria-hidden="true" data-level-default className="pointer-events-none absolute top-1/2 h-3 w-0.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-fg-2" style={{ left: markLeft(DEFAULT_LEVEL_DB) }} />
        <Slider.Thumb
          aria-label={LEVEL_TITLE}
          aria-valuetext={`${levelLabel(shown)}, ${levelNumber(shown)}`}
          className="block size-4 rounded-full bg-accent shadow transition-[scale] duration-motion-fast active:scale-110 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
        />
      </Slider.Root>
      <MotionPresence open={shown !== DEFAULT_LEVEL_DB && !disabled}>
        <div className="flex justify-end">
          <Button size="sm" variant="ghost" className="-mr-3" onClick={() => commit(DEFAULT_LEVEL_DB)}>{LEVEL_RESET}</Button>
        </div>
      </MotionPresence>
    </div>
  );
}

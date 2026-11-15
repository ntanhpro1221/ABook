import type { ReactNode } from "react";
import { MotionRegion } from "./MotionRegion";

/** A state change stays in its fixed slot; clocks and percentages never restart it. */
export function StateIcon({ children, state, className }: { children: ReactNode; state?: unknown; className?: string }) {
  return <MotionRegion as="span" inPlace motionKey={state} data-state-icon className={className ?? "inline-grid shrink-0 place-items-center"}>{children}</MotionRegion>;
}
StateIcon.motionLive = true;

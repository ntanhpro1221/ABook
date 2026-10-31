import type { HTMLAttributes } from "react";

/** A live number changes in place. MotionRegion ignores this boundary, including unit changes. */
export function TickingValue({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return <span {...props} data-motion-live className={["ticking-value", className].filter(Boolean).join(" ")} />;
}
// Survives production minification; MotionRegion examines React elements before DOM commit.
TickingValue.motionLive = true;

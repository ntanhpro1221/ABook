import { flushSync } from "react-dom";
import { EASE, MOTION, prefersReducedMotion } from "@/shared/motion";
import { partTransform, type MorphPart } from "./nowPlayingMorph";

/** Move only the shared parts of the stage. Transport and the window frame keep
 * their layout and never participate in a document-wide View Transition.
 */
export function morphPlayerMode(screen: HTMLElement | null, update: () => void): void {
  const stage = screen?.querySelector<HTMLElement>("[data-np-stage]");
  if (!stage || prefersReducedMotion()) { update(); return; }
  const parts = ["cover", "chapter", "book"] as const;
  const before = new Map<MorphPart, DOMRect>();
  for (const part of parts) {
    const node = stage.querySelector<HTMLElement>(`[data-np="${part}"]`);
    if (!node) continue;
    const rect = node.getBoundingClientRect();
    if (rect.width && rect.height) before.set(part, rect);
  }
  flushSync(update);
  // These new children enter via the shared geometry below. A second generic
  // reveal would offset the measured endpoint and make the cover snap at the end.
  for (const node of stage.querySelectorAll<HTMLElement>(".motion-reveal")) {
    for (const animation of node.getAnimations?.() ?? []) animation.cancel();
  }
  for (const part of parts) {
    const from = before.get(part), node = stage.querySelector<HTMLElement>(`[data-np="${part}"]`);
    if (!from || !node) continue;
    const to = node.getBoundingClientRect();
    if (!to.width || !to.height) continue;
    node.animate([
      { transformOrigin: "0 0", transform: partTransform(part, from, to) },
      { transformOrigin: "0 0", transform: "none" },
    ], { duration: MOTION.medium, easing: EASE.standard });
  }
  stage.querySelector<HTMLElement>("[data-read-along]")?.animate([
    { transform: "translateY(16px)", clipPath: "inset(100% 0 0)" },
    { transform: "none", clipPath: "inset(0)" },
  ], { duration: MOTION.medium, easing: EASE.decelerate });
}

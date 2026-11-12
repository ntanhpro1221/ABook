import * as Radix from "@radix-ui/react-dropdown-menu";
import { forwardRef, useRef, type ComponentPropsWithoutRef, type ComponentRef, type PointerEvent } from "react";

export * from "@radix-ui/react-dropdown-menu";

/** A menu may appear beneath the opening pointer before it is released. Radix
 * treats that unmatched release as a selection; require a press inside the menu. */
function useOpeningReleaseGuard({ onPointerDownCapture, onPointerUpCapture, onPointerCancelCapture }: ComponentPropsWithoutRef<typeof Radix.Content>) {
  const pressed = useRef<number | null>(null);
  return {
    onPointerDownCapture: (event: PointerEvent<HTMLDivElement>) => {
      pressed.current = event.pointerId;
      onPointerDownCapture?.(event);
    },
    onPointerUpCapture: (event: PointerEvent<HTMLDivElement>) => {
      if (pressed.current !== event.pointerId) {
        event.preventDefault();
        event.stopPropagation();
      }
      pressed.current = null;
      onPointerUpCapture?.(event);
    },
    onPointerCancelCapture: (event: PointerEvent<HTMLDivElement>) => {
      pressed.current = null;
      onPointerCancelCapture?.(event);
    },
  };
}

export const Content = forwardRef<ComponentRef<typeof Radix.Content>, ComponentPropsWithoutRef<typeof Radix.Content>>(
  function MenuContent(props, ref) { return <Radix.Content {...props} {...useOpeningReleaseGuard(props)} ref={ref} />; });
export const SubContent = forwardRef<ComponentRef<typeof Radix.SubContent>, ComponentPropsWithoutRef<typeof Radix.SubContent>>(
  function SubmenuContent(props, ref) { return <Radix.SubContent {...props} {...useOpeningReleaseGuard(props)} ref={ref} />; });

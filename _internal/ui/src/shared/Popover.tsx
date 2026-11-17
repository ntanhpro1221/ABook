import * as Radix from "@radix-ui/react-popover";
import { forwardRef, type ComponentPropsWithoutRef, type ComponentRef } from "react";
import { useOutsideShield } from "./outsideShield";

export * from "@radix-ui/react-popover";

/** Popover của Radix không modal: bấm ra ngoài vừa đóng vừa tới thứ nằm dưới. Ở đây bấm ra ngoài chỉ đóng (outsideShield.ts), như Qt / Android. */
export const Content = forwardRef<ComponentRef<typeof Radix.Content>, ComponentPropsWithoutRef<typeof Radix.Content>>(
  function PopoverContent(props, ref) { return <Radix.Content {...props} {...useOutsideShield(ref, props.onInteractOutside)} />; });

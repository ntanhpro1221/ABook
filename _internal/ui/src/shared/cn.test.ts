import { expect, it } from "vitest";
import { cn } from "./cn";

it("keeps semantic text sizes independent of foreground colors", () => {
  expect(cn("text-accent-ink", "text-body")).toBe("text-accent-ink text-body");
  expect(cn("text-body", "text-fg-2")).toBe("text-body text-fg-2");
  expect(cn("text-body-small", "text-lg")).toBe("text-lg");
  expect(cn("text-sm", "text-caption")).toBe("text-caption");
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { expect, it, vi } from "vitest";

const h = vi.hoisted(() => ({ state: "ready" }));
vi.mock("@/listen/player", () => ({ usePlayer: () => ({ track: { bookId: "book", chapterId: 1 }, queue: [{ id: 1, state: h.state }], musicBroken: false }) }));
import { TooltipProvider } from "@/shared/ui";
import { musicEditView } from "@/listen/EditBook";
import { MusicMenu } from "@/listen/PlayerViews";

function menu(data: unknown): string {
  const client = new QueryClient();
  client.setQueryData(["listen", "edit-music", "book"], data);
  const html = renderToString(<QueryClientProvider client={client}><TooltipProvider><MusicMenu /></TooltipProvider></QueryClientProvider>);
  client.clear();
  return html;
}

const project = { plan: { enabled: true, levelDb: -20, scenes: [{ chapterId: 1, start: 0, end: 120, link: "cached" }] }, overrides: { enabled: true, levelDb: -20 }, taxonomy: {}, error: "" };

it("a Studio project's chapter with audio and a music plan has the music control in the player", () => {
  expect(menu(project)).toContain("Nhạc nền");
});

it("a project without any music scene shows no control, like a packaged book without music", () => {
  expect(menu({ ...project, plan: { enabled: true, levelDb: -20, scenes: [] } })).not.toMatch(/<button|Nhạc nền/);
  expect(menu({ ...project, plan: null })).not.toMatch(/<button|Nhạc nền/);
});

it("packaged audio with the same music keeps its control", () => {
  expect(menu({ package: true, hasMusic: true, enabled: true, levelDb: -20, defaultLevelDb: -20, cues: [] })).toContain("Nhạc nền");
});

it("the project's mute and level are read from its overrides", () => {
  expect(musicEditView({ ...project, overrides: { enabled: false, levelDb: -26 } })).toMatchObject({ project: true, hasMusic: true, enabled: false, levelDb: -26 });
  expect(musicEditView({ ...project, overrides: {} })).toMatchObject({ enabled: true, levelDb: -20 });
});

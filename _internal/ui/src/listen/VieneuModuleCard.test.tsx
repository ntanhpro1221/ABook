import { expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { VieneuModuleCard, type VieneuBackend } from "./VieneuModuleCard";
import { VIENEU_COPY, type VieneuStatus } from "./vieneuModule";

it("offers cleanup for an incomplete voice with removable bytes", () => {
  const status: VieneuStatus = {
    state: "missing", done: 0, total: 0, error: "", supported: true, reason: "",
    choices: [{ id: "turbo", label: "Giọng VieNeu", detail: "", needs: [], bytes: 10,
      installed: false, recommended: false, default: false, removable: true }],
    parts: [], outdatedParts: [], outdatedBytes: 0, benchmark: {}, benchmarking: false,
    suggestion: null, device: { cores: 4, ramGb: 8, gpu: "", runs: "cpu" }, recommended: "turbo",
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(["readaloud", VIENEU_COPY.key], status);
  const action = async () => status;
  const backend: VieneuBackend = { status: action, start: action, measure: action, remove: action, voices: async () => [] };
  const html = renderToStaticMarkup(<QueryClientProvider client={client}><VieneuModuleCard backend={backend} /></QueryClientProvider>);
  expect(html).toContain("Xoá phần đã tải");
  client.clear();
});

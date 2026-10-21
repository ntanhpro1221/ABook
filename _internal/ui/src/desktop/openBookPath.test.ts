import { expect, it, vi } from "vitest";
import { ReadCancelled, readSessions } from "@/listen/importQueue";

const mocks = vi.hoisted(() => ({ navigate: vi.fn(), invalidate: vi.fn(), api: vi.fn(), success: vi.fn(), error: vi.fn() }));
vi.mock("react", async (original) => ({ ...await original<typeof import("react")>(), useCallback: (callback: unknown) => callback }));
vi.mock("react-router", async (original) => ({ ...await original<typeof import("react-router")>(), useNavigate: () => mocks.navigate }));
vi.mock("@tanstack/react-query", async (original) => ({ ...await original<typeof import("@tanstack/react-query")>(), useQueryClient: () => ({ invalidateQueries: mocks.invalidate }) }));
vi.mock("@/studio/api", async (original) => ({ ...await original<typeof import("@/studio/api")>(), api: mocks.api }));
vi.mock("sonner", async (original) => ({ ...await original<typeof import("sonner")>(), toast: Object.assign(vi.fn(), { success: mocks.success, error: mocks.error }) }));

it.each([
  [{ id: "late", how: "new" }, ["listen"]],
  [{ id: "late", how: "studio" }, ["library"]],
])("does not navigate or toast when the API returns after the dialog closed, but the library still shows the imported book", async (book, key) => {
  vi.clearAllMocks();
  let resolve!: (book: unknown) => void;
  mocks.api.mockReturnValue(new Promise((done) => { resolve = done; }));
  const { useOpenBookPath } = await import("./App");
  const sessions = readSessions();
  const opening = useOpenBookPath()("a.abook", sessions.start());
  sessions.cancel();
  resolve(book);
  await expect(opening).rejects.toBeInstanceOf(ReadCancelled);
  expect(mocks.navigate).not.toHaveBeenCalled();
  expect(mocks.invalidate).toHaveBeenCalledTimes(1);
  expect(mocks.invalidate).toHaveBeenCalledWith({ queryKey: key });
  expect(mocks.success).not.toHaveBeenCalled();
  expect(mocks.error).not.toHaveBeenCalled();
});

it("a cancelled open that imported nothing refreshes nothing", async () => {
  vi.clearAllMocks();
  mocks.api.mockResolvedValue({ id: null, error: "hỏng", file: "a.abook" });
  const { useOpenBookPath } = await import("./App");
  const sessions = readSessions();
  const session = sessions.start();
  sessions.cancel();
  await expect(useOpenBookPath()("a.abook", session)).rejects.toBeInstanceOf(ReadCancelled);
  expect(mocks.invalidate).not.toHaveBeenCalled();
  expect(mocks.error).not.toHaveBeenCalled();
});

it("opens a live result and still supports callers outside the dialog", async () => {
  mocks.api.mockResolvedValue({ id: "live", how: "new" });
  const { useOpenBookPath } = await import("./App");
  const opening = useOpenBookPath();
  await expect(opening("a.abook", readSessions().start())).resolves.toBe(true);
  await expect(opening("b.abook")).resolves.toBe(true);
  expect(mocks.navigate).toHaveBeenLastCalledWith("/book/live");
});

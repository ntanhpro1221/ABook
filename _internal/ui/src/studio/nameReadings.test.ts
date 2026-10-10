import { describe, expect, it } from "vitest";
import { withReading, type NameReadings } from "./NameReadings";

const item = { surface: "Lucien", spoken: "Lu-xi-ên", byListener: false, lines: 12, requested: null, example: null };
const other = { surface: "Heidi", spoken: "Hai-đi", byListener: true, lines: 4, requested: null, example: null };
const data: NameReadings = { items: [item, other], unseen: 3 };

describe("withReading", () => {
  it("shows a new reading as waiting to be applied and leaves the others alone", () => {
    const next = withReading(data, item, "Lu-si-en");
    expect(next.items[0]).toMatchObject({ surface: "Lucien", spoken: "Lu-xi-ên", requested: "Lu-si-en", byListener: false });
    expect(next.items[1]).toBe(other);
    expect(next.unseen).toBe(3);
    expect(data.items[0].requested).toBeNull();
  });
  it("keeping the current reading waits for nothing and counts as the listener's choice", () => {
    const next = withReading({ items: [{ ...item, requested: "Lu-si-en" }, other], unseen: 0 }, item, "Lu-xi-ên");
    expect(next.items[0]).toMatchObject({ requested: null, byListener: true });
  });
  it("a name not in the list yet waits for the server, so a refused reading keeps its box open (soát UX a23)", () => {
    const fresh = { surface: "Hailkes", spoken: "", byListener: false, lines: 0, requested: null, example: null };
    expect(withReading(data, fresh, "Hên-khơ")).toBe(data);
  });
});

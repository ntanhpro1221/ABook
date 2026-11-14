import { beforeEach, expect, it, vi } from "vitest";
import cases from "../../../tests/fixtures/studio_edits/cases.json";
import { postLineFix } from "./ScriptTab";
import { api } from "./api";
import { runInNewContext } from "node:vm";
import qtScript from "../../../desktop_qt/qml/ScriptLogic.js?raw";
import qtStore from "../../../desktop_qt/qml/ScriptStore.qml?raw";
import copy from "../../../ui_strings/vi.json";

vi.mock("./api", () => ({ api: vi.fn() }));

beforeEach(() => vi.mocked(api).mockReset());

for (const id of ["narration-dialogue", "thought"]) {
  it(`matches the Android request fixture: ${id}`, async () => {
    const scenario = cases.find(item => item.id === id)!;
    const expected = scenario.expected[0].body;
    vi.mocked(api).mockResolvedValue({ requestedAt: 42 });
    await postLineFix("b1", { stableId: "c1s0", textSha256: "sha-c1s0" }, { kind: scenario.kind!, speaker: "NATASHA" }, null);
    expect(api).toHaveBeenCalledExactlyOnceWith("/api/books/b1/line", { method: "POST", body: expected });
  });
}

it("withdraws the first receipt if a new speaker request fails", async () => {
  vi.mocked(api).mockResolvedValueOnce({ requestedAt: 42 }).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce({});
  await expect(postLineFix("b1", { stableId: "c1s0", textSha256: "sha-c1s0" }, { kind: "thought", speaker: "Bác Trực", newGender: "male" }, null)).rejects.toThrow("offline");
  expect(api).toHaveBeenNthCalledWith(3, "/api/books/b1/line", { method: "POST", body: { stableId: "c1s0", withdraw: true, requestedAt: 42 } });
});

const qtLogic = runInNewContext(qtScript.replace(/^\.(?:import|pragma).*$/gm, "") +
  "\n({ref, seenDelivery, deliveryChange, deliveryReady, EMOTIONS, KINDS, LEVELS})", { S: copy.strings });

function qtRequests(kind: string, newGender = "", failSpeaker = false) {
  const calls: { endpoint: string; body: Record<string, unknown> }[] = [];
  const line = { stableId: "c1s0", textSha256: "sha-c1s0", kind: "narration", emotion: "neutral", intensity: 0, spoken: null, text: "Đèn sân đã sáng." };
  const picked = { value: newGender ? "Bác Trực" : "NATASHA", newGender };
  const change = qtLogic.deliveryChange(line, kind, "neutral", 0, picked, line.text);
  expect(qtLogic.deliveryReady(line, kind, change)).toBe(true);
  const quietly = (_method: string, path: string, body: Record<string, unknown>, done: (answer: unknown, error: string) => void) => {
    calls.push({ endpoint: path.slice(1), body });
    if (failSpeaker && path === "/speaker") done(null, "offline");
    else done({ requestedAt: 42 }, "");
  };
  const source = qtStore.match(/    function postLineFix\([\s\S]*?(?=\n    function fixLine\()/)![0];
  const post = runInNewContext(source + "\npostLineFix", { Script: qtLogic, quietly, root: { quietly } });
  post(line, change, () => undefined);
  return calls;
}

for (const id of ["narration-dialogue", "thought"]) {
  it(`matches the Qt request path against the same fixture: ${id}`, () => {
    const scenario = cases.find(item => item.id === id)!;
    expect(qtRequests(scenario.kind!)).toEqual(scenario.expected);
  });
}

it("Qt withdraws the same first receipt after a failed new-person request", () => {
  expect(qtRequests("thought", "male", true).at(-1)).toEqual({
    endpoint: "line", body: { stableId: "c1s0", withdraw: true, requestedAt: 42 },
  });
});

it("keeps Qt and web delivery labels identical", async () => {
  const { EMOTIONS, KINDS } = await import("./ScriptTab");
  expect(qtLogic.EMOTIONS).toEqual(EMOTIONS);
  expect(qtLogic.KINDS).toEqual(KINDS);
  expect(qtLogic.LEVELS).toEqual(["Nhẹ", "Vừa", "Mạnh", "Rất mạnh"]);
});

// Nghe ngay delegates spoken forms to Python; exercise that backend with the
// same fixture as pytest and Android rather than maintaining a TS normaliser.
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import { beforeAll, expect, it } from "vitest";

const internal = path.resolve(import.meta.dirname, "../../..");
const fixture = JSON.parse(readFileSync(path.join(internal, "tests/fixtures/readaloud/spoken/reading_forms.json"), "utf8")) as {
  cases: { id: string; text: string; said: string }[];
};
let actual: { shown: string; local: string; edge: string; studio: string }[];
beforeAll(() => {
  const python = process.env.ABOOK_TEST_PYTHON ?? path.join(internal, "runtime/.venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
  actual = JSON.parse(execFileSync(python, ["-X", "utf8", "-c", `
import json, sys
from abook.readaloud import vieneu, spoken
from abook.readaloud.studio_tn import studio_tn
result = []
for case in json.load(sys.stdin)['cases']:
    text = case['text']
    shown, units = vieneu.units(text, 256)
    result.append(dict(shown=' '.join(shown), local=' '.join(p for u in units for p in u.pieces if p),
        edge=spoken.layout(text, None)[0], studio=studio_tn(text, None, True)[0]))
json.dump(result, sys.stdout, ensure_ascii=False)
`], { cwd: internal, input: JSON.stringify(fixture), encoding: "utf8", env: { ...process.env, CUDA_VISIBLE_DEVICES: "-1", QT_QPA_PLATFORM: "offscreen" } }));
});

it.each(fixture.cases.map((c, index) => ({ ...c, index })))("$id: same spoken words, original story preserved", ({ text, said, index }) => {
  expect(actual[index]).toEqual({ shown: text, local: said, edge: said, studio: said });
});

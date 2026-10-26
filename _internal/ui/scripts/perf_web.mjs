// Chạy các bài đo hiệu năng web (src/perf/*.perf.dom.test.tsx) nhiều lần rồi in bảng trung vị - số cho docs/PERF_WEB.md.
//
//   node scripts/perf_web.mjs [--runs 3] [--json FILE]
//
// Mỗi lần chạy là một tiến trình vitest mới (happy-dom, bản dev của React): thời gian chỉ để so trước / sau trên CÙNG máy, không phải số
// của trình duyệt thật. Số lần vẽ và số ảnh chuyển cảnh thì tất định - đó là số chính.
import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import path from "node:path";

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const at = args.indexOf(name);
  return at >= 0 ? args[at + 1] : fallback;
};
const runs = Number(option("--runs", "3"));
const jsonFile = option("--json", null);
const ui = path.resolve(import.meta.dirname, "..");

/** title -> phase name -> list of samples */
const samples = new Map();
const extras = new Map();
for (let run = 0; run < runs; run++) {
  let output = "";
  try {
    output = execFileSync(process.execPath, [path.join(ui, "node_modules/vitest/vitest.mjs"), "run", "src/perf", "--silent=false", "--reporter=dot"], {
      cwd: ui, encoding: "utf8", maxBuffer: 64 * 1024 * 1024, stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (error) {
    // Trần trong test trượt (bản cũ khi đo "trước"): số vẫn in ra, vẫn dùng được.
    output = `${error.stdout ?? ""}`;
  }
  for (const line of output.split("\n")) {
    const at = line.indexOf("[perf-json] ");
    if (at < 0) continue;
    const report = JSON.parse(line.slice(at + "[perf-json] ".length));
    extras.set(report.title, { watch: report.watch, ...report.extra });
    const phases = samples.get(report.title) ?? new Map();
    for (const phase of report.phases) phases.set(phase.name, [...(phases.get(phase.name) ?? []), phase]);
    samples.set(report.title, phases);
  }
  process.stderr.write(`lần ${run + 1}/${runs} xong\n`);
}

const median = (values) => {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = sorted.length >> 1;
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
};
const round = (value) => Math.round(value * 10) / 10;

const result = {};
for (const [title, phases] of samples) {
  const extra = extras.get(title);
  console.log(`\n### ${title}\n`);
  console.log(Object.entries(extra).filter(([key]) => key !== "watch").map(([key, value]) => `${key}: ${value}`).join(" · "));
  console.log(`\n| pha | ms (trung vị ${runs} lần) | ${extra.watch} vẽ lại | mọi component vẽ lại | ảnh chuyển cảnh (nút DOM) |\n|---|---|---|---|---|`);
  result[title] = { extra, phases: {} };
  for (const [name, list] of phases) {
    const row = {
      ms: round(median(list.map((phase) => phase.ms))),
      watched: round(median(list.map((phase) => phase.watched))),
      components: round(median(list.map((phase) => phase.components))),
      snapshots: round(median(list.map((phase) => phase.snapshots))),
      snapshotNodes: round(median(list.map((phase) => phase.snapshotNodes))),
    };
    result[title].phases[name] = row;
    console.log(`| ${name} | ${row.ms} | ${row.watched} | ${row.components} | ${row.snapshots} (${row.snapshotNodes}) |`);
  }
}
if (jsonFile) writeFileSync(jsonFile, JSON.stringify(result, null, 2));

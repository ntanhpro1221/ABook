// Đo bản dựng máy tính (vite.config.ts): cỡ từng chunk JS / CSS (thô và gzip) và phần mỗi nhóm mã nguồn chiếm trong chunk, đọc từ
// sourcemap. Không thư viện ngoài: tự giải trường mappings (VLQ).
//
//   node scripts/bundle_report.mjs [--out DIR] [--top 25] [--json FILE]
//
// Dựng vào DIR (mặc định thư mục tạm, không đụng abook/webui/static) kèm sourcemap rồi in bảng.
// Số dùng cho docs/PERF_WEB.md: "trang đầu" = chunk vào + mọi chunk nó import tĩnh (tải trước khi app vẽ được gì).
import { execFileSync } from "node:child_process";
import { mkdtempSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { gzipSync } from "node:zlib";

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const at = args.indexOf(name);
  return at >= 0 ? args[at + 1] : fallback;
};
const ui = path.resolve(import.meta.dirname, "..");
const out = path.resolve(option("--out", mkdtempSync(path.join(tmpdir(), "abook-bundle-"))));
const top = Number(option("--top", "25"));
const jsonFile = option("--json", null);

execFileSync(process.execPath, [path.join(ui, "node_modules/vite/bin/vite.js"), "build", "--outDir", out, "--emptyOutDir", "--sourcemap"], {
  cwd: ui,
  stdio: ["ignore", "ignore", "inherit"],
});

const assets = path.join(out, "assets");
const kb = (bytes) => (bytes / 1024).toFixed(1);

/** Nhóm của một file nguồn: gói npm (theo tên gói) hay thư mục trong src/. */
function groupOf(source) {
  const clean = source.replace(/\\/g, "/");
  const npm = clean.match(/node_modules\/((?:@[^/]+\/)?[^/]+)/);
  if (npm) return npm[1];
  const local = clean.match(/src\/([^/]+\/)?([^/]+)$/);
  if (local) return `src/${local[1] ?? ""}${local[2]}`;
  return clean;
}

/** Số byte của chunk thuộc về từng nhóm nguồn: mỗi đoạn mã sinh ra tính cho nguồn của mapping đứng trước nó. */
function bytesBySource(code, map) {
  const lines = code.split("\n");
  const sizes = new Map();
  const add = (source, bytes) => sizes.set(source, (sizes.get(source) ?? 0) + bytes);
  const entries = map.mappings ? decode(map) : [];
  entries.sort((a, b) => a.line - b.line || a.column - b.column);
  let cursor = 0;
  for (let line = 0; line < lines.length; line++) {
    const text = lines[line];
    const here = [];
    while (cursor < entries.length && entries[cursor].line === line) here.push(entries[cursor++]);
    let previous = 0;
    let owner = "(không rõ)";
    for (const entry of here) {
      add(owner, Buffer.byteLength(text.slice(previous, entry.column)));
      previous = entry.column;
      owner = entry.source ?? "(không rõ)";
    }
    add(owner, Buffer.byteLength(text.slice(previous)) + 1);
  }
  return sizes;
}

/** Giải trường mappings (VLQ base64) thành {line, column, source}. */
function decode(payload) {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  const value = new Map([...chars].map((char, index) => [char, index]));
  const result = [];
  let source = 0;
  let line = 0;
  for (const row of payload.mappings.split(";")) {
    let column = 0;
    if (row) {
      for (const segment of row.split(",")) {
        const fields = [];
        let shift = 0;
        let number = 0;
        for (const char of segment) {
          const digit = value.get(char);
          number += (digit & 31) << shift;
          if (digit & 32) shift += 5;
          else {
            fields.push(number & 1 ? -(number >> 1) : number >> 1);
            shift = 0;
            number = 0;
          }
        }
        column += fields[0];
        if (fields.length > 1) source += fields[1];
        result.push({ line, column, source: fields.length > 1 ? payload.sources[source] : null });
      }
    }
    line++;
  }
  return result;
}

const files = readdirSync(assets).filter((name) => /\.(js|css)$/.test(name));
const chunks = files.map((name) => {
  const code = readFileSync(path.join(assets, name));
  return { name, bytes: code.length, gzip: gzipSync(code, { level: 9 }).length };
});

// Trang đầu: index.html nạp gì (script module + modulepreload + stylesheet).
const html = readFileSync(path.join(out, "index.html"), "utf8");
const initialNames = new Set([...html.matchAll(/(?:src|href)="\.\/assets\/([^"]+\.(?:js|css))"/g)].map((match) => match[1]));
const initial = chunks.filter((chunk) => initialNames.has(chunk.name));
const sum = (list, key) => list.reduce((total, chunk) => total + chunk[key], 0);

console.log(`\nChunk (${out})`);
for (const chunk of [...chunks].sort((a, b) => b.bytes - a.bytes)) {
  console.log(`${initialNames.has(chunk.name) ? "*" : " "} ${chunk.name.padEnd(48)} ${kb(chunk.bytes).padStart(9)} KB  gzip ${kb(chunk.gzip).padStart(7)} KB`);
}
const js = chunks.filter((chunk) => chunk.name.endsWith(".js"));
console.log(`\nTrang đầu (*): ${kb(sum(initial, "bytes"))} KB, gzip ${kb(sum(initial, "gzip"))} KB`);
console.log(`Mọi JS: ${kb(sum(js, "bytes"))} KB, gzip ${kb(sum(js, "gzip"))} KB; mọi CSS: ${kb(sum(chunks.filter((c) => c.name.endsWith(".css")), "bytes"))} KB`);

const groups = new Map();
for (const name of files.filter((file) => file.endsWith(".js"))) {
  const mapFile = path.join(assets, `${name}.map`);
  let map;
  try {
    map = JSON.parse(readFileSync(mapFile, "utf8"));
  } catch {
    continue;
  }
  for (const [source, bytes] of bytesBySource(readFileSync(path.join(assets, name), "utf8"), map)) {
    const group = groupOf(source);
    const entry = groups.get(group) ?? { bytes: 0, initial: 0 };
    entry.bytes += bytes;
    if (initialNames.has(name)) entry.initial += bytes;
    groups.set(group, entry);
  }
}
console.log(`\nNhóm nguồn lớn nhất (KB thô sau nén mã; cột 2 = phần nằm ở trang đầu)`);
for (const [group, entry] of [...groups].sort((a, b) => b[1].bytes - a[1].bytes).slice(0, top)) {
  console.log(`  ${group.padEnd(44)} ${kb(entry.bytes).padStart(8)} ${kb(entry.initial).padStart(8)}`);
}

if (jsonFile) {
  writeFileSync(jsonFile, JSON.stringify({
    chunks, initial: { bytes: sum(initial, "bytes"), gzip: sum(initial, "gzip") },
    groups: Object.fromEntries([...groups].sort((a, b) => b[1].bytes - a[1].bytes)),
  }, null, 2));
}

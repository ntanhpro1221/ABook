// Chữ của người dùng không bao giờ bị cắt (luật cứng của chủ sách): tên sách, tên chương, tên hồ sơ, tên file đã chọn xuống dòng, không "…" (truncate) và không
// cắt sau N dòng (line-clamp). Máy quét mã giao diện máy tính / phần Nghe: mọi khối có truncate / line-clamp mà chữ bên trong là tên sách / chương.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { cwd } from "node:process";
import { expect, it } from "vitest";

const root = `${cwd()}/src`;
function sourceFiles(dir: string, prefix = ""): string[] {
  return readdirSync(`${root}/${dir}/${prefix}`).flatMap((file) => {
    const relative = `${prefix}${file}`;
    return statSync(`${root}/${dir}/${relative}`).isDirectory() ? sourceFiles(dir, `${relative}/`) : [relative];
  });
}
/** Biểu thức trong JSX in tên sách / chương / tên do người dùng đặt. */
const USER_TEXT = /book\.title|bookTitle|chapterTitle|chapter\.(sub)?title|fullTitle|displayTitle\(|titleOf\(|labels\.get\(|item\.label|\{item\.name\}|active\??\.name|\b(?:target|only|phone|device|computer|found|peer|profile|record|remote|sharer|session|push|sync)\??\.(?:name|displayName|label)\b|\bnames\.current\b|\b(?:deviceName|phoneName|profileName|machineName|recordName)\b|^\{(name|title|sub|where)\}$/;
const DEVICE_PROFILE_TEXT = /\b(?:target|only|phone|device|computer|found|peer|profile|record|remote|sharer|session|push|active|sync)\??\.(?:name|displayName|label)\b|\bnames\.current\b|\b(?:deviceName|phoneName|profileName|machineName|recordName)\b/;
/** Derived location/status lines also contain the remote computer's name. */
const DEVICE_LINE = /\b(?:remoteName|remotePlace|computerOf|peerBarLine|onComputerLine)\(|^\{?status\}?$/;
/** Chỗ còn cắt có lý do (đã ghi trong báo cáo, chờ chủ sách quyết): thanh phát thu nhỏ cao cố định một dòng tên chương + một dòng tên sách (DESIGN 6),
 *  tên đầy đủ ở tooltip `title` của nút. */
const ALLOWED = new Set(["listen/PlayerViews.tsx:{track.chapterTitle}#mini", "listen/PlayerViews.tsx:{track.bookTitle}#mini"]);
/** Tên máy trong chỗ hẹp (ShortName): rút có chủ đích, tên đầy đủ ở tooltip - tên máy không phải chữ của sách. */
const ALLOWED_ANYWHERE = new Set(["shared/ShortName.tsx:{name}"]);

it("không khối nào cắt tên sách / tên chương / tên người dùng đặt bằng truncate hay line-clamp", () => {
  const clipped: string[] = [];
  for (const dir of ["listen", "desktop", "shared", "studio"]) {
    for (const file of sourceFiles(dir)) {
      if (!file.endsWith(".tsx") || file.includes(".test.")) continue;
      const source = readFileSync(`${root}/${dir}/${file}`, "utf8");
      const tag = /className=(?:"[^"]*\b(?:truncate|line-clamp-\d)\b[^"]*"|\{[^}]*\b(?:truncate|line-clamp-\d)\b[^}]*\})[^>]*>\s*([^<]*)/g;
      for (const match of source.matchAll(tag)) {
        const inner = match[1].trim();
        const expression = inner.match(/\{[^{}]*\}/g)?.find((part) => USER_TEXT.test(part.slice(1, -1).trim()) || USER_TEXT.test(part) || DEVICE_LINE.test(part.slice(1, -1).trim()));
        if (!expression) continue;
        // Extend the Studio scan to device/profile names; book text there has a separate audit scope.
        if (dir === "studio" && !DEVICE_PROFILE_TEXT.test(expression)) continue;
        const where = `${dir}/${file}:${expression}`;
        if (ALLOWED_ANYWHERE.has(where)) continue;
        // Thanh phát thu nhỏ: khối MotionRegion của tên chương ngay trong nút "Mở trình phát".
        const before = source.slice(Math.max(0, (match.index ?? 0) - 900), match.index);
        if (ALLOWED.has(`${where}#mini`) && before.includes('aria-label={S.s_mo_man_hinh_dang_nghe_')) continue;
        // Dòng tên sách của cùng thanh thu nhỏ (nút `data-track-book`, chỉ look="bar" cắt; tên đầy đủ ở tooltip `title`).
        if (ALLOWED.has(`${where}#mini`) && before.includes('data-track-book') && /look === "bar" && "[^"]*truncate/.test(source.slice(match.index ?? 0, (match.index ?? 0) + 400))) continue;
        clipped.push(`${where} (dòng ${source.slice(0, match.index).split("\n").length})`);
      }
    }
  }
  expect(clipped).toEqual([]);
});

it("máy dò bắt tên thiết bị và hồ sơ, cả trong câu dịch", () => {
  for (const expression of ["target.name", "only.name", "phone.name", "device.name", "computer.name", "found.name", "peer.name", "info.peer.name", "profile.name", "record.name", "active?.name", "push.name", "sync.name", "names.current", "S.s_dang_phat_tren_0_62a989a1(names.current)", "deviceName", "profileName"]) {
    expect(USER_TEXT.test(expression), expression).toBe(true);
    const old = `<span className="min-w-0 flex-1 truncate">{${expression}}</span>`;
    const match = /className="[^"]*\btruncate\b[^"]*"[^>]*>\s*([^<]*)/.exec(old);
    expect(match && USER_TEXT.test(match[1].trim()), expression).toBe(true);
  }
});

/** Biểu thức in tên giọng / tên nhân vật (cùng loại với tên giọng của điện thoại, TextCutScanTest). */
const NAME_TEXT = /spokenVoiceName\(|voiceName\(|cleanName\(|\bvoice\.name\b|\bperson\.(?:name|label)\b|\bpicked\.label\b|^\{shown\}$/;
/** Nhãn của nút giọng trên thanh phát rộng (`look` khác "row"): nút công cụ cao cố định, ẩn dưới 75rem; tên đầy đủ ở dòng đang chọn trong hộp giọng ngay khi bấm. */
const NAME_ALLOWED = new Set(["listen/PlayerViews.tsx:{current ? spokenVoiceName(current.name) : \"\"}#bar"]);

it("tên giọng / tên nhân vật không bị cắt \"…\": một dòng thì qua OneLineFit (thu cỡ, không vừa thì xuống dòng)", () => {
  const clipped: string[] = [];
  for (const dir of ["listen", "desktop", "shared", "studio"]) {
    for (const file of sourceFiles(dir)) {
      if (!file.endsWith(".tsx") || file.includes(".test.")) continue;
      const source = readFileSync(`${root}/${dir}/${file}`, "utf8");
      const tag = /className=(?:"[^"]*\b(?:truncate|line-clamp-\d)\b[^"]*"|\{[^}]*\b(?:truncate|line-clamp-\d)\b[^}]*\})[^>]*>\s*([^<]*)/g;
      for (const match of source.matchAll(tag)) {
        const expression = match[1].trim().match(/\{(?:[^{}]|\{[^{}]*\})*\}/g)?.find((part) => NAME_TEXT.test(part.slice(1, -1).trim()) || NAME_TEXT.test(part));
        if (!expression) continue;
        const where = `${dir}/${file}:${expression}`;
        // Nút thanh phát rộng: lớp `max-w-24 truncate @max-[75rem]:hidden` (chỉ dạng nút công cụ, không phải dòng menu).
        if (NAME_ALLOWED.has(`${where}#bar`) && /max-w-24 truncate @max-\[75rem\]:hidden/.test(match[0])) continue;
        clipped.push(`${where} (dòng ${source.slice(0, match.index).split("\n").length})`);
      }
    }
  }
  expect(clipped).toEqual([]);
});

it("máy dò tên giọng bắt được chỗ cắt cũ (đối chứng: dòng giọng trước OneLineFit)", () => {
  const old = `<span className="min-w-0 truncate text-sm font-medium">{shown}</span>`;
  const match = /className="[^"]*\btruncate\b[^"]*"[^>]*>\s*([^<]*)/.exec(old);
  expect(match && NAME_TEXT.test(match[1].trim())).toBe(true);
});

it("ShortName chỉ xuất hiện ở hàng điều khiển phiên điện thoại có chiều cao cố định", () => {
  const callers: string[] = [];
  for (const dir of ["listen", "desktop", "shared", "studio"]) {
    for (const file of sourceFiles(dir)) {
      if (!file.endsWith(".tsx") || file.includes(".test.")) continue;
      const source = readFileSync(`${root}/${dir}/${file}`, "utf8");
      for (const match of source.matchAll(/<ShortName\b[^>]*>/g)) {
        callers.push(`${dir}/${file}`);
        expect(match[0]).toContain('name={phone.name}');
        expect(source.slice(Math.max(0, match.index! - 1200), match.index)).toMatch(/h-14|h-12/);
      }
    }
  }
  expect(callers).toEqual(["desktop/RemotePhone.tsx"]);
});

// Chữ của sách và của người dùng không bao giờ bị cắt (luật cứng của chủ sách): tên sách, tên chương, câu trích, tên hồ sơ / máy / giọng xuống dòng
// (hoặc OneLineFit / FitBox: thu cỡ), không "…" (truncate) và không cắt sau N dòng (line-clamp); ô một dòng cao cố định (thanh phát, dòng tên sách
// màn Đang nghe) qua MarqueeLine: thu cỡ rồi chạy chữ. Máy dò đọc cây JSX thật (testing/clipScan.ts):
// mọi chỗ cắt trong mã giao diện phải nằm trong bảng kiểm kê dưới đây, mỗi chỗ một lý do, ĐÚNG số lần xuất hiện (soát leftfix L4: khoá theo
// "file:biểu thức" thì chỗ cắt thứ hai cùng biểu thức lọt). Chỗ cắt mới chưa phân loại là lỗi.
import { readFileSync } from "node:fs";
import { cwd } from "node:process";
import { expect, it } from "vitest";
import { clipHits, fitFrameHits, scanClips, scanFitFrames, type ClipHit } from "@/testing/clipScan";

const root = `${cwd()}/src`;

/** Chữ sách / chữ người dùng (tên sách, chương, tác giả, câu, file, thư mục, mẫu, dự án, bài nhạc) và tên (máy, điện thoại, hồ sơ, giọng, nhân vật). */
export const BOOK_OR_USER_TEXT = new RegExp([
  /book\.title|bookTitle|\.author\b|chapterTitle|chapter\.(?:sub)?title|chapter\.displayTitle|fullTitle|displayTitle\(|titleOf\(|chapterLabel\(|chapterSubline\(/.source,
  /\bmain\b|found\.title|volume\.title|cue\.(?:chapter|title)|item\.(?:title|label|name|surface)|entry\.surface|playing\??\.title|track\.(?:title|chapterTitle|bookTitle)/.source,
  /template\.name|file\.(?:firstLine|title|name)\b|row\.firstLine|line\.(?:label|text)\b|\bprimaryLabel\b|libraryRoot|\bfolder\b|example\.(?:before|after|text)|unquoted\(|sentence\b/.source,
  /\b(?:target|only|phone|device|computer|found|peer|profile|record|remote|sharer|session|push|sync|active|person|character|project)\??\.(?:name|displayName|label)\b/.source,
  /\bnames\.current\b|\b(?:deviceName|phoneName|profileName|machineName|recordName)\b|remoteName\(|remotePlace\(|computerOf\(|peerBarLine\(|onComputerLine\(/.source,
  /spokenVoiceName\(|voiceName\(|cleanName\(|\bvoice\.name\b|\bpicked\.label\b|\bnarrator\b|^\{(?:name|title|sub|where|shown|author|label|children)\}$/.source,
].join("|"));

/** Kiểm kê mọi chỗ cắt chữ: [file, lớp cắt, biểu thức trong thẻ (nối bằng " "), loại, lý do]. Một dòng = một chỗ; hai chỗ giống hệt thì ghi hai dòng. */
type Kind = "app" | "book-kept" | "name-kept";
const INVENTORY: [string, string, string, Kind, string][] = [
  // --- Chữ sách / tên còn giữ có chủ ý (cùng luật ở ba nền) ---
  ["listen/LibraryScreen.tsx", "line-clamp-2", "{children}", "book-kept", "TileName: tên dưới bìa ô thư viện đúng 2 dòng dành sẵn (DESIGN Lưới bìa; Android LibraryScreen, Qt BookCell cùng luật)"],
  ["music/MusicScreen.tsx", "line-clamp-2", "{title}", "book-kept", "tên bài trong danh sách nhạc tối đa 2 dòng (chủ sách; Android TrackRow, Qt MusicTrackRow)"],
  ["listen/EditBook.tsx", "line-clamp-2", "{cue.silenced ? S.s_im_lang_ban_chon_356a628b : cue.title || S.s_nhac_nen_271fb292}", "book-kept", "tên bài nhạc: tối đa 2 dòng như hàng nhạc (luật tên bài)"],
  ["listen/MyMusic.tsx", "line-clamp-2", "{item.title}", "book-kept", "tên bài nhạc của tôi: tối đa 2 dòng (luật tên bài)"],
  ["listen/PlayerViews.tsx", "line-clamp-2", "{S.s_nhac_nen_198fce26} {label}", "book-kept", "nhãn nhạc nền dưới Đang nghe: tên bài tối đa 2 dòng (luật tên bài), đủ chữ ở title và khi mở"],
  ["listen/PlayerViews.tsx", "truncate", "{current ? spokenVoiceName(current.name) : \"\"}", "name-kept", "nút giọng trên thanh phát rộng: nút công cụ cao cố định, ẩn dưới 75rem; tên đầy đủ ở dòng đang chọn trong hộp giọng"],
  ["listen/PlayerViews.tsx", "truncate", "{playing ? shortPlaylistLabel(label) : \"\"}", "name-kept", "chip nhạc trên thanh phát rộng: nút công cụ cao cố định, ẩn dưới 83rem; tên đủ ở title và trong menu nhạc (break-words)"],
  ["shared/ShortName.tsx", "truncate", "{name}", "name-kept", "tên điện thoại ở hàng điều khiển cố định 48/56 px (RemotePhone), tên đầy đủ ở tooltip; tên máy không phải chữ sách"],
  // --- Chữ app ghép (tiến độ, host:port, nhãn tab/menu, lỗi, số): không phải chữ sách ---
  ["desktop/OtherComputers.tsx", "truncate", "{computer.error ? computer.error : `${routeLine(computer, devices)}${computer.lastSeen ? S.s_thay_0_45bf670a(formatRelative(computer.lastSeen)) : \"\"}`}", "app", "đường nối / lỗi kết nối"],
  ["desktop/OtherComputers.tsx", "truncate", "{found.host} {found.port}", "app", "host:port"],
  ["desktop/Shell.tsx", "truncate", "{children}", "app", "nhãn tab dưới (chữ app cố định)"],
  ["desktop/Shell.tsx", "truncate", "{S.s_co_abook_39ccc742} {info.update.version}", "app", "báo bản cập nhật"],
  ["desktop/Shell.tsx", "truncate", "{job.state === \"running\" ? S.s_import_running_title : S.s_chua_them_duoc_sach_b327e086}", "app", "tiêu đề hàng nhập nền (chữ app cố định); tên file / lỗi ở dòng dưới xuống dòng"],
  ["listen/LibraryScreen.tsx", "truncate", "{[progressText(book, speaks, false), ...(twin ? [twinKind(book), book.addedAt ? S.s_them_0_07ca4c38(formatWhen(book.addedAt)) : \"\"] : [])].filter(Boolean).join(\" · \")}", "app", "dòng tình trạng ô thư viện: tiến độ do app ghép, tên máy nằm ở dấu laptop (Qt BookCell cùng nội dung)"],
  ["listen/LibraryScreen.tsx", "truncate", "{item.items.length} {S.s_tap_269b0b3d}", "app", "số tập"],
  ["listen/menuSlot.tsx", "truncate", "{slot.label}", "app", "nhãn dòng menu (chữ app)"],
  ["listen/MorningRecap.tsx", "truncate", "{marker.hint}", "app", "gợi ý mốc do app ghép"],
  ["listen/MyMusic.tsx", "truncate", "{[item.creator, item.duration ? formatClock(item.duration) : \"\"].filter(Boolean).join(\" · \")}", "app", "người làm · thời lượng một dòng (cùng hàng nhạc ba nền)"],
  ["listen/PlayerViews.tsx", "truncate", "{caption}", "app", "nhãn dòng menu thanh phát (chữ app)"],
  ["listen/PlayerViews.tsx", "truncate", "{S.s_am_luong_5dafca26}", "app", "nhãn âm lượng"],
  ["listen/PlayerViews.tsx", "truncate", "{children}", "app", "MenuRow: dòng việc trong menu … (chữ app)"],
  ["listen/PlayerViews.tsx", "truncate", "{otherBookLine(book)}", "app", "tiến độ sách khác (giờ, số chương)"],
  ["listen/ReaderScreen.tsx", "truncate", "{S.s_nghe_tu_day_6a7ff4ab}", "app", "nút Nghe từ đây"],
  ["music/TrackSheet.tsx", "truncate", "{label}", "app", "nhãn thang cảm xúc / thể loại (từ vựng app)"],
  ["shared/CoverSearch.tsx", "truncate", "{found.provider}", "app", "tên nguồn ảnh"],
  ["shared/ui.tsx", "truncate", "{value}", "app", "Stat: số liệu"],
  ["shared/ui.tsx", "truncate", "{hint}", "app", "Stat: chú thích số"],
  ["studio/ChapterError.tsx", "truncate", "{shown.summary} {S.s_chi_tiet_e762d926}", "app", "tóm tắt lỗi, chi tiết khi bấm"],
  ["studio/NewProjectScreen.tsx", "truncate", "{S.s_phan_a17569d5} {part + 1} {S.s_bat_dau_76545e3c}", "app", "nhãn Phần N"],
  ["studio/PrecastReview.tsx", "truncate", "{counts[value]}", "app", "số đếm"],
  ["studio/ProjectsScreen.tsx", "truncate", "{busy ? S.s_chua_mo_duoc_ffa5657d : S.s_chua_doc_duoc_2213ed66} {book.broken}", "app", "lỗi mở dự án (mô tả lỗi của app)"],
  ["studio/ProjectsScreen.tsx", "line-clamp-2", "{detail}", "app", "tiến độ dự án"],
  ["studio/StudioSetup.tsx", "truncate", "{step.label}", "app", "bước cài đặt"],
  ["studio/StudioSetup.tsx", "truncate", "{step.hint}", "app", "gợi ý bước cài đặt"],
  ["studio/StudioSetup.tsx", "truncate", "{status.detail || current.label}", "app", "tình trạng tải"],
];

const key = (file: string, clip: string, exprs: string) => `${file} | ${clip} | ${exprs}`;
const hitKey = (hit: ClipHit) => key(hit.file, hit.clip, hit.exprs.join(" "));

function counts(keys: string[]) {
  const map = new Map<string, number>();
  for (const k of keys) map.set(k, (map.get(k) ?? 0) + 1);
  return map;
}

it("mọi chỗ cắt chữ trong giao diện đều đã kiểm kê, đúng số lần (không chỗ mới, không chỗ thừa)", () => {
  const found = counts(clipHits().map(hitKey));
  const listed = counts(INVENTORY.map(([file, clip, exprs]) => key(file, clip, exprs)));
  const unlisted = [...found].filter(([k, n]) => (listed.get(k) ?? 0) < n).map(([k, n]) => `${k} (${n} chỗ, kiểm kê ${listed.get(k) ?? 0})`);
  const stale = [...listed].filter(([k, n]) => (found.get(k) ?? 0) < n).map(([k, n]) => `${k} (kiểm kê ${n}, mã ${found.get(k) ?? 0})`);
  expect(unlisted, "chỗ cắt chưa phân loại - chữ sách / người dùng thì bỏ cắt (xuống dòng, OneLineFit, FitBox)").toEqual([]);
  expect(stale, "dòng kiểm kê không còn trong mã - xoá dòng ấy").toEqual([]);
});

it("chỗ cắt ghi là chữ app không chứa chữ sách / chữ người dùng / tên", () => {
  // {children} / {label} của thành phần chung: nhãn tab (Shell), dòng menu (MenuRow), thang cảm xúc (TrackSheet labelOf(emotions)) - nơi gọi truyền chữ app.
  const wrong = INVENTORY.filter(([, , exprs, kind]) => kind === "app" && exprs.split(/(?=\{)/).some((part) => BOOK_OR_USER_TEXT.test(part.trim()) && !/^\{(?:children|label)\}$/.test(part.trim())));
  expect(wrong.map(([file, , exprs]) => `${file}: ${exprs}`)).toEqual([]);
});

it("chữ sách còn giữ chỉ ở dạng đã chốt: tên tối đa 2 dòng, không bao giờ \"…\" một dòng", () => {
  const bad = INVENTORY.filter(([, clip, , kind]) => kind === "book-kept" && clip !== "line-clamp-2");
  expect(bad).toEqual([]);
});

it("máy dò bắt mọi dạng cắt mà máy dò regex cũ sót (đối chứng leftfix mục 4)", () => {
  const cases: [string, string][] = [
    // Thẻ con lồng nhau (RemotePhone cũ).
    [`<div className="truncate text-sm"><span className="font-medium">{phone.chapterTitle}</span><span> · {phone.bookTitle}</span></div>`, "{phone.chapterTitle} {phone.bookTitle}"],
    // Chữ đứng sau icon.
    [`<span className="truncate"><Icon className="size-4" />{book.title}</span>`, "{book.title}"],
    // cn("a", { b: c }, "truncate"): dấu } sớm làm regex cũ dừng.
    [`<span className={cn("a", { "text-fg": on }, "truncate")}>{book.title}</span>`, "{book.title}"],
    // line-clamp-[3].
    [`<p className="line-clamp-[3] text-sm">{line.text}</p>`, "{line.text}"],
    // Lớp trong mẫu chuỗi / điều kiện.
    [`<p className={\`mt-1 \${wide ? "" : "line-clamp-2"}\`}>{example.before}</p>`, "{example.before}"],
    // Tên biến mà danh sách regex cũ không có: tên trên bìa vẽ, kết quả tìm bìa, tập, chương của đoạn nhạc.
    [`<span className="line-clamp-4 font-bold">{main}</span>`, "{main}"],
    [`<div className="mt-2 line-clamp-2 text-xs">{found.title}</div>`, "{found.title}"],
    [`<div className="truncate">{volume.title}</div>`, "{volume.title}"],
    [`<div className="truncate text-xs">{cue.chapter} · {formatClock(cue.start)}</div>`, "{cue.chapter} {formatClock(cue.start)}"],
  ];
  for (const [code, exprs] of cases) {
    const hits = scanClips("listen/Probe.tsx", `export const X = () => (${code});`);
    expect(hits.map((hit) => hit.exprs.join(" ")), code).toEqual([exprs]);
    expect(BOOK_OR_USER_TEXT.test(exprs), exprs).toBe(true);
  }
  expect(scanClips("listen/Probe.tsx", `export const X = () => (<OneLineFit className="font-medium">{book.title}</OneLineFit>);`)).toEqual([]);
});

it("bảng nhận diện chữ sách / tên bắt các biểu thức chữ người dùng đã biết", () => {
  for (const expression of ["target.name", "only.name", "phone.name", "device.name", "computer.name", "found.name", "peer.name", "info.peer.name", "profile.name", "record.name", "active?.name", "push.name", "sync.name", "names.current", "S.s_dang_phat_tren_0_62a989a1(names.current)", "deviceName", "profileName", "spokenVoiceName(x)", "voice.name", "person.label", "{shown}", "chapterLabel(chapter)", "template.name", "line.label || S.s_nguoi_ke_fd36cd15", "preferences?.libraryRoot", "{main}", "cue.chapter", "remotePlace(book)"]) {
    expect(BOOK_OR_USER_TEXT.test(expression), expression).toBe(true);
  }
});

it("ShortName chỉ xuất hiện ở hàng điều khiển phiên điện thoại có chiều cao cố định", () => {
  const callers: string[] = [];
  for (const file of ["desktop/RemotePhone.tsx"]) {
    const source = readFileSync(`${root}/${file}`, "utf8");
    for (const match of source.matchAll(/<ShortName\b[^>]*>/g)) {
      callers.push(file);
      expect(match[0]).toContain("name={phone.name}");
      expect(source.slice(Math.max(0, match.index! - 1200), match.index)).toMatch(/h-14|h-12/);
    }
  }
  const all = clipHits().length;   // nạp cây mã một lần (bộ đệm) - ShortName chỉ được gọi từ RemotePhone:
  expect(all).toBeGreaterThan(0);
  for (const hit of clipHits()) expect(hit.file === "shared/ShortName.tsx" || !hit.before.includes("<ShortName")).toBe(true);
  expect(callers).toEqual(["desktop/RemotePhone.tsx"]);
});

it("CSS không cắt chữ bằng text-overflow: ellipsis, trừ dòng tác giả/thời lượng của hàng nhạc (cùng quyết định với Android TrackRow và Qt MusicTrackRow)", () => {
  const css = readFileSync(`${root}/styles.css`, "utf8");
  const rules = [...css.matchAll(/([^{}]+)\{[^}]*text-overflow:\s*ellipsis[^}]*\}/g)].map((match) => match[1].trim().split("\n").pop()!.trim());
  expect(rules).toEqual([".dot-join-single > span > span:first-child"]);
});

it("OneLineFit không nằm thẳng trong khung cao cố định (xuống dòng thì tràn dọc): dùng min-h-* (leftfix T1)", () => {
  expect(fitFrameHits().map((hit) => `${hit.file}:${hit.line} ${hit.classes}`)).toEqual([]);
  // Đối chứng: nút chọn chương cũ của ScriptTab (h-9) bị bắt, bản min-h-9 thì không.
  const old = `export const X = () => (<button className="-ml-3 inline-flex h-9 min-w-0 flex-1 items-center"><OneLineFit>{label}</OneLineFit></button>);`;
  expect(scanFitFrames("studio/Old.tsx", old)).toHaveLength(1);
  expect(scanFitFrames("studio/New.tsx", old.replace("h-9", "min-h-9"))).toEqual([]);
});

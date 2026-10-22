import { afterEach, expect, it, vi } from "vitest";
import type { ListenBook } from "./model";
import { makeAnchor } from "./readingAnchor";
import { latestReading, readingIndex, readingKey } from "./readingPosition";
import { textScript } from "./textScript";

afterEach(() => vi.unstubAllGlobals());

it("chỗ đọc và câu trích đi theo đoạn sau khi bỏ dòng trước đó", () => {
  const raw = "Chương 1\n\nTrans: Lan\n\nCâu bạn đánh dấu.\n\nCâu kế tiếp.";
  const before = textScript(1, "Chương 1", raw);
  const after = textScript(1, "Chương 1", raw, ["Trans: Lan"]);
  const anchor = makeAnchor(before.segments.map(s => s.text), 2, 0);
  expect(readingIndex(after, { index: 2, anchor })).toBe(1);
  expect(readingIndex(after, { index: 2, quote: before.segments[2].text })).toBe(1);
  expect(readingIndex(after, { index: 999 })).toBe(2);
});

it("câu trích dấu trang rút gọn và gộp khoảng trắng vẫn tìm đúng đoạn", () => {
  const script = textScript(1, "", "Đoạn đầu.\n\nTrời   đã sáng, và sương còn phủ kín cánh đồng làng này.\n\nĐoạn cuối.");
  expect(readingIndex(script, { index: 2, quote: "Trời đã sáng, và sương…" })).toBe(1);
});

it("bản mới hơn thắng nhưng local của hồ sơ khác không được dùng", () => {
  const data = new Map<string,string>();
  vi.stubGlobal("localStorage", { getItem: (key:string) => data.get(key) ?? null });
  const book = { id:"b", chapters:[{id:1},{id:4}], records:[{id:"r-a", active:true}], state:{reading:{chapterId:1,index:10,at:50}} } as ListenBook;
  data.set(readingKey("b","r-a"), JSON.stringify({chapterId:4,index:30,at:100}));
  data.set(readingKey("b","r-b"), JSON.stringify({chapterId:1,index:99,at:200}));
  expect(latestReading(book)).toMatchObject({chapterId:4,index:30});
  book.state.reading!.at = 150;
  expect(latestReading(book)).toMatchObject({chapterId:1,index:10});
  book.records = [{id:"r-c",name:"Bạn",active:true}];
  expect(latestReading(book)).toMatchObject({chapterId:1,index:10});
});

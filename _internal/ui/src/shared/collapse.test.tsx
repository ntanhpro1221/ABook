// @vitest-environment node
// a120: mục gấp / mở (shared/Collapse.tsx) - chủ app: màn nhiều đầu mục thì "foldout chúng lại", và mở / gập phải có chuyển động.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Collapse, Fold, readFold, writeFold } from "./Collapse";
import { MoreInfo, SettingsBlock } from "./SettingsNav";

function memoryStorage() {
  const data = new Map<string, string>();
  return { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => void data.set(key, value), data };
}

describe("Collapse", () => {
  it("gập: vẫn dựng sẵn (mở ra không chờ) nhưng ra khỏi Tab / trình đọc màn hình và mang data-state cho chuyển động CSS", () => {
    const html = renderToStaticMarkup(<Collapse open={false} id="x">Nội dung</Collapse>);
    expect(html).toContain('class="motion-collapse"');
    expect(html).toContain('data-state="closed"');
    expect(html).toContain("inert");
    expect(html).toContain("Nội dung");
  });
  it("mở: không inert", () => {
    const html = renderToStaticMarkup(<Collapse open>Nội dung</Collapse>);
    expect(html).toContain('data-state="open"');
    expect(html).not.toContain("inert");
  });
});

describe("Fold nhớ gấp / mở theo từng khối", () => {
  it("chưa từng chọn thì theo mặc định; đã chọn thì nhớ; không đọc được thì theo mặc định", () => {
    const storage = memoryStorage();
    expect(readFold("devices.storage", false, storage)).toBe(false);
    writeFold("devices.storage", true, storage);
    expect(storage.data.get("abook.fold.devices.storage")).toBe("1");
    expect(readFold("devices.storage", false, storage)).toBe(true);
    writeFold("devices.storage", false, storage);
    expect(readFold("devices.storage", true, storage)).toBe(false);
    const broken = { getItem: () => { throw new Error("blocked"); } };
    expect(readFold("x", true, broken)).toBe(true);
  });

  it("đầu khối là nút bấm có aria-expanded trỏ tới thân, có dòng tóm tắt; mặc định gập", () => {
    const html = renderToStaticMarkup(
      <Fold storageKey="test.fold" title="Dung lượng trên máy" summary="Sách 2 GB · còn trống 10 GB">
        Danh sách
      </Fold>,
    );
    expect(html).toMatch(/<button[^>]*aria-expanded="false"[^>]*aria-controls="[^"]+"/);
    expect(html).toContain("Sách 2 GB · còn trống 10 GB");
    expect(html).toContain('data-state="closed"');
    expect(html).toContain("fold-chevron");
  });
});

describe("Cài đặt: khối gập và Tìm hiểu thêm", () => {
  it("SettingsBlock fold: tiêu đề thành nút gập / mở, nội dung vẫn có trong trang", () => {
    const html = renderToStaticMarkup(
      <SettingsBlock title="Chẩn đoán" fold="advanced.diagnostics">
        <div>Nhật ký</div>
      </SettingsBlock>,
    );
    expect(html).toMatch(/<h2[^>]*><button[^>]*aria-expanded="false"/);
    expect(html).toContain("Nhật ký");
  });
  it("SettingsBlock không fold: như cũ", () => {
    const html = renderToStaticMarkup(
      <SettingsBlock title="Thư viện">
        <div>x</div>
      </SettingsBlock>,
    );
    expect(html).not.toContain("aria-expanded");
  });
  it("Tìm hiểu thêm: phần giải thích nằm trong Collapse (mở / gập có chuyển động), không bật tắt", () => {
    const html = renderToStaticMarkup(<MoreInfo>Giải thích dài</MoreInfo>);
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain("motion-collapse");
    expect(html).toContain("Giải thích dài");
  });
});

import type { ReactNode } from "react";
import { cn } from "@/shared/cn";

/** Các mẩu nối bằng dấu "·", chỉ xuống dòng giữa hai mẩu, và dấu của mẩu đứng đầu một dòng không hiện: không "Giọng Ngọc Lan ·" treo cuối
 * dòng, không "· 4 giờ 40 phút" đứng đầu dòng (audit140 C7). Dấu là lớp giả trước mỗi mẩu; hàng lùi trái đúng bề rộng một dấu và khung cắt phần
 * lùi ấy, nên dấu của mẩu mở đầu dòng nằm ngoài khung (styles.css `.dot-join`). Mẩu dài vẫn tự xuống dòng bên trong. */
export function DotJoin({ parts, className }: { parts: ReactNode[]; className?: string }) {
  const shown = parts.filter((part) => part !== false && part !== null && part !== undefined && part !== "");
  return (
    <span className={cn("dot-join", className)}>
      <span>{shown.map((part, index) => <span key={index}>{part}</span>)}</span>
    </span>
  );
}

// Khoảng trắng thường ngay trước hay ngay sau một dấu "·" có khoảng trắng (thường hay không ngắt) cả hai bên.
const LOOSE_DOT = / (?=·[ \u00a0])|(?<=[ \u00a0]·) /g;
// Chữ của sách ở mặt đọc giữ nguyên từng ký tự; ô nhập không có nút chữ để đổi.
const UNTOUCHED = ".reading-surface, [contenteditable], textarea, script, style";

function keepText(node: Node) {
  const text = node.nodeValue;
  if (!text || text.indexOf("·") < 0 || node.parentElement?.closest(UNTOUCHED)) return;
  const kept = text.replace(LOOSE_DOT, "\u00a0");
  if (kept !== text) node.nodeValue = kept;
}

function keepTree(node: Node) {
  if (node.nodeType === Node.TEXT_NODE) return keepText(node);
  if (node.nodeType !== Node.ELEMENT_NODE && node.nodeType !== Node.DOCUMENT_FRAGMENT_NODE) return;
  const walker = node.ownerDocument!.createTreeWalker(node, NodeFilter.SHOW_TEXT);
  for (let text = walker.nextNode(); text; text = walker.nextNode()) keepText(text);
}

/** Chữ liền có sẵn dấu " · " (tên sách "Thành Phố Sương Mù · Tập 2" ở thanh bên, tiêu đề hộp thoại, thông báo, chuỗi ghép bằng template):
 * khoảng trắng hai bên dấu thành khoảng không ngắt, nên dấu không bao giờ đứng đầu hay cuối dòng (luật LINE BREAK của gallery_inspect).
 * Một chỗ cho cả app như Android vẽ mọi chữ qua TextWrap.kt: mọi nút chữ có dấu, kể cả trong cổng hộp thoại / thông báo, được sửa khi vào
 * trang hay đổi chữ. Cùng độ dài (khoảng trắng đổi lấy khoảng không ngắt), chỉ đổi cách hiện, không đổi chữ của sách. */
export function installKeepDots(doc: Document = document): () => void {
  const observer = new MutationObserver((records) => {
    for (const record of records) {
      if (record.type === "characterData") keepText(record.target);
      else record.addedNodes.forEach(keepTree);
    }
  });
  keepTree(doc.body);
  observer.observe(doc.body, { subtree: true, childList: true, characterData: true });
  return () => observer.disconnect();
}

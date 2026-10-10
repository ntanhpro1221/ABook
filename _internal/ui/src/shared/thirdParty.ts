// Danh sách thành phần bên thứ ba cho mục "Giới thiệu" (máy tính và điện thoại): đọc thẳng docs/THIRD_PARTY.md lúc build - Vite gói
// file thành một phần tải riêng, chỉ tải khi người dùng mở danh sách; thiếu file thì build hỏng chứ không ra app thiếu danh sách.

export interface ThirdPartySection {
  title: string;
  /** Mỗi mục là một gạch đầu dòng hay một đoạn văn (dòng tiếp nối đã nối vào). */
  items: { text: string; bullet: boolean }[];
}

/** Mục dành cho người bảo trì (cách phát hành, đường trong mã nguồn): nằm trong file docs để người phát hành đọc, app không hiện cho người dùng. */
export const MAINTAINER_SECTION = "Ghi chú cho người bảo trì";

export async function loadThirdParty(): Promise<string> {
  return (await import("../../../docs/THIRD_PARTY.md?raw")).default;
}

/** Tách Markdown của THIRD_PARTY.md thành các mục theo tiêu đề `##`; phần mở đầu (dưới tiêu đề `#`) là mục không tên. Mục
 *  "Ghi chú cho người bảo trì" bị bỏ. */
export function parseThirdParty(markdown: string): ThirdPartySection[] {
  const sections: ThirdPartySection[] = [{ title: "", items: [] }];
  let open: { text: string; bullet: boolean } | null = null;
  for (const raw of markdown.replace(/\r/g, "").split("\n")) {
    const line = raw.trim();
    if (!line) {
      open = null;
      continue;
    }
    if (line.startsWith("# ")) continue;
    if (line.startsWith("## ")) {
      sections.push({ title: line.slice(3).trim(), items: [] });
      open = null;
      continue;
    }
    const section = sections[sections.length - 1];
    const bullet = /^[-*] /.test(line);
    if (bullet || !open) {
      open = { text: bullet ? line.slice(2) : line, bullet };
      section.items.push(open);
    } else {
      open.text += ` ${line}`;
    }
  }
  return sections.filter((section) => section.items.length && !section.title.startsWith(MAINTAINER_SECTION));
}

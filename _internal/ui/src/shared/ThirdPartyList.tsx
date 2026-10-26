import { MotionRegion } from "./MotionRegion";
import { useEffect, useState } from "react";
import { loadThirdParty, parseThirdParty, type ThirdPartySection } from "./thirdParty";

/** Chữ đậm `**...**` và mã `` `...` `` của Markdown; còn lại để nguyên. */
function Inline({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\*\*[^*]+\*\*|`[^`]+`)/).map((part, index) =>
        part.startsWith("**") && part.endsWith("**") && part.length > 4 ? (
          <strong key={index} className="font-semibold text-fg">{part.slice(2, -2)}</strong>
        ) : part.startsWith("`") && part.endsWith("`") && part.length > 2 ? (
          <code key={index} className="rounded-control bg-sunken px-1 text-[0.92em]">{part.slice(1, -1)}</code>
        ) : (
          part
        ),
      )}
    </>
  );
}

export function ThirdPartySections({ sections }: { sections: ThirdPartySection[] }) {
  return (
    <div className="space-y-4 text-[0.8125rem] leading-relaxed text-fg-2">
      {sections.map((section, index) => (
        <section key={index}>
          {section.title && <h3 className="mb-1 text-sm font-semibold text-fg"><Inline text={section.title} /></h3>}
          <ul className="space-y-1">
            {section.items.map((item, itemIndex) => (
              <li key={itemIndex} className={item.bullet ? "ml-4 list-disc" : undefined}>
                <Inline text={item.text} />
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

/** Danh sách thành phần bên thứ ba, tải khi mở (hộp ở máy tính, tấm trượt ở điện thoại). */
export function ThirdPartyList() {
  const [sections, setSections] = useState<ThirdPartySection[] | null>(null);
  useEffect(() => {
    let alive = true;
    void loadThirdParty()
      .then((text) => alive && setSections(parseThirdParty(text)))
      .catch(() => alive && setSections([]));
    return () => {
      alive = false;
    };
  }, []);
  // "Đang mở danh sách…" -> danh sách / lỗi: mờ qua theo pha trong hộp đang mở, không đổi cứng.
  return (
    <MotionRegion motionKey={sections === null ? "loading" : sections.length ? "list" : "error"}>
      {sections === null ? <p className="py-4 text-sm text-fg-2">Đang mở danh sách…</p> : !sections.length ? <p className="py-4 text-sm text-fg-2">Chưa mở được danh sách.</p> : <ThirdPartySections sections={sections} />}
    </MotionRegion>
  );
}

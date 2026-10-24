import { useLayoutEffect, useRef } from "react";

let context: CanvasRenderingContext2D | null | undefined;

/** Cùng 6 px giữa mực cuối tên và glyph mở câu, kể cả tên kết bằng ư hay ê và câu mở bằng dấu ngoặc. */
export function SpeakerLabel({ speaker, sentence }: { speaker: string; sentence: string }) {
  const label = useRef<HTMLSpanElement>(null);
  useLayoutEffect(() => {
    const element = label.current;
    if (!element) return;
    const measure = () => {
      context ??= document.createElement("canvas").getContext("2d");
      if (!context) return;
      const labelStyle = getComputedStyle(element);
      const textStyle = getComputedStyle(element.nextElementSibling ?? element.parentElement!);
      const font = (style: CSSStyleDeclaration) => `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
      context.font = font(labelStyle);
      const name = context.measureText(speaker);
      const endBearing = name.width - name.actualBoundingBoxRight;
      context.font = font(textStyle);
      const first = context.measureText([...sentence.trimStart()][0] ?? "");
      element.style.marginRight = `${Math.max(0, 6 - endBearing + first.actualBoundingBoxLeft)}px`;
    };
    measure();
    let active = true;
    void document.fonts?.ready.then(() => { if (active) measure(); });
    document.fonts?.addEventListener("loadingdone", measure);
    window.addEventListener("resize", measure);
    return () => { active = false; document.fonts?.removeEventListener("loadingdone", measure); window.removeEventListener("resize", measure); };
  }, [speaker, sentence]);
  return <span ref={label} className="mr-[6px] inline-block text-xs font-medium text-fg-2">{speaker}</span>;
}

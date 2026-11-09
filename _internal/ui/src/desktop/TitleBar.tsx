import { S } from "../shared/strings.generated";
import { useEffect, useState, type ReactNode } from "react";
import { chromeStateEvent, windowChrome, type CaptionState } from "./windowChrome";
import "./titlebar.css";

// Identical paths to desktop_qt/qml/CaptionGlyph.qml. Both maximize glyphs stay mounted for the 120ms crossfade.
const paths = {
  minimize: "M0 5.5 H10",
  maximize: "M0.5 0.5 H9.5 V9.5 H0.5 Z",
  restore: "M2.5 2.5 V0.5 H9.5 V7.5 H7.5 M0.5 2.5 H7.5 V9.5 H0.5 Z",
  close: "M0 0 L10 10 M10 0 L0 10",
};

function Glyph({ kind, shown = true }: { kind: keyof typeof paths; shown?: boolean }) {
  return <svg className="caption-glyph" data-shown={shown} data-glyph={kind} width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="butt" strokeLinejoin="miter"><path d={paths[kind]} /></svg>;
}

export function TitleBar({ toggle }: { toggle?: ReactNode }) {
  const chrome = windowChrome();
  const [state, setState] = useState<CaptionState>(() => chrome?.state ?? { maximized: false, focused: true, snapHovered: false, snapPressed: false });
  useEffect(() => {
    if (!chrome) return;
    const update = () => setState({ ...chrome.state });
    update();
    window.addEventListener(chromeStateEvent, update);
    return () => window.removeEventListener(chromeStateEvent, update);
  }, [chrome]);
  if (!chrome) return null;
  return (
    <header className="desktop-titlebar" data-focused={state.focused} aria-label={S.s_dieu_khien_cua_so_4e08e039}>
      <div className="titlebar-toggle">{toggle}</div>
      <div className="titlebar-drag" data-tauri-drag-region="" />
      <div className="caption-buttons">
        <button type="button" className="caption-button" aria-label={S.s_thu_nho_d7896922} onClick={() => chrome.action("minimize")}><Glyph kind="minimize" /></button>
        <button type="button" className="caption-button" data-caption-maximize data-hovered={state.snapHovered} data-pressed={state.snapPressed} aria-label={state.maximized ? S.s_khoi_phuc_c652d9c0 : S.s_phong_to_65b20d37} onClick={() => chrome.action("toggleMaximize")}>
          <Glyph kind="maximize" shown={!state.maximized} /><Glyph kind="restore" shown={state.maximized} />
        </button>
        <button type="button" className="caption-button caption-close" aria-label={S.s_dong_5d54c2a1} onClick={() => chrome.action("close")}><Glyph kind="close" /></button>
      </div>
    </header>
  );
}

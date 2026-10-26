export interface CaptionState {
  maximized: boolean;
  focused: boolean;
  snapHovered: boolean;
  snapPressed: boolean;
}

export interface WindowChrome {
  state: CaptionState;
  action: (action: "minimize" | "toggleMaximize" | "close" | "drag" | "systemMenu") => void;
}

declare global {
  interface Window {
    __ABOOK_CHROME__?: WindowChrome;
    __ABOOK_BOOT_THEME__?: "light" | "dark";
  }
}

export const chromeStateEvent = "abook-window-state";

/** Only the desktop shell installs this bridge; browsers and remote Studio keep their own window chrome. */
export function windowChrome(): WindowChrome | undefined {
  return typeof window === "undefined" ? undefined : window.__ABOOK_CHROME__;
}

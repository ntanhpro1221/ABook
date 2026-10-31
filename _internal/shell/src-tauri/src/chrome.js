// Installed in the top-level webview, including the packaged loading page. No file, book or shell IPC.
(() => {
  if (window !== window.top) return;
  const choice = __BOOT_THEME__;
  const media = matchMedia('(prefers-color-scheme: dark)');
  const theme = choice === 'dark' || (choice !== 'light' && media.matches) ? 'dark' : 'light';
  window.__ABOOK_BOOT_THEME__ = theme;
  const state = { maximized: false, focused: true, snapHovered: false, snapPressed: false };
  const publish = patch => {
    if (Object.keys(patch).every(key => state[key] === patch[key])) return;
    Object.assign(state, patch);
    window.dispatchEvent(new Event('abook-window-state'));
    const fallback = document.querySelector('[data-loading-titlebar]');
    if (fallback) {
      fallback.dataset.focused = String(state.focused);
      const maximize = fallback.querySelector('[data-caption-maximize]');
      maximize.dataset.hovered = String(state.snapHovered);
      maximize.dataset.pressed = String(state.snapPressed);
      maximize.setAttribute('aria-label', state.maximized ? 'Khôi phục' : 'Phóng to');
      maximize.querySelectorAll('[data-glyph]').forEach(glyph => { glyph.dataset.shown = String((glyph.dataset.glyph === 'restore') === state.maximized); });
    }
  };
  window.__abookNativeState = publish;
  const invoke = (action, payload = null) => window.__TAURI_INTERNALS__.invoke('window_action', { action, payload })
    .then(value => { publish(value); return value; }).catch(error => console.error('Điều khiển cửa sổ:', error));
  window.__ABOOK_CHROME__ = { state, action: action => { void invoke(action); } };
  const setInitialTheme = () => {
    if (!document.documentElement) return false;
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.nativeChrome = '';
    const style = document.createElement('style');
    style.textContent = ':root{--bg:#f5f3ef;--text:#1a1814;--fg-3:#8a8478;--focus:#a0600c;background:var(--bg);color:var(--text)}[data-theme="dark"]{--bg:#121110;--text:#ece8e1;--fg-3:#7a746a;--focus:#e9a945}' + __CHROME_CSS__;
    document.documentElement.append(style);
    return true;
  };
  if (!setInitialTheme()) {
    const root = new MutationObserver(() => { if (setInitialTheme()) root.disconnect(); });
    root.observe(document, { childList: true });
  }
  const syncBounds = () => {
    const element = document.querySelector('.desktop-titlebar:not([data-loading-titlebar]) [data-caption-maximize]') ?? document.querySelector('[data-loading-titlebar] [data-caption-maximize]');
    const rect = element?.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    void invoke('bounds', rect ? { x: rect.x * ratio, y: rect.y * ratio, width: rect.width * ratio, height: rect.height * ratio } : null);
  };
  document.addEventListener('DOMContentLoaded', () => {
    const fallback = document.createElement('header');
    fallback.className = 'desktop-titlebar';
    fallback.dataset.loadingTitlebar = '';
    fallback.setAttribute('aria-label', 'Điều khiển cửa sổ');
    const glyph = (kind, path) => `<svg class="caption-glyph" data-glyph="${kind}" data-shown="${kind !== 'restore'}" width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="butt" stroke-linejoin="miter"><path d="${path}"/></svg>`;
    fallback.innerHTML = '<div class="titlebar-drag" data-tauri-drag-region></div><div class="caption-buttons">' +
      '<button type="button" class="caption-button" aria-label="Thu nhỏ" data-window-action="minimize">' + glyph('minimize', 'M0 5.5 H10') + '</button>' +
      '<button type="button" class="caption-button" aria-label="Phóng to" data-caption-maximize data-window-action="toggleMaximize">' + glyph('maximize', 'M0.5 0.5 H9.5 V9.5 H0.5 Z') + glyph('restore', 'M2.5 2.5 V0.5 H9.5 V7.5 H7.5 M0.5 2.5 H7.5 V9.5 H0.5 Z') + '</button>' +
      '<button type="button" class="caption-button caption-close" aria-label="Đóng" data-window-action="close">' + glyph('close', 'M0 0 L10 10 M10 0 L0 10') + '</button></div>';
    document.body.append(fallback);
    fallback.addEventListener('click', event => {
      const action = event.target.closest('[data-window-action]')?.dataset.windowAction;
      if (action) void invoke(action);
    });
    let queued = false;
    const queueBounds = () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => { queued = false; syncBounds(); });
    };
    const observer = new MutationObserver(records => {
      // Theme uses the page's own View Transition. The strip adds no separate animation.
      if (records.some(record => record.target === document.documentElement && record.attributeName === 'data-theme')) {
        void invoke('theme', { theme: document.documentElement.dataset.theme });
      }
      if (records.some(record => record.type === 'childList')) {
        fallback.hidden = Boolean(document.querySelector('.desktop-titlebar:not([data-loading-titlebar])'));
        queueBounds();
      }
    });
    observer.observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-theme'] });
    new ResizeObserver(queueBounds).observe(document.documentElement);
    window.addEventListener('resize', queueBounds);
    window.visualViewport?.addEventListener('resize', queueBounds);
    document.addEventListener('contextmenu', event => {
      if (event.target instanceof Element && event.target.hasAttribute('data-tauri-drag-region')) {
        event.preventDefault(); void invoke('systemMenu');
      }
    });
    document.addEventListener('keydown', event => {
      if (event.altKey && event.code === 'Space') { event.preventDefault(); void invoke('systemMenu'); }
    });
    syncBounds();
    void invoke('ready', { theme: document.documentElement.dataset.theme ?? theme });
  }, { once: true });
  // Resize/maximize, keyboard shortcuts, Snap and OS actions all update the same state (including while a flyout owns the mouse).
  window.addEventListener('abook-native-resize', () => { syncBounds(); void invoke('state'); });
  window.addEventListener('focus', () => { void invoke('state'); });
  window.addEventListener('blur', () => { void invoke('state'); });
})();

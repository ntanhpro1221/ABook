//! Narrow window-only IPC. The host keeps all book/file operations; no general Tauri API is granted to it.
use serde_json::{json, Value};
use std::{path::PathBuf, sync::Mutex};
use tauri::{Manager, State, Url, WebviewWindow};

#[cfg(windows)]
#[path = "chrome_windows.rs"]
mod native;

#[derive(Default)]
pub struct HostOrigin(pub Mutex<Option<String>>);

pub fn boot_theme() -> String {
    let path = std::env::var_os("ABOOK_PREFERENCES").map(PathBuf::from).or_else(|| {
        std::env::var_os("LOCALAPPDATA").map(|base| PathBuf::from(base).join("ABook/preferences.json"))
    }).or_else(|| std::env::var_os("HOME").map(|base| PathBuf::from(base).join(".abook/preferences.json")));
    let theme = path.and_then(|path| std::fs::read(path).ok())
        .and_then(|bytes| serde_json::from_slice::<Value>(&bytes).ok())
        .and_then(|prefs| prefs.get("theme").and_then(Value::as_str).map(str::to_owned));
    match theme.as_deref() { Some("light") => "light", Some("dark") => "dark", _ => "system" }.into()
}

pub fn allow_host(app: &tauri::AppHandle, url: &Url) -> Result<(), String> {
    if url.scheme() != "http" || url.host_str() != Some("127.0.0.1") {
        return Err("Host của ABook phải chạy trên loopback".into());
    }
    let origin = url.origin().ascii_serialization();
    app.add_capability(json!({
        "identifier": "window-chrome-host",
        "local": false,
        "remote": { "urls": [format!("{origin}/*")] },
        "windows": ["main"],
        "permissions": ["allow-window-action", "core:window:allow-start-dragging", "core:window:allow-internal-toggle-maximize"]
    }).to_string()).map_err(|e| e.to_string())?;
    *app.state::<HostOrigin>().0.lock().unwrap() = Some(origin);
    Ok(())
}

#[tauri::command]
pub fn window_action(window: WebviewWindow, state: State<'_, HostOrigin>, action: String, payload: Option<Value>) -> Result<Value, String> {
    let url = window.url().map_err(|e| e.to_string())?;
    let local = url.scheme() == "tauri" || (url.scheme() == "http" && url.host_str() == Some("tauri.localhost"));
    let trusted = state.0.lock().unwrap().as_deref() == Some(&url.origin().ascii_serialization());
    if window.label() != "main" || !(local || trusted) { return Err("Trang không có quyền điều khiển cửa sổ".into()); }
    let payload = payload.unwrap_or(Value::Null);
    let result = match action.as_str() {
        "minimize" => window.minimize(),
        "toggleMaximize" => if window.is_maximized().unwrap_or(false) { window.unmaximize() } else { window.maximize() },
        "close" => window.close(),
        "drag" => window.start_dragging(),
        "theme" | "ready" => {
            let dark = payload.get("theme").and_then(Value::as_str) == Some("dark");
            let color = if dark { tauri::window::Color(18, 17, 16, 255) } else { tauri::window::Color(245, 243, 239, 255) };
            window.set_background_color(Some(color)).map_err(|e| e.to_string())?;
            if action == "ready" && !window.is_visible().unwrap_or(false) {
                window.show().map_err(|e| e.to_string())?;
                window.set_focus()
            } else { Ok(()) }
        }
        "bounds" => {
            #[cfg(windows)]
            native::bounds(&window, &payload)?;
            Ok(())
        }
        "systemMenu" => {
            #[cfg(windows)]
            native::system_menu(&window)?;
            Ok(())
        }
        "state" => Ok(()),
        _ => return Err("Lệnh cửa sổ không hợp lệ".into()),
    };
    result.map_err(|e| e.to_string())?;
    Ok(json!({ "maximized": window.is_maximized().unwrap_or(false), "focused": window.is_focused().unwrap_or(true) }))
}

pub fn install(window: &WebviewWindow) -> Result<(), String> {
    #[cfg(windows)]
    native::install(window)?;
    Ok(())
}

pub fn script(theme: &str) -> String {
    include_str!("chrome.js").replace("__BOOT_THEME__", &json!(theme).to_string())
        .replace("__CHROME_CSS__", &json!(include_str!("../../../ui/src/desktop/titlebar.css")).to_string())
}

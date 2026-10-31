//! WebView2 consumes hit tests before its parent. A transparent STATIC sibling above the maximize button
//! answers HTMAXBUTTON; DefSubclassProc handles native Snap hover, while Rust forwards click/system commands.
//! No rendering or layout library: Tauri/Tao retain frame resizing, DWM shadow and maximized work-area handling.
use serde_json::{json, Value};
use std::{mem::size_of, ptr::{null, null_mut}};
use tauri::WebviewWindow;
use windows_sys::Win32::{
    Foundation::{HWND, LPARAM, LRESULT, POINT, RECT, WPARAM},
    Graphics::Dwm::{DwmSetWindowAttribute, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND},
    UI::{
        HiDpi::GetDpiForWindow,
        Input::KeyboardAndMouse::{TrackMouseEvent, TRACKMOUSEEVENT, TME_LEAVE, TME_NONCLIENT},
        Shell::{DefSubclassProc, RemoveWindowSubclass, SetWindowSubclass},
        WindowsAndMessaging::*,
    },
};

const SUBCLASS: usize = 0xab001;
const LATCH_TIMER: usize = 0xab002;
const CHILD_PROP: &[u16] = &[65, 66, 111, 111, 107, 77, 97, 120, 0];

struct Chrome {
    window: WebviewWindow,
    parent: HWND,
    child: HWND,
    hovered: bool,
    pressed: bool,
}

impl Chrome {
    unsafe fn publish(&mut self, hovered: bool, pressed: bool) {
        if self.hovered == hovered && self.pressed == pressed { return; }
        self.hovered = hovered;
        self.pressed = pressed;
        let _ = self.window.eval(format!("window.__abookNativeState?.({})", json!({ "snapHovered": hovered, "snapPressed": pressed })));
    }

    unsafe fn cursor_inside(&self) -> bool {
        let mut point = POINT::default();
        let mut rect = RECT::default();
        GetCursorPos(&mut point) != 0 && GetWindowRect(self.child, &mut rect) != 0
            && point.x >= rect.left && point.x < rect.right && point.y >= rect.top && point.y < rect.bottom
    }
}

pub fn install(window: &WebviewWindow) -> Result<(), String> {
    let parent = window.hwnd().map_err(|e| e.to_string())?.0 as HWND;
    unsafe {
        let corner = DWMWCP_ROUND;
        // Unsupported on Windows 10: DWM safely ignores the preference.
        DwmSetWindowAttribute(parent, DWMWA_WINDOW_CORNER_PREFERENCE as u32, &corner as *const _ as _, size_of::<i32>() as u32);
        let class: Vec<u16> = "STATIC\0".encode_utf16().collect();
        let child = CreateWindowExW(0, class.as_ptr(), null(), WS_CHILD | WS_VISIBLE, 0, 0, 0, 0, parent, null_mut(), null_mut(), null());
        if child.is_null() { return Err(std::io::Error::last_os_error().to_string()); }
        let state = Box::into_raw(Box::new(Chrome { window: window.clone(), parent, child, hovered: false, pressed: false }));
        SetPropW(parent, CHILD_PROP.as_ptr(), child);
        if SetWindowSubclass(child, Some(child_proc), SUBCLASS, state as usize) == 0 {
            DestroyWindow(child); drop(Box::from_raw(state)); return Err("Không gắn được vùng Snap".into());
        }
        if SetWindowSubclass(parent, Some(parent_proc), SUBCLASS, child as usize) == 0 {
            DestroyWindow(child); return Err("Không theo dõi được kích thước cửa sổ".into());
        }
    }
    Ok(())
}

pub fn bounds(window: &WebviewWindow, value: &Value) -> Result<(), String> {
    let parent = window.hwnd().map_err(|e| e.to_string())?.0 as isize;
    let rect: Vec<i32> = ["x", "y", "width", "height"].iter().map(|key| value.get(key).and_then(Value::as_f64).unwrap_or(0.0).clamp(0.0, 100000.0).round() as i32).collect();
    window.run_on_main_thread(move || unsafe {
        let child = GetPropW(parent as HWND, CHILD_PROP.as_ptr());
        if !child.is_null() { SetWindowPos(child, HWND_TOP, rect[0], rect[1], rect[2], rect[3], SWP_NOACTIVATE); }
    }).map_err(|e| e.to_string())
}

pub fn system_menu(window: &WebviewWindow) -> Result<(), String> {
    let parent = window.hwnd().map_err(|e| e.to_string())?.0 as isize;
    window.run_on_main_thread(move || unsafe {
        // Native keyboard system menu includes Move, Size, Minimize, Maximize/Restore and Close, at the correct DPI.
        SendMessageW(parent as HWND, WM_SYSCOMMAND, SC_KEYMENU as usize, ' ' as isize);
    }).map_err(|e| e.to_string())
}

unsafe extern "system" fn parent_proc(hwnd: HWND, msg: u32, wp: WPARAM, lp: LPARAM, id: usize, child: usize) -> LRESULT {
    if msg == WM_NCDESTROY {
        RemovePropW(hwnd, CHILD_PROP.as_ptr());
        RemoveWindowSubclass(hwnd, Some(parent_proc), id);
    }
    let result = DefSubclassProc(hwnd, msg, wp, lp);
    if msg == WM_SIZE || msg == WM_DPICHANGED {
        // Keep the native hit target attached during a resize; the DOM supplies exact bounds again after layout/zoom.
        let mut rect = RECT::default();
        if GetClientRect(hwnd, &mut rect) != 0 {
            let scale = GetDpiForWindow(hwnd) as f64 / 96.0;
            let width = (46.0 * scale).round() as i32;
            SetWindowPos(child as HWND, HWND_TOP, rect.right - 2 * width, 0, width, (40.0 * scale).round() as i32, SWP_NOACTIVATE);
        }
    }
    result
}

unsafe extern "system" fn child_proc(hwnd: HWND, msg: u32, wp: WPARAM, lp: LPARAM, id: usize, data: usize) -> LRESULT {
    let state = &mut *(data as *mut Chrome);
    match msg {
        WM_NCDESTROY => {
            KillTimer(hwnd, LATCH_TIMER);
            RemoveWindowSubclass(hwnd, Some(child_proc), id);
            drop(Box::from_raw(data as *mut Chrome));
            return DefSubclassProc(hwnd, msg, wp, lp);
        }
        WM_NCHITTEST => {
            // The overlay also covers the top resize border. Let Tao's border window receive those pixels.
            let hit = SendMessageW(state.parent, WM_NCHITTEST, wp, lp);
            if (HTLEFT as LRESULT..=HTBOTTOMRIGHT as LRESULT).contains(&hit) {
                return HTTRANSPARENT as LRESULT;
            }
            state.publish(true, state.pressed);
            let mut tracking = TRACKMOUSEEVENT { cbSize: size_of::<TRACKMOUSEEVENT>() as u32, dwFlags: TME_LEAVE | TME_NONCLIENT, hwndTrack: hwnd, dwHoverTime: 0 };
            TrackMouseEvent(&mut tracking);
            SetTimer(hwnd, LATCH_TIMER, 80, None);
            return HTMAXBUTTON as LRESULT;
        }
        WM_TIMER if wp == LATCH_TIMER => {
            // Windows' Snap flyout can send LEAVE even though the pointer remains on the maximize glyph.
            if !state.cursor_inside() { state.publish(false, false); KillTimer(hwnd, LATCH_TIMER); }
            return 0;
        }
        WM_NCMOUSELEAVE => {
            if !state.cursor_inside() { state.publish(false, false); KillTimer(hwnd, LATCH_TIMER); }
        }
        WM_NCLBUTTONDOWN if wp == HTMAXBUTTON as usize => { state.publish(true, true); return 0; }
        WM_NCLBUTTONUP if wp == HTMAXBUTTON as usize => {
            let clicked = state.pressed && state.cursor_inside();
            state.publish(state.cursor_inside(), false);
            if clicked { PostMessageW(state.parent, WM_SYSCOMMAND, if IsZoomed(state.parent) != 0 { SC_RESTORE } else { SC_MAXIMIZE } as usize, 0); }
            return 0;
        }
        WM_SETCURSOR => { SetCursor(LoadCursorW(null_mut(), IDC_ARROW)); return 1; }
        _ => {}
    }
    DefSubclassProc(hwnd, msg, wp, lp)
}

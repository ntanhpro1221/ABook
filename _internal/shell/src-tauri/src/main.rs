//! Vỏ Tauri 2 của app Windows ABook (docs/PACKAGING.md).
//!
//! Vỏ chỉ làm những việc một trang web không tự làm được; mọi thứ khác là server giao diện Python
//! (`abook.webui.host`) - đúng server của cửa sổ Qt. Vỏ chạy host làm tiến trình con, nói chuyện qua stdin/stdout
//! (JSON từng dòng), mở cửa sổ ở địa chỉ host báo, mở hộp thoại Windows khi host nhờ, chuyển file `.abook` của lần mở
//! thứ hai, tìm và cài bản mới có chữ ký khi người dùng bấm, và khi cửa sổ đóng thì dừng host. Trang web không được cấp
//! IPC của Tauri: nó nằm ở `http://127.0.0.1`.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde_json::{json, Value};
use std::fs::{self, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Manager, RunEvent, Url};
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_updater::{Update, UpdaterExt};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;
const BOOK_SUFFIX: &str = ".abook";
/// Cả dự án Studio trong một file (webui/projectfile.py): host mở thành dự án mới.
const PROJECT_SUFFIX: &str = ".abookproj";
/// Host có chừng ấy thời gian để đóng server sau lệnh thoát, rồi bị giết.
const HOST_STOP_GRACE: Duration = Duration::from_secs(5);

static QUITTING: AtomicBool = AtomicBool::new(false);

/// Bản mới đã tìm thấy, chờ người dùng bấm "Cập nhật" (host chuyển lệnh `install_update`).
struct PendingUpdate(Mutex<Option<Update>>);

/// Tiến trình host và đầu ghi của ống tới nó.
struct Host {
    stdin: Mutex<Option<ChildStdin>>,
    child: Mutex<Option<Child>>,
}

impl Host {
    fn send(&self, message: &Value) {
        if let Some(stdin) = self.stdin.lock().unwrap().as_mut() {
            let _ = writeln!(stdin, "{message}");
            let _ = stdin.flush();
        }
    }

    /// Lệnh thoát, rồi đóng ống (host đọc thấy stdin đóng cũng thoát), rồi chờ; quá hạn thì giết.
    fn stop(&self) {
        self.send(&json!({"quit": true}));
        self.stdin.lock().unwrap().take();
        if let Some(mut child) = self.child.lock().unwrap().take() {
            let deadline = Instant::now() + HOST_STOP_GRACE;
            loop {
                match child.try_wait() {
                    Ok(Some(_)) => break,
                    Ok(None) if Instant::now() < deadline => thread::sleep(Duration::from_millis(50)),
                    _ => {
                        let _ = child.kill();
                        let _ = child.wait();
                        break;
                    }
                }
            }
        }
    }
}

/// File `.abook` trong dòng lệnh (bấm đúp file trong Explorer).
fn book_files(args: &[String]) -> Vec<String> {
    args.iter()
        .skip(1)
        .filter(|arg| {
            let lower = arg.to_lowercase();
            (lower.ends_with(BOOK_SUFFIX) || lower.ends_with(PROJECT_SUFFIX)) && Path::new(arg).is_file()
        })
        .cloned()
        .collect()
}

/// `_internal` của mã nguồn - bản dev chạy host từ đây.
fn source_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("..").join("..")
}

/// Nhật ký stderr của host, cạnh dữ liệu của app (`%LOCALAPPDATA%\ABook\logs`).
fn host_log() -> Stdio {
    let Some(base) = std::env::var_os("LOCALAPPDATA") else {
        return Stdio::null();
    };
    let folder = Path::new(&base).join("ABook").join("logs");
    let _ = fs::create_dir_all(&folder);
    match OpenOptions::new()
        .create(true)
        .append(true)
        .open(folder.join("host.log"))
    {
        Ok(file) => Stdio::from(file),
        Err(_) => Stdio::null(),
    }
}

/// Lệnh chạy host. Bản cài: Python nhúng trong thư mục tài nguyên (`scripts/build_windows_app.ps1` dựng; đường dẫn
/// mã nằm trong `python*._pth`, PYTHONPATH bị bỏ qua). Bản dev:
/// python của runtime cạnh mã nguồn, hoặc `ABOOK_HOST_PYTHON` (+ `ABOOK_HOST_APP` = thư mục chứa `abook`).
fn host_command(app: &AppHandle) -> Result<Command, String> {
    let (python, folder, bundled) = if let Some(python) = std::env::var_os("ABOOK_HOST_PYTHON") {
        let folder = std::env::var_os("ABOOK_HOST_APP")
            .map(PathBuf::from)
            .unwrap_or_else(source_root);
        (PathBuf::from(python), folder, false)
    } else if cfg!(debug_assertions) {
        let root = source_root();
        (
            root.join("runtime").join(".venv").join("Scripts").join("pythonw.exe"),
            root,
            false,
        )
    } else {
        // tauri.conf.json `bundle.resources`: thư mục giữ nguyên đường dẫn tương đối, dưới thư mục tài nguyên của app.
        let resources = app
            .path()
            .resource_dir()
            .map_err(|error| error.to_string())?
            .join("resources");
        (
            resources.join("python").join("pythonw.exe"),
            resources.join("app"),
            true,
        )
    };
    if !python.is_file() {
        return Err(format!("Không tìm thấy Python của ABook: {}", python.display()));
    }
    let version = app.package_info().version.to_string();
    let mut command = Command::new(python);
    command
        .args(["-m", "abook.webui.host", "--version", &version])
        .current_dir(folder)
        .env("PYTHONIOENCODING", "utf-8")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(host_log());
    // Bản cài: Studio (thư viện + model làm sách) tải thêm vào %LOCALAPPDATA%\ABook\Studio, và runtime phải nằm ở đó -
    // mặc định `app\runtime` nằm trong thư mục chương trình, bị xoá mỗi lần cập nhật. `ABOOK_STUDIO_ROOT`: thử ở bản dev.
    let studio = std::env::var_os("ABOOK_STUDIO_ROOT").map(PathBuf::from).or_else(|| {
        bundled
            .then(|| std::env::var_os("LOCALAPPDATA").map(|base| Path::new(&base).join("ABook").join("Studio")))
            .flatten()
    });
    if let Some(studio) = studio {
        command
            .arg("--studio")
            .arg(&studio)
            .env("ABOOK_RUNTIME", studio.join("runtime"));
    }
    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);
    Ok(command)
}

/// Thay nội dung trang đang hiện bằng một thông báo lỗi đọc được (trang chờ, hay trang của host vừa chết).
fn show_failure(app: &AppHandle, message: &str) {
    let script = format!(
        "document.body.innerHTML='';document.body.style.cssText='margin:0;height:100vh;display:grid;place-items:center;\
         background:#0e1115;color:#c9d1d9;font:15px Segoe UI,sans-serif';var p=document.createElement('p');\
         p.style.cssText='max-width:36em;line-height:1.5;padding:0 16px';p.textContent={};document.body.appendChild(p);",
        Value::from(message)
    );
    let app = app.clone();
    // Trang chờ có thể chưa nạp xong lúc lỗi xảy ra ngay khi mở: gửi lại vài lần (kịch bản không đổi gì nếu lặp).
    thread::spawn(move || {
        for delay in [0u64, 800, 2500] {
            thread::sleep(Duration::from_millis(delay));
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.eval(&script);
            }
        }
    });
}

/// Phát một CustomEvent vào trang đang hiện (trang của host nghe `abook-opened`, `abook-update`...).
fn dispatch_event(app: &AppHandle, name: &str, detail: &Value) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.eval(format!(
            "window.dispatchEvent(new CustomEvent({}, {{detail: {detail}}}))",
            Value::from(name)
        ));
    }
}

/// Tìm bản mới một lần mỗi lần mở app, gói phải có chữ ký khớp khoá công khai trong tauri.conf.json. Không có mạng hay
/// chưa có bản phát hành nào: im lặng, lần mở sau thử lại. Bản dev không tìm, trừ khi thử bằng `ABOOK_UPDATE_URL`.
fn check_for_update(app: &AppHandle) {
    let endpoint = std::env::var("ABOOK_UPDATE_URL").ok();
    if cfg!(debug_assertions) && endpoint.is_none() {
        return;
    }
    let app = app.clone();
    tauri::async_runtime::spawn(async move {
        let mut builder = app.updater_builder();
        if let Some(url) = endpoint.and_then(|url| url.parse::<Url>().ok()) {
            let Ok(with_endpoint) = builder.endpoints(vec![url]) else {
                return;
            };
            builder = with_endpoint;
        }
        let Ok(updater) = builder.build() else { return };
        if let Ok(Some(update)) = updater.check().await {
            let notes = update.body.clone().unwrap_or_default();
            let message = json!({"update": {"version": update.version, "notes": notes}});
            *app.state::<PendingUpdate>().0.lock().unwrap() = Some(update);
            app.state::<Host>().send(&message);
        }
    });
}

/// Người dùng bấm "Cập nhật": tải gói (kiểm chữ ký), dừng host để bộ cài ghi đè được Python nhúng, chạy bộ cài. Trên
/// Windows `install` tự thoát app; bộ cài chế độ passive mở lại app khi xong. Tải hỏng: trang được báo, bấm lại được.
fn install_update(app: &AppHandle) {
    let Some(update) = app.state::<PendingUpdate>().0.lock().unwrap().take() else {
        return;
    };
    let app = app.clone();
    thread::spawn(
        move || match tauri::async_runtime::block_on(update.download(|_, _| {}, || {})) {
            Ok(bytes) => {
                QUITTING.store(true, Ordering::SeqCst);
                app.state::<Host>().stop();
                if let Err(error) = update.install(bytes) {
                    show_failure(
                        &app,
                        &format!("Không cài được bản mới ({error}). Đóng rồi mở lại ABook."),
                    );
                }
            }
            Err(error) => {
                *app.state::<PendingUpdate>().0.lock().unwrap() = Some(update);
                dispatch_event(&app, "abook-update-failed", &Value::from(error.to_string()));
            }
        },
    );
}

fn answer_dialog(app: &AppHandle, message: &Value) {
    let title = message.get("title").and_then(Value::as_str).unwrap_or("");
    let start = message.get("start").and_then(Value::as_str).unwrap_or("");
    let mut dialog = app.dialog().file().set_title(title);
    if !start.is_empty() && Path::new(start).is_dir() {
        dialog = dialog.set_directory(start);
    }
    if let Some(window) = app.get_webview_window("main") {
        dialog = dialog.set_parent(&window);
    }
    let path_text = |path: tauri_plugin_dialog::FilePath| path.into_path().ok().map(|path| path.display().to_string());
    let result = match message.get("kind").and_then(Value::as_str) {
        Some("folder") => dialog.blocking_pick_folder().and_then(path_text).map(Value::from),
        Some("files") => {
            // "Nhập nhạc của tôi" xin bộ lọc nhạc; mọi nơi khác chọn chương truyện (TXT) hay file sách (EPUB, DOCX, PDF).
            let dialog = match message.get("filter").and_then(Value::as_str) {
                Some("music") => dialog.add_filter(
                    "Nhạc (mp3, m4a, ogg, opus, flac, wav)",
                    &["mp3", "m4a", "ogg", "opus", "flac", "wav"],
                ),
                _ => dialog.add_filter("Chương truyện (TXT) hay sách (EPUB, DOCX, PDF)", &["txt", "epub", "docx", "pdf"]),
            };
            dialog
                .blocking_pick_files()
                .map(|paths| Value::from(paths.into_iter().filter_map(path_text).collect::<Vec<_>>()))
        }
        Some("book") => dialog
            .add_filter("Sách hay dự án ABook", &["abook", "abookproj"])
            .blocking_pick_file()
            .and_then(path_text)
            .map(Value::from),
        _ => None,
    };
    let reply = json!({"dialog": message.get("dialog").cloned().unwrap_or(Value::Null), "result": result});
    app.state::<Host>().send(&reply);
}

/// Đọc từng dòng host gửi, cho tới khi host thoát.
fn pump(app: AppHandle, stdout: ChildStdout) {
    for line in BufReader::new(stdout).lines() {
        let Ok(line) = line else { break };
        let Ok(message) = serde_json::from_str::<Value>(&line) else {
            continue;
        };
        if let Some(address) = message.get("ready").and_then(Value::as_str) {
            if let (Some(window), Ok(url)) = (app.get_webview_window("main"), address.parse::<Url>()) {
                let _ = window.navigate(url);
            }
        } else if message.get("dialog").is_some() {
            // Hộp thoại chặn tới khi người dùng chọn xong: mỗi cái một luồng, ống vẫn được đọc tiếp.
            let app = app.clone();
            thread::spawn(move || answer_dialog(&app, &message));
        } else if let Some(event) = message.get("event").and_then(Value::as_str) {
            dispatch_event(&app, event, message.get("detail").unwrap_or(&Value::Null));
        } else if message.get("install_update").is_some() {
            install_update(&app);
        }
    }
    if !QUITTING.load(Ordering::SeqCst) {
        show_failure(
            &app,
            "ABook dừng bất ngờ. Đóng cửa sổ rồi mở lại app; nếu vẫn lỗi, xem %LOCALAPPDATA%\\ABook\\logs\\host.log.",
        );
    }
}

fn main() {
    tauri::Builder::default()
        // Phải đăng ký đầu tiên: lần mở thứ hai thoát ngay, đường dẫn .abook của nó về cửa sổ đang chạy.
        .plugin(tauri_plugin_single_instance::init(|app, argv, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.unminimize();
                let _ = window.show();
                let _ = window.set_focus();
            }
            for path in book_files(&argv) {
                app.state::<Host>().send(&json!({"open": path}));
            }
        }))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .setup(|app| {
            let handle = app.handle().clone();
            app.manage(PendingUpdate(Mutex::new(None)));
            match host_command(&handle).and_then(|mut command| command.spawn().map_err(|error| error.to_string())) {
                Ok(mut child) => {
                    let stdout = child.stdout.take().expect("stdout của host là ống");
                    let stdin = child.stdin.take();
                    app.manage(Host {
                        stdin: Mutex::new(stdin),
                        child: Mutex::new(Some(child)),
                    });
                    // Host đọc ống sau khi báo sẵn sàng: đường dẫn gửi sớm nằm chờ trong ống, không mất.
                    let args: Vec<String> = std::env::args().collect();
                    for path in book_files(&args) {
                        app.state::<Host>().send(&json!({"open": path}));
                    }
                    check_for_update(&handle);
                    thread::spawn(move || pump(handle, stdout));
                }
                Err(error) => {
                    app.manage(Host {
                        stdin: Mutex::new(None),
                        child: Mutex::new(None),
                    });
                    show_failure(&handle, &format!("ABook không mở được: {error}"));
                }
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("không dựng được cửa sổ ABook")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                QUITTING.store(true, Ordering::SeqCst);
                app.state::<Host>().stop();
            }
        });
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::File;

    #[test]
    fn only_existing_abook_files_from_the_command_line_are_opened() {
        let folder = std::env::temp_dir().join(format!("abook-shell-test-{}", std::process::id()));
        fs::create_dir_all(&folder).unwrap();
        let book = folder.join("Sách.ABOOK");
        File::create(&book).unwrap();
        let project = folder.join("Dự án.abookproj");
        File::create(&project).unwrap();
        let args = vec![
            "ABook.exe".to_string(),
            book.display().to_string(),
            project.display().to_string(),
            folder.join("khong_co.abook").display().to_string(),
            folder.join("chuong.txt").display().to_string(),
        ];
        assert_eq!(book_files(&args), vec![book.display().to_string(), project.display().to_string()]);
        let _ = fs::remove_dir_all(&folder);
    }
}

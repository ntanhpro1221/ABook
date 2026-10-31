//! Vỏ Tauri 2 của app Windows ABook (docs/PACKAGING.md).
//!
//! Vỏ chỉ làm những việc một trang web không tự làm được; mọi thứ khác là server giao diện Python
//! (`abook.webui.host`) - đúng server của cửa sổ Qt. Vỏ chạy host làm tiến trình con, nói chuyện qua stdin/stdout
//! (JSON từng dòng), mở cửa sổ ở địa chỉ host báo, mở hộp thoại Windows khi host nhờ, chuyển file `.abook` của lần mở
//! thứ hai, tìm và cài bản mới có chữ ký khi người dùng bấm, và khi cửa sổ đóng thì dừng host. Trang web không được cấp
//! IPC tệp của Tauri: nó nằm ở `http://127.0.0.1`; chrome chỉ cấp các thao tác cửa sổ cho đúng origin của host.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde_json::{json, Value};
use std::fs::{self, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::mpsc::{self, Receiver, RecvTimeoutError};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use tauri::{AppHandle, DragDropEvent, Manager, RunEvent, Url, WindowEvent};
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_updater::{Update, UpdaterExt};

mod chrome;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;
const BOOK_SUFFIX: &str = ".abook";
/// Cả dự án Studio trong một file (webui/projectfile.py): host mở thành dự án mới.
const PROJECT_SUFFIX: &str = ".abookproj";
/// Host có chừng ấy thời gian để đóng server sau lệnh thoát, rồi bị giết.
const HOST_STOP_GRACE: Duration = Duration::from_secs(5);

/// Host chưa báo sẵn sàng cũng chưa thoát sau chừng này kể từ lúc chạy thì coi là kẹt: trang chờ hiện lỗi mở app kèm "Thử lại". Đo 31-10: sẵn sàng
/// khoảng 0,9 giây sau khi chạy; 60 giây chừa chỗ cho lần mở đầu lạnh (antivirus quét runtime). Bản Qt: Backend::s_startLimitMs.
const HOST_START_LIMIT: Duration = Duration::from_secs(60);
/// Cùng câu với bản Qt (Backend::start); trang chờ không có Cài đặt nên chỉ đường tới nhật ký bằng đường dẫn, như lời báo "dừng bất ngờ".
const HOST_START_FAILURE: &str =
    "ABook chưa mở được. Bạn thử lại; nếu vẫn lỗi, xem nhật ký: %LOCALAPPDATA%\\ABook\\logs\\host.log.";

static QUITTING: AtomicBool = AtomicBool::new(false);
/// Thế hệ của host đang chạy (tăng mỗi lần chạy / chạy lại): ống và đồng hồ canh của host cũ thấy mình đã cũ thì im lặng.
static HOST_GENERATION: AtomicU64 = AtomicU64::new(0);
/// "Thử lại" đang chạy lại host: bấm thêm lúc ấy không chạy thêm lần nữa.
static RESTARTING: AtomicBool = AtomicBool::new(false);

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

/// Kịch bản thay nội dung trang bằng lời báo lỗi, có nút "Thử lại" khi `retry` (xem [show_failure]).
fn failure_script(message: &str, retry: bool) -> String {
    format!(
        "document.querySelectorAll('body > :not([data-loading-titlebar])').forEach(e=>e.remove());\
         document.body.style.cssText='margin:0;height:100vh;display:grid;place-items:center;\
         background:var(--bg);color:var(--text);font:15px Segoe UI,sans-serif';var p=document.createElement('p');\
         p.style.cssText='max-width:36em;line-height:1.5;padding:40px 16px 12px';p.textContent={message};\
         var box=document.createElement('div');box.style.cssText='display:grid;justify-items:center';box.appendChild(p);\
         if({retry}){{var b=document.createElement('button');b.type='button';b.textContent='Thử lại';\
         b.style.cssText='font:inherit;color:inherit;background:transparent;border:1px solid currentColor;border-radius:8px;padding:8px 22px;cursor:pointer';\
         b.onclick=function(){{b.disabled=true;window.__ABOOK_CHROME__.action('restartHost')}};box.appendChild(b);}}\
         document.body.appendChild(box);",
        message = Value::from(message),
        retry = retry
    )
}

/// Thay nội dung trang đang hiện bằng một thông báo lỗi đọc được (trang chờ, hay trang của host vừa chết). `retry`: kèm nút "Thử lại" chạy lại host
/// (`restart_host`, qua `window_action`); chỉ trang chờ của vỏ gọi được lệnh ấy.
fn show_failure(app: &AppHandle, message: &str, retry: bool) {
    let script = failure_script(message, retry);
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

/// File kéo thả vào cửa sổ: WebView2 giao việc nhận file cho vỏ (trang không nhận được sự kiện `drop` của HTML5), nên vỏ chuyển đường dẫn thật
/// sang trang qua `abook-drag` - `state` là "enter" (đang kéo ngang cửa sổ), "leave" hoặc "drop" (kèm `paths`). Thư viện hiện lớp "Thả để thêm sách".
fn forward_drag_drop(app: &AppHandle, event: &DragDropEvent) {
    let paths = |paths: &[PathBuf]| paths.iter().map(|path| path.display().to_string()).collect::<Vec<_>>();
    match event {
        DragDropEvent::Enter { .. } => dispatch_event(app, "abook-drag", &json!({"state": "enter"})),
        DragDropEvent::Drop { paths: dropped, .. } => dispatch_event(app, "abook-drag", &json!({"state": "drop", "paths": paths(dropped)})),
        DragDropEvent::Leave => dispatch_event(app, "abook-drag", &json!({"state": "leave"})),
        _ => {}
    }
}

/// Hỏi trang phát hành quá chừng này mà không thấy trả lời: coi là không có mạng (nút "Kiểm tra bản mới" trở lại bấm được).
const UPDATE_CHECK_TIMEOUT: Duration = Duration::from_secs(30);
/// Đang tải gói mà chừng này không thêm byte nào: coi là đứt mạng. Gói vài trăm MB nên không đặt hạn cho cả lần tải,
/// chỉ canh chỗ đứng yên.
const UPDATE_STALL: Duration = Duration::from_secs(60);

/// Lời báo cho người dùng khi tìm / tải / cài bản mới hỏng - câu cố định, không lộ chuỗi lỗi của thư viện (chi tiết vào `host.log`).
fn update_failure(error: &tauri_plugin_updater::Error) -> &'static str {
    use tauri_plugin_updater::Error;
    match error {
        Error::Minisign(_) | Error::Base64(_) | Error::SignatureUtf8(_) => {
            "Gói tải về không khớp chữ ký của ABook nên bạn chưa nên cài nó. Bạn thử lại sau ít phút."
        }
        Error::Io(_) | Error::Extract(_) => "Không cài được bản mới. Bạn đóng rồi mở lại ABook, rồi thử lại.",
        _ => UPDATE_NETWORK,
    }
}

const UPDATE_NETWORK: &str =
    "Chưa lấy được bản mới - mạng chập chờn hoặc không tới được trang phát hành. Bạn kiểm tra mạng rồi thử lại.";
const UPDATE_STALLED: &str =
    "Đường tải bản mới đứng yên quá lâu. Bạn kiểm tra mạng rồi bấm Cập nhật lần nữa.";

/// Ghi một dòng vào `%LOCALAPPDATA%\ABook\logs\host.log` (cùng file với stderr của host) cho những lỗi mà trang chỉ nói gọn.
fn log_line(line: &str) {
    let Some(base) = std::env::var_os("LOCALAPPDATA") else {
        return;
    };
    let folder = Path::new(&base).join("ABook").join("logs");
    let _ = fs::create_dir_all(&folder);
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(folder.join("host.log")) {
        let _ = writeln!(file, "[shell] {line}");
    }
}

/// Chờ kết quả của việc chạy nền; bỏ cuộc (None) khi `progress` (mili giây từ `started` ở lần nhích gần nhất) đứng quá `stall`,
/// hay việc nền chết mà không trả gì.
fn wait_unless_stalled<T>(receiver: &Receiver<T>, started: Instant, progress: &AtomicU64, stall: Duration) -> Option<T> {
    loop {
        match receiver.recv_timeout(Duration::from_millis(250)) {
            Ok(value) => return Some(value),
            Err(RecvTimeoutError::Disconnected) => return None,
            Err(RecvTimeoutError::Timeout) => {
                let idle = started.elapsed().saturating_sub(Duration::from_millis(progress.load(Ordering::Relaxed)));
                if idle > stall {
                    return None;
                }
            }
        }
    }
}

/// Tìm bản mới một lần mỗi lần mở app, gói phải có chữ ký khớp khoá công khai trong tauri.conf.json. Không có mạng hay
/// chưa có bản phát hành nào: im lặng, lần mở sau thử lại. Bản dev không tìm, trừ khi thử bằng `ABOOK_UPDATE_URL`.
/// `manual` (người dùng bấm "Kiểm tra bản mới"): kết quả nào cũng báo trang qua `abook-update-checked`
/// (`state` = `found` / `latest` / `failed` kèm `message`), để nút không đứng im.
fn check_for_update(app: &AppHandle, manual: bool) {
    let endpoint = std::env::var("ABOOK_UPDATE_URL").ok();
    let report = {
        let app = app.clone();
        move |detail: Value| {
            if manual {
                dispatch_event(&app, "abook-update-checked", &detail);
            }
        }
    };
    if cfg!(debug_assertions) && endpoint.is_none() {
        report(json!({"state": "latest"}));
        return;
    }
    let app = app.clone();
    tauri::async_runtime::spawn(async move {
        let mut builder = app.updater_builder().timeout(UPDATE_CHECK_TIMEOUT);
        if let Some(url) = endpoint.and_then(|url| url.parse::<Url>().ok()) {
            let Ok(with_endpoint) = builder.endpoints(vec![url]) else {
                return report(json!({"state": "failed", "message": UPDATE_NETWORK}));
            };
            builder = with_endpoint;
        }
        let updater = match builder.build() {
            Ok(updater) => updater,
            Err(error) => {
                log_line(&format!("kiểm bản mới: không dựng được bộ kiểm: {error}"));
                return report(json!({"state": "failed", "message": update_failure(&error)}));
            }
        };
        match updater.check().await {
            Ok(Some(mut update)) => {
                // Hạn của lần kiểm không được dính sang lần tải gói (canh bằng `UPDATE_STALL`).
                update.timeout = None;
                let notes = update.body.clone().unwrap_or_default();
                let message = json!({"update": {"version": update.version, "notes": notes}});
                *app.state::<PendingUpdate>().0.lock().unwrap() = Some(update);
                app.state::<Host>().send(&message);
                report(json!({"state": "found"}));
            }
            Ok(None) => report(json!({"state": "latest"})),
            Err(error) => {
                log_line(&format!("kiểm bản mới hỏng: {error}"));
                report(json!({"state": "failed", "message": update_failure(&error)}));
            }
        }
    });
}

/// Người dùng bấm "Cập nhật": tải gói (kiểm chữ ký), dừng host để bộ cài ghi đè được Python nhúng, chạy bộ cài. Trên
/// Windows `install` tự thoát app; bộ cài chế độ passive mở lại app khi xong. Tải hỏng hay đứng yên quá `UPDATE_STALL`:
/// trang được báo, bấm lại được.
fn install_update(app: &AppHandle) {
    let Some(update) = app.state::<PendingUpdate>().0.lock().unwrap().take() else {
        return;
    };
    let app = app.clone();
    thread::spawn(move || {
        let started = Instant::now();
        let progress = Arc::new(AtomicU64::new(0));
        let (sender, receiver) = mpsc::channel();
        let job = {
            let (update, progress) = (update.clone(), progress.clone());
            tauri::async_runtime::spawn(async move {
                let result = update
                    .download(
                        move |_, _| progress.store(started.elapsed().as_millis() as u64, Ordering::Relaxed),
                        || {},
                    )
                    .await;
                let _ = sender.send(result);
            })
        };
        let fail = |message: &str| {
            *app.state::<PendingUpdate>().0.lock().unwrap() = Some(update.clone());
            dispatch_event(&app, "abook-update-failed", &Value::from(message));
        };
        match wait_unless_stalled(&receiver, started, &progress, UPDATE_STALL) {
            Some(Ok(bytes)) => {
                QUITTING.store(true, Ordering::SeqCst);
                app.state::<Host>().stop();
                if let Err(error) = update.install(bytes) {
                    log_line(&format!("cài bản mới hỏng: {error}"));
                    show_failure(&app, "Không cài được bản mới. Bạn đóng rồi mở lại ABook.", false);
                }
            }
            Some(Err(error)) => {
                log_line(&format!("tải bản mới hỏng: {error}"));
                fail(update_failure(&error));
            }
            None => {
                job.abort();
                log_line("tải bản mới: đứng yên quá lâu, bỏ");
                fail(UPDATE_STALLED);
            }
        }
    });
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

/// Đọc từng dòng host gửi, cho tới khi host thoát. `generation`: host này còn là host hiện tại không; `ready`: báo cho đồng hồ canh khi host nói sẵn sàng
/// (thả khi ống đóng: đồng hồ thấy host đã thoát, tự lời báo "dừng bất ngờ" ở dưới nói thay).
fn pump(app: AppHandle, stdout: ChildStdout, generation: u64, ready: mpsc::Sender<()>) {
    for line in BufReader::new(stdout).lines() {
        let Ok(line) = line else { break };
        if HOST_GENERATION.load(Ordering::SeqCst) != generation {
            return; // đã "Thử lại" sang host khác: host cũ không được đụng tới cửa sổ nữa
        }
        let Ok(message) = serde_json::from_str::<Value>(&line) else {
            continue;
        };
        if let Some(address) = message.get("ready").and_then(Value::as_str) {
            let _ = ready.send(());
            // Báo sẵn sàng muộn (sau lời báo kẹt) vẫn mở app: trang thật thay trang lỗi.
            if let (Some(window), Ok(url)) = (app.get_webview_window("main"), address.parse::<Url>()) {
                match chrome::allow_host(&app, &url) {
                    Ok(()) => { let _ = window.navigate(url); }
                    Err(error) => show_failure(&app, &error, false),
                }
            }
        } else if message.get("dialog").is_some() {
            // Hộp thoại chặn tới khi người dùng chọn xong: mỗi cái một luồng, ống vẫn được đọc tiếp.
            let app = app.clone();
            thread::spawn(move || answer_dialog(&app, &message));
        } else if let Some(event) = message.get("event").and_then(Value::as_str) {
            dispatch_event(&app, event, message.get("detail").unwrap_or(&Value::Null));
        } else if message.get("install_update").is_some() {
            install_update(&app);
        } else if message.get("check_update").is_some() {
            check_for_update(&app, true);
        }
    }
    if !QUITTING.load(Ordering::SeqCst) && HOST_GENERATION.load(Ordering::SeqCst) == generation {
        show_failure(
            &app,
            "ABook dừng bất ngờ. Đóng cửa sổ rồi mở lại app; nếu vẫn lỗi, xem %LOCALAPPDATA%\\ABook\\logs\\host.log.",
            false,
        );
    }
}

/// Host đã đến đâu sau khi chạy: báo sẵn sàng, thoát, hay kẹt quá `limit`.
#[derive(Debug, PartialEq)]
enum StartOutcome {
    Ready,
    Exited,
    Stuck,
}

/// Chờ tín hiệu từ ống của host: gửi = sẵn sàng; đầu gửi bị thả (ống đóng) = host đã thoát; im quá `limit` = kẹt.
fn wait_for_start(signal: &Receiver<()>, limit: Duration) -> StartOutcome {
    match signal.recv_timeout(limit) {
        Ok(()) => StartOutcome::Ready,
        Err(RecvTimeoutError::Disconnected) => StartOutcome::Exited,
        Err(RecvTimeoutError::Timeout) => StartOutcome::Stuck,
    }
}

/// Chạy host, nối ống của nó và bật đồng hồ canh `HOST_START_LIMIT`: kẹt thì trang chờ hiện lỗi mở app kèm "Thử lại" (host vẫn chạy, báo sẵn sàng muộn vẫn mở app).
fn start_host(app: &AppHandle) -> bool {
    let generation = HOST_GENERATION.fetch_add(1, Ordering::SeqCst) + 1;
    match host_command(app).and_then(|mut command| command.spawn().map_err(|error| error.to_string())) {
        Ok(mut child) => {
            let stdout = child.stdout.take().expect("stdout của host là ống");
            let host = app.state::<Host>();
            *host.stdin.lock().unwrap() = child.stdin.take();
            *host.child.lock().unwrap() = Some(child);
            // Host đọc ống sau khi báo sẵn sàng: đường dẫn gửi sớm nằm chờ trong ống, không mất.
            let args: Vec<String> = std::env::args().collect();
            for path in book_files(&args) {
                host.send(&json!({"open": path}));
            }
            let (ready, started) = mpsc::channel();
            let reader = app.clone();
            thread::spawn(move || pump(reader, stdout, generation, ready));
            let watcher = app.clone();
            thread::spawn(move || {
                if wait_for_start(&started, HOST_START_LIMIT) == StartOutcome::Stuck && HOST_GENERATION.load(Ordering::SeqCst) == generation {
                    log_line(&format!("host chưa báo sẵn sàng sau {} giây", HOST_START_LIMIT.as_secs()));
                    show_failure(&watcher, HOST_START_FAILURE, true);
                }
            });
            true
        }
        Err(error) => {
            show_failure(app, &format!("ABook không mở được: {error}"), false);
            false
        }
    }
}

/// "Thử lại" ở trang lỗi mở app: bỏ host đang kẹt (hết hạn dừng thì bị giết), trả trang chờ, chạy host mới.
pub fn restart_host(app: &AppHandle) {
    if RESTARTING.swap(true, Ordering::SeqCst) {
        return;
    }
    let app = app.clone();
    thread::spawn(move || {
        HOST_GENERATION.fetch_add(1, Ordering::SeqCst); // ống và đồng hồ canh của host cũ thôi có tiếng nói ngay từ đây
        app.state::<Host>().stop();
        if let Some(window) = app.get_webview_window("main") {
            let _ = window.eval("location.reload()");
        }
        start_host(&app);
        RESTARTING.store(false, Ordering::SeqCst);
    });
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![chrome::window_action])
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
        // Nhớ kích thước, vị trí, phóng to của cửa sổ qua các lần mở; vị trí chỉ khôi phục khi màn hình cũ còn (rút màn phụ thì
        // cửa sổ không nằm ngoài màn). Hiện / ẩn cửa sổ vẫn do app quyết, không theo lần đóng trước.
        .plugin(
            tauri_plugin_window_state::Builder::default()
                .with_state_flags(tauri_plugin_window_state::StateFlags::all() - tauri_plugin_window_state::StateFlags::VISIBLE)
                .build(),
        )
        .on_window_event(|window, event| {
            if let WindowEvent::DragDrop(drag) = event {
                forward_drag_drop(window.app_handle(), drag);
            }
            if matches!(event, WindowEvent::Resized(_) | WindowEvent::ScaleFactorChanged { .. } | WindowEvent::Focused(_)) {
                if let Some(webview) = window.app_handle().get_webview_window(window.label()) {
                    let _ = webview.eval("window.dispatchEvent(new Event('abook-native-resize'))");
                }
            }
        })
        .setup(|app| {
            let handle = app.handle().clone();
            app.manage(chrome::HostOrigin::default());
            let config = app.config().app.windows.iter().find(|window| window.label == "main").expect("main config");
            let window = tauri::WebviewWindowBuilder::from_config(app, config)?
                .initialization_script(chrome::script(&chrome::boot_theme()))
                .build()?;
            chrome::install(&window).map_err(std::io::Error::other)?;
            app.manage(PendingUpdate(Mutex::new(None)));
            app.manage(Host {
                stdin: Mutex::new(None),
                child: Mutex::new(None),
            });
            if start_host(&handle) {
                check_for_update(&handle, false);
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

    #[test]
    fn a_download_that_stops_moving_is_given_up_not_waited_for_forever() {
        let (_sender, receiver) = mpsc::channel::<u8>();
        let progress = AtomicU64::new(0);
        let started = Instant::now();
        assert_eq!(wait_unless_stalled(&receiver, started, &progress, Duration::from_millis(300)), None);
        assert!(started.elapsed() < Duration::from_secs(5));
    }

    #[test]
    fn a_slow_download_that_keeps_moving_is_not_given_up() {
        let (sender, receiver) = mpsc::channel();
        let progress = Arc::new(AtomicU64::new(0));
        let started = Instant::now();
        let ticker = progress.clone();
        thread::spawn(move || {
            for _ in 0..8 {
                thread::sleep(Duration::from_millis(100));
                ticker.store(started.elapsed().as_millis() as u64, Ordering::Relaxed);
            }
            let _ = sender.send(7u8);
        });
        // Cả lần tải (~800 ms) dài hơn hạn đứng yên (400 ms) nhưng không lúc nào đứng yên quá hạn.
        assert_eq!(wait_unless_stalled(&receiver, started, &progress, Duration::from_millis(400)), Some(7));
    }

    #[test]
    fn a_host_that_says_ready_is_ready_whatever_the_limit() {
        let (sender, receiver) = mpsc::channel();
        sender.send(()).unwrap();
        assert_eq!(wait_for_start(&receiver, Duration::from_secs(60)), StartOutcome::Ready);
    }

    #[test]
    fn a_host_that_exits_before_ready_is_not_waited_for() {
        let (sender, receiver) = mpsc::channel::<()>();
        drop(sender); // ống đóng: pump thoát, đầu gửi bị thả
        let started = Instant::now();
        assert_eq!(wait_for_start(&receiver, Duration::from_secs(60)), StartOutcome::Exited);
        assert!(started.elapsed() < Duration::from_secs(5));
    }

    #[test]
    fn a_host_silent_past_the_limit_is_stuck_and_may_still_become_ready() {
        let (sender, receiver) = mpsc::channel();
        let started = Instant::now();
        assert_eq!(wait_for_start(&receiver, Duration::from_millis(300)), StartOutcome::Stuck);
        assert!(started.elapsed() >= Duration::from_millis(300) && started.elapsed() < Duration::from_secs(5));
        // Báo sẵn sàng muộn: đầu gửi của pump vẫn dùng được (pump mở app theo lời báo ấy, không cần ai nhận).
        assert!(sender.send(()).is_ok());
        assert_eq!(wait_for_start(&receiver, Duration::from_secs(60)), StartOutcome::Ready);
        drop(receiver);
        assert!(sender.send(()).is_err()); // đồng hồ canh đã bỏ đi: pump chỉ bỏ qua (`let _ =`)
    }

    #[test]
    fn the_start_limit_is_sixty_seconds_like_the_qt_app() {
        assert_eq!(HOST_START_LIMIT, Duration::from_secs(60));
        assert!(HOST_START_FAILURE.starts_with("ABook chưa mở được. Bạn thử lại;"));
    }

    #[test]
    fn the_start_failure_page_offers_try_again_that_restarts_the_host_other_failures_do_not() {
        let stuck = failure_script(HOST_START_FAILURE, true);
        assert!(stuck.contains("Thử lại") && stuck.contains("action('restartHost')") && stuck.contains("if(true)"));
        assert!(stuck.contains(&Value::from(HOST_START_FAILURE).to_string()));
        let died = failure_script("ABook dừng bất ngờ.", false);
        assert!(died.contains("if(false)"));
    }

    #[test]
    fn a_download_task_that_died_without_answering_counts_as_failed() {
        let (sender, receiver) = mpsc::channel::<u8>();
        drop(sender);
        let progress = AtomicU64::new(0);
        assert_eq!(wait_unless_stalled(&receiver, Instant::now(), &progress, Duration::from_secs(60)), None);
    }
}

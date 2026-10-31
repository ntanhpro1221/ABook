// Bộ dò khay Win32 (Lead 01-11, việc 2 của 0.4.152): chạy đúng mã src/trayicon.cpp (include nguyên file, không sửa dòng nào) trên
// Explorer thật. Shell_NotifyIconW và GetProcAddress được thay bằng bộ bọc ghi lại từng lệnh: mọi NIM_ADD / NIM_MODIFY bị ép thêm
// NIF_STATE + NIS_HIDDEN nên icon ẩn ngay từ lúc thêm (không gì hiện trên màn hình), NIF_INFO (bong bóng) bị chặn hẳn.
//   tray_probe.exe shell <out.json>     icon ẩn trên khay thật: thêm / đổi / gỡ, icon cũ còn sót, dựng lại khay, thông điệp phát tán
//   tray_probe.exe menu <out_prefix>    menu theo chế độ Windows chụp vào bitmap (CHỈ chạy trong desktop riêng: tools/guarded_process.py)
//   tray_probe.exe menu-plain <prefix>  như trên nhưng không gọi allowDarkMenus: đối chứng (menu Win32 mặc định luôn sáng)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <shellapi.h>

#include <QCoreApplication>
#include <QFile>
#include <QImage>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QVariantMap>

#include <atomic>
#include <thread>

static QJsonArray g_calls;
static QJsonArray g_themeCalls;

static QString messageName(DWORD message) {
    switch (message) {
    case NIM_ADD: return QStringLiteral("NIM_ADD");
    case NIM_MODIFY: return QStringLiteral("NIM_MODIFY");
    case NIM_DELETE: return QStringLiteral("NIM_DELETE");
    case NIM_SETVERSION: return QStringLiteral("NIM_SETVERSION");
    case NIM_SETFOCUS: return QStringLiteral("NIM_SETFOCUS");
    default: return QStringLiteral("?");
    }
}

static BOOL trayProbeNotify(DWORD message, PNOTIFYICONDATAW data) {
    if (data->uFlags & NIF_INFO) {   // bong bóng hiện trên màn hình: không bao giờ gửi
        g_calls.append(QJsonObject{{"message", messageName(message)}, {"blocked", QStringLiteral("NIF_INFO")}});
        return FALSE;
    }
    if (message == NIM_ADD || message == NIM_MODIFY) {
        data->uFlags |= NIF_STATE;
        data->dwState |= NIS_HIDDEN;
        data->dwStateMask |= NIS_HIDDEN;
    }
    SetLastError(0);
    const BOOL ok = Shell_NotifyIconW(message, data);
    const DWORD error = GetLastError();
    g_calls.append(QJsonObject{{"message", messageName(message)}, {"ok", bool(ok)}, {"lastError", qint64(error)},
                               {"guid", bool(data->uFlags & NIF_GUID)}, {"hidden", bool((data->uFlags & NIF_STATE) && (data->dwState & NIS_HIDDEN))},
                               {"version", qint64(message == NIM_SETVERSION ? data->uVersion : 0)}});
    return ok;
}

// Ghi thứ tự gọi các hàm uxtheme không tài liệu hóa (135 SetPreferredAppMode, 133 AllowDarkModeForWindow, 136 FlushMenuThemes)
static FARPROC g_real135 = nullptr, g_real133 = nullptr, g_real136 = nullptr;
static int WINAPI probe135(int mode) {
    g_themeCalls.append(QStringLiteral("SetPreferredAppMode(%1)").arg(mode));
    return reinterpret_cast<int(WINAPI *)(int)>(g_real135)(mode);
}
static BOOL WINAPI probe133(HWND hwnd, BOOL allow) {
    g_themeCalls.append(QStringLiteral("AllowDarkModeForWindow(%1)").arg(allow));
    return reinterpret_cast<BOOL(WINAPI *)(HWND, BOOL)>(g_real133)(hwnd, allow);
}
static void WINAPI probe136() {
    g_themeCalls.append(QStringLiteral("FlushMenuThemes()"));
    reinterpret_cast<void(WINAPI *)()>(g_real136)();
}
static FARPROC trayProbeGetProcAddress(HMODULE module, LPCSTR name) {
    const FARPROC real = GetProcAddress(module, name);
    if (!real || !IS_INTRESOURCE(name))
        return real;
    switch (reinterpret_cast<quintptr>(name)) {
    case 135: g_real135 = real; return reinterpret_cast<FARPROC>(probe135);
    case 133: g_real133 = real; return reinterpret_cast<FARPROC>(probe133);
    case 136: g_real136 = real; return reinterpret_cast<FARPROC>(probe136);
    default: return real;
    }
}

#define Shell_NotifyIconW trayProbeNotify
#define GetProcAddress trayProbeGetProcAddress
#include "../src/trayicon.cpp"
#undef GetProcAddress
#undef Shell_NotifyIconW

namespace {

QJsonArray take(QJsonArray &calls) {
    QJsonArray out = calls;
    calls = QJsonArray();
    return out;
}

void pump(int ms) {
    const ULONGLONG until = GetTickCount64() + ms;
    MSG msg;
    while (GetTickCount64() < until) {
        while (PeekMessageW(&msg, nullptr, 0, 0, PM_REMOVE)) {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
        QCoreApplication::processEvents();
        Sleep(10);
    }
}

// ---- thông điệp phát tán: TaskbarCreated đi đường HWND_BROADCAST, chỉ tới cửa sổ top-level ----
UINT g_probeMessage = 0;
std::atomic<int> g_seenTray{0}, g_seenTopLevel{0};
WNDPROC g_trayProc = nullptr;

LRESULT CALLBACK traySubclass(HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam) {
    if (message == g_probeMessage && g_probeMessage)
        ++g_seenTray;
    return CallWindowProcW(g_trayProc, hwnd, message, wParam, lParam);
}

LRESULT CALLBACK topLevelProc(HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam) {
    if (message == g_probeMessage && g_probeMessage)
        ++g_seenTopLevel;
    return DefWindowProcW(hwnd, message, wParam, lParam);
}

HWND makeWindow(bool messageOnly) {
    static const ATOM klass = [] {
        WNDCLASSEXW info{};
        info.cbSize = sizeof(info);
        info.lpfnWndProc = topLevelProc;
        info.hInstance = GetModuleHandleW(nullptr);
        info.lpszClassName = L"ABookTrayProbeWindow";
        return RegisterClassExW(&info);
    }();
    if (!klass)
        return nullptr;
    // Top-level: không WS_VISIBLE, không bao giờ ShowWindow - không vẽ gì; WS_EX_TOOLWINDOW để không lên thanh tác vụ
    return CreateWindowExW(messageOnly ? 0 : WS_EX_TOOLWINDOW, L"ABookTrayProbeWindow", L"", messageOnly ? 0 : WS_POPUP, 0, 0, 0, 0,
                           messageOnly ? HWND_MESSAGE : nullptr, nullptr, GetModuleHandleW(nullptr), nullptr);
}

// Thông điệp đăng ký riêng (app khác không biết, DefWindowProc bỏ qua) phát như Explorer phát TaskbarCreated: cửa sổ thật của
// TrayIcon (đã subclass để đếm) có nhận không, so với một cửa sổ top-level ẩn.
QJsonObject broadcastReach() {
    g_probeMessage = RegisterWindowMessageW(L"ABookTrayProbe-Broadcast-1f6c");
    TrayIcon tray;
    const HWND trayWindow = reinterpret_cast<HWND>(tray.window());
    g_trayProc = reinterpret_cast<WNDPROC>(SetWindowLongPtrW(trayWindow, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(traySubclass)));
    const HWND topLevel = makeWindow(false);
    wchar_t klass[64] = {};
    GetClassNameW(trayWindow, klass, 64);
    const bool messageOnly = GetAncestor(trayWindow, GA_PARENT) != GetDesktopWindow();   // gốc của cửa sổ message-only không phải desktop
    const BOOL sent = SendNotifyMessageW(HWND_BROADCAST, g_probeMessage, 0, 0);
    pump(500);
    // Gửi thẳng (không phát tán) tới cửa sổ khay: chứng minh bộ đếm hoạt động
    SendMessageW(trayWindow, g_probeMessage, 0, 0);
    QJsonObject out{{"sent", bool(sent)}, {"trayWindowClass", QString::fromWCharArray(klass)}, {"trayWindowIsMessageOnly", messageOnly},
                    {"trayWindowGotBroadcast", g_seenTray.load() > 1 ? true : false}, {"trayWindowCountWithDirectSend", g_seenTray.load()},
                    {"hiddenTopLevelGotBroadcast", g_seenTopLevel.load()}};
    SetWindowLongPtrW(trayWindow, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(g_trayProc));
    DestroyWindow(topLevel);
    return out;
}

int shellProbe(const QString &outPath) {
    QJsonObject report;
    OSVERSIONINFOW info{};
    info.dwOSVersionInfoSize = sizeof(info);
    reinterpret_cast<LONG(WINAPI *)(OSVERSIONINFOW *)>(GetProcAddress(GetModuleHandleW(L"ntdll.dll"), "RtlGetVersion"))(&info);
    report["build"] = qint64(info.dwBuildNumber);
    report["taskbarFound"] = FindWindowW(L"Shell_TrayWnd", nullptr) != nullptr;

    // 1. Thêm (GUID cố định) + bản 4, đổi tooltip, gỡ - như app mở, cập nhật, thoát
    {
        TrayIcon tray;
        tray.setTooltip(QStringLiteral("ABook - bộ dò"));
        tray.setVisible(true);
        report["addAvailable"] = tray.available();
        report["add"] = take(g_calls);
        tray.setTooltip(QStringLiteral("ABook - bộ dò 2"));
        report["modify"] = take(g_calls);
        tray.showMessage(QStringLiteral("t"), QStringLiteral("m"));   // phải bị chặn, không bong bóng nào
        report["balloonBlocked"] = take(g_calls);
        tray.setVisible(false);
        report["remove"] = take(g_calls);
        report["removeAvailable"] = tray.available();
    }
    // 2. Icon cũ còn sót: lần chạy trước chết - cửa sổ mất mà icon cùng GUID vẫn đăng ký. Lần sau phải gỡ rồi thêm lại được.
    {
        auto *crashed = new TrayIcon;
        crashed->setTooltip(QStringLiteral("ABook - lần chết"));
        crashed->setVisible(true);
        report["staleFirstAdd"] = take(g_calls);
        DestroyWindow(reinterpret_cast<HWND>(crashed->window()));   // không NIM_DELETE: như tiến trình chết
        TrayIcon next;
        next.setTooltip(QStringLiteral("ABook - lần sau"));
        next.setVisible(true);
        report["staleNextAvailable"] = next.available();
        report["staleNextAdd"] = take(g_calls);
        next.setVisible(false);
        report["staleNextRemove"] = take(g_calls);
        // `crashed` cố ý không xoá (cửa sổ đã huỷ, như tiến trình đã chết)
    }
    // 3. Explorer dựng lại thanh tác vụ: icon mất, handleTaskbarCreated thêm lại (gọi thẳng; việc thông điệp có tới không ở mục 4)
    {
        TrayIcon tray;
        tray.setTooltip(QStringLiteral("ABook - dựng lại"));
        tray.setVisible(true);
        take(g_calls);
        NOTIFYICONDATAW gone{};   // giả Explorer mới: icon cũ không còn
        gone.cbSize = sizeof(gone);
        gone.hWnd = reinterpret_cast<HWND>(tray.window());
        gone.uID = kIconId;
        gone.uFlags = NIF_GUID;
        gone.guidItem = kIconGuid;
        Shell_NotifyIconW(NIM_DELETE, &gone);
        gone.uFlags = 0;
        Shell_NotifyIconW(NIM_DELETE, &gone);
        tray.handleTaskbarCreated();
        report["taskbarCreatedAvailable"] = tray.available();
        report["taskbarCreatedReAdd"] = take(g_calls);
        tray.setVisible(false);
        take(g_calls);
    }
    // 4. Thông điệp phát tán có tới cửa sổ của TrayIcon không
    report["broadcast"] = broadcastReach();
    report["themeCalls"] = take(g_themeCalls);

    QFile file(outPath);
    if (!file.open(QIODevice::WriteOnly))
        return 2;
    file.write(QJsonDocument(report).toJson());
    return 0;
}

// ---- menu: chỉ chạy trong desktop riêng ----
std::atomic<bool> g_captured{false};
QJsonObject g_capture;

double meanLuma(const QImage &image) {
    if (image.isNull())
        return -1;
    double sum = 0;
    for (int y = 0; y < image.height(); ++y)
        for (int x = 0; x < image.width(); ++x) {
            const QRgb p = image.pixel(x, y);
            sum += 0.2126 * qRed(p) + 0.7152 * qGreen(p) + 0.0722 * qBlue(p);
        }
    return sum / (image.width() * image.height());
}

QImage grab(HWND menu, int w, int h, bool printWindow) {
    HDC screen = GetDC(nullptr);
    HDC dc = CreateCompatibleDC(screen);
    HBITMAP bitmap = CreateCompatibleBitmap(screen, w, h);
    HGDIOBJ old = SelectObject(dc, bitmap);
    RECT fill{0, 0, w, h};
    FillRect(dc, &fill, static_cast<HBRUSH>(GetStockObject(GRAY_BRUSH)));   // xám 50 %: phân biệt "không vẽ gì" với sáng / tối
    const BOOL ok = printWindow ? PrintWindow(menu, dc, PW_RENDERFULLCONTENT)
                                : BOOL(SendMessageW(menu, WM_PRINT, WPARAM(dc), PRF_CLIENT | PRF_NONCLIENT | PRF_ERASEBKGND | PRF_CHILDREN) || true);
    QImage image(w, h, QImage::Format_RGB32);
    BITMAPINFO info{};
    info.bmiHeader = {sizeof(BITMAPINFOHEADER), w, -h, 1, 32, BI_RGB};
    GetDIBits(dc, bitmap, 0, h, image.bits(), &info, DIB_RGB_COLORS);
    SelectObject(dc, old);
    DeleteObject(bitmap);
    DeleteDC(dc);
    ReleaseDC(nullptr, screen);
    return ok ? image : QImage();
}

void captureMenuThread(HWND owner, const QString &path) {
    for (int i = 0; i < 200 && !g_captured; ++i) {
        HWND menu = FindWindowW(L"#32768", nullptr);
        if (menu && IsWindowVisible(menu)) {
            Sleep(300);   // menu mờ dần vào: đợi hết hiệu ứng
            RECT rect{};
            GetWindowRect(menu, &rect);
            const int w = rect.right - rect.left, h = rect.bottom - rect.top;
            const QImage printed = grab(menu, w, h, true), painted = grab(menu, w, h, false);
            if (!printed.isNull())
                printed.save(path + "_printwindow.png");
            painted.save(path + "_wmprint.png");
            g_capture = QJsonObject{{"width", w}, {"height", h}, {"printWindowOk", !printed.isNull()},
                                    {"printWindowLuma", meanLuma(printed)}, {"wmPrintLuma", meanLuma(painted)}};
            g_captured = true;
            break;
        }
        Sleep(25);
    }
    // EndMenu chỉ đóng menu của luồng gọi; từ luồng khác thì WM_CANCELMODE tới cửa sổ chủ (vòng lặp menu vẫn nhận thông điệp gửi)
    SendMessageTimeoutW(owner, WM_CANCELMODE, 0, 0, SMTO_NORMAL, 2000, nullptr);
}

int menuProbe(const QString &prefix, bool themed) {
    const QVariantList actions{QVariantMap{{"action", "open"}, {"label", "Mở ABook"}, {"enabled", true}},
                               QVariantMap{{"action", "play"}, {"label", "Phát / tạm dừng"}, {"enabled", false}},
                               QVariantMap{{"separator", true}},
                               QVariantMap{{"action", "quit"}, {"label", "Thoát"}, {"enabled", true}}};
    QJsonObject report;
    // Cửa sổ thật của TrayIcon (HWND_MESSAGE) rồi cửa sổ top-level ẩn - đúng thứ tự Win32TrayShell::popup
    for (const bool real : {true, false}) {
        TrayIcon tray;
        const HWND owner = real ? reinterpret_cast<HWND>(tray.window()) : makeWindow(false);
        const QString name = prefix + (real ? "_traywindow" : "_toplevel");
        QStringList commands;
        const quintptr menu = TrayIcon::buildMenu(actions, commands);
        g_captured = false;
        g_capture = QJsonObject();
        std::thread capture(captureMenuThread, owner, name);
        const bool dark = themed && TrayIcon::allowDarkMenus(quintptr(owner));   // `menu-plain`: đối chứng, không gọi
        SetLastError(0);
        const BOOL fg = SetForegroundWindow(owner);
        const DWORD fgError = GetLastError();
        SetLastError(0);
        const BOOL picked = TrackPopupMenuEx(reinterpret_cast<HMENU>(menu), TPM_RETURNCMD | TPM_RIGHTBUTTON | TPM_BOTTOMALIGN | TPM_LEFTALIGN,
                                             200, 400, owner, nullptr);
        const DWORD trackError = GetLastError();
        PostMessageW(owner, WM_NULL, 0, 0);
        capture.join();
        report[real ? "trayWindow" : "topLevel"] = QJsonObject{{"darkApplied", dark}, {"setForeground", bool(fg)}, {"setForegroundError", qint64(fgError)},
                                                                  {"picked", qint64(picked)}, {"trackError", qint64(trackError)}, {"capture", g_capture}};
        TrayIcon::destroyMenu(menu);
        if (!real)
            DestroyWindow(owner);
    }
    report["themeCalls"] = take(g_themeCalls);
    QFile file(prefix + ".json");
    if (!file.open(QIODevice::WriteOnly))
        return 2;
    file.write(QJsonDocument(report).toJson());
    return 0;
}

}  // namespace

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    const QStringList args = app.arguments();
    if (args.size() == 3 && args.at(1) == QLatin1String("shell"))
        return shellProbe(args.at(2));
    if (args.size() == 3 && (args.at(1) == QLatin1String("menu") || args.at(1) == QLatin1String("menu-plain")))
        return menuProbe(args.at(2), args.at(1) == QLatin1String("menu"));
    return 1;
}

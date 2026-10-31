#include "trayicon.h"

#include <QCoreApplication>
#include <QJSValue>
#include <QVariantMap>

#include <iterator>
#include <utility>

#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <windowsx.h>
#include <shellapi.h>

namespace {

// GUID cố định: Windows nhớ vị trí và việc người dùng ghim / ẩn icon theo GUID này. Chỉ gắn được khi exe cùng đường dẫn với lần
// trước (bản dựng ở thư mục khác thì Windows từ chối), nên thêm thất bại thì thử lại không GUID.
const GUID kIconGuid = {0x6f1b6c52, 0x3a0e, 0x4d3c, {0x9b, 0x1d, 0x7a, 0x41, 0x2e, 0x5c, 0x0a, 0xd8}};
constexpr UINT kIconId = 1;
constexpr wchar_t kWindowClass[] = L"ABookTrayWindow";

QVariantMap itemMap(const QVariant &entry) {
    if (entry.metaType() == QMetaType::fromType<QJSValue>())
        return entry.value<QJSValue>().toVariant().toMap();
    return entry.toMap();
}

void copyClipped(wchar_t *target, int capacity, const QString &text) {
    const QString clipped = TrayIcon::clip(text, capacity - 1);
    clipped.toWCharArray(target);
    target[clipped.size()] = L'\0';
}

class Win32TrayShell final : public TrayShell {
public:
    bool add(quintptr window, const QString &tip) override {
        // Lần chạy trước chết giữa chừng có thể để lại icon cùng GUID: gỡ rồi thêm lại.
        m_guid = true;
        bool added = notify(NIM_ADD, window, tip);
        if (!added) {
            notify(NIM_DELETE, window, tip);
            added = notify(NIM_ADD, window, tip);
        }
        if (!added) {
            m_guid = false;
            added = notify(NIM_ADD, window, tip);
        }
        if (!added)
            return false;
        NOTIFYICONDATAW data = base(window);
        data.uVersion = NOTIFYICON_VERSION_4;
        Shell_NotifyIconW(NIM_SETVERSION, &data);
        return true;
    }
    bool modify(quintptr window, const QString &tip) override { return notify(NIM_MODIFY, window, tip); }
    void remove(quintptr window) override {
        NOTIFYICONDATAW data = base(window);
        Shell_NotifyIconW(NIM_DELETE, &data);
    }
    void balloon(quintptr window, const QString &title, const QString &text) override {
        NOTIFYICONDATAW data = base(window);
        data.uFlags = NIF_INFO;
        copyClipped(data.szInfoTitle, int(std::size(data.szInfoTitle)), title);
        copyClipped(data.szInfo, int(std::size(data.szInfo)), text);
        data.dwInfoFlags = NIIF_INFO | NIIF_NOSOUND;
        Shell_NotifyIconW(NIM_MODIFY, &data);
    }
    unsigned popup(quintptr window, quintptr menu, int x, int y) override {
        const HWND hwnd = reinterpret_cast<HWND>(window);
        TrayIcon::allowDarkMenus(window);
        // Đúng hướng dẫn của Microsoft: không đưa cửa sổ lên trước thì menu không đóng khi bấm ra ngoài; WM_NULL sau đó để
        // thông điệp tiếp theo không bị nuốt.
        SetForegroundWindow(hwnd);
        const UINT align = GetSystemMetrics(SM_MENUDROPALIGNMENT) ? TPM_RIGHTALIGN : TPM_LEFTALIGN;
        const BOOL command = TrackPopupMenuEx(reinterpret_cast<HMENU>(menu), TPM_RETURNCMD | TPM_RIGHTBUTTON | TPM_BOTTOMALIGN | align, x, y, hwnd, nullptr);
        PostMessageW(hwnd, WM_NULL, 0, 0);
        return unsigned(command);
    }

private:
    NOTIFYICONDATAW base(quintptr window) const {
        NOTIFYICONDATAW data{};
        data.cbSize = sizeof(data);
        data.hWnd = reinterpret_cast<HWND>(window);
        data.uID = kIconId;
        if (m_guid) {
            data.uFlags = NIF_GUID;
            data.guidItem = kIconGuid;
        }
        return data;
    }
    // Icon trong resource của exe (appicon.rc, tên IDI_ICON1), đúng cỡ nhỏ theo DPI hiện tại.
    static HICON icon() {
        const int size = GetSystemMetricsForDpi(SM_CXSMICON, GetDpiForSystem());
        HICON handle = static_cast<HICON>(LoadImageW(GetModuleHandleW(nullptr), L"IDI_ICON1", IMAGE_ICON, size, size, LR_SHARED));
        return handle ? handle : LoadIconW(nullptr, IDI_APPLICATION);
    }
    bool notify(DWORD message, quintptr window, const QString &tip) {
        NOTIFYICONDATAW data = base(window);
        data.uFlags |= NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_SHOWTIP;   // bản 4 chỉ hiện tooltip khi có NIF_SHOWTIP
        data.uCallbackMessage = TrayIcon::kCallbackMessage;
        data.hIcon = icon();
        copyClipped(data.szTip, int(std::size(data.szTip)), tip);
        return Shell_NotifyIconW(message, &data) != FALSE;
    }
    bool m_guid = true;
};

UINT taskbarCreatedMessage() {
    static const UINT message = RegisterWindowMessageW(L"TaskbarCreated");
    return message;
}

LRESULT CALLBACK windowProc(HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam) {
    if (message == WM_NCCREATE) {
        const auto *create = reinterpret_cast<const CREATESTRUCTW *>(lParam);
        SetWindowLongPtrW(hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(create->lpCreateParams));
    }
    auto *self = reinterpret_cast<TrayIcon *>(GetWindowLongPtrW(hwnd, GWLP_USERDATA));
    if (self) {
        if (message == TrayIcon::kCallbackMessage) {
            self->handleCallback(wParam, lParam);
            return 0;
        }
        if (message == taskbarCreatedMessage()) {
            self->handleTaskbarCreated();
            return 0;
        }
    }
    return DefWindowProcW(hwnd, message, wParam, lParam);
}

quintptr createMessageWindow(TrayIcon *owner) {
    static const ATOM windowClass = [] {
        WNDCLASSEXW info{};
        info.cbSize = sizeof(info);
        info.lpfnWndProc = windowProc;
        info.hInstance = GetModuleHandleW(nullptr);
        info.lpszClassName = kWindowClass;
        return RegisterClassExW(&info);
    }();
    if (!windowClass)
        return 0;
    return reinterpret_cast<quintptr>(CreateWindowExW(0, kWindowClass, L"", 0, 0, 0, 0, 0, HWND_MESSAGE, nullptr, GetModuleHandleW(nullptr), owner));
}

}  // namespace

std::unique_ptr<TrayShell> makeWin32TrayShell() { return std::make_unique<Win32TrayShell>(); }

QString TrayIcon::clip(const QString &text, int limit) {
    if (text.size() <= limit)
        return text;
    int length = limit;
    if (length > 0 && text.at(length - 1).isHighSurrogate())
        --length;
    return text.left(length);
}

TrayIcon::TrayIcon(QObject *parent) : TrayIcon(makeWin32TrayShell(), parent) {}

TrayIcon::TrayIcon(std::unique_ptr<TrayShell> shell, QObject *parent) : QObject(parent), m_shell(std::move(shell)) {
    m_window = createMessageWindow(this);
    taskbarCreatedMessage();   // đăng ký sớm: Explorer khởi động lại thì gửi tới cửa sổ này
    // Thoát bình thường thì icon biến mất ngay, không đợi người dùng rê chuột qua icon ma.
    if (QCoreApplication::instance())
        connect(QCoreApplication::instance(), &QCoreApplication::aboutToQuit, this, &TrayIcon::removeIcon);
}

TrayIcon::~TrayIcon() {
    removeIcon();
    if (m_window) {
        SetWindowLongPtrW(reinterpret_cast<HWND>(m_window), GWLP_USERDATA, 0);
        DestroyWindow(reinterpret_cast<HWND>(m_window));
    }
}

void TrayIcon::setTooltip(const QString &tooltip) {
    if (m_tooltip == tooltip)
        return;
    m_tooltip = tooltip;
    emit tooltipChanged();
    const QString shown = clip(tooltip, kTipLimit);
    if (m_added && shown != m_shownTip) {
        m_shownTip = shown;
        m_shell->modify(m_window, shown);
    }
}

void TrayIcon::setActions(const QVariantList &actions) {
    if (m_actions == actions)
        return;
    m_actions = actions;
    emit actionsChanged();
}

void TrayIcon::setVisible(bool visible) {
    if (m_visible == visible)
        return;
    m_visible = visible;
    emit visibleChanged();
    if (visible) addIcon(); else removeIcon();
}

void TrayIcon::addIcon() {
    if (!m_visible || m_added || !m_window)
        return;
    m_shownTip = clip(m_tooltip, kTipLimit);
    if (!m_shell->add(m_window, m_shownTip))
        return;
    m_added = true;
    emit availableChanged();
}

void TrayIcon::removeIcon() {
    if (!m_added)
        return;
    m_shell->remove(m_window);
    m_added = false;
    emit availableChanged();
}

void TrayIcon::showMessage(const QString &title, const QString &message) {
    if (m_added)
        m_shell->balloon(m_window, title, message);
}

void TrayIcon::handleCallback(quintptr wParam, quintptr lParam) {
    switch (LOWORD(lParam)) {
    case NIN_SELECT:
    case NIN_KEYSELECT:
        emit activated();
        break;
    case WM_CONTEXTMENU:
        showMenu(GET_X_LPARAM(wParam), GET_Y_LPARAM(wParam));
        break;
    default:
        break;
    }
}

void TrayIcon::handleTaskbarCreated() {
    // Thanh tác vụ mới không có icon nào của ta: coi như chưa thêm, thêm lại.
    if (m_added) {
        m_added = false;
        emit availableChanged();
    }
    addIcon();
}

void TrayIcon::showMenu(int x, int y) {
    if (!m_added)
        return;
    const quintptr menu = buildMenu(m_actions, m_commands);
    if (!menu)
        return;
    const unsigned command = m_shell->popup(m_window, menu, x, y);
    destroyMenu(menu);
    // Phát lệnh SAU khi menu đã đóng và hủy: lệnh "Thoát" hay "Mở" không chạy trong vòng lặp của menu.
    if (command)
        selectCommand(command);
}

void TrayIcon::selectCommand(unsigned command) {
    if (command >= 1 && command <= unsigned(m_commands.size()))
        emit triggered(m_commands.at(int(command) - 1));
}

quintptr TrayIcon::buildMenu(const QVariantList &actions, QStringList &actionByCommand) {
    actionByCommand.clear();
    HMENU menu = CreatePopupMenu();
    if (!menu)
        return 0;
    for (const QVariant &entry : actions) {
        const QVariantMap item = itemMap(entry);
        if (item.value(QStringLiteral("separator")).toBool()) {
            AppendMenuW(menu, MF_SEPARATOR, 0, nullptr);
            continue;
        }
        actionByCommand.append(item.value(QStringLiteral("action")).toString());
        QString label = item.value(QStringLiteral("label")).toString();
        label.replace(QLatin1Char('&'), QStringLiteral("&&"));   // "&" là phím tắt của menu Win32
        const UINT state = item.value(QStringLiteral("enabled")).toBool() ? MF_ENABLED : MF_GRAYED;
        AppendMenuW(menu, MF_STRING | state, UINT_PTR(actionByCommand.size()), reinterpret_cast<LPCWSTR>(label.utf16()));
    }
    return reinterpret_cast<quintptr>(menu);
}

void TrayIcon::destroyMenu(quintptr menu) {
    if (menu)
        DestroyMenu(reinterpret_cast<HMENU>(menu));
}

bool TrayIcon::allowDarkMenus(quintptr window) {
    static const bool supported = [] {
        // uxtheme không tài liệu hóa: số hiệu hàm 133 / 135 / 136 chỉ đúng từ Windows 10 1903 (build 18362).
        using RtlGetVersion = LONG(WINAPI *)(OSVERSIONINFOW *);
        const HMODULE ntdll = GetModuleHandleW(L"ntdll.dll");
        const auto version = ntdll ? reinterpret_cast<RtlGetVersion>(GetProcAddress(ntdll, "RtlGetVersion")) : nullptr;
        OSVERSIONINFOW info{};
        info.dwOSVersionInfoSize = sizeof(info);
        return version && version(&info) == 0 && info.dwBuildNumber >= 18362;
    }();
    static bool applied = false;
    if (!supported)
        return false;
    const HMODULE uxtheme = LoadLibraryExW(L"uxtheme.dll", nullptr, LOAD_LIBRARY_SEARCH_SYSTEM32);
    if (!uxtheme)
        return false;
    const auto setPreferredAppMode = reinterpret_cast<int(WINAPI *)(int)>(GetProcAddress(uxtheme, MAKEINTRESOURCEA(135)));
    const auto allowDarkForWindow = reinterpret_cast<BOOL(WINAPI *)(HWND, BOOL)>(GetProcAddress(uxtheme, MAKEINTRESOURCEA(133)));
    const auto flushMenuThemes = reinterpret_cast<void(WINAPI *)()>(GetProcAddress(uxtheme, MAKEINTRESOURCEA(136)));
    if (!setPreferredAppMode || !allowDarkForWindow || !flushMenuThemes)
        return false;
    if (!applied) {
        setPreferredAppMode(1);   // AllowDark: menu theo cài đặt "chế độ ứng dụng" của Windows, không ép tối
        applied = true;
    }
    allowDarkForWindow(reinterpret_cast<HWND>(window), TRUE);
    flushMenuThemes();
    return true;
}

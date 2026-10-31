#pragma once

#include <QObject>
#include <QString>
#include <QStringList>
#include <QVariantList>
#include <QtQml/qqmlregistration.h>

#include <memory>

// Ranh giới với Shell_NotifyIconW và TrackPopupMenuEx: khay thật đi qua đây, bộ thử thay bằng đồ giả nên không icon nào hiện trong
// khay của chủ máy. Tay cầm cửa sổ / menu truyền dạng quintptr để header không kéo windows.h.
class TrayShell {
public:
    virtual ~TrayShell() = default;
    virtual bool add(quintptr window, const QString &tip) = 0;
    virtual bool modify(quintptr window, const QString &tip) = 0;
    virtual void remove(quintptr window) = 0;
    virtual void balloon(quintptr window, const QString &title, const QString &text) = 0;
    // Mở menu tại (x, y) và đợi người dùng chọn; trả mã lệnh đã chọn, 0 là đóng mà không chọn.
    virtual unsigned popup(quintptr window, quintptr menu, int x, int y) = 0;
};

// Khay hệ thống viết thẳng bằng Win32 (Shell_NotifyIcon, bản 4) thay Qt.labs.platform: bản ấy kéo Qt6Widgets.dll (6,3 MB) vào chỉ vì
// khay. Một cửa sổ top-level ẩn giữ icon (nhận được TaskbarCreated phát tán); menu dựng lại từ `actions` mỗi lần mở nên luôn
// theo trạng thái mới nhất.
// `actions` cùng dạng với TrayMenuModel: {action, label, enabled} hoặc {separator: true}.
class TrayIcon : public QObject {
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QString tooltip READ tooltip WRITE setTooltip NOTIFY tooltipChanged FINAL)
    Q_PROPERTY(QVariantList actions READ actions WRITE setActions NOTIFY actionsChanged FINAL)
    Q_PROPERTY(bool visible READ isVisible WRITE setVisible NOTIFY visibleChanged FINAL)
    // Icon đã nằm trong khay (thêm được). Explorer chưa chạy thì false, khi nó dựng lại khay icon được thêm lại.
    Q_PROPERTY(bool available READ available NOTIFY availableChanged FINAL)
public:
    explicit TrayIcon(QObject *parent = nullptr);
    explicit TrayIcon(std::unique_ptr<TrayShell> shell, QObject *parent = nullptr);
    ~TrayIcon() override;

    // szTip của Windows chứa 127 ký tự UTF-16; cắt không bao giờ chia đôi một cặp surrogate.
    static constexpr int kTipLimit = 127;
    static QString clip(const QString &text, int limit);
    // Thông điệp Windows gửi cửa sổ ẩn khi có sự kiện trên icon.
    static constexpr unsigned kCallbackMessage = 0x8001;   // WM_APP + 1

    QString tooltip() const { return m_tooltip; }
    void setTooltip(const QString &tooltip);
    QVariantList actions() const { return m_actions; }
    void setActions(const QVariantList &actions);
    bool isVisible() const { return m_visible; }
    void setVisible(bool visible);
    bool available() const { return m_added; }

    Q_INVOKABLE void showMessage(const QString &title, const QString &message);

    // Menu popup Win32 dựng từ `actions`: mục tách là MF_SEPARATOR, mục tắt là MF_GRAYED, mã lệnh = số thứ tự mục (không tính
    // dòng tách) từ 1; actionByCommand[mã - 1] là action tương ứng. Người gọi hủy bằng destroyMenu.
    static quintptr buildMenu(const QVariantList &actions, QStringList &actionByCommand);
    static void destroyMenu(quintptr menu);
    // Menu theo chế độ tối của Windows (uxtheme ordinal 133/135/136, chỉ từ build 18362); thiếu thì bỏ qua êm, trả false.
    static bool allowDarkMenus(quintptr window);

    quintptr window() const { return m_window; }
    // Chuỗi dưới đây là phần thân của thủ tục cửa sổ, để bộ thử gọi trực tiếp hoặc qua SendMessage.
    void handleCallback(quintptr wParam, quintptr lParam);
    void handleTaskbarCreated();
    void showMenu(int x, int y);
    void selectCommand(unsigned command);

signals:
    void tooltipChanged();
    void actionsChanged();
    void visibleChanged();
    void availableChanged();
    // Bấm trái hoặc Enter / Space trên icon.
    void activated();
    void triggered(const QString &action);

private:
    void addIcon();
    void removeIcon();

    std::unique_ptr<TrayShell> m_shell;
    quintptr m_window = 0;
    QString m_tooltip, m_shownTip;
    QVariantList m_actions;
    QStringList m_commands;
    bool m_visible = false;
    bool m_added = false;
};

std::unique_ptr<TrayShell> makeWin32TrayShell();

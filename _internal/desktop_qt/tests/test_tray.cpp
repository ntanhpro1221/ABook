// Khay Win32 tự viết (src/trayicon.cpp). GUILESS: cửa sổ top-level ẩn không bao giờ hiện, menu Win32 dựng thật nhưng không bao giờ mở,
// Shell_NotifyIcon thay bằng đồ giả nên KHÔNG icon nào vào khay của máy chạy test.
#include "trayicon.h"

#include <QJSEngine>
#include <QJSValue>
#include <QSignalSpy>
#include <QtTest>

#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

namespace {

struct MenuRow {
    QString text;
    bool separator = false;
    bool grayed = false;
    unsigned id = 0;
};

QList<MenuRow> readMenu(quintptr handle) {
    const HMENU menu = reinterpret_cast<HMENU>(handle);
    QList<MenuRow> rows;
    for (int i = 0, count = GetMenuItemCount(menu); i < count; ++i) {
        wchar_t text[128] = {};
        MENUITEMINFOW info{};
        info.cbSize = sizeof(info);
        info.fMask = MIIM_FTYPE | MIIM_STATE | MIIM_ID | MIIM_STRING;
        info.dwTypeData = text;
        info.cch = 127;
        GetMenuItemInfoW(menu, UINT(i), TRUE, &info);
        MenuRow row;
        row.separator = (info.fType & MFT_SEPARATOR) != 0;
        row.grayed = (info.fState & MFS_GRAYED) != 0;
        row.id = row.separator ? 0 : info.wID;
        row.text = QString::fromWCharArray(text);
        rows << row;
    }
    return rows;
}

class FakeShell final : public TrayShell {
public:
    int adds = 0, removes = 0, modifies = 0, balloons = 0, popups = 0;
    bool addResult = true;
    QString lastTip, lastBalloonTitle, lastBalloonText;
    unsigned choice = 0;                // mã lệnh "người dùng chọn" khi menu mở
    QList<MenuRow> shown;               // nội dung menu đúng lúc mở
    int popupX = 0, popupY = 0;
    quintptr lastWindow = 0;

    bool add(quintptr window, const QString &tip) override { ++adds; lastWindow = window; lastTip = tip; return addResult; }
    bool modify(quintptr, const QString &tip) override { ++modifies; lastTip = tip; return true; }
    void remove(quintptr) override { ++removes; }
    void balloon(quintptr, const QString &title, const QString &text) override { ++balloons; lastBalloonTitle = title; lastBalloonText = text; }
    unsigned popup(quintptr, quintptr menu, int x, int y) override {
        ++popups; popupX = x; popupY = y;
        shown = readMenu(menu);
        return choice;
    }
};

// Cùng dạng với TrayMenuModel.actions khi cuốn đã nạp, "Chương trước" tắt.
QVariantList modelActions() {
    auto item = [](const QString &action, const QString &label, bool enabled) {
        return QVariant(QVariantMap{{QStringLiteral("action"), action}, {QStringLiteral("label"), label}, {QStringLiteral("enabled"), enabled}});
    };
    auto separator = [] { return QVariant(QVariantMap{{QStringLiteral("separator"), true}}); };
    return {item(QStringLiteral("open"), QStringLiteral("Mở ABook"), true), separator(),
            item(QStringLiteral("play"), QStringLiteral("Phát"), true), item(QStringLiteral("back"), QStringLiteral("Lùi 15 giây"), true),
            item(QStringLiteral("forward"), QStringLiteral("Tới 15 giây"), true), item(QStringLiteral("previous"), QStringLiteral("Chương trước"), false),
            item(QStringLiteral("next"), QStringLiteral("Chương sau"), true), separator(),
            item(QStringLiteral("mini"), QStringLiteral("Cửa sổ mini"), true), separator(),
            item(QStringLiteral("quit"), QStringLiteral("Thoát ABook"), true)};
}

struct Tray {
    FakeShell *shell = nullptr;
    std::unique_ptr<TrayIcon> icon;
    explicit Tray() {
        auto fake = std::make_unique<FakeShell>();
        shell = fake.get();
        icon = std::make_unique<TrayIcon>(std::move(fake));
    }
    HWND hwnd() const { return reinterpret_cast<HWND>(icon->window()); }
    void callback(unsigned event, int x = 0, int y = 0) const {
        SendMessageW(hwnd(), TrayIcon::kCallbackMessage, WPARAM(MAKELONG(short(x), short(y))), LPARAM(MAKELONG(event, 1)));
    }
};

// Đếm một thông điệp đăng ký riêng tới cửa sổ khay (subclass), để biết thông điệp PHÁT TÁN có tới không
UINT g_broadcastProbe = 0;
int g_broadcastSeen = 0;
WNDPROC g_trayProc = nullptr;
LRESULT CALLBACK countingProc(HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam) {
    if (message == g_broadcastProbe)
        ++g_broadcastSeen;
    return CallWindowProcW(g_trayProc, hwnd, message, wParam, lParam);
}

}  // namespace

class TrayTests : public QObject {
    Q_OBJECT
private slots:
    void tipIsCutAtTheShellLimitNeverInsideASurrogatePair() {
        QCOMPARE(TrayIcon::clip(QStringLiteral("ngắn"), TrayIcon::kTipLimit), QStringLiteral("ngắn"));
        QCOMPARE(TrayIcon::clip(QString(300, QLatin1Char('a')), TrayIcon::kTipLimit).size(), 127);
        const QString emoji = QString::fromUcs4(U"\U0001F600");
        QCOMPARE(emoji.size(), 2);
        // Cặp surrogate nằm gọn trong 127 đơn vị: giữ nguyên.
        const QString fits = QString(125, QLatin1Char('a')) + emoji + QStringLiteral("bbb");
        QCOMPARE(TrayIcon::clip(fits, 127), QString(125, QLatin1Char('a')) + emoji);
        // Cặp bị cắt đôi ở đơn vị thứ 127: bỏ cả cặp, không để nửa surrogate.
        const QString straddles = QString(126, QLatin1Char('a')) + emoji + QStringLiteral("bbb");
        QCOMPARE(TrayIcon::clip(straddles, 127), QString(126, QLatin1Char('a')));
        // Tiếng Việt có dấu nằm trong BMP: một đơn vị mỗi chữ.
        QCOMPARE(TrayIcon::clip(QString(200, QChar(0x1ED9)), 127).size(), 127);
    }

    void menuIsBuiltFromActions() {
        QStringList commands;
        const quintptr menu = TrayIcon::buildMenu(modelActions(), commands);
        QVERIFY(menu);
        const QList<MenuRow> rows = readMenu(menu);
        TrayIcon::destroyMenu(menu);
        QCOMPARE(rows.size(), 11);
        const QList<int> separators{1, 7, 9};
        for (int i = 0; i < rows.size(); ++i)
            QCOMPARE(rows[i].separator, separators.contains(i));
        QCOMPARE(commands, (QStringList{QStringLiteral("open"), QStringLiteral("play"), QStringLiteral("back"), QStringLiteral("forward"),
                                        QStringLiteral("previous"), QStringLiteral("next"), QStringLiteral("mini"), QStringLiteral("quit")}));
        // Mã lệnh = thứ tự mục không tính dòng tách, từ 1.
        unsigned expectedId = 1;
        for (const MenuRow &row : rows) {
            if (row.separator)
                continue;
            QCOMPARE(row.id, expectedId);
            ++expectedId;
        }
        // Chỉ "Chương trước" (mục thứ 5 trong 8 lệnh) bị làm xám.
        for (const MenuRow &row : rows) {
            if (!row.separator)   // Windows tự đánh dấu dòng tách là xám, không tính
                QCOMPARE(row.grayed, row.id == 5);
        }
        QCOMPARE(rows[0].text, QStringLiteral("Mở ABook"));
        QCOMPARE(rows[10].text, QStringLiteral("Thoát ABook"));
    }

    void ampersandIsLiteralAndMissingEnabledMeansGrayed() {
        QStringList commands;
        const QVariantList actions{QVariantMap{{QStringLiteral("action"), QStringLiteral("x")}, {QStringLiteral("label"), QStringLiteral("Tom & Jerry")}}};
        const quintptr menu = TrayIcon::buildMenu(actions, commands);
        const QList<MenuRow> rows = readMenu(menu);
        TrayIcon::destroyMenu(menu);
        QCOMPARE(rows.size(), 1);
        QCOMPARE(rows[0].text, QStringLiteral("Tom && Jerry"));   // Win32 hiển thị "&&" là một dấu "&"
        QVERIFY(rows[0].grayed);
    }

    void menuReadsActionsThatQmlDeliversAsJsValues() {
        QJSEngine engine;
        const QJSValue value = engine.evaluate(QStringLiteral("({action: 'play', label: 'Phát', enabled: true})"));
        QStringList commands;
        const quintptr menu = TrayIcon::buildMenu({QVariant::fromValue(value)}, commands);
        const QList<MenuRow> rows = readMenu(menu);
        TrayIcon::destroyMenu(menu);
        QCOMPARE(commands, QStringList{QStringLiteral("play")});
        QCOMPARE(rows.size(), 1);
        QVERIFY(!rows[0].grayed);
    }

    void choosingAnItemTriggersItsAction() {
        Tray tray;
        tray.icon->setActions(modelActions());
        tray.icon->setVisible(true);
        QSignalSpy triggered(tray.icon.get(), &TrayIcon::triggered);
        tray.shell->choice = 4;   // "Tới 15 giây"
        tray.callback(WM_CONTEXTMENU, 1200, 700);
        QCOMPARE(tray.shell->popups, 1);
        QCOMPARE(tray.shell->popupX, 1200);
        QCOMPARE(tray.shell->popupY, 700);
        QCOMPARE(tray.shell->shown.size(), 11);
        QCOMPARE(triggered.size(), 1);
        QCOMPARE(triggered.at(0).at(0).toString(), QStringLiteral("forward"));
        // Đóng menu mà không chọn: không phát gì.
        tray.shell->choice = 0;
        tray.callback(WM_CONTEXTMENU);
        QCOMPARE(tray.shell->popups, 2);
        QCOMPARE(triggered.size(), 1);
        // Mã ngoài dải (menu cũ) bị bỏ qua.
        tray.icon->selectCommand(99);
        QCOMPARE(triggered.size(), 1);
    }

    void menuIsRebuiltEachTimeItOpens() {
        Tray tray;
        tray.icon->setActions(modelActions());
        tray.icon->setVisible(true);
        tray.callback(WM_CONTEXTMENU);
        QCOMPARE(tray.shell->shown.size(), 11);
        QCOMPARE(tray.shell->shown[0].text, QStringLiteral("Mở ABook"));
        tray.icon->setActions({QVariantMap{{QStringLiteral("action"), QStringLiteral("quit")}, {QStringLiteral("label"), QStringLiteral("Thoát")}, {QStringLiteral("enabled"), true}}});
        tray.callback(WM_CONTEXTMENU);
        QCOMPARE(tray.shell->shown.size(), 1);
        QCOMPARE(tray.shell->shown[0].text, QStringLiteral("Thoát"));
    }

    void leftClickAndKeyboardActivateNothingElse() {
        Tray tray;
        tray.icon->setVisible(true);
        QSignalSpy activated(tray.icon.get(), &TrayIcon::activated);
        tray.callback(NIN_SELECT);
        tray.callback(NIN_KEYSELECT);
        QCOMPARE(activated.size(), 2);
        tray.callback(WM_MOUSEMOVE);
        tray.callback(NIN_BALLOONSHOW);
        QCOMPARE(activated.size(), 2);
        QCOMPARE(tray.shell->popups, 0);
    }

    void iconIsAddedChangedAndRemoved() {
        Tray tray;
        QSignalSpy availability(tray.icon.get(), &TrayIcon::availableChanged);
        tray.icon->setTooltip(QStringLiteral("ABook"));
        QCOMPARE(tray.shell->adds, 0);   // chưa visible: chưa có icon
        QVERIFY(!tray.icon->available());
        tray.icon->setVisible(true);
        QCOMPARE(tray.shell->adds, 1);
        QCOMPARE(tray.shell->lastTip, QStringLiteral("ABook"));
        QCOMPARE(tray.shell->lastWindow, tray.icon->window());
        QVERIFY(tray.icon->available());
        tray.icon->setTooltip(QStringLiteral("Cuốn sách · Chương 2"));
        QCOMPARE(tray.shell->modifies, 1);
        QCOMPARE(tray.shell->lastTip, QStringLiteral("Cuốn sách · Chương 2"));
        // Tooltip dài: cắt đúng giới hạn, và hai tooltip khác nhau chỉ ở phần bị cắt thì không gọi Windows lần nữa.
        tray.icon->setTooltip(QString(200, QLatin1Char('a')));
        QCOMPARE(tray.shell->modifies, 2);
        QCOMPARE(tray.shell->lastTip.size(), 127);
        tray.icon->setTooltip(QString(201, QLatin1Char('a')));
        QCOMPARE(tray.shell->modifies, 2);
        tray.icon->setVisible(false);
        QCOMPARE(tray.shell->removes, 1);
        QVERIFY(!tray.icon->available());
        tray.icon->setVisible(true);
        QCOMPARE(tray.shell->adds, 2);
        QCOMPARE(availability.size(), 3);
    }

    void iconDisappearsWhenTheAppQuitsAndWhenTheObjectIsDeleted() {
        {
            Tray tray;
            tray.icon->setVisible(true);
            QVERIFY(QMetaObject::invokeMethod(QCoreApplication::instance(), "aboutToQuit", Qt::DirectConnection));
            QCOMPARE(tray.shell->removes, 1);
            QVERIFY(!tray.icon->available());
        }
        // Hủy đối tượng phải gỡ icon; FakeShell chết cùng TrayIcon nên đếm bằng biến ngoài.
        static int removed = 0;
        struct Counting final : TrayShell {
            bool add(quintptr, const QString &) override { return true; }
            bool modify(quintptr, const QString &) override { return true; }
            void remove(quintptr) override { ++removed; }
            void balloon(quintptr, const QString &, const QString &) override {}
            unsigned popup(quintptr, quintptr, int, int) override { return 0; }
        };
        removed = 0;
        auto counted = std::make_unique<TrayIcon>(std::make_unique<Counting>());
        counted->setVisible(true);
        counted.reset();
        QCOMPARE(removed, 1);
        // Đã gỡ khi thoát thì hủy đối tượng không gỡ lần hai.
        removed = 0;
        counted = std::make_unique<TrayIcon>(std::make_unique<Counting>());
        counted->setVisible(true);
        QVERIFY(QMetaObject::invokeMethod(QCoreApplication::instance(), "aboutToQuit", Qt::DirectConnection));
        counted.reset();
        QCOMPARE(removed, 1);
    }

    void explorerRestartAddsTheIconAgain() {
        Tray tray;
        tray.icon->setVisible(true);
        QCOMPARE(tray.shell->adds, 1);
        SendMessageW(tray.hwnd(), RegisterWindowMessageW(L"TaskbarCreated"), 0, 0);
        QCOMPARE(tray.shell->adds, 2);
        QVERIFY(tray.icon->available());
        QCOMPARE(tray.shell->removes, 0);   // thanh tác vụ cũ đã mất icon, không gửi NIM_DELETE vào thanh mới
    }

    // Explorer báo dựng lại thanh tác vụ bằng PHÁT TÁN (HWND_BROADCAST), không gửi thẳng như hai test trên: cửa sổ HWND_MESSAGE
    // không bao giờ nhận (tools/tray_probe.cpp trên Explorer thật, 01-11). Thông điệp đăng ký riêng đi cùng đường, app khác không
    // biết nên bỏ qua; với cửa sổ của chính luồng này SendNotifyMessage gửi đồng bộ, không phải chờ. Cửa sổ vẫn không bao giờ hiện.
    void explorerBroadcastReachesTheTrayWindow() {
        Tray tray;
        const HWND hwnd = tray.hwnd();
        g_broadcastProbe = RegisterWindowMessageW(L"ABookTrayTests-Broadcast-5e2a");
        g_broadcastSeen = 0;
        g_trayProc = reinterpret_cast<WNDPROC>(SetWindowLongPtrW(hwnd, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(countingProc)));
        QVERIFY(SendNotifyMessageW(HWND_BROADCAST, g_broadcastProbe, 0, 0));
        SetWindowLongPtrW(hwnd, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(g_trayProc));
        QCOMPARE(g_broadcastSeen, 1);
        QVERIFY(!IsWindowVisible(hwnd));
        QVERIFY(GetWindowLongPtrW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW);   // không lên thanh tác vụ / Alt+Tab
    }

    void iconAddedLaterWhenExplorerWasNotUpAtStart() {
        Tray tray;
        tray.shell->addResult = false;
        tray.icon->setVisible(true);
        QVERIFY(!tray.icon->available());   // app biết khay không dùng được: đóng cửa sổ là thoát
        tray.callback(WM_CONTEXTMENU);
        QCOMPARE(tray.shell->popups, 0);
        tray.shell->addResult = true;
        SendMessageW(tray.hwnd(), RegisterWindowMessageW(L"TaskbarCreated"), 0, 0);
        QVERIFY(tray.icon->available());
        QCOMPARE(tray.shell->adds, 2);
    }

    void balloonOnlyWhenTheIconIsThere() {
        Tray tray;
        tray.icon->showMessage(QStringLiteral("ABook"), QStringLiteral("x"));
        QCOMPARE(tray.shell->balloons, 0);
        tray.icon->setVisible(true);
        tray.icon->showMessage(QStringLiteral("ABook"), QStringLiteral("ABook vẫn chạy ở khay"));
        QCOMPARE(tray.shell->balloons, 1);
        QCOMPARE(tray.shell->lastBalloonText, QStringLiteral("ABook vẫn chạy ở khay"));
    }

    void darkMenuSwitchesAreOptionalAndSafe() {
        Tray tray;
        // Có hay không tùy bản Windows; gọi hai lần không được hỏng và cho cùng kết quả.
        const bool first = TrayIcon::allowDarkMenus(tray.icon->window());
        QCOMPARE(TrayIcon::allowDarkMenus(tray.icon->window()), first);
    }
};

QTEST_GUILESS_MAIN(TrayTests)
#include "test_tray.moc"

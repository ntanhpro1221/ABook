// WindowChrome (src/windowchrome.cpp): lớp gói QWindowKit cho dải tiêu đề tự vẽ. Chạy trên nền tảng offscreen, cửa sổ thật không hiện và
// con trỏ thật không bị động tới (QCursor::setPos của offscreen chỉ đổi con trỏ ảo). Khoá hợp đồng với qml/Main.qml + qml/TitleBar.qml:
//   - dải tiêu đề là vùng kéo cửa sổ (agent->titleBar) và ba nút là "nút hệ thống" (Minimize / Maximize / Close) để Windows biết vùng
//     của chúng (Snap Layouts hiện khi rê vào nút phóng to);
//   - mục khác nằm trong dải mà vẫn phải bấm được (nút thu / mở thanh bên) khai bằng keepClickable() và chỉ những mục đó;
//   - cửa sổ mini bỏ dải kéo (tự kéo ở vùng trống), trở lại bình thường thì dải kéo về;
//   - cursorInside() đo con trỏ thật theo toạ độ màn hình, không dựa vào tin rê chuột của Qt.
#include "windowchrome.h"

#include <QWKQuick/quickwindowagent.h>

#include <QCursor>
#include <QGuiApplication>
#include <QQuickItem>
#include <QQuickWindow>
#include <QtTest>

class WindowChromeTests : public QObject {
    Q_OBJECT
    struct Scene {
        QQuickWindow window;
        QQuickItem *titleBar = nullptr, *minimize = nullptr, *maximize = nullptr, *close = nullptr, *toggle = nullptr, *other = nullptr;
        Scene() {
            window.resize(1280, 800);
            auto item = [this](QQuickItem *parent, qreal x, qreal y, qreal w, qreal h) {
                auto *created = new QQuickItem(parent ? parent : window.contentItem());
                created->setPosition({x, y});
                created->setSize({w, h});
                return created;
            };
            titleBar = item(nullptr, 0, 0, 1280, 40);
            minimize = item(titleBar, 1280 - 3 * 46, 0, 46, 40);
            maximize = item(titleBar, 1280 - 2 * 46, 0, 46, 40);
            close = item(titleBar, 1280 - 46, 0, 46, 40);
            toggle = item(titleBar, 12, 4, 32, 32);
            other = item(titleBar, 400, 4, 32, 32);
        }
    };
    static QWK::QuickWindowAgent *agentOf(WindowChrome &chrome) {
        auto *agent = chrome.findChild<QWK::QuickWindowAgent *>();
        return agent;
    }

private slots:
    void initTestCase() {
        // Chạy trên nền tảng thật thì cửa sổ test hiện ra màn hình chủ máy: dừng ngay.
        QCOMPARE(QGuiApplication::platformName(), QStringLiteral("offscreen"));
    }

    void attachMakesTheStripTheDragAreaAndRegistersTheThreeSystemButtons() {
        Scene scene;
        WindowChrome chrome;
        auto *agent = agentOf(chrome);
        QVERIFY(agent);
        QVERIFY(chrome.attach(&scene.window, scene.titleBar, scene.minimize, scene.maximize, scene.close));
        QCOMPARE(agent->titleBar(), scene.titleBar);
        QCOMPARE(agent->systemButton(QWK::WindowAgentBase::Minimize), scene.minimize);
        QCOMPARE(agent->systemButton(QWK::WindowAgentBase::Maximize), scene.maximize);
        QCOMPARE(agent->systemButton(QWK::WindowAgentBase::Close), scene.close);
        QVERIFY(!agent->isHitTestVisible(scene.other));      // chưa khai thì là vùng kéo
    }

    void onlyDeclaredItemsStayClickableInsideTheStrip() {
        Scene scene;
        WindowChrome chrome;
        QVERIFY(chrome.attach(&scene.window, scene.titleBar, scene.minimize, scene.maximize, scene.close));
        auto *agent = agentOf(chrome);
        QVERIFY(!agent->isHitTestVisible(scene.toggle));
        chrome.keepClickable(scene.toggle);
        QVERIFY(agent->isHitTestVisible(scene.toggle));
        QVERIFY(!agent->isHitTestVisible(scene.other));
        QVERIFY(!agent->isHitTestVisible(scene.titleBar));   // cả dải không bao giờ thành vùng bấm
    }

    void miniWindowDropsTheDragStripAndNormalWindowGetsItBack() {
        Scene scene;
        WindowChrome chrome;
        QVERIFY(chrome.attach(&scene.window, scene.titleBar, scene.minimize, scene.maximize, scene.close));
        auto *agent = agentOf(chrome);
        chrome.setMini(true);
        QCOMPARE(agent->titleBar(), static_cast<QQuickItem *>(nullptr));
        chrome.setMini(false);
        QCOMPARE(agent->titleBar(), scene.titleBar);
        chrome.setMini(true);
        chrome.setMini(true);                                // gọi lặp không hỏng
        QCOMPARE(agent->titleBar(), static_cast<QQuickItem *>(nullptr));
        chrome.setMini(false);
        QCOMPARE(agent->titleBar(), scene.titleBar);
    }

    void cursorInsideReadsTheRealCursorInScreenCoordinates() {
        Scene scene;
        scene.window.setPosition(100, 50);
        scene.window.show();
        WindowChrome chrome;
        QVERIFY(chrome.attach(&scene.window, scene.titleBar, scene.minimize, scene.maximize, scene.close));
        const QPointF origin = scene.maximize->mapToGlobal(QPointF(0, 0));
        QCursor::setPos(QPoint(qRound(origin.x()) + 23, qRound(origin.y()) + 20));
        QVERIFY(chrome.cursorInside(scene.maximize));
        QVERIFY(!chrome.cursorInside(scene.minimize));
        QVERIFY(!chrome.cursorInside(scene.close));
        QCursor::setPos(QPoint(qRound(origin.x()) - 1, qRound(origin.y()) + 20));      // sát mép trái, ngoài một điểm ảnh
        QVERIFY(!chrome.cursorInside(scene.maximize));
        QCursor::setPos(QPoint(qRound(origin.x()) + 45, qRound(origin.y()) + 39));      // góc dưới phải còn trong nút 46 x 40
        QVERIFY(chrome.cursorInside(scene.maximize));
        QCursor::setPos(QPoint(qRound(origin.x()) + 47, qRound(origin.y()) + 20));      // QRectF::contains tính cả mép phải: ngoài nút từ điểm 47
        QVERIFY(!chrome.cursorInside(scene.maximize));
    }

    void cursorInsideIsFalseWithoutAnItemOrAWindow() {
        WindowChrome chrome;
        QVERIFY(!chrome.cursorInside(nullptr));
        QQuickItem lonely;
        lonely.setSize({46, 40});
        QVERIFY(!chrome.cursorInside(&lonely));
    }
};

int main(int argc, char **argv) {
    qputenv("QT_QPA_PLATFORM", "offscreen");
    QGuiApplication app(argc, argv);
    WindowChromeTests tests;
    return QTest::qExec(&tests, argc, argv);
}
#include "test_windowchrome.moc"

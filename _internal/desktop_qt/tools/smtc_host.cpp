// Cửa sổ Win32 chỉ tạo, không bao giờ hiện; thử SMTC thật mà không mở thiết bị âm thanh.
#include <windows.h>
#include "mediacontrols.h"
#include "player.h"
#include "fakes.h"
#include <QCoreApplication>
#include <QFile>
#include <QJsonDocument>
#include <QTemporaryDir>
#include <QThread>
#include <QTimer>

int main(int argc, char **argv) {
    MediaControls::setAppId();
    QCoreApplication app(argc, argv);
    const QString path = qEnvironmentVariable("ABOOK_SMTC_HOST_RESULT");
    const wchar_t *name = L"ABookSmtcHiddenProbe";
    WNDCLASSW wc{}; wc.lpfnWndProc = DefWindowProcW; wc.hInstance = GetModuleHandleW(nullptr); wc.lpszClassName = name;
    RegisterClassW(&wc);
    HWND hwnd = CreateWindowExW(WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW, name, L"ABook SMTC hidden test", WS_OVERLAPPED,
                                -10000, -10000, 1, 1, nullptr, nullptr, wc.hInstance, nullptr);
    if (!hwnd) return 2;
    int result = 1;
    {
        QTemporaryDir dir;
        FakeOut out; FakeNet net;
        Player player(&out, &net, dir.filePath(QStringLiteral("outbox.json")), nullptr);
        MediaControls media(&player, &out);
        if (!media.attachWindow(quintptr(hwnd))) { DestroyWindow(hwnd); return 3; }
        net.books[QStringLiteral("smtc")] = makeBook(QStringLiteral("smtc"));
        player.open(QStringLiteral("smtc"), 1, 0, true);
        auto write = [&](const QString &phase) {
            QFile file(path);
            if (file.open(QIODevice::WriteOnly)) file.write(QJsonDocument(QJsonObject{
                {QStringLiteral("phase"), phase}, {QStringLiteral("playing"), player.playing()},
                {QStringLiteral("ui_thread"), QThread::currentThread() == player.thread()},
                {QStringLiteral("chapter"), player.chapterId()}, {QStringLiteral("position"), player.position()},
                {QStringLiteral("visible"), bool(IsWindowVisible(hwnd))},
                {QStringLiteral("foreground"), GetForegroundWindow() == hwnd}}).toJson());
        };
        write(QStringLiteral("ready"));
        QObject::connect(&media, &MediaControls::commandExecuted, &app, [&](MediaCommand command) {
            write(QStringLiteral("command_%1").arg(int(command)));
            if (command == MediaCommand::Pause) {
                write(QStringLiteral("pause_reached_player"));
                result = player.playing() || IsWindowVisible(hwnd) || GetForegroundWindow() == hwnd ? 4 : 0;
                QTimer::singleShot(1500, &app, &QCoreApplication::quit);
            }
        });
        QTimer::singleShot(30000, &app, &QCoreApplication::quit);
        app.exec();
    }
    DestroyWindow(hwnd);
    return result;
}

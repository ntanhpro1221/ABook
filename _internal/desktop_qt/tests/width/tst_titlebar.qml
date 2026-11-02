import QtQuick
import QtTest
import ABook
import "LayoutAudit.js" as Audit

// Dải tiêu đề Windows tự vẽ (qml/TitleBar.qml + CaptionButton.qml + CaptionGlyph.qml) trong cửa sổ thật (qml/Main.qml, WindowChrome giả có nhớ lời gọi).
// Khoá từng chi tiết của thiết kế: dải cao Theme.buttonHeight (40), không nền riêng, ba nút rộng 46 sát nhau ở mép phải, nét tự vẽ ở giữa nút,
// nút thu / mở thanh bên nằm lọt trong dải, nền rê chuột / nhấn của nút (Đóng đỏ chuẩn Windows, còn lại là token của màu chữ).
// Phần C++ của hợp đồng (vùng kéo, vùng bấm) nằm ở tests/test_windowchrome.cpp.
TestCase {
    id: test
    name: "TitleBar"
    when: windowShown
    property var win: null
    property var chrome: null
    property var bar: null
    property var minimize: null
    property var maximize: null
    property var close: null
    property var toggle: null

    function initTestCase() {
        DesktopApi.reset()
        Platform.reset()
        Api.bind(DesktopApi, Theme)
        Api.preferences = {theme: "system"}
        Api.loaded = true
        Theme.reduceMotion = false
        const component = Qt.createComponent(Qt.resolvedUrl("../../qml/Main.qml"))
        compare(component.status, Component.Ready, component.errorString())
        win = component.createObject(null)
        verify(win !== null)
        tryVerify(function() { return win.visible })
        win.requestActivate()
        tryVerify(function() { return win.active && win.activeFocusItem !== null })
        waitForRendering(win.contentItem)
        chrome = findChrome()
        verify(chrome !== null && chrome.attached !== null, "Main.qml phải gắn WindowChrome")
        compare(chrome.attached.window, win)
        bar = chrome.attached.titleBar
        minimize = chrome.attached.minimize
        maximize = chrome.attached.maximize
        close = chrome.attached.close
        compare(chrome.kept.length, 1, "đúng một mục khác trong dải được giữ bấm được")
        toggle = chrome.kept[0]
    }
    function cleanupTestCase() {
        Nav.layers = []
        win.destroy()
        Nav.stack = null
        Theme.reduceMotion = false
    }
    // WindowChrome là con không có thuộc tính nào trỏ tới: tìm trong dữ liệu của cửa sổ, nhận ra bằng hàm attach của bản giả.
    function findChrome() {
        for (let i = 0; i < win.data.length; ++i)
            if (typeof win.data[i].attach === "function" && "attached" in win.data[i]) return win.data[i]
        return null
    }
    function box(item) { return Audit.box(item, win.contentItem) }
    function near(actual, expected, tolerance, label) { verify(Math.abs(actual - expected) <= tolerance, label + ": " + actual + " != " + expected) }
    function rgb(color) { const c = Qt.color(color); return [Math.round(c.r * 255), Math.round(c.g * 255), Math.round(c.b * 255)] }
    function mix(back, front, alpha) {
        const a = rgb(back), b = rgb(front)
        return [0, 1, 2].map(function(i) { return Math.round(a[i] * (1 - alpha) + b[i] * alpha) })
    }
    function pixel(image, x, y) { return [image.red(x, y), image.green(x, y), image.blue(x, y)] }
    function sameColor(actual, expected, label, tolerance) {
        for (let i = 0; i < 3; ++i) verify(Math.abs(actual[i] - expected[i]) <= (tolerance === undefined ? 2 : tolerance), label + ": got " + actual + ", want " + expected)
    }
    // Mép trên-trái của nút (xa nét chữ 10 x 10 ở giữa): chỉ thấy nền rê chuột / nhấn.
    function edgePixel(button) {
        const b = box(button)
        return pixel(grabImage(win.contentItem), Math.round(b.x) + 3, Math.round(b.y) + 3)
    }
    // Chờ nền hết chuyển (hai ảnh cách 100 ms giống nhau) rồi mới đo: đo giữa chừng sẽ bắt gặp mọi giá trị trung gian.
    function settledEdge(button) {
        let previous = edgePixel(button)
        for (let i = 0; i < 30; ++i) {
            wait(100)   // fixed: samples timing - hai ảnh cách 100 ms giống nhau mới coi là nền đã dừng chuyển
            const now = edgePixel(button)
            if (now.join() === previous.join()) return now
            previous = now
        }
        verify(false, "nền nút không dừng chuyển")
    }
    function park() { mouseMove(win.contentItem, 400, 300) }
    function glyphs(button) {
        const found = []
        for (const child of button.children) for (const inner of child.children || [])
            if (inner.kind !== undefined && inner.paths !== undefined) found.push(inner)
        return found
    }
    function descendants(item, out) {
        out = out || []
        for (const child of item.children || []) { out.push(child); descendants(child, out) }
        return out
    }

    function test_1_stripFillsTopOfWindowAndIsFortyHigh() {
        compare(Theme.buttonHeight, 40)
        compare(bar.height, 40)
        compare(bar.height, Theme.buttonHeight)
        const b = box(bar)
        compare(b.x, 0)
        compare(b.y, 0)
        compare(b.w, win.contentItem.width)
        let top = toggle
        while (top.parent !== win.contentItem) top = top.parent
        verify(bar.z > top.z, "dải trên cả thanh bên mở tạm (z " + bar.z + " > " + top.z + ")")
    }
    function test_2_threeButtonsAre46WideFlushRightWithNoGap() {
        const buttons = [minimize, maximize, close]
        for (const button of buttons) {
            compare(button.width, 46)
            compare(button.height, 40)
            compare(box(button).y, 0)
        }
        const boxes = buttons.map(box)
        compare(boxes[2].x + boxes[2].w, win.contentItem.width, "Đóng sát mép phải")
        compare(boxes[1].x + boxes[1].w, boxes[2].x, "Phóng to chạm Đóng, không khe")
        compare(boxes[0].x + boxes[0].w, boxes[1].x, "Thu nhỏ chạm Phóng to, không khe")
        compare(boxes[2].x + boxes[2].w - boxes[0].x, 3 * 46)
    }
    function test_3_glyphsAreDrawnCentredAndNotFontsOrImages() {
        const expected = [[minimize, ["minimize"]], [maximize, ["maximize", "restore"]], [close, ["close"]]]
        for (const row of expected) {
            const button = row[0], found = glyphs(button)
            compare(found.map(function(g) { return g.kind }).join(), row[1].join(), "kiểu nét trong nút")
            for (const glyph of found) {
                compare(glyph.width, 10)
                compare(glyph.height, 10)
                const centre = glyph.mapToItem(button, glyph.width / 2, glyph.height / 2)       // tâm, vì nét ẩn đang thu về 0,8
                near(centre.x, button.width / 2, 0.01, "nét ở giữa ngang")
                near(centre.y, button.height / 2, 0.01, "nét ở giữa dọc")
            }
            for (const item of descendants(button)) {
                const kind = String(item)
                verify(kind.indexOf("QQuickText") !== 0 && kind.indexOf("QQuickImage") !== 0 && kind.indexOf("QQuickAnimatedImage") !== 0,
                       "nút cửa sổ không dùng chữ / ảnh cho nét: " + kind)
            }
            verify(descendants(button).some(function(item) { return String(item).indexOf("QQuickShape") === 0 }), "nét là Shape vẽ tay")
        }
        // Nét thật sự có mực: gạch Thu nhỏ dày 1 điểm ảnh, rộng đúng 10 điểm ảnh, nằm giữa nút; hai bên không có gì.
        park()
        const image = grabImage(win.contentItem), b = box(minimize), bg = rgb(Theme.bg)[0], ink = rgb(Theme.text)[0]
        const inked = []
        let thickness = 0
        for (let x = 10; x < 36; ++x) {
            let coverage = 0
            for (let y = 14; y < 27; ++y) coverage += (bg - image.red(Math.round(b.x) + x, Math.round(b.y) + y)) / (bg - ink)
            if (coverage > 0.3) inked.push(x)
            thickness = Math.max(thickness, coverage)
        }
        const rows = []
        for (let y = 10; y < 32; ++y) {
            let coverage = 0
            for (let x = 18; x < 28; ++x) coverage += (bg - image.red(Math.round(b.x) + x, Math.round(b.y) + y)) / (bg - ink)
            if (coverage / 10 > 0.3) rows.push(y)
        }
        compare(rows.join(), "20", "hàng có mực của gạch Thu nhỏ (giữa dải 40)")
        compare(inked.join(), [18, 19, 20, 21, 22, 23, 24, 25, 26, 27].join(), "cột có mực của gạch Thu nhỏ")
        verify(thickness > 0.5 && thickness < 1.2, "gạch mảnh, 1 điểm ảnh (đo " + thickness + ")")   // bộ vẽ Shape cho ~0,67 độ phủ ở nét 1 pt
        // Phóng to <-> khôi phục: chỉ một nét hiện cùng lúc.
        const pair = glyphs(maximize)
        compare(pair[0].shown, win.visibility !== Window.Maximized)
        compare(pair[1].shown, win.visibility === Window.Maximized)
    }
    function test_4_noOwnBackgroundSameColourAsTheArea() {
        park()
        tryCompare(maximize, "hovered", false)
        const image = grabImage(win.contentItem)
        const want = rgb(Theme.bg)
        // Trên thanh bên, trên nội dung và ngay dưới dải: cùng một màu nền cửa sổ, không có dải nào khác màu.
        for (const x of [60, 320, 700, 1000]) {
            sameColor(pixel(image, x, 8), want, "dải ở x=" + x)
            sameColor(pixel(image, x, 32), want, "dải ở x=" + x + " y=32")
        }
        for (const item of descendants(bar)) {
            // Chỉ có nền rê chuột của ba nút (trong suốt lúc nghỉ); không Rectangle nào của dải mờ đục.
            if (String(item).indexOf("QQuickRectangle") === 0 && item.visible) verify(item.opacity === 0 || item.parent.width === 46, "nền riêng trong dải: " + item)
        }
        verify(bar.children.every(function(child) { return String(child).indexOf("QQuickRectangle") !== 0 }), "dải không có Rectangle trực tiếp")
    }
    function test_5_sidebarToggleSitsInsideTheStripAndClearOfTheButtons() {
        const t = box(toggle)
        verify(t.y >= 0 && t.y + t.h <= bar.height, "nút thanh bên lọt trong dải 40: y=" + t.y + " h=" + t.h)
        near(t.y + t.h / 2, bar.height / 2, 0.01, "nút thanh bên giữa dải theo chiều dọc")
        compare(t.h, Theme.hit)
        compare(t.x, 12)
        verify(t.x + t.w < box(minimize).x, "không đè lên ba nút cửa sổ")
        compare(toggle.tip.indexOf("(Ctrl+B)") > 0, true)
        // Bấm thật vào giữa nút phải tới nút (dải trong suốt không chặn), không tới ba nút cửa sổ.
        const icon = toggle.icon
        mouseClick(toggle)
        tryVerify(function() { return toggle.icon !== icon })
        mouseClick(toggle)
        tryCompare(toggle, "icon", icon)
    }
    function test_6_closeButtonHoverAndPressUseTheWindowsRedAndWhiteInk() {
        park()
        tryCompare(close, "hovered", false)
        sameColor(settledEdge(close), rgb(Theme.bg), "Đóng lúc nghỉ không có nền", 1)
        mouseMove(close, 23, 20)
        tryCompare(close, "hovered", true)
        sameColor(settledEdge(close), [0xc4, 0x2b, 0x1c], "Đóng khi rê chuột", 0)
        compare(close.ink.toString(), "#ffffff")
        const spy = createTemporaryObject(spyComponent, test, {target: close, signalName: "clicked"})
        mousePress(close, 23, 20)
        tryCompare(close, "pressed", true)
        sameColor(settledEdge(close), [0xa8, 0x24, 0x19], "Đóng khi nhấn", 0)
        mouseMove(close, -80, 20)             // kéo ra ngoài rồi nhả: không tính là bấm Đóng
        mouseRelease(close, -80, 20)
        compare(spy.count, 0)
        park()
        tryCompare(close, "hovered", false)
        sameColor(settledEdge(close), rgb(Theme.bg), "Đóng trả lại nền", 1)
    }
    function test_7_otherButtonsUseTheTextTokenAt6And10Percent() {
        for (const button of [minimize, maximize]) {
            park()
            tryCompare(button, "hovered", false)
            sameColor(settledEdge(button), rgb(Theme.bg), "nút nghỉ", 1)
            mouseMove(button, 23, 20)
            tryCompare(button, "hovered", true)
            sameColor(settledEdge(button), mix(Theme.bg, Theme.text, 0.06), "rê chuột = 6% màu chữ", 1)
            compare(button.ink.toString(), Qt.color(Theme.text).toString(), "chữ không đổi màu khi rê chuột")
            const spy = createTemporaryObject(spyComponent, test, {target: button, signalName: "clicked"})
            mousePress(button, 23, 20)
            tryCompare(button, "pressed", true)
            sameColor(settledEdge(button), mix(Theme.bg, Theme.text, 0.10), "nhấn = 10% màu chữ", 1)
            mouseMove(button, -80, 20)
            mouseRelease(button, -80, 20)
            compare(spy.count, 0)
        }
        park()
    }
    function test_8_inactiveWindowFadesTheInkAndDangerStaysWhiteOnHover() {
        const component = Qt.createComponent(Qt.resolvedUrl("../../qml/CaptionButton.qml"))
        compare(component.status, Component.Ready, component.errorString())
        const plain = createTemporaryObject(component, test, {active: false})
        compare(plain.ink.toString(), Qt.color(Theme.faint).toString())
        plain.active = true
        compare(plain.ink.toString(), Qt.color(Theme.text).toString())
        const danger = createTemporaryObject(component, test, {active: false, danger: true})
        compare(danger.ink.toString(), Qt.color(Theme.faint).toString())
        danger.latched = true                 // Windows đang giữ rê chuột (Snap Layouts)
        compare(danger.hovered, true)
        compare(danger.ink.toString(), "#ffffff")
        compare(danger.implicitWidth, 46)
        compare(danger.implicitHeight, Theme.buttonHeight)
    }
    function test_9_maximizedSwapsTheMaximizeGlyphForRestore() {
        win.showMaximized()
        tryCompare(win, "visibility", Window.Maximized)
        const pair = glyphs(maximize)
        tryCompare(pair[1], "shown", true)
        compare(pair[0].shown, false)
        compare(box(close).x + 46, win.contentItem.width, "Đóng vẫn sát mép phải khi phóng to")
        win.showNormal()
        tryCompare(win, "visibility", Window.Windowed)
        tryCompare(pair[0], "shown", true)
        compare(pair[1].shown, false)
    }

    Component { id: spyComponent; SignalSpy {} }
}

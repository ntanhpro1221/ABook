import QtQuick
import QtTest
import "VisualReady.js" as VisualReady
import ABook

// Luật chủ sách 30-10 "số tự đổi không chuyển động": giá trị tự đổi đổi tại chỗ (không trượt, mờ, co giãn), chữ số đều độ rộng.
// Máy dò tĩnh là tools/check_ticks.py; ở đây đo trên font đóng kèm và bề mặt thật của Đang phát.
Item {
    id: host
    width: 1280; height: 900
    Component { id: nowComponent; NowPlaying {} }
    Component { id: clockComponent; ClockLabel { font.pixelSize: 13 } }
    Component { id: plainComponent; Text { font.pixelSize: 13 } }
    Component { id: barComponent; StudioBar { width: 200 } }
    TestCase {
        name: "Ticks"
        when: windowShown
        function ready() { VisualReady.render(this, host.Window.window, host, qtVisualReady) }
        function init() {
            Theme.reduceMotion = false; Nav.layers = []; Nav.uiVisible = true
            Platform.reset(); DesktopApi.reset(); Api.bind(DesktopApi, Theme)
            Api.preferences = {sleepFadeSeconds: 30, sleepExtendMinutes: 10}
            Player.configure(Api.preferences); WidthNet.resetBooks(); Player.open("width", 1, 0, true); Player.pause(); Player.seek(0); Player.setSleep("off")
        }
        function cleanup() {
            Player.close(); Player.setSleep("off"); Nav.layers = []; Nav.uiVisible = true
            Player.open("width", 1, 0, false)
        }
        function open() {
            const now = createTemporaryObject(nowComponent, host, {width: 1000, height: 900})
            now.show(); tryCompare(now, "open", true); tryCompare(now, "p", 1); ready()
            return now
        }

        function test_bundled_font_has_real_tabular_digits_data() {
            return [{tag: "regular", weight: Font.Normal}, {tag: "medium", weight: Font.Medium}, {tag: "bold", weight: Font.Bold}]
        }
        function test_bundled_font_has_real_tabular_digits(data) {
            const clock = createTemporaryObject(clockComponent, host), plain = createTemporaryObject(plainComponent, host)
            clock.font.weight = data.weight; plain.font.weight = data.weight
            const widths = function(text) { clock.text = text; plain.text = text; return [clock.implicitWidth, plain.implicitWidth] }
            const narrow = widths("1:11:11"), wide = widths("8:48:48")
            compare(narrow[0], wide[0])                 // tnum có thật trong Be Vietnam Pro đóng kèm (mobile/android/scripts/add_tabular_digits.py)
            verify(wide[1] - narrow[1] > 4)             // chữ số mặc định vẫn rộng tự nhiên: phép so trên có nghĩa
        }

        function test_now_playing_time_changes_in_place() {
            const now = open()
            const elapsed = findChild(now, "nowElapsed"), remaining = findChild(now, "nowRemaining")
            Player.resume(); WidthNet.advance(0.5); ready()
            const left = elapsed.mapToItem(now, 0, 0).x, right = remaining.mapToItem(now, remaining.width, 0).x
            const width = elapsed.width, seen = {}
            for (let second = 0; second < 12; ++second) {
                const before = elapsed.text, beforeLeft = remaining.text
                WidthNet.advance(1)
                // Giá trị mới có ngay trong nhịp này, không qua chuyển động nào
                verify(elapsed.text !== before); verify(remaining.text !== beforeLeft)
                compare(elapsed.opacity, 1); compare(remaining.opacity, 1)
                compare(elapsed.mapToItem(now, 0, 0).x, left)
                compare(remaining.mapToItem(now, remaining.width, 0).x, right)
                compare(elapsed.width, width)            // 0:01 ... 0:12: "1" và "8" cùng độ rộng
                seen[elapsed.text] = true
            }
            verify(Object.keys(seen).some(text => text.indexOf("8") >= 0) && Object.keys(seen).some(text => text.indexOf("1") >= 0))
        }

        function test_progress_fill_jumps_to_the_value() {
            // Phần tô của thanh tiến độ tự chạy (tải / xuất / phân tích) vẽ thẳng theo giá trị, như điện thoại native: không trượt
            const bar = createTemporaryObject(barComponent, host, {value: 0.3}), fill = findChild(bar, "studioBarFill")
            ready(); compare(fill.width, 60)
            bar.value = 0.7
            compare(fill.width, 140)
        }

        function test_sleep_countdown_chip_keeps_its_place() {
            const now = open()
            const chip = findChild(now, "nowSleep"), flow = chip.parent
            Player.resume(); Player.setSleep("minutes", 1); ready()
            compare(chip.text, "1 phút")
            const width = chip.width, places = []
            for (let i = 0; i < flow.children.length; ++i) places.push(flow.children[i].x)
            const texts = [chip.text]
            // "1 phút" -> "55 giây" (đổi đơn vị) -> ... -> "5 giây" (còn một chữ số): nút không co giãn, các nút bên cạnh không trượt.
            // ready() mỗi nhịp: Row / Flow chỉ xếp lại lúc polish, đo trước khung hình thì bề rộng cũ luôn "đứng yên".
            for (const step of [0.5].concat(Array(11).fill(5))) {
                WidthNet.advance(step); ready()
                texts.push(chip.text)
                compare(chip.width, width)
                for (let i = 0; i < flow.children.length; ++i) compare(flow.children[i].x, places[i])
            }
            verify(texts.some(text => /^\d\d giây$/.test(text)) && texts.some(text => /^\d giây$/.test(text)), texts.join(", "))
        }
    }
}

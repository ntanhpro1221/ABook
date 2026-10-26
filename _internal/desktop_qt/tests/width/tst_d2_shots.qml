import QtQuick
import QtTest
import ABook

// Ảnh offscreen của các màn D2 (Cài đặt, Thêm sách, Sửa sách) sáng + tối, ghi ra build/d2shots/<tên>.png để người làm mở ra xem.
// Không kiểm điểm ảnh - chỉ chụp; dữ liệu giả đặt vào DesktopApi giả (tests/qml/stub/ABook/DesktopApi.qml). Khung của Cài đặt; ảnh từng
// nhóm / hộp thoại nằm ở bộ thử của nhóm ấy (tst_d2_<phần>.qml) với cùng hàm shot().
Item {
    id: host
    width: 1440
    height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: settingsFactory; SettingsScreen {} }

    TestCase {
        id: test
        name: "D2Shots"
        when: windowShown

        function init() {
            DesktopApi.reset()
            Api.bind(DesktopApi, Theme)
            Api.preferences = {theme: "system", autoRewind: true, autoMusic: true, safetyStopHours: 2, sleepSchedule: {from: "22:00", to: "06:00", minutes: 30}}
            Api.info = {version: "0.4.40", studio: {installed: true}}
            DesktopApi.responses = {"/api/sync": {status: 200, data: {enabled: true, devices: [{}, {}]}}}
            Api.loaded = true
            Api.saving = false
            Nav.layers = []
            Theme.reduceMotion = true
        }
        function cleanup() { Theme.mode = "auto"; Theme.reduceMotion = false; Nav.layers = [] }

        // Chụp `item` (mặc định cả khung thử) ra build/d2shots/<name>_<light|dark>.png
        function shot(name, item) {
            const target = item || host
            waitForRendering(target)
            wait(400)
            const img = grabImage(target)
            const path = Qt.resolvedUrl("../../build/d2shots/" + name + "_" + (Theme.dark ? "dark" : "light") + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            img.save(path)
        }
        function both(make) {
            for (const mode of ["light", "dark"]) { Theme.mode = mode; make() }
        }

        function test_settingsGroups() {
            both(function() {
                for (const group of ["voice", "listen", "sleep", "look", "devices", "studio", "advanced"]) {
                    const page = createTemporaryObject(settingsFactory, host, {width: host.width, height: host.height, active: group})
                    shot("settings_" + group)
                    page.destroy()
                }
            })
        }
        function test_settingsCompact() {
            both(function() {
                const page = createTemporaryObject(settingsFactory, host, {width: 760, height: host.height})
                shot("settings_compact_list")
                page.active = "sleep"
                shot("settings_compact_sleep")
                page.destroy()
            })
        }
    }
}

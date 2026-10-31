import QtQuick
import QtTest
import "ShotTruth.js" as ShotTruth
import ABook

// Kiểm lực máy dò ảnh nói thật (ShotTruth.js): thanh bên tô "Thư viện" cạnh màn Cài đặt phải bị bắt, tô "Cài đặt" thì sạch;
// ảnh tối trong khi tuỳ chọn còn "Sáng" phải bị bắt, đổi theme qua tuỳ chọn (Api.update, như ô Màu ở Giao diện) thì sạch.
Item {
    id: host
    width: 1280; height: 800
    Component {
        id: scene
        Item {
            property alias sidebar: bar
            anchors.fill: parent
            Sidebar { id: bar; width: 232; height: parent.height; onSectionRequested: index => currentSection = index }
            SettingsScreen { x: 232; width: parent.width - 232; height: parent.height; active: "look" }
        }
    }
    // objectName leakProbe: GlyphAudit (bộ quét chữ rò toàn cục) bỏ qua chữ cố ý rò của phép thử lực này
    Component { id: leakText; Text { objectName: "leakProbe"; x: 300; y: 20 } }
    Component { id: leakField; TextInput { x: 300; y: 60; width: 100; height: 20 } }
    TestCase {
        name: "ShotTruth"
        when: windowShown
        function init() {
            Platform.reset(); DesktopApi.reset(); Api.bind(DesktopApi, Theme)
            Api.loaded = true; Api.preferences = {theme: "light"}; Api.info = {version: "fixture", studio: {installed: true}}
            Nav.layers = []
        }
        function cleanup() { Theme.mode = "auto" }
        function rules(found) { return found.map(f => f.rule).sort().join() }
        function test_sidebarMustMarkTheScreenShown() {
            const page = createTemporaryObject(scene, host)
            waitForRendering(page)
            compare(rules(ShotTruth.problems(host)), "sidebar")
            page.sidebar.choose(2)
            compare(rules(ShotTruth.problems(host)), "")
        }
        function test_themeMustFollowThePreference() {
            const page = createTemporaryObject(scene, host)
            page.sidebar.choose(2)
            Theme.mode = "dark"
            waitForRendering(page)
            compare(rules(ShotTruth.problems(host)), "theme")
            Api.update({theme: "dark"})
            compare(Api.preferences.theme, "dark")
            verify(Theme.dark)
            compare(rules(ShotTruth.problems(host)), "")
            Api.update({theme: "light"})
            verify(!Theme.dark)
            compare(rules(ShotTruth.problems(host)), "")
        }
        function test_leakedValuesAreCaught() {
            const page = createTemporaryObject(scene, host)
            page.sidebar.choose(2)
            waitForRendering(page)
            compare(rules(ShotTruth.problems(host)), "")
            for (const leak of ["Máy thấy undefined: mỗi thư mục", "Còn NaN phút", "Tên: [object Object]"]) {
                const label = createTemporaryObject(leakText, page, {text: leak})
                compare(rules(ShotTruth.problems(host)), "leak", leak)
                label.visible = false
            }
            const field = createTemporaryObject(leakField, page, {text: "undefined"})   // ô nhập: chữ người dùng gõ
            compare(rules(ShotTruth.problems(host)), "")
            const fine = createTemporaryObject(leakText, page, {text: "Không xác định (undefinedness là một từ khác)"})
            compare(rules(ShotTruth.problems(host)), "")
        }
        function test_typeNameReadsQmlTypes() {
            const page = createTemporaryObject(scene, host)
            compare(ShotTruth.typeName(page.sidebar), "Sidebar")
        }
    }
}

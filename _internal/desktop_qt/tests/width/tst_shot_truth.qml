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
        function test_typeNameReadsQmlTypes() {
            const page = createTemporaryObject(scene, host)
            compare(ShotTruth.typeName(page.sidebar), "Sidebar")
        }
    }
}

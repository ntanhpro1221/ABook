import QtQuick
import QtTest
import ABook

// Ảnh của chủ sách 17-11 (Kho nhạc): bấm thanh "Đang nghe thử" thì cú bấm lọt xuống dòng bài nằm dưới. Dựng một dòng bài THẬT (MusicTrackRow) phủ cả
// khung, đặt thanh nghe thử (MusicPreviewBar) đè lên đáy như MusicScreen.qml, rồi bấm: thân thanh mở đúng bài đang nghe thử, ■ chỉ dừng, chỗ trống /
// khe dưới thanh không tới dòng bài. Thêm: TapShield nuốt cú bấm ở chỗ trống của một lớp nổi mà nút bên trong vẫn bấm được.
Item {
    id: host
    width: 600
    height: 400

    Component {
        id: sceneFactory
        Item {
            id: scene
            width: 600; height: 400
            property alias row: row
            property alias bar: bar
            property int rowClicks: 0
            property int rowPreviews: 0
            property var opened: []
            property int stops: 0
            MusicTrackRow {
                id: row
                width: parent.width; height: parent.height
                track: ({ link: "https://music/07.mp3", title: "07 Under The Bar", creator: "Someone", duration: 120 })
                onClicked: scene.rowClicks++
                onPreview: scene.rowPreviews++
            }
            MusicPreviewBar {
                id: bar
                x: 40; width: parent.width - 80
                y: parent.height - height
                height: implicitHeight
                track: ({ link: "https://music/03.mp3", title: "03 Jungle of Mysteries" })
                onOpened: scene.opened = scene.opened.concat(["https://music/03.mp3"])
                onStopped: scene.stops++
            }
        }
    }

    Component {
        id: layerFactory
        Item {
            id: layer
            width: 600; height: 400
            property int below: 0
            property int button: 0
            property alias action: action
            property alias panel: panel
            Interactive { anchors.fill: parent; onClicked: layer.below++ }
            Rectangle {
                id: panel
                x: 100; y: 100; width: 300; height: 120
                color: "white"
                TapShield {}
                // Không đặt exclusiveTap: nằm trong lớp có TapShield thì Interactive tự giữ riêng cú bấm
                Interactive { id: action; x: 200; y: 40; width: 80; height: 40; onClicked: layer.button++ }
            }
        }
    }

    // Lớp như Đang nghe / bảng nổi: nút nằm sâu (trong Column, hàng của ListView, nội dung Loader) đều tự giữ riêng cú bấm. Bên dưới là một
    // Interactive phủ cả khung như bìa / dòng của thư viện; tổ tiên có TapHandler nút Back như Main.qml và HoverHandler như panel của Sidebar.
    Component {
        id: deepFactory
        Item {
            id: deep
            width: 600; height: 400
            property int below: 0
            property int backs: 0
            property var picked: []
            property alias under: under
            property alias list: list
            property alias loaded: loader.item
            property alias panel: panel
            property alias panelHover: panelHover
            property alias plain: plain
            TapHandler { acceptedButtons: Qt.BackButton; gesturePolicy: TapHandler.ReleaseWithinBounds; onTapped: deep.backs++ }
            Interactive { id: under; anchors.fill: parent; tip: "under"; onClicked: deep.below++ }
            Item {
                id: panel
                x: 50; y: 50; width: 500; height: 300
                HoverHandler { id: panelHover }
                TapShield {}
                Column {
                    width: parent.width
                    Interactive { id: plain; width: 200; height: 40; onClicked: deep.picked = deep.picked.concat(["plain"]) }
                    ListView {
                        id: list
                        width: 200; height: 120
                        model: 3
                        delegate: Interactive {
                            required property int index
                            width: 200; height: 40
                            onClicked: deep.picked = deep.picked.concat(["row" + index])
                        }
                    }
                    Loader {
                        id: loader
                        sourceComponent: Interactive { width: 200; height: 40; onClicked: deep.picked = deep.picked.concat(["loaded"]) }
                    }
                }
            }
        }
    }

    TestCase {
        name: "TapThrough"
        when: windowShown

        function settle() { wait(Theme.motionMedium + 50) }

        function test_barBodyOpensItsOwnTrack() {
            const scene = createTemporaryObject(sceneFactory, host)
            settle()
            // Tên đọc giữ trạng thái + tên bài (soát 17-11: "Mở <tên>" làm mất "Đang đệm / Đã tạm dừng"); việc "Mở" ở phần mô tả
            compare(scene.bar.body.Accessible.name, "Đang nghe thử · 03 Jungle of Mysteries")
            compare(scene.bar.body.Accessible.description, "Mở")
            scene.bar.loading = true
            compare(scene.bar.body.Accessible.name, "Đang đệm · 03 Jungle of Mysteries")
            scene.bar.loading = false; scene.bar.paused = true
            compare(scene.bar.body.Accessible.name, "Đã tạm dừng · 03 Jungle of Mysteries")
            scene.bar.paused = false
            mouseClick(scene.bar.body, 60, scene.bar.body.height / 2)
            compare(scene.opened, ["https://music/03.mp3"])
            compare(scene.rowClicks, 0, "the tap fell through to the row under the bar")
            compare(scene.rowPreviews, 0)
            compare(scene.stops, 0)
        }

        function test_stopOnlyStops() {
            const scene = createTemporaryObject(sceneFactory, host)
            settle()
            const stop = scene.bar.stopButton
            mouseClick(stop, stop.width / 2, stop.height / 2)
            compare(scene.stops, 1)
            compare(scene.opened.length, 0, "stop also opened the track")
            compare(scene.rowClicks, 0)
        }

        function test_gapUnderTheBarSwallowsTaps() {
            const scene = createTemporaryObject(sceneFactory, host)
            settle()
            // Khe giữa thân thanh và đáy màn: thanh vẽ ở trên, dòng bài nằm dưới cả khe.
            const y = scene.bar.body.height + scene.bar.gap / 2
            verify(scene.bar.gap > 0)
            mouseClick(scene.bar, scene.bar.width / 2, y)
            compare(scene.rowClicks, 0, "the gap under the bar let the tap through")
            compare(scene.opened.length, 0)
            // Đối chứng: ngoài thanh thì dòng bài vẫn nhận cú bấm.
            mouseClick(scene.row, 300, 60)
            compare(scene.rowClicks, 1)
        }

        function test_shieldKeepsEmptySpaceButNotButtons() {
            const layer = createTemporaryObject(layerFactory, host)
            mouseClick(layer.panel, 20, 20)
            compare(layer.below, 0, "a tap on the layer's empty space reached the item below")
            mouseClick(layer.action, 10, 10)
            compare(layer.button, 1)
            compare(layer.below, 0)
            mouseClick(layer, 20, 20)
            compare(layer.below, 1)
        }

        // Cách sửa chung: không nút nào trong lớp đặt exclusiveTap, vậy mà nút thường, hàng của ListView và nội dung Loader đều giữ riêng cú bấm;
        // Interactive ngoài lớp thì không (vẫn thụ động như cũ).
        function test_everyInteractiveInsideAShieldedLayerHoldsItsTap() {
            const deep = createTemporaryObject(deepFactory, host)
            tryVerify(() => deep.list.count === 3 && deep.loaded !== null)
            const rows = [deep.plain, deep.list.itemAtIndex(1), deep.loaded]
            for (const item of rows) verify(item.holdsTap, "an Interactive inside the layer does not hold its tap")
            verify(!deep.under.holdsTap, "an Interactive outside every layer turned exclusive")
            for (const item of rows) mouseClick(item, item.width / 2, item.height / 2)
            compare(deep.picked, ["plain", "row1", "loaded"])
            compare(deep.below, 0, "a tap on a button inside the layer reached the Interactive under it")
        }

        // Soát 17-11: khiên nuốt cả nút Back của chuột thì Back không còn đóng Đang nghe khi trỏ nằm trên nó. Back phải đi tiếp tới TapHandler Back của
        // tổ tiên (Main.qml), dù trỏ đứng trên chỗ trống của lớp hay trên một nút của lớp.
        function test_backButtonPassesThroughTheShield() {
            const deep = createTemporaryObject(deepFactory, host)
            tryVerify(() => deep.list.count === 3)
            mouseClick(deep.panel, 400, 250, Qt.BackButton)
            compare(deep.backs, 1, "the shield swallowed the mouse Back button")
            mouseClick(deep.plain, 10, 10, Qt.BackButton)
            compare(deep.backs, 2, "a button in the layer swallowed the mouse Back button")
            compare(deep.below, 0)
            compare(deep.picked.length, 0)
            // Phải / giữa vẫn bị khiên giữ lại (không mở menu chuột phải của dòng nằm dưới)
            mouseClick(deep.panel, 400, 250, Qt.RightButton)
            mouseClick(deep.panel, 400, 250, Qt.MiddleButton)
            compare(deep.below, 0)
        }

        // Soát 17-11: rê chuột qua khe dưới thanh nghe thử làm dòng bài nằm dưới sáng hover và hiện chú thích. Khiên giữ con trỏ lại; HoverHandler của
        // chính lớp (như panel của Sidebar) vẫn thấy con trỏ.
        function test_hoverStopsAtTheShield() {
            const scene = createTemporaryObject(sceneFactory, host)
            settle()
            const gapY = scene.bar.y + scene.bar.body.height + scene.bar.gap / 2
            mouseMove(scene, 300, 40); tryCompare(scene.row, "hovered", true)
            mouseMove(scene, 300, gapY)
            tryCompare(scene.row, "hovered", false)
            wait(700)       // quá 600 ms của chú thích
            compare(scene.row.hovered, false, "the row under the gap still shows hover")
            const deep = createTemporaryObject(deepFactory, host)
            mouseMove(deep, 10, 10); tryCompare(deep.under, "hovered", true)
            mouseMove(deep, 450, 250)
            tryCompare(deep.under, "hovered", false)
            verify(deep.panelHover.hovered, "the layer's own HoverHandler lost the pointer")
        }
    }
}

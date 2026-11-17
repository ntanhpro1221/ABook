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
                Interactive { id: action; x: 200; y: 40; width: 80; height: 40; exclusiveTap: true; onClicked: layer.button++ }
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
            compare(scene.bar.body.Accessible.name, "Mở 03 Jungle of Mysteries")
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
    }
}

import QtQuick
import QtQuick.Effects
import ABook
import "AvatarLogic.js" as Art
import "CastLogic.js" as Cast

Item {
    id: root
    property string name: ""
    property var portrait: null
    property string bookId: ""
    property string peer: ""
    property bool voice: false
    property real pixels: 40
    property string mark: ""                    // thay chữ cái đầu (vd "?" của người chưa rõ)
    readonly property var fallback: portrait && portrait.kind === "pattern" ? portrait : Art.pattern(portrait && portrait.key || name)
    readonly property string file: portrait && portrait.file || (voice ? Art.voiceFile(name) : "")
    readonly property url imageUrl: voice || (portrait && portrait.kind === "voice") ? "qrc:/voiceavatars/" + file
        : /^avatars\/[0-9a-f]{64}\.webp$/.test(file) && bookId ? DesktopApi.mediaUrl(Cast.routed("/media/books/" + bookId + "/" + file, peer)) : ""
    implicitWidth: pixels
    implicitHeight: pixels
    width: pixels
    height: pixels
    Rectangle { anchors.fill: parent; radius: width / 2; color: root.fallback.color }
    Canvas {
        anchors.fill: parent
        property var art: root.fallback
        onArtChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset(); ctx.beginPath(); ctx.arc(width/2, height/2, width/2, 0, 2*Math.PI); ctx.clip()
            ctx.fillStyle = "rgba(255,255,255,0.10)"
            for (let y = 0; y < 5; y++) for (let x = 0; x < 5; x++) if (Art.cell(art.bits, x, y)) ctx.fillRect(x*width/5,y*height/5,width/5,height/5)
        }
    }
    Text { anchors.centerIn: parent; text: root.mark || root.fallback.initials; color: "white"; font.pixelSize: root.width * 0.30; font.weight: Font.Bold }
    Image { id: photo; anchors.fill: parent; source: root.imageUrl; sourceSize: Qt.size(256,256); asynchronous: true; cache: true; fillMode: Image.PreserveAspectCrop; visible: false }
    Item { id: circleMask; anchors.fill: parent; layer.enabled: true; visible: false; Rectangle { anchors.fill: parent; radius: width/2; color: "white" } }
    MultiEffect { anchors.fill: parent; source: photo; maskEnabled: true; maskSource: circleMask; opacity: photo.status === Image.Ready ? 1 : 0; Behavior on opacity { NumberAnimation { duration: Theme.motionFast } } }
}

import QtQuick
import ABook
import "MusicArtRaster.mjs" as Raster

// Decorative: the row/sheet already provides the accessible track title.
Item {
    id: root
    objectName: "musicArt"
    property var track: ({})
    implicitWidth: 40
    implicitHeight: 40
    readonly property int seed: Number.isInteger(track.artSeed) ? track.artSeed : Raster.fallbackSeed(track.link || "")
    Image {
        objectName: "musicArtGenerated"
        anchors.fill: parent
        source: "data:image/bmp;base64," + Raster.base64(root.seed)
        asynchronous: true
        fillMode: Image.PreserveAspectFit
        smooth: true
    }
    Image {
        anchors.fill: parent
        source: root.visible && root.track.art && root.track.art.sha1 && root.track.art.url
            ? "image://musicart/" + root.track.art.sha1 + "/" + encodeURIComponent(root.track.art.url) : ""
        sourceSize: Qt.size(Math.ceil(root.width * Screen.devicePixelRatio), Math.ceil(root.height * Screen.devicePixelRatio))
        asynchronous: true
        fillMode: Image.PreserveAspectFit
        visible: status === Image.Ready
    }
}

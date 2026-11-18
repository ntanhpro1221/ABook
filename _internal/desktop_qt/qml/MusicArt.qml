import QtQuick
import ABook
import "MusicArtRaster.mjs" as Raster

// Decorative: the row/sheet already provides the accessible track title.
// Corners: Theme.radiusCover like web (`rounded-cover`) and Android (RoundedCornerShape(Dim.radiusCover)); RoundedImage clips
// both images without a shader, so the corners also show in the software-backend screenshots.
Item {
    id: root
    objectName: "musicArt"
    property var track: ({})
    property real radius: Theme.radiusCover
    implicitWidth: 40
    implicitHeight: 40
    readonly property int seed: Number.isInteger(track.artSeed) ? track.artSeed : Raster.fallbackSeed(track.link || "")
    RoundedImage {
        objectName: "musicArtGenerated"
        anchors.fill: parent
        radius: root.radius
        source: "image://musicart/generated/" + root.seed
        asynchronous: true
    }
    RoundedImage {
        id: suppliedArt
        objectName: "musicArtSupplied"
        anchors.fill: parent
        radius: root.radius
        source: root.visible && root.track.art && root.track.art.sha1 && root.track.art.url
            ? "image://musicart/" + root.track.art.sha1 + "/" + encodeURIComponent(root.track.art.url) : ""
        sourceSize: Qt.size(Math.ceil(root.width * Screen.devicePixelRatio), Math.ceil(root.height * Screen.devicePixelRatio))
        Reveal { target: suppliedArt; shown: suppliedArt.status === Image.Ready }
    }
}

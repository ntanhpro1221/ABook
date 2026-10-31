import QtQuick
import ABook
import "StudioSetupLogic.js" as Setup

// Lời nói thật với người đang tạo sách nói trên máy chưa có Studio (StudioInstallNotice + NoStudioHere của studio/StudioSetup.tsx): máy không đủ để làm sách nói thì mời tạo ở máy tính đã
// ghép ("Tạo trên <máy>" mở Studio của máy ấy); máy làm được nhưng chưa cài / cần sửa / cần cập nhật thì nói dự án giữ thiết lập và chờ, nút dẫn tới thẻ cài ở trang Dự án.
// Máy có Studio thì không hiện gì. `unfitOnly`: chỉ khối "Máy thiếu cấu hình" (đặt cạnh nút tạo).
Item {
    id: root
    property var form: null
    property bool unfitOnly: false
    signal setupRequested()
    signal peerRequested(string id)
    readonly property var studio: form ? form.studio : Setup.studioMissing(null)
    readonly property var fit: form ? form.fit : null
    readonly property bool remote: form ? form.remote : false
    readonly property bool unfit: Boolean(form && form.unfit)
    readonly property bool shownInstall: !unfitOnly && studio.missing && !unfit
    readonly property bool shownUnfit: studio.missing && unfit
    property var peers: []
    implicitHeight: reveal.height
    height: implicitHeight
    visible: reveal.visible

    function loadPeers() {
        if (remote) return
        Api.call("GET", "/api/computers", null, function(data, error) {
            if (!error && data) root.peers = (data.computers || []).filter(computer => computer.kind !== "phone")
        })
    }
    onShownUnfitChanged: if (shownUnfit && peers.length === 0) loadPeers()
    Component.onCompleted: if (shownUnfit) loadPeers()

    Collapse {
        id: reveal
        width: parent.width
        open: root.shownInstall || root.shownUnfit
        Item {
            width: parent.width
            Accessible.role: Accessible.Grouping
            Accessible.name: "Cần Studio"
            readonly property bool wide: width >= 520
            readonly property real buttons: root.shownUnfit ? peerFlow.height : (root.remote ? 0 : install.height)
            height: 16 + Math.max(words.height, wide ? buttons : words.height + 8 + buttons) + 16
            Icon { y: 16 + 2; name: "cpu"; size: 16; color: Theme.warning }
            Column {
                id: words
                objectName: root.shownUnfit ? "noStudioHere" : "studioInstallNotice"
                x: 28
                y: 16
                width: parent.wide && buttons > 0 ? parent.width - 28 - Math.max(install.width, peerFlow.width) - 12 : parent.width - 28
                readonly property real buttons: parent.buttons
                Prose {
                    strong: true
                    tone: Theme.text
                    text: root.shownUnfit ? "Máy thiếu cấu hình" : (root.studio.repair ? "Cần sửa Studio" : root.studio.update ? "Studio cần cập nhật" : "Chưa cài Studio")
                }
                Prose {
                    objectName: "studioNoticeLine"
                    topPadding: 4
                    small: true
                    text: root.shownUnfit
                        ? Setup.noStudioLine(root.fit && root.fit.reason ? root.fit.reason : "").replace(/\.$/, "") + "; " +
                          (root.peers.length ? "tạo trên máy đã ghép có Studio, sách xong nghe ở cả hai máy." : "cài Studio trên máy khác rồi ghép tại Cài đặt → Thiết bị.")
                        : "Dự án giữ thiết lập và chờ Studio sẵn sàng."
                }
            }
            Button {
                id: install
                objectName: "studioNoticeInstall"
                visible: root.shownInstall && !root.remote
                x: parent.wide ? parent.width - width : 28
                y: parent.wide ? 16 : 16 + words.height + 8
                text: root.studio.action
                icon: "download"
                kind: "ghost"
                size: "sm"
                onActivated: root.setupRequested()
            }
            Flow {
                id: peerFlow
                visible: root.shownUnfit && root.peers.length > 0
                x: parent.wide ? parent.width - width : 28
                y: parent.wide ? 16 : 16 + words.height + 8
                width: parent.wide ? natural : parent.width - 28
                spacing: 8
                readonly property real natural: {
                    let sum = 0
                    for (let i = 0; i < children.length; ++i) sum += children[i].width + (i ? spacing : 0)
                    return sum
                }
                Repeater {
                    model: root.peers
                    delegate: Button {
                        required property var modelData
                        objectName: "studioNoticePeer"
                        text: "Tạo trên " + modelData.name
                        icon: "clapperboard"
                        kind: "ghost"
                        size: "sm"
                        onActivated: root.peerRequested(modelData.id)
                    }
                }
            }
        }
    }
}

import "UiStrings.js" as S
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
    Reveal { shown: reveal.visible }

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
            Accessible.name: S.s_can_studio_4b14a373
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
                    text: root.shownUnfit ? S.s_may_thieu_cau_hinh_df5ae9ef : (root.studio.repair ? S.s_can_sua_studio_a65aa0f0 : root.studio.update ? S.s_studio_can_cap_nhat_c0338642 : S.s_chua_cai_studio_029df34a)
                }
                Prose {
                    objectName: "studioNoticeLine"
                    topPadding: 4
                    small: true
                    text: root.shownUnfit
                        ? Setup.noStudioLine(root.fit && root.fit.reason ? root.fit.reason : "").replace(/\.$/, "") + "; " +
                          (root.peers.length ? S.s_tao_tren_may_da_ghep_co_studio_sach_xong_n_816bfc37 : S.s_cai_studio_tren_may_khac_roi_ghep_tai_cai_ae8031d9)
                        : S.s_du_an_giu_thiet_lap_va_cho_studio_san_sang_e878c6ea
                }
            }
            Button {
                id: install
                objectName: "studioNoticeInstall"
                Reveal { shown: root.shownInstall && !root.remote }
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
                Reveal { shown: root.shownUnfit && root.peers.length > 0 }
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
                        text: S.s_tao_tren_91f136e2 + modelData.name
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

import "UiStrings.js" as S
import QtQuick
import ABook
import "EditBookLogic.js" as Edit

// Ảnh bìa thật cho một cuốn ở đầu trang dự án (CoverEditor.tsx; webui/covers.py): chọn file, kéo thả ảnh vào bìa, dán (Ctrl+V), hay tìm trên mạng (Tìm ảnh bìa). Máy chủ tự thu nhỏ
// và tính màu; ảnh đi theo sách sang điện thoại, màn hình khoá và file MP3 xuất ra. Mọi lời gọi đi qua `store.request` nên Studio của máy khác cũng đặt được bìa (ảnh bìa của
// máy ấy chỉ hiện bằng bìa vẽ ở đây - ảnh thật nằm trên máy tính kia).
Item {
    id: root
    property var store: null
    property var book: null
    property bool dragging: false
    property bool working: false          // đang đặt / bỏ
    property bool choosing: false         // ảnh mạng đã chọn đang về
    property bool wantPick: false
    property bool narrow: false           // màn hẹp: bìa 96, chỉ còn nút biểu tượng
    readonly property bool busy: working || choosing
    readonly property bool peer: store ? store.peer !== "" : false
    readonly property bool hasCover: Boolean(book && book.cover)
    readonly property real coverW: narrow ? 96 : 176
    implicitWidth: coverW
    implicitHeight: art.height + 8 + actions.height + (narrow ? 0 : 20)
    width: coverW
    objectName: "coverEditor"

    function request(method, body, done) { return store.request(method, "/api/books/" + book.id + "/cover", body, done) }
    function fail(title, status, data) { Api.notice = title + "\n" + store.errorText(status, data) }
    function refresh() { store.refresh(book.id) }
    function setImage(image) {
        if (busy || !book) return
        if (!image) { Api.notice = S.s_chua_dat_duoc_anh_bia_chua_doc_duoc_file_a_07b09b14; return }
        working = true
        request("PUT", {image: image}, function(status, data) {
            root.working = false
            if (status < 200 || status >= 300) { root.fail(S.s_chua_dat_duoc_anh_bia_a4afb9fa, status, data); return }
            root.refresh()
            Api.toast(S.s_da_dat_anh_bia_90470364)
        })
    }
    function removeCover() {
        if (busy || !book) return
        working = true
        request("DELETE", null, function(status, data) {
            root.working = false
            if (status < 200 || status >= 300) { root.fail(S.s_chua_bo_duoc_anh_bia_a4173b5d, status, data); return }
            root.refresh()
            Api.toast(S.s_da_bo_anh_bia_dc2da6ed)
        })
    }
    function chooseFile() {
        picker.active = true
        if (picker.item) picker.item.choose()
        else wantPick = true
    }
    Loader {
        id: picker
        active: false
        sourceComponent: CoverPicker { onPicked: file => root.setImage(DesktopApi.imageData(file)) }
        onLoaded: if (root.wantPick) { root.wantPick = false; item.choose() }
    }
    // Dán ảnh (Ctrl+V) ở bất kỳ đâu trên trang sách - trừ khi đang gõ vào ô chữ
    function typing() {
        const focused = Window.window ? Window.window.activeFocusItem : null
        return Boolean(focused) && typeof focused.cursorPosition === "number"
    }
    Shortcut {
        sequences: [StandardKey.Paste]
        enabled: root.visible && root.enabled && Nav.uiVisible && !searchBox.open
        onActivated: {
            if (root.typing()) return
            const image = DesktopApi.clipboardImage()
            if (image) root.setImage(image)
        }
    }

    // Bìa + kéo thả
    Item {
        id: art
        objectName: "coverArt"
        width: parent.width
        height: Math.round(width * 1.5)
        CoverView {
            anchors.fill: parent
            title: root.book ? root.book.title : ""
            radius: Theme.radiusControl
            coverKey: root.hasCover && !root.peer ? root.book.id + "/" + (root.book.cover.version || 0) : ""
        }
        Rectangle {
            anchors.fill: parent
            anchors.margins: -2
            radius: Theme.radiusControl + 2
            color: "transparent"
            border.width: 2
            border.color: Theme.accent
            opacity: root.dragging ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
        }
        Rectangle {
            objectName: "coverBusy"
            anchors.fill: parent
            radius: Theme.radiusControl
            color: Theme.sunken
            opacity: root.busy ? 0.85 : 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
        }
        DropArea {
            anchors.fill: parent
            onEntered: drag => {
                drag.accepted = drag.hasUrls && drag.urls.some(url => /\.(png|jpe?g|webp|gif|bmp)$/i.test(String(url)))
                root.dragging = drag.accepted
            }
            onExited: root.dragging = false
            onDropped: drop => {
                root.dragging = false
                const image = drop.urls.filter(url => /\.(png|jpe?g|webp|gif|bmp)$/i.test(String(url)))[0]
                if (image) { drop.acceptProposedAction(); root.setImage(DesktopApi.imageData(image)) }
                else Api.notice = S.s_chi_tha_duoc_file_anh_png_jpeg_webp_2d5d7caf
            }
        }
    }
    // Nút: chữ đầu thẳng mép trái của bìa (lề âm bù đệm của nút)
    Row {
        id: actions
        x: root.narrow ? 0 : -8
        y: art.height + 8
        spacing: 4
        Button {
            objectName: "coverSet"
            Reveal { shown: !root.narrow }
            text: root.hasCover ? S.s_doi_bia_37220dae : S.s_dat_bia_a7e3a9a7
            icon: "image-plus"
            kind: "ghost"
            size: "sm"
            enabled: !root.busy
            onActivated: root.chooseFile()
        }
        IconButton {
            objectName: "coverSetIcon"
            Reveal { shown: root.narrow }
            icon: "image-plus"
            iconSize: 16
            ink: Theme.text2
            hoverInk: Theme.text
            tip: root.hasCover ? S.s_doi_anh_bia_7889ff91 : S.s_dat_anh_bia_dac4c265
            Accessible.name: root.hasCover ? S.s_doi_anh_bia_7889ff91 : S.s_dat_anh_bia_dac4c265
            enabled: !root.busy
            onClicked: root.chooseFile()
        }
        IconButton {
            objectName: "coverSearch"
            implicitWidth: 32
            implicitHeight: 32
            icon: "globe"
            iconSize: 16
            ink: Theme.text2
            hoverInk: Theme.text
            tip: S.s_tim_anh_bia_tren_mang_a87bd41b
            Accessible.name: S.s_tim_anh_bia_tren_mang_a87bd41b
            enabled: !root.busy
            onClicked: { search.begin(root.book.id, Edit.seriesName(root.book.title)); searchBox.show() }
        }
        IconButton {
            objectName: "coverRemove"
            Reveal { shown: root.hasCover }
            implicitWidth: 32
            implicitHeight: 32
            icon: "trash"
            iconSize: 16
            ink: Theme.text2
            hoverInk: Theme.text
            tip: S.s_bo_anh_bia_696c6692
            Accessible.name: S.s_bo_anh_bia_dung_lai_bia_ve_tu_ten_sach_95de3f45
            enabled: !root.busy
            onClicked: root.removeCover()
        }
    }
    Text {
        objectName: "coverHint"
        Reveal { shown: !root.narrow }
        y: actions.y + actions.height
        width: parent.width
        text: S.s_keo_hoac_dan_anh_71bf1343
        color: Theme.text3
        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
        font.pixelSize: Theme.sizeCaption
    }

    // Tìm ảnh bìa trên mạng (CoverSearchDialog)
    Modal {
        id: searchBox
        objectName: "coverSearchBox"
        title: S.s_tim_anh_bia_9825b3d1
        description: S.s_ban_chon_anh_tu_cac_nguon_sach_hoac_tren_m_ca23c898
        panelWidth: 560
        onClosed: { search.cancel(); root.choosing = false }
        CoverSearch {
            id: search
            objectName: "coverSearchPanel"
            width: parent.width
            route: function(method, path, body, done) { return root.store.request(method, path, body, done) }
            onChosen: { searchBox.dismiss(); root.refresh(); Api.toast(S.s_da_dat_anh_bia_90470364) }
            onChooseFile: { searchBox.dismiss(); root.chooseFile() }
            onChoosingChanged: root.choosing = choosing
        }
    }
}

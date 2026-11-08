import "UiStrings.js" as S
import QtQuick
import ABook
import "EditBookLogic.js" as Logic

// "Cách đọc tên" trong hộp "Sửa sách" (BookReadingsSection của listen/WordReadings.tsx; cuốn chỉ có chữ): các từ đã dạy giọng đọc, sửa / bỏ từng
// từ. Chỉ giọng đọc đổi, chữ của sách giữ nguyên. Ô sửa mở tại chỗ dưới từ (Collapse) và có lớp Back riêng. Chưa có nút "Nghe thử": giọng đọc thử
// của máy tính chưa nối vào bản Qt.
Column {
    id: root
    property string bookId: ""
    property var list: []
    property bool loading: true
    property bool failed: false
    property bool saving: false
    property string editing: ""           // từ đang sửa
    property string draft: ""
    signal changed()

    function load() {
        loading = list.length === 0; failed = false
        Api.call("GET", "/api/books/" + bookId + "/readings", null, function(data, error) {
            root.loading = false
            if (error) { Api.notice = ""; root.failed = root.list.length === 0; return }
            root.list = data.readings || []
        })
    }
    function store(surface, spoken, current) {
        if (saving) return
        saving = true
        const said = Logic.cleanSpoken(spoken)
        Api.call("PUT", "/api/books/" + bookId + "/readings", {surface: surface, spoken: said}, function(data, error) {
            root.saving = false
            if (error) { Api.notice = Logic.toastText(editing === surface ? S.s_chua_luu_duoc_cach_doc_484ed453 : S.s_chua_bo_duoc_cach_doc_0fffff4e, error); return }
            root.list = data.readings || []
            Api.notice = said ? "“" + surface + S.s_se_doc_la_7a286c54 + said + S.s_tu_doan_sau_c4975fce : "“" + surface + S.s_doc_lai_nhu_chu_trong_sach_tu_doan_sau_0f8d93c4
            root.closeEdit()
            root.changed()
        })
    }
    function remove(surface) {
        if (saving) return
        saving = true
        Api.call("PUT", "/api/books/" + bookId + "/readings", {surface: surface, spoken: ""}, function(data, error) {
            root.saving = false
            if (error) { Api.notice = Logic.toastText(S.s_chua_bo_duoc_cach_doc_0fffff4e, error); return }
            root.list = data.readings || []
            root.closeEdit()
        })
    }
    QtObject {
        id: layer
        property bool on: false
        function close() { root.closeEdit() }
    }
    function openEdit(item) {
        if (editing === item.surface) { closeEdit(); return }
        editing = item.surface; draft = item.spoken
        if (!layer.on) { layer.on = true; Nav.openLayer(layer) }
    }
    function closeEdit() { editing = ""; if (layer.on) { layer.on = false; Nav.closedLayer(layer) } }
    Component.onCompleted: load()
    Component.onDestruction: closeEdit()

    Collapse {
        width: parent.width
        open: root.loading
        EditBookSkeleton { width: parent.width; count: 2; label: S.s_dang_tai_cach_doc_32d14df3 }
    }
    InlineError {
        width: parent.width
        open: root.failed && !root.loading
        message: S.s_ban_hay_thu_tai_lai_danh_sach_cach_doc_78ca66ce
        onRetry: root.load()
    }
    Collapse {
        width: parent.width
        open: !root.loading && !root.failed && root.list.length === 0
        HintText {
            width: parent.width
            text: S.s_chua_co_tu_nao_o_man_doc_giu_hay_bam_chuot_56927ffd
        }
    }
    Repeater {
        model: root.list
        Column {
            id: entry
            objectName: "readingRow"
            required property var modelData
            required property int index
            width: Theme.listWidth(root, root.width)
            Rectangle { visible: entry.index > 0; width: parent.width; height: 1; color: Theme.line }
            Item { width: 1; height: 8 }
            Item {
                width: parent.width
                height: Math.max(sentence.height, 32)
                Text {
                    id: sentence
                    width: parent.width - 2 * 32 - 2 * 8
                    anchors.verticalCenter: parent.verticalCenter
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    color: Theme.text
                    font.pixelSize: Theme.sizeBodySmall
                    textFormat: Text.StyledText
                    text: "<b>" + escapeHtml(entry.modelData.surface) + "</b><font color='" + Theme.text2 + S.s_doc_la_font_0ec4a1ff + escapeHtml(entry.modelData.spoken) + "”"
                    function escapeHtml(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\u00a0/g, "&nbsp;") }
                }
                IconButton {
                    x: parent.width - 72
                    width: 32; height: 32
                    anchors.verticalCenter: parent.verticalCenter
                    icon: "pencil"; iconSize: 16
                    tip: S.s_sua_cach_doc_5968f72a + entry.modelData.surface
                    Accessible.name: tip
                    onClicked: root.openEdit(entry.modelData)
                }
                IconButton {
                    x: parent.width - 32
                    width: 32; height: 32
                    anchors.verticalCenter: parent.verticalCenter
                    icon: "trash"; iconSize: 16
                    enabled: !root.saving
                    tip: S.s_bo_cach_doc_4887d95e + entry.modelData.surface
                    Accessible.name: tip
                    onClicked: root.remove(entry.modelData.surface)
                }
            }
            Collapse {
                width: parent.width
                open: root.editing === entry.modelData.surface
                Item { width: 1; height: 8 }
                Text {
                    width: parent.width
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    color: Theme.text2
                    font.pixelSize: Theme.sizeCaption
                    textFormat: Text.StyledText
                    text: "<b><font color='" + Theme.text + "'>“" + entry.modelData.surface.replace(/&/g, "&amp;").replace(/</g, "&lt;") + S.s_font_b_doc_la_b6fb6454
                }
                FormField {
                    width: parent.width
                    label: S.s_cach_doc_cho_d0061fb3 + entry.modelData.surface
                    placeholderText: S.s_vd_ha_ru_to_93151b6c
                    text: root.editing === entry.modelData.surface ? root.draft : ""
                    onTextChanged: if (root.editing === entry.modelData.surface && text !== root.draft) root.draft = text.slice(0, 200)
                    onAccepted: saveButton.activated()
                }
                Flow {
                    width: parent.width
                    spacing: 8
                    Button {
                        id: saveButton
                        text: S.s_luu_cho_ca_cuon_76b88dc9
                        size: "sm"
                        enabled: Logic.cleanSpoken(root.draft) !== "" && Logic.cleanSpoken(root.draft) !== entry.modelData.spoken && Logic.cleanSpoken(root.draft) !== entry.modelData.surface
                        busy: root.saving && Logic.cleanSpoken(root.draft) !== ""
                        onActivated: if (enabled) root.store(entry.modelData.surface, root.draft, entry.modelData.spoken)
                    }
                    Button {
                        visible: entry.modelData.spoken !== ""
                        text: S.s_doc_nhu_chu_trong_sach_9a45fc3e
                        kind: "ghost"
                        size: "sm"
                        enabled: !root.saving
                        onClicked: root.store(entry.modelData.surface, "", entry.modelData.spoken)
                    }
                }
            }
            Item { width: 1; height: 8 }
        }
    }
}

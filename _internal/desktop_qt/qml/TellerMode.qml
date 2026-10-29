import QtQuick
import QtQuick.Controls.Basic as C
import ABook
import "TellerLogic.js" as T

// Công tắc "Nhân vật tự kể" của một cuốn (TellerModeSwitch.tsx, webui/teller_mode.py), dưới hàng "Người kể chuyện" của tab Nhân vật. Mặc định tắt. Sách đã có bản thu thì bật / tắt
// hiện trước số câu phải thu lại và chờ bạn xác nhận; sách đang chạy thì phải bấm “Dừng” trước (Tạm dừng không đủ). Máy không có chức năng này (`available` false) thì không hiện gì.
// Hỏi GET /narrator-mode một lần khi tab mở (15 giây một lần nếu sách đang chạy, chỉ khi cửa sổ đang thấy); đổi bằng PUT /narrator-mode {mode}.
Item {
    id: root
    objectName: "tellerMode"
    property var store: null
    property var book: null
    property string asking: ""                  // "teller" | "narrator" khi hộp xác nhận đang mở
    property bool saving: false
    readonly property var view: query.data
    readonly property bool shown: view !== null && Boolean(view.available)
    readonly property bool on: shown && view.mode === "teller"
    readonly property bool busy: shown && Boolean(view.castLocked) && !!book && (Boolean(book.running) || Boolean(book.starting))
    readonly property bool readOnly: shown && view.editableHere === false
    readonly property string hint: readOnly ? T.hint(on) + " " + T.ELSEWHERE : busy ? T.BUSY_NOTE : T.hint(on)
    width: parent ? parent.width : 400
    height: body.height

    StudioQuery {
        id: query
        store: root.store
        path: root.book ? "/api/books/" + root.book.id + "/narrator-mode" : ""
        wanted: root.visible && !!root.book
        interval: root.book && root.book.running ? 15000 : 0
    }

    function change(value) {
        const mode = value ? "teller" : "narrator"
        if (T.needsConfirm(view)) {
            asking = mode
            confirm.title = T.confirmTitle(mode)
            confirm.description = T.costText(view.plan, mode === "teller")
            confirm.actions = [{key: "later", text: "Thôi"}, {key: "go", text: T.confirmAction(mode), icon: "mic", kind: "primary"}]
            confirm.show()
        } else save(mode)
    }
    function save(mode) {
        if (saving || !book) return
        saving = true
        const id = book.id
        const recorded = view && view.plan ? view.plan.recorded || 0 : 0
        store.request("PUT", "/api/books/" + id + "/narrator-mode", {mode: mode}, function(status, data) {
            root.saving = false
            root.asking = ""
            confirm.dismiss()
            if (!root.store.ok(status)) { root.store.fail("Chưa đổi được", status, data); return }
            query.setData(data)
            root.store.editedCast(id)
            const note = T.savedNote(data, recorded)
            if (note) Api.notice = note
        })
    }

    Collapse {
        id: body
        width: parent.width
        open: root.shown
        Item { width: 1; height: 12 }
        SettingRow {
            objectName: "tellerRow"
            width: parent.width
            label: T.TITLE
            hint: root.hint
            Switch {
                objectName: "tellerSwitch"
                label: T.TITLE
                checked: root.on
                enabled: !root.saving && !root.busy && !root.readOnly
                onToggled: value => root.change(value)
            }
        }
    }
    StudioConfirm {
        id: confirm
        objectName: "tellerConfirm"
        parent: C.Overlay.overlay
        panelWidth: 480
        onChosen: key => {
            if (key === "go") root.save(root.asking)
            else { root.asking = ""; confirm.dismiss() }
        }
        onClosed: if (!root.saving) root.asking = ""
    }
}

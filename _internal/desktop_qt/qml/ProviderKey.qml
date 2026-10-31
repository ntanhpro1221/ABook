import QtQuick
import QtQuick.Controls.Basic as C
import ABook
import "VoiceLogic.js" as VoiceLogic

// Khung khoá riêng của một nhà cung cấp giọng (KeyCard của listen/VoiceSettings.tsx): đầu DisclosureRow (tên + "Dùng được · N giọng" / "Chưa dùng được"),
// gập sẵn (đã có khoá thì mở sẵn); thân: giới hạn miễn phí + cách tô chữ, "Nhận khoá", ô khoá (ẩn chữ) + vùng (Azure) + Lưu / Kiểm tra / Xoá khoá,
// dòng kết quả. "Lưu" chỉ cất khoá trên máy; "Kiểm tra" mới gọi dịch vụ (và lưu khoá đang gõ trước khi kiểm). Lỗi hiện tại chỗ, không toast.
Item {
    id: root
    property var info: ({limits: {}})
    property string busy: ""            // "" | "check" | "save" | "remove"
    property bool resultOk: false
    property string result: ""
    property string lastResult: ""      // giữ chữ lúc Collapse khép lại
    property bool open: Boolean(info.hasKey)
    readonly property string savedRegion: info.region || ""
    readonly property bool hasRegion: Boolean(info.limits && info.limits.region)
    readonly property bool regionChanged: hasRegion && regionField.text.trim() !== savedRegion
    readonly property string status: info.valid ? "Dùng được · " + info.voices + " giọng" : info.hasKey ? "Chưa dùng được" : ""
    signal changed()
    objectName: "providerKey." + (info.id || "")
    implicitHeight: col.height + 24
    height: implicitHeight
    onSavedRegionChanged: regionField.text = savedRegion
    onResultChanged: if (result !== "") lastResult = result

    function path() { return "/api/readaloud/online/" + info.id }
    function fail(error) { resultOk = false; result = error }
    function finish() { busy = ""; changed() }
    function save() {
        busy = "save"; result = ""
        if (!secret.text.trim() && !info.hasKey) { fail("Dán khoá trước đã."); finish(); return }
        Api.quiet("PUT", path(), {key: secret.text.trim(), region: regionField.text.trim()}, function(data, error) {
            if (error) fail(error)
            else { secret.text = ""; resultOk = true; result = "Đã lưu khoá. Bấm “Kiểm tra” để thử." }
            finish()
        })
    }
    function check() {
        busy = "check"; result = ""
        function ask() {
            Api.quiet("POST", path() + "/check", {}, function(checked, error) {
                if (error) fail(error)
                else {
                    secret.text = ""
                    resultOk = checked.ok === true
                    result = checked.ok ? "Dùng được · " + (checked.voices !== undefined && checked.voices !== null ? checked.voices : checked.provider.voices) + " giọng tiếng Việt"
                                        : (checked.message || "Khoá chưa dùng được.")
                }
                finish()
            })
        }
        if (secret.text.trim() || (hasRegion && regionField.text.trim() !== savedRegion)) {
            if (!secret.text.trim() && !info.hasKey) { fail("Dán khoá trước đã."); finish(); return }
            Api.quiet("PUT", path(), {key: secret.text.trim() || "", region: regionField.text.trim()}, function(data, error) {
                if (error) { fail(error); finish() }
                else ask()
            })
        } else ask()
    }
    function remove() {
        busy = "remove"
        Api.quiet("DELETE", path(), null, function(data, error) {
            if (error) fail(error)
            else { result = ""; secret.text = "" }
            finish()
        })
    }

    // Ô nhập của khung này: cao 36, bo điều khiển, viền --line, nền --panel, chữ 14 (input h-9 của web)
    component Box: C.TextField {
        property bool flexGrow: false
        property real flexBasis: 0
        implicitHeight: 36
        leftPadding: 12
        rightPadding: 12
        topPadding: 0
        bottomPadding: 0
        verticalAlignment: TextInput.AlignVCenter
        color: Theme.text
        placeholderTextColor: Theme.text3
        selectionColor: Theme.accent
        selectedTextColor: Theme.accentInk
        font.family: Theme.family
        font.pixelSize: Theme.sizeBodySmall
        selectByMouse: true
        activeFocusOnTab: true
        opacity: enabled ? 1 : 0.5
        background: Rectangle {
            color: Theme.panel
            radius: Theme.radiusControl
            border.width: 1
            border.color: parent.activeFocus ? Theme.focus : Theme.line
            Behavior on border.color { ColorAnimation { duration: Theme.motionFast } }
        }
    }

    Column {
        id: col
        y: 12
        width: root.width
        DisclosureRow {
            width: parent.width
            title: root.info.name || ""
            summary: root.status
            expanded: root.open
            onClicked: root.open = !root.open
        }
        Collapse {
            width: parent.width
            open: root.open
            Text {
                width: parent.width
                topPadding: 4
                text: (root.info.limits.free || "") + ". " + (root.info.limits.timings === "exact" ? "Tô đúng từng chữ đang đọc." : "Tô từng chữ đang đọc theo ước lượng.")
                color: Theme.text2
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: 13
            }
            MoreInfo {
                width: parent.width
                label: "Nhận khoá"
                HintText { width: parent.width; text: VoiceLogic.KEY_HELP[root.info.id] || "" }
            }
            Item { width: parent.width; height: 10 }
            VoiceFlex {
                width: parent.width
                Box {
                    id: secret
                    objectName: "keyInput"
                    flexGrow: true
                    flexBasis: 224
                    echoMode: TextInput.Password
                    passwordMaskDelay: 0
                    inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
                    enabled: root.busy === ""
                    Accessible.name: "Khoá " + (root.info.name || "")
                    placeholderText: root.info.hasKey ? "Đã lưu " + root.info.masked + " - dán khoá mới để thay" : "Dán khoá của bạn"
                }
                Box {
                    id: regionField
                    objectName: "regionInput"
                    visible: root.hasRegion
                    implicitWidth: 192
                    enabled: root.busy === ""
                    Accessible.name: "Vùng " + (root.info.name || "")
                    placeholderText: "Vùng, ví dụ southeastasia"
                    text: root.savedRegion
                }
                Button {
                    objectName: "keySave"
                    text: "Lưu"
                    kind: "text"
                    busy: root.busy === "save"
                    enabled: root.busy === "" && (secret.text.trim() !== "" || root.regionChanged)
                    onActivated: root.save()
                }
                Button {
                    objectName: "keyCheck"
                    text: "Kiểm tra"
                    icon: "key-round"
                    busy: root.busy === "check"
                    enabled: root.busy === "" && (Boolean(root.info.hasKey) || secret.text.trim() !== "")
                    onActivated: root.check()
                }
                Button {
                    objectName: "keyRemove"
                    visible: Boolean(root.info.hasKey)
                    text: "Xoá khoá"
                    icon: "trash"
                    kind: "text"
                    busy: root.busy === "remove"
                    enabled: root.busy === ""
                    onActivated: root.remove()
                }
            }
            Collapse {
                width: parent.width
                open: root.result !== ""
                Text {
                    objectName: "keyResult"
                    width: parent.width
                    topPadding: 8
                    text: root.lastResult
                    color: root.resultOk ? Theme.success : Theme.danger
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    font.pixelSize: 13
                    Accessible.role: Accessible.StaticText
                }
            }
        }
    }
}

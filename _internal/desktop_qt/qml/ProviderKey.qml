import "UiStrings.js" as S
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
    readonly property string status: info.valid ? S.s_dung_duoc_u00a0_u00a0_d746b459 + info.voices + S.s_giong_17cc0855 : info.hasKey ? S.s_chua_dung_duoc_c68b3845 : ""
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
        if (!secret.text.trim() && !info.hasKey) { fail(S.s_dan_khoa_truoc_da_d88da35d); finish(); return }
        Api.quiet("PUT", path(), {key: secret.text.trim(), region: regionField.text.trim()}, function(data, error) {
            if (error) fail(error)
            else { secret.text = ""; resultOk = true; result = S.s_da_luu_khoa_bam_kiem_tra_de_thu_a21b7359 }
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
                    result = checked.ok ? S.s_dung_duoc_u00a0_u00a0_d746b459 + (checked.voices !== undefined && checked.voices !== null ? checked.voices : checked.provider.voices) + S.s_giong_tieng_viet_aaa6e239
                                        : (checked.message || S.s_khoa_chua_dung_duoc_2ae17f08)
                }
                finish()
            })
        }
        if (secret.text.trim() || (hasRegion && regionField.text.trim() !== savedRegion)) {
            if (!secret.text.trim() && !info.hasKey) { fail(S.s_dan_khoa_truoc_da_d88da35d); finish(); return }
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
                text: (root.info.limits.free || "") + ". " + (root.info.limits.timings === "exact" ? S.s_to_dung_tung_chu_dang_doc_b0692da6 : S.s_to_tung_chu_dang_doc_theo_uoc_luong_b0de406b)
                color: Theme.text2
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: 14
            }
            MoreInfo {
                width: parent.width
                label: S.s_nhan_khoa_7ba3a705
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
                    Accessible.name: S.s_khoa_d7b08da0 + (root.info.name || "")
                    placeholderText: root.info.hasKey ? S.s_da_luu_62b04ebe + root.info.masked + S.s_dan_khoa_moi_de_thay_eb5e0364 : S.s_dan_khoa_cua_ban_c390a2e9
                }
                Box {
                    id: regionField
                    objectName: "regionInput"
                    visible: root.hasRegion
                    implicitWidth: 192
                    enabled: root.busy === ""
                    Accessible.name: S.s_vung_0dec5e2e + (root.info.name || "")
                    placeholderText: S.s_vung_vi_du_southeastasia_959965a2
                    text: root.savedRegion
                }
                Button {
                    objectName: "keySave"
                    text: S.s_luu_e91f26c0
                    kind: "text"
                    busy: root.busy === "save"
                    enabled: root.busy === "" && (secret.text.trim() !== "" || root.regionChanged)
                    onActivated: root.save()
                }
                Button {
                    objectName: "keyCheck"
                    text: S.s_kiem_tra_ff6e2891
                    icon: "key-round"
                    busy: root.busy === "check"
                    enabled: root.busy === "" && (Boolean(root.info.hasKey) || secret.text.trim() !== "")
                    onActivated: root.check()
                }
                Button {
                    objectName: "keyRemove"
                    visible: Boolean(root.info.hasKey)
                    text: S.s_xoa_khoa_2ec6cb1a
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
                    font.pixelSize: 14
                    Accessible.role: Accessible.StaticText
                }
            }
        }
    }
}

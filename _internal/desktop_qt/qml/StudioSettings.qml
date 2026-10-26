import QtQuick
import ABook

// Cài đặt › Studio › "Máy này" (StudioSettings của studio/StudioSetup.tsx + studio/studioFit.ts): Studio ở đâu, chạy trên card nào; chưa cài thì
// cần gì, máy có đủ không, và Cài / Xem tiến độ cài. Gỡ là xoá 15-20 GB nên bấm hai lần: lần đầu "Xác nhận gỡ" (6 giây, hoặc Back / Esc
// để huỷ - lớp Back riêng), lần hai mới gỡ. Tiến độ cài hiện ở màn Studio (`studioRequested`), ở đây chỉ nói "Đang cài.".
Item {
    id: root
    property var status: null           // GET /api/studio/setup
    property bool armed: false
    property bool busy: false
    signal studioRequested()
    readonly property bool present: Boolean(Api.info && Api.info.studio) && status !== null
    readonly property bool installed: status !== null && Boolean(status.installed)
    readonly property var fit: studioFit(status ? status.gpu : null)
    readonly property string needs: "NVIDIA từ 8 GB · tải ~25 GB · trống 35 GB · ~7–10 phút/chương."
    implicitHeight: present ? column.height : 0
    height: implicitHeight
    visible: present || column.height > 0
    objectName: "studioSettings"

    // ---- studio/studioFit.ts: máy này có đủ để làm sách nói không (NVIDIA từ 8 GB đủ, 6-8 GB chưa thử, dưới 6 GB hay không có card là không) ----
    function studioFit(gpu) {
        if (!gpu) {
            const reason = "không có card đồ hoạ NVIDIA, hay driver NVIDIA chưa cài"
            return {level: "no", line: "Máy này " + reason + ".", reason: reason}
        }
        if (!(gpu.memory > 0)) return {level: "maybe", line: "Card " + gpu.name + ": chưa đọc được bộ nhớ của card, chưa biết có đủ không."}
        const gb = gpu.memory / Math.pow(2, 30)
        const shown = gpu.name + " (" + Math.round(gb) + " GB)"
        if (gb >= 7.5) return {level: "ok", line: "Card " + shown + ": đủ để làm sách nói (đã thử trên card 8 GB)."}
        if (gb >= 5.5) return {level: "maybe", line: "Card " + shown + ": có thể chạy được nhưng chưa thử trên card dưới 8 GB, có thể chậm."}
        const reason = "card " + shown + " ít bộ nhớ hơn mức tối thiểu 6 GB"
        return {level: "no", line: "Card " + shown + ": ít bộ nhớ hơn mức tối thiểu 6 GB.", reason: reason}
    }
    function noStudioLine(reason) { return "Máy này không làm sách nói được (" + reason + "). Bạn vẫn nghe ngay mọi sách." }

    function ask(method, done) {
        if (!Api.transport) return
        Api.transport.request(method, "/api/studio/setup", method === "POST" ? {} : null, function(code, data) { done(code >= 200 && code < 300, data) })
    }
    function load() {
        if (!Api.info || !Api.info.studio || !Api.transport) return
        Api.transport.request("GET", "/api/studio/setup", null, function(code, data) { if (code >= 200 && code < 300) root.status = data })
    }
    function failure(title, data) { Api.notice = title + "\n" + (data && (data.message || data.error) || "Không làm được lúc này.") }
    function refreshInfo() { Api.call("GET", "/api/app", null, function(data, error) { if (!error) Api.info = data }) }

    // Bấm là cài luôn rồi sang màn Studio xem tiến độ - không phải bấm "Cài Studio" lần hai ở đó
    function install() {
        busy = true
        ask("POST", function(ok, data) {
            busy = false
            if (!ok) { failure("Không cài được Studio", data); return }
            status = data
            studioRequested()
        })
    }
    function remove() {
        if (!armed) { arm(true); return }
        arm(false)
        busy = true
        ask("DELETE", function(ok, data) {
            busy = false
            if (!ok) { failure("Chưa gỡ được Studio", data); return }
            status = data
            Api.notice = "Đã gỡ Studio"
            refreshInfo()
        })
    }
    property QtObject armLayer: QtObject { function close() { root.arm(false) } }
    function arm(on) {
        if (armed === on) return
        armed = on
        if (on) { Nav.openLayer(armLayer); disarm.restart() }
        else { Nav.closedLayer(armLayer); disarm.stop() }
    }
    Timer { id: disarm; interval: 6000; onTriggered: root.arm(false) }
    Timer { interval: 2000; repeat: true; running: root.present && Boolean(root.status && root.status.running); onTriggered: root.load() }
    Connections { target: Api; function onInfoChanged() { if (!root.status) root.load() } }
    Component.onCompleted: load()
    Component.onDestruction: Nav.closedLayer(armLayer)

    Column {
        id: column
        width: parent.width
        // ---- chưa cài ----
        Collapse {
            width: parent.width
            open: root.present && !root.installed
            SettingsItem {
                width: parent.width
                Column {
                    width: Math.min(parent.width, 576)
                    Text {
                        width: parent.width
                        height: Math.max(56, implicitHeight)
                        verticalAlignment: Text.AlignVCenter
                        text: "Studio trên máy này"
                        color: Theme.text
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeSection
                        font.weight: Theme.weightMedium
                    }
                    Text { objectName: "studioState"; width: parent.width; topPadding: 4; text: root.status && root.status.running ? "Đang cài." : "Chưa cài."; color: Theme.text; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
                    Text { width: parent.width; topPadding: 4; text: root.needs; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: 13; lineHeight: 1.3 }
                    Text {
                        objectName: "studioFit"
                        width: parent.width
                        topPadding: 4
                        text: root.fit.level === "no" ? root.noStudioLine(root.fit.reason || "") : root.fit.line
                        color: root.fit.level === "no" ? Theme.text : Theme.text2
                        wrapMode: Text.Wrap
                        font.pixelSize: 13
                        font.weight: root.fit.level === "no" ? Theme.weightMedium : Theme.weightRegular
                        lineHeight: 1.3
                    }
                    Item {
                        width: parent.width
                        height: installButton.height + 12
                        // Một nút đổi dáng theo tình trạng: đang cài -> Xem tiến độ cài; máy không đủ -> Vẫn cài (nhỏ); còn lại Cài Studio
                        Button {
                            id: installButton
                            objectName: "studioInstall"
                            y: 12
                            readonly property bool running: Boolean(root.status && root.status.running)
                            readonly property bool unfit: !running && root.fit.level === "no"
                            text: running ? "Xem tiến độ cài" : unfit ? "Vẫn cài" : "Cài Studio"
                            kind: running || unfit ? "ghost" : "primary"
                            size: unfit ? "sm" : "md"
                            icon: running ? "" : "download"
                            enabled: running || !root.busy
                            onClicked: running ? root.studioRequested() : root.install()
                        }
                    }
                }
            }
        }
        // ---- đã cài ----
        Collapse {
            width: parent.width
            open: root.present && root.installed
            SettingRow {
                width: parent.width
                label: "Studio trên máy này"
                hint: "Đã cài" + (root.status && root.status.gpu ? " · " + root.status.gpu.name : "") + "\n" + (root.status ? root.status.root : "")
                Button {
                    objectName: "studioRemove"
                    size: "sm"
                    kind: root.armed ? "danger" : "ghost"
                    icon: "trash-2"
                    text: root.busy ? "Đang gỡ…" : root.armed ? "Xác nhận gỡ" : "Gỡ Studio"
                    enabled: !root.busy
                    onClicked: root.remove()
                }
            }
            Collapse {
                width: parent.width
                open: root.status !== null && (root.status.outdated || []).length > 0
                Flow {
                    id: outdated
                    objectName: "studioOutdated"
                    readonly property bool damaged: Boolean(root.status && root.status.damaged && root.status.damaged.length)
                    width: parent.width
                    topPadding: 4
                    Text {
                        width: Math.min(implicitWidth, outdated.width)
                        text: (outdated.damaged ? "Mất " + root.status.damaged.join(", ") + " (file đã bị xoá hay hỏng)" : "Cần cập nhật " + (root.status ? root.status.outdated : []).join(", ")) + " - "
                        color: Theme.text2
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: 13
                    }
                    Interactive {
                        id: fixLink
                        objectName: "studioFixLink"
                        implicitWidth: fixText.implicitWidth
                        implicitHeight: fixText.implicitHeight
                        Accessible.role: Accessible.Link
                        Accessible.name: fixText.text
                        onClicked: root.studioRequested()
                        Text {
                            id: fixText
                            text: outdated.damaged ? "Sửa Studio" : "Cập nhật Studio"
                            color: Theme.accentText
                            font.pixelSize: 13
                            font.weight: Theme.weightMedium
                            font.underline: true
                        }
                    }
                    Text { text: "."; color: Theme.text2; font.pixelSize: 13 }
                }
            }
            // Hậu quả của việc gỡ chỉ cần lúc đang xác nhận - không treo thường trực dưới nút
            Collapse {
                width: parent.width
                open: root.armed
                HintText {
                    objectName: "studioArmedNote"
                    width: parent.width
                    bottomPadding: 12
                    text: "Xoá runtime/model (15–20 GB), giữ sách và hồ sơ; cuốn đang làm phải làm lại sau khi cài."
                    lineHeight: 1.15
                }
            }
        }
    }
}

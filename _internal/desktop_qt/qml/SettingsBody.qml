import QtQuick
import ABook

Column {
    id: root
    property string group: ""
    readonly property var prefs: Api.preferences
    property var cache: ({})
    property bool clearing: false
    property bool clearBusy: false
    property string updateLine: ""
    property string previous: ""
    property real phase: 1
    onGroupChanged: {
        if (transition.running) transition.complete()
        transition.start()
        if (group === "advanced") refreshCache()
    }
    SequentialAnimation {
        id: transition
        NumberAnimation { target: root; property: "phase"; to: 0; duration: Theme.reduceMotion ? 0 : Theme.motionFastOut }
        PropertyAction { target: root; property: "previous"; value: root.group }
        NumberAnimation { target: root; property: "phase"; to: 1; duration: Theme.reduceMotion ? 0 : Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeDecelerate }
    }
    opacity: phase
    transform: Translate { x: Theme.reduceMotion ? 0 : 16 * (1 - root.phase) }
    function refreshCache() { Api.call("GET", "/api/readaloud/cache", null, function(data, error) { if (!error) root.cache = data }) }
    function schedule(changes) {
        const value = Object.assign({}, prefs.sleepSchedule || {from: "22:00", to: "06:00", minutes: 30}, changes)
        Api.update({sleepSchedule: value}, function(data, error) {
            if (!error && JSON.stringify(data.sleepSchedule) !== JSON.stringify(value)) Api.notice = "Chưa đổi được lịch đêm"
        })
    }
    SettingsVoice { width: parent.width; visible: root.previous === "voice" }
    Column {
        width: parent.width; visible: root.previous === "listen"
        SectionBlock {
            width: parent.width
            SettingRow { width: parent.width; label: "Tự lùi"; hint: "Nghỉ quá 30 giây thì lùi 5 giây (quá 10 phút: 10 giây)."; Switch { label: "Tự lùi"; checked: root.prefs.autoRewind !== false; enabled: Api.loaded && !Api.saving; onToggled: value => Api.update({autoRewind: value}) } }
        }
        SectionBlock {
            width: parent.width; title: "Nhạc nền"
            SettingRow { width: parent.width; label: "Tự chọn nhạc nền"; hint: "Sách chỉ có chữ: nhạc nhẹ đổi theo cảnh."; Switch { label: "Tự chọn nhạc nền"; checked: root.prefs.autoMusic !== false; enabled: Api.loaded && !Api.saving; onToggled: value => Api.update({autoMusic: value}) } }
            MyMusicSettings { width: parent.width }
        }
    }
    SectionBlock {
        width: parent.width; visible: root.previous === "sleep"
        SettingChoices { width: parent.width; label: "Tự tắt"; hint: "Không ai chạm máy chừng này thì nhỏ dần rồi dừng."; value: root.prefs.safetyStopHours ?? 2; options: [{value: 0, label: "Không"}, {value: 1, label: "1 giờ"}, {value: 2, label: "2 giờ"}, {value: 3, label: "3 giờ"}]; enabled: !Api.saving; onPicked: value => Api.update({safetyStopHours: value}) }
        SettingRow { width: parent.width; label: "Lịch đêm"; hint: "Nghe trong khung giờ này thì tự hẹn giờ."; Switch { label: "Lịch đêm"; checked: Boolean(root.prefs.sleepSchedule); enabled: Api.loaded && !Api.saving; onToggled: value => Api.update({sleepSchedule: value ? {from: "22:00", to: "06:00", minutes: 30} : null}) } }
        SectionBlock {
            width: parent.width; topPadding: 0; expanded: Boolean(root.prefs.sleepSchedule)
            Flow {
                width: parent.width; spacing: 8
                FormLabel { text: "Từ"; topPadding: 12 }
                FormField { width: 80; label: "Từ"; text: root.prefs.sleepSchedule?.from || "22:00"; enabled: !Api.saving; onAccepted: if (/^([01]\d|2[0-3]):[0-5]\d$/.test(text)) root.schedule({from: text}) }
                FormLabel { text: "đến"; topPadding: 12 }
                FormField { width: 80; label: "Đến"; text: root.prefs.sleepSchedule?.to || "06:00"; enabled: !Api.saving; onAccepted: if (/^([01]\d|2[0-3]):[0-5]\d$/.test(text)) root.schedule({to: text}) }
                FormLabel { text: "hẹn"; topPadding: 12 }
            }
            SettingChoices { width: parent.width; label: "Số phút hẹn"; value: root.prefs.sleepSchedule?.minutes || 30; enabled: !Api.saving; options: [15,30,45,60].map(n => ({value: n, label: n + " phút"})); onPicked: value => root.schedule({minutes: value}) }
        }
        SettingChoices { width: parent.width; label: "Mỗi lần nghe thêm"; hint: "Lúc đang nhỏ dần: chạm phím hoặc chuột."; value: root.prefs.sleepExtendMinutes ?? 10; options: [5,10,15].map(n => ({value: n, label: n + " phút"})); enabled: !Api.saving; onPicked: value => Api.update({sleepExtendMinutes: value}) }
        SettingChoices { width: parent.width; label: "Nhỏ dần"; value: root.prefs.sleepFadeSeconds ?? 30; options: [{value: 10, label: "10 giây"}, {value: 30, label: "30 giây"}, {value: 60, label: "1 phút"}]; enabled: !Api.saving; onPicked: value => Api.update({sleepFadeSeconds: value}) }
    }
    Column {
        objectName: "settingsAppearance"
        width: parent.width; visible: root.previous === "look"
        SectionBlock {
            width: parent.width
            SettingChoices { width: parent.width; label: "Màu"; value: root.prefs.theme || "system"; options: [{value: "system", label: "Tự động"}, {value: "light", label: "Sáng"}, {value: "dark", label: "Tối"}]; enabled: !Api.saving; onPicked: value => Api.update({theme: value}) }
            SettingChoices { width: parent.width; label: "Nền đọc"; hint: "Nền của chữ khi đọc theo."; value: root.prefs.readingSurface || "auto"; options: [{value: "auto", label: "Tự động"}, {value: "paper", label: "Giấy"}, {value: "ivory", label: "Ngà"}, {value: "night", label: "Đêm"}]; enabled: !Api.saving; onPicked: value => Api.update({readingSurface: value}) }
            SettingRow { width: parent.width; label: "Âm thanh chạm"; hint: "Tiếng khẽ khi bạn chọn. Im khi đang nghe."; Switch { label: "Âm thanh chạm"; checked: root.prefs.touchSounds !== false; enabled: !Api.saving; onToggled: value => Api.update({touchSounds: value}) } }
        }
        SectionBlock {
            width: parent.width; title: "Phím tắt"
            SettingRow { width: parent.width; label: "Phím tắt chữ"; hint: "Tắt nếu hay lỡ chạm phím hay nhập bằng giọng nói."; Switch { label: "Phím tắt chữ"; checked: root.prefs.letterShortcuts !== false; enabled: !Api.saving; onToggled: value => Api.update({letterShortcuts: value}) } }
            Repeater {
                model: [{keys: "Space", label: "Phát / tạm dừng"}, {keys: "← →", label: "Lùi / tới 15 giây"}, {keys: "Shift + ← →", label: "Chương trước / sau"}, {keys: "M", label: "Tắt / bật tiếng", letter: true}, {keys: "[ ]", label: "Giảm / tăng tốc độ đọc", letter: true}, {keys: "Esc", label: "Thu nhỏ màn hình đang nghe"}, {keys: "?", label: "Xem các phím tắt này", letter: true}]
                SettingRow { required property var modelData; width: parent.width; label: modelData.label + (modelData.letter && root.prefs.letterShortcuts === false ? " (đang tắt)" : ""); line: false; FormLabel { text: modelData.keys; font.strikeout: Boolean(modelData.letter && root.prefs.letterShortcuts === false) } }
            }
            FormLabel { width: parent.width; visible: root.prefs.letterShortcuts === false; text: "Phím một chữ cái đang tắt. Space, mũi tên, Esc vẫn chạy."; color: Theme.text2 }
        }
    }
    SettingsDevices { width: parent.width; visible: root.previous === "devices" }
    SettingsStudio { width: parent.width; visible: root.previous === "studio" }
    Column {
        objectName: "settingsAdvanced"
        width: parent.width; visible: root.previous === "advanced"
        SectionBlock {
            width: parent.width; title: "Thư viện"; visible: !Api.info.listenOnly
            SettingRow { width: parent.width; label: root.prefs.libraryRoot || ""; Button { kind: "text"; text: "Đổi thư mục"; onClicked: folders.choose("library") } }
        }
        SectionBlock {
            width: parent.width; title: "Cập nhật"; visible: Boolean(Api.info.update || Api.info.canCheckUpdate)
            FormLabel { width: parent.width; visible: Boolean(Api.info.update); text: "ABook " + (Api.info.update?.version || "") + " đã có" + (Api.info.version ? " · đang dùng " + Api.info.version : "") }
            FormLabel { width: parent.width; visible: Boolean(Api.info.update?.notes); text: Api.info.update?.notes || ""; color: Theme.text2 }
            Button { text: Api.info.update ? "Cập nhật ABook" : "Kiểm tra bản mới"; kind: "text"; icon: Api.info.update ? "download" : ""; onClicked: Api.call("POST", Api.info.update ? "/api/app/update" : "/api/app/check-update", {}, function(data, error) { if (!error) root.updateLine = Api.info.update ? "Đang tải bản mới…" : "Đang kiểm tra…" }) }
            FormLabel { width: parent.width; text: root.updateLine; visible: text !== ""; color: Theme.text2 }
        }
        SectionBlock {
            width: parent.width; title: "Bộ nhớ"
            SettingRow { width: parent.width; label: "Bản đọc đã làm"; hint: root.cache.total ? "Đã dùng " + Math.round(root.cache.total / 1048576) + " MB" : "Chưa có bản đọc nào đã làm."; Button { kind: "text"; text: "Dọn bản đọc"; visible: root.cache.total > 0; onClicked: root.clearing = true } }
            SectionBlock { width: parent.width; title: "Tìm hiểu thêm"; fold: true; FormLabel { width: parent.width; text: "Nghe lại đoạn đã đọc xong thì không phải chờ máy đọc lại; dọn đi thì lấy lại chỗ trống."; color: Theme.text2 } }
            Column { width: parent.width; visible: root.clearing; spacing: 8
                FormLabel { width: parent.width; text: "Dọn bản đọc đã làm" }
                Flow { width: parent.width; spacing: 8
                    Button { text: "Giữ lại"; kind: "text"; enabled: !root.clearBusy; onClicked: root.clearing = false }
                    Button { text: "Dọn"; enabled: !root.clearBusy; onClicked: { root.clearBusy = true; Api.call("DELETE", "/api/readaloud/cache?all=1", null, function(data, error) { root.clearBusy = false; if (!error) { root.cache = data; root.clearing = false; Api.notice = "Đã dọn bản đọc đã làm" } }) } }
                }
            }
        }
        SectionBlock {
            width: parent.width; title: "Chẩn đoán"; fold: true
            SettingRow { width: parent.width; label: "Xem lại trước khi gửi; bạn tự gửi đi."; Button { text: "Gửi nhật ký"; kind: "text"; icon: "save"; onClicked: folders.choose("diagnostics") } }
            SectionBlock { width: parent.width; title: "Tìm hiểu thêm"; fold: true; FormLabel { width: parent.width; text: "Gồm thông tin máy và nhật ký gần nhất; tự che khoá, mã ghép, đường dẫn và IP nhận ra được."; color: Theme.text2 } }
        }
        SectionBlock {
            width: parent.width; title: "Giới thiệu"; fold: true
            FormLabel { width: parent.width; text: "ABook " + (Api.info.version || "") + " - nghe sách tiếng Việt và làm sách nói."; color: Theme.text2 }
            FormLabel { width: parent.width; text: "Mã nguồn mở (MIT):"; color: Theme.text2 }
            Button { kind: "text"; text: "github.com/ntanhpro1221/ABook"; onClicked: Qt.openUrlExternally("https://github.com/ntanhpro1221/ABook/") }
            SectionBlock { width: parent.width; title: "Thành phần sử dụng"; fold: true; FormLabel { width: parent.width; text: thirdParty.text; color: Theme.text2 } }
        }
    }
    NativeFolders { id: folders }
    ThirdPartyText { id: thirdParty }
}

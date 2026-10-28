import QtQuick
import ABook
import "VoiceLogic.js" as VoiceLogic

// Nhóm "Giọng đọc" (VoiceGroup của desktop/SettingsScreen.tsx + listen/VoiceSettings.tsx): giọng mặc định của "Nghe ngay", nghe thử từng giọng, lời nói rõ
// chữ của sách đi đâu với từng nhóm giọng trực tuyến, "Bộ giọng" (tải VieNeu / Supertonic), "Hiệu năng" và phần gập "Khoá trực tuyến" ở cuối. Mọi thứ
// nằm trong một mục py-3.5 của khối phẳng, cách nhau 20 (grid gap-5): khoảng cách đặt TRONG từng khối gập (VoiceBlock) nên khối hiện / ẩn thì
// khoảng cách cũng mở / khép cùng nhịp. Giọng mặc định lưu bằng Api.chooseDefaultVoice (cùng chỗ với tên giọng ở trang gốc Cài đặt).
Column {
    id: root
    property var voices: null                      // null: đang tải
    property var providers: []
    property string loadError: ""
    property string playing: ""
    property string loading: ""
    property string failedVoice: ""
    property string failedMessage: ""
    property int turn: 0
    property bool keysOpen: Platform.setting("fold.voice.keys", "0") === "1"
    readonly property string chosen: Api.defaultVoice
    readonly property var current: voices && voices.length ? VoiceLogic.resolveVoice(voices, chosen) : undefined
    readonly property int keyCount: providers.filter(info => info.hasKey).length
    property string keptName: ""                   // tên giọng giữ lại lúc dòng "Đang dùng" khép
    onCurrentChanged: if (current) keptName = current.name

    function load() {
        Api.quiet("GET", "/api/readaloud/voices", null, function(data, error) {
            if (error || !Array.isArray(data)) { root.loadError = error || VoiceLogic.LOAD_ERROR; return }
            root.voices = data
            root.loadError = ""
            Api.voiceList = data
            Api.refreshVoiceName()
        })
        Api.quiet("GET", "/api/readaloud/online", null, function(data, error) { root.syncProviders(!error && Array.isArray(data) ? data : []) })
    }
    // Danh sách khung khoá giữ nguyên khung (trạng thái nhập dở, gập / mở) khi chỉ nội dung đổi
    function syncProviders(list) {
        const ids = list.map(info => info.id)
        let same = ids.length === providerIds.count
        for (let i = 0; same && i < ids.length; ++i) same = providerIds.get(i).pid === ids[i]
        if (!same) {
            providerIds.clear()
            for (const id of ids) providerIds.append({pid: id})
        }
        providers = list
    }
    function chooseVoice(id) { Api.chooseDefaultVoice(id) }
    // Mũi tên / Home / End đổi chọn trong nhóm rồi đưa tiêu điểm tới giọng ấy (radioGroupKeys: vòng lại ở hai đầu)
    function move(ids, from, direction) {
        if (!ids.length) return
        const index = ids.indexOf(current ? current.id : "")
        const next = index < 0 ? (direction > 0 ? 0 : ids.length - 1) : (index + direction + ids.length) % ids.length
        pick(ids, ids[next])
    }
    function pick(ids, id) {
        chooseVoice(id)
        Qt.callLater(function() { root.focusVoice(stack, id) })
    }
    function focusVoice(item, id) {
        if (!item) return false
        if (item.voiceId === id && item.radio) { item.radio.forceActiveFocus(Qt.TabFocusReason); return true }
        for (let i = 0; i < item.children.length; ++i) if (focusVoice(item.children[i], id)) return true
        return false
    }

    // ---- nghe thử (useVoiceSample): mỗi lần bấm là một lượt mới, mẫu của lượt cũ về muộn bị bỏ ----
    function stopSample() {
        turn++
        DesktopApi.stopPreview()
        playEnd.stop()
        playing = ""
        loading = ""
    }
    function playSample(id) {
        stopSample()
        const mine = turn
        failedVoice = ""
        failedMessage = ""
        loading = id
        Api.quiet("POST", "/api/readaloud/clip", {voice: id, text: VoiceLogic.SAMPLE_TEXT}, function(data, error) {
            if (root.turn !== mine) return
            root.loading = ""
            if (error || !data || !data.url) {
                root.playing = ""
                root.failedVoice = id
                root.failedMessage = error || "Không làm được lúc này."
                return
            }
            DesktopApi.preview(data.url)
            root.playing = id
            playEnd.interval = Math.max(500, (data.duration_ms || 8000) + 300)
            playEnd.restart()
        })
    }
    Timer { id: playEnd; onTriggered: root.playing = "" }
    Component.onCompleted: load()
    Component.onDestruction: if (playing !== "" || loading !== "") DesktopApi.stopPreview()
    ListModel { id: providerIds }

    SectionBlock {
        width: parent.width
        SettingsItem {
            width: parent.width
            // Khối nào cũng mang khoảng cách 20 phía trên; khối đầu tiên bỏ nó đi bằng cách dịch cột lên 20
            Item {
                width: parent.width
                height: stack.height - 20
                Column {
                    id: stack
                    y: -20
                    width: parent.width

                    // Không tải được danh sách giọng (InlineError)
                    VoiceBlock {
                        width: parent.width
                        gap: 20
                        show: root.loadError !== ""
                        Item {
                            width: parent.width
                            height: errorFlow.height + 24
                            Icon { name: "triangle-alert"; size: 16; color: Theme.danger; x: 0; y: 12 + (Theme.buttonHeight - 16) / 2 }
                            VoiceFlex {
                                id: errorFlow
                                x: 28
                                y: 12
                                width: parent.width - 28
                                spacing: 0
                                Text {
                                    objectName: "voiceLoadError"
                                    text: VoiceLogic.LOAD_ERROR
                                    color: Theme.text2
                                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                    font.pixelSize: Theme.sizeBodySmall
                                    rightPadding: 12
                                }
                                Button { objectName: "voiceLoadRetry"; text: "Thử lại"; icon: "rotate-cw"; size: "sm"; kind: "text"; onClicked: root.load() }
                            }
                        }
                    }

                    // Giọng đang dùng
                    VoiceBlock {
                        width: parent.width
                        gap: 20
                        show: root.current !== undefined
                        Text {
                            objectName: "voiceCurrent"
                            width: parent.width
                            text: "Đang dùng: " + root.keptName
                            color: Theme.text
                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                            font.pixelSize: Theme.sizeBodySmall
                            font.weight: Theme.weightMedium
                        }
                    }

                    // Khung chờ đúng hình danh sách (ContentSkeleton "Đang tải giọng đọc"): ba hàng, nhịp mờ 0,6 <-> 1
                    VoiceBlock {
                        width: parent.width
                        gap: 20
                        show: root.voices === null && root.loadError === ""
                        Column {
                            id: skeleton
                            objectName: "voiceSkeleton"
                            width: parent.width
                            spacing: 16
                            Accessible.role: Accessible.Indicator
                            Accessible.name: "Đang tải giọng đọc"
                            SequentialAnimation {
                                running: skeleton.visible && Nav.uiVisible && !Theme.reduceMotion
                                loops: Animation.Infinite
                                OpacityAnimator { target: skeleton; from: 1; to: 0.6; duration: 800; easing.type: Easing.InOutSine }
                                OpacityAnimator { target: skeleton; from: 0.6; to: 1; duration: 800; easing.type: Easing.InOutSine }
                            }
                            Repeater {
                                model: 3
                                Item {
                                    width: skeleton.width
                                    height: 40
                                    Rectangle { width: 40; height: 40; radius: Theme.radiusControl; color: Theme.line }
                                    Rectangle { x: 52; y: 8; width: (parent.width - 52) * 0.75; height: 12; radius: Theme.radiusControl; color: Theme.line }
                                    Rectangle { x: 52; y: 28; width: (parent.width - 52) * 0.5; height: 12; radius: Theme.radiusControl; color: Theme.line }
                                }
                            }
                        }
                    }

                    // Mỗi nhà cung cấp một khối gập; nhóm rỗng bỏ qua (trừ "Giọng của máy": còn câu hướng dẫn cài giọng)
                    Repeater {
                        model: VoiceLogic.GROUPS
                        VoiceBlock {
                            id: groupBlock
                            required property var modelData
                            readonly property var list: root.voices ? root.voices.filter(voice => voice.provider === modelData.provider) : []
                            readonly property var ids: VoiceLogic.orderedIds(list)
                            readonly property string tabId: ids.indexOf(root.current ? root.current.id : "") >= 0 ? root.current.id : (ids.length ? ids[0] : "")
                            readonly property string notice: modelData.provider === "edge" ? VoiceLogic.ONLINE_NOTICE : (list.length ? VoiceLogic.onlineNotice(list[0]) : "")
                            width: parent.width
                            gap: 20
                            show: root.voices !== null && (list.length > 0 || modelData.provider === "device")
                            VoiceFold {
                                width: parent.width
                                storageKey: "voice.provider." + groupBlock.modelData.provider
                                title: groupBlock.modelData.title
                                summary: (groupBlock.modelData.detail ? groupBlock.modelData.detail + " · " : "") + groupBlock.list.length + " giọng"
                                         + (root.current && root.current.provider === groupBlock.modelData.provider ? " · đang dùng" : "")
                                // Chưa có giọng nào của nhóm (máy chưa cài giọng tiếng Việt của hệ điều hành)
                                VoiceNote { width: parent.width; gap: 0; text: groupBlock.list.length === 0 ? VoiceLogic.DEVICE_HINT : ""; px: 13 }
                                Column {
                                    width: parent.width
                                    Accessible.role: Accessible.Grouping
                                    Accessible.name: VoiceLogic.groupLabel(groupBlock.modelData)
                                    Repeater {
                                        model: VoiceLogic.voiceSections(groupBlock.list)
                                        Column {
                                            id: section
                                            required property var modelData
                                            width: parent.width
                                            Text {
                                                width: parent.width
                                                topPadding: 8
                                                bottomPadding: 2
                                                height: section.modelData.label ? implicitHeight : 0
                                                text: section.modelData.label || ""
                                                color: Theme.text2
                                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                                font.pixelSize: 13
                                                font.weight: Theme.weightMedium
                                            }
                                            Repeater {
                                                model: section.modelData.voices
                                                VoiceRow {
                                                    required property var modelData
                                                    required property int index
                                                    width: section.width
                                                    voice: modelData.voice
                                                    shown: modelData.shown
                                                    first: index === 0
                                                    selected: root.current !== undefined && modelData.voice.id === root.current.id
                                                    tabbable: modelData.voice.id === groupBlock.tabId
                                                    playing: root.playing === modelData.voice.id
                                                    loading: root.loading === modelData.voice.id
                                                    failure: root.failedVoice === modelData.voice.id ? root.failedMessage : ""
                                                    onChoose: root.chooseVoice(modelData.voice.id)
                                                    onSample: { if (playing) root.stopSample(); else root.playSample(modelData.voice.id) }
                                                    onStep: direction => root.move(groupBlock.ids, modelData.voice.id, direction)
                                                    onJump: end => root.pick(groupBlock.ids, end ? groupBlock.ids[groupBlock.ids.length - 1] : groupBlock.ids[0])
                                                }
                                            }
                                        }
                                    }
                                }
                                // Chữ của sách đi đâu với nhóm giọng này
                                VoiceNote { width: parent.width; gap: 4; text: groupBlock.list.length > 0 ? groupBlock.notice : ""; px: Theme.sizeCaption }
                            }
                        }
                    }

                    // Bộ giọng + Hiệu năng
                    VoiceBlock {
                        width: parent.width
                        gap: 20
                        show: true
                        VoiceModules {
                            id: modules
                            width: parent.width
                            onChanged: { root.load(); speed.refresh() }
                            onSwitched: voice => Api.chooseDefaultVoice(voice)
                        }
                    }
                    VoiceBlock {
                        width: parent.width
                        gap: 20
                        show: speed.ready
                        VoiceSpeed { id: speed; width: parent.width; supertonic: modules.supertonic }
                    }

                    // Khoá trực tuyến: hiếm dùng, gập sẵn, nhớ lựa chọn; số khoá luôn thấy ở đầu mục
                    VoiceBlock {
                        width: parent.width
                        gap: 20
                        show: root.providers.length > 0
                        Column {
                            width: parent.width
                            DisclosureRow {
                                objectName: "voiceKeysHeader"
                                width: parent.width
                                section: true
                                title: "Khoá trực tuyến"
                                summary: root.keyCount > 0 ? root.keyCount + " khoá" : ""
                                expanded: root.keysOpen
                                onClicked: {
                                    root.keysOpen = !root.keysOpen
                                    Platform.setSetting("fold.voice.keys", root.keysOpen ? "1" : "0")
                                }
                            }
                            Collapse {
                                width: parent.width
                                open: root.keysOpen
                                Text {
                                    width: parent.width
                                    topPadding: 4
                                    text: "Chữ của sách gửi tới dịch vụ ấy; có thể bị tính tiền."
                                    color: Theme.text2
                                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                    font.pixelSize: 13
                                }
                                MoreInfo {
                                    width: parent.width
                                    topPadding: 4
                                    HintText { width: parent.width; text: "Khoá chỉ lưu trên máy. Dịch vụ có thể tính phí; lỗi khoá thì tạm dùng Edge hoặc giọng máy." }
                                }
                                Column {
                                    width: parent.width
                                    topPadding: 12
                                    spacing: 12
                                    Repeater {
                                        model: providerIds
                                        ProviderKey {
                                            required property string pid
                                            width: parent.width
                                            info: root.providers.find(item => item.id === pid) || ({limits: {}})
                                            onChanged: root.load()
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

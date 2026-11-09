import "UiStrings.js" as S
import QtQuick
import ABook
import "StudioSetupLogic.js" as Setup

// Cài đặt › Studio › "Máy này" (StudioSettings của studio/StudioSetup.tsx + studio/studioFit.ts): Studio ở đâu, chạy trên card nào; chưa cài thì
// cần gì, máy có đủ không, và Cài / Xem tiến độ cài. Gỡ là xoá 15-20 GB nên bấm hai lần: lần đầu "Xác nhận gỡ" (6 giây, hoặc Back / Esc
// để huỷ - lớp Back riêng), lần hai mới gỡ. Tiến độ cài hiện ở màn Studio (`studioRequested`), ở đây chỉ nói "Đang cài.".
Item {
    id: root
    UiActivity { target: root; id: activity; onResumed: setup.load() }
    // Tình trạng + lệnh cài / gỡ nằm ở StudioSetupState (dùng chung với thẻ "Cài Studio" ở màn Dự án)
    StudioSetupState { id: setup; wanted: activity.running || setup.status === null }   // 1.ª lần luôn hỏi (khối còn ẩn tới khi có đáp), sau đó chỉ hỏi lại khi cửa sổ hiện
    property bool armed: false
    readonly property alias busy: setup.busy
    signal studioRequested()
    readonly property var status: setup.status
    readonly property bool present: Boolean(Api.info && Api.info.studio) && status !== null
    readonly property bool installed: setup.installed
    readonly property var fit: setup.fit || Setup.studioFit(null)
    readonly property string needs: Setup.STUDIO_NEEDS
    implicitHeight: present ? column.height : 0
    height: implicitHeight
    visible: present || column.height > 0
    objectName: "studioSettings"

    function noStudioLine(reason) { return Setup.noStudioLine(reason) }
    function load() { setup.load() }

    // Bấm là cài luôn rồi sang màn Studio xem tiến độ - không phải bấm "Cài Studio" lần hai ở đó
    function install() {
        setup.install(function(ok, data) {
            if (!ok) { setup.failure(S.s_chua_cai_duoc_studio_ee5900df, data); return }
            studioRequested()
        })
    }
    function remove() {
        if (!armed) { arm(true); return }
        arm(false)
        setup.remove(function(ok, data) {
            if (!ok) { setup.failure(S.s_chua_go_duoc_studio_1b3d65b8, data); return }
            Api.notice = S.s_da_go_studio_63706a8a
            setup.refreshInfo()
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
                        text: S.s_studio_tren_may_nay_e2fb04aa
                        color: Theme.text
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeSection
                        font.weight: Theme.weightMedium
                    }
                    Text { objectName: "studioState"; width: parent.width; topPadding: 4; text: root.status && root.status.running ? S.s_dang_cai_4ea651d1 : S.s_chua_cai_6003057a; color: Theme.text; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
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
                            text: running ? S.s_xem_tien_do_cai_42e94c00 : unfit ? S.s_van_cai_ef098464 : S.s_cai_studio_5fdd3bd9
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
                label: S.s_studio_tren_may_nay_e2fb04aa
                hint: S.s_da_cai_e0159635 + (root.status && root.status.gpu ? "\u00a0·\u00a0" + root.status.gpu.name : "") + "\n" + (root.status ? root.status.root : "")
                Button {
                    objectName: "studioRemove"
                    size: "sm"
                    kind: root.armed ? "danger" : "ghost"
                    icon: "trash"
                    text: root.busy ? S.s_dang_go_063a61fd : root.armed ? S.s_xac_nhan_go_80920dda : S.s_go_studio_832e6f10
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
                        text: (outdated.damaged ? S.s_mat_185abbd8 + root.status.damaged.join(", ") + S.s_file_da_bi_xoa_hay_hong_bbfea488 : S.s_can_cap_nhat_1655056f + ((root.status && root.status.outdated) || []).join(", ")) + " - "
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
                            text: outdated.damaged ? S.s_sua_studio_2f99394d : S.s_cap_nhat_studio_b3acc7e7
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
                    text: S.s_xoa_runtime_model_1520_gb_giu_sach_va_ho_s_66d08224
                    lineHeight: 1.15
                }
            }
        }
    }
}

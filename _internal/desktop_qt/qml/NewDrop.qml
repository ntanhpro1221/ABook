import "UiStrings.js" as S
import QtQuick
import QtQuick.Shapes
import ABook
import "NewProjectLogic.js" as Logic
import "UploadLogic.js" as Upload

// Khung nét đứt khi chưa có chương nào (SourceStep của NewProjectScreen.tsx): chọn / kéo thả thư mục truyện hay file sách; Studio của máy khác thì gửi chương lên
// (nút "Chọn file" / "Chọn thư mục" + thanh tiến độ + "Huỷ gửi"). Dán đường dẫn (máy này; lui vào "Dán đường dẫn" khi gửi chương), lời báo khi nguồn không đọc được và
// các thư mục con gợi ý chọn. Khung sáng lên khi đang kéo file vào.
Item {
    id: root
    property var form: null
    property bool dragging: false
    property bool advanced: false
    property string typed: ""
    signal folderRequested()
    signal filesRequested()

    readonly property bool browser: form ? form.browser : false
    readonly property bool dialogs: form ? form.dialogs : false
    readonly property var problem: form ? form.problem : null
    readonly property bool narrow: width < 480
    readonly property real pad: narrow ? 16 : 32
    readonly property real inner: box.width - 2 * pad
    readonly property bool busy: Boolean(form && (form.scanning || form.uploading))
    readonly property string path: Logic.cleanPath(typed)
    implicitHeight: 24 + box.height
    height: implicitHeight

    function submitPath() { if (path !== "" && form) form.setPaths([path]) }

    Rectangle {
        id: box
        objectName: "newDropBox"
        y: 24
        width: parent.width
        height: content.height + 80
        radius: Theme.radiusCover
        color: root.dragging ? Theme.accentSoft : Theme.panel
        Behavior on color { ColorAnimation { duration: Theme.motionFast } }
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: root.dragging ? Theme.accent : Theme.controlLine
                strokeWidth: 2
                fillColor: "transparent"
                strokeStyle: ShapePath.DashLine
                dashPattern: [4, 3]
                PathRectangle { x: 1; y: 1; width: box.width - 2; height: box.height - 2; radius: Theme.radiusCover }
            }
        }
        Column {
            id: content
            x: root.pad
            y: 40
            width: root.inner
            Rectangle {
                x: (parent.width - width) / 2
                width: 56; height: 56
                radius: Theme.radiusCover
                color: Theme.accentSoft
                Icon {
                    id: spinner
                    anchors.centerIn: parent
                    name: root.busy ? "loader-circle" : "folder-input"
                    size: 28
                    color: Theme.accentText
                    RotationAnimator on rotation { running: root.busy && Nav.uiVisible && !Theme.reduceMotion; from: 0; to: 360; duration: Theme.spinMs; loops: Animation.Infinite }
                    onNameChanged: rotation = 0
                }
            }
            Item { width: 1; height: 16 }
            Prose {
                objectName: "newDropTitle"
                strong: true
                tone: Theme.text
                horizontalAlignment: Text.AlignHCenter
                font.pixelSize: Theme.sizeBody
                font.weight: Theme.weightMedium
                text: root.form && root.form.scanning ? S.s_dang_doc_cac_chuong_fe5fd08f
                    : root.browser ? S.s_chon_hay_keo_tha_vao_day_cac_chuong_cua_tr_77883a5f
                    : S.s_chon_hay_keo_tha_vao_day_thu_muc_truyen_ha_978b59fe
            }
            Item { width: 1; height: 4 }
            Prose {
                objectName: "newDropHint"
                horizontalAlignment: Text.AlignHCenter
                text: root.browser ? S.s_cac_file_txt_hay_ca_thu_muc_hoac_mot_file_093d722b + Upload.UPLOAD_LIMIT / Math.pow(2, 20) + S.s_mb_moi_file_af437f1b
                                   : S.s_chi_lay_file_nam_ngay_trong_thu_muc_khong_29e37f3e
            }
            // Gửi chương từ máy này (Studio của máy khác)
            Item {
                Reveal { shown: root.browser }
                width: parent.width
                height: visible ? 24 + browseRow.height : 0
                Row {
                    id: browseRow
                    y: 24
                    x: (parent.width - width) / 2
                    spacing: 8
                    Button { objectName: "newUploadFiles"; text: S.s_chon_file_f43fd47b; icon: "upload"; enabled: !root.form || !root.form.uploading; onActivated: root.filesRequested() }
                    Button { objectName: "newUploadFolder"; text: S.s_chon_thu_muc_1fe47e38; icon: "folder"; kind: "ghost"; enabled: !root.form || !root.form.uploading; onActivated: root.folderRequested() }
                }
            }
            // Tiến độ gửi chương
            Column {
                objectName: "newUploadProgress"
                Reveal { shown: Boolean(root.form && root.form.uploading) }
                x: (parent.width - width) / 2
                width: Math.min(parent.width, 320)
                topPadding: visible ? 16 : 0
                spacing: 8
                StudioBar {
                    width: parent.width
                    size: "sm"
                    value: root.form && root.form.uploading && root.form.uploading.totalBytes ? root.form.uploading.bytes / root.form.uploading.totalBytes : 0
                    indeterminate: !(root.form && root.form.uploading && root.form.uploading.totalBytes)
                    label: S.s_dang_gui_cac_chuong_d7b47553
                }
                Prose { objectName: "newUploadLabel"; small: true; horizontalAlignment: Text.AlignHCenter; text: root.form && root.form.uploading ? Upload.progressLabel(root.form.uploading) : "" }
                Item {
                    width: parent.width
                    height: cancelUpload.height
                    Button {
                        id: cancelUpload
                        objectName: "newUploadCancel"
                        x: (parent.width - width) / 2
                        text: root.form && root.form.stopping ? S.s_dang_dung_2fb8aa7c : S.s_huy_gui_4d53a582
                        kind: "ghost"
                        size: "sm"
                        enabled: !(root.form && root.form.stopping)
                        onActivated: root.form.cancelUpload()
                    }
                }
            }
            // Hộp chọn của máy này
            Item {
                Reveal { shown: root.dialogs && !root.browser }
                width: parent.width
                height: visible ? 24 + dialogRow.height : 0
                Row {
                    id: dialogRow
                    y: 24
                    x: (parent.width - width) / 2
                    spacing: 8
                    Button { objectName: "newPickFolder"; text: S.s_chon_thu_muc_1fe47e38; icon: "folder"; onActivated: root.folderRequested() }
                    Button { objectName: "newPickFiles"; text: S.s_chon_tung_file_c6f96077; icon: "file-text"; kind: "ghost"; onActivated: root.filesRequested() }
                }
            }
            // Dán đường dẫn: Studio từ xa không có đường dẫn nào của máy tính để dán
            Item {
                Reveal { shown: !(root.form && root.form.remote) && root.browser && !root.advanced }
                width: parent.width
                height: visible ? 20 + pasteLink.height : 0
                TextLink { id: pasteLink; objectName: "newPasteLink"; y: 20; x: (parent.width - width) / 2; text: S.s_dan_duong_dan_2ae49bc1; small: true; onClicked: root.advanced = true }
            }
            Column {
                Reveal { shown: !(root.form && root.form.remote) && !(root.browser && !root.advanced) }
                x: (parent.width - width) / 2
                width: Math.min(parent.width, 512)
                topPadding: visible ? 20 : 0
                spacing: 8
                Row {
                    width: parent.width
                    spacing: 8
                    FormField {
                        id: pathField
                        objectName: "newPathField"
                        width: parent.width - pasteButton.width - 8
                        label: S.s_duong_dan_thu_muc_d8f9678b
                        placeholderText: root.dialogs ? S.s_hoac_dan_duong_dan_bb4837f7 : S.s_dan_duong_dan_thu_muc_hay_file_40ebc3a2
                        invalid: Boolean(root.problem)
                        onTextChanged: root.typed = text
                        onAccepted: root.submitPath()
                    }
                    Button {
                        id: pasteButton
                        objectName: "newPathGo"
                        text: S.s_lay_chuong_8869b554
                        enabled: root.path !== "" && !(root.form && root.form.scanning)
                        onActivated: root.submitPath()
                    }
                }
                Prose { Reveal { shown: !root.dialogs } small: true; tone: Theme.text3; text: S.s_vi_du_d_truyen_ten_truyen_d4c4a6e8 }
            }
            // Nguồn không đọc được
            Column {
                objectName: "newSourceProblem"
                Reveal { shown: Boolean(root.problem) }
                x: (parent.width - width) / 2
                width: Math.min(parent.width, 512)
                topPadding: visible ? 12 : 0
                spacing: 8
                Prose { objectName: "newSourceProblemText"; tone: Theme.danger; text: root.problem ? root.problem.text : "" }
                Column {
                    width: parent.width
                    Reveal { shown: Boolean(root.problem) && root.problem.subfolders.length > 0 }
                    spacing: 4
                    Prose { text: S.s_co_le_nen_chon_thu_muc_con_b36394ab }
                    // Light novel ra từng tập, mỗi tập một thư mục: chọn cả bộ một lần; bước sau ĐỀ XUẤT chia tập, người dùng bấm mới chia.
                    Interactive {
                        Reveal { shown: Boolean(root.problem) && root.problem.subfolders.length > 1 }
                        objectName: "newPickAllFolders"
                        width: parent.width
                        height: visible ? Math.max(40, allText.height + 16) : 0
                        Accessible.role: Accessible.Button
                        Accessible.name: allText.text
                        onClicked: root.form.setPaths(root.problem.subfolders)
                        Icon { x: 0; anchors.verticalCenter: parent.verticalCenter; name: "layers"; size: 16; color: Theme.accentText }
                        Text {
                            id: allText
                            x: 24; width: parent.width - 24
                            anchors.verticalCenter: parent.verticalCenter
                            text: root.problem ? S.s_chon_345d435d + root.problem.subfolders.length + S.s_tap_269b0b3d : ""
                            color: Theme.accentText
                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                            font.pixelSize: Theme.sizeBodySmall
                            font.weight: Theme.weightMedium
                        }
                    }
                    Repeater {
                        model: root.problem ? root.problem.subfolders.slice(0, 8) : []
                        delegate: Interactive {
                            required property string modelData
                            objectName: "newSubfolder"
                            width: parent.width
                            height: Math.max(40, folderText.height + 16)
                            Accessible.role: Accessible.Button
                            Accessible.name: Logic.sourceName(modelData)
                            onClicked: root.form.setPaths([modelData])
                            Icon { x: 0; anchors.verticalCenter: parent.verticalCenter; name: "folder"; size: 16; color: Theme.text2 }
                            // Tên thư mục đứng trước: hai thư mục "Tập 1", "Tập 2" cùng một đường dẫn dài thì đuôi nhìn y hệt nhau.
                            Text {
                                id: folderText
                                x: 24; width: parent.width - 24
                                anchors.verticalCenter: parent.verticalCenter
                                textFormat: Text.StyledText
                                text: "<b>" + Logic.esc(Logic.sourceName(modelData)) + "</b>" +
                                    (Logic.isSourceRef(modelData) ? "" : " <font color=\"" + Theme.text3 + "\">" + Logic.esc(modelData) + "</font>")
                                color: Theme.accentText
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                font.pixelSize: Theme.sizeBodySmall
                            }
                        }
                    }
                    Prose { Reveal { shown: Boolean(root.problem) && root.problem.subfolders.length > 8 } text: S.s_va_6e638075 + (root.problem ? root.problem.subfolders.length - 8 : 0) + S.s_thu_muc_nua_deu_nam_trong_dung_ca_o_tren_ea2063d1 }
                }
            }
        }
    }
}

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
                    RotationAnimator on rotation { running: root.busy && Nav.uiVisible && !Theme.reduceMotion; from: 0; to: 360; duration: 1000; loops: Animation.Infinite }
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
                text: root.form && root.form.scanning ? "Đang đọc các chương…"
                    : root.browser ? "Chọn hay kéo thả vào đây các chương của truyện"
                    : "Chọn hay kéo thả vào đây thư mục truyện, hay một file EPUB, DOCX, PDF"
            }
            Item { width: 1; height: 4 }
            Prose {
                objectName: "newDropHint"
                horizontalAlignment: Text.AlignHCenter
                text: root.browser ? "Các file .txt hay cả thư mục, hoặc một file .epub / .docx / .pdf, tới " + Upload.UPLOAD_LIMIT / Math.pow(2, 20) + " MB mỗi file."
                                   : "Chỉ lấy file nằm ngay trong thư mục, không quét thư mục con."
            }
            // Gửi chương từ máy này (Studio của máy khác)
            Item {
                visible: root.browser
                width: parent.width
                height: visible ? 24 + browseRow.height : 0
                Row {
                    id: browseRow
                    y: 24
                    x: (parent.width - width) / 2
                    spacing: 8
                    Button { objectName: "newUploadFiles"; text: "Chọn file"; icon: "upload"; enabled: !root.form || !root.form.uploading; onActivated: root.filesRequested() }
                    Button { objectName: "newUploadFolder"; text: "Chọn thư mục"; icon: "folder"; kind: "ghost"; enabled: !root.form || !root.form.uploading; onActivated: root.folderRequested() }
                }
            }
            // Tiến độ gửi chương
            Column {
                objectName: "newUploadProgress"
                visible: Boolean(root.form && root.form.uploading)
                x: (parent.width - width) / 2
                width: Math.min(parent.width, 320)
                topPadding: visible ? 16 : 0
                spacing: 6
                StudioBar {
                    width: parent.width
                    size: "sm"
                    value: root.form && root.form.uploading && root.form.uploading.totalBytes ? root.form.uploading.bytes / root.form.uploading.totalBytes : 0
                    label: "Đang gửi các chương"
                }
                Prose { objectName: "newUploadLabel"; small: true; horizontalAlignment: Text.AlignHCenter; text: root.form && root.form.uploading ? Upload.progressLabel(root.form.uploading) : "" }
                Item {
                    width: parent.width
                    height: cancelUpload.height
                    Button {
                        id: cancelUpload
                        objectName: "newUploadCancel"
                        x: (parent.width - width) / 2
                        text: root.form && root.form.stopping ? "Đang dừng…" : "Huỷ gửi"
                        kind: "ghost"
                        size: "sm"
                        enabled: !(root.form && root.form.stopping)
                        onActivated: root.form.cancelUpload()
                    }
                }
            }
            // Hộp chọn của máy này
            Item {
                visible: root.dialogs && !root.browser
                width: parent.width
                height: visible ? 24 + dialogRow.height : 0
                Row {
                    id: dialogRow
                    y: 24
                    x: (parent.width - width) / 2
                    spacing: 8
                    Button { objectName: "newPickFolder"; text: "Chọn thư mục"; icon: "folder"; onActivated: root.folderRequested() }
                    Button { objectName: "newPickFiles"; text: "Chọn từng file"; icon: "file-text"; kind: "ghost"; onActivated: root.filesRequested() }
                }
            }
            // Dán đường dẫn: Studio từ xa không có đường dẫn nào của máy tính để dán
            Item {
                visible: !(root.form && root.form.remote) && root.browser && !root.advanced
                width: parent.width
                height: visible ? 20 + pasteLink.height : 0
                TextLink { id: pasteLink; objectName: "newPasteLink"; y: 20; x: (parent.width - width) / 2; text: "Dán đường dẫn"; small: true; onClicked: root.advanced = true }
            }
            Column {
                visible: !(root.form && root.form.remote) && !(root.browser && !root.advanced)
                x: (parent.width - width) / 2
                width: Math.min(parent.width, 512)
                topPadding: visible ? 20 : 0
                spacing: 6
                Row {
                    width: parent.width
                    spacing: 8
                    FormField {
                        id: pathField
                        objectName: "newPathField"
                        width: parent.width - pasteButton.width - 8
                        label: "Đường dẫn thư mục"
                        placeholderText: root.dialogs ? "…hoặc dán đường dẫn" : "Dán đường dẫn thư mục hay file"
                        invalid: Boolean(root.problem)
                        onTextChanged: root.typed = text
                        onAccepted: root.submitPath()
                    }
                    Button {
                        id: pasteButton
                        objectName: "newPathGo"
                        text: "Lấy chương"
                        enabled: root.path !== "" && !(root.form && root.form.scanning)
                        onActivated: root.submitPath()
                    }
                }
                Prose { visible: !root.dialogs; small: true; tone: Theme.text3; text: "Ví dụ: D:\\Truyện\\Tên truyện" }
            }
            // Nguồn không đọc được
            Column {
                objectName: "newSourceProblem"
                visible: Boolean(root.problem)
                x: (parent.width - width) / 2
                width: Math.min(parent.width, 512)
                topPadding: visible ? 12 : 0
                spacing: 8
                Prose { objectName: "newSourceProblemText"; tone: Theme.danger; text: root.problem ? root.problem.text : "" }
                Column {
                    width: parent.width
                    visible: Boolean(root.problem) && root.problem.subfolders.length > 0
                    spacing: 4
                    Prose { text: "Có lẽ nên chọn thư mục con:" }
                    // Light novel ra từng tập, mỗi tập một thư mục: chọn cả bộ một lần; bước sau ĐỀ XUẤT chia tập, người dùng bấm mới chia.
                    Interactive {
                        visible: Boolean(root.problem) && root.problem.subfolders.length > 1
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
                            text: root.problem ? "Chọn " + root.problem.subfolders.length + " tập" : ""
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
                    Prose { visible: Boolean(root.problem) && root.problem.subfolders.length > 8; text: "…và " + (root.problem ? root.problem.subfolders.length - 8 : 0) + " thư mục nữa (đều nằm trong “Dùng cả” ở trên)." }
                }
            }
        }
    }
}

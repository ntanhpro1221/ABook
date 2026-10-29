import QtQuick
import ABook
import "NewProjectLogic.js" as Logic
import "StudioLogic.js" as Studio

// "Chia thành nhiều tập" (VolumeSplit.tsx; abook/webui/volumes.py): máy ĐỀ XUẤT chỗ cắt (thư mục / EPUB / tiêu đề "Tập N"); không bấm thì cả truyện vẫn là MỘT sách.
// Bấm thì hiện danh sách phần: sửa chỗ cắt theo số chương, thêm, bỏ. Tạo xong: phần 1 là sách thường, các phần sau nối tiếp và tự chạy khi phần trước xong.
// Chỗ cắt lưu bằng đường dẫn file chương đầu của phần (sống sót qua việc bỏ chương); số chương chỉ là cách hiện và cách nhập.
Column {
    id: root
    property var form: null
    readonly property var draft: form ? form.draft : ({})
    readonly property var files: form && form.scan ? form.scan.files : []
    readonly property var proposal: form && form.rawScan ? form.rawScan.volumes : null
    readonly property bool applicable: files.length >= 2
    readonly property bool chosen: form ? form.splitting : false
    readonly property var starts: form ? form.volumeStarts : [1]
    readonly property var parts: Logic.ranges(starts, files.length)
    readonly property var titles: Logic.volumeTitles(String(draft.title || "").trim() || "Tên sách", parts.length)
    readonly property var proposed: {
        const map = {}
        for (const volume of (proposal ? proposal.volumes : [])) map[volume.startPath] = volume.label
        return map
    }
    // Đặt chỗ cắt theo số chương (từ 1) -> đường dẫn chương đầu mỗi phần; false khi số không hợp lệ
    function commit(next) {
        if (!next) return false
        form.update({volumeStarts: next.map(number => files[number - 1].path)})
        return true
    }

    // Chưa chia, máy không có đề xuất: một nút trơn
    Collapse {
        width: parent.width
        open: root.applicable && !root.chosen && !root.proposal
        Item {
            width: parent.width
            height: 16 + plain.height
            Button { id: plain; objectName: "newSplitPlain"; y: 16; text: "Chia thành nhiều phần"; icon: "layers"; kind: "ghost"; size: "sm"; onActivated: root.form.update({volumeStarts: [root.files[0].path]}) }
        }
    }
    // Chưa chia, máy đề xuất
    Collapse {
        width: parent.width
        open: root.applicable && !root.chosen && Boolean(root.proposal)
        NewNote {
            objectName: "newVolumeProposal"
            width: parent.width
            icon: "sparkles"
            tone: Theme.accentText
            Prose { strong: true; tone: Theme.text; text: root.proposal ? "Chia " + root.proposal.volumes.length + " phần?" : " " }
            Prose { text: "Nối các phần, giữ giọng và cách đọc tên." }
            MoreInfo {
                width: parent.width
                Prose {
                    small: true
                    text: {
                        if (!root.proposal) return " "
                        const shown = root.proposal.volumes.slice(0, 4)
                        return "Máy thấy " + Logic.SOURCE_TEXT[root.proposal.source] + ": " +
                            shown.map(volume => volume.label + " (" + Studio.formatNumber(volume.chapters) + " chương)").join(", ") +
                            (root.proposal.volumes.length > shown.length ? ", …" : "") + ". Chưa chia thì cả truyện là một sách. Mỗi phần tự bắt đầu sau phần trước; bạn sửa chỗ cắt bằng số chương."
                    }
                }
            }
            Item { width: 1; height: 6 }
            Button { objectName: "newSplitAccept"; text: "Chia thành nhiều phần"; icon: "layers"; kind: "ghost"; size: "sm"; onActivated: root.form.update({volumeStarts: root.proposal.volumes.map(volume => volume.startPath)}) }
        }
    }
    // Đang chia: danh sách phần
    Collapse {
        width: parent.width
        open: root.applicable && root.chosen
        Column {
            objectName: "newVolumeList"
            width: parent.width
            topPadding: 32
            Item {
                width: parent.width
                height: Math.max(heading.height, noMore.height)
                Row {
                    id: heading
                    spacing: 8
                    width: parent.width - noMore.width - 8
                    Icon { y: 3; name: "layers"; size: 16; color: Theme.accentText }
                    Prose { width: parent.width - 24; strong: true; tone: Theme.text; text: root.parts.length > 1 ? "Chia thành " + root.parts.length + " phần" : "Chia thành mấy phần?" }
                }
                Button { id: noMore; objectName: "newSplitCancel"; x: parent.width - width; text: "Không chia nữa"; kind: "ghost"; size: "sm"; onActivated: root.form.update({volumeStarts: null}) }
            }
            Prose { topPadding: 4; text: "Mỗi phần thành một sách nối tiếp; chọn chương bắt đầu để chia." }
            Item { width: 1; height: 12 }
            StudioRows {
                id: rowsList
                objectName: "newVolumeRows"
                width: parent.width
                keyField: "key"
                items: root.parts.map((part, index) => ({key: String(part.start), start: part.start, end: part.end, chapters: part.chapters, index: index, title: root.titles[index]}))
                delegate: Component {
                    Item {
                        id: row
                        property var modelData: ({key: "", start: 1, end: 1, chapters: 0, index: 0, title: ""})
                        readonly property bool wide: width >= 520
                        readonly property var first: root.files[modelData.start - 1]
                        width: parent ? parent.width : 0
                        height: 16 + Math.max(info.height, wide ? controls.height : info.height + 4 + controls.height)
                        Column {
                            id: info
                            y: 8
                            width: row.wide ? parent.width - controls.width - 12 : parent.width
                            Prose {
                                strong: false
                                tone: Theme.text
                                font.weight: Theme.weightMedium
                                textFormat: Text.StyledText
                                // Phần 1 giữ nguyên tên sách (là sách thường, như máy chủ đặt) - nên nói ra nó là phần 1
                                text: Logic.esc(row.modelData.title) + (row.modelData.index === 0 ? " <font color=\"" + Theme.text3 + "\" size=\"2\">phần 1</font>" : "")
                            }
                            Prose {
                                small: true
                                text: row.first ? Logic.esc((row.first.firstLine || row.first.name) + (root.proposed[row.first.path] ? " · " + root.proposed[row.first.path] : "")) : " "
                                textFormat: Text.StyledText
                            }
                            Prose {
                                visible: Logic.foldersIn(root.files.slice(row.modelData.start - 1, row.modelData.end)) > 1
                                small: true
                                tone: Theme.warning
                                // Dây chuyền xếp chương theo TÊN file: chương của hai thư mục trong một phần thì xen nhau (máy chủ từ chối khi tạo).
                                text: "Dời chỗ cắt về ranh giới thư mục để giữ thứ tự đọc."
                            }
                        }
                        Row {
                            id: controls
                            x: row.wide ? row.width - width : 0
                            y: row.wide ? 8 + (info.height - height) / 2 : 8 + info.height + 4
                            spacing: 12
                            Text { anchors.verticalCenter: parent.verticalCenter; text: "từ chương"; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall }
                            Item {
                                width: 64; height: 32
                                anchors.verticalCenter: parent.verticalCenter
                                Text { visible: row.modelData.index === 0; anchors.centerIn: parent; text: "1"; color: Theme.text; font.pixelSize: Theme.sizeBodySmall; font.features: { "tnum": 1 } }
                                NumberBox {
                                    visible: row.modelData.index > 0
                                    objectName: "newCutBox"
                                    width: 64
                                    value: row.modelData.start
                                    label: "Phần " + (row.modelData.index + 1) + " bắt đầu từ chương"
                                    commitWith: number => root.commit(Logic.moveStart(root.starts, row.modelData.index, number, root.files.length))
                                }
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                width: 90
                                horizontalAlignment: Text.AlignRight
                                text: Studio.formatNumber(row.modelData.chapters) + " chương"
                                color: Theme.text2
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                font.pixelSize: Theme.sizeCaption
                                font.features: { "tnum": 1 }
                            }
                            Item {
                                width: 32; height: 32
                                anchors.verticalCenter: parent.verticalCenter
                                IconButton {
                                    visible: row.modelData.index > 0
                                    objectName: "newCutRemove"
                                    anchors.fill: parent
                                    icon: "trash-2"
                                    iconSize: 16
                                    tip: "Gộp vào phần trước"
                                    Accessible.name: "Bỏ chỗ cắt trước " + row.modelData.title
                                    onClicked: root.commit(Logic.removeStart(root.starts, row.modelData.index))
                                }
                            }
                        }
                    }
                }
            }
            // Thêm chỗ cắt
            Item {
                width: parent.width
                height: 12 + addRow.height
                Flow {
                    id: addRow
                    y: 12
                    width: parent.width
                    spacing: 8
                    Text { height: 32; verticalAlignment: Text.AlignVCenter; text: "Cắt từ chương"; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall }
                    NumberBox {
                        id: addBox
                        objectName: "newCutAdd"
                        width: 112
                        mode: "add"
                        placeholderText: "từ 2 đến " + root.files.length
                        label: "Thêm phần từ chương"
                        commitWith: number => root.commit(Logic.addStart(root.starts, number, root.files.length))
                    }
                    Button {
                        objectName: "newCutAddButton"
                        text: "Thêm"
                        icon: "plus"
                        kind: "ghost"
                        size: "sm"
                        enabled: addBox.text.trim() !== ""
                        onActivated: addBox.commitNow()
                    }
                    Text {
                        objectName: "newCutError"
                        visible: addBox.bad
                        width: Math.min(implicitWidth, addRow.width)
                        text: root.starts.length >= 99 ? "Tối đa 99 phần." : "Chương này đã là chỗ cắt, hay không nằm trong 2 – " + root.files.length + "."
                        color: Theme.danger
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: Theme.sizeBodySmall
                    }
                }
            }
        }
    }
}

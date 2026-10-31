import QtQuick
import ABook
import "NameLogic.js" as N

// Cách đọc chung khác cách cuốn này đang đọc (SharedReadingsOffer của sharedReadings.tsx): một dòng nói cái gì sẽ đổi thành cái gì + một nút dùng hết. Không có gì khác thì không hiện.
Collapse {
    id: root
    objectName: "sharedOffer"
    property var work: null
    property bool busy: false
    readonly property var entries: work && work.offer.data && work.offer.data.entries ? work.offer.data.entries : []
    property var held: []
    onEntriesChanged: if (entries.length > 0) held = entries
    open: entries.length > 0

    Item {
        width: root.width
        height: 12 + Math.max(line.height, apply.height) + 8
        Flow {
            y: 12
            width: Math.min(parent.width, 672)
            spacing: 12
            Text {
                id: line
                objectName: "sharedOfferLine"
                width: Math.max(200, parent.width - apply.width - 12)
                text: N.offerLine(root.held)
                color: Theme.text
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
            }
            Button {
                id: apply
                objectName: "sharedOfferApply"
                size: "sm"
                kind: "ghost"
                icon: "book-open-check"
                text: "Dùng " + root.held.length + " cách đọc chung"
                busy: root.busy
                onActivated: {
                    root.busy = true
                    root.work.applyShared(function() { root.busy = false })
                }
            }
        }
    }
}

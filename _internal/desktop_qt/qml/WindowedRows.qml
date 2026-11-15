import QtQuick
import ABook

// Long disclosures share their enclosing Flickable. Offscreen rows retain measured height without keeping controls alive.
Column {
    id: root
    property var rows: []
    property Component delegate: null
    property real estimate: 140
    property var viewport: null
    property real viewTop: 0
    property real viewBottom: 0
    readonly property bool windowed: rows.length > 12

    function findViewport() {
        let item = parent
        while (item) {
            if (item.contentY !== undefined && item.contentHeight !== undefined && item.interactive !== false) return item
            item = item.parent
        }
        return null
    }
    function refresh() {
        if (!viewport) return
        const top = mapFromItem(viewport, 0, 0).y
        viewTop = top - viewport.height / 2
        viewBottom = top + viewport.height * 1.5
    }
    Component.onCompleted: { viewport = findViewport(); Later.call(root, refresh) }
    onYChanged: refresh()
    onWidthChanged: Later.call(root, refresh)
    onVisibleChanged: Later.call(root, refresh)
    Connections {
        target: root.viewport
        ignoreUnknownSignals: true
        function onContentYChanged() { root.refresh() }
        function onContentHeightChanged() { root.refresh() }
        function onHeightChanged() { root.refresh() }
    }
    Repeater {
        model: root.rows
        Item {
            id: slot
            required property var modelData
            required property int index
            width: root.width
            property real measured: root.estimate
            // New delegates may themselves be revealing from zero. Do not let zero-height rows fill the whole viewport.
            // Activation must not change its own culling bounds synchronously.
            // The settled measurement updates the slot after layout completes.
            height: measured
            onYChanged: root.refresh()
            Loader {
                id: loader
                property var rowData: slot.modelData
                property int rowIndex: slot.index
                width: parent.width
                active: !root.windowed || (root.viewport !== null && root.visible && slot.y + slot.height >= root.viewTop && slot.y <= root.viewBottom)
                sourceComponent: root.delegate
                onLoaded: {
                    settled.restart()
                }
            }
            Connections {
                target: loader.item
                function onHeightChanged() { if (loader.item) settled.restart() }
            }
            Timer { id: settled; interval: 250; onTriggered: if (loader.item) slot.measured = loader.item.height }
        }
    }
}

import QtQuick

// Composite the surface, its border and its shadow once before fading the window.
// Reserve the full shadow image extent; a layer sized to the panel would cut it.
Item {
    id: root
    readonly property int shadowPadding: Theme.dark ? 130 : 96
    default property alias surfaceData: surface.data
    readonly property alias composition: composite
    data: Item {
        id: composite
        x: -root.shadowPadding
        y: -root.shadowPadding
        width: root.width + 2 * root.shadowPadding
        height: root.height + 2 * root.shadowPadding
        // A closed surface has no pixels to composite. Keep the layer until
        // the exit fade has finished, then release its render target.
        layer.enabled: root.visible
        Item {
            id: surface
            x: root.shadowPadding
            y: root.shadowPadding
            width: root.width
            height: root.height
        }
    }
}

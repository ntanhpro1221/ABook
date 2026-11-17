import QtQuick

// Keep the popup's public actions synchronous, without constructing its hidden
// controls at startup. Retain the owner after first use so pending work and
// exit animations survive closing.
Loader {
    id: root
    active: false
    readonly property bool open: item ? item.open : false
    function ensure() { active = true; return item }
    function show() { ensure().show() }
    function toggle() { ensure().toggle() }
    function close() { if (item) item.close() }
    function dismiss() { if (item) item.dismiss() }
}

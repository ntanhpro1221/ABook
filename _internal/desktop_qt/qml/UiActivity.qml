import QtQuick

// Window visibility, not focus: an inactive visible window still needs updates.
QtObject {
    id: root
    property Item target: null
    property bool wanted: true
    property bool ready: false
    readonly property bool running: wanted && target !== null && target.visible && target.Window.window !== null
                                   && target.Window.visibility !== Window.Minimized && target.Window.visibility !== Window.Hidden
    signal resumed()
    onRunningChanged: if (ready && running) resumed()
    Component.onCompleted: ready = true
}

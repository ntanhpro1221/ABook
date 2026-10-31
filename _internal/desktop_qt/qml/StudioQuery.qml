import QtQuick
import ABook
import "StudioLogic.js" as Logic

// Một nguồn dữ liệu của Studio hỏi qua StudioStore (useQuery của bản web): `path` là đường /api/..., chỉ hỏi khi `wanted` (nơi dùng đang mở) - không ai dùng thì không
// hỏi. Hỏi lại theo nhịp `interval` (ms, 0 = không) chỉ khi cửa sổ đang thấy (`store.active`), lùi dần khi lỗi và thôi hẳn khi 404 (pollDelay như trang dự án).
// `invalidate()` = làm mới (invalidateQueries): đang có người dùng thì hỏi lại ngay, không thì ghi nhớ để hỏi khi cần. `setData` đặt bản lạc quan.
// Đổi máy (store.peer) hay đổi đường thì bỏ dữ liệu cũ - của máy trước không thuộc máy sau.
QtObject {
    id: root
    property var store: null
    property string path: ""
    property bool wanted: false
    property int interval: 0
    property var data: null
    property var error: null               // null = lần hỏi gần nhất ổn; không thì {status, text}
    property int errors: 0
    property int asked: 0
    property bool dirty: false
    readonly property bool loading: wanted && path !== "" && data === null && error === null
    readonly property string scope: store ? store.peer : ""
    readonly property int delay: Math.max(0, Logic.pollDelay(interval, error ? error.status : null, errors))
    signal loaded(var data)

    function load() {
        if (!store || path === "") return
        const ask = ++asked
        const mine = path
        const where = scope
        dirty = false
        store.request("GET", path, null, function(status, answer) {
            if (ask !== root.asked || mine !== root.path || where !== root.scope) return
            if (store.ok(status) && answer !== null && answer !== undefined) {
                root.data = answer
                root.error = null
                root.errors = 0
                root.loaded(answer)
            } else {
                root.error = {status: status, text: store.errorText(status, answer)}
                root.errors++
            }
        })
    }
    function invalidate() { if (wanted && path !== "") load(); else dirty = true }
    function setData(next) { asked++; data = next; error = null }
    function reset() { asked++; data = null; error = null; errors = 0; dirty = false }
    onWantedChanged: if (wanted && path !== "") load()
    onPathChanged: { reset(); if (wanted && path !== "") load() }
    onScopeChanged: { reset(); if (wanted && path !== "") load() }

    property Timer timer: Timer {
        interval: Math.max(1, root.delay)
        running: root.wanted && root.path !== "" && root.delay > 0 && !!root.store && root.store.active
        repeat: true
        onTriggered: root.load()
    }
}

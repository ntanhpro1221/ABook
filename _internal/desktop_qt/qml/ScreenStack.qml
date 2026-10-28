import QtQuick
import ABook

// Ngăn xếp màn của cửa sổ. Mỗi mục thanh bên (Thư viện, Studio, Cài đặt) có ngăn xếp riêng, dựng lười và giữ nguyên khi chuyển mục
// (Thư viện còn đúng chỗ cuộn khi quay lại). Chuyển cảnh KHÔNG bao giờ là mờ thuần và luôn đối xứng:
//   vào sâu (push)      màn cũ trôi sang trái 24 px + thu 0,98 + mờ hết, rồi màn mới từ phải 24 px vào
//   lùi ra (pop / Back) đúng gương: màn cũ trôi sang phải, màn mới từ trái vào
//   đổi mục thanh bên   trượt dọc 16 px theo chiều của mục (xuống = mục dưới), vì thanh bên xếp dọc
// Ra nhanh hơn vào (90 / 220 ms, ra dùng đường cong tăng tốc, vào giảm tốc); ảnh cũ mờ hết rồi ảnh mới mới hiện nên không bao giờ
// hai lớp chữ chồng nhau. "Giảm hiệu ứng" của Windows: bỏ trượt / thu, chỉ còn mờ <= 120 ms. Bấm liên tiếp: chuyển cảnh đang dở
// được chốt ngay rồi chuyển cảnh mới chạy.
Item {
    id: root
    clip: true

    property var roots: []              // Component của màn gốc từng mục
    property int current: -1
    property int depth: 0
    readonly property bool canPop: depth > 1
    readonly property bool busy: seq.running
    signal reselected(int index)          // chọn lại mục đang mở ở thanh bên: màn gốc tự về đầu (Studio: về danh sách dự án)

    property var _stacks: ({})
    property Item _out: null
    property Item _in: null
    property bool _destroyOut: false
    property int _stage: 2              // 0 đang ra, 1 đang vào, 2 xong
    property real outDx: 0
    property real outDy: 0
    property real inDx0: 0
    property real inDy0: 0
    property real zoomOut: 0.98
    property int outMs: Theme.motionFastOut
    property int inMs: Theme.motionMedium

    Component {
        id: wrapperComp
        Item {
            id: wrapper
            property Item content: null
            property real dx: 0
            property real dy: 0
            property real zoom: 1
            anchors.fill: parent
            visible: false
            scale: zoom
            transform: Translate { x: wrapper.dx; y: wrapper.dy }
        }
    }

    function _top(index) {
        const s = _stacks[index]
        return s && s.length ? s[s.length - 1] : null
    }
    function _wrap(comp, props) {
        const w = wrapperComp.createObject(root)
        const page = comp.createObject(w, props || {})
        page.anchors.fill = w
        w.content = page
        return w
    }
    function _neutral(w) {
        if (!w) return
        w.opacity = 1
        w.dx = 0
        w.dy = 0
        w.zoom = 1
    }

    // ---- API ----
    function rootContent(index) { const s = _stacks[index]; return s && s.length ? s[0].content : null }
    function show(index) {
        if (index === current) {
            popToRoot()
            reselected(index)
            return
        }
        if (!_stacks[index]) _stacks[index] = [_wrap(roots[index])]
        const outW = current >= 0 ? _top(current) : null
        const inW = _top(index)
        const kind = current < 0 ? "none" : (index > current ? "peerDown" : "peerUp")
        current = index
        depth = _stacks[index].length
        _run(outW, inW, kind, false)
    }
    function push(comp, props) {
        const outW = _top(current)
        const inW = _wrap(comp, props)
        _stacks[current].push(inW)
        depth = _stacks[current].length
        _run(outW, inW, "forward", false)
    }
    function pop() {
        const s = _stacks[current]
        if (!s || s.length < 2) return
        const outW = s.pop()
        depth = s.length
        _run(outW, s[s.length - 1], "back", true)
    }
    function popToRoot() {
        const s = _stacks[current]
        if (!s || s.length < 2) return
        _finish()
        const outW = s.pop()
        while (s.length > 1) s.pop().destroy()
        depth = 1
        _run(outW, s[0], "back", true)
    }

    // ---- chuyển cảnh ----
    function _run(outW, inW, kind, destroyOut) {
        _finish()
        _out = outW
        _in = inW
        _destroyOut = destroyOut
        if (kind === "none" || !outW) {
            if (outW) outW.visible = false
            _neutral(inW)
            inW.visible = true
            _out = null
            _in = null
            _stage = 2
            return
        }
        const reduced = Theme.reduceMotion
        const magnitude = reduced ? 0 : (kind.indexOf("peer") === 0 ? 16 : 24)
        let sx = 0, sy = 0
        if (kind === "forward") sx = -1
        else if (kind === "back") sx = 1
        else if (kind === "peerDown") sy = -1
        else sy = 1
        outDx = sx * magnitude
        outDy = sy * magnitude
        inDx0 = -sx * magnitude
        inDy0 = -sy * magnitude
        zoomOut = reduced ? 1 : 0.98
        outMs = reduced ? 90 : Theme.motionFastOut
        inMs = reduced ? 120 : Theme.motionMedium
        _stage = 0
        seq.restart()
    }
    function _swap() {
        _stage = 1
        if (_out) {
            _out.visible = false
            _neutral(_out)
            if (_destroyOut) _out.destroy()
            _out = null
        }
        _in.opacity = 0
        _in.dx = inDx0
        _in.dy = inDy0
        _in.zoom = zoomOut
        _in.visible = true
    }
    function _done() {
        _neutral(_in)
        _in = null
        _out = null
        _stage = 2
    }
    function _finish() {
        if (_stage === 2 && !seq.running) return
        seq.stop()
        if (_stage === 0) _swap()
        _done()
    }

    SequentialAnimation {
        id: seq
        ParallelAnimation {
            NumberAnimation { target: root._out; property: "opacity"; to: 0; duration: root.outMs; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeAccelerate }
            NumberAnimation { target: root._out; property: "dx"; to: root.outDx; duration: root.outMs; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeAccelerate }
            NumberAnimation { target: root._out; property: "dy"; to: root.outDy; duration: root.outMs; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeAccelerate }
            NumberAnimation { target: root._out; property: "zoom"; to: root.zoomOut; duration: root.outMs; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeAccelerate }
        }
        ScriptAction { script: root._swap() }
        ParallelAnimation {
            NumberAnimation { target: root._in; property: "opacity"; to: 1; duration: root.inMs; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeDecelerate }
            NumberAnimation { target: root._in; property: "dx"; to: 0; duration: root.inMs; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeDecelerate }
            NumberAnimation { target: root._in; property: "dy"; to: 0; duration: root.inMs; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeDecelerate }
            NumberAnimation { target: root._in; property: "zoom"; to: 1; duration: root.inMs; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeDecelerate }
        }
        ScriptAction { script: root._done() }
    }
}

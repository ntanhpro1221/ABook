import QtQuick
import ABook

// Ngăn xếp màn của cửa sổ. Mỗi mục thanh bên (Thư viện, Studio, Cài đặt) có ngăn xếp riêng, dựng lười và giữ nguyên khi chuyển mục
// (Thư viện còn đúng chỗ cuộn khi quay lại). Chuyển cảnh KHÔNG bao giờ là mờ thuần và luôn đối xứng:
//   vào sâu (push)      màn cũ trượt sang trái, màn mới vào đồng thời từ phải, qua hết bề rộng khung
//   lùi ra (pop / Back) đúng gương: màn cũ trôi sang phải, màn mới từ trái vào
//   đổi mục thanh bên   trượt dọc 16 px theo chiều của mục (xuống = mục dưới), vì thanh bên xếp dọc
// Push / Back share one motionSlow slide and a cover path when a source is available. Sidebar changes use 90 / 220 ms fade-through with geometry.
// "Giảm hiệu ứng" của Windows: bỏ trượt / thu, chỉ còn mờ <= 120 ms. Bấm liên tiếp: chuyển cảnh đang dở
// được chốt ngay rồi chuyển cảnh mới chạy.
Item {
    id: root
    clip: true

    property var roots: []              // Component của màn gốc từng mục
    property int current: -1
    property int depth: 0
    readonly property bool canPop: depth > 1
    readonly property bool busy: seq.running || slide.running
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
    property real coverT: 0
    property Item _coverFrom: null
    property Item _coverTo: null
    property rect _coverStart: Qt.rect(0, 0, 0, 0)
    property rect _coverEnd: Qt.rect(0, 0, 0, 0)
    readonly property rect liveCoverEnd: {
        if (!_coverTo || !_in) return _coverEnd
        // Sample in the destination page's coordinates. Subtracting dx from a
        // root mapping can read Translate before its binding catches up.
        const tick = _in.dx
        return _coverBox(_coverTo, _in)
    }

    Component {
        id: wrapperComp
        Item {
            id: wrapper
            property Item content: null
            property Item transitionSource: null
            property real dx: 0
            property real dy: 0
            property real zoom: 1
            anchors.fill: parent
            visible: false
            scale: zoom
            transform: Translate { x: wrapper.dx; y: wrapper.dy }
        }
    }

    // Màn trên cùng của mục `index` (chưa dựng: null).
    function topPage(index) {
        const top = _top(index)
        return top ? top.content : null
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
    function push(comp, props, sourceItem) {
        const outW = _top(current)
        const inW = _wrap(comp, props)
        inW.transitionSource = sourceItem || null
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
        if (!reduced && (kind === "forward" || kind === "back")) {
            const direction = kind === "forward" ? -1 : 1
            outDx = direction * width
            outDy = 0
            inDx0 = -outDx
            inDy0 = 0
            _neutral(outW)
            _neutral(inW)
            _startCover(kind === "back" ? outW.content.transitionCover : inW.transitionSource,
                        kind === "back" ? outW.transitionSource : inW.content.transitionCover)
            inW.dx = inDx0
            inW.visible = true
            _stage = 1
            slide.restart()
            return
        }
        const magnitude = reduced ? 0 : (kind.indexOf("peer") === 0 ? height : width)
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
        _neutral(outW)
        _neutral(inW)
        inW.dx = inDx0; inW.dy = inDy0
        inW.opacity = reduced ? 0 : 1
        inW.visible = true
        _stage = 1
        seq.restart()
    }
    function _done() {
        _neutral(_in)
        _in = null
        _out = null
        _stage = 2
    }
    function _coverBox(item, relativeTo) {
        const a = item.mapToItem(relativeTo || root, 0, 0)
        const b = item.mapToItem(relativeTo || root, item.width, item.height)
        return Qt.rect(a.x, a.y, b.x - a.x, b.y - a.y)
    }
    function _startCover(from, to) {
        if (!from || !to) return
        _coverStart = _coverBox(from)
        _coverEnd = _coverBox(to)
        _coverFrom = from
        _coverTo = to
        // The source remains painted until covered by the destination. The
        // overlay may still be decoding its size-specific artwork.
        to.opacity = 0
        coverT = 0
    }
    function _slideDone() {
        _coverEnd = liveCoverEnd
        if (_coverFrom) _coverFrom.opacity = 1
        if (_coverTo) _coverTo.opacity = 1
        _coverFrom = null
        _coverTo = null
        if (_out) {
            _out.visible = false
            _neutral(_out)
            if (_destroyOut) _out.destroy()
        }
        _done()
    }
    function _finish() {
        if (slide.running) { slide.stop(); _slideDone(); return }
        if (_stage === 2 && !seq.running) return
        seq.stop()
        _slideDone()
    }

    ShaderEffectSource {
        id: sharedCover
        objectName: "navigationCoverMorph"
        sourceItem: root._coverFrom
        hideSource: false
        live: true
        recursive: true
        z: 100
        visible: root._coverFrom !== null && root._coverTo !== null
        x: root._coverStart.x + (root.liveCoverEnd.x - root._coverStart.x) * root.coverT
        y: root._coverStart.y + (root.liveCoverEnd.y - root._coverStart.y) * root.coverT
        width: root._coverStart.width + (root.liveCoverEnd.width - root._coverStart.width) * root.coverT
        height: width * Theme.coverRatio
    }
    ParallelAnimation {
        id: slide
        onFinished: root._slideDone()
        NumberAnimation { target: root._out; property: "dx"; to: root.outDx; duration: Theme.motionSlow; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard }
        NumberAnimation { target: root._in; property: "dx"; to: 0; duration: Theme.motionSlow; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard }
        NumberAnimation { target: root; property: "coverT"; to: 1; duration: Theme.motionSlow; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard }
    }

    ParallelAnimation {
        id: seq
        onFinished: root._slideDone()
        NumberAnimation { target: root._out; property: "opacity"; to: Theme.reduceMotion ? Theme.motionReduced : 1; duration: Theme.motionMedium }
        NumberAnimation { target: root._out; property: "dx"; to: root.outDx; duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard }
        NumberAnimation { target: root._out; property: "dy"; to: root.outDy; duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard }
        NumberAnimation { target: root._in; property: "opacity"; to: 1; duration: Theme.motionMedium }
        NumberAnimation { target: root._in; property: "dx"; to: 0; duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard }
        NumberAnimation { target: root._in; property: "dy"; to: 0; duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard }
    }
}

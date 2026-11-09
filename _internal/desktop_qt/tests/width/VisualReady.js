.pragma library
.import "ModalLayer.js" as ModalLayer
.import "IconText.js" as IconText
.import "Separators.js" as Separators
.import "ShotTruth.js" as ShotTruth
.import "Orphans.js" as Orphans

// Rendered once does not mean ready for input: Collapse and popover delegates
// can still be hidden or moving. Wait for finite animations, keeping perpetual
// busy indicators and timers running as they do in the app.
function targetsSettled(object) {
    if (typeof object.settled === "boolean" && !object.settled) return false
    if (typeof object.open === "boolean" && typeof object.shown === "number"
            && object.shown !== (object.open ? 1 : 0)) return false
    for (const child of object.children || []) if (!targetsSettled(child)) return false
    return true
}

function settled(object, probe) {
    return probe.settled(object) && targetsSettled(object)
}

// Hoạt ảnh vòng lặp (Vu) đứng ở khung nghỉ: ảnh chụp tất định và đọc ra hình, không bắt một khung giữa chừng
function rest(item) {
    if (!item) return
    if (item.still === false && item.phase !== undefined) item.still = true
    for (const child of item.children || []) rest(child)
}

// Reading Text metrics can itself finish deferred text/font layout and dirty a
// containing Row/Column/ListView. Observe the geometry on both sides of a frame,
// rather than treating an animation endpoint or a delegate count as layout-ready.
function layoutState(item, state) {
    if (!item.visible) return state
    if (item.paintedWidth !== undefined)
        state.push(item, item.x, item.y, item.width, item.height, item.text,
            item.contentWidth, item.contentHeight, item.paintedWidth, item.paintedHeight)
    // Read the metrics the audits use. Decorative geometry (Vu bars, caret,
    // scrollbar thumb) is allowed to move without invalidating text layout.
    for (const child of item.children || []) layoutState(child, state)
    return state
}

function sameLayout(before, after) {
    return before.length === after.length && before.every((value, index) => value === after[index])
}

function difference(before, after) {
    if (!before) return "first frame"
    const index = before.findIndex((value, index) => value !== after[index])
    if (index < 0) return "length " + before.length + " -> " + after.length
    // A delegate in the old sample may already be destroyed. Do not inspect
    // it (even String(item) can throw for a deleted QML wrapper).
    const describe = value => typeof value === "object" ? "<item>" : String(value)
    return index + ": " + describe(before[index]) + " -> " + describe(after[index])
}

// A target value may also be the initial value of a sequential transition.
// Each Qt wait keeps its own 5s budget: expensive text polish/rendering must not
// consume the animation wait's budget (the old wall deadline could leave 1ms).
function waitForSettledFrame(test, window, item, probe, freeze) {
    let previous = null
    let change = ""
    // Keep frame sampling out of tryVerify's predicate: Qt evaluates a true
    // predicate once more to record the assertion. Rendering in that last
    // evaluation can invalidate the very condition it has just accepted.
    // Bound convergence in observed frames, not total wall time spent inside
    // the already-bounded Qt waits. A slow frame must not consume a later
    // transition/layout wait's allowance. Return as soon as two samples agree.
    for (let frame = 0; frame < 120; ++frame) {
        if (freeze) rest(window.contentItem)
        test.verify(test.waitForPolish(window), "window polish must finish")
        test.tryVerify(function() { return settled(window.contentItem, probe) }, 5000, "finite visual transitions must finish")
        const before = layoutState(window.contentItem, [])
        test.verify(test.waitForPolish(window), "measured text layout must finish")
        window.update()
        test.verify(test.waitForRendering(item), "requested frame must render")
        const after = layoutState(window.contentItem, [])
        // Frame delivery and lazy text measurements can schedule another
        // polish. Drain that work, rather than repeatedly rendering while
        // rejecting an otherwise identical text layout for queued polish.
        test.verify(test.waitForPolish(window), "post-render text layout must finish")
        // Responses, delegate creation and metric reads can queue more layout
        // or start another transition during that frame. Paint the new state.
        const ready = settled(window.contentItem, probe) && !test.isPolishScheduled(window)
            && sameLayout(before, after) && previous !== null && sameLayout(previous, after)
        if (ready) return
        if (frame === 119) change = difference(before, after) + "; previous " + difference(previous, after)
            + "; animations=" + settled(window.contentItem, probe) + "; polish=" + test.isPolishScheduled(window)
        previous = after
    }
    test.verify(false, "visual text layout must converge across rendered frames: " + change)
}

function render(test, window, item, probe) {
    waitForSettledFrame(test, window, item, probe, true)
    // Audit the settled scene: overlays, text/icons, separators, sidebar and theme.
    ModalLayer.assertAbove(test, window.contentItem)
    IconText.assertClean(test, grabTarget(window, item), probe)
    Separators.assertClean(test, grabTarget(window, item), probe)
    ShotTruth.assertTrue(test, window.contentItem)
    Orphans.assertClean(test, grabTarget(window, item), probe)
}

// Ảnh chụp: hộp thoại / bảng nổi tự ở gốc cửa sổ (WindowLayer), không còn nằm dưới `item`; có lớp nào đang mở thì chụp cả cửa sổ để ảnh có hộp.
function grabTarget(window, item) {
    return ModalLayer.anyOpen(window.contentItem) ? window.contentItem : item
}

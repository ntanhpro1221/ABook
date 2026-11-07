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

// A target value may also be the initial value of a sequential transition.
// Observe running animations, polish, and the frame which actually paints it.
function waitForSettledFrame(test, window, item, probe, freeze) {
    const deadline = Date.now() + 5000
    while (true) {
        if (freeze) rest(window.contentItem)
        test.verify(test.waitForPolish(window), "window polish must finish")
        test.tryVerify(function() { return settled(window.contentItem, probe) }, Math.max(1, deadline - Date.now()))
        test.verify(test.waitForPolish(window), "window polish must finish")
        window.update()
        test.verify(test.waitForRendering(item))
        // A queued response can start another transition during that frame.
        if (settled(window.contentItem, probe)) return
        test.verify(Date.now() < deadline, "visual transitions must settle after rendering")
    }
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

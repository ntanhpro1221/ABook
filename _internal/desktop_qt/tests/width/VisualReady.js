.pragma library
.import "ModalLayer.js" as ModalLayer

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

function render(test, window, item, probe) {
    const deadline = Date.now() + 5000
    while (true) {
        test.waitForPolish(window)
        test.tryVerify(function() { return settled(window.contentItem, probe) }, Math.max(1, deadline - Date.now()))
        test.waitForPolish(window)
        window.update()
        test.verify(test.waitForRendering(item))
        // A queued response can start another transition during that frame.
        // Mọi lần dựng xong cũng kiểm lớp: hộp đang mở thì không phần tử nào của trang vẽ đè lên mặt hộp
        if (settled(window.contentItem, probe)) { ModalLayer.assertAbove(test, window.contentItem); return }
        test.verify(Date.now() < deadline, "visual transitions must settle after rendering")
    }
}

// Ảnh chụp: hộp thoại / bảng nổi tự ở gốc cửa sổ (WindowLayer), không còn nằm dưới `item`; có lớp nào đang mở thì chụp cả cửa sổ để ảnh có hộp.
function grabTarget(window, item) {
    return ModalLayer.anyOpen(window.contentItem) ? window.contentItem : item
}

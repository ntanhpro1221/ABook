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

function render(test, window, item, probe) {
    const deadline = Date.now() + 5000
    while (true) {
        rest(window.contentItem)
        test.waitForPolish(window)
        test.tryVerify(function() { return settled(window.contentItem, probe) }, Math.max(1, deadline - Date.now()))
        test.waitForPolish(window)
        window.update()
        test.verify(test.waitForRendering(item))
        // A queued response can start another transition during that frame.
        // Mọi lần dựng xong cũng kiểm lớp (hộp đang mở thì không phần tử nào của trang vẽ đè lên mặt hộp), chữ / icon (chữ đè icon, icon
        // lệch tâm dòng đầu, nút trơn trên bìa), dấu ngăn đầu dòng, chữ mồ côi và ảnh nói thật (thanh bên, theme): mọi cảnh chụp L_/W_/D_ đều phải sạch
        if (settled(window.contentItem, probe)) {
            ModalLayer.assertAbove(test, window.contentItem)
            IconText.assertClean(test, grabTarget(window, item), probe)
            Separators.assertClean(test, grabTarget(window, item), probe)
            ShotTruth.assertTrue(test, window.contentItem)
            Orphans.assertClean(test, grabTarget(window, item), probe)
            return
        }
        test.verify(Date.now() < deadline, "visual transitions must settle after rendering")
    }
}

// Ảnh chụp: hộp thoại / bảng nổi tự ở gốc cửa sổ (WindowLayer), không còn nằm dưới `item`; có lớp nào đang mở thì chụp cả cửa sổ để ảnh có hộp.
function grabTarget(window, item) {
    return ModalLayer.anyOpen(window.contentItem) ? window.contentItem : item
}

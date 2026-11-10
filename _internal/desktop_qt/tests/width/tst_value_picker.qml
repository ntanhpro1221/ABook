import QtQuick
import QtTest
import "../../qml/ValuePickerLogic.js" as Logic
import ABook

// Bộ chọn giá trị: MỘT bộ ca cho ba nền (web valuePickerLogic.test.ts, Android ValuePickerLogicTest) - tests/fixtures/value_picker/cases.json,
// test_width.cpp đọc file ấy vào `qtValuePickerCases`. Thêm phần thao tác thật trên ValuePicker.qml: kéo, -/+, phím, chip, gõ số (kẹp + báo).
Item {
    id: host
    width: 360
    height: 420
    Rectangle { anchors.fill: parent; color: Theme.bg }
    ValuePicker {
        id: picker
        x: 16; width: 328
        spec: Logic.SPECS.sleepMinutes
        value: 30
        label: "Hẹn giờ ngủ"
        format: Logic.minutesLabel
        onPicked: v => value = v
    }
    SignalSpy { id: picks; target: picker; signalName: "picked" }
    Component {
        id: extraPickerComponent
        ValuePicker {
            width: 328
            spec: Logic.SPECS.sleepMinutes
            Text { objectName: "specialLabel"; text: "Số chương"; font.pixelSize: 14 }
            Row { objectName: "specialRow"; height: 48; Rectangle { width: 48; height: 48 } }
        }
    }
    Component { id: sleepPopoverComponent; SleepPopover { width: 360; height: 600; open: true; shown: 1 } }
    Component { id: speedPopoverComponent; SpeedPopover { width: 360; height: 600; open: true; shown: 1 } }

    TestCase {
        name: "ValuePicker"
        when: windowShown
        readonly property var fixture: JSON.parse(qtValuePickerCases)

        function init() {
            picker.dense = false
            picker.fontScale = 1
            picker.spec = Logic.SPECS.sleepMinutes
            picker.format = Logic.minutesLabel
            picker.value = 30
            picker.current = true
            picker.typing = false
            picker.clampNote = false
            picks.clear()
        }

        function test_balancedRowsAndInverse() {
            for (const c of fixture.chipRows) compare(Logic.chipRows(c.widths, c.available, c.gap).map(row => row.length), c.out)
            for (const name in Logic.SPECS) {
                const spec = Logic.SPECS[name]
                for (let i = 0; i <= Math.round((spec.max - spec.min) / spec.step); i++) {
                    const value = Logic.stepValue(spec, spec.min, i)
                    compare(Logic.fromFraction(spec, Logic.toFraction(spec, value)), value, name + " " + value)
                }
                if (spec.min > 0 && spec.max / spec.min >= 8) for (let i = 1; i < spec.typical.length; i++)
                    verify((Logic.toFraction(spec, spec.typical[i]) - Logic.toFraction(spec, spec.typical[i-1])) * 200 >= 24, name)
            }
        }

        function test_everyPickerAt360() {
            for (const fontScale of [1, 1.3]) for (const name in Logic.SPECS) {
                picker.spec = Logic.SPECS[name]
                picker.fontScale = fontScale
                picker.value = picker.spec.min
                waitForRendering(picker)
                const rows = findChild(picker, "valueChips").rows
                if (fontScale === 1) compare(rows.length, 1, name + " at normal font size")
                for (const row of rows) verify(row.length > 1, name + " at " + fontScale)
            }
        }

        function test_specialChildrenStackWithoutOverlap() {
            const extra = createTemporaryObject(extraPickerComponent, host)
            verify(extra !== null)
            verify(waitForRendering(extra))
            const label = findChild(extra, "specialLabel")
            const row = findChild(extra, "specialRow")
            verify(row.y >= label.y + label.height + Theme.s4)
            verify(extra.height >= row.mapToItem(extra, 0, row.height).y)
        }

        function test_phonePopoversReserveOneMeasuredRow() {
            for (const data of [{component: sleepPopoverComponent, name: "sleepPicker"}, {component: speedPopoverComponent, name: "speedPicker"}]) {
                const popover = createTemporaryObject(data.component, host)
                verify(popover !== null)
                verify(waitForRendering(popover))
                const control = findChild(popover, data.name)
                const chips = findChild(control, "valueChips")
                compare(chips.rows.length, 1, data.name + " in a 360px window")
                verify(control.width >= control.minimumWidth)
                popover.destroy()
            }
        }

        function test_denseLabelsStayOnTicksAndPick() {
            picker.dense = true
            for (const name in Logic.SPECS) {
                picker.spec = Logic.SPECS[name]
                picker.value = picker.spec.min
                waitForRendering(picker)
                const ruler = findChild(picker, "valueRuler")
                for (const v of picker.spec.typical) {
                    const chip = findChild(picker, "valueChip_" + Logic.formatNumber(picker.spec, v))
                    compare(chip.width, 48); compare(chip.height, 48)
                    fuzzyCompare(chip.x + chip.width / 2, ruler.inset + Logic.toFraction(picker.spec, v) * (ruler.width - 2 * ruler.inset), 0.5)
                    mouseClick(chip, chip.width / 2, chip.height / 2)
                    compare(picker.value, v, name)
                }
            }
        }

        function sameSpec(a, b) {
            return a.min === b.min && a.max === b.max && a.step === b.step && JSON.stringify(a.typical) === JSON.stringify(b.typical)
                && JSON.stringify(a.scale || null) === JSON.stringify(b.scale || null)
        }

        function test_theNativeTableIsTheSharedTable() {
            compare(fixture.snapSteps, Logic.SNAP_STEPS)
            compare(fixture.pageSteps, Logic.PAGE_STEPS)
            compare(Object.keys(fixture.specs).sort(), Object.keys(Logic.SPECS).sort())
            for (const name in fixture.specs) verify(sameSpec(fixture.specs[name], Logic.SPECS[name]), name)
        }

        function test_everySharedCase() {
            for (const c of fixture.cases) {
                const spec = fixture.specs[c.spec]
                const name = c.spec + " " + c.op + " " + c.in
                switch (c.op) {
                case "clamp": { const r = Logic.clampValue(spec, c.in); compare(r.value, c.out, name); compare(r.clamped, c.clamped, name); break }
                case "step": compare(Logic.stepValue(spec, c.in, c.steps), c.out, name); break
                case "fromFraction": compare(Logic.fromFraction(spec, c.in), c.out, name); break
                case "toFraction": fuzzyCompare(Logic.toFraction(spec, c.in), c.out, 1e-9, name); break
                case "parse": {
                    const r = Logic.parseValue(spec, c.in)
                    if (c.out === null) compare(r, null, name)
                    else { verify(r !== null, name); compare(r.value, c.out, name); compare(r.clamped, c.clamped, name) }
                    break
                }
                case "chip": compare(Logic.chipIndex(spec, c.in), c.out, name); break
                case "detent": compare(Logic.isDetent(spec, c.prev, c.in), c.out, name); break
                case "format": compare(Logic.formatNumber(spec, c.in), c.out, name); break
                default: fail("ca lạ: " + name)
                }
            }
        }

        // Nấc hút không nuốt bước kề: kéo tới được MỌI giá trị trong biên.
        function test_everyValueIsReachableByDragging() {
            for (const name in Logic.SPECS) {
                const spec = Logic.SPECS[name]
                const reached = {}
                for (let i = 0; i <= 20000; ++i) reached[Logic.fromFraction(spec, i / 20000)] = true
                compare(Object.keys(reached).length, Math.round((spec.max - spec.min) / spec.step) + 1, name)
            }
        }

        // Một thao tác sau khi mở: kéo thước ra 23 phút (chủ sách 09-11: chọn tự do mà vẫn nhanh).
        function test_dragReaches23Minutes() {
            const ruler = findChild(picker, "valueRuler")
            const track = ruler.width - 2 * ruler.inset
            const x = ruler.inset + Logic.toFraction(picker.spec, 23) * track
            mousePress(ruler, ruler.width / 2, ruler.height / 2)
            mouseMove(ruler, x, ruler.height / 2)
            compare(picks.count, 0)             // đang kéo: chưa áp
            compare(picker.shown, 23)
            mouseRelease(ruler, x, ruler.height / 2)
            compare(picks.count, 1)
            compare(picker.value, 23)
            compare(findChild(picker, "valueDisplay").Accessible.name, "Hẹn giờ ngủ: 23 phút. Chạm để gõ số")
        }

        function test_stepButtonsAndKeys() {
            for (const name of ["valueDown", "valueUp"]) {
                const button = findChild(picker, name)
                compare(button.width, 48); compare(button.height, 48)
                compare(button.y + button.height / 2, findChild(picker, "valueRuler").height / 2)
            }
            mouseClick(findChild(picker, "valueUp"))
            compare(picker.value, 31)
            mouseClick(findChild(picker, "valueDown"))
            compare(picker.value, 30)
            const ruler = findChild(picker, "valueRuler")
            ruler.forceActiveFocus()
            keyClick(Qt.Key_Right); compare(picker.value, 31)
            keyClick(Qt.Key_PageUp); compare(picker.value, 41)
            keyClick(Qt.Key_PageDown); keyClick(Qt.Key_Left); compare(picker.value, 30)
            keyClick(Qt.Key_End); compare(picker.value, 240)
            verify(!findChild(picker, "valueUp").enabled)
            keyClick(Qt.Key_Home); compare(picker.value, 1)
        }

        function test_chipIsLitAndPicks() {
            const chip = findChild(picker, "valueChip_15")
            verify(!chip.selected)
            verify(findChild(picker, "valueChip_30").selected)
            mouseClick(chip)
            compare(picker.value, 15)
            verify(chip.selected)
            picker.current = false              // hẹn giờ đang "Hết chương": không chip nào sáng, chạm đúng số đang đứng vẫn là đặt
            verify(!chip.selected)
            mouseClick(chip)
            compare(picks.count, 2)
        }

        // Mở + chạm số + gõ: 1,35× trong hai thao tác; gõ ngoài biên thì kẹp và báo nhẹ.
        function test_typingANumber() {
            picker.spec = Logic.SPECS.speed
            picker.format = function(v) { return Logic.formatNumber(Logic.SPECS.speed, v) + "×" }
            picker.value = 1
            mouseClick(findChild(picker, "valueDisplay"))
            const input = findChild(picker, "valueInput")
            tryVerify(function() { return input.activeFocus })
            input.selectAll(); keyClick(Qt.Key_Delete)
            keyClick(Qt.Key_1); keyClick(Qt.Key_Comma); keyClick(Qt.Key_3); keyClick(Qt.Key_5)
            keyClick(Qt.Key_Return)
            compare(picker.value, 1.35)
            verify(!picker.clampNote)
            mouseClick(findChild(picker, "valueDisplay"))
            tryVerify(function() { return input.activeFocus })
            input.selectAll(); keyClick(Qt.Key_Delete); keyClick(Qt.Key_9); keyClick(Qt.Key_Return)
            compare(picker.value, 3)
            verify(picker.clampNote)
            tryCompare(findChild(picker, "valueClamped"), "text", "Trong khoảng 0,5×–3×")
            mouseClick(findChild(picker, "valueDisplay"))
            tryVerify(function() { return input.activeFocus })
            input.selectAll(); keyClick(Qt.Key_Delete); keyClick(Qt.Key_X); keyClick(Qt.Key_Return)
            compare(picker.value, 3)            // chữ không ra số: giữ giá trị cũ
        }
    }
}

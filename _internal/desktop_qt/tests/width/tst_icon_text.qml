import QtQuick
import QtTest
import "IconText.js" as IconText
import ABook

// Kiểm lực máy dò chữ-đè-icon (IconText.js): cảnh cố tình đè / lệch phải bị bắt, cảnh đúng và số trong SkipGlyph thì không.
Item {
    id: host
    width: 600; height: 400
    Component {
        id: overText
        Item {
            width: 200; height: 40
            Icon { name: "play"; size: 24; x: 10; y: 8 }
            Text { text: "15"; x: 14; y: 10; font.pixelSize: 14 }          // absolute, đè lên icon
        }
    }
    Component {
        id: offCenter
        Item {
            width: 200; height: 40
            Row {
                spacing: 8
                Icon { name: "plus"; size: 16; y: 12 }                     // tụt 12 px so với dòng chữ
                Text { text: "Thêm sách"; font.pixelSize: 14 }
            }
        }
    }
    Component {
        id: aligned
        Item {
            width: 200; height: 40
            Row {
                spacing: 8
                height: 20
                Icon { name: "plus"; size: 16; anchors.verticalCenter: parent.verticalCenter }
                Text { text: "Thêm sách"; font.pixelSize: 14; height: 20; verticalAlignment: Text.AlignVCenter }
            }
        }
    }
    Component {
        id: skip
        Item { width: 60; height: 60; SkipGlyph { size: 32; forward: false } }
    }
    Component {
        id: plainOnCover
        Item {
            width: 200; height: 300
            CoverView { width: 200; height: 300; title: "Bìa tối" }
            IconButton { objectName: "plainPlay"; icon: "play"; x: 146; y: 246 }
        }
    }
    Component {
        id: roundOnCover
        Item {
            width: 200; height: 300
            CoverView { width: 200; height: 300; title: "Bìa tối" }
            CoverButton { icon: "play"; x: 146; y: 246 }
        }
    }
    // Ba cảnh từng báo nhầm ở lượt đo đầu (79 lượt): bút ngay sau chữ cuối của tên xuống dòng, mũi tên xoay 90 độ, Icon tên rỗng của phím chữ
    Component {
        id: penAfterWrap
        Item {
            width: 200; height: 80
            Text { id: wrapped; width: 130; text: "Một tên chương dài xuống dòng"; wrapMode: Text.Wrap; font.pixelSize: 14 }
            Icon { name: "pencil"; size: 12; x: 112; y: wrapped.height - 14 }
        }
    }
    Component {
        id: turnedChevron
        Item {
            width: 200; height: 40
            Icon { name: "chevron-right"; size: 14; y: 13; rotation: 90 }
            Text { x: 22; y: 10; text: "Nhật ký"; font.pixelSize: 14 }
        }
    }
    Component {
        id: emptyIcon
        Item {
            width: 40; height: 20
            Text { anchors.centerIn: parent; text: "Shift"; font.pixelSize: 11 }
            Icon { anchors.centerIn: parent; name: ""; size: 12 }
        }
    }
    // Nút wrap (dòng cao 1,25) một dòng và hai dòng; câu dòng cao 1,4 với LineIcon
    Component {
        id: wrapButton
        Button { size: "lg"; wrap: true; icon: "play"; width: 240 }
    }
    Component {
        id: tallLines
        Item {
            width: 200; height: 120
            LineIcon { line: tall; name: "check"; size: 14 }
            Text { id: tall; x: 22; width: 178; wrapMode: Text.Wrap; font.pixelSize: 14; lineHeight: 1.4; text: "Một câu dài gãy thành vài dòng để thử icon đứng giữa dòng đầu" }
        }
    }
    Component {
        id: inlineError
        InlineError { message: "Bạn hãy kiểm tra kết nối rồi tải lại danh sách giọng." }
    }
    TestCase {
        name: "IconText"
        when: windowShown
        function hitsOf(component) {
            const scene = createTemporaryObject(component, host)
            waitForRendering(scene)
            return IconText.scan(scene, qtVisualReady)
        }
        function test_textOverIconIsCaught() {
            const hits = hitsOf(overText)
            compare(hits.length, 1, JSON.stringify(hits)); compare(hits[0].rule, "text-over-icon")
        }
        function test_iconOffTheFirstLineIsCaught() {
            const hits = hitsOf(offCenter)
            compare(hits.length, 1, JSON.stringify(hits)); compare(hits[0].rule, "icon-off-center")
        }
        function test_plainButtonOnCoverIsCaught() {
            const hits = hitsOf(plainOnCover)
            compare(hits.length, 1, JSON.stringify(hits)); compare(hits[0].rule, "plain-button-on-cover"); compare(hits[0].button, "plainPlay")
            compare(hitsOf(roundOnCover), [])
        }
        function test_wrappedTextTurnedArrowAndEmptyIconPass() {
            compare(JSON.stringify(hitsOf(penAfterWrap)), "[]")
            compare(JSON.stringify(hitsOf(turnedChevron)), "[]")
            compare(JSON.stringify(hitsOf(emptyIcon)), "[]")
        }
        // Lỗi tải chung: rộng (nút sau câu) và hẹp (câu gãy dòng, nút xuống dòng) đều không lệch tâm, và bấm "Thử lại" phát retry
        function test_inlineErrorIsAlignedAtAnyWidth() {
            for (const width of [640, 200]) {
                const error = createTemporaryObject(inlineError, host, {width: width})
                tryCompare(error, "open", true)
                waitForRendering(error)
                compare(JSON.stringify(IconText.scan(error, qtVisualReady)), "[]", "width " + width)
                const icon = findChild(error, "inlineErrorIcon"), retry = findChild(error, "inlineErrorRetry")
                const iconCenter = icon.mapToItem(error, 0, icon.height / 2).y
                compare(iconCenter, findChild(error, "inlineErrorText").mapToItem(error, 0, 0).y + retry.height / 2)
            }
            const error = createTemporaryObject(inlineError, host, {width: 640})
            const spy = createTemporaryQmlObject("import QtTest; SignalSpy { signalName: 'retry' }", host)
            spy.target = error
            tryCompare(error, "open", true)
            mouseClick(findChild(error, "inlineErrorRetry"))
            compare(spy.count, 1)
        }
        function test_wrappedButtonAndTallLinesKeepTheIconOnTheFirstLine() {
            for (const text of ["Nghe tiếp", "Nghe tiếp\u00a0·\u00a0Chương 12: một tên chương rất dài để gãy dòng"]) {
                const button = createTemporaryObject(wrapButton, host, {text: text})
                waitForRendering(button)
                compare(JSON.stringify(IconText.scan(button, qtVisualReady)), "[]", text)
            }
            const lines = createTemporaryObject(tallLines, host)
            waitForRendering(lines)
            verify(lines.children[1].lineCount > 1)
            compare(JSON.stringify(IconText.scan(lines, qtVisualReady)), "[]")
        }
        function test_alignedRowAndSkipDigitsPass() {
            compare(hitsOf(aligned), [])
            compare(hitsOf(skip), [])
        }
    }
}

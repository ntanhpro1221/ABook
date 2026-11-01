import QtQuick
import QtTest
import "Separators.js" as Separators
import ABook

// Kiểm lực máy dò dấu ngăn ở mép dòng (Separators.js): chuỗi ghép bằng " · " thường gãy ngay trước dấu khi khung hẹp vừa đủ cho mảnh
// đầu - phải bị bắt; ghép bằng "\u00a0· " thì dấu treo cuối dòng 1 - cũng bị bắt; ghép bằng "\u00a0·\u00a0" (cách app ghép) thì dấu
// đi giữa dòng cùng hai mảnh. Flow xuống hàng trước khúc "· …", hay ngay sau khúc "… ·", cũng bị bắt.
Item {
    id: host
    width: 600; height: 400
    TextMetrics { id: first; font.pixelSize: 14; text: "Đang làm dở" }
    TextMetrics { id: hung; font.pixelSize: 14; text: "Đang làm dở\u00a0·" }   // vừa đủ cho mảnh đầu kèm dấu dính trước: dấu ở lại dòng 1
    Component {
        id: wrapped
        Text { width: first.advanceWidth + 6; wrapMode: Text.WordWrap; font.pixelSize: 14 }
    }
    Component {
        id: flowRow
        Flow {
            width: first.advanceWidth + 6
            Text { text: "Đang làm dở"; font.pixelSize: 14 }
            Text { text: "· 12 chương"; font.pixelSize: 14 }
        }
    }
    Component {
        id: flowTail
        Flow {
            width: first.advanceWidth + 6
            Text { text: "Đang làm dở\u00a0·"; font.pixelSize: 14 }
            Text { text: "12 chương"; font.pixelSize: 14 }
        }
    }
    // Mảnh phụ dùng chung của app: cùng hàng thì có dấu, bị đẩy xuống hàng mới thì đứng đầu hàng KHÔNG dấu
    Component {
        id: detailRow
        Flow {
            property alias detail: piece
            spacing: 4
            Text { text: "Đang làm dở"; font.pixelSize: 14 }
            FlowDetail { id: piece; detail: "142.329 chữ"; font.pixelSize: 14; font.features: { "tnum": 1 } }   // số đều: TextMetrics đo hụt, chữ gãy "chữ" xuống dòng
        }
    }
    TestCase {
        name: "Separators"
        when: windowShown
        function hitsOf(component, properties) {
            const scene = createTemporaryObject(component, host, properties || {})
            waitForRendering(scene)
            return Separators.scan(scene, qtVisualReady)
        }
        function test_plainSpaceBreaksBeforeTheDot() {
            const hits = hitsOf(wrapped, {text: "Đang làm dở · 3/10 chương"})
            compare(hits.length, 1, JSON.stringify(hits)); compare(hits[0].rule, "dot-starts-line")
        }
        function test_separatorBoundOnlyBeforeHangsAtTheLineEnd() {
            const hits = hitsOf(wrapped, {text: "Đang làm dở\u00a0· 3/10 chương", width: hung.advanceWidth + 6})
            compare(hits.length, 1, JSON.stringify(hits)); compare(hits[0].rule, "dot-ends-line"); compare(hits[0].line, 1)
        }
        function test_separatorBoundToBothPiecesStaysInsideTheLine() {
            for (const width of [first.advanceWidth + 6, hung.advanceWidth + 6]) {
                const scene = createTemporaryObject(wrapped, host, {text: "Đang làm dở\u00a0·\u00a03/10 chương", width: width})
                waitForRendering(scene)
                verify(scene.lineCount > 1); compare(Separators.scan(scene, qtVisualReady), [])
            }
        }
        function test_flowWrappingAfterADotIsCaught() {
            const hits = hitsOf(flowTail)
            compare(hits.length, 1, JSON.stringify(hits)); compare(hits[0].rule, "dot-ends-flow-row")
        }
        function test_flowWrappingBeforeTheDotIsCaught() {
            const hits = hitsOf(flowRow)
            compare(hits.length, 1, JSON.stringify(hits)); compare(hits[0].rule, "dot-starts-flow-row")
        }
        function test_flowDetailDropsItsDotOnlyWhenItLeadsTheRow() {
            const wide = createTemporaryObject(detailRow, host, {width: 400})
            waitForRendering(wide)
            compare(wide.detail.text, "· 142.329 chữ"); verify(wide.detail.x > 1); compare(wide.detail.lineCount, 1)
            const narrow = createTemporaryObject(detailRow, host, {width: first.advanceWidth + 6})
            waitForRendering(narrow)
            compare(narrow.detail.x, 0); compare(narrow.detail.text, "142.329 chữ"); compare(narrow.detail.lineCount, 1)
            compare(Separators.scan(narrow, qtVisualReady), [])
            // bề rộng theo bản có dấu: bỏ dấu không kéo mảnh về hàng trên rồi lại đẩy xuống
            compare(narrow.detail.width, Math.min(wide.detail.width, narrow.width))
        }
    }
}

import QtQuick
import QtTest
import "Orphans.js" as Orphans
import "../../qml/TextWrap.js" as TextWrap
import ABook

// Kiểm lực máy dò chữ mồ côi (Orphans.js) và text-wrap: pretty của app (TextWrap.js): câu gãy để một từ ngắn ở dòng cuối phải bị
// bắt; cùng câu qua TextWrap.pretty thì hai từ cuối xuống dòng cùng nhau - sạch. Đoạn mới ngắn (xuống dòng cứng), câu một dòng,
// dòng trên ngắn và từ cuối dài đều không phải chữ mồ côi.
Item {
    id: host
    width: 600; height: 400
    readonly property string sentence: "Bạn hãy thử tải lại tiến độ."
    TextMetrics { id: head; font.pixelSize: 14; text: "Bạn hãy thử tải lại tiến" }
    TextMetrics { id: shortHead; font.pixelSize: 14; text: "Tải lại" }
    Component {
        id: wrapped
        Text { width: head.advanceWidth + 4; wrapMode: Text.Wrap; font.pixelSize: 14; textFormat: Text.PlainText }
    }
    TestCase {
        name: "Orphans"
        when: windowShown
        function hits(text, width) {
            const item = createTemporaryObject(wrapped, host, width ? {text: text, width: width} : {text: text})
            waitForRendering(item)
            return Orphans.scan(item, qtVisualReady)
        }
        function test_shortLastWordIsCaught() {
            const found = hits(host.sentence)
            compare(found.length, 1)
            compare(found[0].last, "độ.")
        }
        function test_prettyKeepsTheLastTwoWordsTogether() {
            compare(TextWrap.pretty(host.sentence), "Bạn hãy thử tải lại tiến\u00a0độ.")
            compare(hits(TextWrap.pretty(host.sentence)).length, 0)
        }
        function test_prettyLeavesLongLastWordsAndEachHardLine() {
            compare(TextWrap.pretty("Đã lưu bản sửa của chương"), "Đã lưu bản sửa của chương")
            compare(TextWrap.pretty("Một dòng là đủ\nHai dòng xét từng câu"), "Một dòng là\u00a0đủ\nHai dòng xét từng\u00a0câu")
            compare(TextWrap.pretty("Một"), "Một")
            compare(TextWrap.pretty("Hồ Vy"), "Hồ Vy")                                       // chỗ ngắt duy nhất: giữ
            compare(TextWrap.pretty(TextWrap.pretty(host.sentence)), TextWrap.pretty(host.sentence))
        }
        function test_notOrphans() {
            compare(hits("Bạn hãy thử tải lại tiến\nđộ.").length, 0)                       // đoạn mới cố ý
            compare(hits(host.sentence, 600).length, 0)                                      // một dòng
            compare(hits("Tải lại độ.", shortHead.advanceWidth + 4).length, 0)                  // dòng trên cũng ngắn
            compare(hits("Bạn hãy thử tải lại tiến chương.").length, 0)                      // từ cuối dài
            const solid = createTemporaryObject(wrapped, host, {text: "Bạnhãythửtảilạitiến độ."})   // phần trước một từ: không dời được
            waitForRendering(solid)
            compare(solid.lineCount, 2)
            compare(Orphans.scan(solid, qtVisualReady).length, 0)
        }
    }
}

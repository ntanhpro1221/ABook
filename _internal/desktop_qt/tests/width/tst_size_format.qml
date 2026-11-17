import QtQuick
import QtTest
import "../../qml/SizeFormat.js" as Size

// SizeFormat.js = shared/format.ts formatSize của bản web (hệ 1024, Intl vi-VN). Đáp án là kết quả của chính hàm web chạy trong Node cho cùng
// số byte, nên hai bản ghi một cỡ file y hệt nhau ở mọi màn (Cài đặt, Studio, giọng, nhạc, gửi sách). Nhãn hiện lên để máy soát chữ thấy mọi
// ký tự (phẩy, chấm, KB / MB / GB) có trong phông.
Item {
    width: 400
    height: 40
    Text { id: label; font.pixelSize: 14 }

    TestCase {
        name: "SizeFormat"
        when: windowShown

        function test_matchesTheWeb_data() {
            const M = 1024 * 1024, G = 1024 * M
            return [
                {tag: "0 byte", bytes: 0, text: "1\u00a0KB"},
                {tag: "nửa KB", bytes: 500, text: "1\u00a0KB"},
                {tag: "50\u00a0KB", bytes: 51200, text: "50\u00a0KB"},
                {tag: "sát 0,1\u00a0MB", bytes: 104857, text: "102\u00a0KB"},
                {tag: "0,1\u00a0MB", bytes: 104858, text: "0,1\u00a0MB"},
                {tag: "5 triệu byte", bytes: 5000000, text: "4,8\u00a0MB"},
                {tag: "9,96\u00a0MB làm tròn", bytes: 10443817, text: "10\u00a0MB"},
                {tag: "10\u00a0MB", bytes: 10 * M, text: "10\u00a0MB"},
                {tag: "12 triệu byte", bytes: 12000000, text: "11\u00a0MB"},
                {tag: "820\u00a0MB", bytes: 820 * M, text: "820\u00a0MB"},
                {tag: "999,6\u00a0MB", bytes: 999.6 * M, text: "1.000\u00a0MB"},
                {tag: "sát 1\u00a0GB", bytes: G - 1, text: "1.024\u00a0MB"},
                {tag: "1\u00a0GB", bytes: G, text: "1\u00a0GB"},
                {tag: "1,04\u00a0GB bỏ ,0", bytes: 1116691497, text: "1\u00a0GB"},
                {tag: "3,2\u00a0GB", bytes: 3435973837, text: "3,2\u00a0GB"},
                {tag: "5,2 tỉ byte", bytes: 5200000000, text: "4,8\u00a0GB"},
                {tag: "1.500\u00a0GB", bytes: 1500 * G, text: "1.500\u00a0GB"}
            ]
        }
        function test_matchesTheWeb(row) {
            label.text = Size.formatSize(row.bytes)
            compare(label.text, row.text)
        }
        function test_showsEveryLabel() {
            label.text = test_matchesTheWeb_data().map(row => Size.formatSize(row.bytes)).join("\u00a0·\u00a0")
            waitForRendering(label)
            qtGlyphAudit.scan()
        }
    }
}

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
                {tag: "0 byte", bytes: 0, text: "1 KB"},
                {tag: "nửa KB", bytes: 500, text: "1 KB"},
                {tag: "50 KB", bytes: 51200, text: "50 KB"},
                {tag: "sát 0,1 MB", bytes: 104857, text: "102 KB"},
                {tag: "0,1 MB", bytes: 104858, text: "0,1 MB"},
                {tag: "5 triệu byte", bytes: 5000000, text: "4,8 MB"},
                {tag: "9,96 MB làm tròn", bytes: 10443817, text: "10 MB"},
                {tag: "10 MB", bytes: 10 * M, text: "10 MB"},
                {tag: "12 triệu byte", bytes: 12000000, text: "11 MB"},
                {tag: "820 MB", bytes: 820 * M, text: "820 MB"},
                {tag: "999,6 MB", bytes: 999.6 * M, text: "1.000 MB"},
                {tag: "sát 1 GB", bytes: G - 1, text: "1.024 MB"},
                {tag: "1 GB", bytes: G, text: "1 GB"},
                {tag: "1,04 GB bỏ ,0", bytes: 1116691497, text: "1 GB"},
                {tag: "3,2 GB", bytes: 3435973837, text: "3,2 GB"},
                {tag: "5,2 tỉ byte", bytes: 5200000000, text: "4,8 GB"},
                {tag: "1.500 GB", bytes: 1500 * G, text: "1.500 GB"}
            ]
        }
        function test_matchesTheWeb(row) {
            label.text = Size.formatSize(row.bytes)
            compare(label.text, row.text)
        }
        function test_showsEveryLabel() {
            label.text = test_matchesTheWeb_data().map(row => Size.formatSize(row.bytes)).join(" · ")
            waitForRendering(label)
            qtGlyphAudit.scan()
        }
    }
}

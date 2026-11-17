import QtQuick
import ABook

// Sonner ở góc trên phải: lời mới nhất (Đã ghi) trước, cảnh báo vừa phát trước
// nó ở dưới. Hai lời có đồng hồ, nút việc và hiệu ứng đóng/mở độc lập.
// Lớp nổi trên trang: TapShield phủ cả cột (kể cả khe 12 px giữa hai lời - soát 18-11: bấm vào khe ấy từng trúng dòng nằm dưới). Không lời nào
// hiện thì cột cao 0 và không chặn gì.
Item {
    objectName: "toastStack"
    // Toast stays below every open surface, including while either one is moving.
    z: 45
    width: 356
    height: stack.height
    TapShield {}
    Column {
        id: stack
        width: parent.width
        spacing: 12
        Toast { objectName: "successToast" }
        Toast { objectName: "elsewhereToast"; slot: "edited-elsewhere" }
    }
}

import QtQuick
import ABook

// Sonner ở góc trên phải: lời mới nhất (Đã ghi) trước, cảnh báo vừa phát trước
// nó ở dưới. Hai lời có đồng hồ, nút việc và hiệu ứng đóng/mở độc lập.
Column {
    objectName: "toastStack"
    width: 356
    spacing: 12
    Toast { objectName: "successToast" }
    Toast { objectName: "elsewhereToast"; slot: "edited-elsewhere" }
}

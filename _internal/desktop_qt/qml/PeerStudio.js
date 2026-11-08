.import "UiStrings.js" as S
.pragma library

// "Mở Studio" của máy tính đã ghép (shared/peerStudio.ts, webui/peer_studio.py): chữ chép từng chữ. Mọi lời gọi của Studio máy kia đi qua cầu nối
// /api/peers/<mã máy>/studio của máy chủ máy này - mã thiết bị đã nhận lúc ghép không bao giờ xuống giao diện.

/** Đường đi của một lời gọi: qua cầu nối khi đang mở Studio của máy khác, nguyên vẹn khi không. */
function throughPeer(path, peer) { return peer ? "/api/peers/" + peer + "/studio" + path : path }

/** Máy kia chưa cho dòng thiết bị của máy này "Điều khiển sản xuất" - cùng câu máy chủ trả (peer_studio.listen_only). */
function listenOnlyLine(name) { return S.s_chi_nghe_bat_quyen_sua_o_ec16f137 + name + S.s_cai_dat_thiet_bi_7648a732 }

/** Máy cần bật quyền sửa cho trang chỉ nghe: máy tính đang mở qua app này (`peer`), không thì chính máy phục vụ trang (`machine`). */
function listenOnlyOwner(info) { return (info && info.peer && info.peer.name) || (info && info.machine) || S.s_may_tinh_8eafc226 }

/** Dòng ở thanh trên cùng khi đang mở Studio của máy khác: máy ấy không trả lời (câu của máy chủ), chỉ được nghe, hay bình thường. */
function peerBarLine(name, silent, listenOnly) {
    if (silent) return silent + S.s_tu_noi_lai_khi_may_ay_tra_loi_b4bc9400
    return listenOnly ? listenOnlyLine(name) : S.s_dang_mo_studio_cua_cc1c6397 + name
}

/** Máy kia im thì hỏi lại mỗi chừng này, bỏ cuộc sau chừng kia (listen/peerBack.ts watchUntilBack). */
var WATCH_EVERY_MS = 5000
var WATCH_GIVE_UP_MS = 30 * 60000

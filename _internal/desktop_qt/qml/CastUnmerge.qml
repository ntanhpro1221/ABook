import "UiStrings.js" as S
import QtQuick
import ABook
import "CastLogic.js" as Logic
import "EditBookLogic.js" as Edit

// "Bỏ gộp" (useUnmerge.ts): không có đường riêng - tìm đúng lần gộp trong danh sách thay đổi đang chờ rồi rút bằng đường hoàn tác của "Ai nói câu này".
// Dùng chung cho trang sách (Api, máy này) và Studio (`store`: đi đúng máy, kể cả máy tính ghép).
QtObject {
    id: root
    property var store: null
    function ask(method, path, body, done) { return store ? store.quiet(method, path, body, done) : Api.quiet(method, path, body, done) }
    function run(id, person) {
        const name = Logic.cleanName(person.displayName)
        const fail = error => { Api.notice = Edit.toastText(S.s_chua_bo_gop_duoc_68297e79, error) }
        ask("GET", "/api/books/" + id + "/pending-changes", null, function(details, error) {
            if (error) { fail(error); return }
            const stamp = person.mergedAt
            const items = details && details.items ? details.items : []
            const item = typeof stamp === "number" ? items.filter(e => e.section === "speakers" && Math.abs(e.requestedAt - stamp) < 1e-6)[0] : undefined
            if (!item) { fail(S.s_lan_gop_nay_da_duoc_ap_hoac_da_bi_thay_ban_a6f706a3); return }
            const keys = item.keys || [item.key]
            ask("POST", "/api/books/" + id + "/speaker", {lines: keys.map(k => ({stableId: k})), withdraw: true, requestedAt: item.requestedAt}, function(data, err) {
                if (err) { fail(err); return }
                if (root.store) root.store.editedCast(id); else Api.editedBook(id)
                Api.notice = S.s_da_bo_gop_961aed25 + name
            })
        })
    }
}

import "UiStrings.js" as S
import QtQuick
import ABook
import "NewProjectLogic.js" as Logic

// Khung "Phần N của …" khi tạo phần nối tiếp (SeedBanner): nối sau phần nào, mang theo gì, thiếu gì; "Bỏ nối tiếp" thì sách phân vai lại từ đầu (Hoàn tác trong toast).
// Hẹp: nút bỏ xuống dưới đoạn chữ thay vì ép chữ thành cột hẹp.
Item {
    id: root
    property var form: null
    readonly property var seed: form ? form.draft.seed : undefined
    readonly property bool hasFiles: Boolean(form && form.scan && form.scan.files.length)
    readonly property bool wide: width >= 640
    implicitHeight: shown.height
    height: implicitHeight

    Collapse {
        id: shown
        width: parent.width
        open: Boolean(root.seed)
        // Giữ nội dung cuối trong lúc khép
        property var last: null
        Connections { target: root; function onSeedChanged() { if (root.seed) shown.last = root.seed } }
        Component.onCompleted: last = root.seed
        Item {
            id: box
            readonly property var seed: root.seed || shown.last
            width: parent.width
            height: 20 + Math.max(body.height, root.wide ? drop.height : body.height + 4 + drop.height) + 16
            Icon { x: 0; y: 20 + 16 + 2; name: "layers"; size: 16; color: Theme.accentText }
            Column {
                id: body
                objectName: "newSeedBanner"
                x: 28
                y: 36
                width: root.wide ? parent.width - 28 - drop.width - 12 : parent.width - 28
                spacing: 4
                Prose { strong: true; tone: Theme.text; text: box.seed ? S.s_phan_0_1_07722a78(box.seed.part, box.seed.title) : " " }
                Prose {
                    visible: Boolean(box.seed) && Boolean(box.seed.clickedTitle)
                    text: box.seed ? S.s_noi_sau_26bf063a + (box.seed.latestTitle || box.seed.title) + S.s_giu_c0878737 + Logic.carriedText(box.seed.carries) + "." : ""
                }
                Prose {
                    visible: Boolean(box.seed) && !box.seed.clickedTitle
                    text: box.seed ? S.s_giu_d3777f80 + Logic.carriedText(box.seed.carries) + S.s_giong_va_cach_doc_ten_995cc280 : ""
                }
                // Khung "chưa có chương mới" tắt ngay khi đã chọn / thêm được file
                Prose {
                    visible: Boolean(box.seed && box.seed.folder)
                    topPadding: visible ? 4 : 0
                    text: visible ? S.s_continuation_hint(box.seed.folder) : ""
                }
                Prose {
                    objectName: "newSeedEmpty"
                    visible: Boolean(box.seed) && box.seed.empty && !root.hasFiles
                    topPadding: visible ? 4 : 0
                    text: box.seed ? (box.seed.folder ? S.s_chon_file_moi_sau_5b6856da + (box.seed.lastChapter || S.s_chuong_cuoi_phan_truoc_7e3d0c5b) + S.s_o_duoi_a9e009c8 : S.s_chon_file_chuong_moi_o_duoi_0af6839c) : ""
                }
                Prose {
                    objectName: "newSeedModelMissing"
                    visible: Boolean(box.seed) && Boolean(box.seed.analysisModelMissing)
                    topPadding: visible ? 4 : 0
                    tone: Theme.warning
                    text: S.s_thieu_bo_phan_tich_cua_phan_truoc_doi_bo_c_9b47e7fe
                }
                Prose {
                    objectName: "newSeedUnanalyzed"
                    visible: Boolean(box.seed) && !box.seed.analyzed
                    topPadding: visible ? 4 : 0
                    tone: Theme.warning
                    text: S.s_phan_truoc_chua_phan_tich_xong_chi_mang_du_6719c096
                }
            }
            TextLink {
                id: drop
                objectName: "newSeedDrop"
                x: root.wide ? parent.width - width : 28
                y: root.wide ? 20 + 12 : 36 + body.height + 4
                text: S.s_bo_noi_tiep_2b7945ba
                small: true
                onClicked: root.form.dropSeed()
            }
        }
    }
}

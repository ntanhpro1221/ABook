package vn.abook.player

import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

/**
 * Gộp xưởng khi nhập file dự án của CÙNG cuốn (WorkshopMerge, soát UX a25 T5) so với bản Python (webui/workshop_merge.py) qua bộ ví
 * dụ dùng chung tests/fixtures/book_edits/workshop_merge/<ca>.json: {now, local, incoming, merged, report}.
 */
class WorkshopMergeTest {
    @Test
    fun every_workshop_merge_case_gives_what_python_gave() {
        val names = BookEditsFixtures.cases("workshop_merge")
        assertTrue(names.size >= 2)
        for (name in names) {
            val case = BookEditsFixtures.obj("workshop_merge/$name.json")
            val (merged, report) = WorkshopMerge.files(case.getJSONObject("local"), case.getJSONObject("incoming"), case.getDouble("now"))
            if (!StrictJson.equal(case.getJSONObject("report"), report)) fail("$name: báo cáo ${StrictJson.dumps(report)}")
            if (!StrictJson.equal(case.getJSONObject("merged"), merged)) fail("$name: kết quả gộp\n${StrictJson.dumps(merged)}")
        }
    }
}

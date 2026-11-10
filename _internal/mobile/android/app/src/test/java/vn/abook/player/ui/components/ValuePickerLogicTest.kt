package vn.abook.player.ui.components

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import vn.abook.player.BookEditsFixtures

/**
 * Bộ chọn giá trị: MỘT bộ ca cho ba nền (web valuePickerLogic.test.ts, Qt tst_value_picker) - tests/fixtures/value_picker/cases.json.
 * Mỗi ca kiểm một luật (kẹp, bước, kéo + nấc hút, vị trí trên thước, gõ số, chip tô, rung nấc, định dạng số).
 */
class ValuePickerLogicTest {
    private val fixture = JSONObject(BookEditsFixtures.file("../value_picker/cases.json").readText(Charsets.UTF_8))

    private fun numbers(array: JSONArray) = (0 until array.length()).map { array.getDouble(it) }

    @Test fun balancedRowsUseTheSharedCases() {
        val cases = fixture.getJSONArray("chipRows")
        for (i in 0 until cases.length()) {
            val c = cases.getJSONObject(i)
            assertEquals(numbers(c.getJSONArray("out")).map { it.toInt() },
                ValuePickerLogic.chipRows(numbers(c.getJSONArray("widths")).map { it.toInt() }, c.getInt("available"), c.getInt("gap")).map { it.count() })
        }
    }

    @Test fun everyStepInvertsAndWideDetentsHaveRoom() {
        for ((name, spec) in ValueSpecs.all) {
            for (i in 0..Math.round((spec.max - spec.min) / spec.step).toInt()) {
                val value = ValuePickerLogic.step(spec, spec.min, i)
                assertEquals("$name $value", value, ValuePickerLogic.fromFraction(spec, ValuePickerLogic.toFraction(spec, value)), 0.0)
            }
            if (spec.min > 0 && spec.max / spec.min >= 8) spec.typical.zipWithNext().forEach { (a, b) ->
                org.junit.Assert.assertTrue(name, (ValuePickerLogic.toFraction(spec, b) - ValuePickerLogic.toFraction(spec, a)) * 200 >= 24)
            }
        }
    }

    private fun specOf(json: JSONObject) = ValueSpec(
        json.getDouble("min"), json.getDouble("max"), json.getDouble("step"), numbers(json.getJSONArray("typical")),
        json.optJSONArray("scale")?.let { scale -> (0 until scale.length()).map { scale.getJSONArray(it).getDouble(0) to scale.getJSONArray(it).getDouble(1) } }.orEmpty(),
    )

    @Test fun theNativeTableIsTheSharedTable() {
        assertEquals(fixture.getDouble("snapSteps"), ValuePickerLogic.SNAP_STEPS, 0.0)
        assertEquals(fixture.getInt("pageSteps"), ValuePickerLogic.PAGE_STEPS)
        val specs = fixture.getJSONObject("specs")
        assertEquals(specs.keys().asSequence().toSet(), ValueSpecs.all.keys)
        for (name in specs.keys()) assertEquals(name, specOf(specs.getJSONObject(name)), ValueSpecs.all.getValue(name))
    }

    @Test fun everySharedCase() {
        val specs = fixture.getJSONObject("specs")
        val cases = fixture.getJSONArray("cases")
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            val spec = specOf(specs.getJSONObject(case.getString("spec")))
            val name = "${case.getString("spec")} ${case.getString("op")} ${case.get("in")}"
            when (case.getString("op")) {
                "clamp" -> assertEquals(name, Parsed(case.getDouble("out"), case.getBoolean("clamped")), ValuePickerLogic.clamp(spec, case.getDouble("in")))
                "step" -> assertEquals(name, case.getDouble("out"), ValuePickerLogic.step(spec, case.getDouble("in"), case.getInt("steps")), 0.0)
                "fromFraction" -> assertEquals(name, case.getDouble("out"), ValuePickerLogic.fromFraction(spec, case.getDouble("in")), 0.0)
                "toFraction" -> assertEquals(name, case.getDouble("out"), ValuePickerLogic.toFraction(spec, case.getDouble("in")), 1e-9)
                "parse" -> {
                    val parsed = ValuePickerLogic.parse(spec, case.getString("in"))
                    if (case.isNull("out")) assertNull(name, parsed)
                    else assertEquals(name, Parsed(case.getDouble("out"), case.getBoolean("clamped")), parsed)
                }
                "chip" -> assertEquals(name, case.getInt("out"), ValuePickerLogic.chipIndex(spec, case.getDouble("in")))
                "detent" -> assertEquals(name, case.getBoolean("out"), ValuePickerLogic.isDetent(spec, case.getDouble("prev"), case.getDouble("in")))
                "format" -> assertEquals(name, case.getString("out"), ValuePickerLogic.format(spec, case.getDouble("in")))
                else -> error("ca lạ: $name")
            }
        }
    }

    /** Nấc hút không nuốt bước kề: kéo tới được MỌI giá trị trong biên. */
    @Test fun everyValueIsReachableByDragging() {
        for ((name, spec) in ValueSpecs.all) {
            val reached = (0..20_000).map { ValuePickerLogic.fromFraction(spec, it / 20_000.0) }.toSet()
            assertEquals(name, Math.round((spec.max - spec.min) / spec.step).toInt() + 1, reached.size)
        }
    }
}

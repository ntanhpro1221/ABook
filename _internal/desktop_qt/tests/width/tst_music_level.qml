import QtQuick
import QtTest
import ABook

Item {
    width: 360
    height: 240
    MusicLevelSlider { id: level; width: 280; value: -18.5 }
    SignalSpy { id: saves; target: level; signalName: "picked" }
    TestCase {
        name: "MusicLevelSlider"
        when: windowShown
        function init() {
            level.enabled = true
            level.value = -18.5
            const slider = findChild(level, "musicLevelSlider")
            slider.value = -18.5
            saves.clear()
        }
        function test_drag_commits_on_release() {
            const slider = findChild(level, "musicLevelSlider")
            compare(slider.from, -40)
            compare(slider.to, -6)
            compare(slider.stepSize, 1)
            mousePress(slider, slider.width / 2, slider.height / 2)
            mouseMove(slider, slider.width - 1, slider.height / 2)
            compare(saves.count, 0)
            mouseRelease(slider, slider.width - 1, slider.height / 2)
            compare(saves.count, 1)
            compare(saves.signalArguments[0][0], -6)
        }
        function test_reset() {
            mouseClick(findChild(level, "musicLevelReset"))
            compare(saves.count, 1)
            compare(saves.signalArguments[0][0], -20)
        }
        function test_disabled() {
            level.enabled = false
            const slider = findChild(level, "musicLevelSlider")
            mouseClick(slider, slider.width - 1, slider.height / 2)
            compare(saves.count, 0)
        }
        function test_save_blocks_input_then_reset_sends_old_value() {
            const slider = findChild(level, "musicLevelSlider")
            level.value = -20
            slider.value = -19
            slider.moved()
            compare(saves.count, 1)
            level.enabled = false
            mouseClick(findChild(level, "musicLevelReset"))
            compare(saves.count, 1)
            level.value = -19
            level.enabled = true
            mouseClick(findChild(level, "musicLevelReset"))
            compare(saves.count, 2)
            compare(saves.signalArguments[1][0], -20)
        }
    }
}

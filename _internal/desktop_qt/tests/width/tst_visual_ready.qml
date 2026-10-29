import QtQuick
import QtTest
import "VisualReady.js" as VisualReady

Item {
    id: host
    width: 300; height: 100
    Text { text: "Ready" }
    Item {
        id: motion
        property real value: 0
        Behavior on value { NumberAnimation { duration: 180 } }
    }
    Item {
        id: sequence
        property real value: 0
        SequentialAnimation {
            id: fade
            NumberAnimation { target: sequence; property: "value"; to: 1; duration: 180 }
        }
    }
    Item {
        id: continuous
        property real value: 0
        NumberAnimation on value { from: 0; to: 1; duration: 180; loops: Animation.Infinite; running: true }
        Timer { interval: 10; repeat: true; running: true }
    }
    TestCase {
        name: "VisualReady"
        when: windowShown
        function test_behaviorIsObserved() {
            motion.value = motion.value === 0 ? 1 : 0
            verify(!VisualReady.settled(motion, qtVisualReady), "must observe Behavior animation")
            tryVerify(function() { return VisualReady.settled(motion, qtVisualReady) })
        }
        function test_sequenceIsObserved() {
            fade.restart()
            verify(!VisualReady.settled(sequence, qtVisualReady), "must observe sequential animation")
            tryVerify(function() { return VisualReady.settled(sequence, qtVisualReady) })
        }
        function test_renderWaitsForAQueuedTransition() {
            const target = motion.value === 0 ? 1 : 0
            Qt.callLater(function() { motion.value = target })
            VisualReady.render(this, host.Window.window, host, qtVisualReady)
            compare(motion.value, target)
            verify(VisualReady.settled(motion, qtVisualReady))
        }
        function test_infiniteAnimationAndTimerDoNotBlock() {
            verify(VisualReady.settled(continuous, qtVisualReady))
        }
    }
}

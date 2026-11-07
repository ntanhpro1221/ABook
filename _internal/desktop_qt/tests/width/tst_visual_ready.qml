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
        id: roundTrip
        property real value: 1
        SequentialAnimation {
            id: roundTripFade
            NumberAnimation { target: roundTrip; property: "value"; to: 0; duration: 90 }
            NumberAnimation { target: roundTrip; property: "value"; to: 1; duration: 220 }
        }
    }
    Item {
        id: controlled
        property real value: 0
        NumberAnimation { id: linear; target: controlled; property: "value"; from: 0; to: 1; duration: 1000 }
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
        function test_initialEndpointDoesNotMeanTheSequenceFinished() {
            roundTripFade.restart()
            compare(roundTrip.value, 1)
            verify(!VisualReady.settled(roundTrip, qtVisualReady))
            VisualReady.waitForSettledFrame(this, host.Window.window, host, qtVisualReady)
            compare(roundTrip.value, 1)
            verify(VisualReady.settled(roundTrip, qtVisualReady))
        }
        function test_manualClockAdvancesAnimationTime() {
            qtAnimationClock.begin()
            try {
                linear.restart()
                qtAnimationClock.step(100)
                verify(controlled.value > 0 && controlled.value < 1)
                const first = controlled.value
                qtAnimationClock.step(100)
                fuzzyCompare(controlled.value - first, 0.1, 0.001)
                qtAnimationClock.step(1000)
                compare(controlled.value, 1)
                compare(linear.running, false)
            } finally {
                qtAnimationClock.end()
            }
        }
        function test_infiniteAnimationAndTimerDoNotBlock() {
            verify(VisualReady.settled(continuous, qtVisualReady))
        }
    }
}

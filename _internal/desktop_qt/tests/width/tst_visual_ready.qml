import QtQuick
import QtTest
import ABook
import "VisualReady.js" as VisualReady

Item {
    id: host
    width: 300; height: 100
    Text { text: "Ready" }
    Vu { id: liveVu; x: 280; still: false }
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
    Column {
        id: textLayout
        width: 260
        Text {
            id: wrapped
            width: parent.width
            text: "Một đoạn chữ dài cần xuống dòng sau khi đổi chiều rộng và cỡ phông chữ."
            wrapMode: Text.Wrap
            font.pixelSize: 12
        }
        Item { id: following; width: 1; height: 1 }
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
        function test_queuedTextMetricsAndColumnLayoutArePainted() {
            for (const width of [110, 260]) {
                Qt.callLater(function() { textLayout.width = width; wrapped.font.pixelSize = width === 110 ? 24 : 12 })
                VisualReady.waitForSettledFrame(this, host.Window.window, host, qtVisualReady)
                compare(textLayout.width, width)
                compare(wrapped.font.pixelSize, width === 110 ? 24 : 12)
                verify(wrapped.lineCount > 1)
                compare(following.y, wrapped.height)
                compare(textLayout.height, wrapped.height + following.height)
                verify(!isPolishScheduled(host.Window.window))
                verify(qtVisualReady.lines(wrapped).length === wrapped.lineCount)
            }
        }
        function test_metricReadQueuesAnotherLayoutPass() {
            // Model a metric getter/response invalidating layout at the last
            // readiness check. The helper must observe the new geometry and
            // polish it before returning, even when no animation is running.
            let firstFrame = null
            let queued = false
            const probe = {settled: function() {
                const frame = qtFullRepaint.frames()
                if (firstFrame === null) firstFrame = frame
                else if (!queued && frame > firstFrame) {
                    queued = true
                    Qt.callLater(function() { textLayout.width = 110; wrapped.font.pixelSize = 24 })
                }
                return true
            }}
            textLayout.width = 260; wrapped.font.pixelSize = 12
            VisualReady.waitForSettledFrame(this, host.Window.window, host, probe)
            verify(queued)
            compare(textLayout.width, 110)
            compare(following.y, wrapped.height)
            verify(!isPolishScheduled(host.Window.window))
        }
        function test_layoutWaitKeepsPerpetualIndicatorsRunning() {
            liveVu.still = false
            VisualReady.waitForSettledFrame(this, host.Window.window, host, qtVisualReady)
            compare(liveVu.still, false)
        }
    }
}

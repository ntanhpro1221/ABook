import QtQuick
import QtTest
import ABook

Item {
    id: host
    width: 300; height: 200
    Component {
        id: sample
        Rectangle {
            id: row
            property bool allowed: true
            property bool expanded: true
            width: 120; height: 40
            enabled: allowed
            opacity: allowed ? 1 : 0.5
            Reveal { id: controller; objectName: "controller"; shown: row.expanded }
        }
    }
    Component {
        id: holder
        Item {
            width: 200; height: 60
            Rectangle {
                id: inner
                property bool expanded: true
                width: 120; height: 40
                Reveal { objectName: "controller"; shown: inner.expanded }
            }
        }
    }
    TestCase {
        name: "RevealLifetime"
        when: windowShown
        function cleanup() { Theme.reduceMotion = false }
        function test_exit_data() { return [{tag: "normal", reduced: false}, {tag: "reduced", reduced: true}] }
        function test_exit(data) {
            Theme.reduceMotion = data.reduced
            const row = createTemporaryObject(sample, host)
            verify(row)
            verify(row.visible)
            row.expanded = false
            verify(row.visible, "keep the outgoing item until its fade finishes")
            verify(!row.enabled, "closing blocks input immediately")
            const control = findChild(row, "controller")
            tryVerify(() => control.progress > 0 && control.progress < 1)
            verify(row.visible)
            tryCompare(row, "visible", false)
            compare(row.opacity, 0)
            row.allowed = false
            row.expanded = true
            tryCompare(control, "progress", 1)
            verify(row.visible)
            verify(!row.enabled, "restore the caller's enabled binding")
            compare(row.opacity, 0.5, "the caller's own opacity returns once fully shown")
            row.allowed = true
            verify(row.enabled)
            compare(row.opacity, 1)
        }
        function test_reverse() {
            const row = createTemporaryObject(sample, host)
            row.expanded = false
            const control = findChild(row, "controller")
            tryVerify(() => control.progress > 0 && control.progress < 1)
            const middle = control.progress
            row.expanded = true
            verify(control.progress >= middle && control.progress < 1, "reverse the current fade")
            tryCompare(control, "progress", 1)
            verify(row.visible && row.enabled)
        }
        function test_leaves_the_visual_tree() {
            const row = createTemporaryObject(sample, host)
            const control = findChild(row, "controller")
            verify(control, "still reachable as a QObject child")
            compare(row.children.length, 0, "children[0] and positioners see only what the caller wrote")
            compare(control.target, row)
            row.expanded = false
            tryCompare(row, "visible", false)
            row.expanded = true
            tryCompare(control, "progress", 1)
            verify(row.visible && row.enabled)
        }
        function test_disabled_parent_does_not_stick() {
            const box = createTemporaryObject(holder, host, {enabled: false})
            const row = box.children[0]
            row.expanded = false
            tryCompare(row, "visible", false)
            row.expanded = true
            box.enabled = true
            tryCompare(findChild(row, "controller"), "progress", 1)
            verify(row.enabled, "an ancestor's disabled state is not saved as the item's own")
            box.enabled = false
            row.expanded = false
            box.enabled = true
            verify(!row.enabled, "closing still blocks input once the ancestor is enabled again")
            row.expanded = true
            verify(row.enabled)
        }
        function test_starts_hidden_without_flash() {
            const row = createTemporaryObject(sample, host, {expanded: false})
            const control = findChild(row, "controller")
            compare(control.progress, 0)
            verify(!row.visible, "a closed item never paints on creation")
        }
    }
}

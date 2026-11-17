import QtQuick
import QtTest
import ABook
import "VisualReady.js" as VisualReady

// Invented names exercise the actual device, destination and listening-profile surfaces.
Item {
    id: host
    width: 1024
    height: 1100
    readonly property string longName: "Điện thoại OPPO Find X8 Ultra của Nguyễn Văn An"
    FontMetrics { id: nameMetrics }
    Component { id: phone; PhoneSyncDevice {} }
    Component { id: computer; OtherComputersRow {} }
    Component { id: peer; PeerBar {} }
    Component { id: chip; RecordChip {} }
    Component { id: records; RecordMenu {} }
    Component { id: inbox; PhoneEdits {} }
    Component { id: output; OutputPopover {} }
    Component { id: deviceButton; Button { nameText: true; icon: "bluetooth"; kind: "ghost"; size: "sm" } }

    TestCase {
        name: "RemoteProfileNames"
        when: windowShown
        property var outputBefore: []
        function ready() { VisualReady.render(this, host.Window.window, host, qtVisualReady) }
        function init() {
            outputBefore = OutputDevices.devices
            Theme.reduceMotion = true
            Nav.layers = []
            Platform.reset()
            DesktopApi.reset()
            Api.bind(DesktopApi, Theme)
        }
        function cleanup() { Nav.layers = []; Theme.reduceMotion = false; OutputDevices.devices = outputBefore }
        function clean(text) { return String(text).replace(/\u00a0/g, " ") }
        function uncut(label) {
            verify(label !== null)
            compare(label.elide, Text.ElideNone)
            verify(!label.truncated, "complete name: " + label.text)
            verify(label.paintedWidth <= label.width + 1, "name stays within its row")
            verify(label.paintedHeight <= label.height + 1, "row grows to the complete name")
            verify(label.font.pixelSize >= Math.ceil(label.baseSize * 0.75))
            if (label.fit === "wrap") {
                compare(label.font.pixelSize, label.baseSize)
                // RichText reports lineCount=1 even for its wrapped text document.
                nameMetrics.font = label.font
                if (label.textFormat === Text.RichText)
                    verify(label.paintedHeight > nameMetrics.height + 1, "rich-text document occupies multiple lines")
                else
                    verify(label.lineCount > 1)
            }
        }
        function test_paired_phone_and_computer_data() { return [{tag: "phone", phone: true}, {tag: "computer", phone: false}] }
        function test_paired_phone_and_computer(data) {
            const item = createTemporaryObject(data.phone ? phone : computer, host, {
                width: 280, rowId: "invented", json: JSON.stringify({id: "invented", name: host.longName,
                    kind: data.phone ? "phone" : "computer", pairedAt: 1700000000, lastSeen: 1700000000})
            })
            const label = findChild(item, "disclosureTitle")
            ready()
            compare(clean(label.text), host.longName)
            compare(label.fit, "wrap")
            uncut(label)
            verify(item.height >= label.height)
            if (data.phone) {
                label.parent.parent.parent.expanded = true
                ready()
                const detail = findChild(item, "pairedDeviceName")
                compare(clean(detail.text), host.longName)
                uncut(detail)
            }
        }
        function test_peer_banner_keeps_name() {
            const item = createTemporaryObject(peer, host, {width: 360, name: host.longName, open: true})
            const label = findChild(item, "peerLine")
            ready()
            verify(clean(label.text).includes(host.longName))
            uncut(label)
            verify(item.height >= label.height)
        }
        function test_profile_chip_and_menu() {
            const item = createTemporaryObject(chip, host, {maxWidth: 260, name: host.longName})
            const menu = createTemporaryObject(records, host, {x: 400, width: 260, book: {records: [{id: "invented", name: host.longName, active: true}]}})
            ready()
            for (const label of [findChild(item, "recordChipName"), findChild(menu, "recordChoiceName")]) {
                compare(clean(label.text), host.longName)
                uncut(label)
            }
            verify(item.height >= findChild(item, "recordChipName").height)
        }
        function test_inbox_name_grows_beyond_action_height() {
            const item = createTemporaryObject(inbox, host, {width: 300, work: {inbox: {data: {
                devices: [{id: "invented", name: host.longName, at: 0, items: []}], skipped: [], recent: [], waiting: 0
            }}}})
            let label = null
            tryVerify(() => { label = findChild(item, "inboxDeviceName"); return label !== null && label.height > 0 })
            ready()
            verify(clean(label.text).includes(host.longName))
            compare(label.fit, "wrap")
            uncut(label)
            verify(label.parent.height >= label.height)
            verify(item.height >= label.mapToItem(item, 0, label.height).y)
        }
        function test_output_device_menu() {
            OutputDevices.devices = [{id: "invented", name: host.longName}]
            const item = createTemporaryObject(output, host, {width: host.width, height: host.height})
            item.show()
            tryCompare(item, "open", true)
            ready()
            const row = findChild(host.Window.window.contentItem, "output_invented")
            const label = findChild(row, "menuRowName")
            compare(clean(label.text), host.longName)
            uncut(label)
            verify(row.height >= label.height)
            item.close()
        }
        function test_bluetooth_name_button() {
            const item = createTemporaryObject(deviceButton, host, {width: 240, text: host.longName})
            ready()
            const label = findChild(item, "buttonDeviceName")
            compare(clean(label.text), host.longName)
            compare(label.fit, "wrap")
            uncut(label)
            verify(item.height >= label.height)
        }
    }
}

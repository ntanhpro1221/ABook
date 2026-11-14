import QtQuick
import QtQuick.Dialogs
import ABook
import "UiStrings.js" as S

CastModal {
    id: root
    panelWidth: 400
    title: S.s_avatar_portrait
    property var person: ({})
    property bool available: false
    property bool pending: false
    property string error: ""
    function begin(data) {
        generation++; bookId = data.bookId; person = data.person; saving = false; pending = false; error = ""; show(); refresh()
    }
    function refresh() {
        const mine = generation
        ask("GET", "/api/books/" + bookId + "/avatar?character=" + encodeURIComponent(person.name), null, function(data, failure) {
            if (mine !== root.generation) return
            if (failure) { root.error = failure; return }
            const wasPending = root.pending
            root.available = Boolean(data.available); root.pending = Boolean(data.pending); root.error = data.error || ""
            if (wasPending && !root.pending) root.saved()
            if (root.pending) poll.restart()
        })
    }
    function change(action, image) {
        if (saving) return
        saving = true
        const mine = generation
        ask("POST", "/api/books/" + bookId + "/avatar", {character: person.name, action: action, data: image || ""}, function(data, failure) {
            if (mine !== root.generation) return
            root.saving = false
            if (failure) { root.error = failure; return }
            if (data.avatar) root.person = Object.assign({}, root.person, {avatar: data.avatar})
            root.pending = Boolean(data.pending); root.saved(); root.refresh()
        })
    }
    Timer { id: poll; interval: 1000; onTriggered: root.refresh() }
    FileDialog { id: picker; nameFilters: ["Images (*.png *.jpg *.jpeg *.webp)"]; onAccepted: {
        const image = DesktopApi.imageData(selectedFile)
        if (image) root.change("upload", image.split(",")[1])
    } }
    Column {
        width: parent.width
        spacing: 12
        AvatarPortrait { name: root.person.name || ""; portrait: root.person.avatar || null; bookId: root.bookId; pixels: 96 }
        Button { text: S.s_chon_anh_41ecf092; enabled: !root.saving; onClicked: picker.open() }
        Button { text: root.pending ? S.s_avatar_generating : S.s_avatar_generate; enabled: !root.saving && !root.pending && root.available; onClicked: root.change("generate") }
        Text {
            Reveal { shown: !root.available }
            width: parent.width; text: S.s_avatar_unavailable; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall; wrapMode: Text.Wrap
        }
        Button { text: S.s_avatar_pattern; enabled: !root.saving; onClicked: root.change("pattern") }
        Text {
            Reveal { shown: root.error !== "" }
            width: parent.width; text: root.error; color: Theme.danger; font.pixelSize: Theme.sizeBodySmall; wrapMode: Text.Wrap
        }
    }
}

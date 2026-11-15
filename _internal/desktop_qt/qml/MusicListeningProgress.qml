import QtQuick
import ABook
import "UiStrings.js" as S
import "MusicLibraryLogic.js" as Logic

Column {
    id: root
    SeekBar { id: seek; width: parent.width; musicMode: true; implicitHeight: 44 }
    Row {
        id: clocks
        width: parent.width
        ClockLabel { width: parent.width / 2; text: Logic.clock(Clip.position); color: Theme.text2; font.pixelSize: Theme.sizeCaption }
        ClockLabel { width: parent.width / 2; text: Logic.clock(Clip.duration); color: Theme.text2; horizontalAlignment: Text.AlignRight; font.pixelSize: Theme.sizeCaption }
    }
}

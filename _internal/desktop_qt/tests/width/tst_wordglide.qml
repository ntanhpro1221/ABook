import QtQuick
import QtTest
import ABook

Item {
    id: host
    width: 1200; height: 1000
    Component { id: scene; ReadAlongView {} }
    TestCase {
        name: "WordGlide"
        when: windowShown
        function init() {
            Platform.reset(); DesktopApi.reset(); Api.bind(DesktopApi, Theme)
            Theme.reduceMotion = false
            Platform.setSetting("readingSize", "20")
            const text = "“Nghĩ văn, chuyện. ...!? nhẹ-nhàng bước qua thềm nắng."
            const tokens = text.split(" ")
            const segments = []
            for (let p = 0; p < 50; p++) segments.push({paragraph:p, text:text, start:p*5, end:p*5+5,
                words:tokens.map((word, i) => [p*5000+i*500, p*5000+(i+1)*500])})
            ReadAlong.active = false
            WidthNet.setReadScript(JSON.stringify({timed:true, segments:segments}))
            Player.open("wordglide", 1, 0, true); Player.pause()
            ReadAlong.active = true
            wait(0) // Drain the controller's queued reload before observing its ready state.
            Player.seek(0.1)
            tryCompare(ReadAlong, "status", "ready")
            compare(Player.bookId,"wordglide")
            tryCompare(ReadAlong, "currentWord", 0)
        }
        function cleanup() { ReadAlong.active = false; Player.open("width",1,0,true); Player.pause(); WidthNet.resetBooks(); Theme.reduceMotion = false }
        function make(width, height) {
            const page = createTemporaryObject(scene, host, {width:width, height:height})
            verify(page !== null)
            const list = findChild(page, "readAlongParagraphs")
            tryVerify(() => list.itemAtIndex(ReadAlong.currentPara) !== null)
            return page
        }
        function test_onlyOneInkAndExactTrimmedBounds() {
            const page = make(720, 640)
            const list = findChild(page, "readAlongParagraphs")
            const ink = findChild(page, "readingWordInk")
            tryCompare(ink, "opacity", 1)
            const item = list.itemAtIndex(0), edit = findChild(item, "readAlongParagraphText")
            const first = edit.positionToRectangle(1), last = edit.positionToRectangle(5)
            fuzzyCompare(ink.width, last.x-first.x, 1)
            fuzzyCompare(ink.x, (item.width-item.textW)/2 + first.x, 1)
            const oldX = ink.x
            Player.seek(0.6)
            tryCompare(ReadAlong, "currentWord", 1)
            tryVerify(() => ink.x > oldX)
            tryVerify(() => Math.abs(ink.width - item.wordRects[0].width) < 1)
            fuzzyCompare(ink.width, edit.positionToRectangle(9).x - edit.positionToRectangle(6).x, 1)
            Player.seek(1.1)
            tryCompare(ReadAlong, "currentWord", 2)
            tryVerify(() => Math.abs(ink.width - (edit.positionToRectangle(17).x - edit.positionToRectangle(11).x)) < 1)
            tryVerify(() => Math.abs(ink.x - ((item.width-item.textW)/2 + edit.positionToRectangle(11).x)) < 0.001)
            const held = ink.x
            Player.seek(1.6)
            tryCompare(ReadAlong, "currentWord", 3)
            wait(Theme.motionFast)
            compare(ink.x, held) // punctuation-only token holds preceding geometry
            Player.seek(2.1)
            tryCompare(ReadAlong, "currentWord", 4)
            tryVerify(() => Math.abs(ink.width - (edit.positionToRectangle(34).x - edit.positionToRectangle(25).x)) < 1)
        }
        function test_returnNeverReservesOrOverlapsControls_data() {
            return [{tag:"small", w:320,h:480,size:20}, {tag:"large-font",w:360,h:640,size:40},
                {tag:"landscape",w:720,h:320,size:32}, {tag:"desktop",w:1100,h:860,size:28}]
        }
        function test_returnNeverReservesOrOverlapsControls(data) {
            Platform.setSetting("readingSize", String(data.size))
            const page = make(data.w, data.h)
            const list = findChild(page, "readAlongParagraphs"), chip = findChild(page, "readingReturn")
            verify(list.y + list.height >= page.height - Theme.s8 - 1)
            page.manual(); page.scrollTo(list.contentHeight - list.height, false); page.refreshPlacement()
            tryCompare(chip, "opacity", 1)
            verify(chip.y >= list.y)
            verify(chip.y + chip.height <= list.y + list.height)
            const old = list.contentY
            page.goBackToReading()
            wait(32)
            verify(list.contentY !== old)
            tryCompare(chip, "opacity", 0)
        }
        function test_reducedMotionPlacesImmediately() {
            Theme.reduceMotion = true
            const page = make(360,640), list = findChild(page,"readAlongParagraphs"), ink = findChild(page,"readingWordInk")
            Player.seek(0.6)
            tryCompare(ReadAlong,"currentWord",1)
            const item = list.itemAtIndex(0)
            tryVerify(() => Math.abs(ink.width - item.wordRects[0].width) < 1)
        }
        function test_sameLineHasIntermediatePosition() {
            const page = make(360,640), list = findChild(page,"readAlongParagraphs"), ink = findChild(page,"readingWordInk")
            tryCompare(ink,"opacity",1)
            const old = ink.x
            qtAnimationClock.begin()
            try {
                Player.seek(0.6)
                wait(0)
                qtAnimationClock.step(32)
                const item=list.itemAtIndex(0), target=(item.width-item.textW)/2+item.wordRects[0].x
                verify(ink.x>old && ink.x<target, "intermediate x="+ink.x+" from="+old+" target="+target)
                qtAnimationClock.step(160)
                fuzzyCompare(ink.x,target,0.5)
            } finally { qtAnimationClock.end() }
        }
        function test_captureMotionFrames() {
            if (!qtWideShotDir) skip("No capture directory")
            const page = make(360,640)
            Player.seek(0.05); wait(160)
            Player.seek(0.6)
            for (let i=0;i<8;i++) {
                wait(16)
                const destination = qtWideShotDir.replace(/\\/g,"/") + "/qt-word-"+i+".png"
                grabImage(page).save(destination)
            }
        }
        function test_lineChangeNeverSweepsDiagonallyAndReflowSnaps() {
            Platform.setSetting("readingSize", "40")
            const page = make(320,640), list = findChild(page,"readAlongParagraphs"), ink = findChild(page,"readingWordInk")
            tryCompare(ink,"opacity",1)
            const item = list.itemAtIndex(0), edit = findChild(item,"readAlongParagraphText")
            let crossing = -1
            for (let w=1;w<9;w++) {
                const a=ReadAlong.wordRects(edit.textDocument,0,0,w-1), b=ReadAlong.wordRects(edit.textDocument,0,0,w)
                if (a.length && b.length && Math.abs(a[0].y-b[0].y)>4) { crossing=w; break }
            }
            verify(crossing>0)
            Player.seek((crossing-1)*0.5+0.1); wait(200)
            const oldY=ink.y, oldWidth=ink.width
            qtAnimationClock.begin()
            try {
                Player.seek(crossing*0.5+0.1); wait(0)
                qtAnimationClock.step(32)
                fuzzyCompare(ink.y,oldY,0.01)
                verify(ink.width>0 && ink.width<oldWidth)
                if(qtWideShotDir) grabImage(page).save(qtWideShotDir.replace(/\\/g,"/")+"/qt-line-32.png")
                qtAnimationClock.step(160)
                const target=item.wordRects[0]
                fuzzyCompare(ink.y,item.y+item.bodyY+target.y+1,0.01)
                fuzzyCompare(ink.width,target.width,0.01)
                if(qtWideShotDir) grabImage(page).save(qtWideShotDir.replace(/\\/g,"/")+"/qt-line-final.png")
            } finally { qtAnimationClock.end() }
            page.width=600
            tryVerify(() => Math.abs(ink.width-item.wordRects[0].width)<0.01 &&
                Math.abs(ink.x-((item.width-item.textW)/2+item.wordRects[0].x))<0.01)
            compare(page.inkTween,false)
        }
    }
}

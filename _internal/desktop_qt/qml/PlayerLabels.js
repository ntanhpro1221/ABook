.pragma library

// labels.ts readerHint, desktop pointer variant. This is a complete sentence
// even when the chapter has no audio or this machine has no installed voice.
function readerHint(textOnly, canSpeak, timed, tapped) {
    const verb = "Bấm"
    if (textOnly) {
        if (!canSpeak) return "Máy này chưa có giọng đọc."
        return tapped ? "Nghe bằng giọng đọc." : `${verb} chữ để nghe từ đó.`
    }
    if (!timed) return "Chưa có audio; bạn vẫn đọc được chữ."
    return tapped ? "" : `${verb} chữ để nghe từ đó.`
}

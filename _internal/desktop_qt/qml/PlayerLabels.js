.import "UiStrings.js" as S
.pragma library

// labels.ts signedNumber / Android PlayerLabels.signed: real minus sign "−" (never a hyphen), "+" when positive,
// decimal comma, at most one decimal - every two-sided value of the Audio and Tone pages.
function signed(value) {
    const text = String(Math.round(Math.abs(value) * 10) / 10).replace(".", ",")
    return text === "0" ? "0" : (value < 0 ? "−" : "+") + text
}

// labels.ts readerHint, desktop pointer variant. This is a complete sentence
// even when the chapter has no audio or this machine has no installed voice.
function readerHint(textOnly, canSpeak, timed, tapped) {
    const verb = S.s_bam_457e5bf3
    if (textOnly) {
        if (!canSpeak) return S.s_may_nay_chua_co_giong_doc_3449f846
        return tapped ? S.s_nghe_bang_giong_doc_ad6d3d0c : S.s_0_chu_de_nghe_tu_do_f3859cf4(verb)
    }
    if (!timed) return S.s_chua_co_audio_ban_van_doc_duoc_chu_6b728db5
    return tapped ? "" : S.s_0_chu_de_nghe_tu_do_f3859cf4(verb)
}

.pragma library
.import "UiStrings.js" as S

// Script identity is carried by the selected text, including when timing is absent.
function identified(source) { return !!source && !!source.stableId && !!source.textSha256 }
function blocked(caps, listenOnly) {
    if (listenOnly) return S.s_may_tinh_chua_cho_ban_sua_6a5d6567
    if (!caps) return S.s_chua_lam_duoc_luc_nay_2e7cacde
    if (caps.link && !caps.workshop) return S.s_sach_nay_lay_tu_may_tinh_khac_muon_sua_thi_d2a5136b
    if (caps.local && !caps.workshop) return S.s_sach_nay_nam_tren_dien_thoai_khac_sua_tung_269dd675
    if (caps.workshop && !caps.toolchain) return S.s_can_cai_studio_7de0b351
    return ""
}
function people(cast, wishes) {
    const seen = {}, out = []
    for (const person of [].concat(cast.characters || [], cast.extras || [], cast.carried || [])) {
        if (!person.voice || seen[person.name]) continue
        seen[person.name] = true
        out.push({value: person.name, label: person.displayName || person.name, lines: person.lines || 0})
    }
    for (const wish of Object.values(wishes.lines || {})) {
        const person = wish.speaker
        if (!person || !person.newGender || seen[person.name]) continue
        seen[person.name] = true
        out.push({value: person.name, label: person.shown, lines: 0, newGender: person.newGender})
    }
    return out
}
function line(source, cast, wishes, timed) {
    const all = people(cast, wishes)
    const person = all.find(p => p.label.toLowerCase() === String(source.speaker || "").toLowerCase() || p.value === source.speaker)
    const wish = (wishes.lines || {})[source.stableId] || {}
    const speaker = wish.speaker
    return {segmentId: source.id, stableId: source.stableId || "", textSha256: source.textSha256 || "", seq: 0,
        text: source.text, kind: source.kind, speaker: source.speaker,
        current: person ? person.value : source.speaker || "NARRATOR", label: person ? person.label : source.speaker || S.s_nguoi_ke_fd36cd15,
        editable: identified(source), hasAudio: !!timed, hint: null,
        emotion: source.emotion === undefined ? null : source.emotion, intensity: source.intensity === undefined ? null : source.intensity,
        spoken: source.spoken === undefined ? null : source.spoken,
        wish: speaker ? {value: speaker.name, label: speaker.shown, state: "pending", held: !!speaker.held} : null,
        lineWish: wish.delivery ? Object.assign({}, wish.delivery, {state: "pending"}) : null,
        verdict: wish.retake ? "redo" : "", retake: wish.retake ? "pending" : null}
}

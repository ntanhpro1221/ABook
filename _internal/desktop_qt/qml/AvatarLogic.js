function hash(name) {
    const bytes = unescape(encodeURIComponent(String(name || "").normalize("NFC")))
    let value = 2166136261
    for (let i = 0; i < bytes.length; i++) value = Math.imul(value ^ bytes.charCodeAt(i), 16777619) >>> 0
    return value
}
function pattern(name) {
    const key = String(name || "").normalize("NFC")
    const value = hash(key)
    const colors = ["#805c38", "#675f48", "#73594c", "#4c6963", "#66607a", "#80565e"]
    const initials = key.replace(/_/g, " ").split(/\s+/).filter(w => w && !/^[IVXLCDM]+$/.test(w))
        .slice(0, 2).map(w => Array.from(w)[0]).join("").toUpperCase()
    return {kind: "pattern", key: key, initials: initials, color: colors[value % colors.length], bits: value & 32767}
}
function voiceFile(name) { return "voice-" + hash(name).toString(16).padStart(8, "0") + ".webp" }
function cell(bits, x, y) { return Boolean(bits & (1 << (y * 3 + Math.min(x, 4 - x)))) }

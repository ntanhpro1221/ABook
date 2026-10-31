.pragma library
.import ABook 1.0 as A

// Ảnh chụp phải nói thật (Lead soát 0.4.151 lượt 2): bộ chụp đặt trạng thái bằng đường người dùng, không ép riêng từng mảnh.
// Hai lời nói dối đã gặp: thanh bên tô "Thư viện" trong khi màn là Studio / Cài đặt (Sidebar trần không nối với màn như Main:
// currentSection = stack.current), và ảnh tối mà ô Màu ở Giao diện chọn "Sáng" (Theme.mode ép tối, tuỳ chọn vẫn "light").
// Dùng: VisualReady.render gọi assertTrue sau mỗi lần dựng; problems() cho bộ thử lực.

const SECTION = {LibraryScreen: 0, StudioScreen: 1, SettingsScreen: 2}

// "StudioScreen_QMLTYPE_12(0x...)" / "StudioScreen(0x...)" -> "StudioScreen"
function typeName(object) {
    return String(object).replace(/(_QMLTYPE_\d+|_QML_\d+)?\(0x[0-9a-fA-F]+.*$/, "")
}

function collect(item, wanted, out) {
    if (!item || item.visible === false || item.opacity === 0) return out
    if (wanted(item)) out.push(item)
    for (const child of item.children || []) collect(child, wanted, out)
    return out
}

function problems(root) {
    const out = []
    const theme = (A.Api.preferences || {}).theme
    if (A.Api.loaded && (theme === "light" || theme === "dark") && A.Theme.dark !== (theme === "dark"))
        out.push({rule: "theme", preference: theme, dark: A.Theme.dark})
    const bars = collect(root, item => typeName(item) === "Sidebar", [])
    const sections = [...new Set(collect(root, item => SECTION[typeName(item)] !== undefined, []).map(item => SECTION[typeName(item)]))]
    if (sections.length === 1)
        for (const bar of bars)
            if (bar.currentSection !== sections[0]) out.push({rule: "sidebar", current: bar.currentSection, screen: sections[0]})
    return out
}

function assertTrue(test, root) {
    const found = problems(root)
    test.verify(found.length === 0, "SHOT_TRUTH " + JSON.stringify(found))
}

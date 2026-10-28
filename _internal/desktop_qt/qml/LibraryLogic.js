.pragma library

// Same contracts as listen/model.ts and librarySort.ts. Keep source order for
// recent; the host already orders by last listen and update time.
function fold(text) { return String(text || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[đĐ]/g, "d").toLowerCase() }
function progress(book) { return book.listeningProgress || (typeof book.progress === "object" ? book.progress : {}) }
function state(book) {
    const p = progress(book)
    return p.finished ? "finished" : (p.heardSeconds > 0 || (book.state && book.state.last) ? "listening" : "new")
}
function matches(book, filter, query) {
    return (filter === "all" || state(book) === filter) && fold([book.title, book.author, book.narrator].join(" ")).indexOf(fold(query.trim())) >= 0
}
function compare(a, b) {
    // QML's JS localeCompare has no numeric option. Compare digit runs first.
    const left = fold(a).match(/\d+|\D+/g) || [], right = fold(b).match(/\d+|\D+/g) || []
    for (let i = 0; i < Math.min(left.length, right.length); ++i) {
        const n = /^\d+$/.test(left[i]) && /^\d+$/.test(right[i]) ? Number(left[i]) - Number(right[i]) : left[i].localeCompare(right[i])
        if (n) return n
    }
    return left.length - right.length
}
function sort(books, order) {
    const result = books.slice()
    if (order === "title") result.sort((a,b) => compare(a.title, b.title))
    else if (order === "author") result.sort((a,b) => {
        const x = (a.author || "").trim(), y = (b.author || "").trim()
        return (!x !== !y) ? (x ? -1 : 1) : compare(x,y) || compare(a.title,b.title)
    })
    else if (order === "added") result.sort((a,b) => (b.addedAt || b.updatedAt || 0) - (a.addedAt || a.updatedAt || 0))
    return result
}
function place(title) {
    title = String(title || "")
    const m = title.match(/^(.*?)\s*[·|:—–-]\s*(Tập|Quyển|Phần|Vol\.?|Book)\s*(\d+)\b/i)
    return m ? {key: "title:" + m[1].trim(), title: m[1].trim(), volume: Number(m[3])}
             : {key: "title:" + title.trim(), title: title.trim(), volume: null}
}
function sections(books) {
    const titles = {}, roots = {}, places = {}, units = {}, candidates = {}
    for (const b of books) { titles[b.bookId] = b.title; if (b.series) roots[b.series.root] = true }
    for (const b of books) {
        let p
        if (b.series) p = {key: "chain:" + b.series.root, title: place(titles[b.series.root] || b.title).title, volume: b.series.part}
        else if (roots[b.bookId]) p = {key: "chain:" + b.bookId, title: place(b.title).title, volume: 1}
        else { p = place(b.title); if (p.volume !== null) units[p.key] = true }
        places[b.bookId] = p
    }
    for (const b of books) {
        const p = places[b.bookId]
        if (p.key.indexOf("title:") === 0 && p.volume === null && units[p.key]) {
            if (!candidates[p.key]) candidates[p.key] = []
            candidates[p.key].push(b)
        }
    }
    for (const key in candidates) {
        const heard = candidates[key].filter(b => b.stage !== "text"), pool = heard.length ? heard : candidates[key]
        if (pool.length === 1) places[pool[0].bookId].volume = 1
    }
    const groups = {}, result = []
    for (const b of books) {
        const p = places[b.bookId], key = p.volume === null ? "book:" + b.bookId : p.key
        if (!groups[key]) { groups[key] = {key: key, title: p.title, books: []}; result.push(groups[key]) }
        groups[key].books.push(b)
    }
    for (const group of result) {
        group.books.sort((a,b) => (places[a.bookId].volume || 0) - (places[b.bookId].volume || 0))
        group.remote = group.books.some(b => !!b.source)
    }
    return result
}
function listening(books, playingId) {
    const current = books.find(b => b.bookId === playingId && !progress(b).finished)
    if (current) return current
    return books.filter(b => !progress(b).finished && b.state && b.state.last)
        .sort((a,b) => b.state.last.at - a.state.last.at)[0] || null
}
function otherBooks(books, currentId, nextId) {
    const eligible = books.filter(b => b.bookId && b.bookId !== currentId && b.bookId !== nextId && b.stage !== "text"
        && b.chaptersAvailable > 0 && !progress(b).finished && !progress(b).caughtUp)
    const started = b => !!(b.state && b.state.last)
    const listening = eligible.filter(started).sort((a,b) => b.state.last.at - a.state.last.at)
    return listening.concat(eligible.filter(b => !started(b))).slice(0, 3)
}

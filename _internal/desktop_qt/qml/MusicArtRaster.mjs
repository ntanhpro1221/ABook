// Artwork v1. Canonical output: 96x96 RGB bytes, row major, no alpha or text.
// Integer arithmetic avoids graphics-driver, font and antialiasing differences.
export function seedOf(link, info) {
    function axis(key) {
        var v = typeof info[key] === "number" && Number.isFinite(info[key]) ? info[key] : 0;
        return Math.floor((Math.max(-1, Math.min(1, v)) + 1) * 100 + 0.5);
    }
    var emotions = info.emotions || {};
    var ranked = Object.keys(emotions).filter(function(k) { return typeof emotions[k] === "number" && Number.isFinite(emotions[k]); });
    ranked.sort(function(a, b) { return emotions[b] - emotions[a] || (a < b ? -1 : a > b ? 1 : 0); });
    var mood = ranked.length ? ranked[0] : "", style = info.style || "";
    link += "|" + style + "|" + axis("valence") + "|" + axis("arousal") + "|" + mood;
    var h = 7;
    for (var i = 0; i < link.length; i++) h = (h * 31 + link.charCodeAt(i)) % 65521;
    var palette = style === "dark" || ["fear", "tension", "anger"].indexOf(mood) >= 0 || axis("valence") < 70 ? 3
        : ["tenderness", "nostalgia", "moved"].indexOf(mood) >= 0 ? 1
        : axis("valence") > 130 || ["joy", "playful"].indexOf(mood) >= 0 ? 2
        : ["medieval_folk", "acoustic_light", "world_other"].indexOf(style) >= 0 ? 4 : 0;
    return h * 25 + Math.min(4, Math.floor(axis("arousal") / 41)) * 5 + palette;
}

export function fallbackSeed(link) {
    return seedOf(link, {});
}

export function rgb(seed) {
    var s = Number.isInteger(seed) && seed >= 0 ? seed % 1638025 : 7;
    var palettes = [
        [[24, 46, 48], [73, 127, 125], [226, 190, 132]],
        [[48, 37, 59], [129, 103, 141], [230, 190, 164]],
        [[48, 40, 30], [159, 113, 64], [236, 211, 165]],
        [[29, 42, 64], [88, 124, 159], [214, 203, 170]],
        [[46, 51, 38], [115, 133, 90], [223, 206, 152]]
    ];
    var p = palettes[s % 5];
    var cx = 22 + s % 51, cy = 20 + Math.floor(s / 53) % 39;
    var radius = 20 + (4 - Math.floor(s / 5) % 5) * 3;
    var rr = radius * radius, out = new Uint8Array(96 * 96 * 3);
    for (var y = 0; y < 96; y++) {
        for (var x = 0; x < 96; x++) {
            var d = (x - cx) * (x - cx) + (y - cy) * (y - cy);
            var glow = Math.max(0, 96 - Math.floor(d / 90));
            var wave = 64 + Math.floor((x - 48) * (x - 48) / 100) - s % 13;
            var band = y >= wave ? 1 : 0;
            var disc = d <= rr;
            var ring = d > rr + 130 && d < rr + 210;
            for (var c = 0; c < 3; c++) {
                var v = Math.floor((p[0][c] * (192 - glow) + p[1][c] * glow) / 192);
                if (disc) v = Math.floor((p[2][c] * 4 + v) / 5);
                if (ring) v = Math.floor((p[1][c] + v) / 2);
                if (band) v = Math.floor((v * 3 + p[1][c]) / 4);
                out[(y * 96 + x) * 3 + c] = v;
            }
        }
    }
    return out;
}

// BMP has a trivial deterministic encoding understood by browser and Qt decoders.
export function bmp(seed) {
    var pixels = rgb(seed), bytes = new Uint8Array(54 + 96 * 96 * 3);
    var view = new DataView(bytes.buffer);
    bytes[0] = 66; bytes[1] = 77;
    view.setUint32(2, bytes.length, true); view.setUint32(10, 54, true);
    view.setUint32(14, 40, true); view.setInt32(18, 96, true); view.setInt32(22, -96, true);
    view.setUint16(26, 1, true); view.setUint16(28, 24, true);
    for (var i = 0; i < pixels.length; i += 3) {
        bytes[54 + i] = pixels[i + 2]; bytes[55 + i] = pixels[i + 1]; bytes[56 + i] = pixels[i];
    }
    return bytes;
}

export function binary(seed) {
    var bytes = bmp(seed), text = "";
    for (var i = 0; i < bytes.length; i++) text += String.fromCharCode(bytes[i]);
    return text;
}

// Qt.btoa encodes a QString as UTF-8. Encode bytes directly so high RGB bytes survive.
export function base64(seed) {
    var data = bmp(seed), alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/", text = "";
    for (var i = 0; i < data.length; i += 3) {
        var a = data[i], b = i + 1 < data.length ? data[i + 1] : 0, c = i + 2 < data.length ? data[i + 2] : 0;
        text += alphabet[a >> 2] + alphabet[((a & 3) << 4) | (b >> 4)]
            + (i + 1 < data.length ? alphabet[((b & 15) << 2) | (c >> 6)] : "=")
            + (i + 2 < data.length ? alphabet[c & 63] : "=");
    }
    return text;
}

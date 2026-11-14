"""Small, versioned artwork descriptor; no network or audio policy changes."""
from __future__ import annotations

import math
from typing import Any


def seed(link: str, info: dict[str, Any]) -> int:
    def axis(key: str) -> int:
        value = info.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            return 100
        return math.floor((max(-1, min(1, value)) + 1) * 100 + .5)
    emotions = info.get("emotions")
    ranked = sorted(((-v, k) for k, v in emotions.items() if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v))) if isinstance(emotions, dict) else []
    text = f"{link}|{info.get('style') or ''}|{axis('valence')}|{axis('arousal')}|{ranked[0][1] if ranked else ''}"
    value = 7
    # UTF-16 code units, shared with ECMAScript and Kotlin, including non-BMP names.
    data = text.encode("utf-16-le", errors="surrogatepass")
    for at in range(0, len(data), 2):
        value = (value * 31 + int.from_bytes(data[at:at + 2], "little")) % 65521
    mood = ranked[0][1] if ranked else ""
    style = info.get("style")
    palette = (3 if style == "dark" or mood in ("fear", "tension", "anger") or axis("valence") < 70
               else 1 if mood in ("tenderness", "nostalgia", "moved")
               else 2 if axis("valence") > 130 or mood in ("joy", "playful")
               else 4 if style in ("medieval_folk", "acoustic_light", "world_other") else 0)
    return value * 25 + min(4, axis("arousal") // 41) * 5 + palette


def descriptor(link: str, info: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"artSeed": seed(link, info)}
    art = info.get("art")
    if isinstance(art, dict) and isinstance(art.get("url"), str) and art["url"].startswith("https://"):
        sha = art.get("sha1")
        if (isinstance(sha, str) and len(sha) == 40 and all(c in "0123456789abcdef" for c in sha)
                and all(isinstance(art.get(k), int) and not isinstance(art[k], bool) and 0 < art[k] <= 512 for k in ("w", "h"))):
            out["art"] = {k: art[k] for k in ("url", "sha1", "w", "h", "source", "landing", "credit", "rights")
                          if k in art and (k in ("w", "h") or isinstance(art[k], str))}
    return out

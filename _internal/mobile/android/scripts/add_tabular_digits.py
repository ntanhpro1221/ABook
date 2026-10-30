"""Add opt-in tnum to the bundled Be Vietnam Pro fonts, preserving existing layout features.

Run with the project's Python (fontTools). Idempotent: an existing tnum is verified, not rewritten.
Only alternate digit outlines/metrics and their GSUB feature are added; default glyphs stay intact.
"""
from pathlib import Path

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables


def add_tabular(path: Path) -> None:
    font = TTFont(path, recalcTimestamp=False)
    table = font["GSUB"].table
    cmap = font.getBestCmap()
    names = [cmap[ord(c)] for c in "0123456789"]
    if not any(f.FeatureTag == "tnum" for f in table.FeatureList.FeatureRecord):
        widest = max(font["hmtx"][name][0] for name in names)
        glyph_set = font.getGlyphSet()
        order = list(font.getGlyphOrder())
        mapping = {}
        for name in names:
            alternate = name + ".tnum"
            advance = font["hmtx"][name][0]
            recording = DecomposingRecordingPen(glyph_set)
            glyph_set[name].draw(recording)
            pen = TTGlyphPen(None)
            recording.replay(TransformPen(pen, (1, 0, 0, 1, (widest - advance) / 2, 0)))
            glyph = pen.glyph()
            glyph.recalcBounds(font["glyf"])
            font["glyf"][alternate] = glyph
            font["hmtx"][alternate] = (widest, glyph.xMin)
            mapping[name] = alternate
        font.setGlyphOrder(order + list(mapping.values()))
        sub = otTables.SingleSubst()
        sub.mapping = mapping
        lookup = otTables.Lookup()
        lookup.LookupType, lookup.LookupFlag = 1, 0
        lookup.SubTable, lookup.SubTableCount = [sub], 1
        index = len(table.LookupList.Lookup)
        table.LookupList.Lookup.append(lookup)
        table.LookupList.LookupCount += 1
        record = otTables.FeatureRecord()
        record.FeatureTag = "tnum"
        record.Feature = otTables.Feature()
        record.Feature.FeatureParams = None
        record.Feature.LookupListIndex, record.Feature.LookupCount = [index], 1
        # Feature records must be sorted by tag; remap every existing language's indices.
        old = list(table.FeatureList.FeatureRecord)
        ordered = sorted(old + [record], key=lambda f: f.FeatureTag)
        for script in table.ScriptList.ScriptRecord:
            langs = [script.Script.DefaultLangSys] + [r.LangSys for r in script.Script.LangSysRecord]
            for lang in filter(None, langs):
                lang.FeatureIndex = sorted([ordered.index(old[i]) for i in lang.FeatureIndex] + [ordered.index(record)])
                lang.FeatureCount = len(lang.FeatureIndex)
                if lang.ReqFeatureIndex != 0xFFFF:
                    lang.ReqFeatureIndex = ordered.index(old[lang.ReqFeatureIndex])
        table.FeatureList.FeatureRecord = ordered
        table.FeatureList.FeatureCount = len(ordered)
        font.save(path)
    check = TTFont(path)
    widths = {check["hmtx"][name + ".tnum"][0] for name in names}
    assert len(widths) == 1, widths
    print(f"{path.name}: tnum digit widths {widths}")


if __name__ == "__main__":
    for file in sorted((Path(__file__).resolve().parents[1] / "app/src/main/res/font").glob("be_vietnam_pro_*.ttf")):
        add_tabular(file)

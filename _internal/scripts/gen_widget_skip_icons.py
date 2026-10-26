"""Sinh ic_widget_back.xml / ic_widget_forward.xml: cùng hình nút lùi / tới 15 giây trong app (web skipIcon, PlayerVisuals.drawSkip).

Số 15 lấy nét thật của Be Vietnam Pro Bold (vector drawable không vẽ được chữ). Chạy:
  runtime/.venv/Scripts/python.exe scripts/gen_widget_skip_icons.py mobile/android/app/src/main/res/font/be_vietnam_pro_bold.ttf mobile/android/app/src/main/res/drawable
"""
import sys
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
font = TTFont(sys.argv[1])
cmap = font.getBestCmap(); gs = font.getGlyphSet(); upm = font['head'].unitsPerEm
names = [cmap[ord(c)] for c in "15"]
tn = [n + '.tf' if n + '.tf' in gs else (n + '.tnum' if n + '.tnum' in gs else n) for n in names]
size = 14.5; s = size / upm; ls = -0.2
adv = [gs[n].width * s for n in tn]
total = sum(adv) + ls
x = 12 - total / 2; base = 22.0
pen = SVGPathPen(gs, ntos=lambda v: ('%.2f' % v).rstrip('0').rstrip('.'))
for n, a in zip(tn, adv):
    gs[n].draw(TransformPen(pen, (s, 0, 0, -s, x, base)))
    x += a + ls
digits = pen.getCommands()
arc_f = "M4.05,9A8.5,8.5 0 0,1 19.95,9"
head_f = "M20.94,6.17L19.95,9L17.34,7.53"
head_b = "M3.06,6.17L4.05,9L6.66,7.53"
def vec(head):
    return f'''<?xml version="1.0" encoding="utf-8"?>
<!-- Cùng hình nút lùi / tới 15 giây trong app (PlayerVisuals.drawSkip, web skipIcon): cung nông, mũi tên ở đầu cung, số 15 (nét lấy từ Be Vietnam Pro) nằm dưới. -->
<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24">
    <path android:strokeColor="#E9ECF0" android:strokeWidth="1.9" android:strokeLineCap="round" android:strokeLineJoin="round" android:pathData="{arc_f}" />
    <path android:strokeColor="#E9ECF0" android:strokeWidth="1.9" android:strokeLineCap="round" android:strokeLineJoin="round" android:pathData="{head}" />
    <path android:fillColor="#E9ECF0" android:pathData="{digits}" />
</vector>
'''
open(sys.argv[2] + '/ic_widget_back.xml', 'w', newline='\n', encoding='utf-8').write(vec(head_b))
open(sys.argv[2] + '/ic_widget_forward.xml', 'w', newline='\n', encoding='utf-8').write(vec(head_f))

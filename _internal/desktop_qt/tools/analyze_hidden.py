"""Summarize wall/media gaps in timestamped MF traces (keep raw lines)."""
import argparse
import json
from pathlib import Path
import re

LINE = re.compile(r"mf t_ms=(\d+) out=(\S+) (?:event=(\d+)|state=(\S+)).*pos=([-\d.]+)")


def gaps(path):
    rows = []
    primary = None
    previous = None
    stalled = None
    for number,line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        match = LINE.search(line)
        if not match:
            continue
        ms,out,event,state,pos = match.groups()
        ms,pos = int(ms),float(pos)
        if primary is None and state == "setRate":
            primary = out
        if out != primary or event != "18":
            continue
        if previous:
            old_ms,old_pos,old_line = previous
            wall,media = (ms-old_ms)/1000,pos-old_pos
            if wall > 0 and 0 <= media < wall * 0.9:
                if stalled is None:
                    stalled = [old_ms,old_pos,old_line,ms,pos,number]
                else:
                    stalled[3:] = [ms,pos,number]
            elif stalled:
                a,p,l,b,q,m = stalled
                if (b-a)/1000-(q-p) > 0.4:
                    rows.append(dict(start_ms=a,end_ms=b,wall_s=round((b-a)/1000,3),media_s=round(q-p,3),
                                     lost_s=round((b-a)/1000-(q-p),3),lines=[l,m],positions=[p,q]))
                stalled = None
        previous = ms,pos,number
    return rows


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    args=ap.parse_args()
    for file in args.files:
        print(str(file), json.dumps(gaps(file), indent=2))


if __name__ == "__main__":
    main()

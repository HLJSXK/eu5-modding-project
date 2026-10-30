# -*- coding: utf-8 -*-
"""Post step: re-encode the cut once (fast), write SRT, then burn subtitles.

Split out from build_cut.py because the concat + burn easily exceeds a single
shell time limit while the per-line segments themselves do not.

Run: python3 post_cut.py <out_dir> [--concat] [--srt] [--burn]
"""
import json, os, subprocess, sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = sys.argv[1]
steps = [a.lstrip("-") for a in sys.argv[2:]] or ["concat", "srt", "burn"]
WORK = os.path.join(OUT, "work")
SEG = os.path.join(WORK, "seg")
LEAD = 0.0  # edl starts already include the silent title card


def ts(x):
    h, r = divmod(x, 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"


if "srt" in steps:
    edl = json.load(open(os.path.join(WORK, "edl.json"), encoding="utf-8"))
    with open(os.path.join(WORK, "subtitles.srt"), "w", encoding="utf-8") as f:
        n = 0
        prev_end = None
        for k, e in enumerate(edl):
            if not e.get("line") or e["line"] == "(hold)":
                continue
            n += 1
            nxt = None
            for later in edl[k + 1:]:
                if later.get("line") and later["line"] != "(hold)":
                    nxt = later["start"] + LEAD
                    break
            a = e["start"] + LEAD
            b = max(a + 0.6, e["end"] + LEAD - 0.10)
            # a subtitle may never run past the next line's start
            if nxt and b > nxt:
                b = max(a + 0.6, nxt - 0.04)
            prev_end = b
            f.write(f"{n}\n{ts(a)} --> {ts(b)}\n{e['line']}\n\n")
    print("srt ok", n)

if "concat" in steps:
    files = sorted(os.listdir(SEG))
    lst = os.path.join(WORK, "list.txt")
    with open(lst, "w") as f:
        for i in files:
            f.write(f"file '{os.path.join(SEG, i)}'\n")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p",
                    os.path.join(WORK, "composed.mp4")], check=True)
    print("concat ok", len(files))

if "burn" in steps:
    srt = os.path.join(WORK, "subtitles.srt").replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    style = ("FontName=Noto Sans CJK SC,FontSize=17,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,"
             "BorderStyle=1,Outline=3,Shadow=0,MarginV=12,Alignment=2,Bold=0")
    final = os.path.join(OUT, "SOL_2026-10_粗剪.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(WORK, "composed.mp4"),
                    "-vf", f"subtitles='{srt}':force_style='{style}'",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p", final],
                   check=True)
    print("burn ok", final)

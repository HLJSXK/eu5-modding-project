# -*- coding: utf-8 -*-
"""Render the real-footage rough cut: each subtitle line gets its own timed
segment built from assets/1024-movie, then everything is concatenated and the
subtitles are burned in.

Run: python3 build_cut.py <project_root> <out_dir> [--no-sub]
"""
import json, os, subprocess, sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT, OUT = sys.argv[1], sys.argv[2]
ASSETS = os.path.join(ROOT, "assets/1024-movie")
VDIR = os.path.join(ROOT, "docs/video/2026-10_major_update")
TOOLS = os.path.join(VDIR, "tools")
BURN = "--no-sub" not in sys.argv
FPS = 30
W, H = 1920, 1080
RATE = 4.6  # spoken units per second, measured from the previous SOL video

SC = json.load(open(os.path.join(TOOLS, "script.json"), encoding="utf-8"))
CUT = json.load(open(os.path.join(TOOLS, "cut_map.json"), encoding="utf-8"))
TMP = os.path.join(OUT, "work")
os.makedirs(TMP, exist_ok=True)
SEG = os.path.join(TMP, "seg")
os.makedirs(SEG, exist_ok=True)


def dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", p], capture_output=True, text=True)
    return float(r.stdout.strip())


def units(t):
    import re
    return len(re.findall(r"[一-鿿]", t)) + len(re.findall(r"[A-Za-z0-9&]+", t))


def path_of(name):
    """Slides live under the video docs folder, footage under assets/1024-movie."""
    if name.startswith(("slides/", "tools/")) or name.endswith("_overlay.png"):
        return os.path.join(VDIR, name)
    return os.path.join(ASSETS, name)


ZOOM = ("scale=2640:1485:force_original_aspect_ratio=increase,crop=2640:1485,"
        "zoompan=z=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d=1:s={W}x{H}:fps={FPS},setsar=1")


def snap_still(src, dst, t):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1", dst], check=True)


def build_img(src, seconds, dst, zoom=True):
    vf = ZOOM if zoom else f"scale={W}:{H},setsar=1,fps={FPS}"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(FPS), "-i", src,
                    "-t", f"{seconds:.3f}", "-vf", vf, "-pix_fmt", "yuv420p", "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "20", dst], check=True)


def build_img_overlay(base, overlay, seconds, dst):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(FPS), "-i", base,
                    "-loop", "1", "-framerate", str(FPS), "-i", overlay, "-filter_complex",
                    f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[bg];"
                    f"[1:v]scale={W}:{H}[ov];[bg][ov]overlay=0:0,"
                    f"fps={FPS},"
                    f"setsar=1[v]",
                    "-map", "[v]", "-t", f"{seconds:.3f}", "-pix_fmt", "yuv420p", "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "20", dst], check=True)


def build_clip(src, in_pt, seconds, dst, crop=""):
    """Take `seconds` from in_pt; if the clip runs out, freeze the last frame."""
    total = dur(src)
    avail = max(0.0, total - in_pt)
    parts = []
    if avail >= seconds:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{in_pt:.3f}", "-i", src,
                        "-t", f"{seconds:.3f}", "-vf", f"{crop + ',' if crop else ''}scale={W}:{H},setsar=1,fps={FPS}",
                        "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", dst],
                       check=True)
        return
    a = os.path.join(TMP, "a.mp4")
    b = os.path.join(TMP, "b.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{in_pt:.3f}", "-i", src,
                    "-t", f"{avail:.3f}", "-vf", f"{crop + ',' if crop else ''}scale={W}:{H},setsar=1,fps={FPS}",
                    "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", a], check=True)
    still = os.path.join(TMP, "last.png")
    snap_still(src, still, max(0.0, total - 0.08))
    build_img(still, seconds - avail + 0.1, b)
    with open(os.path.join(TMP, "cat.txt"), "w") as f:
        f.write(f"file '{a}'\nfile '{b}'\n")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", os.path.join(TMP, "cat.txt"),
                    "-t", f"{seconds:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", dst], check=True)


def render(name, seconds, dst):
    if name != "T00" and os.path.exists(dst) and os.path.getsize(dst) > 10000:
        return  # resumable: keep segments from an earlier pass
    spec = CUT[name]
    if spec.get("overlay"):
        build_img_overlay(path_of(spec["source"]),
                          os.path.join(VDIR, spec["overlay"] + ".png"), seconds, dst)
        return
    src = path_of(spec["source"])
    if spec["type"] == "image" or src.lower().endswith(".png"):
        a = os.path.join(TMP, "i1.mp4")
        build_img(src, seconds, a)
        nxt = spec.get("then") or spec.get("insert")
        if not nxt:
            os.replace(a, dst)
            return
        at = spec.get("then", {}).get("at")
        if at is None:  # insert: a short clip dropped in mid-way
            at = max(0.6, seconds * 0.55)
        n = nxt.get("seconds", seconds * (1 - at))
        b = os.path.join(TMP, "i2.mp4")
        if nxt["source"].endswith(".png"):
            build_img(path_of(nxt["source"]), n, b)
        else:
            build_clip(path_of(nxt["source"]), nxt.get("in", 0.0), n, b)
        tail = max(0.0, seconds - at - n)
        with open(os.path.join(TMP, "cat.txt"), "w") as f:
            f.write(f"file '{a}'\nfile '{b}'\n")
            if tail > 0.05:
                c = os.path.join(TMP, "i3.mp4")
                build_img(path_of(spec["source"]), tail, c)
                f.write(f"file '{c}'\n")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", os.path.join(TMP, "cat.txt"),
                        "-t", f"{seconds:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-pix_fmt", "yuv420p", dst], check=True)
        # the pieces above are frame-rounded; force the segment back to its slot
        real = dur(dst)
        if abs(real - seconds) > 0.05:
            fixed = os.path.join(TMP, "fixed.mp4")
            if real > seconds:
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", dst, "-t", f"{seconds:.3f}",
                                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", fixed], check=True)
            else:
                pad = os.path.join(TMP, "pad.mp4")
                build_img(path_of(spec["source"]), seconds - real + 0.1, pad)
                with open(os.path.join(TMP, "cat2.txt"), "w") as f:
                    f.write(f"file '{dst}'\nfile '{pad}'\n")
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", os.path.join(TMP, "cat2.txt"),
                                "-t", f"{seconds:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                                "-pix_fmt", "yuv420p", fixed], check=True)
            os.replace(fixed, dst)
        return
    build_clip(src, spec.get("in", 0.0), seconds, dst, spec.get("crop", ""))


lines, t = [], 0.0
silent = 3.5
render("T00", silent, os.path.join(SEG, "s000.mp4"))
lines.append((0.0, silent, None))
t = silent
idx = 1
edl = []
for sc in SC:
    for line, vis in sc["lines"]:
        d = max(1.4, units(line) / RATE) + 0.25
        dst = os.path.join(SEG, f"s{idx:03d}.mp4")
        render(vis, d, dst)
        lines.append((t, t + d, line))
        edl.append({"scene": sc["id"], "line": line, "visual": vis, "start": round(t, 1),
                    "end": round(t + d, 1), "seconds": round(d, 2),
                    "source": CUT[vis]["source"], "in": CUT[vis].get("in")})
        t += d
        idx += 1
    t += sc.get("pause", 0.4)
    if sc.get("pause"):
        # hold the last visual through the pause
        last = os.path.join(SEG, f"s{idx-1:03d}.mp4")
        d = sc["pause"]
        dst = os.path.join(SEG, f"s{idx:03d}.mp4")
        vis = SC[SC.index(sc)]["lines"][-1][1]
        render(vis, d, dst)
        lines.append((t - d, t, None))
        edl.append({"scene": sc["id"], "line": "(hold)", "visual": vis, "start": round(t - d, 1),
                    "end": round(t, 1), "seconds": round(d, 2),
                    "source": CUT[vis]["source"], "in": CUT[vis].get("in")})
        idx += 1

print("total", round(t, 2), "s")
os.makedirs(OUT, exist_ok=True)
with open(os.path.join(TMP, "list.txt"), "w") as f:
    for i in range(1, idx):
        f.write(f"file '{os.path.join(SEG, f's{i:03d}.mp4')}'\n")
json.dump(edl, open(os.path.join(TMP, "edl.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump({"total_seconds": round(t, 2)}, open(os.path.join(OUT, "timing_cut.json"), "w", encoding="utf-8"), indent=1)
print("segments", idx - 1, "-> run post_cut.py next")

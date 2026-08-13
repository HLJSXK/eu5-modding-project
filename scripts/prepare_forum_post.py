#!/usr/bin/env python3
"""Validate the BBCode forum post and split it into per-post chunks.

XenForo (the Paradox forum engine) caps a single post's body length, so a long
write-up has to be posted as an opening post plus replies. This script checks
tag hygiene first, then cuts the source at section boundaries so no post
exceeds the limit and no BBCode tag is ever split across posts.

Usage:
    python scripts/prepare_forum_post.py
    python scripts/prepare_forum_post.py --limit 20000
    python scripts/prepare_forum_post.py --write
"""
import argparse
import re
import sys
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SOURCE = Path("docs/technical/Country_Demand_Solver_Forum_Post.bbcode")
OUT_DIR = Path("docs/technical/forum_post_parts")

# Tags that must appear in matched open/close pairs.
PAIRED = ("B", "I", "U", "SIZE", "COLOR", "CENTER", "LIST", "TABLE", "TR",
          "TD", "TH", "SPOILER", "QUOTE", "CODE", "ICODE", "IMG", "URL", "HR")

SECTION_RE = re.compile(r"\[SIZE=5\]\[B\](\d+)\. (.+?)\[/B\]\[/SIZE\]")


def strip_tags(text: str) -> str:
    return re.sub(r"\[/?[A-Za-z]+(?:=[^\]]*)?\]", "", text)


def validate(text: str) -> bool:
    ok = True
    print("=== tag balance ===")
    for tag in PAIRED:
        opens = len(re.findall(r"\[" + tag + r"(?:[=\]])", text, re.I))
        closes = len(re.findall(r"\[/" + tag + r"\]", text, re.I))
        if not (opens or closes):
            continue
        # [HR][/HR] is written as a pair in this document; other engines allow
        # a bare [HR], so only warn when the two counts disagree.
        mark = "" if opens == closes else "   <-- MISMATCH"
        print(f"  {tag:9s} open {opens:3d}  close {closes:3d}{mark}")
        if opens != closes:
            ok = False

    print()
    print("=== tables ===")
    for i, tbl in enumerate(re.findall(r"\[TABLE\].*?\[/TABLE\]", text, re.S), 1):
        rows = re.findall(r"\[TR\].*?\[/TR\]", tbl, re.S)
        widths = Counter(len(re.findall(r"\[T[DH]\]", r)) for r in rows)
        if len(widths) != 1:
            print(f"  table {i}: RAGGED {dict(widths)}")
            ok = False
    print(f"  {len(re.findall(r'.TABLE.', text)) // 2} tables, all rectangular"
          if ok else "  see above")

    print()
    print("=== stray markdown / LaTeX (CODE blocks excluded) ===")
    outside = re.sub(r"\[CODE\].*?\[/CODE\]", "", text, flags=re.S)
    checks = {
        "markdown heading": len(re.findall(r"(?m)^#{1,6} ", outside)),
        "markdown bold": outside.count("**"),
        "markdown table": len(re.findall(r"(?m)^\|", outside)),
        "markdown image": len(re.findall(r"!\[", outside)),
        "inline math": len(re.findall(r"\$[^$\n]+\$", outside)),
        "display math": outside.count("$$"),
        "latex command": len(re.findall(r"\\[A-Za-z]{2,}", outside)),
    }
    for name, n in checks.items():
        if n:
            print(f"  {name}: {n}   <-- LEAK")
            ok = False
    if all(v == 0 for v in checks.values()):
        print("  none")

    print()
    print("=== CJK (post is English) ===")
    cjk = sorted({c for c in text if "一" <= c <= "鿿"})
    print("  " + ("".join(cjk) + "   <-- LEAK" if cjk else "none"))
    if cjk:
        ok = False

    print()
    print("=== image placeholders to replace before posting ===")
    holders = re.findall(r"\[IMG\](FIGURE_\d+_URL)\[/IMG\]", text)
    for h in holders:
        print("  " + h)
    if not holders:
        print("  none (all images have real URLs)")

    return ok


def split_posts(text: str, limit: int) -> list[tuple[str, str]]:
    """Cut at section headings, packing as many sections per post as fit."""
    marks = [m.start() for m in SECTION_RE.finditer(text)]
    if not marks:
        return [("post 1", text)]

    # Header (title + intro) always leads the opening post.
    bounds = [0] + marks + [len(text)]
    blocks = [text[bounds[i]:bounds[i + 1]] for i in range(len(bounds) - 1)]

    labels = ["header"]
    for m in SECTION_RE.finditer(text):
        labels.append(f"{m.group(1)}. {m.group(2)}")

    posts: list[tuple[str, str]] = []
    cur, cur_labels = "", []
    for block, label in zip(blocks, labels):
        if cur and len(cur) + len(block) > limit:
            posts.append((", ".join(cur_labels), cur))
            cur, cur_labels = block, [label]
        else:
            cur += block
            cur_labels.append(label)
    if cur:
        posts.append((", ".join(cur_labels), cur))
    return posts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=20000,
                    help="max characters per post (default 20000)")
    ap.add_argument("--write", action="store_true",
                    help="write the split parts to disk")
    args = ap.parse_args()

    if not SOURCE.exists():
        print(f"missing source: {SOURCE}", file=sys.stderr)
        return 1
    text = SOURCE.read_text(encoding="utf-8")

    ok = validate(text)

    print()
    print("=== size ===")
    print(f"  with tags     : {len(text):,}")
    print(f"  visible text  : {len(strip_tags(text)):,}")

    posts = split_posts(text, args.limit)
    print()
    print(f"=== split at {args.limit:,} chars/post -> {len(posts)} posts ===")
    for i, (label, body) in enumerate(posts, 1):
        over = "   <-- OVER LIMIT" if len(body) > args.limit else ""
        print(f"  post {i}: {len(body):>6,} chars{over}")
        print(f"          {label}")
        # A tag split across posts would render as literal text.
        for tag in PAIRED:
            o = len(re.findall(r"\[" + tag + r"(?:[=\]])", body, re.I))
            c = len(re.findall(r"\[/" + tag + r"\]", body, re.I))
            if o != c:
                print(f"          UNBALANCED {tag}: {o} open, {c} close")
                ok = False

    if args.write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        for old in OUT_DIR.glob("post_*.bbcode"):
            old.unlink()
        for i, (label, body) in enumerate(posts, 1):
            path = OUT_DIR / f"post_{i:02d}.bbcode"
            note = (f"[SIZE=2][I]Part {i} of {len(posts)}. "
                    f"Sections: {label}[/I][/SIZE]\n\n") if len(posts) > 1 else ""
            path.write_text(note + body.strip() + "\n", encoding="utf-8")
            print(f"  wrote {path}")

    print()
    print("RESULT:", "clean" if ok else "problems found")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

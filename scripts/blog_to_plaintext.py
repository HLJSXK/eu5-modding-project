#!/usr/bin/env python3
"""Render the Chinese blog Markdown as plain text for hand editing.

Strips Markdown syntax and rewrites LaTeX into plain notation so the result can
be edited in any text editor without fighting escapes. Tables become aligned
columns (CJK width aware), display math becomes indented blocks, and figures
become bracketed markers.

The output is meant for editing prose, not for round-tripping back into
Markdown automatically -- the formatted versions are updated by hand against
the edited text.

Usage:
    python scripts/blog_to_plaintext.py
    python scripts/blog_to_plaintext.py --width 84
"""
import argparse
import re
import sys
import unicodedata
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SOURCE = Path("docs/technical/Country_Demand_Solver_Blog.md")
TARGET = Path("docs/technical/Country_Demand_Solver_PlainText.txt")

# LaTeX -> plain text, applied longest-first so \mathbf{t} beats \mathbf.
LATEX = [
    (r"\dfrac{\sum_s I_s(\ell)}{\sum_s B_s(\ell)}", "(各阶层 I_s(l) 之和) / (各阶层 B_s(l) 之和)"),
    # Norm bars: \| is an escaped pipe in Markdown tables, so handle the whole
    # notation before anything else touches it.
    (r"\|\cdot\|_2", "||.||_2"),
    (r"\|\cdot\|_1", "||.||_1"),
    (r"\|\cdot\|_\infty", "||.||_无穷"),
    (r"\|\cdot\|", "||.||"),
    (r"\operatorname{cone}(M_{\text{任意划分}})", "cone(任意划分)"),
    (r"\operatorname{cone}(M_{\text{每地点一列}})", "cone(每地点一列)"),
    (r"\operatorname{cone}(M)", "cone(M)"),
    (r"\mathcal{S}", "S"),
    (r"\mathbf{x}", "x"),
    (r"\mathbf{t}", "t"),
    (r"\mathbf{f}", "f"),
    (r"\mathbf{0}", "0"),
    (r"\mathbf{1}", "1"),
    (r"\mathbb{R}", "R"),
    (r"\text{贵族}", "贵族"),
    (r"\text{教士}", "教士"),
    (r"\text{市民}", "市民"),
    (r"\text{下层}", "下层"),
    (r"\text{贵}", "贵"),
    (r"\text{教}", "教"),
    (r"\text{市}", "市"),
    (r"\text{下}", "下"),
    (r"\text{raw}", "raw"),
    (r"\text{share}", "share"),
    (r"\text{all-locations}", "all-locations"),
    (r"\text{s.t.}", "s.t."),
    (r"\text{minimax\_ratio}", "minimax_ratio"),
    (r"\ell", "l"),
    (r"\ldots", "..."),
    (r"\cdots", "..."),
    (r"\geq", ">="),
    (r"\leq", "<="),
    (r"\neq", "!="),
    (r"\approx", "≈"),
    (r"\times", "x"),
    (r"\cdot", "*"),
    (r"\infty", "无穷"),
    (r"\kappa", "kappa"),
    (r"\lambda", "lambda"),
    (r"\delta", "delta"),
    (r"\alpha", "alpha"),
    (r"\Delta", "Delta"),
    (r"\ast", "*"),
    (r"\subseteq", " 包含于 "),
    (r"\sum", "SUM"),
    (r"\max", "max"),
    (r"\min", "min"),
    (r"\det", "det"),
    (r"\bigl", ""), (r"\bigr", ""),
    (r"\Bigl", ""), (r"\Bigr", ""),
    (r"\left", ""), (r"\right", ""),
    (r"\qquad", "    "),
    (r"\quad", "  "),
    (r"\;", " "),
    (r"\,", " "),
    # Row separator inside a matrix; handled before the generic escape strip.
    (r"\\", " ; "),
    # \top must win over the bare-command strip, and \in is last so it does not
    # eat the "in" inside \infty, \int etc.
    (r"^\top", "^T"),
    (r"\top", "^T"),
    (r"\ge", ">="),
    (r"\le", "<="),
    (r"\in", " 属于 "),
]


def delatex(s: str) -> str:
    # Column vectors read better inline than as a stripped begin/end pair.
    def _vec(m: re.Match) -> str:
        parts = [p.strip() for p in re.split(r"\\\\", m.group(1)) if p.strip()]
        return "(" + ", ".join(parts) + ")^T"

    s = re.sub(r"\\begin\{pmatrix\}(.*?)\\end\{pmatrix\}", _vec, s, flags=re.S)
    s = re.sub(r"\\begin\{[a-z]+\*?\}|\\end\{[a-z]+\*?\}", "", s)

    for old, new in LATEX:
        s = s.replace(old, new)
    # frac{a}{b} -> (a)/(b)
    s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", s)
    s = re.sub(r"\\dfrac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", s)
    # Summation ranges read better as "SUM over <range> of" than as a subscript.
    s = re.sub(r"SUM_\{([^{}]*)\}\^\{([^{}]*)\}", r"SUM(\1 到 \2)", s)
    s = re.sub(r"SUM_\{([^{}]*)\}", r"SUM(\1)", s)
    s = re.sub(r"SUM_(\S+)", r"SUM(\1)", s)

    # Subscripts and superscripts: keep the plain characters.
    s = re.sub(r"_\{([^{}]*)\}", r"_\1", s)
    s = re.sub(r"\^\{([^{}]*)\}", r"^\1", s)
    # Any remaining \cmd{...} keeps its content; bare \cmd is dropped.
    s = re.sub(r"\\[A-Za-z]+\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\[A-Za-z]+", "", s)
    s = s.replace("\\", "")
    # The padded CJK operators above leave runs of spaces; tighten them.
    for word in ("属于", "包含于"):
        s = re.sub(r" +" + word + r" +", " " + word + " ", s)
    s = re.sub(r" {3,}", "  ", s)
    return s


def w(s: str) -> int:
    """Display width, counting CJK and fullwidth punctuation as 2 columns."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s: str, target: int) -> str:
    return s + " " * max(0, target - w(s))


def inline(s: str) -> str:
    """Strip inline Markdown and render inline math.

    Math is converted first and then parked in placeholders, because rendered
    output legitimately contains '*' (multiplication) and '^*' (the incumbent
    marker) which the emphasis rules below would otherwise eat.
    """
    stash: list[str] = []

    def _park(m: re.Match) -> str:
        stash.append(delatex(m.group(1)))
        return f"\x00M{len(stash) - 1}\x00"

    s = re.sub(r"\$([^$]+)\$", _park, s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    for i, frag in enumerate(stash):
        s = s.replace(f"\x00M{i}\x00", frag)
    return s


def render_table(rows: list[str]) -> list[str]:
    # An escaped pipe inside a cell is content, not a column separator. The
    # only use here is norm notation, so normalise it to its plain form up
    # front -- by the time delatex() runs the backslash is already gone.
    # Shield escaped pipes first, split on the real separators, then restore.
    # Restoring to a literal '|' before splitting would re-introduce false
    # separators, so the placeholder survives until after the split.
    SHIELD = "\x00PIPE\x00"
    rows = [r.replace(r"\|", SHIELD) for r in rows]
    grid = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    grid = [[c.replace(SHIELD + r"\cdot" + SHIELD, "||.||").replace(SHIELD, "|")
             for c in row] for row in grid]
    grid = [row for row in grid
            if not all(re.fullmatch(r":?-{2,}:?", c) for c in row if c)]
    grid = [[inline(c) for c in row] for row in grid]
    if not grid:
        return []
    ncol = max(len(r) for r in grid)
    grid = [r + [""] * (ncol - len(r)) for r in grid]
    widths = [max(w(r[i]) for r in grid) for i in range(ncol)]

    # A table whose aligned form would run far past a readable line length is
    # emitted as one labelled block per row instead of as columns.
    if sum(widths) + 5 * (ncol - 1) > 110 and ncol >= 2:
        head, *body = grid
        out = []
        for row in body:
            out.append("    " + row[0])
            for label, cell in zip(head[1:], row[1:]):
                if cell:
                    out.append(f"        {label}: {cell}")
            out.append("")
        return out[:-1] if out else out

    out = []
    for i, row in enumerate(grid):
        out.append("    " + "  |  ".join(pad(c, widths[j]) for j, c in enumerate(row)).rstrip())
        if i == 0:
            out.append("    " + "-+-".join("-" * (wd + 2) for wd in widths)[1:-1])
    return out


def convert(md: str, width: int) -> str:
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    in_fence = False

    while i < len(lines):
        line = lines[i]

        if line.startswith("```"):
            in_fence = not in_fence
            out.append("" if in_fence else "")
            i += 1
            continue
        if in_fence:
            out.append("    " + line)
            i += 1
            continue

        # Display math block
        if line.strip() == "$$":
            i += 1
            buf = []
            while i < len(lines) and lines[i].strip() != "$$":
                buf.append(lines[i])
                i += 1
            i += 1
            out.append("")
            for b in buf:
                rendered = delatex(b).strip()
                if rendered:
                    out.append("        " + rendered)
            out.append("")
            continue

        # Table
        if line.lstrip().startswith("|"):
            buf = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                buf.append(lines[i])
                i += 1
            out.append("")
            out.extend(render_table(buf))
            out.append("")
            continue

        # Figure
        m = re.match(r"!\[(.*?)\]\((.*?)\)", line.strip())
        if m:
            out.append(f"    [ 图片: {m.group(2)} ]")
            i += 1
            continue

        # Headings
        if line.startswith("# "):
            t = inline(line[2:].strip())
            out.extend(["=" * width, t, "=" * width])
            i += 1
            continue
        if line.startswith("## "):
            t = inline(line[3:].strip())
            out.extend(["", "=" * width, t, "=" * width])
            i += 1
            continue
        if line.startswith("### "):
            t = inline(line[4:].strip())
            out.extend(["", t, "-" * min(width, w(t))])
            i += 1
            continue

        if line.strip() == "---":
            out.append("")
            i += 1
            continue

        # Lists
        m = re.match(r"^(\s*)[-*] (.*)$", line)
        if m:
            out.append(f"{m.group(1)}  - {inline(m.group(2))}")
            i += 1
            continue
        m = re.match(r"^(\s*)(\d+)\. (.*)$", line)
        if m:
            out.append(f"{m.group(1)}  {m.group(2)}. {inline(m.group(3))}")
            i += 1
            continue

        if line.strip().startswith(">"):
            out.append("    | " + inline(line.strip().lstrip("> ")))
            i += 1
            continue

        out.append(inline(line))
        i += 1

    text = "\n".join(out)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--width", type=int, default=78, help="rule width")
    args = ap.parse_args()

    if not SOURCE.exists():
        print(f"missing {SOURCE}", file=sys.stderr)
        return 1

    text = convert(SOURCE.read_text(encoding="utf-8"), args.width)
    TARGET.write_text(text, encoding="utf-8")

    leftover = re.findall(r"\$|\\[A-Za-z]{2,}|\*\*|^\|", text, re.M)
    print(f"[plaintext] wrote {TARGET}")
    print(f"[plaintext] {len(text):,} chars, {text.count(chr(10)) + 1} lines")
    print(f"[plaintext] leftover markup: {len(leftover)}"
          + (f" -> {sorted(set(leftover))[:10]}" if leftover else " (clean)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Print the full definition of a GUI template/type by name from the game + SOL files.

usage: guidef.py NAME [NAME ...]
"""
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOTS = [
    Path(r"C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V\game"),
    Path(__file__).resolve().parents[2] / "src" / "stable" / "in_game" / "gui",
]
DEF_RE = re.compile(r"^\s*(template|type)\s+([A-Za-z0-9_]+)\b")


def blocks():
    for root in ROOTS:
        for p in root.rglob("*.gui"):
            if "\\mod\\" in str(p):
                continue
            lines = p.read_text(encoding="utf-8-sig", errors="replace").splitlines()
            for i, line in enumerate(lines):
                m = DEF_RE.match(line)
                if m:
                    yield m.group(2), p, i, lines


def extract(lines, start):
    depth, out, opened = 0, [], False
    for line in lines[start:]:
        code = line.split("#", 1)[0]
        out.append(line)
        depth += code.count("{") - code.count("}")
        if "{" in code:
            opened = True
        if opened and depth <= 0:
            break
    return out


def main():
    want = set(sys.argv[1:])
    for name, p, i, lines in blocks():
        if name in want:
            print(f"===== {name}  ({p}:{i + 1})")
            print("\n".join(extract(lines, i)))


if __name__ == "__main__":
    main()

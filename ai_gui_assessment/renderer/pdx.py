"""Minimal Paradox script / Jomini GUI parser.

Produces a list of Node(key, op, value) where value is either a str or a list of Node.
File-local @constants and @[expr] arithmetic are substituted at parse time.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

TOKEN_RE = re.compile(r'''
    (?P<ws>\s+)
  | (?P<comment>\#[^\n]*)
  | (?P<str>"(?:[^"\\]|\\.)*")
  | (?P<op>>=|<=|!=|==|\?=|=|<|>)
  | (?P<lb>\{)
  | (?P<rb>\})
  | (?P<atexpr>@\[[^\]]*\])
  | (?P<word>\[[^\]\n]*\]|[^\s{}=<>!"\#]+(?:\[[^\]]*\])?[^\s{}=<>!"\#]*)
''', re.X)


@dataclass
class Node:
    key: str
    op: str
    value: "str | list[Node]"
    src: str = ""
    line: int = 0

    def is_block(self) -> bool:
        return isinstance(self.value, list)

    def __repr__(self):
        v = self.value if isinstance(self.value, str) else f"[{len(self.value)}]"
        return f"Node({self.key}{self.op}{v})"


def tokenize(text: str, src: str = ""):
    pos, line = 0, 1
    n = len(text)
    while pos < n:
        m = TOKEN_RE.match(text, pos)
        if not m:
            # unknown char: skip
            pos += 1
            continue
        kind = m.lastgroup
        tok = m.group(kind)
        if kind == "str":
            for escape in re.finditer(r"\\(.)", tok, re.DOTALL):
                if escape.group(1) not in ('"', "\\"):
                    escape_line = line + tok[:escape.start()].count("\n")
                    raise ValueError(
                        f"{src or '<script>'}:{escape_line}: invalid quoted-string escape "
                        f"{escape.group(0)!r}; only quote and backslash may be escaped"
                    )
        if kind not in ("ws", "comment"):
            yield kind, tok, line
        line += tok.count("\n")
        pos = m.end()


def _eval_const_expr(expr: str, consts: dict) -> str:
    def rep(m):
        name = m.group(0)
        if name in consts:
            return str(consts[name])
        return name
    e = re.sub(r"[A-Za-z_][A-Za-z0-9_]*", rep, expr)
    try:
        v = eval(e, {"__builtins__": {}}, {})
    except Exception:
        return expr
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v)


def parse(text: str, src: str = "", consts: dict | None = None) -> list[Node]:
    consts = consts if consts is not None else {}
    toks = list(tokenize(text, src))
    i = 0

    def value_of(tok_kind, tok):
        if tok_kind == "str":
            return tok[1:-1]
        if tok_kind == "atexpr":
            return _eval_const_expr(tok[2:-1], consts)
        if tok_kind == "word" and tok.startswith("@") and not tok.endswith("!"):
            name = tok[1:]
            if name in consts:
                return str(consts[name])
        return tok

    def parse_block() -> list[Node]:
        nonlocal i
        out: list[Node] = []
        while i < len(toks):
            kind, tok, line = toks[i]
            if kind == "rb":
                i += 1
                return out
            if kind == "lb":
                # anonymous block (rare) - parse and attach with empty key
                i += 1
                out.append(Node("", "", parse_block(), src, line))
                continue
            key = value_of(kind, tok)
            raw_key = tok
            i += 1
            # block "name" { ... } / blockoverride "name" { ... }
            if raw_key in ("block", "blockoverride") and i < len(toks) and toks[i][0] == "str":
                name = toks[i][1][1:-1]
                i += 1
                if i < len(toks) and toks[i][0] == "lb":
                    i += 1
                    body = parse_block()
                else:
                    body = []
                out.append(Node(f"{raw_key}:{name}", "=", body, src, line))
                continue
            # types Name { ... }
            if raw_key == "types" and i < len(toks) and toks[i][0] == "word":
                i += 1
                if toks[i][0] == "lb":
                    i += 1
                    out.append(Node("types", "=", parse_block(), src, line))
                continue
            # type a = b { ... }
            if raw_key == "type" and i + 2 < len(toks) and toks[i + 1][0] == "op":
                name = toks[i][1]
                base = toks[i + 2][1]
                i += 3
                body = []
                if i < len(toks) and toks[i][0] == "lb":
                    i += 1
                    body = parse_block()
                out.append(Node(f"type:{name}", "=", [Node("__base__", "=", base)] + body, src, line))
                continue
            # template name { ... }
            if raw_key in ("template", "local_template") and i < len(toks) and toks[i][0] == "word":
                name = toks[i][1]
                i += 1
                if i < len(toks) and toks[i][0] == "lb":
                    i += 1
                    out.append(Node(f"template:{name}", "=", parse_block(), src, line))
                continue
            if i < len(toks) and toks[i][0] == "op":
                op = toks[i][1]
                i += 1
                if i < len(toks) and toks[i][0] == "lb":
                    i += 1
                    val = parse_block()
                    node = Node(key, op, val, src, line)
                else:
                    vk, vt, _ = toks[i]
                    i += 1
                    val = value_of(vk, vt)
                    node = Node(key, op, val, src, line)
                if raw_key.startswith("@") and isinstance(val, str):
                    consts[raw_key[1:]] = val
                    continue
                out.append(node)
            elif i < len(toks) and toks[i][0] == "lb":
                i += 1
                out.append(Node(key, "=", parse_block(), src, line))
            else:
                # bare token inside a list, e.g. { 10 20 }
                out.append(Node(key, "", "", src, line))
        return out

    return parse_block()


def parse_file(path: Path, shared_consts: dict | None = None) -> list[Node]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    consts = dict(shared_consts or {})
    return parse(text, str(path), consts)


def scalars(node: Node) -> list[str]:
    """For list values like { 10 20 } return ['10','20']."""
    if isinstance(node.value, str):
        return [node.value]
    return [n.key for n in node.value]

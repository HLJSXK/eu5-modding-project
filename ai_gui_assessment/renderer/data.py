"""Localization, text formats, data-binding expression evaluation with mock data."""
from __future__ import annotations

import re
from pathlib import Path

from gui import GAME, MOD
from pdx import parse

LANG = "simp_chinese"


# ------------------------------------------------------------------ localization
class Loc:
    LINE_RE = re.compile(r'^\s*([A-Za-z0-9_.\-]+):\d*\s*"(.*)"\s*(#.*)?$')

    def __init__(self):
        self.d: dict[str, str] = {}
        roots = [GAME / s / "localization" / LANG for s in ("loading_screen", "main_menu", "in_game")]
        roots.append(MOD / "main_menu" / "localization" / LANG)
        for r in roots:
            if not r.exists():
                continue
            for p in sorted(r.rglob("*.yml")):
                for line in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                    m = self.LINE_RE.match(line)
                    if m:
                        v = m.group(2)
                        # strip trailing quote issues
                        self.d[m.group(1)] = v.replace('\\"', '"').replace("\\n", "\n")

    def get(self, k):
        return self.d.get(k)


# ------------------------------------------------------------------ text formats
class Formats:
    def __init__(self):
        text = (GAME / "loading_screen/gui/textformatting.gui").read_text(encoding="utf-8-sig")
        self.raw: dict[str, str] = {}
        for m in re.finditer(r'name\s*=\s*"?([A-Za-z0-9_]+)"?\s*format\s*=\s*"([^"]*)"', text):
            self.raw.setdefault(m.group(1), m.group(2))
        # color-blind overrides appear first in the file; prefer the normal block definitions
        for m in re.finditer(r'name\s*=\s*"?(color_green|color_red)"?\s*format\s*=\s*"([^"]*)"', text):
            self.raw[m.group(1)] = m.group(2)

    def resolve(self, name: str, depth=0) -> dict:
        st: dict = {}
        fmt = self.raw.get(name)
        if fmt is None or depth > 10:
            return st
        for part in fmt.split(";"):
            part = part.strip()
            if not part:
                continue
            low = part.lower()
            if low.startswith("color:"):
                nums = [float(x) for x in re.findall(r"[-\d.]+", part)]
                st["color"] = tuple(nums[:3])
            elif low.startswith("glow_color:"):
                nums = [float(x) for x in re.findall(r"[-\d.]+", part)]
                st["glow_color"] = tuple(nums[:4])
            elif low.startswith("glow_offset:"):
                st["glow_offset"] = tuple(float(x) for x in re.findall(r"[-\d.]+", part))
            elif low.startswith("font:"):
                st["font"] = part.split(":", 1)[1]
            elif low.startswith("size:"):
                st["size"] = float(part.split(":", 1)[1])
            elif low in ("bold", "italic", "semibold", "medium", "underline", "game_link"):
                st[low] = True
                if low in ("medium",):  # 'medium' is also a format name
                    st.update(self.resolve("medium", depth + 1))
            else:
                st.update(self.resolve(part, depth + 1))
        return st


# ------------------------------------------------------------------ texticons
class TextIcons:
    def __init__(self):
        self.d: dict[str, dict] = {}
        txt = (GAME / "main_menu/gui/shared/font_icons.gui").read_text(encoding="utf-8-sig")
        consts: dict = {}
        nodes = parse(txt, "font_icons", consts)
        for n in nodes:
            if n.key == "texticon" and n.is_block():
                icon = None
                info = {}
                for c in n.value:
                    if c.key == "icon":
                        icon = c.value
                    elif c.key == "iconsize" and c.is_block():
                        for cc in c.value:
                            if cc.is_block():
                                info[cc.key] = [float(x.key) for x in cc.value]
                            else:
                                info[cc.key] = cc.value
                if icon:
                    self.d[icon] = info

    def get(self, name):
        if name in self.d:
            return self.d[name]
        # goods icons are registered by the engine from the goods database
        tex = f"gfx/interface/icons/trade_goods/icon_goods_{name}.dds"
        return {"texture": tex, "size": [20, 20], "offset": [0, 4], "__goods__": True}


# ------------------------------------------------------------------ expressions
class Unknown:
    def __init__(self, path):
        self.path = path

    def __repr__(self):
        return f"?{self.path}"

    def __bool__(self):
        return False


_TOK = re.compile(r"\s*(?:('(?:[^'\\]|\\.)*')|([A-Za-z_][A-Za-z0-9_:]*)|(\d+(?:\.\d+)?)|(.))")


def _tokens(s):
    for m in _TOK.finditer(s):
        if m.group(1) is not None:
            yield ("str", m.group(1)[1:-1])
        elif m.group(2) is not None:
            yield ("id", m.group(2))
        elif m.group(3) is not None:
            yield ("num", m.group(3))
        elif m.group(4) is not None and m.group(4).strip():
            yield ("p", m.group(4))


def parse_expr(s: str):
    toks = list(_tokens(s))
    pos = 0

    def peek():
        return toks[pos] if pos < len(toks) else (None, None)

    def take():
        nonlocal pos
        t = toks[pos]
        pos += 1
        return t

    def expr():
        t = peek()
        if t[0] == "str":
            take()
            return ("lit", t[1])
        if t[0] == "num":
            take()
            return ("lit", t[1])
        parts = []
        while True:
            k, v = take()
            if k != "id":
                return ("lit", v)
            args = None
            if peek() == ("p", "("):
                take()
                args = []
                if peek() != ("p", ")"):
                    args.append(expr())
                    while peek() == ("p", ","):
                        take()
                        args.append(expr())
                if peek() == ("p", ")"):
                    take()
            parts.append((v, args))
            if peek() == ("p", "."):
                take()
                continue
            break
        return ("chain", parts)

    try:
        return expr()
    except IndexError:
        return ("lit", s)


def literal_value(s: str):
    m = re.match(r"^\((CFixedPoint|float|int32|bool|int64|double|CString|ECountryTag)\)(.*)$", s)
    if m:
        t, v = m.groups()
        if t == "bool":
            return v.strip() == "yes"
        try:
            return float(v)
        except ValueError:
            return v
    return s


def _num(v):
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return 0.0
    return 0.0


class Evaluator:
    def __init__(self, mocks: list, loc: Loc, log: list):
        """mocks: list of (regex, value_or_callable)."""
        self.mocks = [(re.compile(p), v) for p, v in mocks]
        self.loc = loc
        self.log = log
        self.item_stack: list[dict] = []
        self.vars: dict = {}

    # canonical form for lookup
    def canon(self, node) -> str:
        if node[0] == "lit":
            return f"'{node[1]}'"
        out = []
        for name, args in node[1]:
            if args is None:
                out.append(name)
            else:
                out.append(f"{name}(" + ",".join(self.canon_arg(a) for a in args) + ")")
        return ".".join(out)

    def canon_arg(self, a):
        if a[0] == "chain" and self.item_stack:
            c = self.canon(a)
            for item in reversed(self.item_stack):
                t = item.get("__type__")
                if t and c.startswith(t + ".") and c[len(t) + 1:] in item:
                    v = item[c[len(t) + 1:]]
                    if isinstance(v, (str, int, float)):
                        return f"'{v}'"
                if c in item and isinstance(item[c], (str, int, float)):
                    return f"'{item[c]}'"
        return self.canon(a)

    def lookup(self, path: str):
        # normalisations
        p = path.replace("LocationView.GetLocation.", "Location.").replace("SituationView.GetActiveSituation.", "Situation.")
        for item in reversed(self.item_stack):
            t = item.get("__type__")
            if t and p.startswith(t + "."):
                key = p[len(t) + 1:]
                if key in item:
                    return item[key]
            if p in item:
                return item[p]
        for rx, v in self.mocks:
            m = rx.fullmatch(p)
            if m:
                return v(m) if callable(v) else v
        return Unknown(p)

    def eval(self, node):
        if node[0] == "lit":
            return literal_value(node[1])
        parts = node[1]
        if len(parts) == 1:
            name, args = parts[0]
            if args is not None:
                fn = getattr(self, "fn_" + name, None)
                if fn is None:
                    fn = self.generic_fn(name)
                if fn is not None:
                    vals = [self.eval(a) for a in args]
                    return fn(*vals)
        path = self.canon(node)
        v = self.lookup(path)
        if isinstance(v, Unknown):
            self.log.append(path)
        return v

    def eval_str(self, s: str):
        s = s.strip()
        if s in ("yes", "no"):
            return s == "yes"
        if s.startswith("[") and s.endswith("]") and s.count("[") == 1:
            return self.eval(parse_expr(s[1:-1]))
        return s

    def truthy(self, s, default=False):
        if s is None:
            return default
        v = self.eval_str(s) if isinstance(s, str) else s
        if isinstance(v, Unknown):
            return default
        return bool(v)

    # ---------------- builtin functions
    def generic_fn(self, name):
        m = re.match(r"^(GreaterThan|LessThan|GreaterThanOrEqualTo|LessThanOrEqualTo|EqualTo|NotEqualTo|Add|Subtract|Multiply|Divide|Max|Min|BetweenInclusiveOfMax|Between)_([A-Za-z0-9]+)$", name)
        if m:
            op = m.group(1)
            if m.group(2) == "string":
                return {"EqualTo": lambda a, b: str(a) == str(b), "NotEqualTo": lambda a, b: str(a) != str(b)}.get(op)
            ops = {
                "GreaterThan": lambda a, b: _num(a) > _num(b),
                "LessThan": lambda a, b: _num(a) < _num(b),
                "GreaterThanOrEqualTo": lambda a, b: _num(a) >= _num(b),
                "LessThanOrEqualTo": lambda a, b: _num(a) <= _num(b),
                "EqualTo": lambda a, b: _num(a) == _num(b),
                "NotEqualTo": lambda a, b: _num(a) != _num(b),
                "Add": lambda a, b: _num(a) + _num(b),
                "Subtract": lambda a, b: _num(a) - _num(b),
                "Multiply": lambda a, b: _num(a) * _num(b),
                "Divide": lambda a, b: _num(a) / _num(b) if _num(b) else 0.0,
                "Max": lambda a, b: max(_num(a), _num(b)),
                "Min": lambda a, b: min(_num(a), _num(b)),
                "BetweenInclusiveOfMax": lambda v, lo, hi: _num(lo) < _num(v) <= _num(hi),
                "Between": lambda v, lo, hi: _num(lo) < _num(v) < _num(hi),
            }
            return ops[op]
        m = re.match(r"^(And|Or)(\d*)$", name)
        if m:
            return (lambda *a: all(bool(x) for x in a)) if m.group(1) == "And" else (lambda *a: any(bool(x) for x in a))
        return None

    def fn_Not(self, a):
        if isinstance(a, Unknown):
            return a
        return not bool(a)

    def fn_FixedPointToFloat(self, a):
        return _num(a)

    def fn_IntToFloat(self, a):
        return _num(a)

    def fn_Select_CString(self, c, a, b):
        return a if c else b

    def fn_SelectLocalization(self, c, a, b):
        return self.loc.get(a if c else b) or (a if c else b)

    def fn_Localize(self, k):
        return self.loc.get(str(k)) or str(k)

    def fn_Concatenate(self, *a):
        return "".join(str(x) for x in a)

    def fn_IsDataModelEmpty(self, a):
        return not a if isinstance(a, list) else True

    def fn_DataModelHasItems(self, a):
        return bool(a) if isinstance(a, list) else False

    def fn_GetDataModelSize(self, a):
        return float(len(a)) if isinstance(a, list) else 0.0

    def fn_StringIsEmpty(self, a):
        return not a or isinstance(a, Unknown)

    def fn_ObjectsEqual(self, a, b):
        return (not isinstance(a, Unknown)) and a == b

    def fn_V2SizeHeight(self, base, n, per):
        return ("vec", -1.0, _num(base) + _num(n) * _num(per))

    def fn_GetConceptTexture(self, name):
        return CONCEPT_TEXTURES.get(str(name), Unknown(f"concept:{name}"))

    def fn_HasPopBreakdownIntelOn(self, a):
        return True

    def fn_HasMigrationIntelOn(self, a):
        return True

    def fn_GetVariableFromGlobalVariableMap(self, name, key):
        return self.lookup(f"GVM:{name}")


# ------------------------------------------------------------------ concept textures
def load_concept_textures():
    out = {}
    for p in (GAME / "in_game" / "common" / "game_concepts").glob("*.txt"):
        nodes = parse(p.read_text(encoding="utf-8-sig", errors="replace"), str(p), {})
        for n in nodes:
            if n.is_block():
                for c in n.value:
                    if c.key == "texture" and isinstance(c.value, str):
                        out[n.key] = c.value
    return out


CONCEPT_TEXTURES = load_concept_textures()


# ------------------------------------------------------------------ number formatting
def format_number(v, spec: str):
    """Best-effort implementation of the |format suffix (semantics inferred, see 02 doc)."""
    x = _num(v)
    digits = re.findall(r"\d", spec)
    dec = int(digits[0]) if digits else None
    pct = "%" in spec
    # '+' alone does not print a sign (vanilla writes "+[X|+0]"); '+=' / '=+' does
    sign = "+=" in spec or "=+" in spec
    color = None
    if "=" in spec:
        neg = "-=" in spec
        if x > 0:
            color = "R" if neg else "G"
        elif x < 0:
            color = "G" if neg else "R"
    if pct:
        x *= 100
    if dec is None:
        dec = 0 if not pct else 0
        if not digits and not pct and abs(x - round(x)) > 1e-9:
            dec = 2
    s = f"{abs(x):,.{dec}f}" if "<" not in spec else f"{abs(x):.{dec}f}"
    if "W" not in spec:
        s = s.replace(",", "")
    if x < 0 and round(abs(x), dec) != 0:
        s = "-" + s
    elif sign and x > 0:
        s = "+" + s
    if pct:
        s += "%"
    letters = [c for c in spec if c.isalpha() and c not in "W"]
    if letters and color is None:
        color = letters[0]
    if color:
        s = f"#{color} {s}#!"
    return s

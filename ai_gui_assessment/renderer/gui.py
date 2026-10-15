"""Load the GUI database (types/templates) and expand an element tree.

Expansion rules implemented (see 01_engine_model.md):
  * `type a = b { ... }` inherits b; body appended after base body.
  * `using = tpl` splices a template body in place.
  * `block "x" { default }` is replaced by the active `blockoverride "x"`.
  * Blockoverrides propagate into nested type instances; an instance's own blockoverride beats inherited ones.
  * Override content is expanded in the context where it is spliced, minus itself.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from pdx import Node, parse, tokenize, scalars  # noqa: F401

GAME = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V\game")
REPO = Path(__file__).resolve().parents[2]
MOD = REPO / "src" / "stable"

# element-level keys that contain property sub-blocks rather than child elements
PROP_BLOCKS = {
    "background", "modify_texture", "glow", "state", "tooltipwidget", "action_tooltip",
    "scripted_action_tooltip", "item", "contextmenu_widget", "textureinfo", "size", "position",
    "margin", "minimumsize", "maximumsize", "spriteborder", "color", "tintcolor", "frame_grid",
    "framesize", "slider", "buttonText", "viewportwidget", "scrollwidget_props", "tooltipmeta",
    "bezier", "start_sound", "soundeffect", "fonttintcolor", "uv_scale", "scale",
    "parameter", "on_finish", "glow_color", "dragdropargs", "tagtooltip", "drop_shadow",
    "left_click_and_hold_action", "right_click_and_hold_action", "spriteborder_bottom",
    "datamodel_reuse_widgets", "button_ignore", "mask", "fontcolor", "mirror",
    "progresstexture", "noprogresstexture", "lowpriotextcontext",
}
CHILD_WRAPPERS = {"scrollbar_vertical", "scrollbar_horizontal", "scrollwidget", "viewportwidget",
                  "tooltipwidget", "contextmenu_widget", "item", "buttonText"}


def _relpath(p: Path, root: Path) -> str:
    return str(p.relative_to(root)).replace("\\", "/").lower()


def collect_files() -> list[Path]:
    """Game GUI files with SOL (stable) files replacing the same relative path."""
    files: dict[str, Path] = {}
    for stage in ("loading_screen", "main_menu", "in_game"):
        for p in sorted((GAME / stage / "gui").rglob("*.gui")):
            files[f"{stage}/" + _relpath(p, GAME / stage / "gui")] = p
        mod_gui = MOD / stage / "gui"
        if mod_gui.exists():
            for p in sorted(mod_gui.rglob("*.gui")):
                files[f"{stage}/" + _relpath(p, mod_gui)] = p
    return list(files.values())


class GuiDB:
    def __init__(self, files: list[Path] | None = None):
        self.types: dict[str, list[Node]] = {}
        self.type_base: dict[str, str] = {}
        self.templates: dict[str, list[Node]] = {}
        self.roots: dict[str, list[Node]] = {}
        files = files or collect_files()
        # pass 1: global @constants
        consts: dict[str, str] = {}
        texts = {}
        for p in files:
            t = p.read_text(encoding="utf-8-sig", errors="replace")
            texts[p] = t
            for kind, tok, _ in tokenize(t):
                pass
        for p in files:
            local: dict[str, str] = {}
            parse(texts[p], str(p), local)
            for k, v in local.items():
                consts.setdefault(k, v)
        self.consts = consts
        # pass 2: real parse with global fallback + file-local constants
        for p in files:
            c = dict(consts)
            nodes = parse(texts[p], str(p), c)
            self.roots[str(p)] = nodes
            self._register(nodes)

    def _register(self, nodes: list[Node]):
        for n in nodes:
            if n.key == "types":
                self._register(n.value)
            elif n.key.startswith("type:"):
                name = n.key[5:]
                base = n.value[0].value
                self.types[name] = n.value[1:]
                self.type_base[name] = base
            elif n.key.startswith("template:"):
                self.templates[n.key[9:]] = n.value

    def type_chain(self, name: str) -> list[str]:
        chain = []
        seen = set()
        while name in self.types and name not in seen:
            seen.add(name)
            chain.append(name)
            base = self.type_base[name]
            if base == name:
                break
            name = base
        return chain  # most derived first


@dataclass
class Element:
    kind: str                      # primitive kind (widget/hbox/vbox/icon/text_single/...)
    typename: str                  # outermost type name as written
    props: dict = field(default_factory=dict)
    children: list = field(default_factory=list)
    backgrounds: list = field(default_factory=list)   # list[dict]
    modifies: list = field(default_factory=list)       # modify_texture on the element itself
    glows: list = field(default_factory=list)
    states: list = field(default_factory=list)
    tooltipwidget: "Element | None" = None
    item: "Element | None" = None
    slices: list = field(default_factory=list)
    src: str = ""
    line: int = 0
    # layout results
    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0

    def get(self, k, d=None):
        return self.props.get(k, d)


PRIMITIVE_ALIAS = {
    "uberwidget": "widget", "uberhbox": "hbox", "ubervbox": "vbox", "ubericon": "icon",
    "uberbutton": "button", "ubertextbox": "textbox", "uberscrollarea": "scrollarea",
    "uberpieslice": "pieslice", "dropDown": "dropdown",
}


class Expander:
    def __init__(self, db: GuiDB, log=None):
        self.db = db
        self.log = log if log is not None else []

    # ---------------- helpers
    def is_element_key(self, key: str) -> bool:
        if key in PROP_BLOCKS:
            return False
        return key in self.db.types or key in PRIMITIVE_ALIAS or key in (
            "widget", "hbox", "vbox", "icon", "button", "textbox", "text_single", "text_multi",
            "scrollarea", "flowcontainer", "fixedgridbox", "dynamicgridbox", "overlappingitembox",
            "container", "margin_widget", "piechart", "pieslice", "progressbar", "expand",
            "ecs_scene_viewer_widget", "window", "editbox", "checkbutton", "dropdown",
            "scrollbar", "scrollvbox", "barchart", "barslice", "spacer", "textbox",
            "scrollbar_vertical", "scrollbar_horizontal", "scrollwidget", "tooltip_widget",
            "uberpieslice", "pieslice_no_highlight", "ranged_slider")

    def splice_usings(self, body: list[Node], depth=0) -> list[Node]:
        out = []
        for n in body:
            if n.key == "using" and isinstance(n.value, str):
                tpl = self.db.templates.get(n.value)
                if tpl is None:
                    self.log.append(f"missing template {n.value}")
                    continue
                if depth > 30:
                    continue
                out.extend(self.splice_usings(tpl, depth + 1))
            else:
                out.append(n)
        return out

    def expand_entries(self, body: list[Node], ctx: dict, depth=0) -> list[Node]:
        """Resolve usings and blocks; leave elements/properties as nodes."""
        out = []
        for n in self.splice_usings(body):
            if n.key.startswith("blockoverride:"):
                continue
            if n.key.startswith("block:"):
                name = n.key[6:]
                if name in ctx:
                    content, _ = ctx[name]
                    sub = dict(ctx)
                    del sub[name]
                    # nodes spliced from an override keep the reduced context: an override never applies to
                    # elements inside its own content (otherwise scrollbox-in-scrollbox recurses forever)
                    for x in self.expand_entries(content, sub, depth + 1):
                        if x.is_block() and getattr(x, "ctx", None) is None:
                            x = Node(x.key, x.op, x.value, x.src, x.line)
                            x.ctx = sub
                        out.append(x)
                else:
                    out.extend(self.expand_entries(n.value, ctx, depth + 1))
                continue
            out.append(n)
        return out

    # ---------------- element building
    def build(self, key: str, body: list[Node], ctx: dict, src="", line=0) -> Element:
        body = self.splice_usings(body)
        inst_over = {n.key[14:]: (n.value, None) for n in body if n.key.startswith("blockoverride:")}
        chain = self.db.type_chain(key)
        kind = key
        if chain:
            base = self.db.type_base[chain[-1]]
            kind = PRIMITIVE_ALIAS.get(base, base)
        kind = PRIMITIVE_ALIAS.get(kind, kind)
        # override priority: base types lowest < outer ctx < this instance's own blockoverride.
        # A nested instance that re-declares an override must get its own content (ui_library nests a
        # scrollbox inside a scrollbox's "scrollbox_content"; outer-wins would recurse forever).
        new_ctx: dict = {}
        for tname in reversed(chain):
            for n in self.splice_usings(self.db.types[tname]):
                if n.key.startswith("blockoverride:"):
                    new_ctx[n.key[14:]] = (n.value, None)
        new_ctx.update(ctx)
        new_ctx.update(inst_over)
        entries = []
        for tname in reversed(chain):
            entries.extend(self.expand_entries(self.db.types[tname], new_ctx))
        entries.extend(self.expand_entries(body, new_ctx))
        el = Element(kind=kind, typename=key, src=src, line=line)
        self.fill(el, entries, new_ctx)
        # The engine merges named siblings; drawing both hides accidental row
        # overrides. Diagnose duplicates rather than claiming to emulate merging.
        explicit_names = {
            prop.value for entry in entries
            if entry.is_block() and self.is_element_key(entry.key)
            for prop in entry.value
            if prop.key == 'name' and isinstance(prop.value, str)
        }
        named_children = {}
        for child in el.children:
            name = child.props.get('name')
            if not isinstance(name, str) or not name or name not in explicit_names:
                continue
            if name in named_children:
                previous = named_children[name]
                self.log.append(
                    f"DUPLICATE NAMED CHILD: {name} at {child.src}:{child.line}; "
                    f"previous at {previous.src}:{previous.line}"
                )
            named_children[name] = child
        bt = el.props.pop("__buttontext__", None)
        if bt and ("text" in el.props or "raw_text" in el.props):
            tb = self.build(*bt)
            for k in ("text", "raw_text"):
                if k in el.props:
                    tb.props[k] = el.props.pop(k)
            tb.props.setdefault("size", ["100%", "100%"])
            el.children.insert(0, tb)
        if el.kind in ("hbox", "vbox"):
            for child in el.children:
                if child.props.get("ignore_layout") == "yes":
                    continue
                invalid = []
                if "parentanchor" in child.props:
                    invalid.append("parentanchor")
                if any("%" in str(v) for v in child.props.get("size", [])):
                    invalid.append("size with a percentage")
                for prop in invalid:
                    self.log.append(
                        f"INVALID BOX CHILD: {prop} on {child.typename} "
                        f"inside {el.kind} at {child.src}:{child.line}"
                    )
        return el

    def fill(self, el: Element, entries: list[Node], outer_ctx: dict):
        for n in entries:
            ctx = getattr(n, "ctx", None) or outer_ctx
            k = n.key
            if k == "background" and n.is_block():
                el.backgrounds.append(self.texture_spec(n.value, ctx))
            elif k == "modify_texture" and n.is_block():
                el.modifies.append(self.texture_spec(n.value, ctx))
            elif k == "glow" and n.is_block():
                el.glows.append(self.props_of(self.expand_entries(n.value, ctx)))
            elif k == "state" and n.is_block():
                el.states.append(self.props_of(self.expand_entries(n.value, ctx)))
            elif k == "tooltipwidget" and n.is_block():
                sub = [c for c in self.expand_entries(n.value, ctx) if c.is_block() and self.is_element_key(c.key)]
                if sub:
                    el.tooltipwidget = (sub[0].key, sub[0].value, ctx, sub[0].src, sub[0].line)
            elif k == "item" and n.is_block():
                sub = [c for c in self.expand_entries(n.value, ctx) if c.is_block() and self.is_element_key(c.key)]
                if sub:
                    el.item = (sub[0].key, sub[0].value, ctx, sub[0].src, sub[0].line)
            elif k == "active_item" and n.is_block():
                # dropDown keeps its selected item as a regular child; the open list is
                # an engine-owned popup and is intentionally not instantiated here.
                sub = [c for c in self.expand_entries(n.value, ctx) if c.is_block() and self.is_element_key(c.key)]
                if sub:
                    active = self.build(sub[0].key, sub[0].value, ctx, sub[0].src, sub[0].line)
                    # The vanilla control supplies a default label until a selection is made.
                    # The UI Library deliberately leaves this block empty, so preserve that
                    # visible engine fallback for the static reference render.
                    def set_default_label(node):
                        if node.kind in ("textbox", "editbox") and not ("text" in node.props or "raw_text" in node.props):
                            node.props["raw_text"] = "默认"
                            return True
                        return any(set_default_label(c) for c in node.children)
                    set_default_label(active)
                    el.children.append(active)
            elif k in ("scrollwidget", "viewportwidget") and n.is_block():
                # scrollarea content wrapper: children inside become our children (tagged)
                for c in self.expand_entries(n.value, ctx):
                    if c.is_block() and self.is_element_key(c.key):
                        ch = self.build(c.key, c.value, ctx, c.src, c.line)
                        ch.props["__wrapper__"] = k
                        el.children.append(ch)
            elif k == "buttonText" and n.is_block():
                # button label: the button's own text/raw_text is rendered by this textbox child
                for c in self.expand_entries(n.value, ctx):
                    if c.is_block() and self.is_element_key(c.key):
                        el.props["__buttontext__"] = (c.key, c.value, ctx, c.src, c.line)
            elif k in ("scrollbar_vertical", "scrollbar_horizontal", "contextmenu_widget"):
                el.props[k] = True
            elif k in ("track", "track_range", "track_highlight", "slider", "slider_low",
                       "dec_button", "inc_button", "dec_button_low", "inc_button_low") and n.is_block():
                # Special ranged_slider parts are specs rather than normal children.
                el.props[k] = self.widget_spec(n.value, ctx)
            elif n.is_block() and self.is_element_key(k):
                el.children.append(self.build(k, n.value, ctx, n.src, n.line))
            elif n.is_block():
                if k in ("action_tooltip", "scripted_action_tooltip", "tooltipmeta"):
                    el.props[k] = self.props_of(self.expand_entries(n.value, ctx))
                else:
                    el.props[k] = scalars(n) if all(not c.is_block() for c in n.value) else n.value
            else:
                if k == "datacontext":
                    el.props.setdefault("datacontexts", []).append(n.value)
                el.props[k] = n.value

    def build_lazy(self, spec):
        key, body, ctx, src, line = spec
        return self.build(key, body, ctx, src, line)

    def texture_spec(self, body: list[Node], ctx: dict) -> dict:
        entries = self.expand_entries(body, ctx)
        spec = {"modifies": []}
        for n in entries:
            if n.key == "modify_texture" and n.is_block():
                spec["modifies"].append(self.texture_spec(n.value, ctx))
            elif n.is_block():
                spec[n.key] = scalars(n)
            else:
                spec[n.key] = n.value
        return spec

    def widget_spec(self, body: list[Node], ctx: dict) -> dict:
        """Flatten a widget/template block into a renderable texture spec.

        Slider parts use ``using = economy_slider_*`` templates whose first node is
        a type instance. Build that instance once, retaining its background and
        texture layers while ignoring layout-only child widgets.
        """
        spec = {"modifies": []}
        for n in self.expand_entries(body, ctx):
            if n.key == "modify_texture" and n.is_block():
                spec["modifies"].append(self.texture_spec(n.value, ctx))
            elif n.is_block() and self.is_element_key(n.key):
                child = self.build(n.key, n.value, ctx, n.src, n.line)
                spec.update(child.props)
                spec["modifies"].extend(child.modifies)
                spec.setdefault("backgrounds", []).extend(child.backgrounds)
            elif n.is_block():
                spec[n.key] = scalars(n) if all(not c.is_block() for c in n.value) else n.value
            else:
                spec[n.key] = n.value
        return spec

    def props_of(self, entries: list[Node]) -> dict:
        d = {}
        for n in entries:
            d[n.key] = scalars(n) if n.is_block() and all(not c.is_block() for c in n.value) else n.value
        return d


def dump(el: Element, depth=0, out=None, maxdepth=99):
    out = out if out is not None else []
    vis = el.props.get("visible", "")
    txt = el.props.get("text") or el.props.get("raw_text") or ""
    out.append("  " * depth + f"{el.typename}<{el.kind}> {el.w:.0f}x{el.h:.0f}@{el.x:.0f},{el.y:.0f} "
               + (f"vis={vis[:60]} " if vis else "") + (f"txt={str(txt)[:50]}" if txt else ""))
    out[-1] = out[-1].rstrip()
    if depth < maxdepth:
        for c in el.children:
            dump(c, depth + 1, out, maxdepth)
    return out

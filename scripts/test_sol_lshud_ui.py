"""Render the shipped SOL left-panel row and its tooltip in both languages and targets.

Uses installed game assets and invented data; does not simulate engine hover.
Set SOL_LSHUD_PREVIEW_OUT to retain the badge and tooltip review images.
"""
import importlib.util
import os
import sys
import unittest
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "ai_gui_assessment/renderer")]

from PIL import Image
import data as binding
import gui
import textures
from data import Evaluator, Formats, Loc, TextIcons
from engine import Engine
from gui import Expander, GuiDB, collect_files
from gen_sol_lshud import LOC, LOC_ENGLISH, PANEL_W, PENDING_BODY_W, ROW_H, ROW_Y, TIER_TEX, W, outputs

# Reuse the adopted prototype's invented country/estate fixtures, never its GUI.
spec = importlib.util.spec_from_file_location(
    "lshud_fixtures", ROOT / "ai_gui_assessment/prototypes/living_standard_hud/build.py"
)
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
row_spec = importlib.util.spec_from_file_location(
    "lshud_leftrow_design", ROOT / "ai_gui_assessment/prototypes/living_standard_leftrow/build.py"
)
row_design = importlib.util.module_from_spec(row_spec)
row_spec.loader.exec_module(row_design)
four_spec = importlib.util.spec_from_file_location(
    "lshud_four_section_design", ROOT / "ai_gui_assessment/prototypes/living_standard_4sections/build.py"
)
four_design = importlib.util.module_from_spec(four_spec)
four_spec.loader.exec_module(four_design)
from eu5_gui_renderer import hud


def visible_walk(engine, element):
    pushed = engine.push(element)
    try:
        if engine.visible(element):
            yield element
            for child in element.children:
                yield from visible_walk(engine, child)
    finally:
        engine.pop(pushed)


class LivingStandardHUD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_language = binding.LANG
        cls.original_search = list(textures.SEARCH)
        cls.databases = {
            target: GuiDB(collect_files(mod_root=ROOT / "src" / target))
            for target in ("stable", "sol_standalone")
        }
        cls.out = Path(os.environ["SOL_LSHUD_PREVIEW_OUT"]) if os.environ.get("SOL_LSHUD_PREVIEW_OUT") else None
        if cls.out:
            cls.out.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        binding.LANG = cls.original_language
        textures.SEARCH[:] = cls.original_search
        textures.TEXTURES.load.cache_clear()

    def context(self, target, language, state, enabled=1, left_shown=False, left_attached=False):
        binding.LANG = language
        target_root = ROOT / "src" / target
        textures.SEARCH[:] = [target_root / stage for stage in ("loading_screen", "main_menu", "in_game")]
        textures.SEARCH += [p for p in self.original_search if ROOT / "src" not in p.parents]
        textures.TEXTURES.load.cache_clear()
        textures.TEXTURES.missing.clear()
        loc = Loc()
        for path in (target_root / "main_menu/localization" / language).glob("*.yml"):
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                match = Loc.LINE_RE.match(line)
                if match:
                    loc.d[match[1]] = match[2]
        rank_pending = state in ("_rank_pending", "_rank_yoy_pending")
        overrides, rank, ready = fixtures.STATES.get(state, fixtures.STATES[""])
        yoy_ready = ready and state not in ("_yoy_pending", "_rank_yoy_pending")

        def annual_value(match):
            if not yoy_ready:
                raise AssertionError("Unavailable annual comparison was read: " + match[0])
            return dict(fixtures.PLAYER_VARS, **overrides)[match[1]]

        four_state = {"_rank2": "", "_yoy_pending": "", "_rank_yoy_pending": "_rank_pending"}.get(state, state)
        mocks = four_design.mocks(four_state) + [
            (r"Player\.MakeScope\.ScriptValue\('sol_ls_hud_enabled'\)", enabled),
            (r"LeftView\.IsShown", left_shown),
            (r"LeftView\.IsSideAttached", left_attached),
            (r"ExtraTooltipInfo.GetUIAction", {"__type__": "UIAction"}),
            (r"Player\.MakeScope\.GetVariable\('sol_ls_(rank|tier)'\)\.IsSet", ready and not rank_pending),
            (r"Player\.MakeScope\.GetVariable\('sol_ls_pci_yoy'\)\.IsSet", yoy_ready),
            (r"Player\.MakeScope\.GetVariable\('(sol_ls_pci_(?:prev|yoy)\w*)'\)\.GetValue", annual_value),
            (r"GetGlobalVariable\('sol_ls_rank_count'\)\.IsSet", not rank_pending),
        ] + fixtures.state_mocks(overrides, rank, ready) + hud.mocks()
        log = []
        ex = Expander(self.databases[target], log)
        eng = Engine(ex, Evaluator(mocks, loc, log), loc, Formats(), TextIcons(), 1)
        path = target_root / "in_game/gui/SOL_lshud.gui"
        node = next(n for n in ex.db.roots[str(path)] if n.is_block() and n.key == "widget")
        root = ex.build(node.key, node.value, {}, str(path), node.line)
        eng.place(root, 0, 0, 1920, 1080)
        row = next(e for e in hud.walk(root) if e.props.get("name") == "sol_lshud4_row")
        owner = row
        tip = ex.build_lazy(next(e for e in hud.walk(owner) if e.props.get("name") == "sol_lshud4_section_1").tooltipwidget)
        width, height = eng.measure(tip, None)["hint"]
        eng.place(tip, 12, 12, width, height)
        return eng, ex, root, row, tip, (width, height), log

    def test_generated_outputs_and_localization_encoding(self):
        for path, expected in outputs().items():
            self.assertEqual(path.read_bytes(), expected, str(path))
            if path.suffix == ".yml":
                self.assertTrue(expected.startswith(b"\xef\xbb\xbf"), str(path))
            if path.suffix == ".gui":
                self.assertFalse(expected.startswith(b"\xef\xbb\xbf"), str(path))
        self.assertEqual(LOC.keys(), LOC_ENGLISH.keys())

    def test_disabled_sol_hides_the_row(self):
        eng, *_ = self.context("stable", "simp_chinese", "", enabled=0)
        self.assertFalse(list(visible_walk(eng, root)))

    def test_leftrow_hides_when_left_panel_is_open_or_ui_is_disabled(self):
        for shown, attached, enabled in ((True, False, 1), (False, True, 1), (False, False, 0)):
            with self.subTest(shown=shown, attached=attached, enabled=enabled):
                eng, *_ = self.context("stable", "simp_chinese", "", enabled, shown, attached)
                self.assertFalse(list(visible_walk(eng, root)))

    def test_four_section_row_and_tooltip_states(self):
        for target in self.databases:
            for language in ("simp_chinese", "english"):
                for state in (*fixtures.STATES, "_rank_pending", "_yoy_pending", "_rank_yoy_pending"):
                    with self.subTest(target=target, language=language, state=state):
                        eng, ex, root, row, tip, (width, height), log = self.context(target, language, state)
                        self.assertEqual((row.x, row.y, row.w, row.h), (0, ROW_Y, PANEL_W, ROW_H))
                        self.assertEqual((row.x, row.y, row.w, row.h), (0, ROW_Y, PANEL_W, ROW_H))
                        elements = []
                        texts = []
                        for element in visible_walk(eng, tip):
                            elements.append(element)
                            if element.kind == "textbox":
                                texts.append(eng.text_of(element) or "")
                        names = {e.props.get("name") for e in elements}
                        self.assertTrue(any(name == "sol_lshud4_income_body" for name in names) or state == "_pending")
                        self.assertIn("sol_lshud4_income_pending" if state == "_pending" else "sol_lshud4_income_body", names)
                        self.assertTrue(any("1.86" in text for text in texts) or state == "_pending")
                        sections = [next(e for e in hud.walk(row) if e.props.get("name") == f"sol_lshud4_section_{i}") for i in range(1, 5)]
                        self.assertEqual(len(sections), 4)
                        for section in sections:
                            self.assertTrue(section.tooltipwidget)
                        image = Image.new("RGBA", (int(width + 24), int(height + 24)), (40, 52, 46, 255))
                        eng.render(tip, image)
                        bar = Image.new("RGBA", (1920, ROW_Y + ROW_H + 8), (29, 35, 42, 255))
                        eng.render(root, bar)
                        self.assertFalse(textures.TEXTURES.missing, textures.TEXTURES.missing)
                        self.assertFalse([entry for entry in log if "sol_substitute_" not in entry], log)
                        self.assertFalse([item for item in eng.unresolved_contexts if "sol_substitute_" not in item], eng.unresolved_contexts)
                        if self.out:
                            stem = f"{target}_{language}{state or '_normal'}"
                            image.save(self.out / f"{stem}_tooltip.png")
                            bar.crop((0, ROW_Y - 5, PANEL_W, ROW_Y + ROW_H + 5)).save(self.out / f"{stem}_row.png")

    def test_actual_glorp_ui_composition_pushes_its_bar_below_the_row(self):
        target_root = ROOT / "src/stable"
        row_path = target_root / "in_game/gui/SOL_lshud.gui"
        compat_path = target_root / "in_game/gui/SOL_lshud_glorp_compat.gui"
        textures.SEARCH[:] = [target_root / stage for stage in ("loading_screen", "main_menu", "in_game")]
        glorp = ROOT / ".eu5-base/reference_mods/3601047146"
        textures.SEARCH += [glorp / stage for stage in ("loading_screen", "main_menu", "in_game")]
        textures.SEARCH += [path for path in self.original_search if ROOT / "src" not in path.parents]
        textures.TEXTURES.load.cache_clear()
        textures.TEXTURES.missing.clear()
        original_row, original_compat = row_design.ROW_GUI, row_design.COMPAT_GUI
        row_design.ROW_GUI, row_design.COMPAT_GUI = row_path, compat_path
        try:
            db = GuiDB(row_design.gui_files(with_glorp=True, compat=True, with_row=True))
            log = []
            ex = Expander(db, log)
            root = hud.build(db, ex, 1920, 1080)
            nodes = db.roots[str(row_path)]
            node = next(n for n in nodes if n.is_block() and n.key == "widget")
            row_root = ex.build(node.key, node.value, {}, str(row_path), node.line)
            root.children.append(row_root)
            row = next(e for e in hud.walk(row_root) if e.props.get("name") == "sol_lshud4_row")
            loc = row_design.load_loc(with_glorp=True)
            for path in (target_root / "main_menu/localization/simp_chinese").glob("*.yml"):
                for line in path.read_text(encoding="utf-8-sig").splitlines():
                    match = Loc.LINE_RE.match(line)
                    if match:
                        loc.d[match[1]] = match[2]
            mocks = row_design.glorp_mocks(bar_shown=True) + row_design.sol_mocks("") + hud.mocks()
            eng = Engine(ex, Evaluator(mocks, loc, log), loc, Formats(), TextIcons(), 1)
            eng.place(root, 0, 0, 1920, 1080)
            bar = next(e for e in hud.walk(root) if e.typename == "left_panel_info_bar")
            bar_body = next(child for child in bar.children if child.kind == "widget")
            self.assertEqual((row.x, row.y, row.w, row.h), (0, ROW_Y, PANEL_W, ROW_H))
            self.assertEqual(round(bar_body.y), ROW_Y + ROW_H)
            image = Image.new("RGBA", (1920, 800), (29, 35, 42, 255))
            eng.render(root, image)
            tip = ex.build_lazy(next(e for e in hud.walk(row) if e.props.get("name") == "sol_lshud4_section_1").tooltipwidget)
            tip_w, tip_h = eng.measure(tip, None)["hint"]
            eng.place(tip, 8, ROW_Y + ROW_H + 6, tip_w, tip_h)
            eng.render(tip, image)
            self.assertFalse(textures.TEXTURES.missing, textures.TEXTURES.missing)
            self.assertFalse(any("SOL_LSHUD" in message or "sol_ls" in message for message in log), log)
            sol_unresolved = {item for item in eng.unresolved_contexts if "SOL_LSHUD" in item or "sol_ls" in item}
            self.assertFalse(sol_unresolved, sol_unresolved)

            hidden_mocks = row_design.glorp_mocks(bar_shown=False) + row_design.sol_mocks("") + hud.mocks()
            hidden_engine = Engine(ex, Evaluator(hidden_mocks, loc, log), loc, Formats(), TextIcons(), 1)
            hidden_engine.place(root, 0, 0, 1920, 1080)
            visible = list(visible_walk(hidden_engine, root))
            self.assertFalse(any(e.typename == "left_panel_info_bar" and e.h > 0 for e in visible))
            toggle = [e for e in visible if e.kind == "icon" and
                      e.props.get("texture") == "gfx/interface/component_tiles/bottom_menu_ribbon.dds"]
            self.assertTrue(toggle, "the collapsed Glorp stats-bar toggle must remain available")
            self.assertGreaterEqual(round(toggle[0].y), ROW_Y + ROW_H)
            hidden_sol_unresolved = {item for item in hidden_engine.unresolved_contexts if "SOL_LSHUD" in item or "sol_ls" in item}
            self.assertFalse(hidden_sol_unresolved, hidden_sol_unresolved)
            if self.out:
                image.crop((0, 0, 900, min(800, ROW_Y + ROW_H + 10 + int(tip_h)))).save(
                    self.out / "stable_glorp_ui_leftrow_hover.png"
                )
        finally:
            row_design.ROW_GUI, row_design.COMPAT_GUI = original_row, original_compat
            textures.SEARCH[:] = self.original_search
            textures.TEXTURES.load.cache_clear()

    def test_glorp_compatibility_types_are_emitted_for_both_targets(self):
        from gen_sol_lshud import GLORP_ROOT, _extract_widget_type

        for target in self.databases:
            path = ROOT / "src" / target / "in_game/gui/SOL_lshud_glorp_compat.gui"
            text = path.read_text(encoding="utf-8")
            self.assertIn("position = { 0 36 }", text)
            original = GLORP_ROOT.read_text(encoding="utf-8-sig")
            for type_name in ("left_panel_info_bar", "left_panel_info_toggle"):
                source_body = _extract_widget_type(original, type_name)
                self.assertIn(source_body, text)
        registration = (ROOT / "src/stable/in_game/gui/scripted_widgets/SOL_lshud_scripted_widgets.txt").read_text(encoding="utf-8")
        self.assertIn("gui/SOL_lshud.gui = sol_lshud4_root", registration)


if __name__ == "__main__":
    unittest.main()

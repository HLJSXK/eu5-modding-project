"""Check shipped SOL substitution UI layouts and hover text with the GUI renderer.

Requires the installed game assets. Set SOL_UI_PREVIEW_OUT to write review images.
This checks mock data, source scopes and layout; it does not simulate engine hover.
"""
import csv
import os
import re
import sys
import unittest
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "ai_gui_assessment/renderer")]

from PIL import Image, ImageStat
import data as binding
import gui
import scenarios
import textures
from data import Evaluator, Formats, Loc, TextIcons
from engine import Engine
from gui import Expander, GuiDB
from pdx import parse
from sol_goods_ui import _consumed_expr, _good_cell, render_goods_vbox
from sol_substitution import CORE


def walk(element):
    yield element
    for child in element.children:
        yield from walk(child)


class SubstitutionUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = GuiDB()
        cls.formats, cls.icons = Formats(), TextIcons()
        cls.old_language = binding.LANG
        cls.old_texture_search = list(textures.SEARCH)
        textures.SEARCH[:0] = [ROOT / 'reference_mods/3613232232/main_menu',
                              ROOT / 'reference_mods/3785316314/main_menu']
        cls.out = Path(os.environ['SOL_UI_PREVIEW_OUT']) if os.environ.get('SOL_UI_PREVIEW_OUT') else None
        if cls.out:
            cls.out.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        binding.LANG = cls.old_language
        textures.SEARCH[:] = cls.old_texture_search

    def engine(self, mocks, language='simp_chinese'):
        binding.LANG = language
        log = []
        ev = Evaluator(mocks, Loc(), log)
        return Engine(Expander(self.db, log), ev, ev.loc, self.formats, self.icons, 1), log

    def cell(self, eng, good='cloth', scope='Location.GetMarket.MakeScope'):
        variable_map = 'sol_market_consumes' if scope.startswith('Location.') else 'gls_country_consumes'
        source = '\n'.join(_good_cell('', good, _consumed_expr(variable_map, good, scope), scope))
        node = parse(source)[0]
        return eng.ex.build(node.key, node.value, {}, '<goods cell>', 0)

    def test_all_memberships_and_compat_extras(self):
        expected = []
        with (ROOT / 'data/goods_weights.csv').open(encoding='utf-8-sig', newline='') as handle:
            expected = [(r['group'], r['good']) for r in csv.DictReader(handle)]
        source = render_goods_vbox(CORE + ['victuals', 'aromatics'], 'sol_market_consumes',
                                   'Location.GetMarket.MakeScope', '')
        nodes = parse(source)
        actual = []

        def visit(items, group=None):
            for node in items:
                if not node.is_block():
                    continue
                current = group
                if node.key == 'sol_group_row':
                    label = next(n for n in node.value if n.key == 'blockoverride:sol_group_label')
                    current = label.value[0].value.removeprefix('SOL_SUBGROUP_').lower()
                for child in node.value:
                    if child.key == 'tooltip' and isinstance(child.value, str) and child.value.startswith('@'):
                        actual.append((current, child.value[1:].split('!', 1)[0]))
                visit(node.value, current)

        visit(nodes)
        self.assertCountEqual(actual, expected + [('ungrouped', 'victuals'), ('ungrouped', 'aromatics')])

    def test_hover_context_and_missing_market(self):
        for language in ('simp_chinese', 'english'):
            with self.subTest(language=language):
                eng, log = self.engine(scenarios.tooltip(), language)
                text = eng.process(self.cell(eng).props['tooltip'], raw=True)
                self.assertIn('0.88', text)
                self.assertIn('0.50', text)
                self.assertIn(eng.loc.get('SOL_SUB_ACTIVE'), text)
                self.assertNotIn('SOL_', text)
                country, country_log = self.engine(scenarios.situation(), language)
                text = country.process(self.cell(country, scope='Player.MakeScope').props['tooltip'], raw=True)
                self.assertNotIn(country.loc.get('SOL_SUB_PRICE_WEIGHT'), text)
                self.assertIn('0.88', text)
                # A missing market must not invent the neutral price weight 1.
                mocks = [(r"GetVariableFromGlobalVariableMap\('sol_market_substitute_weight_cloth',.*\)\.IsSet", False)]
                missing, missing_log = self.engine(mocks + scenarios.tooltip(), language)
                text = missing.process(self.cell(missing).props['tooltip'], raw=True)
                self.assertIn(missing.loc.get('SOL_SUB_PRICE_PENDING'), text)
                self.assertNotIn(missing.loc.get('SOL_SUB_PRICE_WEIGHT') + ':', text)
                self.assertFalse(log + country_log + missing_log)

    def test_supply_dimming_and_substitution_markers(self):
        for consumed in (True, False):
            eng, log = self.engine([
                (r"GetVariableFromGlobalVariableMap\('sol_market_consumes_cloth',.*\)\.GetValue", int(consumed))
            ] + scenarios.tooltip())
            cell = self.cell(eng)
            icons = [e for e in cell.children if e.kind == 'icon' and eng.visible(e)]
            self.assertEqual(len(icons), 1)
            self.assertEqual(float(icons[0].props.get('alpha', 1)), 1 if consumed else .3)
            eng.measure(cell, None)
            eng.place(cell, 0, 0, 20, 24)
            img = Image.new('RGBA', (20, 24), (0, 0, 0, 255))
            eng.render(cell, img)
            brightness = sum(ImageStat.Stat(img.convert('RGB')).mean)
            if consumed:
                bright = brightness
            else:
                self.assertLess(brightness, bright * .6)
            markers = [eng.text_of(e) for e in cell.children if e.kind == 'textbox' and eng.visible(e)]
            self.assertEqual(markers, ['#R -#!'] if consumed else [])
            self.assertFalse(log)
        # Compatibility-only goods remain neutral and have no substitution marker.
        eng, log = self.engine(scenarios.tooltip())
        extra = self.cell(eng, 'victuals')
        self.assertFalse([e for e in extra.children if e.kind == 'textbox'])
        self.assertIn('1.00', eng.process(extra.props['tooltip'], raw=True))
        self.assertFalse(log)

    def test_country_summary_states(self):
        for status, key in ((0, 'SOL_SUB_DISABLED'), (1, 'SOL_SUB_PENDING'), (2, 'SOL_SUB_SUMMARY')):
            mocks = scenarios.substitution_mocks('Player.MakeScope', status) + scenarios.situation()
            eng, log = self.engine(mocks)
            source = render_goods_vbox(['cloth'], 'gls_country_consumes', 'Player.MakeScope', '')
            node = parse(source)[0]
            element = eng.ex.build(node.key, node.value, {}, '<country goods>', 0)
            summary = next(e for e in element.children if 'raw_text' in e.props)
            text = eng.text_of(summary)
            if status == 2:
                self.assertIn('1337', text)
                self.assertIn('42', text)
                self.assertIn('33.0%', text)
            else:
                self.assertEqual(text, eng.loc.get(key))
                self.assertNotIn('1337', text)
            self.assertFalse(log)

    def test_shipped_tooltip_layouts(self):
        for target in ('stable', 'sol_standalone', 'sol_pp_compatibility_submod', 'sol_jtg_compatibility_submod'):
            compat = 'compatibility' in target
            path = ROOT / 'src' / target / 'in_game/gui' / ('zz_SOL_economy_local.gui' if compat else 'SOL_economy_local.gui')
            self.db._register(parse(path.read_text(encoding='utf-8-sig'), str(path), dict(self.db.consts)))
            for language in ('simp_chinese', 'english'):
                with self.subTest(target=target, language=language):
                    eng, log = self.engine(scenarios.tooltip(), language)
                    node = next(n for n in self.db.templates['StandardofLiving_tooltip'] if n.is_block())
                    element = eng.ex.build(node.key, node.value, {}, str(path), 0)
                    width, height = eng.measure(element, None)['hint']
                    eng.place(element, 0, 0, width, height)
                    self.assertLessEqual(width, 500)
                    self.assertLessEqual(height, 1080)
                    for child in walk(element):
                        if child.w > 0 and eng.visible(child):
                            self.assertGreaterEqual(child.x, -1, child.kind)
                            self.assertLessEqual(child.x + child.w, width + 1, child.kind)
                    image = Image.new('RGBA', (int(width), int(height)), (40, 52, 46, 255))
                    eng.render(element, image)
                    if self.out:
                        image.save(self.out / f'{target}_{language}.png')
                    self.assertFalse(log, log)


if __name__ == '__main__':
    unittest.main()

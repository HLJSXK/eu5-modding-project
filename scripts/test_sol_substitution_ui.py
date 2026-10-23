"""Check shipped SOL substitution UI layouts and hover text with the GUI renderer.

Requires the installed game assets. Set SOL_UI_PREVIEW_OUT to write review images.
This checks mock data, source scopes and layout; it does not simulate engine hover.
"""
import csv
import os
import operator
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
from sol_goods_ui import (_consumed_expr, _good_cell, render_goods_vbox, GOODS_CONTENT_W,
                          LOCATION_CARD_W, GOOD_CELL_H, GROUP_CARD_H, SUBSTITUTION_LEVEL_ICONS)
from sol_substitution import CORE
from gen_sol_goods_tooltip import inject, inject_market, price_template, VANILLA_GUI, VANILLA_MARKET_GUI, PRICE_TIERS


def walk(element):
    yield element
    for child in element.children:
        yield from walk(child)


def visible_walk(engine, element):
    if engine.visible(element):
        yield element
        for child in element.children:
            yield from visible_walk(engine, child)


class SubstitutionUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = GuiDB()
        cls.formats, cls.icons = Formats(), TextIcons()
        cls.localizations = {}
        cls.old_language = binding.LANG
        cls.old_texture_search = list(textures.SEARCH)
        textures.SEARCH[:0] = [ROOT / '.eu5-base/reference_mods/3613232232/main_menu',
                              ROOT / '.eu5-base/reference_mods/3785316314/main_menu']
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
        if language not in self.localizations:
            self.localizations[language] = Loc()
        ev = Evaluator(mocks, self.localizations[language], log)
        return Engine(Expander(self.db, log), ev, ev.loc, self.formats, self.icons, 1), log

    def goods_engine(self, good='wine', ratio=None, language='simp_chinese', overrides=()):
        eng, _ = self.engine([], language)
        return self.engine(list(overrides) + scenarios.goods_tooltip(good, ratio, eng.loc), language)

    def cell(self, eng, good='cloth', scope='Location.GetMarket.MakeScope'):
        variable_map = 'sol_market_consumes' if scope.startswith('Location.') else 'gls_country_consumes'
        source = '\n'.join(_good_cell('', good, _consumed_expr(variable_map, good, scope), scope))
        node = parse(source)[0]
        return eng.ex.build(node.key, node.value, {}, '<goods cell>', 0)

    def test_gui_lexer_rejects_invalid_escapes(self):
        for escape in ('\\n', '\\t', '\\q'):
            with self.subTest(escape=escape):
                with self.assertRaisesRegex(ValueError, 'invalid quoted-string escape'):
                    parse(f'widget = {{ tooltip = "first{escape}second" }}', 'bad.gui')
        parse(r'widget = { tooltip = "escaped quote: \"; escaped slash: \\" }')
        parse('# comment with "ignored\\n"\nwidget = { tooltip = "valid" }')

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
                    current = next(n.value for n in label.value if n.key == 'text').removeprefix('SOL_SUBGROUP_').lower()
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
                membership_lines = len(eng.loc.get('SOL_GOOD_SUB_cloth').splitlines())
                self.assertEqual(len(text.splitlines()), 6 + membership_lines)
                self.assertNotIn('\\n', text)
                self.assertIn('0.88', text)
                self.assertIn('0.50', text)
                self.assertIn(eng.loc.get('SOL_SUB_ACTIVE'), text)
                self.assertNotIn('SOL_', text)
                country, country_log = self.engine(scenarios.situation(), language)
                text = country.process(self.cell(country, scope='Player.MakeScope').props['tooltip'], raw=True)
                self.assertEqual(len(text.splitlines()), 5 + membership_lines)
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
            eng.place(cell, 0, 0, 18, GOOD_CELL_H)
            img = Image.new('RGBA', (18, GOOD_CELL_H), (0, 0, 0, 255))
            eng.render(cell, img)
            brightness = sum(ImageStat.Stat(img.crop((0, 0, 18, 18)).convert('RGB')).mean)
            if consumed:
                bright = brightness
            else:
                self.assertLess(brightness, bright * .6)
            markers = [eng.text_of(e) for e in cell.children if e.kind == 'textbox' and eng.visible(e)]
            self.assertEqual(markers, ['@arrow_malus_tier_1!'])
            self.assertFalse(log)
        # Compatibility-only goods remain neutral and have no substitution marker.
        eng, log = self.engine(scenarios.tooltip())
        extra = self.cell(eng, 'victuals')
        self.assertFalse([e for e in extra.children if e.kind == 'textbox'])
        self.assertIn('1.00', eng.process(extra.props['tooltip'], raw=True))
        self.assertFalse(log)

    def test_seven_substitution_levels_below_goods(self):
        cases = (
            (0, 'arrow_malus_tier_3'), (.49999, 'arrow_malus_tier_3'),
            (.5, 'arrow_malus_tier_2'), (.74999, 'arrow_malus_tier_2'),
            (.75, 'arrow_malus_tier_1'), (.99999, 'arrow_malus_tier_1'),
            (1, 'price_stable'), (1.00001, 'arrow_bonus_tier_1'),
            (1.25, 'arrow_bonus_tier_1'), (1.25001, 'arrow_bonus_tier_2'),
            (1.5, 'arrow_bonus_tier_2'), (1.50001, 'arrow_bonus_tier_3'),
            (3, 'arrow_bonus_tier_3'),
        )
        seen = set()
        for scope, country, scenario in (
            ('Location.GetMarket.MakeScope', 'Location.GetOwner.MakeScope', scenarios.tooltip),
            ('Player.MakeScope', 'Player.MakeScope', scenarios.situation),
        ):
            for value, expected in cases:
                with self.subTest(scope=scope, value=value):
                    eng, log = self.engine([
                        (re.escape(country) + r"\.ScriptValue\('sol_substitute_cloth_display'\)", value),
                    ] + scenario())
                    cell = self.cell(eng, scope=scope)
                    eng.measure(cell, None)
                    eng.place(cell, 0, 0, 18, GOOD_CELL_H)
                    markers = [e for e in cell.children if e.kind == 'textbox' and eng.visible(e)]
                    self.assertEqual([eng.text_of(e) for e in markers], [f'@{expected}!'])
                    marker = markers[0]
                    good = next(e for e in cell.children if e.kind == 'icon' and eng.visible(e))
                    self.assertGreaterEqual(marker.y, good.y + good.h)
                    self.assertEqual(marker.x + marker.w / 2, good.x + good.w / 2)
                    self.assertLessEqual(marker.y + marker.h, cell.h)
                    preview = Image.new('RGBA', (18, GOOD_CELL_H), (0, 0, 0, 255))
                    eng.render(cell, preview)
                    ink = preview.crop((0, 18, 18, GOOD_CELL_H)).convert('RGB').getbbox()
                    self.assertIsNotNone(ink)
                    self.assertGreaterEqual(ink[2] - ink[0], 8)
                    seen.add(expected)
                    self.assertFalse(log, log)
            for status in (0, 1):
                eng, log = self.engine([
                    (re.escape(country) + r"\.ScriptValue\('sol_substitute_status_display'\)", status),
                ] + scenario())
                cell = self.cell(eng, scope=scope)
                self.assertFalse([e for e in cell.children if e.kind == 'textbox' and eng.visible(e)])
                self.assertFalse(log, log)
        self.assertEqual(seen, set(SUBSTITUTION_LEVEL_ICONS))

    def test_no_explanatory_text_in_goods_block(self):
        # Player-facing rule: no summary/legend lines above the groups and no
        # explanatory notes in each good's hover, on every surface.
        for scope in ('Player.MakeScope', 'Location'):
            source = render_goods_vbox(['cloth'], 'gls_country_consumes', scope, '')
            for key in ('SOL_SUB_SUMMARY', 'SOL_SUB_LEGEND', 'SOL_SUB_SCOPE_NOTE'):
                self.assertNotIn(key, source)

    def test_supply_legend_removed_everywhere(self):
        for target in ('stable', 'sol_standalone', 'sol_pp_compatibility_submod', 'sol_jtg_compatibility_submod'):
            for rel in ('in_game/gui/panels/situation/global_living_standard.gui',):
                text = (ROOT / 'src' / target / rel).read_text(encoding='utf-8-sig')
                self.assertNotIn('SOL_F_GOODS_SUPPLY_NOTE', text, target)

    def test_tooltip_text_block_outside_tooltip_is_flagged(self):
        # Prove that the original misuse is caught by the renderer, while a real
        # location tooltip continues to supply the tint context.
        bad = parse('textbox = { using = tooltip_text_block_template max_width = 500 text = "SOL_SUB_MULTIPLIER" }')[0]
        eng, log = self.engine(scenarios.situation())
        eng.measure(eng.ex.build(bad.key, bad.value, {}, '<bad panel note>', 0), 500)
        self.assertIn('ExtraTooltipInfo.GetTintColor', log)
        eng, log = self.engine(scenarios.tooltip())
        eng.measure(eng.ex.build(bad.key, bad.value, {}, '<tooltip note>', 0), 500)
        self.assertFalse(log, log)

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
                    self.assertAlmostEqual(width, GOODS_CONTENT_W + 20, delta=1)
                    self.assertLessEqual(height, 1080)
                    for child in walk(element):
                        if child.w > 0 and eng.visible(child):
                            self.assertGreaterEqual(child.x, -1, child.kind)
                            self.assertLessEqual(child.x + child.w, width + 1, child.kind)
                    # Every supplied group, including compatibility tails, is one icon row.
                    cards = [c for c in walk(element) if c.kind == 'vbox' and c.props.get('size') == ['122', str(GROUP_CARD_H)]]
                    self.assertGreaterEqual(len(cards), 20)
                    for card in cards:
                        cells = [c for c in walk(card) if str(c.props.get('tooltip', '')).startswith('@')]
                        self.assertLessEqual(len(cells), 6)
                        self.assertEqual(len({round(c.y, 1) for c in cells}), 1)
                    image = Image.new('RGBA', (int(width), int(height)), (40, 52, 46, 255))
                    eng.render(element, image)
                    if self.out:
                        image.save(self.out / f'{target}_{language}.png')
                    self.assertFalse(log, log)

    def test_duplicate_named_siblings_are_reported(self):
        eng, log = self.engine([])
        node = parse('vbox = { widget = { name = "row" } widget = { name = "row" } }')[0]
        eng.ex.build(node.key, node.value, {}, '<duplicate rows>', 0)
        self.assertTrue(any('DUPLICATE NAMED CHILD: row' in entry for entry in log))
        eng, log = self.engine([])
        node = parse('vbox = { widget = { name = "row_a" widget = { name = "value" } } widget = { name = "row_b" widget = { name = "value" } } }')[0]
        eng.ex.build(node.key, node.value, {}, '<separate row scopes>', 0)
        self.assertFalse(log, log)

    def test_balance_sources_have_unique_sibling_names(self):
        def check(nodes, path):
            seen = set()
            for node in nodes:
                if not node.is_block():
                    continue
                names = [n.value for n in node.value if n.key == 'name' and isinstance(n.value, str)]
                for name in names:
                    self.assertNotIn(name, seen, f'{path}:{node.line}: duplicate sibling {name}')
                    seen.add(name)
                check(node.value, path)
        for target in ('stable', 'sol_standalone', 'sol_pp_compatibility_submod', 'sol_jtg_compatibility_submod'):
            for path in (ROOT / 'src' / target / 'in_game/gui').rglob('*.gui'):
                if path.name in ('SOL_economy_local.gui', 'zz_SOL_economy_local.gui', 'global_living_standard.gui'):
                    check(parse(path.read_text(encoding='utf-8-sig'), str(path)), path)

    def test_compact_balance_rows_and_shared_scale(self):
        from gen_sol_ls_gui import balance_sections, LOC, COUNTRY
        for language in ('simp_chinese', 'english'):
            for scope, prefix, scenario, surface in (
                (LOC, 'local_sol', scenarios.tooltip, 'location'),
                (COUNTRY, 'gls_sol', scenarios.situation, 'country'),
            ):
                with self.subTest(language=language, surface=surface):
                    eng, log = self.engine(scenario(), language)
                    source = '\n'.join(balance_sections(0, scope, prefix, 500))
                    node = next(n for n in parse(source) if n.is_block())
                    root = eng.ex.build(node.key, node.value, {}, '<compact balances>', 0)
                    w, h = eng.measure(root, None)['hint']
                    eng.place(root, 0, 0, w, h)
                    elements = list(visible_walk(eng, root))
                    ruler = [e for e in elements if e.props.get('name') == 'sol_balance_scale']
                    self.assertEqual(len(ruler), 1)
                    labels = ruler[0].children
                    self.assertEqual([e.props['raw_text'] for e in labels],
                                     ['-100%', '-50%', '0%', '+100%', '+200%'])
                    # Each half is linear: -50% and +100% bisect their halves.
                    for label, fraction in zip(labels, (0, .25, .5, .75, 1)):
                        self.assertAlmostEqual(label.x + label.w / 2,
                                               ruler[0].x + fraction * ruler[0].w, delta=.5)
                    for left, right in zip(labels, labels[1:]):
                        self.assertLessEqual(left.x + left.w, right.x)
                    rows = [e for e in elements if e.props.get('name') == 'sol_balance_total_row'
                            or str(e.props.get('name', '')).startswith('sol_balance_estate_row_')]
                    self.assertEqual(len(rows), 5)  # no tribal estate in this government
                    self.assertEqual([e.h for e in rows], [64, 42, 42, 42, 42])
                    right_edges = []
                    for index, row in enumerate(rows):
                        descendants = list(walk(row))
                        named = {e.props.get('name'): e for e in descendants}
                        value = named['sol_balance_value']
                        pair = named['sol_balance_funds_baseline']
                        track = named['sol_balance_track']
                        zero = named['sol_balance_zero_tick']
                        for element in (value, pair):
                            self.assertEqual(element.props['align'], 'right|nobaseline')
                            if element.w > 0:
                                right_edges.append(element.x + element.w)
                        self.assertEqual(pair.props['tooltip'], 'SOL_C_FUNDS_BASELINE_TOOLTIP')
                        self.assertEqual(pair.props['alwaystransparent'], 'no')
                        self.assertIn(' / ', eng.text_of(pair))
                        self.assertIn('#color_gray ', pair.props['raw_text'])
                        self.assertNotEqual(eng.loc.get(pair.props['tooltip']), pair.props['tooltip'])
                        self.assertEqual(int(value.props['fontsize']), 24 if index == 0 else 18)
                        self.assertAlmostEqual(zero.x + zero.w / 2, track.x + track.w / 2)
                        self.assertEqual(zero.w, 2)
                        minors = [e for e in descendants if str(e.props.get('name', '')).startswith('sol_balance_minor_tick_')]
                        self.assertEqual(len(minors), 2)
                        self.assertTrue(all(e.w == 1 for e in minors))
                        for tick, label in zip(minors, (labels[1], labels[3])):
                            self.assertAlmostEqual(tick.x + tick.w / 2,
                                                   label.x + label.w / 2, delta=.5)
                        self.assertAlmostEqual(track.x, ruler[0].x)
                        self.assertAlmostEqual(track.w, ruler[0].w)
                        self.assertAlmostEqual(labels[2].x + labels[2].w / 2, zero.x + zero.w / 2)
                        self.assertTrue(all('raw_text' not in e.props or e.props['raw_text'] not in
                                            ('-100%', '-50%', '0%', '+100%', '+200%') for e in descendants))
                        bars = [e for e in descendants if e.kind == 'progressbar']
                        self.assertEqual([e.h for e in bars], [12, 12] if index == 0 else [8, 8])
                        for tick in minors + [zero]:
                            self.assertAlmostEqual(tick.y + tick.h / 2, bars[0].y + bars[0].h / 2)
                        for child in descendants:
                            if eng.visible(child) and child.w > 0:
                                self.assertGreaterEqual(child.x, row.x)
                                self.assertLessEqual(child.x + child.w, row.x + row.w)
                                self.assertGreaterEqual(child.y, row.y)
                                self.assertLessEqual(child.y + child.h, row.y + row.h)
                    self.assertEqual(len(set(right_edges)), 1)
                    self.assertGreater(len(rows[0].backgrounds), len(rows[1].backgrounds))
                    preview = Image.new('RGBA', (int(w), int(h)), (32, 40, 39, 255))
                    eng.render(root, preview)
                    if self.out:
                        preview.save(self.out / f'balances_{surface}_{language}.png')
                    self.assertFalse(log, log)

    def test_estate_hover_and_government_visibility_on_shipped_surfaces(self):
        estate_keys = {'nobles': 'nobles_estate', 'clergy': 'clergy_estate',
                       'burghers': 'burghers_estate', 'commoners': 'peasants_estate',
                       'tribesmen': 'tribes_estate'}
        for target in ('stable', 'sol_standalone', 'sol_pp_compatibility_submod', 'sol_jtg_compatibility_submod'):
            for surface, country in (('location', 'Location.GetOwner'), ('country', 'Player')):
                root_path = ROOT / 'src' / target / 'in_game/gui'
                path = (root_path / ('SOL_economy_local.gui' if target in ('stable', 'sol_standalone') else 'zz_SOL_economy_local.gui')
                        if surface == 'location' else root_path / 'panels/situation/global_living_standard.gui')
                for exists in (False, True):
                    with self.subTest(target=target, surface=surface, exists=exists):
                        eng, log = self.engine([
                            (re.escape(country) + r"\.GetGovernment\.GetEstateFromKey\('[^']+'\)\.ExistsForCountry", exists),
                            # All sample population is zero: existence still controls the row.
                            (r"(?:Player|Location)\.MakeScope\.ScriptValue\('[^']*pop[^']*'\)", 0),
                        ] + (scenarios.tooltip() if surface == 'location' else scenarios.situation()))
                        node = next(n for n in parse(path.read_text(encoding='utf-8-sig'), str(path)) if n.is_block())
                        root = eng.ex.build(node.key, node.value, {}, str(path), node.line)
                        elements = list(walk(root))
                        total = next(e for e in elements if e.props.get('name') == 'sol_balance_total_row')
                        self.assertTrue(eng.visible(total))
                        total_label = next(e for e in walk(total) if e.props.get('name') == 'sol_balance_label')
                        self.assertEqual(total_label.props['tooltip'], 'SOL_C_BALANCE_TOOLTIP')
                        for estate, key in estate_keys.items():
                            row = next(e for e in elements if e.props.get('name') == f'sol_balance_estate_row_{estate}')
                            self.assertEqual(eng.visible(row), exists)
                            label = next(e for e in walk(row) if e.props.get('name') == 'sol_balance_label')
                            self.assertEqual(label.props['datacontexts'], [f"[{country}.GetGovernment.GetEstateFromKey('{key}')]"])
                            self.assertEqual(label.props['alwaystransparent'], 'no')
                            self.assertNotIn('tooltip', label.props)
                            pushed = eng.push(label)
                            try:
                                self.assertEqual(eng.ev.item_stack[-1]['__type__'], 'Estate')
                                self.assertEqual(eng.ev.item_stack[-1]['Estate.GetType'], key)
                            finally:
                                eng.pop(pushed)
                            tip = eng.ex.build_lazy(label.tooltipwidget)
                            self.assertTrue(any(e.props.get('text') == '[Estate.GetLongNameWithNoTooltip]' for e in walk(tip)))
                        self.assertFalse(eng.unresolved_contexts, eng.unresolved_contexts)
                        self.assertFalse(log, log)

    def test_unowned_locations_hide_sol_button_in_all_windows(self):
        import sync_location_window
        import generate_sol_location_window
        import gen_sol_mnt_compat
        for target, generator in (('stable', sync_location_window),
                                  ('sol_standalone', generate_sol_location_window),
                                  ('sol_mnt_compatibility_submod', gen_sol_mnt_compat)):
            with self.subTest(target=target):
                path = ROOT / 'src' / target / 'in_game/gui/location_window.gui'
                self.assertIn(generator.SOL_BUTTON, path.read_text(encoding='utf-8-sig'))
                node = parse(generator.SOL_BUTTON)[0]
                for has_owner in (False, True):
                    eng, log = self.engine([(r'Location.HasOwner', has_owner)])
                    button = eng.ex.build(node.key, node.value, {}, str(path), node.line)
                    self.assertEqual(eng.visible(button), has_owner)
                    self.assertFalse(log, log)

    def test_linear_capacity_bar_and_cursor(self):
        from gen_sol_ls_gui import balance_cursor, capacity_bar, f_capacity_components, f_coef
        for position in (0, .166667, .333333, .5, .666667, .833333, 1):
            eng, log = self.engine([])
            expr = f"'(CFixedPoint){position}'"
            source = '\n'.join(balance_cursor(0, 220, expr))
            node = parse(source)[0]
            element = eng.ex.build(node.key, node.value, {}, '<balance cursor>', 0)
            eng.measure(element, None)
            eng.place(element, 0, 0, 220, 14)
            marker = next(c for c in element.children if c.backgrounds)
            share = max(0, min(1, position))
            self.assertAlmostEqual(marker.x, share * 218, delta=.1)
            source = '\n'.join(capacity_bar(0, 220, expr, expr, expr))
            node = parse(source)[0]
            bar = eng.ex.build(node.key, node.value, {}, '<bidirectional bar>', 0)
            progresses = [c for c in walk(bar) if c.kind == 'progressbar']
            values = [float(eng.resolve(c.props['value'])) for c in progresses]
            self.assertEqual(values, [min(1, max(0, position)), min(1, max(0, position))])
            self.assertEqual(progresses[0].props['max'], '1')
            self.assertFalse(log, log)
        # The signed bar maps ratio q=funds/baseline linearly within each half:
        # q=0 -> -100%, q=1 -> 0%, q=3 -> +200%.
        eng, log = self.engine([
            (r"Test.ScriptValue\('funds'\)", 0), (r"Test.ScriptValue\('need'\)", 1),
        ])
        negative, positive, position = f_capacity_components('Test', 'funds', 'need')
        self.assertEqual(eng.resolve(f"[{negative}]"), 1)
        self.assertEqual(eng.resolve(f"[{positive}]"), 0)
        self.assertEqual(eng.resolve(f"[{position}]"), 0)
        self.assertFalse(log, log)
        for funds, expected_negative, expected_positive, expected_position in (
            (.25, .75, 0, .125), (.5, .5, 0, .25), (.75, .25, 0, .375),
            (1, 0, 0, .5), (1.5, 0, .25, .625), (2, 0, .5, .75), (2.5, 0, .75, .875),
            (3, 0, 1, 1), (6, 0, 1, 1),
        ):
            eng, log = self.engine([
                (r"Test.ScriptValue\('funds'\)", funds), (r"Test.ScriptValue\('need'\)", 1),
            ])
            negative, positive, position = f_capacity_components('Test', 'funds', 'need')
            self.assertAlmostEqual(eng.resolve(f"[{negative}]"), expected_negative)
            self.assertAlmostEqual(eng.resolve(f"[{positive}]"), expected_positive)
            self.assertAlmostEqual(eng.resolve(f"[{position}]"), expected_position)
            self.assertFalse(log, log)
        # Raw alpha is neutral for a baseline-free estate.
        for funds in (0, 5):
            eng, log = self.engine([(r"Test.ScriptValue\('funds'\)", funds), (r"Test.ScriptValue\('need'\)", 0)])
            self.assertEqual(eng.resolve(f"[{f_coef('Test', 'funds', 'need')}]"), 0)
            negative, positive, position = f_capacity_components('Test', 'funds', 'need')
            self.assertEqual(eng.resolve(f"[{negative}]"), 0)
            self.assertEqual(eng.resolve(f"[{positive}]"), 0)
            self.assertEqual(eng.resolve(f"[{position}]"), .5)
            self.assertFalse(log, log)

    def test_goods_tooltip_preserves_vanilla_and_packages_both_targets(self):
        vanilla = VANILLA_GUI.read_text(encoding='utf-8-sig')
        market = VANILLA_MARKET_GUI.read_text(encoding='utf-8-sig')
        for target in ('stable', 'sol_standalone'):
            with self.subTest(target=target):
                base = ROOT / 'src' / target
                self.assertEqual((base / 'main_menu/gui/shared/goods_details.gui').read_text(encoding='utf-8'),
                                 inject(vanilla) + price_template())
                self.assertEqual((base / 'in_game/gui/shared/market_tooltips.gui').read_text(encoding='utf-8'),
                                 inject_market(market) + price_template(market=True))
                # A generic tooltip must be usable without any market/country data.
                source = (base / 'main_menu/gui/shared/goods_details.gui').read_text(encoding='utf-8')
                for scope in ('Market.', 'Player.', 'Location.'):
                    self.assertNotIn(scope, source)

    def test_goods_tooltip_all_memberships_and_unknown_good(self):
        from sol_goods_order import GROUP_MEMBERS
        for language in ('simp_chinese', 'english'):
            for good in CORE + ['iron', 'third_party_good']:
                with self.subTest(language=language, good=good):
                    eng, log = self.goods_engine(good, language=language)
                    node = parse('vbox = { using = goods_details }')[0]
                    root = eng.ex.build(node.key, node.value, {}, '<goods details>', 0)
                    width, height = eng.measure(root, None)['hint']
                    eng.place(root, 0, 0, width, height)
                    elements = list(visible_walk(eng, root))
                    groups = [e.props['text'].removeprefix('SOL_GOOD_GROUP_') for e in elements
                              if str(e.props.get('text', '')).startswith('SOL_GOOD_GROUP_')]
                    expected = [group for group, members in GROUP_MEMBERS.items() if good in members]
                    self.assertCountEqual(groups, expected)
                    chips = [e.props['raw_text'][1:].split('!', 1)[0] for e in elements
                             if str(e.props.get('raw_text', '')).startswith('@')]
                    self.assertCountEqual(chips, [g for group in expected for g in GROUP_MEMBERS[group]])
                    texts = [eng.text_of(e) for e in elements if e.kind == 'textbox']
                    if not expected:
                        self.assertNotIn(eng.loc.get('SOL_GOOD_SUB_NONE'), texts)
                        self.assertNotIn(eng.loc.get('SOL_GOOD_SUBSTITUTES_HEADER'), texts)
                        self.assertNotIn(eng.loc.get('SOL_GOOD_PRICE_TIERS'), texts)
                    for element in elements:
                        if element.w > 0:
                            self.assertLessEqual(element.x + element.w, width + 1, element.typename)
                    self.assertLessEqual(width, 422)
                    self.assertFalse(log, log)

    def test_ungrouped_goods_hide_entire_substitution_section(self):
        for language in ('simp_chinese', 'english'):
            for good in ('iron', 'third_party_good', 'default', ''):
                for template in ('Goods_tooltip', 'Goods_Cards_tooltip', 'SpecificGoodsMarket_tooltip'):
                    with self.subTest(language=language, good=good, template=template):
                        market = template == 'SpecificGoodsMarket_tooltip'
                        eng, log = self.goods_engine(good, 1.42 if market else None, language)
                        if good != 'iron':
                            # Unknown/default keys have no generated membership
                            # localization. Their section must still disappear.
                            self.assertIsNone(eng.loc.get('SOL_GOOD_SUB_' + good))
                        node = next(n for n in self.db.templates[template] if n.is_block())
                        root = eng.ex.build(node.key, node.value, {}, '<ungrouped goods tooltip>', 0)
                        width, height = eng.measure(root, None)['hint']
                        eng.place(root, 0, 0, width, height)
                        elements = list(visible_walk(eng, root))
                        self.assertFalse(any(e.typename == 'divider_center_gold' for e in elements))
                        for element in elements:
                            self.assertNotIn('SOL_GOOD_', str(element.props.get('text', '')))
                            self.assertNotIn('SOL_GOOD_', str(element.props.get('raw_text', '')))
                        self.assertTrue(any(e.typename == 'TooltipStatsBar' for e in elements))
                        self.assertFalse(log, log)
                        if self.out and good == 'iron':
                            image = Image.new('RGBA', (int(width + 40), int(height + 40)), (40, 52, 46, 255))
                            eng.place(root, 20, 20, width, height)
                            eng.render(root, image)
                            image.save(self.out / f'ungrouped_{template}_{language}.png')

    def test_market_goods_tooltip_price_ratio_and_bilingual_bounds(self):
        for language in ('simp_chinese', 'english'):
            for template in ('Goods_tooltip', 'Goods_Cards_tooltip', 'SpecificGoodsMarket_tooltip'):
                with self.subTest(language=language, template=template):
                    market = template == 'SpecificGoodsMarket_tooltip'
                    eng, log = self.goods_engine('wine', 1.42 if market else None, language)
                    node = next(n for n in self.db.templates[template] if n.is_block())
                    root = eng.ex.build(node.key, node.value, {}, '<goods tooltip>', 0)
                    width, height = eng.measure(root, None)['hint']
                    eng.place(root, 0, 0, width, height)
                    texts = [eng.text_of(e) or '' for e in visible_walk(eng, root) if e.kind == 'textbox']
                    self.assertEqual(sum('1.42' in text for text in texts), int(market))
                    highlights = [e.props['name'] for e in visible_walk(eng, root)
                                  if str(e.props.get('name', '')).startswith('sol_price_tier_active_')]
                    self.assertEqual(highlights, ['sol_price_tier_active_4'] if market else [])
                    if market:
                        ratio_line = next(e for e in visible_walk(eng, root)
                                          if 'SOL_GOOD_MARKET_RATIO_PREFIX' in str(e.props.get('raw_text', '')))
                        self.assertGreaterEqual(ratio_line.w, 400)
                        self.assertLessEqual(ratio_line.h, 50)
                    weights = [text for text in texts if '×' in text]
                    self.assertEqual(len(weights), 7)
                    self.assertLessEqual(width, 444)
                    self.assertLessEqual(height, 1080)
                    self.assertFalse(log, log)
                    self.assertFalse(eng.unresolved_contexts, eng.unresolved_contexts)
                    if self.out:
                        image = Image.new('RGBA', (int(width + 40), int(height + 40)), (40, 52, 46, 255))
                        eng.place(root, 20, 20, width, height)
                        eng.render(root, image)
                        image.save(self.out / f'goods_{template}_{language}.png')
        # Zero-base-price and invalid-market goods must never fabricate a ratio.
        for mock in ((r'Goods.GetDefaultMarketPrice', 0), (r'Market.IsValid', False)):
            eng, log = self.goods_engine('wine', 1.42, overrides=[mock])
            node = next(n for n in self.db.templates['SpecificGoodsMarket_tooltip'] if n.is_block())
            root = eng.ex.build(node.key, node.value, {}, '<invalid market tooltip>', 0)
            eng.measure(root, None)
            texts = [eng.text_of(e) or '' for e in visible_walk(eng, root) if e.kind == 'textbox']
            self.assertFalse(any('1.42' in text for text in texts))
            self.assertFalse(any(str(e.props.get('name', '')).startswith('sol_price_tier_active_')
                                 for e in visible_walk(eng, root)))
            self.assertFalse(log, log)

    def test_current_price_tier_highlight_boundaries_and_pixels(self):
        from sol_substitution import price_weight
        ratios = [.2, .5, .75, 1, 1.42, 2, 3]
        for boundary in (.4, .65, .85, 1.3, 1.7, 2.3):
            ratios += [boundary - .0001, boundary, boundary + .0001]
        for ratio in ratios:
            with self.subTest(ratio=ratio):
                eng, log = self.goods_engine('wine', ratio)
                node = parse('vbox = { using = SOL_goods_market_price_tiers }')[0]
                root = eng.ex.build(node.key, node.value, {}, '<current price tier>', 0)
                width, height = eng.measure(root, None)['hint']
                eng.place(root, 0, 0, width, height)
                active = [e for e in visible_walk(eng, root)
                          if str(e.props.get('name', '')).startswith('sol_price_tier_active_')]
                expected = next(i for i, tier in enumerate(PRICE_TIERS) if float(tier[0]) == price_weight(ratio))
                self.assertEqual([e.props['name'] for e in active], [f'sol_price_tier_active_{expected}'])
                self.assertEqual((active[0].w, active[0].h), (58, 40))
                self.assertFalse(log, log)
        # Verify that selecting a tier really changes its pixels, while the
        # unselected columns retain the generic legend's appearance.
        images = []
        for market in (False, True):
            eng, log = self.goods_engine('wine', 1.42 if market else None)
            template = 'SOL_goods_market_price_tiers' if market else 'SOL_goods_price_tiers'
            node = parse(f'vbox = {{ using = {template} }}')[0]
            root = eng.ex.build(node.key, node.value, {}, '<price tier pixels>', 0)
            width, height = eng.measure(root, None)['hint']
            eng.place(root, 0, 0, width, height)
            image = Image.new('RGBA', (int(width), int(height)), (20, 20, 20, 255))
            eng.render(root, image)
            row = next(e for e in visible_walk(eng, root) if e.kind == 'hbox')
            images.append((image, row.children))
            self.assertFalse(log, log)
        plain, columns = images[0]
        selected = images[1][0]
        for index, column in enumerate(columns):
            rect = (int(column.x), int(column.y), int(column.x + column.w), int(column.y + column.h))
            self.assertEqual(plain.crop(rect).tobytes() == selected.crop(rect).tobytes(), index != 4)

    def test_goods_price_legend_intervals_match_runtime(self):
        from sol_substitution import price_weight
        comparisons = {'<': operator.lt, '<=': operator.le, '>': operator.gt}
        for threshold in (.4, .65, .85, 1.3, 1.7, 2.3):
            for ratio in (threshold - .0001, threshold, threshold + .0001):
                matches = []
                for weight, _, interval, _ in PRICE_TIERS:
                    tokens = interval.split()
                    values = [ratio if token == 'r' else float(token) for token in tokens[::2]]
                    if all(comparisons[op](left, right) for op, left, right
                           in zip(tokens[1::2], values, values[1:])):
                        matches.append(float(weight))
                self.assertEqual(matches, [price_weight(ratio)], ratio)

    def test_group_card_bounds_and_labels(self):
        for language in ('simp_chinese', 'english'):
            eng, log = self.engine(scenarios.tooltip(), language)
            source = render_goods_vbox(CORE + ['victuals'], 'sol_market_consumes', 'Location.GetMarket.MakeScope', '')
            node = parse(source)[0]
            root = eng.ex.build(node.key, node.value, {}, '<goods>', 0)
            width, height = eng.measure(root, GOODS_CONTENT_W)['hint']
            eng.place(root, 0, 0, GOODS_CONTENT_W, height)
            labels = [e for e in walk(root) if str(e.props.get('text', '')).startswith('SOL_SUBGROUP_')]
            self.assertEqual(len(labels), 21)
            for label in labels:
                self.assertGreaterEqual(label.w, 84)
                self.assertTrue(eng.text_of(label))
            cards = [e for e in walk(root) if any(str(c.props.get('text', '')).startswith('SOL_SUBGROUP_') for c in walk(e)) and e.kind == 'vbox' and e is not root]
            for card in cards:
                self.assertAlmostEqual(card.w, LOCATION_CARD_W)
                self.assertAlmostEqual(card.h, GROUP_CARD_H)
                cells = [c for c in walk(card) if str(c.props.get('tooltip', '')).startswith('@')]
                self.assertLessEqual(len(cells), 6)
                self.assertEqual(len({round(c.y, 1) for c in cells}), 1)
                for child in walk(card):
                    if child.w > 0 and eng.visible(child):
                        self.assertLessEqual(child.x + child.w, card.x + card.w + 1)
                        self.assertLessEqual(child.y + child.h, card.y + card.h + 1)
            self.assertFalse(log, log)


if __name__ == '__main__':
    unittest.main()

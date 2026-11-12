import sys
import shutil
import tempfile
import unittest
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import gen_sol_jtg_compat as g

class JtgAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        source = g.REPO_ROOT / '.eu5-base/reference_mods' / g.JUST_GOODS_WORKSHOP_ID
        target = self.root / g.JUST_GOODS_WORKSHOP_ID
        shutil.copytree(source / '.metadata', target / '.metadata')
        shutil.copytree(source / 'in_game/common/goods', target / 'in_game/common/goods')
        self.goods = self.root / g.JUST_GOODS_WORKSHOP_ID / 'in_game/common/goods'
        self.rows = g._load_rows()
    def tearDown(self):
        self.temp.cleanup()
    def test_current_source(self):
        g._audit_workshop(self.root, self.rows)
        self.assertEqual(len(self.rows), 30)
        self.assertEqual(g.EXPECTED_GUI_GOODS_COUNT, 86)
    def reject(self, text):
        (self.goods / 'unexpected.txt').write_text(text, encoding='utf-8')
        with self.assertRaises(ValueError):
            g._audit_workshop(self.root, self.rows)
    def test_unknown(self):
        self.reject('unknown_goods = { default_market_price = 2 }')
    def test_duplicate_across_files(self):
        self.reject('jade = { default_market_price = 3 }')
    def test_duplicate_same_file(self):
        (self.goods / 'unexpected.txt').write_text('jade = {}\njade = {}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Duplicate Workshop definition within'):
            g._audit_workshop(self.root, self.rows)
    def test_missing(self):
        (self.goods / 'just_stone_goods.txt').unlink()
        with self.assertRaises(ValueError):
            g._audit_workshop(self.root, self.rows)
    def test_excluded_becomes_consumer(self):
        p = self.goods / 'just_stone_goods.txt'
        p.write_text(p.read_text().replace('limestone = {', 'limestone = {\n demand_add = { nobles = 0.1 }'), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'unexpectedly has pop demand'):
            g._audit_workshop(self.root, self.rows)
    def test_lazaretto(self):
        text = g._render_lazaretto()
        source = g.STABLE_ROOT / 'in_game/common/building_types/SOL_living_standard_buildings.txt'
        block = g._find_named_block_in_text(g._read(source), 'lazaretto', str(source))
        hook = g.re.search(r'local_sol_living_standard\s*=\s*(-?[\d.]+)', block).group(1)
        self.assertEqual(text.count('local_sol_living_standard = ' + hook), 1)
        self.assertIn('lime = 0.10', text)

if __name__ == '__main__':
    unittest.main()

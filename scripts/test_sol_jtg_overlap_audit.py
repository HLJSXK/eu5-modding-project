"""Independent source-preservation checks for the JTG 1.1 compatibility update."""
import re
import sys
import unittest
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import gen_sol_jtg_compat as generator

ROOT = Path(__file__).resolve().parents[1]
JTG = ROOT / ".eu5-base/reference_mods/3785316314"


class OverlapAudit(unittest.TestCase):
    def test_final_output_and_authoritative_hook(self):
        self.assertGreater(generator.LAZARETTO_OUTPUT.name, generator.LAZARETTO_SOURCE.name)
        output = generator.LAZARETTO_OUTPUT.read_text(encoding="utf-8-sig")
        stable = (ROOT / "src/stable/in_game/common/building_types/SOL_living_standard_buildings.txt").read_text(encoding="utf-8-sig")
        hook = generator._find_named_block_in_text(stable, "lazaretto", "stable")
        value = re.search(r"local_sol_living_standard\s*=\s*([\d.]+)", hook)[1]
        self.assertEqual(re.findall(r"local_sol_living_standard\s*=\s*([\d.]+)", output), [value])
        self.assertEqual(output, generator._render_lazaretto())

    def test_lazaretto_preserves_every_upstream_token(self):
        source = JTG / "in_game/common/building_types/zzzzzz_just_stone_building_injections.txt"
        original = generator._find_named_block_in_text(source.read_text(encoding="utf-8-sig"), "lazaretto", str(source))
        rendered = generator._render_lazaretto()
        actual = generator._find_named_block_in_text(rendered, "lazaretto", "generated")
        self.assertEqual(actual.count("local_sol_living_standard"), 1)
        stripped = re.sub(r"local_sol_living_standard\s*=\s*0\.03", "", actual)
        self.assertEqual(re.findall(r"\S+", original), re.findall(r"\S+", stripped))

    def test_cloves_duplicate_scalar_prices_agree(self):
        prices = []
        for path in (JTG / "in_game/common/goods").glob("*.txt"):
            text = path.read_text(encoding="utf-8-sig")
            for match in re.finditer(r"INJECT:cloves\s*=\s*\{([^}]+)\}", text):
                prices.append(float(re.search(r"default_market_price\s*=\s*([\d.]+)", match[1])[1]))
        self.assertEqual(prices, [6.0, 6.0])


if __name__ == "__main__":
    unittest.main()

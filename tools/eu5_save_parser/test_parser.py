"""Small structural tests for the targeted parser."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from .parser import decode_jomini_fixed_point, export_analysis, parse_save


SYNTHETIC_SAVE = """SAV02000000000000000000000000000
metadata={
\tdate=1337.6.2.16
\tversion="1.3.11"
\tcompatibility={
\t\tlocations={alpha beta}
\t}
}
countries={
\ttags={
\t\t0=DUMMY
\t\t1=HUN
\t}
\tdatabase={
1={
\tcountry_name="Hungary"
\tvariables={
\t\tdata={ {
\t\t\t\tflag=sol_country_class_coefficient_4
\t\t\t\tdata={
\t\t\t\t\ttype=value
\t\t\t\t\tidentity=125000
\t\t\t\t}
\t\t\t} }
\t}
}
\t}
}
population={
\tdatabase={
0={
\ttype=nobles
\testate=nobles_estate
\tculture=10
\treligion=20
\tsize=1.25
}
1={
\ttype=peasants
\testate=peasants_estate
\tculture=10
\treligion=20
\tsize=8.75
}
2={
\ttype=slaves
\testate=dhimmi_estate
\tculture=11
\treligion=21
}
\t}
}
provinces={
}
locations={
\tlocations={
\t\t1={
\t\t\towner=1
\t\t\tcontroller=1
\t\t\tmarket=7
\t\t\tprovince=0
\t\t\trank=town
\t\t\traw_material=clay
\t\t\tdevelopment=20
\t\t\tcontrol=1
\t\t\tpopulation={
\t\t\t\tpops={ 0 1 }
\t\t\t}
\t\t\tvariables={
\t\t\t\tdata={ {
\t\t\t\t\t\tflag=sol_location_demand_class
\t\t\t\t\t\tdata={
\t\t\t\t\t\t\ttype=value
\t\t\t\t\t\t\tidentity=400000
\t\t\t\t\t\t}
\t\t\t\t\t} {
\t\t\t\t\t\tflag=sol_location_demand_score_nobles
\t\t\t\t\t\tdata={
\t\t\t\t\t\t\ttype=value
\t\t\t\t\t\t\tidentity=18446744073709476616
\t\t\t\t\t\t}
\t\t\t\t\t} }
\t\t\t}
\t\t}
\t\t2={
\t\t\trank=rural_settlement
\t\t}
\t}
}
armies={
}
"""


class ParserTests(unittest.TestCase):
    def test_fixed_point_signed_value(self) -> None:
        self.assertEqual(decode_jomini_fixed_point(400000), 4.0)
        self.assertEqual(
            decode_jomini_fixed_point(18446744073709476616), -0.75
        )

    def test_parse_and_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            save_path = root / "fixture.eu5"
            save_path.write_text(SYNTHETIC_SAVE, encoding="utf-8")

            parsed = parse_save(save_path)
            self.assertEqual(parsed.country_tags[1], "HUN")
            self.assertEqual(
                parsed.country_variables[1]["sol_country_class_coefficient_4"],
                1.25,
            )
            self.assertEqual(parsed.location_names[1], "alpha")
            self.assertEqual(parsed.populations[1].size, 8.75)
            self.assertEqual(parsed.populations[2].size, 0.0)
            self.assertEqual(parsed.locations[0].pop_ids, (0, 1))
            self.assertEqual(
                parsed.locations[0].sol_variables[
                    "sol_location_demand_score_nobles"
                ],
                -0.75,
            )

            output = root / "analysis"
            paths = export_analysis(
                parsed, output, country_tags=["HUN"], emit_populations=True
            )
            self.assertEqual(len(paths), 4)
            locations_csv = (output / "locations.csv").read_text(
                encoding="utf-8"
            )
            self.assertIn("population_total", locations_csv)
            self.assertIn("alpha", locations_csv)
            self.assertIn(",lower,", locations_csv)
            countries_csv = (output / "countries.csv").read_text(
                encoding="utf-8"
            )
            self.assertIn("sol_country_class_coefficient_4", countries_csv)
            self.assertIn("1.25000", countries_csv)


if __name__ == "__main__":
    unittest.main()

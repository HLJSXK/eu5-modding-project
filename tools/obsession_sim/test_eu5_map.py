"""Deterministic miniature EU5 fixtures; no installed game required.

Run: python -m unittest tools.obsession_sim.test_eu5_map
"""
from pathlib import Path
import csv
import tempfile
import unittest

from PIL import Image

from .eu5_map import import_eu5
from .graph import load_json, save_json


class RealMapImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "game"
        self.map = self.root / "in_game/map_data"
        (self.map / "named_locations").mkdir(parents=True)
        setup = self.root / "main_menu/setup/1337"
        setup.mkdir(parents=True)
        (self.map / "default.map").write_text('''provinces="locations.png"
setup="definitions.txt"
location_templates="location_templates.txt"
adjacencies="adjacencies.csv"
wrap_x=no
sea_zones={sea}
lakes={lake}
impassable_mountains={mountain}
non_ownable={corridor}
''')
        (self.map / "named_locations/00_default.txt").write_text('''# short RGB hex is legal
a=1 b=2 c=3 d=4 island=5 mountain=6 lake=7 sea=8 corridor=9
''')
        (self.map / "definitions.txt").write_text('''continent={subcontinent={region={area={province={a b c d island sea lake mountain corridor}}}}}''')
        (self.map / "location_templates.txt").write_text('''a={raw_material=tea culture=alpha topography=flatland}
b={raw_material=wheat culture=beta topography=hills}
c={raw_material=fish} d={raw_material=clay} island={raw_material=fish}
''')
        (setup / "10_countries.txt").write_text('''countries={countries={
AAA={own_control_core={a c} control_core={b}}
BBB={own_core={b} own_control_colony={d}}
}}''')
        (self.map / "adjacencies.csv").write_text('''From;To;Type;Through;Comment
a;b;sea;sea;strait
sea;lake;canal;a;ignored water route
''')
        self.pixels = [[1,1,8,2,2,8,5,8], [1,6,8,2,2,8,8,8], [3,3,7,4,4,8,8,9]]
        self.write_image(self.pixels)

    def tearDown(self):
        self.temp.cleanup()

    def write_image(self, rows):
        image = Image.new("RGB", (len(rows[0]), len(rows)))
        image.putdata([(0, 0, value) for row in rows for value in row])
        image.save(self.map / "locations.png")

    def neighbors(self, graph, name):
        return {graph.names[i] for i in graph.outgoing[graph.names.index(name)]}

    def test_full_resolution_land_topology_attributes_and_geometry(self):
        graph = import_eu5(self.root, raster_width=8)
        self.assertEqual([], graph.validate())
        self.assertEqual(["a", "b", "c", "d", "island"], graph.names)
        self.assertEqual({"c"}, self.neighbors(graph, "a"))
        self.assertEqual({"d"}, self.neighbors(graph, "b"))
        self.assertEqual(set(), self.neighbors(graph, "island"))
        self.assertEqual(["AAA", "BBB", "AAA", "BBB", None], graph.attrs["owner_tag"])
        self.assertEqual([0, 1, 0, 1, -1], graph.owner)
        self.assertEqual(["region"] * 5, graph.attrs["region"])
        self.assertEqual("tea", graph.attrs["raw_material"][0])
        self.assertEqual((1/3, 1/3), graph.coords[0])
        geometry = graph.meta["geometry"]
        self.assertEqual([0, 0, 8, 3], geometry["bounds"])
        decoded = [[value for value, count in row for _ in range(count)] for row in geometry["rows"]]
        self.assertEqual([0, 0, -1, 1, 1, -1, 4, -1], decoded[0])
        tiny = import_eu5(self.map, raster_width=1)
        self.assertEqual(graph.incoming, tiny.incoming)
        self.assertNotIn("geometry", import_eu5(self.root.parent, raster_width=0).meta)

    def test_optional_straits_and_round_trip(self):
        graph = import_eu5(self.root, include_straits=True, raster_width=8)
        self.assertEqual({"b", "c"}, self.neighbors(graph, "a"))
        self.assertEqual([{"a": 0, "b": 1, "type": "strait", "through": "sea"}], graph.meta["special_edges"])
        path = Path(self.temp.name) / "graph.json"
        save_json(graph, path)
        restored = load_json(path)
        self.assertEqual([], restored.validate())
        self.assertEqual(graph.incoming, restored.incoming)
        self.assertEqual(graph.meta["geometry"], restored.meta["geometry"])

    def test_save_overlay_joins_names_and_clears_owner(self):
        path = Path(self.temp.name) / "locations.csv"
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerows([["location_id", "location", "owner_tag", "market_id", "population_total"],
                              ["901", "a", "CCC", "12", "18.5"],
                              ["902", "b", "", "14", "2"],
                              ["903", "not_a_land_node", "DDD", "15", "2"]])
        with self.assertRaisesRegex(ValueError, "covers 2 of 5.*3 missing"):
            import_eu5(self.root, locations_csv=path, raster_width=0)
        graph = import_eu5(self.root, locations_csv=path, raster_width=0, allow_partial_csv=True)
        self.assertEqual(["CCC", None, "AAA", "BBB", None], graph.attrs["owner_tag"])
        self.assertEqual([12, 14, None, None, None], graph.attrs["market_id"])
        self.assertEqual(18.5, graph.attrs["population_total"][0])
        self.assertEqual(901, graph.attrs["location_id"][0])
        self.assertEqual(2, graph.meta["save_overlay"]["matched"])
        self.assertEqual(1, graph.meta["save_overlay"]["unmatched"])
        self.assertTrue(graph.meta["save_overlay"]["partial_overlay"])
        self.assertIsNone(graph.meta["source_date"])

    def test_unknown_colors_do_not_bridge_and_full_snapshot_needs_no_opt_in(self):
        self.write_image([[1, 10, 2, 8, 5], [3, 7, 4, 6, 9]])
        graph = import_eu5(self.root, raster_width=5)
        self.assertEqual({"c"}, self.neighbors(graph, "a"))
        self.assertEqual({"d"}, self.neighbors(graph, "b"))
        self.assertEqual(-1, graph.meta["geometry"]["rows"][0][1][0])
        path = Path(self.temp.name) / "full.csv"
        path.write_text("location,owner_tag\na,NEW\nb,NEW\nc,\nd,\nisland,NEW\n")
        graph = import_eu5(self.root, locations_csv=path, raster_width=0)
        self.assertEqual(["NEW", "NEW", None, None, "NEW"], graph.attrs["owner_tag"])
        self.assertFalse(graph.meta["save_overlay"]["partial_overlay"])

    def test_dates_come_from_bound_bookmark_or_parser_metadata(self):
        graph = import_eu5(self.root, raster_width=0)
        self.assertIsNone(graph.meta["source_date"])
        self.assertEqual(1337, graph.meta["source_year"])
        bookmarks = self.root / "main_menu/common/bookmarks"
        bookmarks.mkdir(parents=True)
        (bookmarks / "00_bookmarks.txt").write_text('bookmark_1337={start_date=1337.4.1 setup_folder="setup/1337"}')
        graph = import_eu5(self.root, raster_width=0)
        self.assertEqual("1337.4.1", graph.meta["source_date"])
        path = Path(self.temp.name) / "full.csv"
        path.write_text("location,owner_tag\na,NEW\nb,NEW\nc,\nd,\nisland,NEW\n")
        (path.parent / "metadata.json").write_text('{"metadata":{"date":"1452.8.14"}}')
        graph = import_eu5(self.root, locations_csv=path, raster_width=0)
        self.assertEqual("1452.8.14", graph.meta["source_date"])
        self.assertEqual(1452, graph.meta["source_year"])

    def test_wrap_and_tile_boundary(self):
        defaults = self.map / "default.map"
        defaults.write_text(defaults.read_text().replace("wrap_x=no", "wrap_x=yes"))
        # No physical a/b contact except across the horizontal map seam.
        self.write_image([[1, 3, 8, 2], [6, 7, 9, 4], [5, 8, 8, 8]])
        graph = import_eu5(self.root, raster_width=0)
        self.assertIn("b", self.neighbors(graph, "a"))
        defaults.write_text(defaults.read_text().replace("wrap_x=yes", "wrap_x=no"))
        rows = [[1, 8, 5, 8, 3, 8, 4] for _ in range(64)] + [[2, 8, 5, 8, 3, 8, 4]]
        self.write_image(rows)
        graph = import_eu5(self.root, raster_width=0)
        self.assertEqual({"b"}, self.neighbors(graph, "a"))

    def test_missing_pixels_are_reported_and_bad_csv_fails_actionably(self):
        self.write_image([[1, 2, 3, 4]])
        graph = import_eu5(self.root)
        self.assertEqual(["island"], graph.meta["absent_named_locations"])
        self.assertNotIn("island", graph.names)
        self.assertEqual([], graph.validate())
        self.assertEqual({"b"}, self.neighbors(graph, "a"))
        self.write_image(self.pixels)
        path = Path(self.temp.name) / "bad.csv"
        path.write_text("location_id,owner_tag\n0,AAA\n")
        with self.assertRaisesRegex(ValueError, "location and owner_tag"):
            import_eu5(self.root, locations_csv=path, raster_width=0)
        for bad in (-1, 2.5, True):
            with self.assertRaises(ValueError):
                import_eu5(self.root, raster_width=bad)


if __name__ == "__main__":
    unittest.main()

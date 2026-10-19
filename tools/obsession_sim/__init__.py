"""Offline simulator for the SOL obsession (痴迷) diffusion model.

See README.md. Python reference implementation of the current plan: one
float x per location x good, option-A transient queue pointer, delta = 0.1,
country-clock decay (T = 240). MapGraph accepts synthetic grids, JSON/CSV, or
full-resolution real EU5 geography extracted by eu5_map.import_eu5.
"""

from .core import Params, Simulation, simulate, PRICE_QUEUE, PRICE_CLOCK
from .graph import MapGraph, from_adjacency, hex_grid, voronoi_groups, hops_from, load_json, save_json, load_csv, from_spec
from .metrics import milestones, front_profile, front_speed, group_arrival
from .export import export_playback, playback_payload, export_html
from .presets import PRESETS, make_params

__all__ = ["Params", "Simulation", "simulate", "PRICE_QUEUE", "PRICE_CLOCK", "MapGraph", "from_adjacency", "hex_grid",
           "voronoi_groups", "hops_from", "load_json", "save_json", "load_csv", "from_spec", "milestones",
           "front_profile", "front_speed", "group_arrival", "export_playback", "playback_payload",
           "PRESETS", "make_params", "export_html"]

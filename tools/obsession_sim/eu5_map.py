"""Import locally installed EU5 map assets without redistributing game files.

Topology uses every horizontal/vertical pixel boundary, never a reduced image.
The optional raster is display-only. Coordinates use the PNG origin (top left).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import re
import warnings

from .graph import MapGraph

DEFAULT_GAME = Path("C:/Program Files (x86)/Steam/steamapps/common/Europa Universalis V/game")
_TOKEN = re.compile(r'#[^\n]*|"(?:\\.|[^"\\])*"|[{}=]|[^\s{}=#]+')


def _parse(path):
    """Small ordered Clausewitz reader retaining duplicate keys and bare lists."""
    tokens = [m.group() for m in _TOKEN.finditer(Path(path).read_text(encoding="utf-8-sig"))
              if not m.group().startswith("#")]
    cursor = 0

    def block(nested=False):
        nonlocal cursor
        result = []
        while cursor < len(tokens):
            token = tokens[cursor]
            cursor += 1
            if token == "}":
                if not nested:
                    raise ValueError(f"Unexpected closing brace in {path}")
                return result
            if token == "{":
                result.append(block(True))
            elif cursor < len(tokens) and tokens[cursor] == "=":
                cursor += 1
                value = tokens[cursor]
                cursor += 1
                result.append((token.strip('"'), block(True) if value == "{" else value.strip('"')))
            else:
                result.append(token.strip('"'))
        if nested:
            raise ValueError(f"Unclosed block in {path}")
        return result

    return block()


def _pairs(block):
    return (item for item in block if isinstance(item, tuple))


def _field(block, key, default=None):
    return next((v for k, v in _pairs(block) if k == key), default)


def _scalars(block):
    return {k: v for k, v in _pairs(block) if isinstance(v, str)}


def _game_root(path):
    path = Path(path) if path else DEFAULT_GAME
    for candidate in (path, path / "game", path.parent.parent):
        if (candidate / "in_game/map_data/default.map").is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"EU5 map_data/default.map not found beneath {path}; pass installation, game, or map_data directory")


def _rle(row):
    result = []
    for value in row:
        value = int(value)
        if result and result[-1][0] == value:
            result[-1][1] += 1
        else:
            result.append([value, 1])
    return result


def _setup_owners(path):
    if not path.exists():
        return {}
    root = _parse(path)
    countries = _field(_field(root, "countries", []), "countries", [])
    owners = {}
    for tag, data in _pairs(countries):
        if not isinstance(data, list):
            continue
        for key, values in _pairs(data):
            if key.startswith("own_") and isinstance(values, list):
                for name in values:
                    if isinstance(name, str):
                        if name in owners and owners[name] != tag:
                            raise ValueError(f"Conflicting 1337 owners for {name}: {owners[name]} and {tag}")
                        owners[name] = tag
    return owners


def _hierarchy(path):
    result = {}
    levels = ("continent", "subcontinent", "region", "area", "province")

    def walk(items, ancestry):
        for item in items:
            if isinstance(item, tuple) and isinstance(item[1], list):
                walk(item[1], ancestry + [item[0]])
            elif isinstance(item, str):
                result[item] = dict(zip(levels, ancestry))
    walk(_parse(path), [])
    return result


def _setup_date(root):
    """Use the bookmark explicitly bound to setup/1337, never a guessed day."""
    for path in sorted((root / "main_menu/common/bookmarks").glob("*.txt")):
        for _, data in _pairs(_parse(path)):
            if isinstance(data, list) and _field(data, "setup_folder") == "setup/1337":
                date = _field(data, "start_date")
                if isinstance(date, str) and re.fullmatch(r"1337\.\d{1,2}\.\d{1,2}", date):
                    return date, str(path.relative_to(root))
    return None, None


def _overlay_csv(path, names, columns, owner_tags, allow_partial):
    index = {name: i for i, name in enumerate(names)}
    seen = set()
    unmatched = 0
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not {"location", "owner_tag"}.issubset(reader.fieldnames or []):
            raise ValueError("locations.csv requires location and owner_tag columns from eu5_save_parser")
        for row in reader:
            name = row["location"]
            if name not in index:
                unmatched += 1
                continue
            if name in seen:
                raise ValueError(f"Duplicate location in locations.csv: {name}")
            seen.add(name)
            i = index[name]
            # The save is authoritative, including explicitly unowned rows.
            owner_tags[i] = row.get("owner_tag") or None
            for key, value in row.items():
                if key in ("location", "owner_tag") or value in (None, ""):
                    continue
                column = columns.setdefault(key, [None] * len(names))
                try:
                    column[i] = float(value) if "." in value or "e" in value.lower() else int(value)
                except ValueError:
                    column[i] = value
    missing = len(names) - len(seen)
    if missing and not allow_partial:
        raise ValueError(f"locations.csv covers {len(seen)} of {len(names)} map locations; {missing} missing. "
                         "A filtered save export would mix snapshot and 1337 owners. Export all locations "
                         "or explicitly set allow_partial_csv=True (--allow-partial-csv).")
    return {"matched": len(seen), "unmatched": unmatched, "unmatched_graph_nodes": missing,
            "partial_overlay": bool(missing)}


def import_eu5(game=None, *, locations_csv=None, include_straits=False, raster_width=2048, allow_partial_csv=False):
    """Build a land-location graph from a local EU5 installation.

    ``game`` accepts the installation root, its game directory, or map_data.
    Only ownable/passable land is simulated; water, impassable mountains, and
    non-ownable corridors stay outside the graph. Optional ``sea`` adjacencies
    add explicit straits. Canal rows connect water and are never used.
    ``locations_csv`` overlays matching names with actual save attributes.
    All land nodes must be covered unless ``allow_partial_csv`` is explicit;
    unmatched nodes then retain the documented 1337 setup and static data.
    Raster values are graph indices; -1 denotes excluded/background pixels.
    """
    import numpy as np
    from PIL import Image

    if isinstance(raster_width, bool) or not isinstance(raster_width, int) or raster_width < 0:
        raise ValueError("raster_width must be a nonnegative integer (0 disables geometry)")
    root = _game_root(game)
    directory = root / "in_game/map_data"
    defaults = _parse(directory / "default.map")
    definitions = directory / _field(defaults, "setup", "definitions.txt")
    templates_path = directory / _field(defaults, "location_templates", "location_templates.txt")
    templates = {k: _scalars(v) for k, v in _pairs(_parse(templates_path)) if isinstance(v, list)}
    excluded_sets = {key: set(_field(defaults, key, [])) for key in
                     ("sea_zones", "lakes", "impassable_mountains", "non_ownable")}
    excluded = set().union(*excluded_sets.values())
    colors = {}
    for path in sorted((directory / "named_locations").glob("*.txt")):
        for name, value in _pairs(_parse(path)):
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{1,6}", value):
                raise ValueError(f"Invalid RGB color for {name} in {path}: {value}")
            colors[name] = int(value, 16)
    if not colors:
        raise ValueError("No named location colors found")
    if len(set(colors.values())) != len(colors):
        raise ValueError("Duplicate named location RGB colors")
    names = [name for name in colors if name not in excluded]
    n = len(names)
    if not n:
        raise ValueError("Map has no eligible land locations")
    color_order = sorted((value, name) for name, value in colors.items())
    lookup_colors = np.array([c for c, _ in color_order], dtype=np.uint32)
    index = {name: i for i, name in enumerate(names)}
    lookup_nodes = np.array([index.get(name, -1) for _, name in color_order], dtype=np.int32)

    def node_pixels(rgb):
        rgb = np.asarray(rgb, dtype=np.uint32)
        packed = (rgb[..., 0] << 16) | (rgb[..., 1] << 8) | rgb[..., 2]
        positions = np.searchsorted(lookup_colors, packed)
        safe = np.minimum(positions, len(lookup_colors) - 1)
        return np.where((positions < len(lookup_colors)) & (lookup_colors[safe] == packed), lookup_nodes[safe], -1)

    # The shipped map legitimately exceeds Pillow's generic untrusted-image
    # threshold; keep that global safety limit unchanged for other callers.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        image = Image.open(directory / _field(defaults, "provinces", "locations.png"))
        image.load()
    width, height = image.size
    counts = np.zeros(n, dtype=np.int64)
    sum_x = np.zeros(n, dtype=np.float64)
    sum_y = np.zeros(n, dtype=np.float64)
    boundary_codes = set()
    prev = None
    wrap = _field(defaults, "wrap_x", "no") == "yes"

    def add_edges(a, b):
        mask = (a >= 0) & (b >= 0) & (a != b)
        aa, bb = a[mask].astype(np.int64), b[mask].astype(np.int64)
        if len(aa):
            codes = np.minimum(aa, bb) * n + np.maximum(aa, bb)
            boundary_codes.update(np.unique(codes).tolist())

    for top in range(0, height, 64):
        bottom = min(height, top + 64)
        pix = node_pixels(image.crop((0, top, width, bottom)).convert("RGB"))
        add_edges(pix[:, :-1], pix[:, 1:])
        add_edges(pix[:-1], pix[1:])
        if prev is not None:
            add_edges(prev, pix[0])
        if wrap:
            add_edges(pix[:, 0], pix[:, -1])
        prev = pix[-1].copy()
        yy, xx = np.nonzero(pix >= 0)
        ids = pix[yy, xx]
        counts += np.bincount(ids, minlength=n)
        sum_x += np.bincount(ids, weights=xx, minlength=n)
        sum_y += np.bincount(ids, weights=yy + top, minlength=n)

    absent = [names[i] for i in np.nonzero(counts == 0)[0]]
    if absent:
        # Vanilla contains obsolete names with no pixels. Do not invent
        # positions or leave ghost simulation nodes for those definitions.
        present = np.nonzero(counts > 0)[0]
        if not len(present):
            raise ValueError("No named land locations have map pixels")
        remap = np.full(n, -1, dtype=np.int32)
        remap[present] = np.arange(len(present))
        boundary_codes = {int(remap[a]) * len(present) + int(remap[b])
                          for a, b in (divmod(code, n) for code in boundary_codes)}
        lookup_nodes = np.array([remap[v] if v >= 0 else -1 for v in lookup_nodes], dtype=np.int32)
        names = [names[i] for i in present]
        counts, sum_x, sum_y = counts[present], sum_x[present], sum_y[present]
        n = len(names)
        index = {name: i for i, name in enumerate(names)}
    adjacency = [set() for _ in names]
    for code in boundary_codes:
        a, b = divmod(code, n)
        adjacency[a].add(b)
        adjacency[b].add(a)
    special_edges = []
    skipped_special = {}
    adjacency_path = directory / _field(defaults, "adjacencies", "adjacencies.csv")
    if adjacency_path.exists():
        with adjacency_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle, delimiter=";"):
                kind = row.get("Type", "").strip()
                a, b = index.get(row.get("From")), index.get(row.get("To"))
                if kind == "sea" and include_straits and a is not None and b is not None:
                    adjacency[a].add(b)
                    adjacency[b].add(a)
                    special_edges.append({"a": a, "b": b, "type": "strait", "through": row.get("Through", "")})
                else:
                    skipped_special[kind] = skipped_special.get(kind, 0) + 1
    setup_path = root / "main_menu/setup/1337/10_countries.txt"
    setup = _setup_owners(setup_path)
    owner_tags = [setup.get(name) for name in names]
    hierarchy = _hierarchy(definitions)
    all_keys = sorted(set().union(*(templates.get(name, {}).keys() for name in names)))
    columns = {key: [templates.get(name, {}).get(key) for name in names] for key in all_keys}
    for key in ("continent", "subcontinent", "region", "area", "province"):
        columns[key] = [hierarchy.get(name, {}).get(key) for name in names]
    columns["pixel_area"] = counts.tolist()
    source_date, date_source = _setup_date(root)
    meta = {"kind": "eu5_map", "source": str(root), "source_year": 1337,
            "source_date": source_date, "source_date_reference": date_source, "snapshot_label": "1337 setup",
            "owner_source": "1337 setup own_* lists" if setup_path.exists() else "unavailable",
            "topology": "full-resolution four-neighbor pixel boundaries",
            "map_width": width, "map_height": height, "wrap_x": wrap,
            "land_edges": len(boundary_codes), "include_straits": bool(include_straits),
            "special_edges": special_edges, "skipped_special_adjacencies": skipped_special,
            "excluded_counts": {k: len(v) for k, v in excluded_sets.items()},
            "absent_named_locations": absent,
            "attribute_sources": {"static": "location_templates.txt", "geography": "definitions.txt",
                                  "market": "save CSV only; no setup market catchments inferred"}}
    if locations_csv is not None:
        meta["save_overlay"] = dict(_overlay_csv(locations_csv, names, columns, owner_tags, allow_partial_csv),
                                    path=str(Path(locations_csv)))
        meta["owner_source"] = ("locations.csv matched rows + 1337 setup for missing locations"
                                if meta["save_overlay"]["partial_overlay"] else "locations.csv (complete land coverage)")
        meta["source_date"] = None  # CSV export alone does not declare its save date.
        meta["source_year"] = None
        meta["source_date_reference"] = None
        meta["snapshot_label"] = "save CSV" + (" + 1337 setup (partial overlay)" if meta["save_overlay"]["partial_overlay"] else "")
        manifest_path = Path(locations_csv).parent / "metadata.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            save_metadata = manifest.get("metadata", {}) if isinstance(manifest, dict) else {}
            save_date = save_metadata.get("date") if isinstance(save_metadata, dict) else None
            if isinstance(save_date, str) and re.fullmatch(r"\d{1,4}\.\d{1,2}\.\d{1,2}", save_date):
                meta["source_date"] = save_date
                meta["source_year"] = int(save_date.split(".")[0])
                meta["source_date_reference"] = str(manifest_path)
    columns["owner_tag"] = owner_tags
    group_names = sorted({tag for tag in owner_tags if tag})
    group_index = {tag: i for i, tag in enumerate(group_names)}
    owner = [group_index.get(tag, -1) for tag in owner_tags]
    coords = list(zip((sum_x / counts).tolist(), (sum_y / counts).tolist()))
    if raster_width:
        sw = min(raster_width, width)
        sh = max(1, round(height * sw / width))
        sampled = node_pixels(image.resize((sw, sh), resample=Image.Resampling.NEAREST).convert("RGB"))
        meta["geometry"] = {"type": "index-raster/1", "width": sw, "height": sh,
                            "bounds": [0, 0, width, height], "rows": [_rle(row) for row in sampled]}
        meta["geometry_note"] = "Nearest sampled display only; small islands may need centroid markers. Topology uses every source pixel."
    image.close()
    adjacency = [tuple(sorted(neighbors)) for neighbors in adjacency]
    return MapGraph(incoming=adjacency, outgoing=adjacency, owner=owner, group_names=group_names,
                    names=names, coords=coords, attrs=columns, meta=meta)

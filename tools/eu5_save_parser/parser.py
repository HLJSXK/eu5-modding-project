"""Parse the population data needed by SOL from an EU5 debug save.

This is deliberately not a general Clausewitz/Jomini deserializer.  A debug
save can be hundreds of megabytes, while SOL's location-class compensation
work needs only four relationships:

* metadata location order -> numeric location id;
* country id -> country tag and cached SOL solver variables;
* population id -> population type and size;
* location id -> owner, population ids, and cached SOL variables.

The parser memory-maps the save, locates top-level blocks with byte searches,
and applies compiled regular expressions only inside those blocks.  It never
builds a syntax tree for the complete save and never copies a full section.
"""

from __future__ import annotations

import csv
import json
import math
import mmap
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence


SAVE_HEADER = b"SAV"
FIXED_POINT_SCALE = 100_000
UINT64_MODULUS = 1 << 64
UINT64_SIGN_BIT = 1 << 63

SOL_POP_TYPES = (
    "nobles",
    "clergy",
    "burghers",
    "laborers",
    "peasants",
    "soldiers",
    "tribesmen",
)
PREFERRED_POP_TYPES = SOL_POP_TYPES + ("slaves",)
SOL_CLASS_LABELS = {
    0: "unclassified",
    1: "nobles",
    2: "clergy",
    3: "burghers",
    4: "lower",
}

_TOP_LEVEL_BLOCK_RE = re.compile(
    rb"(?m)^([A-Za-z_][A-Za-z0-9_]*)=\{\r?$"
)
_POP_RECORD_RE = re.compile(rb"(?m)^(\d+)=\{\r?$")
_LOCATION_RECORD_RE = re.compile(rb"(?m)^\t\t(\d+)=\{\r?$")
_COUNTRY_TAG_RE = re.compile(rb"(?m)^\t\t(\d+)=([A-Za-z0-9_]+)\r?$")
_COUNTRY_RECORD_RE = re.compile(
    rb"(?m)^(\d+)=\{\r?\n\tcountry_name="
)
_POP_FIELD_PATTERNS = {
    "type": re.compile(rb"(?m)^\ttype=([^\s{}]+)\r?$"),
    "estate": re.compile(rb"(?m)^\testate=([^\s{}]+)\r?$"),
    "culture": re.compile(rb"(?m)^\tculture=([^\s{}]+)\r?$"),
    "status": re.compile(rb"(?m)^\tstatus=([^\s{}]+)\r?$"),
    "religion": re.compile(rb"(?m)^\treligion=([^\s{}]+)\r?$"),
    "size": re.compile(rb"(?m)^\tsize=([-+0-9.eE]+)\r?$"),
    "satisfaction": re.compile(
        rb"(?m)^\tsatisfaction=([-+0-9.eE]+)\r?$"
    ),
    "literacy": re.compile(rb"(?m)^\tliteracy=([-+0-9.eE]+)\r?$"),
    "goods": re.compile(rb"(?m)^\tgoods=([-+0-9.eE]+)\r?$"),
    "price": re.compile(rb"(?m)^\tprice=([-+0-9.eE]+)\r?$"),
}
_LOCATION_DIRECT_FIELD_RE = re.compile(
    rb"(?m)^\t{3}"
    rb"(owner|controller|market|province|rank|raw_material|development|control)"
    rb"=([^\s{}]+)\r?$"
)
_LOCATION_POPS_RE = re.compile(
    rb"(?m)^\t{4}pops=\{([^}\r\n]*)\}\r?$"
)
_LOCATION_SOL_VARIABLE_RE = re.compile(
    rb"(?m)^\t{6}flag="
    rb"(sol_location_[^\r\n]+|gls_location_actual_per_capita_spending)\r?$"
    rb"\n\t{6}data=\{\r?$"
    rb"\n\t{7}type=value\r?$"
    rb"(?:\n\t{7}identity=(\d+)\r?$)?"
)
_COUNTRY_SOL_VARIABLE_RE = re.compile(
    rb"(?m)^\t{4}flag="
    rb"(sol_country_[^\r\n]+|sol_demand_[^\r\n]+|gls_[^\r\n]+)\r?$"
    rb"\n\t{4}data=\{\r?$"
    rb"\n\t{5}type=value\r?$"
    rb"(?:\n\t{5}identity=(\d+)\r?$)?"
)


class SaveFormatError(ValueError):
    """Raised when a save is compressed, binary, or structurally unexpected."""


@dataclass(frozen=True, slots=True)
class PopulationRecord:
    """One entry from ``population.database``."""

    id: int
    type: str
    size: float
    estate: str | None = None
    culture: str | None = None
    status: str | None = None
    religion: str | None = None
    satisfaction: float | None = None
    literacy: float | None = None
    goods: float | None = None
    price: float | None = None


@dataclass(frozen=True, slots=True)
class LocationRecord:
    """The small subset of a location object relevant to SOL analysis."""

    id: int
    name: str | None
    owner_id: int | None
    controller_id: int | None
    market_id: int | None
    province_id: int | None
    rank: str | None
    raw_material: str | None
    development: float | None
    control: float | None
    pop_ids: tuple[int, ...]
    sol_variables: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ParsedSave:
    """A compact in-memory representation of the analysis-relevant data."""

    source: Path
    metadata: Mapping[str, str]
    country_tags: Mapping[int, str]
    country_variables: Mapping[int, Mapping[str, float]]
    location_names: Mapping[int, str]
    populations: Mapping[int, PopulationRecord]
    locations: tuple[LocationRecord, ...]
    diagnostics: Mapping[str, int]

    @property
    def population_types(self) -> tuple[str, ...]:
        found = {record.type for record in self.populations.values()}
        preferred = [name for name in PREFERRED_POP_TYPES if name in found]
        return tuple(preferred + sorted(found.difference(preferred)))


def _decode(raw: bytes) -> str:
    return raw.decode("utf-8", errors="strict")


def _top_level_bounds(
    view: mmap.mmap, block_name: str, *, start_at: int = 0
) -> tuple[int, int]:
    marker = block_name.encode("ascii") + b"={"
    if start_at == 0 and view[: len(marker)] == marker:
        start = 0
    else:
        start = view.find(b"\n" + marker, start_at)
        if start >= 0:
            start += 1
    if start < 0:
        raise SaveFormatError(f"Top-level block {block_name!r} was not found")

    next_match = _TOP_LEVEL_BLOCK_RE.search(view, start + len(marker))
    end = next_match.start() if next_match else len(view)
    return start, end


def _metadata_scalar(
    view: mmap.mmap, start: int, end: int, key: str
) -> str | None:
    pattern = re.compile(
        rb"(?m)^\t"
        + re.escape(key.encode("ascii"))
        + rb"=(?:\"([^\"\r\n]*)\"|([^\s{}]+))\r?$"
    )
    match = pattern.search(view, start, end)
    if not match:
        return None
    return _decode(match.group(1) or match.group(2))


def _parse_metadata(
    view: mmap.mmap, start: int, end: int
) -> tuple[dict[str, str], dict[int, str]]:
    metadata: dict[str, str] = {}
    for key in (
        "date",
        "playthrough_id",
        "playthrough_name",
        "save_label",
        "version",
        "player_country_name",
    ):
        value = _metadata_scalar(view, start, end, key)
        if value is not None:
            metadata[key] = value

    compatibility_start = view.find(b"\n\tcompatibility={", start, end)
    names_marker = b"\n\t\tlocations={"
    names_start = view.find(
        names_marker,
        compatibility_start if compatibility_start >= 0 else start,
        end,
    )
    if names_start < 0:
        raise SaveFormatError(
            "metadata.compatibility.locations was not found; location ids "
            "cannot be named safely"
        )
    names_start += len(names_marker)
    names_end = view.find(b"}", names_start, end)
    if names_end < 0:
        raise SaveFormatError("metadata.compatibility.locations is not closed")

    # EU5 location ids are one-based and follow this compatibility list.
    names = _decode(view[names_start:names_end]).split()
    location_names = {index: name for index, name in enumerate(names, start=1)}
    return metadata, location_names


def _parse_country_tags(
    view: mmap.mmap, start: int, end: int
) -> dict[int, str]:
    tags_start = view.find(b"\n\ttags={", start, end)
    if tags_start < 0:
        raise SaveFormatError("countries.tags was not found")
    tags_start = view.find(b"\n", tags_start + 1, end) + 1
    tags_end = view.find(b"\n\t}", tags_start, end)
    if tags_end < 0:
        raise SaveFormatError("countries.tags is not closed")

    return {
        int(match.group(1)): _decode(match.group(2))
        for match in _COUNTRY_TAG_RE.finditer(view, tags_start, tags_end)
    }


def _matched_text(
    pattern: re.Pattern[bytes], view: mmap.mmap, start: int, end: int
) -> str | None:
    match = pattern.search(view, start, end)
    return _decode(match.group(1)) if match else None


def _matched_float(
    pattern: re.Pattern[bytes], view: mmap.mmap, start: int, end: int
) -> float | None:
    raw = _matched_text(pattern, view, start, end)
    return float(raw) if raw is not None else None


def _parse_population_record(
    view: mmap.mmap, start: int, end: int, record_id: int
) -> PopulationRecord:
    values = {
        key: _matched_text(pattern, view, start, end)
        for key, pattern in _POP_FIELD_PATTERNS.items()
        if key not in {"size", "satisfaction", "literacy", "goods", "price"}
    }
    number_values = {
        key: _matched_float(_POP_FIELD_PATTERNS[key], view, start, end)
        for key in ("size", "satisfaction", "literacy", "goods", "price")
    }
    if values["type"] is None:
        raise SaveFormatError(
            f"Population record {record_id} has no direct type field"
        )
    # The engine omits size entirely for a retained zero-sized population.
    # Keeping the record is important because locations can still reference it.
    size = number_values["size"] if number_values["size"] is not None else 0.0
    return PopulationRecord(
        id=record_id,
        type=values["type"],
        size=size,
        estate=values["estate"],
        culture=values["culture"],
        status=values["status"],
        religion=values["religion"],
        satisfaction=number_values["satisfaction"],
        literacy=number_values["literacy"],
        goods=number_values["goods"],
        price=number_values["price"],
    )


def _parse_populations(
    view: mmap.mmap, start: int, end: int
) -> dict[int, PopulationRecord]:
    database_start = view.find(b"\n\tdatabase={", start, end)
    if database_start < 0:
        raise SaveFormatError("population.database was not found")

    records: dict[int, PopulationRecord] = {}
    iterator = _POP_RECORD_RE.finditer(view, database_start, end)
    previous = next(iterator, None)
    if previous is None:
        return records
    for current in iterator:
        record_id = int(previous.group(1))
        records[record_id] = _parse_population_record(
            view, previous.start(), current.start(), record_id
        )
        previous = current
    record_id = int(previous.group(1))
    records[record_id] = _parse_population_record(
        view, previous.start(), end, record_id
    )
    return records


def decode_jomini_fixed_point(identity: int) -> float:
    """Decode a Jomini ``type=value`` identity from signed 64-bit fixed point."""

    if identity >= UINT64_SIGN_BIT:
        identity -= UINT64_MODULUS
    return identity / FIXED_POINT_SCALE


def _parse_country_variables(
    view: mmap.mmap,
    start: int,
    end: int,
    country_tags: Mapping[int, str],
) -> dict[int, dict[str, float]]:
    database_start = view.find(b"\n\tdatabase={", start, end)
    if database_start < 0:
        raise SaveFormatError("countries.database was not found")

    variables: dict[int, dict[str, float]] = {}
    iterator = _COUNTRY_RECORD_RE.finditer(view, database_start, end)
    previous = next(iterator, None)
    if previous is None:
        return variables

    def parse_record(match: re.Match[bytes], record_end: int) -> None:
        country_id = int(match.group(1))
        if country_id not in country_tags:
            return
        values: dict[str, float] = {}
        for variable_match in _COUNTRY_SOL_VARIABLE_RE.finditer(
            view, match.start(), record_end
        ):
            name = _decode(variable_match.group(1))
            identity = (
                int(variable_match.group(2)) if variable_match.group(2) else 0
            )
            values[name] = decode_jomini_fixed_point(identity)
        if values:
            variables[country_id] = values

    for current in iterator:
        parse_record(previous, current.start())
        previous = current
    parse_record(previous, end)
    return variables


def _parse_location_record(
    view: mmap.mmap,
    start: int,
    end: int,
    location_id: int,
    location_names: Mapping[int, str],
) -> LocationRecord:
    direct: dict[str, str] = {
        _decode(match.group(1)): _decode(match.group(2))
        for match in _LOCATION_DIRECT_FIELD_RE.finditer(view, start, end)
    }

    pop_match = _LOCATION_POPS_RE.search(view, start, end)
    pop_ids = (
        tuple(int(value) for value in pop_match.group(1).split())
        if pop_match
        else ()
    )

    sol_variables: dict[str, float] = {}
    for match in _LOCATION_SOL_VARIABLE_RE.finditer(view, start, end):
        name = _decode(match.group(1))
        identity = int(match.group(2)) if match.group(2) else 0
        sol_variables[name] = decode_jomini_fixed_point(identity)

    def optional_int(key: str) -> int | None:
        return int(direct[key]) if key in direct else None

    def optional_float(key: str) -> float | None:
        return float(direct[key]) if key in direct else None

    return LocationRecord(
        id=location_id,
        name=location_names.get(location_id),
        owner_id=optional_int("owner"),
        controller_id=optional_int("controller"),
        market_id=optional_int("market"),
        province_id=optional_int("province"),
        rank=direct.get("rank"),
        raw_material=direct.get("raw_material"),
        development=optional_float("development"),
        control=optional_float("control"),
        pop_ids=pop_ids,
        sol_variables=sol_variables,
    )


def _parse_locations(
    view: mmap.mmap,
    start: int,
    end: int,
    location_names: Mapping[int, str],
) -> tuple[LocationRecord, ...]:
    database_start = view.find(b"\n\tlocations={", start, end)
    if database_start < 0:
        raise SaveFormatError("locations.locations was not found")

    records: list[LocationRecord] = []
    iterator = _LOCATION_RECORD_RE.finditer(view, database_start, end)
    previous = next(iterator, None)
    if previous is None:
        return ()
    for current in iterator:
        location_id = int(previous.group(1))
        records.append(
            _parse_location_record(
                view,
                previous.start(),
                current.start(),
                location_id,
                location_names,
            )
        )
        previous = current
    location_id = int(previous.group(1))
    records.append(
        _parse_location_record(
            view, previous.start(), end, location_id, location_names
        )
    )
    return tuple(records)


def _reference_diagnostics(
    populations: Mapping[int, PopulationRecord],
    locations: Sequence[LocationRecord],
) -> dict[str, int]:
    references = Counter(
        pop_id for location in locations for pop_id in location.pop_ids
    )
    known_ids = set(populations)
    referenced_ids = set(references)
    return {
        "population_records": len(populations),
        "location_records": len(locations),
        "referenced_population_records": len(referenced_ids),
        "unreferenced_population_records": len(known_ids - referenced_ids),
        "missing_population_records": len(referenced_ids - known_ids),
        "multiply_referenced_population_records": sum(
            count > 1 for count in references.values()
        ),
        "unnamed_location_records": sum(
            location.name is None for location in locations
        ),
    }


def parse_save(path: str | Path, *, strict: bool = True) -> ParsedSave:
    """Parse an uncompressed EU5 debug save into SOL-focused records.

    ``strict`` rejects broken population/location joins.  Unreferenced
    population records are reported but accepted because the engine can keep
    transient database entries that are not attached to a current location.
    """

    source = Path(path).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)

    with source.open("rb") as stream:
        header = stream.read(3)
        if header != SAVE_HEADER:
            raise SaveFormatError(
                "Expected a plaintext debug save beginning with 'SAV'. "
                "Compressed or binary saves are not supported."
            )
        stream.seek(0)
        view = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            metadata_bounds = _top_level_bounds(view, "metadata")
            countries_bounds = _top_level_bounds(view, "countries")
            population_bounds = _top_level_bounds(view, "population")
            locations_bounds = _top_level_bounds(view, "locations")

            metadata, location_names = _parse_metadata(
                view, *metadata_bounds
            )
            country_tags = _parse_country_tags(view, *countries_bounds)
            country_variables = _parse_country_variables(
                view,
                countries_bounds[0],
                population_bounds[0],
                country_tags,
            )
            populations = _parse_populations(view, *population_bounds)
            locations = _parse_locations(
                view, *locations_bounds, location_names
            )
        except Exception:
            # A regex match in an exception traceback can temporarily export
            # the mmap buffer on Windows. Let that traceback release the map
            # instead of masking the useful parse error with BufferError.
            view = None
            raise
        else:
            view.close()

    diagnostics = _reference_diagnostics(populations, locations)
    if strict and (
        diagnostics["missing_population_records"]
        or diagnostics["multiply_referenced_population_records"]
        or diagnostics["unnamed_location_records"]
    ):
        raise SaveFormatError(
            "Population/location validation failed: "
            + ", ".join(
                f"{key}={value}"
                for key, value in diagnostics.items()
                if key
                in {
                    "missing_population_records",
                    "multiply_referenced_population_records",
                    "unnamed_location_records",
                }
                and value
            )
        )

    return ParsedSave(
        source=source,
        metadata=metadata,
        country_tags=country_tags,
        country_variables=country_variables,
        location_names=location_names,
        populations=populations,
        locations=locations,
        diagnostics=diagnostics,
    )


def _population_totals(
    pop_ids: Iterable[int], populations: Mapping[int, PopulationRecord]
) -> dict[str, float]:
    values: dict[str, list[float]] = defaultdict(list)
    for pop_id in pop_ids:
        record = populations.get(pop_id)
        if record is not None:
            values[record.type].append(record.size)
    return {pop_type: math.fsum(sizes) for pop_type, sizes in values.items()}


def _derived_totals(totals: Mapping[str, float]) -> dict[str, float]:
    commoners = math.fsum(
        totals.get(name, 0.0) for name in ("laborers", "peasants", "soldiers")
    )
    lower = commoners + totals.get("tribesmen", 0.0)
    sol_total = math.fsum(totals.get(name, 0.0) for name in SOL_POP_TYPES)
    return {
        "commoners": commoners,
        "lower": lower,
        "sol_total": sol_total,
        "all_total": math.fsum(totals.values()),
    }


def _class_label(value: float | None) -> str:
    if value is None:
        return ""
    rounded = round(value)
    if not math.isclose(value, rounded, abs_tol=1e-5):
        return "invalid"
    return SOL_CLASS_LABELS.get(rounded, "invalid")


def _formatted_csv_row(row: Mapping[str, object]) -> dict[str, object]:
    """Keep exact five-decimal save data free of binary-float artifacts."""

    formatted: dict[str, object] = {}
    for key, value in row.items():
        if isinstance(value, float):
            decimals = 10 if "share" in key else 5
            formatted[key] = f"{value:.{decimals}f}"
        else:
            formatted[key] = value
    return formatted


def _selected_locations(
    parsed: ParsedSave, selected_tags: set[str] | None
) -> list[LocationRecord]:
    if not selected_tags:
        return list(parsed.locations)
    normalized = {tag.upper() for tag in selected_tags}
    unknown = normalized.difference(parsed.country_tags.values())
    if unknown:
        raise ValueError(f"Unknown country tag(s): {', '.join(sorted(unknown))}")
    return [
        location
        for location in parsed.locations
        if location.owner_id is not None
        and parsed.country_tags.get(location.owner_id) in normalized
    ]


def _write_locations_csv(
    path: Path,
    parsed: ParsedSave,
    locations: Sequence[LocationRecord],
) -> None:
    pop_types = parsed.population_types
    sol_variable_names = sorted(
        {
            name
            for location in locations
            for name in location.sol_variables
        }
    )
    fields = [
        "location_id",
        "location",
        "owner_id",
        "owner_tag",
        "controller_id",
        "market_id",
        "province_id",
        "rank",
        "raw_material",
        "development",
        "control",
        "pop_group_count",
        "population_total",
        "sol_population_total",
        *[f"population_{name}" for name in pop_types],
        "population_commoners",
        "population_lower",
        *[f"population_share_{name}" for name in SOL_POP_TYPES],
        "population_share_commoners",
        "population_share_lower",
        "sol_class_label",
        "sol_structural_class_label",
        *sol_variable_names,
    ]

    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for location in locations:
            totals = _population_totals(location.pop_ids, parsed.populations)
            derived = _derived_totals(totals)
            denominator = derived["sol_total"]
            row: dict[str, object] = {
                "location_id": location.id,
                "location": location.name or "",
                "owner_id": location.owner_id if location.owner_id is not None else "",
                "owner_tag": parsed.country_tags.get(location.owner_id, ""),
                "controller_id": (
                    location.controller_id
                    if location.controller_id is not None
                    else ""
                ),
                "market_id": location.market_id if location.market_id is not None else "",
                "province_id": location.province_id if location.province_id is not None else "",
                "rank": location.rank or "",
                "raw_material": location.raw_material or "",
                "development": location.development if location.development is not None else "",
                "control": location.control if location.control is not None else "",
                "pop_group_count": len(location.pop_ids),
                "population_total": derived["all_total"],
                "sol_population_total": derived["sol_total"],
                "population_commoners": derived["commoners"],
                "population_lower": derived["lower"],
                "population_share_commoners": (
                    derived["commoners"] / denominator if denominator else ""
                ),
                "population_share_lower": (
                    derived["lower"] / denominator if denominator else ""
                ),
                "sol_class_label": _class_label(
                    location.sol_variables.get("sol_location_demand_class")
                ),
                "sol_structural_class_label": _class_label(
                    location.sol_variables.get(
                        "sol_location_demand_structural_class"
                    )
                ),
            }
            for pop_type in pop_types:
                row[f"population_{pop_type}"] = totals.get(pop_type, 0.0)
            for pop_type in SOL_POP_TYPES:
                row[f"population_share_{pop_type}"] = (
                    totals.get(pop_type, 0.0) / denominator
                    if denominator
                    else ""
                )
            row.update(location.sol_variables)
            writer.writerow(_formatted_csv_row(row))


def _write_countries_csv(
    path: Path,
    parsed: ParsedSave,
    locations: Sequence[LocationRecord],
) -> None:
    pop_types = parsed.population_types
    owner_ids = {
        location.owner_id
        for location in locations
        if location.owner_id is not None
    }
    country_variable_names = sorted(
        {
            name
            for owner_id in owner_ids
            for name in parsed.country_variables.get(owner_id, {})
        }
    )
    location_counts: Counter[int] = Counter()
    country_pop_ids: dict[int, list[int]] = defaultdict(list)
    for location in locations:
        if location.owner_id is None:
            continue
        location_counts[location.owner_id] += 1
        country_pop_ids[location.owner_id].extend(location.pop_ids)

    fields = [
        "owner_id",
        "owner_tag",
        "location_count",
        "pop_group_count",
        "population_total",
        "sol_population_total",
        *[f"population_{name}" for name in pop_types],
        "population_commoners",
        "population_lower",
        *[f"population_share_{name}" for name in SOL_POP_TYPES],
        "population_share_commoners",
        "population_share_lower",
        *country_variable_names,
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for owner_id in sorted(country_pop_ids):
            pop_ids = country_pop_ids[owner_id]
            totals = _population_totals(pop_ids, parsed.populations)
            derived = _derived_totals(totals)
            denominator = derived["sol_total"]
            row: dict[str, object] = {
                "owner_id": owner_id,
                "owner_tag": parsed.country_tags.get(owner_id, ""),
                "location_count": location_counts[owner_id],
                "pop_group_count": len(pop_ids),
                "population_total": derived["all_total"],
                "sol_population_total": derived["sol_total"],
                "population_commoners": derived["commoners"],
                "population_lower": derived["lower"],
                "population_share_commoners": (
                    derived["commoners"] / denominator if denominator else ""
                ),
                "population_share_lower": (
                    derived["lower"] / denominator if denominator else ""
                ),
            }
            for pop_type in pop_types:
                row[f"population_{pop_type}"] = totals.get(pop_type, 0.0)
            for pop_type in SOL_POP_TYPES:
                row[f"population_share_{pop_type}"] = (
                    totals.get(pop_type, 0.0) / denominator
                    if denominator
                    else ""
                )
            row.update(parsed.country_variables.get(owner_id, {}))
            writer.writerow(_formatted_csv_row(row))


def _write_populations_csv(
    path: Path,
    parsed: ParsedSave,
    locations: Sequence[LocationRecord],
) -> None:
    pop_location = {
        pop_id: location for location in locations for pop_id in location.pop_ids
    }
    fields = [
        "pop_id",
        "location_id",
        "location",
        "owner_id",
        "owner_tag",
        "type",
        "size",
        "estate",
        "culture",
        "status",
        "religion",
        "satisfaction",
        "literacy",
        "goods",
        "price",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for pop_id in sorted(pop_location):
            location = pop_location[pop_id]
            record = parsed.populations[pop_id]
            writer.writerow(
                _formatted_csv_row({
                    "pop_id": pop_id,
                    "location_id": location.id,
                    "location": location.name or "",
                    "owner_id": (
                        location.owner_id if location.owner_id is not None else ""
                    ),
                    "owner_tag": parsed.country_tags.get(location.owner_id, ""),
                    "type": record.type,
                    "size": record.size,
                    "estate": record.estate or "",
                    "culture": record.culture or "",
                    "status": record.status or "",
                    "religion": record.religion or "",
                    "satisfaction": (
                        record.satisfaction
                        if record.satisfaction is not None
                        else ""
                    ),
                    "literacy": record.literacy if record.literacy is not None else "",
                    "goods": record.goods if record.goods is not None else "",
                    "price": record.price if record.price is not None else "",
                })
            )


def export_analysis(
    parsed: ParsedSave,
    output_dir: str | Path,
    *,
    country_tags: Iterable[str] | None = None,
    emit_populations: bool = False,
) -> tuple[Path, ...]:
    """Export analysis-ready CSV tables and a metadata/diagnostic manifest."""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    selected_tag_set = set(country_tags) if country_tags else None
    locations = _selected_locations(parsed, selected_tag_set)

    location_path = output / "locations.csv"
    country_path = output / "countries.csv"
    metadata_path = output / "metadata.json"
    _write_locations_csv(location_path, parsed, locations)
    _write_countries_csv(country_path, parsed, locations)

    manifest = {
        "source": str(parsed.source),
        "source_size_bytes": parsed.source.stat().st_size,
        "metadata": dict(parsed.metadata),
        "population_types": list(parsed.population_types),
        "sol_population_types": list(SOL_POP_TYPES),
        "sol_class_labels": {
            str(key): value for key, value in SOL_CLASS_LABELS.items()
        },
        "size_unit": (
            "raw save size units; EU5 displays these as thousands of people, "
            "but no multiplier has been applied"
        ),
        "selected_country_tags": (
            sorted(tag.upper() for tag in selected_tag_set)
            if selected_tag_set
            else []
        ),
        "exported_location_records": len(locations),
        "countries_with_sol_variables": len(parsed.country_variables),
        "diagnostics": dict(parsed.diagnostics),
    }
    metadata_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    paths = [location_path, country_path, metadata_path]
    if emit_populations:
        populations_path = output / "populations.csv"
        _write_populations_csv(populations_path, parsed, locations)
        paths.append(populations_path)
    return tuple(paths)

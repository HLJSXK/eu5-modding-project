#!/usr/bin/env python3
"""Runtime aliases and bundle overrides for country-event GUI resolution.

Some countries can exist in-game under a tag or flag key that should reuse the
same curated event view as another canonical registry tag.
"""

from __future__ import annotations

from typing import Collection


COUNTRY_RUNTIME_ALIASES: dict[str, tuple[str, ...]] = {
    # Great Ming is represented through the Chinese event set, but it can
    # appear in runtime contexts as MNG and with the CHI_Ming country flag.
    "CHI": ("CHI_Ming", "MNG"),
    # These late-game identities reuse the same historical content bucket.
    "JAP": ("JPN",),
    "MCH": ("QNG",),
    # Mutapa can switch to its restored cosmetic identity without changing
    # the underlying event bucket we want to show.
    "ZMW": ("MTP",),
}


COUNTRY_SUCCESSOR_BUNDLES: dict[str, tuple[str, ...]] = {
    # Italy has no dedicated DHE set in the extracted registry, so build a
    # synthetic successor profile from the main Italian state event sets.
    "ITA": ("FLO", "GEN", "MLO", "NAP", "PAP", "PAV", "SAV", "SIE", "TUS", "VEN"),
    # These tags exist as formables or scripted transformations but the game
    # does not expose enough structured metadata to infer a bundle reliably.
    "EUR": ("FRA", "GER", "HRE", "ITA", "GBR", "HAB", "RUS", "SPA", "POL"),
    "BEJ": ("ETH", "IFA"),
    "GLD": ("HAB", "HUN"),
    "HIN": ("DLH", "ORI", "VIJ"),
    "MLC": ("MAJ", "ADH", "CHA", "DAI", "KHM", "LGK", "SUK"),
    "MTM": ("MAJ", "BEI", "PLB"),
    "PGR": ("MAJ", "BEI", "PLB"),
    "RYU": ("JAP", "SOU"),
}


FORMABLE_GEOGRAPHY_BUCKET_ALIASES: dict[str, tuple[str, ...]] = {
    # High-level formable regions whose country setup buckets use different ids.
    "scandinavian_region": ("_scandinavia",),
    "north_atlantic_islands_region": ("_scandinavia", "british_isles"),
    "great_britain_region": ("british_isles",),
    "ireland_region": ("british_isles",),
    "north_german_region": ("north_germany",),
    "south_german_region": ("south_germany",),
    "east_coast_region": ("eastcoast",),
    "canada_region": ("canadian",),
    "italy_region": ("italy",),
    "france_region": ("france",),
    "iberia_region": ("iberia",),
    "balkan_region": ("balkans",),
    "caucasus_region": ("caucasus",),
    "carpathia_region": ("carpathia",),
    "crescent_region": ("crescent",),
    "egypt_region": ("egypt",),
    "maghreb_region": ("maghreb",),
    "anatolia_region": ("anatolia",),
    "mesoamerica_region": ("mesoamerica",),
    "persia_region": ("persia",),
    "deccan_region": ("india",),
    "tibet_region": ("east_asia",),
    "madagascar_region": ("east_africa",),
    "new_zealand_region": ("polynesia", "indonesia"),
    "north_borneo_area": ("indonesia",),
    "south_borneo_area": ("indonesia",),
    "banten_province": ("indonesia",),
    "ogan_province": ("indonesia",),
    "tulangbawang_province": ("indonesia",),
    "lampung_province": ("indonesia",),
    "gujarat_area": ("india",),
    "saurashtra_area": ("india",),
    "nepal_area": ("india",),
    "punjab_area": ("india",),
    "rajputana_area": ("india",),
    "lower_saxony_area": ("north_germany",),
    "pomerania_area": ("north_germany",),
    "mecklenburg_area": ("north_germany",),
    "swabia_area": ("south_germany",),
    "silesia_area": ("south_germany", "north_germany", "carpathia"),
    "slovakia_area": ("carpathia",),
    "moldavia_area": ("carpathia",),
    "mazovia_area": ("carpathia",),
    "connaught_area": ("british_isles",),
    "iceland_area": ("_scandinavia", "british_isles"),
    "albania_province": ("balkans",),
    "north_epirus_province": ("balkans",),
    "illyria_province": ("balkans",),
    "bulgaria_area": ("balkans",),
    "croatia_area": ("balkans",),
    "slavonia_area": ("balkans",),
    "thrace_area": ("balkans",),
    "thessaly_province": ("balkans",),
    "tunis_area": ("maghreb",),
    "tripolitania_area": ("maghreb", "egypt"),
    "algiers_area": ("maghreb",),
    "sicily_area": ("italy",),
    "west_kongo_area": ("kongo", "west_africa", "east_africa"),
    "kongo_area": ("kongo", "west_africa", "east_africa"),
    "kordestan_area": ("persia", "crescent"),
    "gilan_province": ("persia",),
    "east_mossi_area": ("west_africa",),
    "west_mossi_area": ("west_africa",),
    "nubia_proper_area": ("egypt",),
    "butana_area": ("egypt",),
    "shan_highland_area": ("south_east_asia",),
    "chactemal_area": ("mesoamerica",),
    "chilapan_area": ("mesoamerica",),
    "mayaab_area": ("mesoamerica",),
    "peten_area": ("mesoamerica",),
    "puuk_area": ("mesoamerica",),
    "tezulutlan_area": ("mesoamerica",),
    "desht_kipchak_area": ("steppes", "russia"),
    "zhetysu_area": ("steppes",),
    # Smaller areas that should still resolve into a coherent bundle.
    "scottish_lowlands_area": ("british_isles",),
    "northumbria_area": ("british_isles",),
    "wales_area": ("british_isles",),
    "cornwall_area": ("british_isles",),
    "hebrides_area": ("british_isles",),
    "scottish_highlands_area": ("british_isles",),
    "ulster_area": ("british_isles",),
    "brittany_area": ("france",),
}


def group_runtime_keys(group: dict[str, object], canonical_tags: Collection[str]) -> list[str]:
    """Return the runtime keys that should resolve to this group's content."""
    tags = group.get("country_tags", [])
    if len(tags) != 1:
        return []

    tag = str(tags[0])
    keys = [tag]

    for alias in COUNTRY_RUNTIME_ALIASES.get(tag, ()):
        runtime_key = str(alias).strip()
        if not runtime_key:
            continue
        if runtime_key in canonical_tags and runtime_key != tag:
            continue
        if runtime_key not in keys:
            keys.append(runtime_key)

    return keys

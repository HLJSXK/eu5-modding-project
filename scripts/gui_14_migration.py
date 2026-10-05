#!/usr/bin/env python3
"""Migrate 1.3 location action buttons and road links to the EU5 1.4 GUI API."""

from __future__ import annotations

import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _sub_once(text: str, pattern: str, replacement: str, label: str) -> str:
    text, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE | re.DOTALL)
    if count != 1:
        raise ValueError(f"Expected one {label} block during 1.4 GUI migration, found {count}")
    return text


def _replace_all(text: str, pattern: str, replacement: str, expected: int, label: str) -> str:
    text, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
    if count != expected:
        raise ValueError(
            f"Expected {expected} {label} replacements during 1.4 GUI migration, found {count}"
        )
    return text


def migrate_location_gui(text: str, label: str = "location window") -> str:
    """Convert legacy header actions and the road-builder call in a 1.3 window."""

    header_count = len(re.findall(r"header_action_button_left(?=\s*(?:=|\{))", text))
    if header_count not in (4, 5):
        raise ValueError(
            f"Expected 4 location action buttons (or 5 including garrison), found {header_count}"
        )
    text = re.sub(
        r"header_action_button_left(?P<separator>\s*)(?P<op>=|\{)",
        r"header_action_button_left_uber\g<separator>\g<op>",
        text,
    )
    text = re.sub(
        r"(?m)^(?P<line>[ \t]*type garrison_sortie_button = header_action_button_left_uber \{)[ \t]+$",
        r"\g<line>",
        text,
    )

    if "title = \"GARRISON_SORTIE_TT\"" in text:
        text = _migrate_garrison_action(text, label)

    # Province-capital button: 1.4 keeps the old visibility expression and adds
    # the Uber enabled state, while its action is now scripted_action_tooltip.
    text = _sub_once(
        text,
        r'(?P<i>[ \t]*)visible = "\[And3\(Location\.GetOwner\.IsPlayer, Not\(LocationView\.GetLocation\.IsProvinceCapital\), Not\(LocationView\.GetLocation\.GetProvince\.GetCapital\.IsCapital\)\)\]"',
        r'\g<i>visible = "[And3(Location.GetOwner.IsPlayer, Not(LocationView.GetLocation.IsProvinceCapital), Not(LocationView.GetLocation.GetProvince.GetCapital.IsCapital))]"\n\g<i>enabled = "[PdxGuiWidget.IsUberButtonEnabled]"',
        f"{label} province-capital enabled state",
    )
    text = _sub_once(
        text,
        r'(?P<i>[ \t]*)actor = "\[LocationView\.GetPlayer\]"\n'
        r'(?P=i)parameter = \{\n.*?'
        r'(?P=i)left_click_and_hold_action = \{ action_name = "set_province_capital" \}',
        r'\g<i>scripted_action_tooltip = {\n'
        r'\g<i>\tclick_type = left\n'
        r'\g<i>\tclick_mode = confirm\n'
        r'\g<i>\taction_name = "set_province_capital"\n'
        r'\g<i>\tactor = "[LocationView.GetPlayer]"\n'
        r'\g<i>\tparameter = {\n'
        r'\g<i>\t\tparameter_name = "target"\n'
        r'\g<i>\t\tparameter_value = "[LocationView.GetLocation]"\n'
        r'\g<i>\t}\n'
        r'\g<i>}',
        f"{label} province-capital action",
    )

    # International-organization buttons use the new Uber visibility guard and
    # scripted tooltips. Their existing tooltip widgets remain unchanged.
    text = _replace_all(
        text,
        r"UIAction\.IsVisible, InternationalOrganization\.CanOwnLocations",
        "PdxGuiWidget.IsUberButtonVisible, InternationalOrganization.CanOwnLocations",
        2,
        f"{label} international-organization visibility",
    )
    text = _sub_once(
        text,
        r'(?P<i>[ \t]*)title = "add_location_to_international_organization"\n'
        r'(?P=i)actor = "\[LocationView\.GetPlayer\]"\n'
        r'(?P=i)parameter = \{\n.*?'
        r'(?P=i)left_click_and_hold_action = \{ action_name = "add_location_to_international_organization" \}',
        r'\g<i>scripted_action_tooltip = {\n'
        r'\g<i>\tclick_type = left\n'
        r'\g<i>\tclick_mode = confirm\n'
        r'\g<i>\taction_name = "add_location_to_international_organization"\n'
        r'\g<i>\tactor = "[LocationView.GetPlayer]"\n'
        r'\g<i>\tparameter = {\n'
        r'\g<i>\t\tparameter_name = "target"\n'
        r'\g<i>\t\tparameter_value = "[LocationView.GetLocation]"\n'
        r'\g<i>\t}\n'
        r'\g<i>\tparameter = {\n'
        r'\g<i>\t\tparameter_name = "target_1"\n'
        r'\g<i>\t\tparameter_value = "[InternationalOrganization.MakeScope]"\n'
        r'\g<i>\t}\n'
        r'\g<i>}',
        f"{label} add-to-IO action",
    )
    text = _sub_once(
        text,
        r'(?P<i>[ \t]*)title = "remove_location_from_international_organization"\n'
        r'(?P=i)actor = "\[GetPlayer\]"\n'
        r'(?P=i)parameter = \{\n.*?'
        r'(?P=i)right_click_and_hold_action = \{ action_name = "remove_location_from_international_organization" \}',
        r'\g<i>scripted_action_tooltip = {\n'
        r'\g<i>\tclick_type = right\n'
        r'\g<i>\tclick_mode = confirm\n'
        r'\g<i>\taction_name = "remove_location_from_international_organization"\n'
        r'\g<i>\tactor = "[GetPlayer]"\n'
        r'\g<i>\tparameter = {\n'
        r'\g<i>\t\tparameter_name = "target"\n'
        r'\g<i>\t\tparameter_value = "[LocationView.GetLocation]"\n'
        r'\g<i>\t}\n'
        r'\g<i>\tparameter = {\n'
        r'\g<i>\t\tparameter_name = "target_1"\n'
        r'\g<i>\t\tparameter_value = "[InternationalOrganization.MakeScope]"\n'
        r'\g<i>\t}\n'
        r'\g<i>}',
        f"{label} remove-from-IO action",
    )

    # Periphora is the only left-click action without a title field.
    text = _sub_once(
        text,
        r'(?P<i>[ \t]*)name = "periphora"\n'
        r'(?P=i)actor = "\[LocationView\.GetPlayer\]"\n'
        r'(?P=i)parameter = \{\n.*?'
        r'(?P=i)left_action = \{ action_name = "periphora" \}',
        r'\g<i>name = "periphora"\n\n'
        r'\g<i>visible = "[PdxGuiWidget.IsUberButtonVisible]"\n'
        r'\g<i>enabled = "[PdxGuiWidget.IsUberButtonEnabled]"\n\n'
        r'\g<i>scripted_action_tooltip = {\n'
        r'\g<i>\tclick_type = left\n'
        r'\g<i>\tclick_mode = single\n'
        r'\g<i>\taction_name = "periphora"\n'
        r'\g<i>\tactor = "[LocationView.GetPlayer]"\n'
        r'\g<i>\tparameter = {\n'
        r'\g<i>\t\tparameter_name = "location"\n'
        r'\g<i>\t\tparameter_value = "[LocationView.GetLocation]"\n'
        r'\g<i>\t}\n'
        r'\g<i>}',
        f"{label} periphora action",
    )

    text = _replace_all(
        text,
        r"\[ShowRoadbuilder\(LocationView\.GetLocation\)\]",
        "[ShowRoadBuilder(LocationView.GetLocation)]",
        1,
        f"{label} road builder action",
    )

    return text


def migrate_location_types(text: str, label: str = "location types") -> str:
    """Migrate the standalone garrison action type extracted from Glorp UI."""

    text = _replace_all(
        text,
        r"header_action_button_left(?!_uber)",
        "header_action_button_left_uber",
        1,
        f"{label} header action type",
    )
    text = re.sub(
        r"(?m)^(?P<line>[ \t]*type garrison_sortie_button = header_action_button_left_uber \{)[ \t]+$",
        r"\g<line>",
        text,
    )
    return _migrate_garrison_action(text, label)


def _migrate_garrison_action(text: str, label: str) -> str:
    return _sub_once(
        text,
        r'(?P<i>[ \t]*)size = \{ 25 25 \}\n'
        r'(?P=i)title = "GARRISON_SORTIE_TT"\n'
        r'(?P=i)actor = "\[GetPlayer\]"\n'
        r'(?P=i)parameter = \{\n.*?'
        r'(?P=i)left_click_and_hold_action = \{ action_name = "garrison_sortie" \}',
        r'\g<i>size = { 25 25 }\n\n'
        r'\g<i>visible = "[PdxGuiWidget.IsUberButtonVisible]"\n'
        r'\g<i>enabled = "[PdxGuiWidget.IsUberButtonEnabled]"\n\n'
        r'\g<i>scripted_action_tooltip = {\n'
        r'\g<i>\tclick_type = left\n'
        r'\g<i>\tclick_mode = confirm\n'
        r'\g<i>\taction_name = "garrison_sortie"\n'
        r'\g<i>\tactor = "[GetPlayer]"\n'
        r'\g<i>\tparameter = {\n'
        r'\g<i>\t\tparameter_name = "target"\n'
        r'\g<i>\t\tparameter_value = "[Siege.MakeScope]"\n'
        r'\g<i>\t}\n'
        r'\g<i>}',
        f"{label} garrison action",
    )


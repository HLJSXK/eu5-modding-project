"""Optional Great Projects references shared by SOL's location-window owners.

The provider owns the types, template, assets and behavior. Generation only uses
this public interface; it must not read or require a Great Projects checkout.
See docs/guides/EU5_GUI_SOL_Notes.md for the integration contract and evidence.
"""
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def add_great_projects(text: str, *, expected_queue_actions: int) -> str:
    """Insert bare references without wrappers, placeholders or fallback types."""
    if "tv_location_wonders_" in text:
        raise ValueError("Location window already contains Great Projects references")

    # Same city-scene overlay slot used by GP's own window and compatibility mods.
    scene_anchor = "\n\t\t\t\tvbox = {\n\t\t\t\t\texpand = {}\n"
    root_anchor = '\n\twidgetid = "location_window"'
    for label, anchor in (("city scene", scene_anchor), ("window root", root_anchor)):
        if text.count(anchor) != 1:
            raise ValueError(f"Expected one Great Projects {label} anchor, found {text.count(anchor)}")
    text = text.replace(scene_anchor, "\n\t\t\t\ttv_location_wonders_button = {}\n" + scene_anchor, 1)
    text = text.replace(root_anchor, root_anchor + "\n\ttv_location_wonders_panel = {}", 1)

    # Compose the optional close action before each unchanged native queue action.
    # Current M&T has no OpenConstructionQueue actions; its inline queues remain.
    text, count = re.subn(
        r'(?m)^([ \t]*)(on_action = "\[LocationView\.OpenConstructionQueue\([^\n]+)',
        lambda match: f'{match[1]}using = tv_location_wonders_close_on_queue\n{match[0]}',
        text,
    )
    if count != expected_queue_actions:
        raise ValueError(f"Expected {expected_queue_actions} construction queue actions, found {count}")
    return text

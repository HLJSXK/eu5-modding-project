"""Load and update structured Tier-1 knowledge from agent/knowledge/*.yaml."""

import re
from datetime import date
from pathlib import Path

import yaml

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"

TASK_KEYWORDS: dict[str, list[str]] = {
    "modifier": ["modifier", "modif", "_add", "_mult", "static_modifier"],
    "gui": ["gui", "blockoverride", "widget", "text_single", "situation_card", "card_common"],
    "event": ["event", "on_action", "scripted_effect", "custom_tooltip"],
    "localization": ["locali", ".yml", "l_english", "l_simp_chinese", "encoding", "bom"],
}

DOC_SOURCES: dict[str, list[str]] = {
    "modifier": [
        "docs/guides/AI_Tool_Workflow_Prompt.md",
        "docs/technical/EU5_Modding_Knowledge_Base.md",
        "docs/task_summaries/Task_Summary_AI_Programming_Techniques_20260327.md",
    ],
    "gui": [
        "docs/guides/AI_Tool_Workflow_Prompt.md",
        "docs/technical/EU5_Mod_Framework_Guide.md",
    ],
    "event": [
        "docs/guides/AI_Tool_Workflow_Prompt.md",
        "docs/technical/EU5_Modding_Knowledge_Base.md",
    ],
    "localization": [
        "docs/guides/AI_Tool_Workflow_Prompt.md",
        "docs/technical/EU5_Mod_Framework_Guide.md",
    ],
    "general": [
        "docs/guides/AI_Tool_Workflow_Prompt.md",
        "docs/technical/EU5_Modding_Knowledge_Base.md",
    ],
}


def load_structured_knowledge() -> dict:
    """Load all knowledge/*.yaml files into a unified dict."""
    result = {}
    for yaml_file in sorted(KNOWLEDGE_DIR.glob("*.yaml")):
        with open(yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        result[yaml_file.stem] = data
    return result


def classify_task(task: str) -> str:
    task_lower = task.lower()
    for task_type, keywords in TASK_KEYWORDS.items():
        if any(kw in task_lower for kw in keywords):
            return task_type
    return "general"


def get_doc_sources(task_type: str) -> list[str]:
    return DOC_SOURCES.get(task_type, DOC_SOURCES["general"])


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_yaml(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def update_knowledge(category: str, entry: dict) -> bool:
    """Append a new entry to the appropriate knowledge YAML, with deduplication.

    Returns True if the entry was added, False if it was already present.
    """
    file_map = {
        "anti_pattern": KNOWLEDGE_DIR / "anti_patterns.yaml",
        "enum": KNOWLEDGE_DIR / "valid_enums.yaml",
        "scope": KNOWLEDGE_DIR / "scope_rules.yaml",
        "encoding": KNOWLEDGE_DIR / "encoding_rules.yaml",
    }
    target = file_map.get(category)
    if target is None:
        target = KNOWLEDGE_DIR / "anti_patterns.yaml"

    data = _load_yaml(target)

    if category == "anti_pattern":
        patterns = data.setdefault("anti_patterns", [])
        existing = {p.get("pattern") for p in patterns}
        if entry.get("pattern") in existing:
            return False
        entry.setdefault("date", str(date.today()))
        patterns.append(entry)

    elif category == "enum":
        enums = data.setdefault("enums", {})
        enum_name = entry.get("name")
        if enum_name in enums:
            return False
        enums[enum_name] = {
            "values": entry.get("values", []),
            "source": entry.get("source", "agent-discovered"),
            "notes": entry.get("notes", ""),
        }

    elif category == "scope":
        rules = data.setdefault("scope_rules", {}).setdefault("prefix_patterns", [])
        existing_prefixes = {r.get("prefix") for r in rules}
        if entry.get("prefix") in existing_prefixes:
            return False
        rules.append(entry)

    _save_yaml(target, data)
    return True

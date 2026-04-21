"""Evolve node: update agent prompt files when new verified knowledge warrants it."""

import re
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from agent.state import AgentState

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

FINDING_TO_PROMPTS = {
    "modifier": ["execute.md", "review.md"],
    "encoding": ["execute.md"],
    "enum": ["review.md"],
    "mandatory_category": ["system.md"],
    "eu5_vs_eu4": ["system.md"],
    "scope": ["execute.md", "review.md"],
    "gui": ["review.md"],
    "event": ["execute.md", "review.md"],
}


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    return path.read_text(encoding="utf-8")


def _already_in_prompt(prompt_text: str, rule: str) -> bool:
    # Rough check: if any 6-word n-gram from the rule appears in the prompt
    words = rule.split()
    if len(words) >= 6:
        ngram = " ".join(words[:6]).lower()
        return ngram in prompt_text.lower()
    return rule.lower()[:40] in prompt_text.lower()


def _append_rule_to_prompt(prompt_file: str, rule: str, today: str) -> bool:
    path = PROMPTS_DIR / prompt_file
    if not path.exists():
        return False

    text = path.read_text(encoding="utf-8")
    if _already_in_prompt(text, rule):
        return False

    learned_section = "## Learned Rules"
    rule_line = f"- [{today}] {rule}"

    if learned_section in text:
        text = text.replace(
            "<!-- New rules added here by evolve.py -->",
            f"<!-- New rules added here by evolve.py -->\n{rule_line}",
        )
        if rule_line not in text:
            # Fallback: append after the section header
            text = re.sub(
                rf"({re.escape(learned_section)}.*?\n)",
                rf"\1{rule_line}\n",
                text,
                count=1,
                flags=re.DOTALL,
            )
    else:
        text += f"\n\n{learned_section}\n{rule_line}\n"

    path.write_text(text, encoding="utf-8")
    return True


def _classify_finding(finding: str) -> str:
    finding_lower = finding.lower()
    if "modifier" in finding_lower:
        return "modifier"
    if "encoding" in finding_lower or "bom" in finding_lower:
        return "encoding"
    if "enum" in finding_lower or "location_rank" in finding_lower:
        return "enum"
    if "mandatory" in finding_lower or "forbidden" in finding_lower:
        return "mandatory_category"
    if "eu4" in finding_lower or "mean_time" in finding_lower:
        return "eu5_vs_eu4"
    if "scope" in finding_lower:
        return "scope"
    if "gui" in finding_lower or "blockoverride" in finding_lower:
        return "gui"
    if "event" in finding_lower or "custom_tooltip" in finding_lower:
        return "event"
    return "modifier"


def evolve_prompts(state: AgentState, llm: BaseChatModel | None = None) -> dict:
    new_findings = state.get("new_findings", [])
    if not new_findings:
        return {}

    from datetime import date

    today = str(date.today())
    updates: list[str] = []

    for finding in new_findings:
        category = _classify_finding(finding)
        target_files = FINDING_TO_PROMPTS.get(category, ["execute.md", "review.md"])

        for prompt_file in target_files:
            added = _append_rule_to_prompt(prompt_file, finding, today)
            if added:
                updates.append(f"Updated {prompt_file}: {finding[:80]}")

    return {"_prompt_updates": updates}

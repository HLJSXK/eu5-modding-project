"""Record node: write new findings into docs/ai_agent/knowledge_base.md and agent/knowledge/*.yaml."""

from datetime import date
from pathlib import Path

from agent.state import AgentState
from agent.tools.knowledge_loader import update_knowledge

KNOWLEDGE_BASE = Path(__file__).parent.parent.parent / "docs/ai_agent/knowledge_base.md"


def _ensure_knowledge_base() -> None:
    if KNOWLEDGE_BASE.exists():
        return
    KNOWLEDGE_BASE.parent.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_BASE.write_text(
        "# EU5 Agent Knowledge Base\n\n"
        "Running record of verified anti-patterns and corrections discovered by the agent.\n"
        "Format mirrors `docs/guides/AI_Tool_Workflow_Prompt.md`.\n\n"
        "| Date | Violation | Root cause | Correct behavior |\n"
        "|---|---|---|---|\n",
        encoding="utf-8",
    )


def _append_to_knowledge_base(finding: str, today: str) -> None:
    _ensure_knowledge_base()
    parts = [p.strip() for p in finding.split("|")]
    if len(parts) >= 3:
        row = f"| {today} | {parts[0]} | {parts[1]} | {parts[2]} |\n"
    else:
        row = f"| {today} | {finding} | agent-discovered | see finding |\n"

    with open(KNOWLEDGE_BASE, "a", encoding="utf-8") as f:
        f.write(row)


def record_findings(state: AgentState) -> dict:
    new_findings = state.get("new_findings", [])
    if not new_findings:
        return {}

    today = str(date.today())

    for finding in new_findings:
        # Append to human-readable markdown log
        _append_to_knowledge_base(finding, today)

        # Classify and append to structured YAML
        finding_lower = finding.lower()
        if "modifier" in finding_lower or "->" in finding:
            parts = finding.split("->") if "->" in finding else [finding, finding]
            update_knowledge(
                "anti_pattern",
                {
                    "pattern": parts[0].strip(),
                    "correction": parts[-1].strip(),
                    "category": "modifier",
                    "source": "agent-discovered",
                    "notes": finding,
                },
            )
        elif "location_rank" in finding_lower or "enum" in finding_lower:
            # Enum finding: try to extract enum name and values
            update_knowledge(
                "anti_pattern",
                {
                    "pattern": finding,
                    "correction": "see notes",
                    "category": "enum",
                    "source": "agent-discovered",
                    "notes": finding,
                },
            )
        elif "scope" in finding_lower:
            update_knowledge(
                "anti_pattern",
                {
                    "pattern": finding,
                    "correction": "see notes",
                    "category": "scope",
                    "source": "agent-discovered",
                    "notes": finding,
                },
            )
        else:
            update_knowledge(
                "anti_pattern",
                {
                    "pattern": finding,
                    "correction": "see notes",
                    "category": "general",
                    "source": "agent-discovered",
                    "notes": finding,
                },
            )

    return {}

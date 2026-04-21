"""Execute node: generate proposed file changes with Verification statements."""

from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from agent.state import AgentState

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _parse_proposed_changes(raw: str) -> list[dict]:
    """Best-effort parse of LLM output into structured change dicts."""
    import re

    changes = []
    blocks = re.split(r"###\s+Change:", raw)
    for block in blocks[1:]:
        lines = block.strip().splitlines()
        description = lines[0].strip() if lines else "change"
        file_match = re.search(r"^File:\s*(.+)$", block, re.MULTILINE)
        encoding_match = re.search(r"^ENCODING:\s*(.+)$", block, re.MULTILINE)
        code_match = re.search(r"```[\w]*\n([\s\S]*?)```", block)

        changes.append(
            {
                "description": description,
                "file": file_match.group(1).strip() if file_match else "unknown",
                "encoding": encoding_match.group(1).strip() if encoding_match else "n/a",
                "content": code_match.group(1) if code_match else block,
                "raw": block,
            }
        )
    return changes or [{"description": "change", "file": "unknown", "content": raw, "raw": raw}]


def execute_task(state: AgentState, llm: BaseChatModel) -> dict:
    task = state["task"]
    plan = state.get("plan", "")
    task_type = state.get("task_type", "general")
    loaded_knowledge = state.get("loaded_knowledge", [])
    structured = state.get("structured_knowledge", {})
    review_issues = state.get("review_issues", [])
    iteration = state.get("iteration", 0)

    system_prompt = _load_prompt("system") + "\n\n" + _load_prompt("execute")

    anti_patterns = structured.get("anti_patterns", {}).get("anti_patterns", [])
    anti_pattern_summary = "\n".join(
        f"- INVALID: `{p['pattern']}` → CORRECT: `{p['correction']}` ({p.get('scope','?')} scope)"
        for p in anti_patterns
    )

    knowledge_context = "\n\n".join(loaded_knowledge[:3])

    revision_note = ""
    if iteration > 0 and review_issues:
        issues_text = "\n".join(f"- {i}" for i in review_issues)
        revision_note = f"\n\nThis is revision #{iteration}. Previous review found these issues to fix:\n{issues_text}"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=f"Task: {task}\nTask type: {task_type}\n\n"
            f"Plan:\n{plan}\n\n"
            f"Known invalid modifiers:\n{anti_pattern_summary}\n\n"
            f"Reference knowledge:\n{knowledge_context}"
            f"{revision_note}\n\n"
            "Generate the proposed file changes following the required format. "
            "Include a **Verification** line before every Mandatory Category element."
        ),
    ]

    raw_output = llm.invoke(messages).content
    proposed_changes = _parse_proposed_changes(raw_output)

    return {"proposed_changes": proposed_changes}

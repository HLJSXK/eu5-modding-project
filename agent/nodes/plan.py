"""Plan node: generate a step-by-step task plan with verification requirements."""

from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from agent.state import AgentState

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def plan_task(state: AgentState, llm: BaseChatModel) -> dict:
    task = state["task"]
    task_type = state.get("task_type", "general")
    loaded_knowledge = state.get("loaded_knowledge", [])
    structured = state.get("structured_knowledge", {})

    system_prompt = _load_prompt("system") + "\n\n" + _load_prompt("plan")

    # Build context from structured knowledge anti-patterns
    anti_patterns = structured.get("anti_patterns", {}).get("anti_patterns", [])
    anti_pattern_summary = "\n".join(
        f"- INVALID: `{p['pattern']}` → CORRECT: `{p['correction']}`"
        for p in anti_patterns
    )

    knowledge_context = "\n\n".join(loaded_knowledge[:4])

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=f"Task: {task}\nTask type: {task_type}\n\n"
            f"Known invalid modifiers and corrections:\n{anti_pattern_summary}\n\n"
            f"Loaded knowledge:\n{knowledge_context}\n\n"
            "Produce a step-by-step plan for this task following the required format."
        ),
    ]

    plan_text = llm.invoke(messages).content
    return {"plan": plan_text}

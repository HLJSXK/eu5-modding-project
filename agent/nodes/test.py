"""Test node: generate a human-readable test checklist and pause for HITL feedback."""

from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt

from agent.state import AgentState

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def generate_test_checklist(state: AgentState, llm: BaseChatModel) -> dict:
    """Generate test checklist, then interrupt for human feedback."""
    proposed_changes = state.get("proposed_changes", [])

    system_prompt = _load_prompt("system")
    changes_text = "\n\n".join(
        f"File: {c.get('file')}\nDescription: {c.get('description')}\n{c.get('raw', '')[:800]}"
        for c in proposed_changes
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=f"Based on the following proposed changes, generate a numbered test checklist "
            f"for an EU5 player to verify in-game. Each item should be specific and actionable. "
            f"Focus on what the player should observe or confirm in the game UI, error.log, or mod behavior.\n\n"
            f"Proposed changes:\n{changes_text}"
        ),
    ]

    checklist = llm.invoke(messages).content

    # Interrupt here: pause the graph and surface the checklist to the human.
    # The human resumes by calling graph.invoke with Command(resume="PASS") or Command(resume="error description").
    human_response = interrupt(
        {
            "message": "Please test the changes in-game using the checklist below.",
            "checklist": checklist,
            "instructions": "Respond with 'PASS' if all checks pass, or describe any errors found.",
        }
    )

    return {
        "test_checklist": checklist,
        "human_test_result": human_response if isinstance(human_response, str) else str(human_response),
    }

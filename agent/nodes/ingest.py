"""Ingest node: load Tier-1 structured knowledge + selective Tier-2 docs."""

from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from agent.state import AgentState
from agent.tools.knowledge_loader import (
    classify_task,
    get_doc_sources,
    load_structured_knowledge,
)
from agent.tools.repo_reader import read_file, read_file_lines

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
REPO_ROOT = Path(__file__).parent.parent.parent

VIOLATIONS_LOG_PATH = "docs/guides/AI_Tool_Workflow_Prompt.md"
MAX_DOC_CHARS = 6000


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _load_doc(path: str) -> str:
    try:
        text = read_file(path)
        if len(text) > MAX_DOC_CHARS:
            text = text[:MAX_DOC_CHARS] + f"\n... (truncated, full file at {path})"
        return f"=== {path} ===\n{text}"
    except Exception:
        return f"=== {path} === (could not load)"


def ingest_knowledge(state: AgentState, llm: BaseChatModel | None = None) -> dict:
    task = state["task"]

    # Tier 1: always load structured knowledge (no LLM needed)
    structured = load_structured_knowledge()

    # Classify task
    task_type = classify_task(task)

    # Always load violations log
    violations_log = _load_doc(VIOLATIONS_LOG_PATH)

    # Tier 2: selectively load docs based on task type
    doc_paths = get_doc_sources(task_type)
    loaded_knowledge = [violations_log]

    for path in doc_paths:
        if path == VIOLATIONS_LOG_PATH:
            continue  # already loaded
        loaded_knowledge.append(_load_doc(path))

    # If LLM is available, ask it to summarize what's relevant
    if llm is not None:
        system_prompt = _load_prompt("system") + "\n\n" + _load_prompt("ingest")
        knowledge_text = "\n\n".join(loaded_knowledge[:3])  # cap context
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=f"Task: {task}\n\nTask type classified as: {task_type}\n\n"
                f"Loaded knowledge summary:\n{knowledge_text}\n\n"
                "Briefly summarize what's relevant and flag any immediate concerns."
            ),
        ]
        summary = llm.invoke(messages).content
        loaded_knowledge.append(f"=== Ingest Summary ===\n{summary}")

    return {
        "task_type": task_type,
        "structured_knowledge": structured,
        "loaded_knowledge": loaded_knowledge,
        "violations_log": violations_log,
    }

from typing import TypedDict


class AgentState(TypedDict):
    task: str
    task_type: str                 # "modifier" | "gui" | "event" | "localization" | "general"
    structured_knowledge: dict     # Tier 1: loaded from agent/knowledge/*.yaml
    loaded_knowledge: list[str]    # Tier 2: doc chunks selectively loaded
    violations_log: str            # content of AI_Tool_Workflow_Prompt.md
    plan: str
    proposed_changes: list[dict]   # [{file, content, description}]
    review_result: str             # "ACCEPTED" | "NEEDS_REVISION" | "NEEDS_ESCALATION"
    review_issues: list[str]
    test_checklist: str
    human_test_result: str         # "PASS" or error description
    iteration: int
    max_iterations: int
    new_findings: list[str]
    escalation_reason: str

"""Review node: validate proposed changes against EU5 rules."""

import re
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from agent.state import AgentState
from agent.tools.repo_reader import modifier_exists

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _deterministic_checks(proposed_changes: list[dict], structured: dict) -> list[str]:
    """Run rule checks that don't require an LLM call."""
    issues = []
    anti_patterns = {
        p["pattern"]: p["correction"]
        for p in structured.get("anti_patterns", {}).get("anti_patterns", [])
    }
    valid_enums = structured.get("valid_enums", {}).get("enums", {})
    location_rank_values = {
        v for v in valid_enums.get("location_rank", {}).get("values", [])
    }
    encoding_rules = structured.get("encoding_rules", {})

    for change in proposed_changes:
        content = change.get("content", "") + change.get("raw", "")
        file_path = change.get("file", "")

        # 1. Anti-pattern check
        for bad, good in anti_patterns.items():
            if re.search(rf"\b{re.escape(bad)}\b", content):
                issues.append(
                    f"Anti-pattern in `{file_path}`: `{bad}` is invalid → use `{good}`"
                )

        # 2. Enum validity check
        for m in re.findall(r"location_rank\s*:\s*(\w+)", content):
            if location_rank_values and m not in location_rank_values:
                issues.append(
                    f"Invalid location_rank value `{m}` in `{file_path}`. "
                    f"Valid: {sorted(location_rank_values)}"
                )

        # 3. Encoding check
        ext = Path(file_path).suffix.lower()
        if ext in (".yml", ".txt"):
            encoding = change.get("encoding", "")
            if "bom" not in encoding.lower() and "utf-8-bom" not in encoding.lower():
                issues.append(
                    f"File `{file_path}` ({ext}) must note utf-8-bom encoding requirement."
                )

        # 4. Verification statement check — look for Mandatory Category usage without a Verification line
        mandatory_patterns = [
            (r"blockoverride\s+\"", "blockoverride block name"),
            (r"custom_tooltip\s*=", "custom_tooltip key"),
            (r"location_rank\s*:", "location_rank enum"),
            (r"GetVariable|\.IsSet|MakeScope", "GUI expression syntax"),
        ]
        for pattern, desc in mandatory_patterns:
            if re.search(pattern, content):
                if "**Verification**" not in content:
                    issues.append(
                        f"`{file_path}` uses {desc} (Mandatory Category) but has no **Verification** line."
                    )
                break

        # 5. Modifier existence check for any identifier that looks like a modifier assignment
        for m in re.findall(r"\b([a-z][a-z0-9_]{4,})\s*=\s*[\d\-\.]", content):
            if m in anti_patterns:
                continue  # already caught above
            if not modifier_exists(m):
                issues.append(
                    f"Modifier `{m}` in `{file_path}` not found in 00_modifier_types.txt — verify it exists."
                )

    return issues


def review_output(state: AgentState, llm: BaseChatModel) -> dict:
    proposed_changes = state.get("proposed_changes", [])
    structured = state.get("structured_knowledge", {})
    violations_log = state.get("violations_log", "")
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 3)

    # Deterministic checks first (no LLM cost)
    det_issues = _deterministic_checks(proposed_changes, structured)

    # LLM review for nuanced issues
    system_prompt = _load_prompt("system") + "\n\n" + _load_prompt("review")
    changes_text = "\n\n".join(
        f"File: {c.get('file')}\n{c.get('raw', c.get('content', ''))}"
        for c in proposed_changes
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=f"Review these proposed changes for EU5 correctness:\n\n{changes_text}\n\n"
            f"Violations log context:\n{violations_log[:2000]}\n\n"
            f"Deterministic checks already found these issues:\n"
            + ("\n".join(f"- {i}" for i in det_issues) or "(none)")
            + "\n\nComplete the review using the required format."
        ),
    ]

    llm_review = llm.invoke(messages).content

    # Parse result from LLM output
    if "NEEDS_ESCALATION" in llm_review or iteration >= max_iterations:
        review_result = "NEEDS_ESCALATION"
        escalation_reason = llm_review
    elif "NEEDS_REVISION" in llm_review or det_issues:
        review_result = "NEEDS_REVISION"
        escalation_reason = ""
    else:
        review_result = "ACCEPTED"
        escalation_reason = ""

    # Collect all issues
    llm_issues = re.findall(r"^-\s+(.+)$", llm_review, re.MULTILINE)
    all_issues = det_issues + [i for i in llm_issues if i not in det_issues]

    # Extract new findings mentioned in the LLM review
    new_findings = []
    findings_match = re.search(r"### New Findings.*?\n([\s\S]*?)(?=###|$)", llm_review)
    if findings_match:
        for line in findings_match.group(1).splitlines():
            line = line.strip().lstrip("- ").strip()
            if line:
                new_findings.append(line)

    return {
        "review_result": review_result,
        "review_issues": all_issues,
        "new_findings": new_findings,
        "escalation_reason": escalation_reason,
        "iteration": iteration + 1,
    }

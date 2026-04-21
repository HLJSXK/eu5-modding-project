"""LangGraph workflow definition for the EU5 mod agent.

Per-node model configuration via env vars:
  AGENT_MODEL_INGEST, AGENT_MODEL_PLAN, AGENT_MODEL_EXECUTE,
  AGENT_MODEL_REVIEW, AGENT_MODEL_TEST, AGENT_MODEL_EVOLVE

Provider is auto-detected from model name: claude-* → Anthropic, else → OpenAI.
Falls back to ANTHROPIC_MODEL / OPENAI_MODEL if the per-node var is not set.
"""

import os
from functools import partial

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agent.nodes.evolve import evolve_prompts
from agent.nodes.execute import execute_task
from agent.nodes.ingest import ingest_knowledge
from agent.nodes.plan import plan_task
from agent.nodes.record import record_findings
from agent.nodes.review import review_output
from agent.nodes.test import generate_test_checklist
from agent.state import AgentState
from agent.tools.llm_factory import make_llm


def _route_review(state: AgentState) -> str:
    result = state.get("review_result", "NEEDS_REVISION")
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 3)

    if result == "ACCEPTED":
        return "test"
    if result == "NEEDS_ESCALATION" or iteration >= max_iter:
        return "escalate"
    return "revise"


def _route_after_test(state: AgentState) -> str:
    human_result = state.get("human_test_result", "")
    if isinstance(human_result, str) and human_result.strip().upper() == "PASS":
        return "record"
    return "revise_after_test"


def _revise_output(state: AgentState, llm: BaseChatModel) -> dict:
    return execute_task(state, llm)


def _format_escalation(state: AgentState) -> dict:
    reason = state.get("escalation_reason", "")
    issues = state.get("review_issues", [])
    print("\n=== ESCALATION: Agent could not resolve all issues ===")
    print("Reason:", reason or "(max iterations reached)")
    print("Outstanding issues:")
    for issue in issues:
        print(" -", issue)
    print("======================================================\n")
    return {}


def build_graph(max_iterations: int = 3) -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("ingest",           partial(ingest_knowledge,      llm=make_llm("ingest")))
    graph.add_node("plan",             partial(plan_task,              llm=make_llm("plan")))
    graph.add_node("execute",          partial(execute_task,           llm=make_llm("execute")))
    graph.add_node("review",           partial(review_output,          llm=make_llm("review")))
    graph.add_node("test",             partial(generate_test_checklist,llm=make_llm("test")))
    graph.add_node("revise",           partial(_revise_output,         llm=make_llm("execute")))
    graph.add_node("revise_after_test",partial(_revise_output,         llm=make_llm("execute")))
    graph.add_node("escalate",         _format_escalation)
    graph.add_node("record",           record_findings)
    graph.add_node("evolve",           partial(evolve_prompts,         llm=make_llm("evolve")))

    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "review")
    graph.add_conditional_edges("review", _route_review, {"test": "test", "revise": "revise", "escalate": "escalate"})
    graph.add_edge("revise", "review")
    graph.add_conditional_edges("test", _route_after_test, {"record": "record", "revise_after_test": "revise_after_test"})
    graph.add_edge("revise_after_test", "review")
    graph.add_edge("escalate", END)
    graph.add_edge("record", "evolve")
    graph.add_edge("evolve", END)

    return graph


def compile_graph(max_iterations: int = 3, checkpointer=None):
    graph = build_graph(max_iterations)
    cp = checkpointer or MemorySaver()
    return graph.compile(checkpointer=cp)


def make_initial_state(task: str, max_iterations: int = 3) -> AgentState:
    return AgentState(
        task=task,
        task_type="general",
        structured_knowledge={},
        loaded_knowledge=[],
        violations_log="",
        plan="",
        proposed_changes=[],
        review_result="",
        review_issues=[],
        test_checklist="",
        human_test_result="",
        iteration=0,
        max_iterations=max_iterations,
        new_findings=[],
        escalation_reason="",
    )

"""CLI entry point for the EU5 mod agent."""

import argparse
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

# Load .env from repo root or agent/ directory
for env_path in [Path(__file__).parent / ".env", Path(__file__).parent.parent / ".env"]:
    if env_path.exists():
        load_dotenv(env_path)
        break

from langgraph.types import Command

from agent.graph import compile_graph, make_initial_state


def _print_state_summary(state: dict) -> None:
    print(f"\n--- Task type: {state.get('task_type', '?')} ---")
    print(f"Plan:\n{state.get('plan', '(none)')}\n")

    changes = state.get("proposed_changes", [])
    print(f"Proposed changes ({len(changes)}):")
    for c in changes:
        print(f"  [{c.get('file', '?')}] {c.get('description', '')}")

    result = state.get("review_result", "?")
    issues = state.get("review_issues", [])
    print(f"\nReview result: {result}")
    if issues:
        print("Issues:")
        for i in issues:
            print(f"  - {i}")


def run_task(task: str, max_iterations: int = 3, dry_run: bool = False) -> None:
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    print(f"\n=== EU5 Mod Agent ===")
    print(f"Task: {task}")
    print(f"Max iterations: {max_iterations}")
    if dry_run:
        print("DRY RUN: no files will be written\n")

    graph = compile_graph(max_iterations=max_iterations)
    initial_state = make_initial_state(task, max_iterations)

    # Set dry_run env so record/evolve nodes can respect it
    if dry_run:
        os.environ["AGENT_DRY_RUN"] = "1"
    else:
        os.environ.pop("AGENT_DRY_RUN", None)

    # Run graph; it will pause when interrupt() fires inside the test node
    graph.invoke(initial_state, config)

    current_state = graph.get_state(config)

    # Check if the graph is interrupted (tasks have pending interrupts)
    interrupted = bool(current_state.tasks and any(t.interrupts for t in current_state.tasks))

    if interrupted:
        # Retrieve interrupt value (contains message and checklist from test node)
        interrupt_value = {}
        for task in current_state.tasks:
            if task.interrupts:
                interrupt_value = task.interrupts[0].value or {}
                break

        checklist = interrupt_value.get("checklist", "")
        message = interrupt_value.get("message", "Test the proposed changes in-game.")

        print(f"\n=== TEST CHECKLIST ===")
        print(message)
        if checklist:
            print("\n" + checklist)
        else:
            # Fallback: list proposed changes
            changes = current_state.values.get("proposed_changes", [])
            for c in changes:
                print(f"  [{c.get('file', '?')}] {c.get('description', '')}")

        print("\n=====================")
        print(interrupt_value.get("instructions", "Enter 'PASS' or describe errors:"))

        human_response = input("> ").strip()
        if not human_response:
            human_response = "PASS"

        # Resume graph with human feedback
        graph.invoke(Command(resume=human_response), config)

    # Final summary
    final_state = graph.get_state(config).values
    _print_state_summary(final_state)

    new_findings = final_state.get("new_findings", [])
    if new_findings:
        print(f"\nNew findings recorded ({len(new_findings)}):")
        for f in new_findings:
            print(f"  - {f}")

    human_result = final_state.get("human_test_result", "")
    if human_result.upper() == "PASS":
        print("\n✓ Task completed and human-tested.")
    elif final_state.get("escalation_reason"):
        print("\n⚠ Task escalated — human intervention required.")
    else:
        print("\nDone.")


def interactive_loop(max_iterations: int = 3) -> None:
    print("EU5 Mod Agent — interactive mode. Type 'exit' to quit.\n")
    while True:
        try:
            task = input("Task> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if task.lower() in ("exit", "quit", "q"):
            break
        if not task:
            continue
        run_task(task, max_iterations=max_iterations)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="EU5 Mod Agent — LangGraph-based coding assistant"
    )
    parser.add_argument("task", nargs="?", help="Task description")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive prompt loop")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing files")
    parser.add_argument("--max-iter", type=int, default=3, help="Max revision iterations (default 3)")
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set. Add it to .env or export it.", file=sys.stderr)
        sys.exit(1)

    if args.interactive:
        interactive_loop(max_iterations=args.max_iter)
    elif args.task:
        run_task(args.task, max_iterations=args.max_iter, dry_run=args.dry_run)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

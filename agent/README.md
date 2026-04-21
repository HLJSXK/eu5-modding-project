# EU5 Mod Agent

A LangGraph-based AI coding assistant for EU5 mod development. Reads the repository's own docs/logs/reference files as the source of truth, enforces the 3-Step Resolution Rule, and evolves its own constraints from each run.

---

## Setup

1. Install dependencies:
   ```bash
   pip install -r agent/requirements.txt
   ```

2. Set API keys. Create `agent/.env` or `.env` at the repo root:
   ```
   ANTHROPIC_API_KEY=sk-ant-...        # used by review node (Claude)
   OPENAI_API_KEY=sk-...               # used by all other nodes (Codex/GPT)
   ANTHROPIC_MODEL=claude-sonnet-4-6   # optional, default shown
   OPENAI_MODEL=gpt-4o                 # optional, default shown
   ```

   Model routing: **review → Claude**, **ingest/plan/execute/test/evolve → Codex (OpenAI)**.

---

## Usage

```bash
# Single task
python -m agent.main "Add a local_monthly_control modifier to the SOL building"

# With options
python -m agent.main "Add a new .yml localization file" --dry-run
python -m agent.main "Fix the location_rank filter" --max-iter 5

# Interactive loop
python -m agent.main --interactive
```

### Options

| Flag | Description |
|------|-------------|
| `--dry-run` | Print proposed changes without writing any files |
| `--max-iter N` | Max revision cycles before escalation (default: 3) |
| `--interactive` | Continuous prompt loop |

---

## Workflow

```
ingest → plan → execute → review → [revise loop] → test (HITL) → record → evolve
```

1. **ingest** — Load structured knowledge (Tier 1: `agent/knowledge/*.yaml`) and select relevant docs (Tier 2).
2. **plan** — Produce a step-by-step plan with mandatory verification statements.
3. **execute** — Generate proposed file changes with `**Verification**` lines for all Mandatory Category syntax.
4. **review** — Auto-check modifier names, enums, encoding, scope, anti-patterns. LLM does a deeper review.
5. **revise loop** — Fix issues and re-review (up to `--max-iter` times).
6. **test (HITL)** — Agent pauses and presents a test checklist. You test in-game and respond PASS or describe errors.
7. **record** — Verified new findings are written to `docs/ai_agent/knowledge_base.md` and `agent/knowledge/*.yaml`.
8. **evolve** — New rules are appended to the relevant `agent/prompts/*.md` files so future runs use them immediately.

If the agent cannot resolve issues, it escalates with a report of what it couldn't verify.

---

## Knowledge Architecture

### Tier 1 — Structured (fast, no LLM)
`agent/knowledge/`
- `anti_patterns.yaml` — known invalid modifiers and their replacements
- `valid_enums.yaml` — verified enum values (e.g., `location_rank`)
- `scope_rules.yaml` — prefix-to-scope mapping rules
- `encoding_rules.yaml` — file encoding requirements

These are loaded first on every run. The review node uses them for deterministic checks.

### Tier 2 — Docs (selective, LLM context)
Loaded only when structured knowledge is insufficient:
- `docs/guides/AI_Tool_Workflow_Prompt.md` — always loaded (violations log)
- `docs/technical/EU5_Modding_Knowledge_Base.md`
- `reference_official_defines/types/` — type definitions
- `reference_game_files/game/main_menu/common/modifier_type_definitions/00_modifier_types.txt`

### Self-Evolution
Prompts live in `agent/prompts/*.md` and are loaded at runtime (not hardcoded).
After a successful run, `record.py` updates `docs/ai_agent/knowledge_base.md` and the YAML files.
`evolve.py` then patches the prompt files so the next run has the new rules built in.

---

## Extending the System

### Add a new task type
In `agent/tools/knowledge_loader.py`:
```python
TASK_KEYWORDS["my_type"] = ["keyword1", "keyword2"]
DOC_SOURCES["my_type"] = ["docs/path/to/relevant_doc.md"]
```

### Add a new model provider
In `agent/graph.py`, replace `ChatAnthropic` with any LangChain-compatible chat model:
```python
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-4o")
```

### Add a new agent role / node
1. Create `agent/nodes/my_node.py` with a function `my_node(state, llm) -> dict`
2. Add it to `agent/graph.py` with `graph.add_node("my_node", partial(my_node, llm=llm))`
3. Wire edges as needed

### Add a new review check
In `agent/nodes/review.py`, add a check to `_deterministic_checks()` for zero-LLM-cost rules,
or extend the LLM review prompt in `agent/prompts/review.md`.

---

## Files Modified by the Agent

The agent proposes changes but does **not** automatically write them to mod source files.
Proposed changes are shown as structured output with file paths and content.
Apply them manually or extend `agent/nodes/execute.py` with a file-writing step after human approval.

The only files the agent writes automatically are:
- `docs/ai_agent/knowledge_base.md` — new findings log
- `agent/knowledge/*.yaml` — structured knowledge updates
- `agent/prompts/*.md` — prompt evolution

---

## Troubleshooting

| Problem | Solution |
|---------|---------|
| `ANTHROPIC_API_KEY not set` | Add key to `.env` at repo root or `agent/.env` |
| Agent escalates on first run | Check `agent/knowledge/anti_patterns.yaml` — the modifier may need to be added |
| Review always fails encoding check | Run `.\scripts\ensure-utf8bom.ps1` on the target directory |
| Test checklist is empty | The HITL interrupt fires before the test node generates the checklist; enter PASS or describe what you see |

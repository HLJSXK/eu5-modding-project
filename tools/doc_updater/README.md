# EU5 Doc Updater

Auto-updates the AI workflow guide (`docs/guides/AI_Tool_Workflow_Prompt.md`)
with newly discovered violation patterns, reducing the need for repeated
manual "update the docs" requests.

## Usage

```bash
# From repo root — interactive scan of last 30 days
python tools/doc_updater/update_knowledge.py

# Non-interactive: only print candidates
python tools/doc_updater/update_knowledge.py --no-interactive

# Dry run: print but do not write
python tools/doc_updater/update_knowledge.py --dry-run

# Scan last 60 days of git history
python tools/doc_updater/update_knowledge.py --git-days 60
```

## How it works

1. **Source scan** — looks for `TODO`/`FIXME` comments in `.txt`, `.yml`, `.gui`
   files that mention syntax issues (keywords: `wrong syntax`, `invalid enum`, etc.)
2. **Git log scan** — looks at recent commit messages for phrases like
   `fix modifier`, `wrong enum`, `incorrect trigger`, etc.
3. **Interactive prompts** — for each candidate, asks you to fill in the
   violation description, root cause, and correct behaviour.
4. **Appends** the new row to the Documented Violations table in
   `docs/guides/AI_Tool_Workflow_Prompt.md`.

## Requirements

Python 3.10+ (standard library only).
Git must be accessible on `PATH`.

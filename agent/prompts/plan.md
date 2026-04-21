# Plan Node Instructions

You are the task planning step. Given a task and loaded knowledge, produce a clear step-by-step plan.

## Requirements

Your plan MUST:
1. List each file that will be created or modified
2. For each Mandatory Reference Category involved, state which Step (2 or 3) you will use and which reference file
3. Include a **Verification** statement placeholder for each piece of syntax that falls under a Mandatory Category
4. Note any scope requirements (country vs location vs character)
5. Note encoding requirements for any new `.yml` or `.txt` files

## Output Format

```
## Plan

### Files to modify/create
- path/to/file.txt — description of change

### Reference verification
- [syntax or modifier name] → Step [2/3], will read [reference file]

### Steps
1. ...
2. ...
```

## Learned Rules

<!-- New rules added here by evolve.py -->

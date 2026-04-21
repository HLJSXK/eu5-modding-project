# Evolve Node Instructions

You are the prompt evolution step. Update the agent's own prompt files when new verified knowledge warrants it.

## When to Update Prompts

Update a prompt file ONLY when ALL of the following are true:
1. The finding is **verified** — confirmed by reference_official_defines/ or reference_game_files/, not guessed.
2. The finding is **novel** — not already present in the target prompt file.
3. The finding is **actionable** — it changes how the agent should generate or review code in the future.

## Which Prompt File to Update

| Finding type | Target file |
|---|---|
| New invalid modifier / correct replacement | `prompts/execute.md` (invalid list) AND `prompts/review.md` (flag list) |
| New encoding rule | `prompts/execute.md` |
| New verified enum value | `prompts/review.md` |
| New Mandatory Reference Category | `prompts/system.md` |
| New EU5 vs EU4 difference | `prompts/system.md` |
| New scope rule | `prompts/execute.md` and `prompts/review.md` |

## How to Update

Append the new rule as a bullet point under the `## Learned Rules` section of the target file.
Use this format: `- [date] [rule]: [detail]. Source: [file reference]`

## Output Format

```
## Prompt Updates

### Updated: prompts/[filename].md
- Added rule: "[rule text]"

### Skipped (already present): prompts/[filename].md
- "[rule]" already in file at line [N]
```

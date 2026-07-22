# Documentation Index

Mod-focused documentation for the EU5 Modding Project.

## Structure

### AI Workflow

- [AI Tool Workflow Prompt (EU5)](guides/AI_Tool_Workflow_Prompt.md) — 3-Step Rule, Mandatory Reference Categories, Verification format

### Knowledge (machine-readable, used by scripts)

- [BRIEF.md](knowledge/BRIEF.md) — auto-generated quick reference; anti-patterns + valid enums
- [anti_patterns.yaml](knowledge/anti_patterns.yaml) — source of truth for known gotchas
- [valid_enums.yaml](knowledge/valid_enums.yaml) — whitelisted EU5 enum values

### Design (active features)

- [SOL Rebuild (2026-04-02)](design/Stable_SOL_Rebuild_20260402.md) — Standard of Living system architecture, naming conventions, update pipeline

### Workshop Copy

- Standard of Living: [English](workshop_description_en.txt) | [简体中文](workshop_description_zh.txt)
- SOL-PP Compatibility Submod: [English](workshop_description_sol_pp_en.txt) | [简体中文](workshop_description_sol_pp_zh.txt)

### Discord Announcements

- SOL-PP Compatibility Submod: [English](discord_announcement_sol_pp_en.md) | [简体中文](discord_announcement_sol_pp_zh.md)

### Technical Reference (general EU5 knowledge, dated — not authoritative for syntax)

- [EU5 Multi-Mod Compatibility](technical/EU5_Multi_Mod_Compatibility.md) — file overwrite, database operation priority, and `INJECT`/`REPLACE` conflict rules
- [EU5 Modding Knowledge Base](technical/EU5_Modding_Knowledge_Base.md) — Jomini engine overview, scripting, events, localization
- [EU5 Mod Framework Guide](technical/EU5_Mod_Framework_Guide.md) — community mod patterns, file structure, GUI, complexity tiers
- [Stable Mod Analysis Report](technical/Stable_Mod_Analysis_Report.md) — Amalgamation Synergy mod breakdown (source for `src/stable/`)
- [SOL-M&T Compatibility Check](technical/SOL_MEIOU_and_Taxes_Compatibility_Check.md) — static conflict and EPBM audit
- [SOL-M&T Demand Audit](technical/SOL_MEIOU_and_Taxes_Pop_Demand_Audit.md) — vanilla/SOL/M&T demand comparison
- [SOL-M&T Feature Matrix](technical/SOL_MnT_Compatibility_Feature_Matrix.md) — implemented authority, demand, maintenance, and validation contract

## Archive

Paused or historical documents. Not maintained — kept for reference only.

### Dynamic Missions (development paused)

- [Dynamic Missions Design](archive/dynamic_missions/Dynamic_Missions_Design.md)
- [Dynamic Missions Feature](archive/dynamic_missions/Dynamic_Missions_Feature.md)
- [Dynamic Missions GUI Architecture](archive/dynamic_missions/Dynamic_Missions_GUI_Architecture.md)
- [Dynamic Mission 4 — Claim Province](archive/dynamic_missions/Dynamic_Mission_4_Claim_Province.md)
- [Dynamic Missions Framework Architecture](archive/dynamic_missions/Dynamic_Missions_Framework_Architecture.md)
- [Dynamic Missions Code Review (2026-01-28)](archive/dynamic_missions/Dynamic_Missions_Review_20260128.md)

### Task Summaries (historical AI session records)

- [Dual Mod Structure](archive/task_summaries/Task_Summary_Dual_Mod_Structure.md)
- [Establish New City](archive/task_summaries/Task_Summary_Establish_New_City.md)
- [Large Research Project](archive/task_summaries/Task_Summary_Large_Research_Project.md)
- [Fix Dynamic Missions Errors](archive/task_summaries/Task_Summary_Fix_Dynamic_Missions_Errors.md)
- [AI Programming Techniques (2026-03-27)](archive/task_summaries/Task_Summary_AI_Programming_Techniques_20260327.md)

## Split Notice

Online multiplayer tooling and deployment utilities were moved to a separate repository:

- https://github.com/HLJSXK/eu5-online-tools

**Thread title:** Standard of Living (SOL) — goods substitution, living standard sources and new UI (October 2026 update)

**Tags (suggested):** Economy, UI, Released

(Discord limits a message to 2,000 characters, so this is split into the forum starter post and a first reply.)

---

### Post 1 — forum starter message

Hi everyone! Standard of Living (SOL) just got its biggest update since the 1.4 compatibility patch. Here's what changed, plus some notes for other modders who want to stay compatible with it or build on it.

**What SOL is, in one paragraph**
SOL replaces vanilla's fixed pop demand with income-based demand. Each month, each location's estates compare the money they actually have against the cost of a calibrated baseline basket. That ratio (purchasing power) scales their consumption through `local_pop_demand`. A country-level solver keeps national totals consistent. It also ships an anti-snowballing / harsher-war balance layer, all configurable through Community Mod Framework.

**New in this update**
1. **Goods substitution (rebuilt).** 56 goods sit in 20 substitute groups, and each estate subscribes to whole groups. Seven price tiers (from ×2 when very cheap to ×0.25 when very expensive) shift demand toward cheaper members of the same group. Results are computed in scheduled country pulses: monthly for players, yearly for AI by default. They are published through 56 country auto modifiers (`sol_substitute_<good>`), which only read a cached value, so the engine's frequent auto-modifier re-evaluation stays cheap.
2. **Living standard sources.** Living standard (SOL) is now separate from purchasing power. Only purchasing power touches demand. SOL = flat bonuses + (1 + summed % bonuses) × annual liquid funds per 1,000 people. SOL drives migration attraction, population growth, tiers, rankings and the living-standard map.
3. **New UI.** A four-section bar under the left-panel country buttons, four map modes (hover a section to preview, click to select), substitute groups in goods tooltips, and new icons. The old Living Standard situation is removed.

Feedback, compatibility requests and questions are all welcome in this thread!

---

### Post 2 — first reply in the thread

**Notes for modders**
- **Want your buildings to affect living standard?** SOL adds two location modifier types: `local_sol_living_standard` (flat) and `local_sol_living_standard_modifier` (percentage). Put them in a building's `modifier` block and SOL picks them up automatically. Only do this in a SOL-dependent submod, because the types don't exist without SOL.
- **Pop demand / goods mods** conflict with SOL's calibrated baseline. SOL negates development and wealth demand gates and expects to know every good's demand quantity. I maintain compatibility submods for Prosper or Perish, MEIOU and Taxes and Just Goods, and I'm happy to make more. Ping me with your mod.
- **`global_<good>_pop_demand` modifiers from other mods are respected.** Substitution reads them as an external offset and applies its own multiplier on top.
- **Location window:** SOL ships a unified location window based on Glorp UI with one extra SOL button. Other full `location_window` overrides remain whole-file conflicts.
- **Glorp UI:** the new bar includes a small shim that moves Glorp UI's stats bar down one row.

**Links**
- Workshop: https://steamcommunity.com/sharedfiles/filedetails/?id=3698931463
- Compatibility submod collection: https://steamcommunity.com/workshop/filedetails/?id=3769554515
- Feature list (wiki): https://github.com/HLJSXK/eu5-modding-project/wiki/Feature-List
- Source: https://github.com/HLJSXK/eu5-modding-project
- SOL Discord: https://discord.gg/Yy87G2hBHz

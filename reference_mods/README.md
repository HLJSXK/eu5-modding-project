# Community Mod References

This directory contains 12 community mods from Steam Workshop, serving as reference materials for learning EU5 modding patterns, structures, and vanilla game variables.

## 📚 Purpose

These mods are included to help developers:

1. **Learn mod structure** - See how real mods are organized
2. **Study code patterns** - Understand common scripting approaches
3. **Reference vanilla variables** - Find game-defined variables, triggers, and effects
4. **Understand best practices** - Learn from successful community mods
5. **Explore different mod types** - See examples of various modding approaches

## 🎮 Included Mods

### Translation Mods

| ID | Name | Size | Description |
|----|------|------|-------------|
| 3599957897 | Beyond the Cape CN Translation | 384K | Chinese translation mod - good example of localization structure |
| 3599706198 | 凯撒汉化 | 6.1M | Caesar Chinese localization - comprehensive translation example |
| 3600570317 | New World Improvement Project 汉化 | 1.5M | NWIP Chinese translation - shows translation of complex mods |

**Learning Focus:** Localization file structure, UTF-8 BOM encoding, translation key organization

### Gameplay Mods

| ID | Name | Size | Description |
|----|------|------|-------------|
| 3599116549 | Europa Expanded | 1.3M | Gameplay expansion - events, mechanics, balance changes |
| 3603092142 | Historical Tweaks | 4.5M | Balance mod - country modifiers, historical adjustments |
| 3605031777 | Historic Decentralization & Control | 1.7M | Government mechanics - decentralization system |
| 3606278744 | Mission Trees - Ambi | 11M | Mission system - complex mission trees and objectives |

**Learning Focus:** Event scripting, modifiers, triggers, effects, mission definitions

### UI & Interface Mods

| ID | Name | Size | Description |
|----|------|------|-------------|
| 3601047146 | Glorp UI | 18M | UI overhaul - extensive GUI modifications |
| 3605677866 | Better Road Builder | 1.3M | UI improvement - interface enhancements |
| 3610757528 | Expanded Build View | 496K | UI extension - build interface modifications |

**Learning Focus:** GUI file structure, interface scripting, UI layout patterns

### Mechanics Mods

| ID | Name | Size | Description |
|----|------|------|-------------|
| 3601937478 | Dense Tech Tree | 368K | Technology mod - tech tree modifications |
| 3626895335 | More stable HRE | 636K | Diplomatic mod - HRE stability improvements |

**Learning Focus:** Technology definitions, diplomatic mechanics, game balance

## 📖 How to Use These References

### For Learning Mod Structure

1. **Start with small mods** (300-500K):
   - `3601937478` (Dense Tech Tree)
   - `3599957897` (Beyond the Cape CN Translation)
   - `3626895335` (More stable HRE)

2. **Progress to medium mods** (1-5M):
   - `3599116549` (Europa Expanded)
   - `3603092142` (Historical Tweaks)
   - `3605031777` (Historic Decentralization & Control)

3. **Study complex mods** (5M+):
   - `3606278744` (Mission Trees - Ambi)
   - `3601047146` (Glorp UI)

### For Finding Vanilla Variables

**Common locations to search:**

```bash
# Find all trigger definitions
grep -r "trigger = {" reference_mods/

# Find modifier usage
grep -r "add_modifier" reference_mods/

# Find event patterns
grep -r "namespace =" reference_mods/

# Find localization keys
grep -r "^[[:space:]]*[a-zA-Z_].*:.*\"" reference_mods/ --include="*.yml"
```

### For Studying Specific Systems

#### Events System
- Look at: `3599116549/in_game/events/`
- Look at: `3606278744/in_game/events/`

#### Modifiers
- Look at: `3603092142/in_game/common/static_modifiers/`
- Look at: `3605031777/in_game/common/`

#### Localization
- Look at: `3599957897/main_menu/localization/`
- Look at: `3599706198/main_menu/localization/`

#### GUI
- Look at: `3601047146/in_game/gui/`
- Look at: `3610757528/in_game/gui/`

#### Missions
- Look at: `3606278744/in_game/common/missions/`

## 🔍 Quick Reference Guide

### Common File Locations

```
mod_directory/
├── .metadata/
│   └── metadata.json           # Mod information
├── in_game/
│   ├── common/                 # Game logic definitions
│   │   ├── decisions/          # Player decisions
│   │   ├── events/             # Event definitions (some mods)
│   │   ├── generic_actions/    # Generic actions
│   │   ├── missions/           # Mission definitions
│   │   ├── on_action/          # On-action triggers
│   │   ├── scripted_triggers/  # Reusable triggers
│   │   ├── situations/         # Situation definitions
│   │   └── static_modifiers/   # Modifier definitions
│   ├── events/                 # Event scripts (main location)
│   ├── gui/                    # GUI definitions
│   └── map_data/               # Map modifications
├── main_menu/
│   └── localization/           # Translation files
└── README.md                   # Mod documentation
```

### Common Patterns to Study

1. **Event Structure**
   ```
   namespace = mod_name
   
   mod_name.1 = {
       type = country_event
       title = event_title_key
       desc = event_desc_key
       
       trigger = { ... }
       option = { ... }
   }
   ```

2. **Modifier Definition**
   ```
   modifier_name = {
       country_modifier = yes
       icon = "modifier_icon"
       
       tax_income_mult = 0.1
       manpower_recovery_speed = 0.05
   }
   ```

3. **Localization Format**
   ```yaml
   l_english:
     key_name: "Translated Text"
     key_name_desc: "Description text"
   ```

## 📊 Mod Statistics

| Category | Count | Total Size | Avg Size |
|----------|-------|------------|----------|
| Translation | 3 | 8.0M | 2.7M |
| Gameplay | 4 | 18.5M | 4.6M |
| UI/Interface | 3 | 19.8M | 6.6M |
| Mechanics | 2 | 1.0M | 500K |
| **Total** | **12** | **~47M** | **3.9M** |

## ⚠️ Important Notes

### Copyright & Attribution

These mods are created by community members and are included here for **educational and reference purposes only**. All rights belong to their original creators.

**Original Sources:** Steam Workshop (IDs listed above)

### Usage Guidelines

1. **Do not redistribute** these mods as your own
2. **Do not copy code** without understanding it
3. **Use as reference** to learn patterns and structures
4. **Credit original authors** if you adapt their techniques
5. **Respect licenses** of individual mods

### Limitations

- These mods may be for different game versions
- Some code may be outdated or non-optimal
- Always test and verify code before using
- Refer to official documentation for current best practices

## 🔗 Related Documentation

- [EU5 Modding Knowledge Base](../docs/technical/EU5_Modding_Knowledge_Base.md) - Comprehensive modding guide
- [EU5 Mod Framework Guide](../docs/technical/EU5_Mod_Framework_Guide.md) - Practical framework
- [Mod Structure Analysis](../docs/technical/Mod_Structure_Analysis.txt) - Analysis of these mods
- [Template Mod](../src/template_mod/) - Minimal starting template
- [Dynamic Missions Mod](../src/dynamic_missions/) - Complete example mod

## 🛠️ Recommended Workflow

### For New Modders:

1. **Start with documentation**
   - Read the EU5 Modding Knowledge Base
   - Study the Mod Framework Guide

2. **Explore small mods**
   - Browse `3601937478` (Dense Tech Tree)
   - Study `3626895335` (More stable HRE)

3. **Use the template**
   - Copy `../src/template_mod/`
   - Modify for your needs

4. **Reference these mods**
   - Search for specific patterns
   - Learn from working examples

### For Experienced Modders:

1. **Quick reference**
   - Search for vanilla variables
   - Find complex pattern examples

2. **Study advanced features**
   - GUI modifications in `3601047146`
   - Mission systems in `3606278744`

3. **Adapt patterns**
   - Extract useful techniques
   - Integrate into your mods

## 📝 Contributing

If you find useful patterns or insights from these mods, consider:

1. Documenting them in the knowledge base
2. Creating examples in the template mod
3. Sharing findings with the community

---

**Last Updated:** January 28, 2026  
**Total Mods:** 12  
**Total Size:** ~47MB  
**Source:** Steam Workshop

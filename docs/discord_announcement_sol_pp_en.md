# SOL x Prosper or Perish Compatibility Submod

Standard of Living and Prosper or Perish can now be used together with a dedicated compatibility submod.

**Workshop page:**
https://steamcommunity.com/sharedfiles/filedetails/?id=3769565170

This is a compatibility patch, not a standalone mod. It requires SOL, PP, and Community Mod Framework.

## What the combined setup looks like

- **Prosper or Perish leads the combined economy.** PP keeps control of its food system, population growth and migration, food storage, buildings, production methods, rural capacity, roads, and shared location balance.
- **SOL keeps its core system.** Income-based dynamic pop demand, the Living Standard situation and map, and the location UI remain active.
- **PP goods are handled correctly by SOL.** Victuals are included in SOL calculations and displays, while PP's zero lumber pop demand is preserved.
- **A compact selection of SOL balance rules remains.** This includes selected construction, tax, diplomacy, war-exhaustion, colonial, and non-conflicting price rules.

## Why the submod is required

SOL and PP both edit pop demand, goods, food and climate balance, RGO and location values, roads, age scaling, and war-related modifiers. Loading only the two main mods can cause some changes to overwrite each other while others stack twice.

The compatibility submod resolves those overlaps as one PP-led ruleset instead of leaving the result to load order. It also fixes SOL's missing victuals accounting and prevents SOL from restoring lumber pop demand.

## Required mods and load order

1. [Community Mod Framework](https://steamcommunity.com/sharedfiles/filedetails/?id=3692202776)
2. [Prosper or Perish](https://steamcommunity.com/sharedfiles/filedetails/?id=3613232232)
3. [Standard of Living](https://steamcommunity.com/sharedfiles/filedetails/?id=3698931463)
4. [SOL-PP Compatibility Submod](https://steamcommunity.com/sharedfiles/filedetails/?id=3769565170)

**The compatibility submod must be below both PP and SOL.**

A new campaign is recommended. After a major SOL or PP update, check that the compatibility submod has also been updated before starting a long campaign.

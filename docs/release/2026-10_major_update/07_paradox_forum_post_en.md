**Where to post:** reply in the existing thread — [MOD] Standard of Living - Dynamic Economy Mod
https://forum.paradoxplaza.com/forum/threads/mod-standard-of-living-dynamic-economy-mod.1916241/
(page 1 currently ends in June 2026 with the v1.3 beta changelog, so this posts as the next reply)

**Notes:** BBCode. Links allowed. Pure update post — no corrections, no retreading of the original OP.

---

[B]October 2026 update[/B]

This is the biggest change since the 1.4 compatibility rebuild, and it restores the one system the 1.3 beta had to cut: goods substitution. It is now rebuilt on a new foundation, and living standard has been split away from money.

[B]Goods substitution[/B]

The 56 goods are organised into 20 substitute groups: staples, protein, clothing, heating, crude goods, seasoning, household goods, drinks, fine drinks, luxuries, spices, precious metals, treasures, medicine, ritual goods, weapons, mounts, knowledge goods and others. Estates consume whole groups rather than named goods, so a peasant needs [I]a[/I] staple, not wheat specifically.

Within a group, seven price tiers move the spending shares. The price is measured as market price divided by default price:

[TABLE]
[TR][TH]Price vs default[/TH][TH]Demand weight[/TH][/TR]
[TR][TD]below 0.40[/TD][TD]× 2.00[/TD][/TR]
[TR][TD]0.40 – 0.65[/TD][TD]× 1.50[/TD][/TR]
[TR][TD]0.65 – 0.85[/TD][TD]× 1.25[/TD][/TR]
[TR][TD]0.85 – 1.30[/TD][TD]× 1.00[/TD][/TR]
[TR][TD]1.30 – 1.70[/TD][TD]× 0.75[/TD][/TR]
[TR][TD]1.70 – 2.30[/TD][TD]× 0.50[/TD][/TR]
[TR][TD]above 2.30[/TD][TD]× 0.25[/TD][/TR]
[/TABLE]

A price sitting exactly on a boundary stays in the milder tier, so 2.30 still counts as × 0.50 and 0.40 as × 1.50. There is no hysteresis; tiers are re-evaluated on a yearly cadence so they do not oscillate month to month. When wheat reaches twice its base price it loses share to rice, millet and legumes, and a dirt-cheap good pulls demand toward itself. The result is published per country as a Goods substitution modifier for that good, and the whole feature can be switched off in CMF.

[B]Living standard is more than money[/B]

Purchasing power still decides what pops buy. Living standard is now a separate score that adds what money cannot buy: hospitals, lazarettos, pest houses, aqueducts and famous medical institutions raise it, tanneries, putrefaction works and iron and steel mills pollute and lower it, and theatres, opera houses and libraries raise it by a percentage. A high living standard attracts migrants and speeds population growth, a very low one slows it, and every country and every estate gets a world ranking.

[B]The interface[/B]

The situation panel is replaced by a permanent four-section bar beneath the country buttons: living standard with its tier and year-on-year change, purchasing power, goods substitution, and world ranking, each with a detailed tooltip. Hovering previews a map mode, clicking opens it. Four map modes in total, substitute groups and price tiers inside goods tooltips, an entry in the location window, and Glorp UI compatibility.

[B]Baselines and cadence[/B]

Baseline baskets are recalibrated to 1340 country medians, and the AI now recalculates its economy yearly by default while players stay on a monthly cycle. A new campaign is strongly recommended: older saves load, but the caches and market prices need time to settle and the result will not be representative.

[B]Balance layer[/B]

Unchanged in structure and still fully toggleable through CMF: −15% base tax efficiency by default, halved difficulty tax bonuses, costs scaling by age with roads at two to five times vanilla, harsher winters and raised levies, faster war exhaustion with real economic damage from siege and occupation, AI colonial charters gated behind a 500 tax base, and the smaller items — paid generals and advisors, diplomatic spending scaling with used capacity, GDP converting into development, and the optional AI prosperity recovery.

[B]Compatibility[/B]

Community Mod Framework 2.x is now required. Compatibility submods for Prosper or Perish, MEIOU and Taxes and Just Goods are updated alongside SOL Standalone.

[URL=https://steamcommunity.com/sharedfiles/filedetails/?id=3698931463]Steam Workshop[/URL] · [URL=https://steamcommunity.com/workshop/filedetails/?id=3769554515]Compatibility submods[/URL] · [URL=https://github.com/HLJSXK/eu5-modding-project/wiki/Feature-List]Full feature list[/URL] · [URL=https://discord.gg/Yy87G2hBHz]Discord[/URL]

I am also posting a separate thread going into how the substitution system works internally, for anyone who wants the actual implementation rather than the pitch. Feedback is welcome in either place.

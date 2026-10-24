**Sub-forum:** Europa Universalis V → User Mods (or the pinned mod index thread)
**Thread prefix:** [Mod]
**Thread title:** [Mod] Standard of Living (SOL) — income-based pop demand, goods substitution, living standard
**Icons/prefix notes:** Paradox forums have no flair; use the [Mod] prefix and, if the sub-forum asks for one, the standard mod index format in the first line.

---

[b]Standard of Living (SOL)[/b]
[i]Income-based pop demand · goods substitution · living standard[/i]

[url=https://steamcommunity.com/sharedfiles/filedetails/?id=3698931463]Steam Workshop[/url] · [url=https://github.com/HLJSXK/eu5-modding-project/wiki/Feature-List]Full feature list[/url] · [url=https://discord.gg/Yy87G2hBHz]Discord[/url]

---

Hello everyone. I have been working on [b]Standard of Living (SOL)[/b] since EU5 launched, and this is my first proper thread about it here. The mod has just received its biggest update, so this post covers the whole thing rather than only the changelog.

[h2]Why the mod exists[/h2]

Vanilla pop demand is fixed and low. A pop buys the same small basket whether it is starving or prosperous, nothing ever substitutes for anything, and estates have little to spend their surplus on beyond rebels and the occasional building. The consequence shows up mid-campaign: in one of my France games the nobility held [b]245,000 ducats[/b] while the country's entire tax base was around 3,000. More than ten years of national income, sitting idle. The market only functions because the state keeps constructing end-consumer buildings and purchasing the goods itself.

[h2]What SOL changes[/h2]

[b]Pops spend what they actually earn.[/b] Each month, every estate in every location works out the money it really has: its share of local income, less building upkeep, adjusted according to how its national savings compare against a savings target. That figure is set against the local cost of a calibrated baseline basket. The ratio is the estate's [b]purchasing power[/b], and it scales how much the estate consumes. Wealthy nobles buy far more horses and fine cloth; poor peasants cut back. Hoarding now peaks and then declines, because savings above the target push spending upward, and a country-level solver keeps national totals consistent. Development no longer gates or scales demand at all; SOL replaces that system.

[b]Goods substitution.[/b] This is the centrepiece of the update. The 56 goods are grouped into 20 substitute groups — staples, protein, clothing, heating, crude goods, seasoning, household goods, drinks, fine drinks, luxuries, spices, precious metals, treasures, medicine, ritual goods, weapons, mounts and others. Estates demand whole categories rather than specific goods, so peasants need [i]a[/i] staple, not wheat specifically. Seven price tiers move spending within a group: when wheat reaches twice its base price, demand shifts to rice, millet or legumes, and when a good is very cheap, estates buy more of it. The effect is published per country as "Goods substitution" modifiers. I first built this in 1.1 alongside Engel curves; a 1.2 engine change broke the interface it depended on and it was dead for months. It is now rebuilt on a much cheaper foundation.

[b]Living standard is more than money.[/b] Purchasing power decides what people buy; living standard is a separate score that adds the things money cannot buy. Hospitals, lazarettos, pest houses, aqueducts and famous medical institutions raise it. Tanneries, putrefaction works and iron and steel mills pollute and lower it. Theatres, opera houses and libraries raise it by a percentage. It feeds back into the world: a higher living standard attracts migrants, a very low one slows population growth and a high one accelerates it. Every country and every estate within it receives a world ranking.

[b]A proper interface.[/b] A four-section bar now sits beneath the country buttons, showing living standard (tier and year-on-year change), purchasing power, goods substitution and world ranking, each with a detailed tooltip. Hovering a section previews its map mode and clicking opens it. There are four map modes in total, goods tooltips that display substitute groups and price tiers, and a SOL entry in the location window. It is compatible with Glorp UI.

[h2]The balance layer[/h2]

A richer economy snowballs harder, so SOL ships a balance package derived from Anti Snowballing, configurable part by part through Community Mod Framework.

Base tax efficiency is −15% by default and adjustable. Difficulty tax bonuses for Hard and Very Hard AI, and for Easy and Very Easy players, are halved. Each age makes expansion more expensive: building efficiency, RGO expansion cost, city and town upgrade cost and food consumption all worsen, and roads cost two to five times more, so a country cannot be paved in twenty years. Normal winters and raised levies hit local food harder, so food production has to come before economic construction, though Little Ice Age events are softened to prevent unrecoverable death spirals.

War is more costly. War exhaustion grows faster under occupation and damages levies, control, stability, legitimacy and defence, while sieges, occupation, looting and razing inflict real economic damage. This has the pleasant side effect of ending wars sooner instead of letting them become endless siege slogs. The AI requires a tax base of at least 500 to charter colonies, with historical colonisers exempt and players unrestricted. Generals, admirals and advisors cost gold, diplomatic spending scales with used capacity, GDP gradually converts into development, and there is an optional AI prosperity recovery.

[h2]Playing it[/h2]

Early Europe grows slowly, deliberately, reflecting late-medieval stagnation and the Black Death. Reduce food purchases early and repair food production first. Most countries reach vanilla's tax base around 1400 and then grow faster on genuine demand. For a first campaign, normal AI is recommended; once the system is familiar, harder AI is the better experience, because the AI manages food less well than a player will. A new campaign is strongly recommended.

[h2]Compatibility[/h2]

SOL requires [b]Community Mod Framework 2.x[/b]. Compatibility submods exist for [b]Prosper or Perish[/b], [b]MEIOU and Taxes[/b] and [b]Just Goods[/b], and there is [b]SOL Standalone[/b], which provides the demand and living-standard systems without the balance layer. Mods that alter pop demand or goods will conflict unless a submod is used; ask in this thread and I will look into it, as building one is not difficult. Mods that override the entire location window will conflict with SOL's location window. For those interested in the technical side, the Discord server and the wiki hold the implementation notes.

[h2]Credits[/h2]

SOL began as a combination and extension of two discontinued mods: [b]SoL Based Pop Demands[/b] by 1onepower and [b]Anti Snowballing[/b] by Ethereal. My thanks to both.

[url=https://steamcommunity.com/sharedfiles/filedetails/?id=3698931463]Steam Workshop[/url] · [url=https://steamcommunity.com/workshop/filedetails/?id=3769554515]Compatibility submods[/url] · [url=https://github.com/HLJSXK/eu5-modding-project/wiki/Feature-List]Feature list[/url] · [url=https://discord.gg/Yy87G2hBHz]Discord[/url]

I would be glad to hear how your economies develop, and I will answer any questions in this thread.

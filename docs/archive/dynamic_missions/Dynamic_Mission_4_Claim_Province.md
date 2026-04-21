# Dynamic Mission 4: Claim Province

**Date:** January 28, 2026  
**Author:** Manus AI  
**Version:** 1.0

## 1. Introduction

The "Claim Province" dynamic mission introduces a high-stakes diplomatic and military crisis centered around territorial expansion. It allows a player to formally stake a claim on a neighboring province, initiating a five-year period of escalating tensions. This system is designed to create dynamic, narrative-driven conflicts that go beyond traditional casus belli mechanics, involving intricate diplomatic maneuvering, espionage, and a climactic ultimatum that can lead to a major war or a peaceful transfer of territory.

This document provides a comprehensive overview of the mission's design, mechanics, and event chains, serving as a guide for players and a reference for future development.

## 2. Mission Activation and Goals

The mission becomes available to a human player who meets a specific set of criteria, designed to ensure the claim is both logical and impactful.

#### Trigger Conditions

A player can initiate the "Claim Province" mission from the main Dynamic Missions menu if the following conditions are met:

- The player's nation must share a border with a province owned by another nation.
- The target province cannot belong to a subject of the player.
- The player must not have another Dynamic Mission active.
- The player must possess at least 200 gold and 10 prestige to signal their serious intent.

Upon selection, the player is presented with a list of all eligible neighboring provinces and their current owners, allowing for a strategic choice of target.

#### Core Objective

The primary goal is to secure ownership of the claimed province within the five-year time limit. Success is defined by the province's owner changing to the player, whether through diplomatic capitulation or military conquest initiated by the mission's final event.

## 3. Core Gameplay Loop

Once a province is claimed, a five-year situation, the "Provincial Claim Crisis," begins. This period is characterized by a set of unique player actions and a tense diplomatic standoff. The situation can conclude in one of several ways, as detailed in the table below.

| End Condition | Description |
| :--- | :--- |
| **Success** | The player gains ownership of the province before the time limit expires, typically through a separate, unrelated war. |
| **Ultimatum** | The five-year timer expires, forcing the player to either declare war or back down. |
| **Capitulation** | The target nation surrenders the province in the face of overwhelming force during the ultimatum phase. |
| **Reconciliation** | A (future) option allowing both sides to peacefully resolve the crisis, improving relations. |
| **Player Retreat** | The player chooses to back down during the ultimatum, ending the crisis with a loss of prestige. |

## 4. Player Actions and Espionage

During the five-year crisis, the player has access to a suite of special actions, primarily centered around diplomacy and espionage. These actions are designed to weaken the target nation and build a coalition of support for the player's claim. All espionage actions require an established spy network in the target country.

| Action | Cost / Requirement | Effect |
| :--- | :--- | :--- |
| **Seek Rival Support** | 10 Prestige | Invites all rivals of the target nation to join the player's cause. Their acceptance is based on a complex calculation of their relationship with both the player and the target. |
| **Fabricate Legitimacy** | 20 Spy Network | Grants the player **+1 Diplomatic Reputation** for the duration of the crisis, making it easier to gain support and improving relations. |
| **Incite Panic** | 30 Spy Network | Inflicts a **-30% Fort Defense** penalty on all locations within the target province, making a potential invasion easier. |
| **Contact Surrender Faction** | 40 Spy Network | Immediately inflicts **+5 War Exhaustion** on the target nation, weakening their stability and willingness to fight. |
| **Conduct Border Reconnaissance** | 200 Manpower (Annual) | Grants the player **+5 Army Tradition**, representing the military experience gained from scouting and border skirmishes. |

## 5. AI Diplomacy and The Ultimatum

The target nation is not passive during this crisis. The AI will also attempt to secure its own alliances and may call upon its own supporters, including rivals of the player, creating a complex web of diplomatic intrigue. The player will be notified if the target successfully brings new allies into its defensive coalition.

### The Ultimatum Event

If the five years pass without the province changing hands, the crisis comes to a head with the **Ultimatum Event**. The player is presented with a final choice:

1.  **Declare War:** This triggers the final phase of the crisis. The player declares war with a special "Claim Province" casus belli, which provides a **-25% discount** on conquest and annexation costs for the target province. All rivals who previously agreed to support the player will automatically join the war.
2.  **Back Down:** The player abandons the claim, resulting in a loss of **10 Prestige**, while the target nation gains **10 Prestige**.

If the player chooses to declare war, the target nation receives its own event. The AI's decision to fight or surrender is based on a cold calculation of military strength.

> The AI will only surrender if the total military strength of the player's coalition (the player plus all supporters) is at least **five times greater** than the total strength of its own defensive coalition (the target nation, its allies, its defensive pact members, and any nations guaranteeing its independence). This high threshold ensures that surrender only occurs in the face of truly overwhelming and hopeless odds.

If the target fights, a major war erupts. If the target surrenders, the province is transferred to the player, and the crisis ends peacefully.

## 6. Rewards and Consequences

The resolution of the "Claim Province" crisis has significant consequences for all involved parties, primarily affecting prestige and territory.

| Outcome | Player Effect | Target Effect |
| :--- | :--- | :--- |
| **Successful Conquest/Surrender** | Gains province, **+10 Prestige** | Loses province, **-10 Prestige** |
| **Player Backs Down** | **-10 Prestige** | **+10 Prestige** |
| **Reconciliation** | **+20 Opinion** with target | **+20 Opinion** with player |

## 7. Design Philosophy

The "Claim Province" mission was designed to add a layer of narrative depth to territorial expansion. The five-year buildup allows for a period of strategic planning and diplomatic maneuvering that is often missing from the simple declaration of war. The high threshold for AI surrender is intentional, making diplomatic victory a challenging but rewarding goal that requires significant preparation. The espionage actions provide meaningful ways to impact the target nation before a war even begins, making the spy network a more crucial tool in a player's arsenal.

By creating this structured, multi-stage crisis, the mod aims to generate memorable stories of brinkmanship, betrayal, and hard-won conquest.

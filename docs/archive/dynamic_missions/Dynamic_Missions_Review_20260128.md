# EU5 Dynamic Missions System: Code and Design Review

**Author:** Manus AI  
**Date:** January 28, 2026

## 1. Executive Summary

This report provides a comprehensive review of the Dynamic Missions system within the European Universalis 5 Modding Project. The analysis covers three specific missions: "Develop City," "Large Research Project," and "Establish New City." The system's foundation is robust, featuring a modular structure and clear organization that facilitates future expansion. However, the review identified several areas requiring attention to ensure full functionality, maintainability, and alignment with the project's design principles.

Key findings include inconsistencies between design documentation and implementation, redundant files, missing code components such as events and decisions, and incomplete architectural features like the mission pool selection mechanism. Furthermore, code style varies across different files, and localization is incomplete for the two most recently added missions. This report details these issues and provides a clear set of actionable recommendations to rectify them, aiming to enhance the system's quality and completeness.

## 2. Introduction

The purpose of this review was to assess the current state of the Dynamic Missions system and its three implemented missions. The evaluation focused on four primary areas: the existence of redundant code or documentation, the functional correctness of the implementation against its design, the consistency of the coding style, and the overall completeness of the system's architecture. By systematically analyzing the project's documentation and source code, this review aims to provide a clear path toward a polished and fully realized feature.

## 3. Analysis and Findings

The review process involved a thorough examination of the `docs` and `src/develop` directories. The findings are categorized below.

### 3.1. Documentation Discrepancies

A review of the project's documentation revealed several inconsistencies and redundancies.

- **Redundant Design Documents:** The primary design document, `Dynamic_Missions_Design.md`, contains detailed designs for the "Large Research Project" and "Establish New City" missions. However, separate, more up-to-date design files also exist for these missions (`Large_Research_Project_Design.md` and `Establish_New_City_Mission_Design.md`). This creates a maintenance burden and potential for conflicting information.

- **Missing Document:** Multiple `README.md` files reference a document at `docs/design/Dynamic_Missions_Feature.md`, which does not exist in the repository. This results in broken links and missing information for developers trying to understand the feature.

- **Unimplemented Designs:** The file `docs/design/New_Missions_Design.md` contains detailed designs for two additional missions, "Military Expansion" and "Technological Breakthrough." While the designs are well-documented, they are currently only implemented as non-functional placeholders in the code, which could be confusing.

### 3.2. Functional Correctness and Implementation Gaps

Several discrepancies were found between the intended design and the actual code, leading to incomplete or non-functional components.

| Mission/Component | Issue Description | Impact |
| :--- | :--- | :--- |
| **Develop City** | The subject actions `dm_steal_progress` and `dm_contribute_development` trigger notification events (`dynamic_missions.10` and `.11`) that are not defined. | The player receives no notification when subjects interact with the mission. |
| **Develop City** | The situation's `on_monthly` block references an AI evaluation event (`dynamic_missions.100`) that does not exist. | Subject AI cannot perform its intended actions within the situation. |
| **Large Research Project** | The "Increase Research Funding" action is designed as a toggleable decision but is missing from the decisions file. | Players cannot use a key intended action for this mission. |
| **Large Research Project** | The `on_ended` block contains a `TODO` comment to clean up the appointed scientist's character modifier but lacks the implementation. | The character debuff remains permanently after the mission ends. |
| **Establish New City** | The "Appoint Regional Governor" event calculates a dynamic control bonus but applies a generic, non-functional modifier. | The governor's skills have no effect on the mission's outcome. |
| **Establish New City** | The town selection event (`dynamic_missions.30`) does not allow the player to choose a specific town, instead offering only the capital or a random town. | Player agency is limited, contrary to the design's intent. |

### 3.3. Code Style and Consistency

The codebase exhibits inconsistencies in formatting and naming conventions, which can hinder readability and maintenance.

- **Event Syntax:** Two different syntaxes are used for defining events. Older events use `country_event = { id = ... }`, while newer ones use `dynamic_missions.X = { type = country_event ... }`. A single, consistent format should be adopted.

- **Localization Keys:** The naming convention for localization keys is inconsistent. Some keys follow the `dynamic_missions.X.title` pattern, while others use a `dm_action_name.t` format. Furthermore, the localization file is missing all keys for the "Large Research Project" and "Establish New City" missions.

- **Option Naming:** In the main mission selection event (`dynamic_missions.1`), the options are named `option_a`, `option_c`, and `option_d`, skipping `option_b`. This is a minor but unnecessary inconsistency.

### 3.4. Architectural Completeness

The overall system architecture is not fully implemented as designed in the `Dynamic_Missions_Framework_Architecture.md` document.

- **Missing On-Action Hook:** The system currently relies on manual triggering. There is no `on_action` file to automatically present the mission selection event to the player on a periodic basis (e.g., yearly), which is a critical component for a truly "dynamic" system.

- **Simplified Mission Selection:** The design specifies a mission pool where four random, valid missions are presented to the player. The current implementation simply shows all available missions as options in a single event, deviating from the more dynamic and scalable pool-based design.

## 4. Recommendations

To address the issues identified, the following actions are recommended. They are prioritized to focus on functionality and completeness first.

| ID | Category | Recommended Action |
|:---|:---|:---|
| 1 | **Architecture** | Create an `on_action` file (e.g., `on_yearly_pulse`) to periodically trigger the `dynamic_missions.1` event for eligible players. |
| 2 | **Localization** | Add all missing localization keys for the "Large Research Project" and "Establish New City" missions to the `dynamic_missions_l_english.yml` file. |
| 3 | **Functionality** | Implement the missing decision for the "Increase Research Funding" action in the `dynamic_missions_decisions.txt` file. |
| 4 | **Functionality** | Implement the missing notification events (`.10`, `.11`) and the AI evaluation event (`.100`) in the `dynamic_missions_events.txt` file. |
| 5 | **Functionality** | Correct the `on_ended` logic in the `large_research_project_situation` to properly remove the `dm_lead_scientist_debuff` modifier from the appointed character. |
| 6 | **Functionality** | Refactor the `dynamic_missions.31` event to correctly apply a dynamic modifier based on the governor's skills. |
| 7 | **Architecture** | Refactor the `dynamic_missions.1` event to implement the mission pool selection mechanism as described in the architecture document. |
| 8 | **Code Style** | Standardize all event definitions to a single format (`namespace.id = { ... }`). |
| 9 | **Documentation** | Consolidate the detailed mission designs into their individual files and revise `Dynamic_Missions_Design.md` to serve as a high-level overview, linking to the specific documents. |
| 10 | **Documentation** | Remove all broken links pointing to the non-existent `Dynamic_Missions_Feature.md` file. |

## 5. Conclusion

The Dynamic Missions system is a promising feature with a solid conceptual and structural foundation. The identified issues, while numerous, are largely related to incomplete implementation and a lack of polish rather than fundamental design flaws. By systematically addressing the recommendations outlined in this report, the project team can significantly improve the system's quality, align it with its original design, and deliver a more robust and engaging experience for players. Prioritizing functional completeness and architectural integrity will ensure the system is both scalable and maintainable in the long term.

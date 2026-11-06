# Lesson 1.4 — MITRE ATT&CK Framework

## Lesson Metadata
- **Module:** 1 — Introduction to Malware & Exploitation
- **Lesson:** 4 of 5
- **Difficulty:** Foundational
- **Estimated duration:** 20 minutes
- **Prerequisites:** Lesson 1.3

## Learning Objectives
1. Explain what ATT&CK stands for and what problem it was built to solve relative to the kill chain.
2. Name the ATT&CK matrix structure: Tactics (the "why"), Techniques/Sub-techniques (the "how"), and Procedures (the specific real-world implementation).
3. Navigate the public ATT&CK Enterprise matrix to find a technique's ID, description, detections, and associated groups/software.
4. Map a short technical action to a specific ATT&CK technique ID (not just a tactic).

## Conceptual Explanation

**MITRE ATT&CK** (Adversarial Tactics, Techniques, and Common Knowledge) is a publicly available, community-contributed knowledge base of real-world adversary behavior, maintained by MITRE since 2013 (first published 2015). Where the kill chain gives seven broad linear stages, ATT&CK gives a much finer-grained, matrix-structured model that is explicitly *not* strictly linear — an adversary can and does use techniques from multiple tactic categories in any order, repeatedly, throughout an intrusion.

**The three-level structure:**

- **Tactics** — the adversary's tactical goal, answering "why" (e.g., Initial Access, Execution, Persistence, Privilege Escalation, Defense Evasion, Credential Access, Discovery, Lateral Movement, Collection, Command and Control, Exfiltration, Impact). These map loosely onto kill-chain stages but there are more of them, and they're explicitly not ordered — an adversary might revisit "Discovery" five times across an intrusion.
- **Techniques and sub-techniques** — the "how," a specific method of achieving a tactic's goal, each with a stable ID (e.g., **T1059** "Command and Scripting Interpreter," with sub-techniques like **T1059.001** "PowerShell"). This is the level of detail an analyst actually works at day to day.
- **Procedures** — the concrete, real-world implementation of a technique by a specific threat actor or in a specific malware family (documented on the technique's page under "Procedure Examples"), e.g., "Group G0007 (APT28) has used T1059.001 to execute PowerShell scripts for X purpose."

**Matrices.** ATT&CK publishes separate matrices for Enterprise (Windows/macOS/Linux/cloud/network/containers), Mobile, and ICS (industrial control systems), reflecting that technique sets genuinely differ by platform.

**What each technique page gives you.** A technique ID, a description, platforms it applies to, mitigations (defensive measures mapped to that specific technique), detections (what log sources/data to look for), and — critically for this course — lists of real groups (threat actors) and software (malware/tools) documented using it, each sourced and citable.

**Why ATT&CK matters practically, beyond vocabulary.** It gives defenders a common language to describe detections precisely ("we have coverage for T1055 Process Injection via Sysmon event ID 8" is far more actionable than "we detect injection-type stuff"), lets red teams/adversary-emulation exercises (Module 11, Capstone Track C) scope engagements by technique rather than vaguely, and lets analysts compare two threat-intel reports objectively by their technique IDs rather than by prose descriptions that might use different words for the same behavior.

**Relationship to the kill chain.** Use the kill chain to narrate the overall arc of an intrusion to a non-technical audience; use ATT&CK to document, detect, and compare the specific techniques within (and across repeated passes of) that arc. A mature SOC/detection-engineering practice (Module 11) is usually organized around ATT&CK technique coverage, not kill-chain stage coverage.

## Instructor Script

"The kill chain gave us seven boxes describing the overall shape of an attack. MITRE ATT&CK — Adversarial Tactics, Techniques, and Common Knowledge, first published around 2015 and maintained by MITRE as a free, public, community-contributed knowledge base — gives us the fine print inside those boxes, and it deliberately does not force everything into one straight line.

Here's the structure, and I want this three-level breakdown to be automatic for you by the end of this course. At the top, Tactics — the adversary's goal, the 'why.' Initial Access, Execution, Persistence, Privilege Escalation, Defense Evasion, Credential Access, Discovery, Lateral Movement, Collection, Command and Control, Exfiltration, Impact. Notice there are more of these than kill-chain stages, and critically, they're not ordered. A real adversary might come back to Discovery five separate times over the course of an intrusion, as they land on new systems and need to re-orient.

Below Tactics sit Techniques and Sub-techniques — the 'how,' and this is the level you'll actually work at day to day as an analyst. Each one has a stable ID you'll see constantly: T1059 is Command and Scripting Interpreter, and T1059.001, a sub-technique, is specifically PowerShell. These IDs are the common language — when two analysts, or two different vendor reports, both reference T1059.001, you know they're talking about exactly the same thing, even if they used completely different words to describe it in prose.

Below that, Procedures — the actual, real-world, documented implementation. Every technique page lists procedure examples: specific threat groups and specific malware families that have been documented, with sourced citations, using that exact technique for a specific purpose. This is where ATT&CK stops being theoretical and becomes a research tool — you can go look up a technique and see exactly who's used it and how.

A practical note: ATT&CK isn't one single matrix. There's an Enterprise matrix covering Windows, macOS, Linux, cloud, network infrastructure, and containers. There's a separate Mobile matrix. There's a separate ICS matrix for industrial control systems. That split exists because the realistic technique set genuinely differs by platform — what you'd see on a compromised PLC looks nothing like what you'd see on a compromised laptop.

Go look at an actual technique page right now in your head, or better, pull one up after this video: you'll see the technique ID and description, which platforms it applies to, documented mitigations — defensive measures specific to that technique — documented detections, meaning what log sources and what specifically to look for, and then those procedure examples we just talked about, listing real groups and real software.

Why does any of this matter beyond giving you vocabulary? Three concrete reasons. First, it lets defenders be precise. Saying 'we detect injection-type stuff' tells nobody anything useful. Saying 'we have detection coverage for T1055, Process Injection, via Sysmon event ID 8' is something another analyst can actually verify, build on, or identify a gap in. Second, it lets red teams and adversary-emulation exercises — which you'll do yourself in Module 11 and possibly in your Capstone — scope an engagement by specific technique rather than some vague notion of 'try to hack it.' Third, it lets you compare two different threat-intel reports objectively. If report A and report B both cite T1566.001, you know they're both talking about spear-phishing via attachment, regardless of how differently each vendor's prose described it.

Last point, and this ties straight back to last lesson: use the kill chain when you need to narrate the overall shape of an intrusion to someone who doesn't want twenty technique IDs — a non-technical executive, say. Use ATT&CK when you need to actually document, detect, or compare specific techniques. And here's something worth internalizing now: a mature detection-engineering practice, which we build toward in Module 11, is almost always organized around ATT&CK technique coverage — 'which of these hundreds of techniques do we actually have a working detection for' — not kill-chain stage coverage. That's the operational payoff of the extra detail."

## Practical Demonstration

Live browser walkthrough of https://attack.mitre.org/: open the Enterprise matrix, click into **T1059** (Command and Scripting Interpreter), show the description, sub-techniques list, Mitigations section, Detection section, and scroll to Procedure Examples to show two real, named group/software entries with their citations. Then open one Groups page (e.g., a well-documented group) and show its technique list and software list, pointing out the "associated software" and "techniques used" tables as the connective tissue between Tactics/Techniques/Procedures.

## Hands-On Lab

**Lab objective:** map five short technical actions to specific ATT&CK technique IDs using only the public site, and find one real procedure example for each.

- **Required tools:** web browser, https://attack.mitre.org/
- **Exercise instructions:**
  1. For each of five provided short action descriptions (`assessments/` worksheet) — e.g., "attacker uses a scheduled task to run a script every reboot," "attacker dumps credentials from LSASS memory," "attacker exfiltrates data over DNS queries" — find and record the specific technique ID (and sub-technique where applicable).
  2. For each, record one procedure example (group or software) listed on that technique's page, with the citation ATT&CK itself provides.
  3. Identify which kill-chain stage (Lesson 1.3) each action most closely corresponds to, to practice translating between the two models.
- **Expected observations:** several actions will have a clear single best-fit sub-technique; at least one is likely to be defensible under two adjacent techniques — the worksheet should note the ambiguity and justify the chosen one rather than hide it.
- **Validation steps:** instructor/peer check that technique IDs are exact (including sub-technique suffix where one exists) and that the cited procedure example is genuinely present on that technique's page.
- **Troubleshooting:** if a search on the ATT&CK site returns too many candidate techniques, narrow using the Tactic filter first (e.g., filter to "Credential Access" before searching for LSASS-related techniques).
- **Cleanup/reset:** none required.

## Knowledge Assessment

1. **(MC)** What does ATT&CK stand for? **A)** Advanced Threat Tracking and Countermeasure Knowledgebase **B)** Adversarial Tactics, Techniques, and Common Knowledge **C)** Automated Threat Tracing and Correlation Kit **D)** Attack Taxonomy and Threat Catalog
   **Answer: B.**

2. **(MC)** Which best describes the relationship between Tactics and Techniques? **A)** They're interchangeable terms **B)** Tactics are the "why" (goal); Techniques are the "how" (method) **C)** Techniques always have exactly one Tactic and vice versa in a strict one-to-one mapping **D)** Tactics are more granular than Techniques
   **Answer: B.**

3. **(Technical reasoning)** Why is it more useful for two SOC analysts to say "T1055" to each other than to say "process injection stuff"?
   **Answer:** The technique ID refers to one precisely-defined, documented technique with a stable public page (description, detections, mitigations, procedures); prose descriptions can vary in meaning between speakers, while the ID guarantees both analysts mean exactly the same documented behavior.

4. **(MC)** Which of the following is a published ATT&CK matrix? **A)** Enterprise **B)** Residential **C)** Automotive **D)** Retail
   **Answer: A.** (Enterprise, Mobile, and ICS are the published matrices.)

5. **(Scenario)** You read two vendor reports on what might be the same campaign. Report A describes "the actor used PowerShell to run obfuscated scripts." Report B cites "T1059.001." How would you confirm whether these describe the same technique?
   **Answer:** Look up T1059.001 on ATT&CK (Command and Scripting Interpreter: PowerShell) and compare its description against Report A's prose — if they match, both reports are describing the same technique even though only one used the ID explicitly; this is exactly the kind of cross-report comparison ATT&CK IDs are designed to enable.

6. **(MC)** A "Procedure Example" on an ATT&CK technique page represents: **A)** A hypothetical, unverified scenario **B)** A documented, cited instance of a specific group or software actually using that technique **C)** A list of all possible techniques a group could theoretically use **D)** A recommended mitigation
   **Answer: B.**

7. **(Technical reasoning)** Why doesn't ATT&CK enforce a strict linear order on its Tactics the way the kill chain's seven stages are ordered?
   **Answer:** Real intrusions revisit the same tactical goals multiple times (e.g., Discovery after each lateral move), and techniques from different tactics can be interleaved in any order depending on the adversary's situation — a strict linear model would misrepresent that reality, so ATT&CK is structured as a matrix of tactics/techniques rather than an ordered chain.

## Further Learning

- MITRE ATT&CK home — https://attack.mitre.org/
- MITRE ATT&CK Navigator (for building visual coverage heatmaps, used again in Module 11) — https://mitre-attack.github.io/attack-navigator/
- MITRE ATT&CK Design and Philosophy paper — https://attack.mitre.org/resources/
- *Extension:* build a one-page ATT&CK Navigator layer marking every technique ID found in this lesson's lab, as a template to reuse in Module 10's mapping lab.

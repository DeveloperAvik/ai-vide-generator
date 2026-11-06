# Lesson 1.2 — Malware Classifications and APTs

## Lesson Metadata
- **Module:** 1 — Introduction to Malware & Exploitation
- **Lesson:** 2 of 5
- **Difficulty:** Foundational
- **Estimated duration:** 22 minutes
- **Prerequisites:** Lesson 1.1

## Learning Objectives
1. Classify a described sample by propagation mechanism (virus/worm/trojan) and by function (ransomware, rootkit, spyware/keylogger, RAT, downloader/dropper, wiper, botnet client).
2. Explain why a single real-world sample often spans multiple classification axes at once.
3. Define "APT" precisely and list the four or five traits that distinguish an APT from opportunistic/commodity malware.
4. Explain what a "threat actor" naming convention (e.g., vendor-assigned APT numbers/animal names) does and does not tell you.

## Conceptual Explanation

**Two independent classification axes.** Malware is most usefully classified along two separate dimensions that are often conflated:

1. **Propagation mechanism** — how it gets from one place to another:
   - *Virus*: attaches to/modifies an existing host program or file; requires that host to execute to spread.
   - *Worm*: self-propagating; spreads across a network without needing a host file or (usually) user interaction.
   - *Trojan*: disguises itself as or is bundled with something the user wants; relies on the user (or another process) to execute it voluntarily; does not self-propagate.

2. **Functional payload** — what it does once running:
   - *Ransomware*: encrypts (or claims to encrypt) victim data/systems and demands payment.
   - *Rootkit*: hides its own or another program's presence, typically by subverting OS-level visibility (hooking APIs, kernel-mode manipulation — theory covered in Module 9).
   - *Spyware/keylogger*: covertly collects information (keystrokes, screen contents, credentials).
   - *RAT (Remote Access Trojan)*: gives an operator interactive remote control.
   - *Downloader/dropper*: a small first-stage program whose job is to fetch and install a further payload.
   - *Wiper*: destroys data/availability, sometimes disguised as ransomware (NotPetya is the canonical example — Module 10).
   - *Botnet client/bot*: joins a C2-controlled network of compromised hosts for coordinated use (DDoS, spam, proxying).

A single real sample is almost always a point on *both* axes at once — e.g., "a trojanized downloader that installs a RAT with rootkit-like hiding behavior." Treating these as one list rather than two independent axes is the single most common classification mistake, and it matters practically: propagation mechanism drives *containment* decisions (do I need to isolate the whole network segment, or just this host?), while functional payload drives *impact* and *response* decisions (do I need a ransomware playbook or a data-theft playbook?).

**Advanced Persistent Threat (APT).** "APT" is not a malware family — it is a *threat-actor* classification, describing *how an adversary operates*, regardless of which specific malware they use on a given day. The term was originally coined within U.S. Air Force/DoD circles in the mid-2000s to describe intrusions with characteristics that didn't fit the "smash and grab" opportunistic-crime model. An actor earns the "APT" label by combining:

- **Advanced**: not necessarily zero-day-heavy, but capable of using custom tooling, careful operational tradecraft, and adapting technique to the target (contrast with "advanced" being mistakenly read as "always uses novel exploits" — many APTs rely heavily on well-known techniques executed patiently and carefully).
- **Persistent**: explicit, sustained intent to maintain access over a long period (months to years), actively working to survive detection/remediation attempts, rather than a single opportunistic smash-and-grab.
- **Threat**: human-directed, with resources and intent — distinguishing it from automated/commodity malware with no operator actively adapting to defender action.
- (Commonly added) **State-sponsored or state-aligned**, or otherwise well-resourced with strategic (not purely financial) objectives — though some ransomware-as-a-service crews now exhibit APT-like persistence and operational security without being state-aligned, which is why some practitioners now separate "APT" from "nation-state" more carefully than they used to.

**Naming conventions.** Different vendors track overlapping-but-not-identical sets of APT groups and assign their own names/numbers (e.g., sequential numbers, animal-themed names, constellation names). A single real-world group may have several different vendor-assigned names referring to the same or overlapping activity clusters — this is a byproduct of independent attribution research, not evidence of multiple distinct groups. MITRE ATT&CK's Groups pages (covered in Lesson 1.4) attempt to track these cross-references. A vendor name tells you *that vendor's current attribution confidence and observed TTPs* — it does not tell you the actor's real-world identity, nor guarantee that two reports under different names aren't describing the same humans.

## Instructor Script

"In the last lesson we walked through malware history. Now we need a vocabulary to actually describe what we're looking at, and the single most common mistake people make here is treating 'virus, worm, trojan, ransomware, rootkit, spyware' as one flat list. They're not. They're two separate questions, and conflating them causes real operational mistakes.

The first question is: how does it move? That's propagation. A virus needs a host — some existing file or program it attaches to and rides along with. A worm doesn't need a host; it spreads itself across a network, often without any user action at all. A trojan doesn't self-propagate either; it relies on tricking a user, or another process, into running it voluntarily, usually by disguising itself as something wanted.

The second question is: what does it do once it's running? That's functional payload. Ransomware encrypts your data and demands payment. A rootkit hides — either itself or something else — usually by tampering with how the operating system reports what's running or what files exist. Spyware and keyloggers covertly collect information. A RAT gives a human operator interactive remote control, like a legitimate remote-desktop tool, except without consent. A downloader or dropper is often tiny and boring on purpose — its only job is to fetch the real payload after the initial compromise. A wiper destroys data or availability, and it's sometimes deliberately disguised as ransomware when the real goal is destruction, not extortion — we'll see that exact pattern with NotPetya in Module 10. And a bot joins a botnet, a network of compromised machines a C2 operator controls collectively.

Here's why keeping these two questions separate matters practically, not just academically. If you're doing incident response, propagation mechanism tells you how to contain it — do you need to isolate an entire network segment because it's worming, or is this one host because it's a trojan that needed a user click? Functional payload tells you what kind of damage to expect and which playbook to run — a ransomware response is different from a data-theft response is different from a wiper response, even if all three got onto the box the same way.

And in reality, a real sample sits at one point on each axis simultaneously. Something might be a trojanized downloader — relies on a user running it, and its only job is to fetch something else — that then installs a RAT with some rootkit-style hiding behavior. That's completely normal. Don't look for a single-word label; describe both axes.

Now, APT. This term gets thrown around loosely, so let's be precise, because it is not a malware family — you cannot have 'an APT' sitting on disk the way you can have 'a trojan' sitting on disk. APT describes how an adversary operates. It was coined inside U.S. Air Force and Department of Defense circles in the mid-2000s, specifically because analysts needed a term for intrusions that didn't fit the smash-and-grab opportunistic-crime pattern they were used to.

Three words, each doing real work. Advanced doesn't necessarily mean zero-days everywhere — plenty of APT activity relies on well-known techniques, executed patiently and carefully, adapted specifically to the target. Persistent means sustained intent to maintain access over months or years, and — critically — actively working to survive your remediation attempts, not just a one-time break-in. Threat means there's a human directing this, with resources and intent, as opposed to automated commodity malware grinding away with no one adapting to what you do in response. A lot of people tack on a fourth property, state-sponsored, and that used to be a reasonable shorthand — but some ransomware-as-a-service crews today show APT-like persistence and operational discipline without being state-aligned at all, so increasingly careful practitioners separate the 'APT' behavioral label from the 'nation-state' attribution question.

One more practical point: naming. Different vendors track overlapping sets of threat groups, and each vendor assigns its own name — sequential numbers, animal names, whatever their convention is. You will absolutely see two different reports, from two different vendors, describing what's probably the same group of humans, under two completely different names. That's not evidence of two groups; it's a byproduct of independent attribution research happening in parallel. MITRE's ATT&CK group pages, which we'll use in lesson four, try to cross-reference these aliases. The takeaway: a vendor's name for a group tells you that vendor's current attribution confidence and the TTPs they've observed — it's a research label, not a legal identity, and it doesn't mean two different-sounding names are necessarily two different threats."

## Practical Demonstration

Slide-based walkthrough: present three short, fictional sample descriptions and classify each live on both axes (propagation + function) in front of the learner, e.g.: "Sample arrives as an email attachment disguised as an invoice (propagation: trojan — relies on user execution). On execution, it installs a small program whose only job is fetching a second file (function: downloader/dropper). The second file gives an operator persistent interactive access (function: RAT)." Repeat for two more composite examples, then do the same exercise for one real, named APT group using only its public MITRE ATT&CK group profile (Lesson 1.4 preview) to extract Advanced/Persistent/Threat evidence (TTP diversity → "Advanced"; multi-year activity → "Persistent"; documented objectives → "Threat").

## Hands-On Lab

**Lab objective:** classify three provided fictional malware descriptions on both axes, and assess one real public threat-group profile against the APT criteria.

- **Required tools:** web browser (MITRE ATT&CK Groups pages only).
- **Environment setup:** none.
- **Exercise instructions:**
  1. For each of three provided fictional sample descriptions (in `assessments/lab-worksheet.md` — *written alongside this lesson, not a live sample*), write down the propagation classification and functional classification, with one sentence of justification each.
  2. Pick one group from https://attack.mitre.org/groups/ and write a short paragraph assessing it against each of the Advanced/Persistent/Threat criteria using only evidence from that public page.
  3. Note whether the page lists any known aliases, and what that tells you about attribution confidence.
- **Expected observations:** most fictional samples require citing evidence for *both* axes separately; the real group profile should show multi-year activity (Persistent) and a documented, varied technique set (Advanced).
- **Validation steps:** instructor/peer check that both axes were addressed independently and that each claim about the real group cites the specific ATT&CK page content it came from.
- **Troubleshooting:** if a chosen group's page is thin on detail, pick a more extensively documented group rather than speculating beyond the source.
- **Cleanup/reset:** none required.

## Knowledge Assessment

1. **(MC)** Which pair correctly represents the two independent classification axes? **A)** Ransomware vs. spyware **B)** Propagation mechanism vs. functional payload **C)** Nation-state vs. criminal **D)** Static vs. dynamic analysis
   **Answer: B.**

2. **(MC)** A program disguised as a free utility that a user downloads and runs voluntarily, with no self-propagation, is best classified (propagation axis) as: **A)** Virus **B)** Worm **C)** Trojan **D)** Rootkit
   **Answer: C.**

3. **(Technical reasoning)** Why is "it's a rootkit" an incomplete classification on its own?
   **Answer:** "Rootkit" describes a functional behavior (hiding presence) but says nothing about propagation mechanism (how it got there) — a complete classification needs both axes, e.g., "a trojan-delivered rootkit" vs. "a worm with rootkit-hiding behavior."

4. **(MC)** Which of these is *not* one of the three defining words/concepts of "APT"? **A)** Advanced **B)** Persistent **C)** Threat **D)** Patched
   **Answer: D.**

5. **(Scenario)** A security vendor publishes a report naming a "new" threat group, but another vendor's existing profile seems to describe overlapping TTPs and timeframe under a different name. What's the most defensible interpretation, per this lesson?
   **Answer:** This is most likely two independent attribution efforts describing the same or overlapping activity cluster under different vendor-assigned names, not necessarily two distinct groups — treat vendor names as research labels with their own confidence level, and look for alias cross-references (e.g., on MITRE ATT&CK) before assuming they're unrelated.

6. **(MC)** Which best distinguishes "Persistent" in the APT sense from a one-time opportunistic breach? **A)** Persistent malware cannot be removed **B)** Persistent describes sustained intent and active effort to survive remediation over an extended period **C)** Persistent means the malware uses a persistence registry key **D)** Persistent means the actor is state-sponsored
   **Answer: B.** (Note: this is deliberately not the same as the technical "persistence mechanism" taught in Module 9 — same word, different meaning, worth flagging to learners.)

7. **(Technical reasoning)** Why might classifying an actor as "APT" without also assessing state-sponsorship be more accurate for some modern ransomware-as-a-service crews?
   **Answer:** Some such crews demonstrate the behavioral hallmarks of APT activity — careful tradecraft, sustained/adaptive persistence, human-directed operations — while being financially rather than state-motivated; conflating "APT" with "nation-state" would misclassify them and could misdirect response/attribution efforts.

8. **(MC)** A small first-stage program whose only function is to fetch and install a further payload is best described functionally as a: **A)** Wiper **B)** Downloader/dropper **C)** Bot **D)** RAT
   **Answer: B.**

## Further Learning

- MITRE ATT&CK Groups — https://attack.mitre.org/groups/
- MITRE ATT&CK Software (for functional-payload examples mapped to real tooling) — https://attack.mitre.org/software/
- CISA Advisories (for current APT naming/alias cross-references) — https://www.cisa.gov/news-events/cybersecurity-advisories
- *Extension:* repeat the APT-criteria exercise for two groups that are commonly described as financially (not state-) motivated, and compare.

# Lesson 1.3 — Cyber Kill Chain and Attack Lifecycle

## Lesson Metadata
- **Module:** 1 — Introduction to Malware & Exploitation
- **Lesson:** 3 of 5
- **Difficulty:** Foundational
- **Estimated duration:** 18 minutes
- **Prerequisites:** Lesson 1.2

## Learning Objectives
1. Name and define, in order, all seven stages of the Lockheed Martin Cyber Kill Chain.
2. Map a short attack narrative to the correct kill-chain stage for each described action.
3. Explain the defensive implication of the kill-chain model: breaking any one stage breaks the whole chain.
4. State two commonly cited limitations of the kill-chain model (linear assumption, weak coverage of lateral movement/post-exploitation depth, origin as a vendor marketing framework).

## Conceptual Explanation

The **Cyber Kill Chain**, published by Lockheed Martin in 2011, borrows its name and core idea from military "kill chain" doctrine: an attack is a *chain* of distinct stages, and disrupting any single link breaks the whole operation. The seven stages, in order:

1. **Reconnaissance** — gathering information about the target (public records, employee names/emails via OSINT, exposed services via scanning, technology-stack fingerprinting).
2. **Weaponization** — coupling an exploit with a payload into a deliverable artifact (e.g., a malicious document, a crafted exploit for a known vulnerability).
3. **Delivery** — transmitting the weaponized artifact to the target (phishing email, watering-hole website, infected USB, direct exploitation of an exposed service).
4. **Exploitation** — triggering the vulnerability/weakness to execute attacker code or logic on the target (a macro running, an exploit firing against a vulnerable service, a user entering credentials on a phishing page).
5. **Installation** — establishing a durable foothold (dropping a backdoor/RAT, installing a persistence mechanism — Module 9 territory).
6. **Command and Control (C2)** — establishing a channel for the attacker to direct the compromised system remotely (Module 6 territory).
7. **Actions on Objectives** — the attacker's actual goal: data exfiltration, lateral movement toward a higher-value target, destruction, encryption for ransom, espionage collection, etc.

**The defensive argument.** Lockheed Martin's framing is explicitly defender-oriented: because the attacker must succeed at *every* stage, the defender only needs to break *one*. A phishing-awareness program interrupts Delivery; email attachment sandboxing interrupts Exploitation; EDR catching a persistence mechanism interrupts Installation; network egress filtering/C2 detection interrupts Command and Control. This is the model's enduring value — it gives defenders multiple independent chances to stop an intrusion rather than needing one perfect control.

**Limitations to know.** The model is explicitly linear and assumes a single pass; real intrusions loop (an attacker lands on a low-value host, then runs *another* mini kill-chain — recon, lateral delivery, exploitation of an internal service — to reach a higher-value target), which the basic seven-stage model doesn't represent well on its own. It also compresses everything after initial C2 into one broad "Actions on Objectives" stage, which is far too coarse for real post-exploitation analysis (lateral movement, privilege escalation, collection, exfiltration are each substantial activities). It originated as a vendor (Lockheed Martin) framework, which is not disqualifying, but is why MITRE ATT&CK (Lesson 1.4) — a far more granular, community-maintained, non-linear framework — has become the dominant practitioner tool for the kind of detailed mapping the kill chain can't support alone. The two models are complementary, not competing: the kill chain gives you the high-level narrative arc; ATT&CK gives you the granular technique-level detail within and across that arc.

## Instructor Script

"Now that we can classify what a piece of malware *is*, let's build a model for the sequence of events that gets it onto a target in the first place, and for everything the attacker does afterward. This is the Cyber Kill Chain, published by Lockheed Martin in 2011, and the name is deliberate — it's borrowed directly from military kill-chain doctrine, where an operation is a chain of steps, and breaking any one link breaks the whole chain.

Seven stages, and I want you to be able to recite these in order, because you'll use this vocabulary constantly. Reconnaissance: the attacker learns about the target — public records, employee names and emails, which services are exposed, what technology stack is running. Weaponization: the attacker couples an exploit with a payload into something deliverable — a malicious document, a crafted exploit for a known vulnerability. Delivery: getting that weaponized artifact to the target — a phishing email, a watering-hole site, a USB drop, or directly exploiting an exposed service. Exploitation: the moment the vulnerability actually triggers — the macro runs, the exploit fires, the user types credentials into the fake page. Installation: establishing a durable foothold — dropping a backdoor, installing a persistence mechanism, which is exactly what Module 9 covers in depth. Command and Control: the attacker sets up a channel to direct the compromised system remotely — that's Module 6. And finally, Actions on Objectives: whatever the attacker actually came for — stealing data, moving laterally to a bigger target, destroying something, encrypting for ransom, or quietly collecting intelligence over time.

Here's why this model has stayed useful for over a decade: it's explicitly written from the defender's point of view. The argument is simple — the attacker has to succeed at every single stage, in order, or the chain breaks. But you, the defender, only need to break one link, anywhere in that chain, to stop the whole operation. A good phishing-awareness program interrupts Delivery. Attachment sandboxing interrupts Exploitation. An EDR catching a weird new scheduled task interrupts Installation. Egress filtering that flags unusual outbound connections interrupts Command and Control. That's genuinely useful, because it means you don't need one perfect control — you need several independent, layered opportunities to catch the intrusion.

But — and this matters for how you use the model, not just whether it's valid — it has real limitations. First, it's linear. It assumes one pass through the chain. Real intrusions don't work that way. An attacker often lands on some low-value machine, and then effectively runs a second, smaller kill chain from there — reconnaissance of the internal network, delivery of an internal exploit, exploitation of some internal service — specifically to reach a more valuable target. The basic seven stages don't represent that looping well on their own.

Second limitation: that last stage, Actions on Objectives, is doing an enormous amount of work for one box on a diagram. Lateral movement, privilege escalation, data collection, exfiltration — those are each substantial activities with their own techniques and their own detections, and the kill chain flattens all of it into one label.

And third, worth just knowing as context: this came out of a vendor, Lockheed Martin. That's not a criticism that invalidates it — it's genuinely useful — but it's part of why, over the past decade, MITRE's ATT&CK framework, which we cover next lesson, has become the dominant tool for the kind of granular, technique-by-technique mapping the kill chain alone can't give you. Think of it this way: the kill chain gives you the high-level narrative arc of an attack. ATT&CK gives you the fine-grained detail of exactly which techniques happened within, and across, each part of that arc. You'll use both, for different purposes, for the rest of this course."

## Practical Demonstration

Present a short fictional attack narrative on slides (e.g., "Attacker emails HR a fake resume with a malicious macro → macro runs, drops a loader → loader installs a scheduled task → loader beacons to an external server every 60 seconds → attacker browses file shares and copies finance spreadsheets to an external server") and map each sentence, live, to its kill-chain stage, writing the stage label next to each sentence as it's revealed.

## Hands-On Lab

**Lab objective:** map two provided fictional incident narratives to the seven kill-chain stages, and identify a defensible control for one stage in each.

- **Required tools:** none (paper/text exercise).
- **Exercise instructions:**
  1. For narrative A and narrative B (`assessments/` worksheet), label each sentence/event with its kill-chain stage.
  2. For each narrative, name one concrete, real control (e.g., "email attachment sandboxing," "DNS egress monitoring," "EDR process-creation alerting") that would have broken the chain at a specific stage, and explain why.
- **Expected observations:** some events legitimately span or straddle two stages (e.g., a single phishing email can combine Delivery and, if it contains the exploit itself, Exploitation) — the lab worksheet explanation should justify the chosen boundary rather than treat it as mechanical.
- **Validation steps:** instructor/peer check that the named control is realistic (not "just don't get phished") and tied to a specific, correctly identified stage.
- **Troubleshooting:** if a learner's narrative doesn't cleanly show all seven stages, that's expected and fine — not every real incident report provides equal visibility into every stage; note which stages are "not observed" explicitly rather than guessing.
- **Cleanup/reset:** none required.

## Knowledge Assessment

1. **(MC)** Which is the correct kill-chain stage order (abbreviated)? **A)** Delivery, Recon, Exploitation, Weaponization… **B)** Reconnaissance, Weaponization, Delivery, Exploitation, Installation, C2, Actions on Objectives **C)** Exploitation, Delivery, Weaponization, Recon… **D)** Installation, C2, Recon, Delivery…
   **Answer: B.**

2. **(MC)** A phishing email containing a malicious attachment, sent to an employee, is generally classified as which stage? **A)** Weaponization **B)** Delivery **C)** Installation **D)** Actions on Objectives
   **Answer: B.** (The act of coupling the exploit/payload into the attachment was Weaponization; sending it is Delivery.)

3. **(Technical reasoning)** Why is "the defender only needs to break one link" considered the kill chain's central defensive value?
   **Answer:** Because the attacker's success depends on completing every stage in sequence, a defender has multiple independent opportunities (one per stage) to stop the intrusion, rather than needing a single perfect, all-encompassing control.

4. **(MC)** Which is a commonly cited limitation of the basic seven-stage kill chain? **A)** It has too many stages to be useful **B)** It assumes a single linear pass and compresses post-exploitation activity into one broad stage **C)** It was never adopted by any real organization **D)** It does not include an exploitation stage at all
   **Answer: B.**

5. **(Scenario)** An attacker compromises a low-privilege workstation, then uses it to scan and exploit an internal file server. How does this scenario challenge the basic kill-chain model?
   **Answer:** It represents a second, nested kill chain (internal recon → internal delivery/exploitation) launched from a foothold gained via the first kill chain — the single linear seven-stage model doesn't natively represent this looping/nested structure.

6. **(MC)** Establishing a beaconing channel so an attacker can issue further commands remotely corresponds to which stage? **A)** Installation **B)** Command and Control **C)** Weaponization **D)** Actions on Objectives
   **Answer: B.**

7. **(Technical reasoning)** Why are the Cyber Kill Chain and MITRE ATT&CK described as complementary rather than competing?
   **Answer:** The kill chain provides a high-level narrative arc of an intrusion's phases; ATT&CK provides granular, technique-level detail (often with many techniques mapping within a single kill-chain stage), so the two operate at different levels of resolution and are often used together.

## Further Learning

- Lockheed Martin, Cyber Kill Chain — https://www.lockheedmartin.com/en-us/capabilities/cyber/cyber-kill-chain.html
- SANS, "Applying Security Awareness to the Cyber Kill Chain" (search SANS Reading Room)
- *Extension:* re-map the Lesson 1.1 WannaCry summary to the seven kill-chain stages as a self-check before Module 10.

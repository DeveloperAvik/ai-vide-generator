# Module 1 Assessment — Introduction to Malware & Exploitation

Cumulative, 15 questions spanning Lessons 1.1–1.5. No practical/lab component (conceptual module) — however, item 15 requires the Lesson 1.5 authorization statement as a prerequisite attachment; this assessment cannot be marked complete without it.

1. **(MC)** Which era does the Morris Worm (1988) belong to, per Lesson 1.1's model? **A)** Criminalization/monetization **B)** Curiosity and research **C)** Nation-state/destructive capability **D)** Mass-mailer/macro virus
   **Answer: B.**

2. **(MC)** EternalBlue, used by both WannaCry and NotPetya, exploited a vulnerability in: **A)** DNS **B)** SMB **C)** RDP **D)** FTP
   **Answer: B.**

3. **(Technical reasoning)** Explain why "malware became a business" is a meaningful inflection point distinct from earlier eras, not just "malware got worse."
   **Answer:** It marks a shift in actor motive and organizational structure — from individual curiosity/prank motives to specialized, profit-driven roles (exploit writers, malware authors, access brokers, cash-out operators) mirroring a legitimate industry's division of labor, which is a structural change, not merely a severity increase.

4. **(MC)** A program that disguises itself as a wanted utility and requires the user to run it voluntarily, with no self-propagation, is classified on the propagation axis as a: **A)** Worm **B)** Virus **C)** Trojan **D)** Rootkit
   **Answer: C.**

5. **(MC)** Which three words/concepts define "APT" per Lesson 1.2? **A)** Advanced, Persistent, Threat **B)** Automated, Persistent, Technical **C)** Advanced, Patched, Threat **D)** Anonymous, Persistent, Technical
   **Answer: A.**

6. **(Scenario)** Two vendor reports describe overlapping TTPs and timeframes under two different group names. What should you conclude, and why?
   **Answer:** Likely the same or an overlapping activity cluster tracked independently under different vendor-assigned aliases — not necessarily two distinct groups; check for alias cross-references (e.g., on MITRE ATT&CK) before treating them as unrelated.

7. **(MC)** In the Cyber Kill Chain, establishing a durable foothold (e.g., dropping a backdoor) corresponds to which stage? **A)** Delivery **B)** Exploitation **C)** Installation **D)** Actions on Objectives
   **Answer: C.**

8. **(Technical reasoning)** Why is "the defender only needs to break one link" the kill chain's central defensive argument?
   **Answer:** Because the attacker must succeed at every stage in sequence, each stage represents an independent opportunity for a defensive control to stop the entire intrusion.

9. **(MC)** What is a commonly cited limitation of the basic seven-stage kill chain? **A)** It has no stages for exploitation **B)** It assumes a single linear pass and compresses post-exploitation activity into one broad stage **C)** It cannot be taught to new analysts **D)** It was never used by any defender
   **Answer: B.**

10. **(MC)** In MITRE ATT&CK, which level represents a specific, cited, real-world instance of a group or software using a technique? **A)** Tactic **B)** Technique **C)** Procedure Example **D)** Matrix
    **Answer: C.**

11. **(Technical reasoning)** Why is citing an ATT&CK technique ID (e.g., "T1059.001") more useful between analysts than a prose description like "PowerShell-based execution stuff"?
    **Answer:** The ID references one precisely defined, documented technique with a stable public page (description, mitigations, detections, procedures); prose can vary between speakers, while the ID guarantees both parties mean the exact same documented behavior, enabling precise comparison and detection-coverage tracking.

12. **(MC)** Which published ATT&CK matrix exists, per Lesson 1.4? **A)** Residential **B)** Enterprise **C)** Automotive **D)** Retail
    **Answer: B.**

13. **(MC)** Under laws like the US CFAA, what primarily determines whether computer access was illegal? **A)** Whether damage occurred **B)** Whether access was authorized **C)** Whether the actor is a professional **D)** Whether the actor disclosed findings publicly
    **Answer: B.**

14. **(Scenario)** A researcher privately reports a bug, the vendor goes silent for six months, and the researcher then publishes full details. Is this defensible as coordinated disclosure, and what should the researcher have documented along the way?
    **Answer:** Generally defensible given private-first reporting and a long unresponsive silence beyond common disclosure-window norms, but the researcher should have documented each reporting attempt and the full timeline, since "reasonable" is judgment-dependent.

15. **(Submission requirement)** Attach your Lesson 1.5 personal authorization statement, naming the specific `LAB_SAFETY.md` §3 model that applies to your lab environment for the rest of this course. **This item is required to mark Module 1 complete** and is a prerequisite for starting Module 2's hands-on labs.

## Scoring

14 scored knowledge items (1 point each) + item 15 (pass/fail gate, not point-scored). Passing threshold: 11/14 on scored items **and** a satisfactory, specific authorization statement for item 15.

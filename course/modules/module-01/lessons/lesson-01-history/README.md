# Lesson 1.1 — History and Evolution of Malware and Exploits

## Lesson Metadata
- **Module:** 1 — Introduction to Malware & Exploitation
- **Lesson:** 1 of 5
- **Difficulty:** Foundational
- **Estimated duration:** 20 minutes
- **Prerequisites:** None

## Learning Objectives
By the end of this lesson, the learner can:
1. Describe at least four distinct eras of malware/exploit evolution and the technology shift that drove each.
2. Explain why early self-replicating programs (Creeper, Elk Cloner, Morris Worm) matter to a modern analyst.
3. Explain the shift from "malware as prank/experiment" to "malware as a criminal/financial business" and then to "malware as a state-level capability."
4. Name the general exploit-class progression (unchecked memory-safety bugs → mitigated binaries → logic/supply-chain/cloud-identity bugs) and explain why it happened.

## Conceptual Explanation

Malware and exploitation did not appear fully formed; both evolved in lockstep with the systems they target, and understanding that evolution is what lets an analyst recognize a *new* technique as a variation on an old idea rather than something unprecedented.

**Era 1 — Curiosity and research (1970s–1980s).** Creeper (1971), a self-replicating program on ARPANET, is usually cited as the first self-propagating code; it displayed the message "I'm the creeper, catch me if you can!" and was not malicious by intent. Elk Cloner (1982) was the first PC virus to spread "in the wild," via floppy disk boot sectors, written as a prank by a teenager. The Morris Worm (1988) is the pivotal event of this era: Robert Tappan Morris released a self-propagating program that exploited known Unix vulnerabilities (including a sendmail debug-mode flaw and a weak password list) and a bug in its own spreading logic caused it to infect machines far more aggressively than intended, taking down a meaningful fraction of the early internet. It led directly to the founding of the first CERT (Computer Emergency Response Team) at Carnegie Mellon. The throughline for this era: authors were largely researchers or students, exploiting known, often already-documented weaknesses, with no financial motive.

**Era 2 — Mass-mailer and macro viruses (1990s–early 2000s).** As PCs and email adoption grew, so did viruses built for maximum visible spread rather than stealth: Melissa (1999, Word-macro mass-mailer), the ILOVEYOU worm (2000, VBScript email worm), and Code Red / SQL Slammer / Blaster (2001–2003, worms exploiting unpatched Windows/IIS/SQL services directly over the network with no user interaction required). This era established the idea of a **worm** (self-propagating without a host file) as distinct from a **virus** (requires a host file/program) and demonstrated that a single unpatched network-facing service could cause internet-scale impact within hours.

**Era 3 — Criminalization and monetization (mid-2000s–2010s).** Malware development professionalized. Botnets (Conficker, Zeus) turned infected machines into rentable infrastructure. Banking trojans targeted credentials directly for financial theft. Exploit kits (Blackhole, Angler) commoditized "drive-by" browser exploitation, selling access to vulnerabilities as a service. Ransomware emerged as a distinct, now-dominant business model, encrypting victim data and demanding payment — CryptoLocker (2013) is the commonly cited inflection point for ransomware-as-serious-threat. The throughline: malware became a *business*, with specialization (exploit writers, malware authors, access brokers, money-laundering "cashout" operators) mirroring a legitimate software supply chain.

**Era 4 — Nation-state and destructive capability (2010s–present).** Stuxnet (discovered 2010) demonstrated that malware could cause physical, kinetic damage (sabotaging Iranian uranium-enrichment centrifuges) via a chain of zero-day exploits and a highly specific industrial-control-system payload — covered in depth in Module 10. WannaCry (2017) and NotPetya (2017) showed how a single leaked/weaponized exploit (EternalBlue, targeting a Windows SMB vulnerability) could be wrapped in both criminal ransomware (WannaCry) and a destructive, geopolitically-motivated wiper disguised as ransomware (NotPetya). Supply-chain compromises (e.g., compromising a software update mechanism to reach many downstream victims at once) became a recognized, repeatable technique. The throughline: well-resourced, patient actors — including state-sponsored groups — now treat malware development as a long-term capability-building exercise, not a one-off tool.

**Exploit-class evolution runs on a parallel timeline.** Early exploitation targeted simple, unmitigated memory-safety bugs (stack-based buffer overflows directly overwriting a return address) because operating systems had essentially no defenses — this is exactly what Module 7 teaches hands-on. As mitigations arrived (stack canaries, DEP/NX, ASLR — Module 8), exploitation shifted to bypass techniques (ROP, info leaks) and then increasingly toward memory-safety-adjacent bugs that are harder to mitigate generically (use-after-free, type confusion) and toward entirely different bug classes outside memory safety: logic flaws, deserialization bugs, and — in the current era — cloud-identity misconfigurations and software-supply-chain compromise, because those often bypass memory-safety mitigations entirely by not needing memory corruption at all.

## Instructor Script

"Let's start at the beginning, not because history trivia matters for its own sake, but because every 'new' attack technique you'll see in this course is almost always an old idea applied to a new target. If you can place a technique in this timeline, you can usually guess what defense already exists for it, and what the attacker had to change to get around that defense.

The first self-replicating program most people point to is Creeper, from 1971, running on the early ARPANET. It wasn't malicious — it just displayed a cheeky message and moved itself to another machine. Eleven years later, Elk Cloner did something similar on early Apple II computers, spreading through shared floppy disks. Both were built essentially as pranks or experiments. Nobody made money from either one.

The event that really matters for this era is the Morris Worm, in 1988. Robert Morris, a graduate student, released a program that exploited a handful of known weaknesses — a debug mode left enabled in sendmail, and weak passwords it could guess — to spread between Unix machines. The bug wasn't in the concept, it was in the implementation: a mistake in his own re-infection logic made the worm spread far more aggressively than he intended, and it knocked a meaningful fraction of the early internet offline. This is the event that led to the first CERT being founded. Notice the pattern already: the exploited weaknesses were already known. The novelty was automating and chaining them.

Through the 1990s and into the early 2000s, we get an era of mass-mailer and macro viruses, and then network worms, built to spread as visibly and widely as possible. Melissa and ILOVEYOU rode email attachments and social engineering. Code Red, SQL Slammer, and Blaster are a different and arguably more important category: worms that exploited unpatched network services directly, no user click required. SQL Slammer in particular is still used as a case study in how fast a worm can spread when the vulnerable population is large and the exploit is small enough to fit in a single network packet. This era is where the vocabulary splits: a virus needs a host file to attach to; a worm spreads on its own.

From the mid-2000s on, something changes: malware becomes a business. Botnets like Zeus and Conficker turned infected machines into rentable infrastructure. Banking trojans went straight after credentials. Exploit kits packaged vulnerabilities for sale so an attacker no longer needed deep exploit-development skill to compromise a browser. And ransomware emerged as its own specialty, with CryptoLocker in 2013 usually cited as the moment it became a dominant, scalable criminal business model rather than a novelty. If you map this against legitimate software industries, you'll notice the same specialization: some people write the exploits, some write the malware, some handle access brokering, some handle laundering the proceeds. That's not an accident — it mirrors how any mature industry divides labor.

The most recent era adds a new motive entirely: nation-states building long-term capability. Stuxnet, discovered in 2010, is the clearest example — a chain of exploits delivering a payload built specifically to physically damage centrifuges in a uranium enrichment facility. We'll do a full module-ten deep dive on that. WannaCry and NotPetya, both in 2017, both rode the same leaked exploit — EternalBlue, against a flaw in Windows' SMB file-sharing protocol — but with very different payloads: WannaCry was straightforward, if poorly executed, ransomware; NotPetya dressed itself up as ransomware but was actually a destructive wiper, widely attributed to a geopolitically motivated actor. The lesson there: the exploit is reusable infrastructure, independent of the payload's purpose.

Now, run the same timeline for exploitation techniques specifically, because it tracks the malware timeline closely. Early exploitation targeted simple, completely unmitigated stack overflows, because there was essentially no defense in place — you'll build exactly this kind of exploit yourself in Module 7. As defenses arrived — stack canaries, then DEP and NX marking memory non-executable, then ASLR randomizing memory layout — attackers didn't give up, they adapted: return-oriented programming to work around non-executable memory, information leaks to work around ASLR. That's Module 8. And as memory-safety bugs became harder to find and exploit reliably, attention shifted toward bug classes that don't need memory corruption at all: logic flaws, deserialization issues, and today, increasingly, cloud-identity misconfigurations and software-supply-chain compromise.

Here's the takeaway to carry into every later module: when you see something that looks new, ask what known technique it's really a variation of, and what changed about the target that made the variation necessary. That question will serve you better than memorizing a list of famous names."

## Practical Demonstration

This lesson has no hands-on technical demonstration (conceptual/history lesson). The "demonstration" is a guided timeline walkthrough on slides: present each named incident (Creeper, Elk Cloner, Morris Worm, Melissa/ILOVEYOU, Code Red/SQL Slammer/Blaster, Zeus/Conficker, CryptoLocker, Stuxnet, WannaCry/NotPetya) on a single annotated timeline graphic, then re-draw the same timeline with the exploit-mitigation arms race (unmitigated overflow → canaries → DEP/NX → ASLR → ROP/info-leak → logic/supply-chain bugs) layered beneath it, to make the "parallel evolution" point visually.

## Hands-On Lab

**Lab objective:** produce a one-page "incident card" for one historical event not covered as a named example above (research exercise — no VM/tooling required).

- **Required tools:** a web browser and access to primary/authoritative sources only (vendor postmortems, CERT advisories, NVD/MITRE entries, original researcher reports) — no secondary blog aggregation as the sole source.
- **Environment setup:** none.
- **Exercise instructions:**
  1. Pick one event from this list: the Jerusalem/Friday-the-13th virus, the Chernobyl (CIH) virus, the Mydoom worm, the Conficker worm, or the Shamoon wiper.
  2. Research using at least two authoritative sources.
  3. Produce a one-page card: name, year, propagation mechanism, payload/impact, what made it notable, and which era (per this lesson's four-era model) it belongs to and why.
- **Expected observations:** the chosen incident fits recognizably into one of the four eras, or the learner can articulate specifically why it's a transitional case.
- **Validation steps:** peer or instructor review checks that both sources cited are primary/authoritative (not just blog posts) and that the era classification is justified, not asserted.
- **Troubleshooting:** if authoritative primary sources are hard to find for an obscure incident, pick a better-documented one from the list above rather than relying on a single unsourced blog.
- **Cleanup/reset:** none required (research exercise).

## Knowledge Assessment

1. **(MC)** What distinguishes a worm from a virus? **A)** A worm is always more destructive **B)** A worm requires a host file to spread; a virus does not **C)** A virus requires a host file/program to spread; a worm does not **D)** There is no meaningful difference
   **Answer: C.** A virus attaches to and requires an existing file/program; a worm self-propagates independently across a network.

2. **(MC)** What was notable about the Morris Worm's impact in 1988? **A)** It was the first ransomware **B)** It caused unintended, large-scale disruption due to a bug in its own re-infection logic **C)** It targeted industrial control systems **D)** It used a zero-day browser exploit
   **Answer: B.** Morris's worm spread more aggressively than intended because of a flaw in the logic meant to avoid re-infecting the same host repeatedly.

3. **(Technical reasoning)** Why is SQL Slammer (2003) often cited specifically for propagation *speed* rather than payload sophistication?
   **Answer:** Its exploit fit in a single UDP packet (no multi-packet handshake needed) against a widely-deployed, unpatched network service, so each infected host could scan and infect new hosts almost as fast as it could send packets — propagation speed was a function of exploit simplicity and packet size, not payload complexity.

4. **(MC)** Which best characterizes the mid-2000s–2010s malware era? **A)** Malware authors acted purely for research curiosity **B)** Malware development specialized into a criminal business model with distinct roles **C)** All malware in this era was state-sponsored **D)** Exploit kits disappeared in favor of manual exploitation
   **Answer: B.**

5. **(MC)** EternalBlue, the exploit behind both WannaCry and NotPetya, targeted a vulnerability in which protocol? **A)** HTTP **B)** DNS **C)** SMB **D)** SSH
   **Answer: C.**

6. **(Scenario)** You're asked to assess whether a newly discovered piece of malware represents a "sophisticated new threat." It uses a known, already-patched exploit, wrapped in a new packer, with a new ransom note template. How would you frame this using the era/evolution model from this lesson?
   **Answer:** The exploit and payload *type* (ransomware) are not new — they fit squarely in the criminalization era. The packer is a presentation-layer change (Module 4 territory), not a new capability. "Sophistication" should be assessed on novel technique, not novel wrapping; this sample is most accurately framed as an incremental variation, which matters for prioritizing detection engineering effort.

7. **(MC)** What general shift describes exploit-class evolution over time, as mitigations were introduced? **A)** Exploits became impossible to write **B)** Exploitation shifted from unmitigated memory-safety bugs toward bypass techniques, and then increasingly toward non-memory-safety bug classes **C)** All exploitation moved exclusively to social engineering **D)** Memory-safety bugs stopped existing after 2010
   **Answer: B.**

8. **(Technical reasoning)** Why does Stuxnet (2010) mark a distinct era rather than just a more sophisticated version of earlier malware?
   **Answer:** Prior malware eras were defined by self-propagation for its own sake (Era 1), mass visibility (Era 2), or financial monetization (Era 3). Stuxnet's defining characteristic was a payload engineered to cause specific physical/kinetic damage to industrial control systems, reflecting a different motive (sabotage) and a different resourcing level (multiple chained zero-days, deep ICS-specific engineering) than criminal or research motives typically support.

## Further Learning

- Clifford Stoll, *The Cuckoo's Egg* (1989) — contemporaneous account of early intrusion investigation.
- CERT/CC founding history — https://www.sei.cmu.edu/about/divisions/cert/
- Symantec, "W32.Stuxnet Dossier" (2011) — primary technical source, revisited in depth in Module 10.
- MITRE ATT&CK group/software pages for Conficker, Zeus — https://attack.mitre.org/software/
- *Practical exercise extension:* build a longer timeline (10+ events) spanning all four eras as a personal reference document to revisit before Module 10.

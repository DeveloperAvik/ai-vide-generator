# Module 1 — Lab Worksheet Materials

Source material referenced by the hands-on labs in Lessons 1.2–1.5. All names, systems, and organizations below are fictional.

## Lesson 1.2 lab — Classify these three samples (propagation axis + functional axis)

**Sample 1:** Arrives as an attachment named "Q3_Invoice.docx.exe" in a phishing email. A user must open it. On execution, it copies itself to a startup folder and begins logging all keystrokes to a local file, which it periodically uploads to an external server.

**Sample 2:** Exploits an unpatched flaw in a public-facing file-sharing service with no user interaction required. Once on a host, it scans the local subnet for other instances of the same vulnerable service and copies itself to each one it finds, with no further payload beyond propagation.

**Sample 3:** Bundled inside a cracked version of a popular game, run voluntarily by the user. On execution, it installs a hidden service that hooks several Windows API calls to hide its own process and files from Task Manager and Explorer, then opens a channel allowing an operator to issue commands interactively.

*(Expected axis answers: Sample 1 = Trojan / Spyware-keylogger-downloader-hybrid. Sample 2 = Worm / no additional function beyond propagation (a "pure" worm). Sample 3 = Trojan / Rootkit + RAT.)*

## Lesson 1.3 lab — Map these narratives to kill-chain stages

**Narrative A:** "Attacker emails HR a fake resume with a malicious macro. The macro runs, drops a loader. The loader installs a scheduled task. The loader beacons to an external server every 60 seconds. The attacker browses file shares and copies finance spreadsheets to an external server."

**Narrative B:** "Attacker scans a company's public IP range and finds an outdated VPN appliance with a known unpatched flaw. Attacker sends a crafted request exploiting the flaw directly, gaining a shell with no user interaction. Attacker installs a web shell on the appliance for persistence, then uses the appliance as a pivot point to reach an internal database server, dumping customer records to a cloud storage bucket the attacker controls."

## Lesson 1.4 lab — Map these actions to ATT&CK technique IDs

1. Attacker uses a scheduled task to run a script automatically every reboot.
2. Attacker dumps credentials from LSASS process memory.
3. Attacker exfiltrates data by encoding it into DNS queries to an attacker-controlled domain.
4. Attacker runs an obfuscated PowerShell script to download a second-stage payload.
5. Attacker uses a valid, stolen set of remote-desktop credentials to log into another host on the network.

*(Hint: use the ATT&CK site's search/filter by Tactic first — e.g., filter to "Credential Access" before searching for LSASS-related techniques — rather than free-text search alone.)*

## Lesson 1.5 lab — Classify these disclosure scenarios

**Case 1:** A researcher finds a critical bug in a hospital's patient-portal software. They email the vendor privately, describing the bug in general terms, and offer to provide full technical details "for a consulting fee of $5,000." The vendor does not respond. The researcher does not publish.

**Case 2:** A researcher finds a bug in an open-source library. They open a private security advisory with the maintainers (a standard GitHub Security Advisory), work with the maintainers for three weeks to confirm and fix the issue, and publish full technical details only after the patched version is released, crediting the maintainers' fix timeline.

**Case 3:** A researcher finds a bug in a widely-used enterprise product. They email the vendor's generic support inbox once. Receiving an automated "ticket received" reply and no further response within 24 hours, they publish a full working exploit the next day, stating "the vendor was given a chance and didn't respond."

*(Expected classifications: Case 1 = unethical/extortion — "a consulting fee" tied to providing the vulnerability details crosses into demanding payment in exchange for information, even if framed as "consulting." Case 2 = exemplary coordinated disclosure. Case 3 = not coordinated disclosure — 24 hours to a generic support inbox is not a reasonable fix window by any common norm, and automated ticket acknowledgment does not constitute vendor engagement.)*

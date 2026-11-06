# Module 12 Capstone — Track Selection

Pick one track. Each produces a professional report as the primary deliverable, scored against `instructor/ASSESSMENT_RUBRICS.md`. All tracks run entirely inside the learner's isolated lab per `LAB_SAFETY.md`.

## Track A — Exploit Development & Vulnerability Research
**Deliverable:** reproduce one historical, publicly-documented CVE (chosen from a pre-approved list of well-documented, long-patched vulnerabilities in deliberately-vulnerable practice software — never a currently-supported production target) end to end in an isolated VM: crash it, root-cause it with a debugger, write a working exploit against the vulnerable practice build, and write it up like a vendor advisory (CVE context, affected versions, root cause, PoC description, CVSS reasoning, remediation). See `capstone/track-a-exploit-development.md`.

## Track B — Malware Reverse Engineering & Detection
**Deliverable:** full static + dynamic analysis of a provided benign-but-representative sample (built for this course, not live malware) using Ghidra/x64dbg/sandbox, producing an analysis report, an IOC list, and a working YARA rule, plus a Sigma rule for one behavioral indicator. See `capstone/track-b-malware-analysis.md`.

## Track C — Adversary Emulation & Defensive Validation
**Deliverable:** run a scripted, lab-contained adversary-emulation scenario (mapped to specific MITRE ATT&CK techniques) against the learner's own isolated range, then build the detection content (Sysmon config + Sigma/YARA + a short runbook) that catches it, and write the engagement report from both the red and blue perspective. See `capstone/track-c-adversary-emulation.md`.

## Common requirements (all tracks)

- A written authorization/scope statement for the lab used (can be a one-paragraph self-authorization for a personal lab, per `LAB_SAFETY.md` Section 3).
- Evidence captured from the learner's own environment (screenshots, log excerpts, decompiled snippets) — not copied from a reference writeup.
- A references section citing every external claim (CVE detail, tool capability, technique description).

Per-track detail pages (objectives, step-by-step scope, grading tie-in) are tracked in `PROGRESS.md` and authored alongside Module 12.

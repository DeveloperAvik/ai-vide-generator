# Capstone Assessment Rubrics

Each criterion scored 0–3 (0 = absent, 1 = attempted, 2 = competent, 3 = strong/professional). Passing = 2+ average with no criterion at 0.

## Track A — Exploit Development & Vulnerability Research

| Criterion | 0 | 3 |
|---|---|---|
| Root-cause analysis | Missing or incorrect | Clearly identifies the vulnerable code path and why it's exploitable |
| Reproduction | Crash not reproduced | Reliable crash reproduced with documented steps |
| Exploit/PoC | No working PoC | PoC achieves the stated lab goal (e.g., controlled EIP/RIP, demonstrated code-path redirect) on the practice build |
| Mitigation discussion | Absent | Explains the actual patch/mitigation and why it closes the issue |
| Report quality | Unreadable/no citations | Reads like a vendor advisory; all claims cited |
| Safety/scope compliance | Targets outside the lab or unclear authorization | Fully scoped to the learner's own isolated VM, stated explicitly |

## Track B — Malware Reverse Engineering & Detection

| Criterion | 0 | 3 |
|---|---|---|
| Static analysis | No PE/file triage | Thorough PEStudio/Ghidra triage with correct interpretation |
| Dynamic analysis | No behavioral capture | Sandbox/behavioral trace captured and correctly interpreted |
| IOC extraction | Missing or wrong | Accurate, specific IOCs (hashes, strings, network indicators) |
| YARA rule | Doesn't match sample or false-positive prone | Matches the sample, reasonably specific, documented |
| Sigma rule | Absent/non-functional | Valid Sigma targeting a real behavioral indicator from the analysis |
| Report quality | Unreadable/no citations | Clear, structured, cites tool output directly |

## Track C — Adversary Emulation & Defensive Validation

| Criterion | 0 | 3 |
|---|---|---|
| ATT&CK mapping | Missing/incorrect technique IDs | Correct, specific technique IDs for each emulated step |
| Emulation execution | Not run / not in an isolated lab | Cleanly run in the learner's isolated range, evidenced |
| Detection content | No detections built | Sysmon config + Sigma/YARA that actually fires on the emulated activity, evidenced with logs |
| Runbook | Absent | Clear analyst runbook: alert → triage steps → containment |
| Dual-perspective report | One-sided or missing | Clearly separates red actions taken and blue detections/response |
| Safety/scope compliance | Ambiguous authorization | Explicit, lab-only, documented |

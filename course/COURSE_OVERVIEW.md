# Malware & Exploit Development Masterclass — Course Overview

## Audience

Experienced penetration testers, authorized red-team professionals, exploit-development researchers, malware analysts, vulnerability researchers, and cybersecurity students preparing for advanced offensive/defensive certifications (e.g., OSCP/OSED/OSEE-adjacent, GREM, GCIH).

## Prerequisites

- Comfortable with Linux and Windows command lines, and with at least one of C/C++ or Python at an intermediate level.
- Basic networking (TCP/IP, DNS, HTTP/HTTPS) and basic OS concepts (processes, memory, filesystems).
- A machine capable of running a type-2 hypervisor (VirtualBox/VMware) with at least two VMs concurrently (8+ GB RAM, 4+ cores, virtualization extensions enabled) and 60+ GB free disk.
- Has read and agrees to **[LAB_SAFETY.md](LAB_SAFETY.md)** and holds one of its acceptable authorization models before starting Module 2 onward.

## Course-level learning outcomes

By completion, a learner can:

1. Explain the malware/exploit landscape historically and by classification, and place any given sample or technique in the Cyber Kill Chain and MITRE ATT&CK.
2. Build and operate an isolated malware-analysis and exploit-development lab from scratch.
3. Read and reason about PE/ELF binaries, process/memory internals, and write small C/C++/Python programs that demonstrate core malware mechanisms (keylogging, injection, basic C2) in a contained, de-fanged form.
4. Apply and recognize common obfuscation, packing, and anti-analysis techniques, and reverse them during analysis.
5. Perform static and dynamic analysis of a sample using Ghidra, x64dbg/GDB, and a sandbox, and produce IOCs and a YARA rule.
6. Explain payload/shellcode fundamentals and C2 communication patterns (including DNS/HTTPS covert channels and fileless/LOLBin techniques) well enough to both build a lab-contained proof of concept and detect the pattern defensively.
7. Develop and explain a classic stack-overflow exploit end to end on a deliberately vulnerable target, including SEH behavior on Windows.
8. Explain and demonstrate, against vulnerable practice targets, ROP/DEP-NX bypass, ASLR-bypass concepts, format-string bugs, and introductory heap/UAF exploitation, and reproduce a historical, publicly documented CVE in an isolated lab.
9. Explain persistence and propagation mechanisms (registry/services/cron, rootkit/bootkit theory, worm propagation models) and, critically, how each is detected and removed.
10. Analyze Stuxnet, WannaCry, and NotPetya as case studies and map each to MITRE ATT&CK with threat-intel context.
11. Stand up detection content (YARA/Sigma, Sysmon, an ELK-based pipeline), perform threat hunting and IOC correlation, and run a structured incident-response process.
12. Complete a capstone demonstrating integrated offensive-research or defensive-detection capability, documented to a professional standard.

## Course structure

12 modules, each with 4–6 lessons (16–35 minutes of instructor-led video per lesson), a module lab set, and a module assessment. Total runtime target: ~26–30 hours of instruction plus lab time. See each module's `modules/module-NN/README.md` for the lesson-by-lesson breakdown, durations, and dependencies.

| # | Module | Focus | Est. runtime |
|---|---|---|---|
| 1 | Introduction to Malware & Exploitation | History, classification, kill chain, ATT&CK, legal/ethics | 1.5–2 h |
| 2 | Lab Setup and Tools | VMs, Ghidra/x64dbg/GDB/Wireshark/PEStudio, sandboxing | 2 h |
| 3 | Malware Development Fundamentals | PE/ELF, processes/memory, C/C++/Python for research, DLL internals | 2.5–3 h |
| 4 | Obfuscation, Evasion & Packing | Anti-debug/VM/sandbox, packing, control-flow obfuscation | 2.5 h |
| 5 | Malware Analysis & Reverse Engineering | Static/dynamic analysis, Ghidra, API tracing, IOC/YARA | 3 h |
| 6 | Payload Delivery & C2 Communication | Shellcode, C2 protocols, DNS/HTTPS covert channels, fileless/LOLBins | 3 h |
| 7 | Exploit Development Essentials | Assembly, stack overflows, GDB/x64dbg, SEH | 2.5 h |
| 8 | Advanced Exploitation Techniques | ROP, DEP/NX, ASLR, format strings, heap/UAF, historical CVE repro | 3 h |
| 9 | Persistence & Propagation | Registry/services, Linux persistence, rootkits/bootkits, worm models, forensic detection | 2 h |
| 10 | Real-World Case Studies | Stuxnet, WannaCry, NotPetya, APT campaigns, ATT&CK mapping, threat intel | 2 h |
| 11 | Defensive Strategies & Incident Response | YARA/Sigma, Sysmon/ELK, threat hunting, IOC correlation, red/blue exercises | 2.5 h |
| 12 | Final Capstone Project | Three tracks: exploit-dev, malware RE/detection, adversary emulation | self-paced |

## Assessment strategy

- **Per-lesson knowledge checks**: 5–10 questions (multiple-choice, technical-reasoning, scenario-based) with answer keys and explanations — see each lesson's `assessments/` entry.
- **Per-module assessment**: a cumulative written assessment plus one practical lab-based task, scored against a rubric in `modules/module-NN/assessments/`.
- **Capstone**: one of three tracks (Module 12), evaluated against `instructor/ASSESSMENT_RUBRICS.md`, producing a professional report as the primary deliverable.
- All claims about real CVEs, tool capabilities, and historical incidents are checked against primary/authoritative sources (vendor advisories, NVD/MITRE, CISA, original researcher write-ups) before being included — see `resources/REFERENCE_INDEX.md` once populated per module.

## Explicitly out of scope

Weaponized/production malware, live internet-facing C2 infrastructure, real-world unauthorized targeting, zero-day research against currently-supported commercial software, and any technique whose primary purpose is evading detection on a system the learner does not control. See **[LAB_SAFETY.md](LAB_SAFETY.md)** Section 2 for the full boundary list.

## Status

See **[PROGRESS.md](PROGRESS.md)** for which modules/lessons currently have complete content vs. outline-only.

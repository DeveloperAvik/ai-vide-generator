# Module 5: Malware Analysis & Reverse Engineering

## Lessons

| # | Lesson | Est. duration | Depends on |
|---|---|---|---|
| 5.1 | Static vs. Dynamic Analysis: Methodology and Triage Order | 18 min | Module 4 |
| 5.2 | Disassembly and Decompilation with Ghidra | 28 min | 5.1, Module 2 |
| 5.3 | Dynamic Analysis and API Tracing with x64dbg | 25 min | 5.1, 5.2 |
| 5.4 | Behavioral Analysis in a Sandbox (Cuckoo/CAPE) | 22 min | 2.5, 5.3 |
| 5.5 | IOC Extraction and Writing YARA Rules | 25 min | 5.2–5.4 |
| 5.6 | Capstone Lab: Full Analysis Report on a Provided Sample | 35 min | 5.1–5.5 |

## Module learning objectives

- Follow a repeatable triage order: hash/metadata → static strings/PEStudio → disassembly/decompile → dynamic trace → sandbox behavioral report → IOC write-up.
- Use Ghidra to decompile and annotate a sample's key functions.
- Use x64dbg to set breakpoints, trace API calls, and inspect memory/registers at a call of interest.
- Interpret a sandbox behavioral report (network/file/registry activity) and distinguish signal from noise.
- Extract accurate IOCs (hashes, strings, mutexes, network indicators) and write a specific, low-false-positive YARA rule.

## Lab set
- `labs/lab-05-06-full-analysis-report.md` — end-to-end analysis of a benign-but-representative sample built for this course, producing a written report + YARA rule (feeds directly into Capstone Track B).

## Module assessment
`assessments/module-05-assessment.md` (15 questions + the capstone-lab report as the practical component).

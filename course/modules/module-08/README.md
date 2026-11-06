# Module 8: Advanced Exploitation Techniques

## Lessons

| # | Lesson | Est. duration | Depends on |
|---|---|---|---|
| 8.1 | DEP/NX and Why Code Injection Alone Stops Working | 18 min | Module 7 |
| 8.2 | Return-Oriented Programming (ROP) Fundamentals | 28 min | 8.1 |
| 8.3 | ASLR and Bypass Concepts (Info Leaks, Partial Overwrites) | 25 min | 8.2 |
| 8.4 | Format-String Vulnerabilities | 22 min | 7.1–7.3 |
| 8.5 | Heap Exploitation Fundamentals and Use-After-Free | 30 min | 8.1 |
| 8.6 | Lab: Reproducing a Historical CVE in an Isolated VM | 40 min | 8.1–8.5, Module 7 |

Lesson 8.6 reproduces a single, pre-approved, long-patched, well-documented CVE against the vulnerable build it was originally reported against (pinned exact version, run air-gapped). The pre-approved list, selection rationale, and version pins live in `labs/lab-08-06-cve-reproduction.md`; no currently-supported software is targeted.

## Module learning objectives

- Explain why DEP/NX forces attackers toward code reuse rather than injected shellcode.
- Build a simple ROP chain against a practice binary to call an existing function with attacker-controlled arguments.
- Explain ASLR and how an information leak or partial-overwrite can defeat it in a specific, demonstrated scenario.
- Identify and exploit a format-string bug for a controlled read/write on a practice binary.
- Explain heap metadata/allocator concepts well enough to follow a basic use-after-free exploitation walkthrough.
- Reproduce one historical CVE end to end against its originally-vulnerable, pinned-version practice build, and write it up to the Track A rubric standard.

## Lab set
- `labs/lab-08-02-rop-chain.md`
- `labs/lab-08-06-cve-reproduction.md`

## Module assessment
`assessments/module-08-assessment.md` (15 questions + the CVE-reproduction lab as the practical component; doubles as Capstone Track A rehearsal).

# Module 7: Exploit Development Essentials

All exploit labs target a named, long-public, deliberately-vulnerable practice binary/VM run entirely inside the learner's isolated lab — never a currently-supported production target.

## Lessons

| # | Lesson | Est. duration | Depends on |
|---|---|---|---|
| 7.1 | x86/x64 Assembly Refresher for Exploit Development | 25 min | Module 3 |
| 7.2 | Stack Layout and the Mechanics of a Stack Overflow | 22 min | 7.1 |
| 7.3 | Crash Triage with GDB/x64dbg | 25 min | 7.2, Module 2 |
| 7.4 | Building a Linux Stack-Overflow Exploit (No Mitigations) | 30 min | 7.1–7.3 |
| 7.5 | Windows SEH Mechanics and SEH-Based Overflow Concepts | 28 min | 7.1–7.3 |
| 7.6 | Lab: End-to-End Exploit Against a Practice Binary | 35 min | 7.1–7.5 |

## Module learning objectives

- Read x86/x64 assembly well enough to follow a function prologue/epilogue and a stack-smashing crash.
- Explain stack layout (saved return address, saved frame pointer, canaries where present) and why an overflow can hijack control flow.
- Triage a crash in GDB/x64dbg to find the overflowing offset and the controlled bytes.
- Build a working exploit against a mitigation-free practice binary (`-fno-stack-protector`, no ASLR, as configured by the lab) that redirects execution to attacker-controlled code within the lab VM.
- Explain Windows SEH chain mechanics and how a classic SEH overwrite is constructed conceptually, with a guided SEH lab against a vulnerable practice target.

## Lab set
- `labs/lab-07-04-linux-stack-overflow.md`
- `labs/lab-07-06-end-to-end-exploit.md` — crash → triage → offset-finding → working exploit, write-up required.

## Module assessment
`assessments/module-07-assessment.md` (15 questions + the end-to-end exploit lab as the practical component).

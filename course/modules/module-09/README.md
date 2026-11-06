# Module 9: Persistence & Propagation

Every "build" exercise in this module is immediately paired with the matching detection/removal exercise in the same lesson — this module is taught defense-first.

## Lessons

| # | Lesson | Est. duration | Depends on |
|---|---|---|---|
| 9.1 | Windows Persistence: Registry Run Keys and Services | 22 min | Module 3 |
| 9.2 | Linux Persistence: Cron, systemd, Shell-Profile Mechanisms | 20 min | Module 3 |
| 9.3 | Fileless Persistence Concepts (WMI, Scheduled Tasks, Registry-Resident) | 22 min | 9.1, 6.6 |
| 9.4 | Rootkits and Bootkits: Theory and a Guided Conceptual Walkthrough | 28 min | Module 3, 4.3 |
| 9.5 | Worm Propagation Models (Theory Only, No Working Propagation Code) | 20 min | Module 6 |
| 9.6 | Lab: Detecting and Removing Lab-Built Persistence Mechanisms | 30 min | 9.1–9.3 |

**9.4 and 9.5 are explicitly non-executable / theory-and-diagram lessons.** Rootkit/bootkit mechanics (SSDT/IDT hooking concepts, bootloader-stage theory) are taught via diagrams, annotated public research, and (where available) analysis of a disclosed/patched proof-of-concept's published writeup — not by having the learner build a working rootkit. Worm propagation is taught via its historical mechanics (why Blaster/SQL Slammer/WannaCry's propagation component spread) and a non-functional pseudocode model; no self-propagating code is written or run, including inside the lab, per `LAB_SAFETY.md` §2.

## Module learning objectives

- Set and then detect/remove a Run-key and a service-based persistence mechanism on the Windows lab VM.
- Set and then detect/remove a cron and a systemd-based persistence mechanism on the Linux lab VM.
- Explain fileless persistence techniques and which Sysmon event IDs/log sources surface each.
- Explain rootkit/bootkit mechanics conceptually and name the detection approach for each category (integrity checking, hypervisor-based introspection, secure boot).
- Explain historical worm propagation mechanics and map each to the vulnerability/service it abused, without writing propagating code.

## Lab set
- `labs/lab-09-01-windows-persistence.md`
- `labs/lab-09-02-linux-persistence.md`
- `labs/lab-09-06-detect-and-remove.md`

## Module assessment
`assessments/module-09-assessment.md` (15 questions + the detect-and-remove lab as the practical component).

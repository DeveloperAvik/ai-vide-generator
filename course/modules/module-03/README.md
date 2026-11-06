# Module 3: Malware Development Fundamentals

## Lessons

| # | Lesson | Est. duration | Depends on |
|---|---|---|---|
| 3.1 | Windows PE Internals (Headers, Sections, Imports) | 25 min | Module 2 |
| 3.2 | Linux ELF Internals (Headers, Sections, Dynamic Linking) | 20 min | 3.1 |
| 3.3 | Processes, Threads, Memory, and System Calls | 25 min | 3.1, 3.2 |
| 3.4 | C/C++/Python for Security Research: a Minimal Toolkit | 20 min | 3.3 |
| 3.5 | DLL Architecture and Process Internals (Loading, Exports, Injection Concepts) | 25 min | 3.3, 3.4 |
| 3.6 | Lab: Building and Observing a Benign "Malware-Shaped" Program | 30 min | 3.1–3.5 |

Lesson 3.6 is the de-fanged, lab-only program: a program that logs its own keystrokes to a local file while it has focus and writes a heartbeat to a local log — both confined to the learner's own VM, with no persistence, no network activity, and no stealth. It exists to teach the mechanism (hooking a keyboard API, writing structured logs, basic process self-inspection), not to produce a deployable tool.

## Module learning objectives

- Parse a PE and an ELF file by hand (headers, sections, imports/exports) using a hex view plus PEStudio/`readelf`.
- Explain process creation, threads, virtual memory layout, and the user-mode/kernel-mode system-call boundary on both OSes.
- Write and compile a small C program and a small Python script that each demonstrate one documented OS mechanism (e.g., `SetWindowsHookEx` for input hooking, `ptrace`/`/proc` for process inspection) confined to the lab VM with no network or persistence behavior.
- Explain how DLLs are loaded and resolved, and describe (without weaponizing) how process injection techniques alter that normal flow — this sets up Module 5's detection-side coverage.

## Lab set
- `labs/lab-03-01-pe-elf-parsing.md`
- `labs/lab-03-06-benign-keylogger.md` — explicitly scoped: local-file logging only, deleted at lab end, never leaves the VM, no persistence mechanism installed (that's covered conceptually, not practically, until Module 9's detection-focused labs).

## Module assessment
`assessments/module-03-assessment.md` (15 questions + practical: annotate a provided PE header dump).

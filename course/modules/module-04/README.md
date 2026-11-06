# Module 4: Obfuscation, Evasion & Packing

## Lessons

| # | Lesson | Est. duration | Depends on |
|---|---|---|---|
| 4.1 | Static vs. Dynamic Obfuscation: Concepts and Goals | 18 min | Module 3 |
| 4.2 | Encryption and Packing Concepts (UPX and Custom Stub Theory) | 22 min | 4.1 |
| 4.3 | Anti-Debugging and Anti-Analysis Checks | 25 min | 3.3, 4.1 |
| 4.4 | Virtualization and Sandbox Detection Techniques | 20 min | 4.3 |
| 4.5 | Control-Flow Obfuscation (Flattening, Junk Code, Opaque Predicates) | 22 min | 4.1 |
| 4.6 | Lab: Reverse-Engineering a Deliberately Obfuscated Sample | 30 min | 4.1–4.5, Module 2 tooling |

All anti-debug/anti-sandbox checks are taught as **detection fodder** — every technique shown is paired with "here is exactly how an analyst spots this in Ghidra/x64dbg," per Module 5's framing. No lesson produces a fully-packed, fully-evasive standalone binary; the lab sample is intentionally only partially obfuscated so analysis remains tractable within the lesson time.

## Module learning objectives

- Distinguish static obfuscation (packing, string encryption) from dynamic/behavioral evasion (anti-debug/anti-VM checks).
- Explain how a simple packer stub (UPX-style) works and how to identify a packed binary statically.
- Recognize common anti-debug checks (`IsDebuggerPresent`, timing checks, `CPUID`/hypervisor-bit checks) and defeat them in a debugger for analysis purposes.
- Recognize control-flow flattening and opaque predicates in disassembly and explain the deobfuscation strategy.

## Lab set
- `labs/lab-04-06-deobfuscate-sample.md` — unpack and deobfuscate a provided benign sample built for this course; produce a clean decompiled listing.

## Module assessment
`assessments/module-04-assessment.md` (15 questions + practical: identify and defeat one anti-debug check in a provided binary).

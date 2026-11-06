# Learning Path & Lesson Dependencies

Modules are designed to be taken in order 1→12; most technical modules depend on Module 2 (lab) and Module 3 (fundamentals) being complete. This file lists cross-module dependencies; within-module lesson dependencies are listed in each `modules/module-NN/README.md`.

## Dependency graph (module level)

```
Module 1 (Intro) ─┐
                   ├─> Module 2 (Lab Setup) ─> Module 3 (Dev Fundamentals) ─┬─> Module 4 (Obfuscation/Evasion)
                   │                                                        ├─> Module 5 (Analysis & RE)
                   │                                                        └─> Module 6 (Payload/C2)
                   │
                   └─────────────────────────> Module 7 (Exploit Essentials) ─> Module 8 (Advanced Exploitation)

Modules 4,5,6,8 ──> Module 9 (Persistence & Propagation)
Modules 1,5,6,9 ──> Module 10 (Case Studies)
Modules 5,9,10 ──> Module 11 (Defense & IR)
All modules ─────> Module 12 (Capstone — pick a track)
```

## Recommended pacing (self-paced, ~8–10 h/week)

| Week | Modules |
|---|---|
| 1 | 1, 2 |
| 2 | 3 |
| 3 | 4 |
| 4 | 5 |
| 5 | 6 |
| 6 | 7 |
| 7 | 8 |
| 8 | 9 |
| 9 | 10 |
| 10 | 11 |
| 11–12 | 12 (capstone) |

## Fast tracks

- **Exploit-development track**: 1 → 2 → 3 → 7 → 8 → 12 (Track A), with Module 4 skimmed for anti-debugging context used during exploit dev under a debugger.
- **Malware-analysis/detection track**: 1 → 2 → 3 → 4 → 5 → 6 → 9 → 10 → 11 → 12 (Track B).
- **Adversary-emulation/blue-team track**: 1 → 2 → 10 → 11 → (selected labs from 4/5/6/9) → 12 (Track C).

## Certification alignment (for context, not a guarantee of exam coverage)

- Modules 2, 3, 7, 8 map to OSED/exploit-development style material.
- Modules 4, 5, 6, 9 map to GREM/malware-analysis style material.
- Modules 10, 11 map to GCIH/CTI/threat-hunting style material.

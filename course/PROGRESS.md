# Build Progress Tracker

Legend: ✅ complete content · 📝 outline only (README with lesson list/durations/deps) · ⬜ not started

## Phase 1 — Course Architecture
- ✅ `README.md`, `COURSE_OVERVIEW.md`, `LEARNING_PATH.md`, `LAB_SAFETY.md`, `PROGRESS.md`
- ✅ `requirements/ENVIRONMENT.md`
- ✅ `resources/REFERENCE_INDEX.md`
- ✅ `assessments/ASSESSMENT_STRATEGY.md`
- ✅ `capstone/README.md` (track overviews) — per-track detail pages ⬜
- ✅ `instructor/RECORDING_GUIDE.md`, `COURSE_DELIVERY_PLAN.md`, `ASSESSMENT_RUBRICS.md`
- ✅ `modules/module-01/README.md` … `modules/module-12/README.md` (all 12 outlined: lesson lists, durations, dependencies)

## Phase 2 — Detailed Module Content

| Module | Lesson READMEs (full content) | Labs | Module assessment |
|---|---|---|---|
| 1. Introduction | ✅ 5/5 | n/a (conceptual) | ✅ |
| 2. Lab Setup | ✅ 5/5 | ✅ 3 labs | ✅ |
| 3. Dev Fundamentals | ⬜ 0/6 | ⬜ | ⬜ |
| 4. Obfuscation/Evasion | ⬜ 0/6 | ⬜ | ⬜ |
| 5. Analysis & RE | ⬜ 0/6 | ⬜ | ⬜ |
| 6. Payload/C2 | ⬜ 0/6 | ⬜ | ⬜ |
| 7. Exploit Essentials | ⬜ 0/6 | ⬜ | ⬜ |
| 8. Advanced Exploitation | ⬜ 0/6 | ⬜ | ⬜ |
| 9. Persistence/Propagation | ⬜ 0/6 | ⬜ | ⬜ |
| 10. Case Studies | ⬜ 0/6 | ⬜ | ⬜ |
| 11. Defense & IR | ⬜ 0/6 | ⬜ | ⬜ |
| 12. Capstone | n/a | n/a (capstone/ track pages) | n/a |

## Phase 3 — QA
⬜ Not started (runs after each module's Phase 2 content is drafted: technical-accuracy pass, prerequisite check, lab-instruction validation, dedup, reference check).

## Phase 4 — Final Delivery
⬜ Not started (final docs already drafted in Phase 1 — instructor guide, delivery plan, rubrics — will get a final consistency pass once all modules are complete).

## Resume instructions

Work proceeds module-by-module, in order (2 → 11), following the same lesson-README structure used in `modules/module-01/lessons/*/README.md` (metadata → objectives → conceptual explanation → instructor script → practical demonstration → hands-on lab → knowledge assessment → further learning), plus a `labs/lab-NN-*.md` file per hands-on lab referenced from the lesson, and a `assessments/module-NN-assessment.md` cumulative assessment. Update this table's row to ✅ as each module's lessons/labs/assessment are completed. Do not overwrite a ✅ row without re-reading its files first.

**Last completed:** Module 2 (full: 5 lesson READMEs, 3 labs, module assessment, references), Module 1 (full), Phase 1 architecture (full).
**Next up:** Module 3 — Malware Development Fundamentals.

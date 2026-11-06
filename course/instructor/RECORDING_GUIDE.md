# Instructor Recording Guide

## Opening every module

1. State the module number/title and the lessons it contains.
2. For the **first** technical module a cohort encounters (Module 2 onward), display the safety acknowledgment from `LAB_SAFETY.md` §5 as an on-screen title card and read it aloud before any demonstration. Repeat a short reminder ("isolated lab, your own VM, no real targets") verbally at the start of every subsequent lab segment.
3. State learning objectives from the lesson README verbatim or near-verbatim.

## Recording conventions

- **Screen layout**: instructor cam (intro/summary segments) → slides (concept segments) → terminal/tool capture at 1080p+ (lab segments), matching the `type` values used in `lessons/sqli_fundamentals/bundle.json` (`instructor`, `slide`, `diagram`, `code`, `terminal`, `quiz`, `summary`) if this course is later adapted into that pipeline.
- **Pacing**: speak the instructor script near verbatim; it's written for spoken delivery (expanded numbers/acronyms, short sentences). Pause briefly after each on-screen bullet appears.
- **Lab segments**: narrate what you're about to type before typing it, then narrate the result. Call out the VM name/network mode on screen at the start of each lab segment as a visible reminder of isolation.
- **Never show**: real credentials, real IPs/hostnames beyond lab-internal ones (10.x/192.168.x/RFC1918 only), or any pane revealing a real external account.

## Per-lesson checklist before recording

- [ ] Safety acknowledgment shown (if first lab of the module).
- [ ] Lab VM reverted to its clean snapshot.
- [ ] Lab's required tools confirmed installed/working (`requirements/ENVIRONMENT.md`).
- [ ] Script reviewed for any claim needing a citation (`resources/REFERENCE_INDEX.md`).
- [ ] Knowledge-check slide matches the README's current question set.

## After recording

- Export the raw lab terminal capture alongside the final cut (mirrors `recordings:` mapping in `lessons/sqli_fundamentals/bundle.json`), so a learner can reproduce the exact commands.
- File the recording under the module/lesson it belongs to and update `PROGRESS.md`.

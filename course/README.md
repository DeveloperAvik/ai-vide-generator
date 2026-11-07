# Malware & Exploit Development Masterclass

A 12-module, advanced-level course for authorized red-team professionals, exploit-development researchers, malware analysts, and vulnerability researchers. All technical labs run against isolated VMs and deliberately vulnerable, publicly-known practice targets — never against real-world systems. **Read [LAB_SAFETY.md](LAB_SAFETY.md) before touching any technical module.**

## Start here

1. **[LAB_SAFETY.md](LAB_SAFETY.md)** — binding scope, authorization models, and lab-isolation rules for the whole course.
2. **[COURSE_OVERVIEW.md](COURSE_OVERVIEW.md)** — audience, prerequisites, full module table, learning outcomes, assessment strategy.
3. **[LEARNING_PATH.md](LEARNING_PATH.md)** — module dependency graph, pacing plan, fast tracks.
4. **[PROGRESS.md](PROGRESS.md)** — build status: what's fully written vs. outline-only right now.

## Repository layout

```
course/
├── README.md                  you are here
├── COURSE_OVERVIEW.md         audience, outcomes, module table, assessment strategy
├── LEARNING_PATH.md           dependency graph, pacing, fast tracks
├── LAB_SAFETY.md              binding scope & authorization policy
├── PROGRESS.md                build/completion tracker
├── requirements/              environment & tooling requirements
├── resources/                 course-wide reference index
├── assessments/               course-wide assessment strategy notes
├── capstone/                  the three Module 12 capstone tracks
├── modules/
│   ├── module-01/ … module-12/
│   │   ├── README.md          module overview + lesson list + durations + dependencies
│   │   ├── lessons/           one subfolder per lesson, full lesson content
│   │   ├── instructor-scripts/(script text also embedded in each lesson's README)
│   │   ├── labs/              lab READMEs (objective, setup, steps, validation, cleanup)
│   │   ├── assessments/       module-level assessment + rubric
│   │   └── resources/         module-level reference list
└── instructor/
    ├── RECORDING_GUIDE.md
    ├── COURSE_DELIVERY_PLAN.md
    └── ASSESSMENT_RUBRICS.md
```

## For instructors recording this course

See `instructor/RECORDING_GUIDE.md` for on-camera conventions (including the safety acknowledgment required before any technical demo) and `instructor/COURSE_DELIVERY_PLAN.md` for a cohort/schedule plan.

## Relationship to the rest of this repository

This `course/` tree is a standalone, hand-authored curriculum, independent of the `ciphercast` automated lesson-production pipeline described in the top-level `README.md`. If a lesson here is later adapted into that pipeline's video format, convert it into a `lessons/<slug>/bundle.json` following `ai/schemas/lesson.schema.json` / `ai/schemas/storyboard.schema.json`, per `lessons/sqli_fundamentals/` as the worked example.

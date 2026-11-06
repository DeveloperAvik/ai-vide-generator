# Module 11: Defensive Strategies & Incident Response

## Lessons

| # | Lesson | Est. duration | Depends on |
|---|---|---|---|
| 11.1 | Detection Engineering with YARA and Sigma | 25 min | Module 5, 9 |
| 11.2 | Telemetry with Sysmon and the ELK Stack | 25 min | 9.1, 9.2 |
| 11.3 | Threat Hunting Methodology | 22 min | 10.6, 11.1 |
| 11.4 | IOC Correlation Across Log Sources | 22 min | 11.2, 11.3 |
| 11.5 | Incident-Response Process (Prepare/Detect/Contain/Eradicate/Recover/Lessons-Learned) | 25 min | 11.1–11.4 |
| 11.6 | Lab: Red-Team-vs-Blue-Team Exercise in the Isolated Lab | 35 min | 11.1–11.5, Module 6, 9 |

## Module learning objectives

- Write Sigma rules alongside YARA rules and explain when each applies.
- Deploy Sysmon with a sensible config and route events into an ELK/OpenSearch pipeline.
- Run a structured threat hunt from a hypothesis through to a documented finding (or documented "no finding").
- Correlate IOCs across process, network, and file-system telemetry.
- Execute each IR phase with the correct documentation for a given scenario.
- Participate in a lab-contained red/blue exercise and produce a report from the blue perspective.

## Lab set
- `labs/lab-11-02-sysmon-elk-pipeline.md`
- `labs/lab-11-06-red-vs-blue.md` — reuses artifacts from Modules 6 and 9 as the "red" activity inside the isolated lab; learner builds detections and writes the IR report as "blue."

## Module assessment
`assessments/module-11-assessment.md` (15 questions + the red-vs-blue lab report as the practical component; feeds directly into Capstone Track C).

# Lab Safety, Scope & Authorization Policy

This document is binding for every module, lesson, and lab in this course. It is read before any technical module and referenced at the top of every hands-on lab. No exercise in this course may be delivered, recorded, or performed outside these constraints.

## 1. Who this course is for

Experienced penetration testers, authorized red-team operators, exploit-development researchers, malware analysts, vulnerability researchers, and advanced security students, all operating under one of the authorization models in Section 3.

## 2. What this course will never ask a learner to do

- Target, scan, exploit, or extract data from any system the learner does not own or does not hold explicit written authorization to test.
- Deploy any sample, payload, or technique against production systems, third-party infrastructure, or any network segment shared with untrusted hosts.
- Build or release self-propagating code (worms, auto-spreading payloads) in any form that leaves the learner's isolated lab, or self-propagating code at all outside a single host-to-host demonstration inside a fully air-gapped lab segment the learner controls end to end.
- Produce malware, exploits, or tooling designed for real-world criminal use, fully weaponized/operational payloads, or production-grade C2 implants intended for deployment outside the lab.
- Harvest, exfiltrate, or retain real credentials, personal data, or data belonging to a real person or organization.
- Evade or defeat detection/security controls on any system other than the learner's own disposable lab VM, for any purpose other than understanding the control well enough to detect or defend against it.

Where a module title mentions a capability (e.g., "keylogger," "C2 server," "rootkit"), the lesson teaches the underlying mechanism conceptually, with code that is illustrative, deliberately incomplete or de-fanged (no real network exfiltration, no real stealth, no persistence beyond the lab VM), and run only against the learner's own isolated VM. Nothing in this course is "ready to deploy."

## 3. Acceptable authorization models (pick one before starting technical modules)

| Model | What satisfies it |
|---|---|
| Personal lab | Hardware or VMs you own outright, never bridged to a production or shared network. |
| Employer-sanctioned research | Written internal authorization naming the systems, scope, and dates (standard for malware-analysis/detection-engineering teams). |
| Signed penetration-test engagement | A rules-of-engagement document and signed authorization from the system owner, scoped to specific targets and dates. |
| Public legal training range | A platform whose terms explicitly permit offensive testing (e.g., vendor-provided CTF infrastructure, vulnerable-by-design VM images distributed for this purpose, licensed certification labs). |

If none of these apply to the system in front of you, you do not have authorization. Stop.

## 4. Lab environment requirements (enforced in every lab)

1. **Isolation** — Victim/target VMs run in a hypervisor with networking set to Host-Only or an internal-only virtual switch. No bridged adapters, no NAT to the internet, unless a lab explicitly calls for a single outbound HTTPS test to a service you control, in which case the lab says so and still forbids a bridged adapter.
2. **Disposability** — Snapshot the clean VM state before each exercise. Labs assume you will revert, not "clean up by hand." Any sample built or run in a lab is destroyed (snapshot revert / VM deletion) at the end of the lesson unless explicitly kept for the next lesson in the same module.
3. **Synthetic data only** — No real credentials, real PII, real corporate data, or real production configuration ever enters a lab VM.
4. **Separate attacker/victim roles** — Where a lab has two VMs, both are yours, both are isolated, and the "network" between them does not touch any other device.
5. **No internet-facing services** — Nothing built in this course is ever exposed to a public IP, a cloud instance reachable from the internet, or a shared Wi-Fi/LAN segment.
6. **Tooling** — Prefer free/open tools (Ghidra, x64dbg, GDB, Wireshark, PEStudio, Cuckoo/CAPE, YARA, Sysmon, the ELK stack, Volatility). Where a lab uses a known intentionally-vulnerable target (e.g., a VulnHub/HackTheBox-style VM, a classic stack-overflow practice binary, DVWA-style web app), it names the specific public resource rather than a bespoke unreviewed binary.

## 5. Instructor/learner acknowledgment

Every module's first lesson video and every lab README restate, in the learner's own words by the end of the segment: *"I will only perform these exercises in an isolated lab I own or am explicitly authorized to use, and I will not take any technique taught here outside that lab without separate written authorization."* Recorded course deliveries should capture this acknowledgment on screen (e.g., as an opening title card) before any technical demonstration.

## 6. Reporting conduct (carried into Module 6 and the capstone)

Any real-world finding that falls out of authorized work (e.g., during an actual engagement) is reported through the engagement's agreed channel with root cause, affected component, minimal proof-of-concept, and remediation — never with a working exploit chain, a data dump, or a public disclosure that bypasses the vendor/program's coordinated disclosure process.

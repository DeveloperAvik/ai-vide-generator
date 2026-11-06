# Module 2: Lab Setup and Tools

**Gate:** learner must have read `LAB_SAFETY.md` and hold an acceptable authorization model before starting lesson 2.1's hands-on portion.

## Lessons

| # | Lesson | Est. duration | Depends on |
|---|---|---|---|
| 2.1 | Building an Isolated VM Lab (VirtualBox, Host-Only Networking, Snapshots) | 25 min | Module 1 |
| 2.2 | Windows and Linux Malware-Analysis VM Builds | 20 min | 2.1 |
| 2.3 | Core Static/Debug Tooling: Ghidra, x64dbg, GDB, PEStudio | 25 min | 2.2 |
| 2.4 | Network Monitoring with Wireshark in an Isolated Lab | 15 min | 2.1 |
| 2.5 | Sandbox Setup and Safe C2 Simulation (Internal-Only) | 20 min | 2.2, 2.3 |

## Module learning objectives

- Stand up two isolated VMs on Host-Only/internal-only networking with working snapshots.
- Install and smoke-test Ghidra, x64dbg, GDB, PEStudio, and Wireshark.
- Explain why bridged/NAT-to-internet networking is forbidden for the remainder of the course, and configure a sandbox (Cuckoo/CAPE) that stays fully internal.

## Lab set
- `labs/lab-02-01-vm-build.md` — build and snapshot both analysis VMs.
- `labs/lab-02-03-tool-smoketest.md` — verify each tool runs against a trivial known-good binary.
- `labs/lab-02-05-sandbox-c2-sim.md` — stand up an internal-only "C2" listener on the Linux VM and confirm the Windows VM can reach it only inside the Host-Only network.

## Module assessment
`assessments/module-02-assessment.md` (12 questions + practical: screenshot evidence of isolated network config and a successful tool smoke-test).

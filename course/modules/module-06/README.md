# Module 6: Payload Delivery & C2 Communication

All C2 labs run **entirely within the Host-Only/internal-only lab network** built in Module 2. No lesson produces a C2 implant capable of reaching the public internet; every "client/server" exercise connects two of the learner's own VMs only.

## Lessons

| # | Lesson | Est. duration | Depends on |
|---|---|---|---|
| 6.1 | Shellcode Architecture and Concepts | 20 min | Module 3 |
| 6.2 | Payload Types and Static Analysis of Payloads | 20 min | 6.1, Module 5 |
| 6.3 | Client-Server Communication Fundamentals for C2 | 22 min | 6.1 |
| 6.4 | C2 Protocol Analysis and Lab-Internal Simulation | 28 min | 6.3, 2.5 |
| 6.5 | DNS and HTTPS Covert-Channel Traffic Analysis | 25 min | 6.4, Module 2 (Wireshark) |
| 6.6 | Fileless Malware and LOLBins: Concepts and Detection | 22 min | 6.2 |

Lesson 6.4's "C2 simulation" is a minimal, plaintext-logged client/server pair between the learner's two lab VMs, used to generate real traffic for Wireshark analysis in 6.5 — not a feature-complete C2 framework.

## Module learning objectives

- Explain what shellcode is, why it's position-independent, and how to recognize it in a hex dump/disassembly.
- Classify payload types (dropper, stager, implant) and analyze one statically.
- Build and analyze a minimal lab-internal client/server exchange to understand C2 beaconing patterns (interval, jitter, check-in structure).
- Analyze DNS-tunneling and HTTPS-covert-channel traffic in Wireshark and identify the indicators that distinguish it from normal traffic.
- Explain fileless execution and LOLBin abuse (e.g., signed-binary proxy execution) conceptually and list the Sysmon/EDR telemetry that detects each.

## Lab set
- `labs/lab-06-04-c2-sim.md` — internal-only client/server beacon between two lab VMs.
- `labs/lab-06-05-traffic-analysis.md` — capture and analyze the 6.4 traffic plus a provided DNS-tunneling pcap.

## Module assessment
`assessments/module-06-assessment.md` (15 questions + practical: annotate a provided pcap identifying the covert channel).

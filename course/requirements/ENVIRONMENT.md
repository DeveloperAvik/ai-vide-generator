# Environment & Tooling Requirements

## Hardware (minimum)

- CPU with VT-x/AMD-V enabled in firmware; 4+ cores recommended for running two VMs at once.
- 16 GB RAM recommended (8 GB minimum, tight for a Windows analysis VM + Linux attacker VM simultaneously).
- 100+ GB free disk for VM images, snapshots, and sample storage.

## Hypervisor & VMs

- VirtualBox 7.x (free) or VMware Workstation/Fusion Player (free for personal use). All lab networking uses **Host-Only** or an **internal-only virtual switch** — see `LAB_SAFETY.md`.
- **Analysis VM (Windows)**: Windows 10/11 evaluation ISO (Microsoft provides time-limited eval images for this exact purpose), isolated, snapshot before every lab.
- **Analysis VM (Linux)**: a current Ubuntu or Kali LTS image, isolated, snapshot before every lab.
- **Victim/target VMs**: built per-module from the specific practice targets named in that module's labs (e.g., a classic stack-overflow practice binary set, a deliberately vulnerable web app, a public vulnerable-VM image). No bespoke unreviewed binaries are downloaded from unknown sources.

## Core tools (free/open unless noted)

| Tool | Used in | Purpose |
|---|---|---|
| Ghidra | 5, 8 | Disassembly/decompilation |
| x64dbg | 5, 7, 8 | Windows user-mode debugging |
| GDB + GEF/pwndbg | 7, 8 | Linux debugging, exploit dev |
| Wireshark | 6, 11 | Network/traffic analysis |
| PEStudio | 5 | Static PE triage |
| YARA | 5, 11 | Pattern-based detection |
| Sigma | 11 | Detection-rule format for log sources |
| Sysmon | 9, 11 | Windows telemetry |
| ELK stack (Elasticsearch/Logstash/Kibana) or OpenSearch | 11 | Log aggregation/threat hunting |
| Cuckoo Sandbox or CAPE Sandbox | 5 | Automated dynamic analysis |
| Process Monitor / Process Hacker | 3, 9 | Windows process/registry observation |
| Volatility 3 | 9, 11 | Memory forensics |
| Python 3.11+, GCC/MinGW, Visual Studio Build Tools (free) | 3–9 | Building lab samples |

## Account/licensing notes

All listed tools have a free tier sufficient for this course. No paid licenses are required. Where a module references a commercial EDR/AV product conceptually (for evasion/detection discussion), no purchase or installation is required — the discussion stays at the level of publicly documented product behavior.

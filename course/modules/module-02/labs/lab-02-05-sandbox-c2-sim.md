# Lab 2.5 — Internal-Only Beacon Simulation and Pattern Observation

**Safety acknowledgment (restate before starting):** *"I will only perform these exercises in an isolated lab I own or am explicitly authorized to use, and I will not take any technique taught here outside that lab without separate written authorization."*

**Scope boundary (restate before starting, specific to this lab):** the listener/beacon pair built in this lab is benign, executes no received instruction beyond printing a fixed string, never persists past this session, and never communicates outside the Host-Only network established in Lesson 2.1. Any modification that adds persistence, arbitrary command execution, or outbound reach beyond the Host-Only network is out of scope for this course — see `../../../LAB_SAFETY.md` §2 and §4.

**Covers:** Lesson 2.5 (Sandbox Setup and Safe "C2" Simulation).

## Objective
Stand up a minimal, benign client/server pair that demonstrates the network *shape* of C2 beaconing (periodic outbound connection, small request/response), observe it in Wireshark, and correctly distinguish the pattern from an actual implant.

## Required tools
Python 3 on both VMs (already present on the Linux image; install on Windows via `python.org`'s installer or `winget install Python.Python.3`). Wireshark (Lesson 2.4). Both VMs restored to their `tools-installed` snapshot.

## Environment setup
Revert both VMs to `tools-installed` before starting. Confirm the Host-Only isolation check (`ping 8.8.8.8` fails) still holds on both before proceeding.

## Exercise instructions

1. On the Linux VM, create `listener.py` with the exact contents from Lesson 2.5's Practical Demonstration. Run it: `python3 listener.py`. Confirm it prints a "bound on 0.0.0.0:4444" line.
2. On the Windows VM, create `beacon.py` with the exact contents from Lesson 2.5's Practical Demonstration, substituting the Linux VM's actual current Host-Only IP (check with `ip addr show` on the Linux VM first — do not assume it matches the lesson's example). Run it: `python beacon.py`.
3. Let it run for at least one minute (≈12 beacon cycles at the 5-second interval) so at least one `task:print-hello` cycle occurs (every 4th response in the example rotation).
4. Start a Wireshark capture on the Host-Only interface, let it run across several beacon cycles, then stop it. Apply display filter `ip.addr == <linux-vm-ip> && tcp.port == 4444`.
5. In the packet list, identify and annotate (via Wireshark's "Add a comment" or just in your lab notes): one full handshake-request-response-FIN cycle, and the approximate timing interval between cycle starts.
6. Capture a screenshot of: (a) the beacon console output showing at least one `hello` print, (b) the filtered Wireshark capture showing the periodic pattern.
7. Stop both scripts (Ctrl+C). Shut down both VMs. Revert both to `tools-installed` (this lab's artifacts are not meant to persist).

## Expected observations
- The beacon prints `no-task` on most cycles and `hello` after receiving `task:print-hello`.
- Wireshark shows a new TCP handshake roughly every 5 seconds on port 4444, each followed by one small packet each direction and a connection close — a visibly periodic rhythm, distinct from ordinary human-driven browsing traffic (which is bursty and irregular).

## Validation steps
Instructor/peer confirms both screenshots from step 6, and that the learner can verbally explain, in their own words, why this traffic pattern (not its specific port number or payload text) is what a real detection rule or analyst would flag as anomalous.

## Troubleshooting
- **`OSError: Address already in use` on the listener:** a previous instance is still running — `pgrep -af listener.py` on Linux, then `kill <pid>`, or change the port in both scripts consistently.
- **Beacon hangs on connect, never prints:** confirm the IP in `beacon.py` matches the Linux VM's *current* Host-Only address (DHCP leases can change between reboots — re-check with `ip addr show`), and that `listener.py` is running first. If it still hangs, re-run the Lesson 2.1 isolation check on the Windows VM to rule out an accidentally-changed network adapter.
- **Wireshark shows no port-4444 traffic:** confirm the capture interface is the Host-Only adapter, and that both scripts are actually running (check each VM's own console for errors).

## Cleanup/reset
**Mandatory, not optional for this lab specifically:** stop both scripts and revert both VMs to `tools-installed` at the end of the session — do not leave the listener/beacon pair running between sessions, and do not keep this exercise's code outside the lab VMs.

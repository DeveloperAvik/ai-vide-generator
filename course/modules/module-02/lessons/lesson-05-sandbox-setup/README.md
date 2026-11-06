# Lesson 2.5 — Sandbox Setup and Safe "C2" Simulation (Internal-Only)

## Lesson Metadata
- **Module:** 2 — Lab Setup and Tools
- **Lesson:** 5 of 5
- **Difficulty:** Foundational
- **Estimated duration:** 20 minutes
- **Prerequisites:** 2.2, 2.3 (both VMs built, hardened, tools installed)

## Learning Objectives
By the end of this lesson, the learner can:
1. Explain what an automated dynamic-analysis sandbox (Cuckoo/CAPE) is for, and why this lesson sets up only its concepts/a minimal stand-in rather than a full production deployment.
2. Stand up a benign listener process on the Linux VM and a matching benign client on the Windows VM, communicating only across the Host-Only network, to understand the client/server shape of command-and-control traffic without building anything resembling a real implant.
3. Observe that traffic in Wireshark and correctly identify it as a benign simulation, distinguishing "the networking pattern of C2" from "an actual C2 implant" — a distinction this course maintains throughout Module 6.
4. State, from memory, why this exercise never leaves the Host-Only network and why that boundary is non-negotiable per `LAB_SAFETY.md`.

## Conceptual Explanation

**What a sandbox is, and why this lesson keeps it minimal.** Cuckoo Sandbox and its actively-maintained fork CAPE automate dynamic malware analysis: they run a sample inside a disposable VM, record its behavior (API calls, file/registry changes, network traffic), and produce a report — a faster, more repeatable version of the manual dynamic analysis Module 5 teaches by hand. A full Cuckoo/CAPE deployment is a nontrivial multi-VM install (a management host plus one or more analysis VMs with a specific agent). This lesson introduces the concept and points to the project's own setup documentation for a full install, because a real deployment is better done by following the current upstream guide (versions and steps change) than memorized from a video. What this lesson *does* build hands-on is the piece that matters for understanding the concept and for this lesson's actual title: a minimal, clearly-labeled stand-in that demonstrates the client/server network shape a sandbox would be watching for.

**Why "C2 simulation," precisely, and what it is not.** Command-and-control (C2) communication — covered properly in Module 6 — is simply a network conversation between an implant and an operator: the implant periodically connects out and asks "anything for me to do?" (a *beacon*), and occasionally receives an instruction. The *networking pattern* (periodic outbound connection, small request, variable response) is what detection tooling and analysts actually look for; it's a pattern, not a secret. This lesson's exercise builds exactly that pattern — a benign listener on the Linux VM, a client on the Windows VM that connects to it every few seconds and prints whatever short, harmless text string the listener sends back — and nothing else. It does not execute received commands, does not persist, does not survive a reboot, and does not run outside this single lab exercise. It exists so a learner can *see* the pattern in Wireshark (Lesson 2.4's tool) before Module 6 discusses real-world variants (DNS/HTTPS covert channels, jitter, fileless delivery) conceptually.

**Why this stays internal-only, categorically.** `LAB_SAFETY.md` §2 and §4 are explicit: nothing built in this course is ever exposed to a public IP or reachable from a shared network segment, and self-propagating or production-grade C2 tooling is out of scope entirely. This exercise's listener and client are both ordinary, single-purpose scripts the learner writes themselves, communicate only on the 192.168.56.x Host-Only network from Lesson 2.1, and are destroyed (process killed, VM reverted) at the end of the lesson.

## Instructor Script

"Last lesson of this module, and it's the one where I want to be the most explicit about scope, because the title has the letters 'C2' in it and I don't want anyone to walk away with the wrong idea about what we're building.

First, a sandbox. Cuckoo Sandbox, and its more actively maintained fork, CAPE, are tools that automate what Module 5 teaches you to do by hand: run a suspicious file inside a disposable VM, and record everything it does — API calls, files it touches, registry changes, network connections — into a report, without you having to babysit a debugger the whole time. A full deployment is genuinely involved — it wants a management host plus one or more analysis VMs running a lightweight agent — and the exact install steps shift between releases, so rather than walk through a full deployment that might be stale by the time you watch this, I'm pointing you at the project's own current setup docs in Further Learning, and we're going to spend our hands-on time here on something smaller but more durable: understanding the actual network *pattern* a sandbox — or a human analyst — is watching for.

That pattern is command-and-control, or C2, and here's the core idea, stripped down to its simplest possible form: an implant on a compromised machine periodically reaches out to a server the attacker controls and essentially asks, 'anything for me to do?' That's called beaconing. The server either says 'nothing yet' or sends back an instruction. That's the entire shape of it — a periodic outbound connection, a small request, a response that varies in size depending on whether there's a real instruction. Module 6 goes deep on how real-world C2 disguises this pattern — blending into DNS queries, hiding inside HTTPS traffic that looks like normal web browsing, adding random jitter to the timing so it doesn't look perfectly periodic. Today, we're building only the bare skeleton of that pattern, in the most obviously benign way possible, so you can actually see it in Wireshark before we talk about how real implants disguise it.

On the Linux VM, I'm writing maybe fifteen lines of Python — a TCP server on a port, say 4444, that on each connection just sends back a short, harmless string, something like 'no-task' most of the time, and occasionally 'task:print-hello' to simulate an instruction existing. On the Windows VM, an equally small Python client that connects to the Linux VM's Host-Only address on port 4444 every five seconds, reads whatever comes back, and prints it to the console — and if it ever reads 'task:print-hello', the entire extent of 'executing' that instruction is printing the word hello to its own console. Nothing more. No file writes, no persistence, no process injection, nothing that survives this lesson.

Let's run it. Server first, on Linux: python3, our listener script, and it'll print a line each time a client connects. Client on Windows: python3, our beacon script, and you'll see it print 'no-task' every five seconds, then eventually 'task:print-hello' followed by our client printing 'hello'.

Now open Wireshark — same Host-Only interface from Lesson 2.4 — and watch this traffic live. You'll see exactly the pattern we described: a new TCP connection every five seconds, a tiny request, a small response, over and over. That rhythm — a connection, then silence, then another connection at a predictable interval — is precisely what a human threat hunter or an automated detection rule is trained to notice as anomalous on a real network, because normal applications don't usually behave this way. You're not just building a toy; you're looking directly at the signature Module 11's detection content is designed to catch.

I want to say the boundary out loud one more time, because I mean this literally, not as a disclaimer: this listener and this client exist only on our 192.168.56.x Host-Only network. They have never been designed to do anything beyond what you just watched them do, they do not persist past this VM session, and at the end of this lesson both VMs get reverted to their tools-installed snapshot. If you ever find yourself wanting to make this 'more realistic' — have it survive a reboot, have it actually execute arbitrary commands, point it at a real external address — stop: that is explicitly the line this course does not cross, per lab-safety-dot-m-d, and it's also simply not what this lesson is for. What this lesson is for is giving you one clean, honest mental picture of what 'beaconing' looks like on the wire, so that Module 6's deeper conceptual discussion and Module 11's detection content both have something concrete to point back to."

## Practical Demonstration

```python
# listener.py — runs on the Linux VM only. Benign, single-purpose, no persistence.
import socket, itertools

HOST, PORT = "0.0.0.0", 4444
responses = itertools.cycle(["no-task", "no-task", "no-task", "task:print-hello"])

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen()
    print(f"[listener] bound on {HOST}:{PORT} (Host-Only network only)")
    while True:
        conn, addr = srv.accept()
        msg = next(responses)
        print(f"[listener] connection from {addr}, sending: {msg}")
        conn.sendall(msg.encode())
        conn.close()
```

```python
# beacon.py — runs on the Windows VM only. Prints 'hello' on a task; does nothing else.
import socket, time

SERVER = "192.168.56.102"   # Linux VM's Host-Only address — never a real/external host
PORT = 4444

while True:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((SERVER, PORT))
        msg = s.recv(1024).decode()
        print(f"[beacon] received: {msg}")
        if msg == "task:print-hello":
            print("hello")   # the entire extent of 'executing' a task
    time.sleep(5)
```

```
# Linux VM:
$ python3 listener.py
[listener] bound on 0.0.0.0:4444 (Host-Only network only)
[listener] connection from ('192.168.56.101', 51223), sending: no-task
[listener] connection from ('192.168.56.101', 51224), sending: no-task
[listener] connection from ('192.168.56.101', 51225), sending: no-task
[listener] connection from ('192.168.56.101', 51226), sending: task:print-hello

# Windows VM:
C:\lab> python beacon.py
[beacon] received: no-task
[beacon] received: no-task
[beacon] received: no-task
[beacon] received: task:print-hello
hello
```

```
# Wireshark, same Host-Only interface, display filter:
ip.addr == 192.168.56.102 && tcp.port == 4444
```
Expected: a new SYN/SYN-ACK/ACK handshake roughly every 5 seconds, each followed by one small data packet each direction, then a FIN — the visible "beacon" rhythm.

**Common error and fix — `OSError: [Errno 98] Address already in use` on the listener:**
```
$ python3 listener.py
OSError: [Errno 98] Address already in use
```
Fix: a previous run of the listener is still bound to port 4444 (e.g., from a terminal you forgot was open). Find and stop it (`pgrep -af listener.py`, then `kill <pid>`), or change `PORT` in both scripts consistently, then retry.

**Common error and fix — beacon.py hangs on `connect`, never prints anything:**
Confirm the Linux VM's address in `beacon.py` matches its *current* Host-Only IP (`ip addr show` on the Linux VM — DHCP leases can change across reboots) and that the listener is actually running first. This is also the expected failure mode if the Windows VM's adapter was accidentally left on NAT/Bridged instead of Host-only — re-run the Lesson 2.1 isolation check (`ping 8.8.8.8` should fail) to rule that out before debugging the script further.

## Hands-On Lab

See `labs/lab-02-05-sandbox-c2-sim.md` for the full lab: stand up the listener/beacon pair, observe the pattern in Wireshark, capture a screenshot of both the console output and the filtered Wireshark capture as lab evidence, then revert both VMs to their `tools-installed` snapshot.

## Knowledge Assessment

1. **(MC)** What is "beaconing," in the simplified model this lesson builds? **A)** A one-time file upload **B)** A periodic outbound connection from an implant asking whether there's an instruction to run **C)** A DNS zone transfer **D)** A type of port scan
   **Answer: B.**

2. **(Technical reasoning)** Why does this lesson's `beacon.py` only print the word "hello" rather than actually executing an arbitrary command received from the server?
   **Answer:** Executing arbitrary received instructions would start to resemble a real, generically-capable C2 implant rather than an illustrative demonstration of the beaconing network pattern; keeping the "task" hard-coded and harmless keeps the exercise de-fanged per `LAB_SAFETY.md`, which is the entire point of the lesson.

3. **(MC)** What network behavior makes beaconing traffic stand out to a threat hunter, per this lesson? **A)** Large file transfers **B)** A connection, then silence, then another connection at a roughly predictable interval **C)** Use of HTTPS **D)** High packet loss
   **Answer: B.**

4. **(Scenario)** A learner is tempted to make the lab exercise "more realistic" by having `beacon.py` persist via a scheduled task and reach out to a public IP they control, to see if it still works from outside the lab. What is the correct response?
   **Answer:** Do not do this. It crosses `LAB_SAFETY.md` §2/§4 directly (no persistence beyond the lab VM, no exposure beyond the Host-Only network); the exercise's educational value is in observing the pattern, not in building something that behaves like a real implant.

5. **(MC)** Why does this lesson point to Cuckoo/CAPE's own documentation for a full sandbox deployment rather than walking through one step by step? **A)** A full deployment is out of scope for this course entirely **B)** The install is multi-VM and version-specific enough that following current upstream docs is more reliable than a fixed video walkthrough **C)** Cuckoo/CAPE are paid tools **D)** Sandboxes are not used anywhere else in this course
   **Answer: B.**

## Further Learning
- CAPE Sandbox documentation (actively maintained Cuckoo fork) — https://capesandbox.com/
- Cuckoo Sandbox project — https://cuckoosandbox.org/
- MITRE ATT&CK, Command and Control tactic (TA0011) — https://attack.mitre.org/tactics/TA0011/ (previewed here; covered in depth in Module 6)
- `../../../LAB_SAFETY.md` §2 and §4 — re-read before Module 6's C2 content.
- *Extension:* modify `listener.py` to add a small random delay (jitter) before responding, then observe in Wireshark how much harder the resulting rhythm is to eyeball compared to the fixed 5-second interval — a preview of why real C2 jitter complicates pattern-based detection, discussed properly in Module 11.

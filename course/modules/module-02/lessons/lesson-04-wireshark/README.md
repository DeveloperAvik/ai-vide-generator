# Lesson 2.4 — Network Monitoring with Wireshark in an Isolated Lab

## Lesson Metadata
- **Module:** 2 — Lab Setup and Tools
- **Lesson:** 4 of 5
- **Difficulty:** Foundational
- **Estimated duration:** 15 minutes
- **Prerequisites:** 2.1 (Host-Only network established)

## Learning Objectives
By the end of this lesson, the learner can:
1. Install Wireshark on the Linux (or Windows) analysis VM and capture traffic on the Host-Only interface specifically.
2. Apply a basic capture/display filter to isolate traffic between the two lab VMs.
3. Explain why capturing on the Host-Only interface (not a host-wide interface) keeps the capture scoped to lab traffic only.
4. Read a simple two-host conversation (TCP handshake, HTTP request/response) in Wireshark's packet list and detail panes.

## Conceptual Explanation

**Why Wireshark, and why now.** Wireshark captures and decodes network traffic at the packet level. It reappears constantly from here on: Lesson 2.5's sandbox lab uses it to observe the simulated "C2" traffic it generates, Module 6 uses it to inspect real (lab-contained) C2 communication patterns, and Module 11 uses it for network-based threat hunting. Installing and smoke-testing it now, against completely benign traffic between your own two VMs, means the tool itself is a known quantity before it's asked to do anything more interesting.

**Capture interface selection matters for scope, not just correctness.** A host machine typically has several network interfaces: a physical Wi-Fi/Ethernet adapter (your real network), a VPN adapter if one is active, and the Host-Only virtual adapter(s) VirtualBox created in Lesson 2.1. Capturing on "all interfaces" or the wrong one will show you your host's real network traffic — noisy, and a reminder that the Host-Only boundary is a *networking* isolation, not a *packet-capture* isolation; Wireshark on the host can see real traffic if pointed at a real interface. For this course, always select the specific Host-Only (`vboxnet0`-style) interface, so the capture is scoped to lab-only traffic by construction, not by discipline alone.

**Filters: capture filters vs. display filters.** A **capture filter** (BPF syntax, e.g. `host 192.168.56.102`) is applied *while capturing*, discarding non-matching packets before they're even saved — useful on a busy interface. A **display filter** (Wireshark's own syntax, e.g. `ip.addr == 192.168.56.102 && tcp`) is applied *after* capturing, to everything already captured, and can be changed repeatedly without re-capturing. On a quiet Host-Only interface with only two VMs, a display filter is usually all you need; this lesson uses display filters so nothing is silently discarded while learning the tool.

## Instructor Script

"Quick lesson, because the concept here is simple, but it's load-bearing for several later modules, so let's get the habit right now rather than fix it under pressure in Module 6.

Wireshark captures network traffic at the packet level — literally shows you every byte that crosses an interface, decoded into something readable. Install it on the Linux VM — sudo apt install wireshark, and say yes when it asks whether non-root users should be able to capture packets, which adds your user to the wireshark group; you'll need to log out and back in for that to take effect.

Here's the one decision that matters most in this entire lesson: which interface do you capture on? Open Wireshark, and it'll show you a list of every interface available — your VM might show something like eth0 or enp0s3, which is the Host-Only adapter we set up in Lesson 2.1, and possibly a loopback interface. If you're running Wireshark on your actual host machine instead of inside a VM, you'd see your real Wi-Fi or Ethernet adapter too, and selecting that would show you your real traffic — a good reminder that Host-Only networking isolates the VMs from the internet, but it doesn't stop a capture tool from seeing whatever interface you actually point it at. For this course, always double-click the Host-Only interface specifically — the one on the 192.168.56.x range we configured.

Let's generate some traffic to look at. On the Linux VM, I'll start a capture, then from the Windows VM, I'll just open a browser and try to hit the Linux VM directly by its IP on port 80 — nothing's actually listening there yet, so let's instead start something simple: on the Linux VM, in a second terminal, python3, dash m, http-dot-server, which spins up a disposable one-line web server on port 8000. Now from the Windows VM's browser, I'll navigate to http colon slash slash, the Linux VM's Host-Only address, colon 8000.

Back in Wireshark, stop the capture and look at the packet list. You should see a burst of packets: first a TCP three-way handshake — a SYN, a SYN-ACK, an ACK — between the Windows VM's address and the Linux VM's address on port 8000, then an HTTP GET request, then the response. Click on the GET request packet, and look at the detail pane below — you can expand it down through Ethernet, IP, TCP, and finally HTTP, and see the actual request line and headers Wireshark decoded.

Now let's filter. Type into the display filter bar at the top: ip-dot-addr, double-equals, and the Linux VM's address, ampersand-ampersand, tcp. Hit enter, and the packet list narrows to just that conversation. Try http as a filter by itself, and it'll narrow further to just the HTTP-layer packets specifically — the handshake ACKs disappear from view, though they're still in the capture underneath, just not shown.

One filter worth knowing by name, even if we don't need it on this quiet interface: a capture filter, which uses different syntax — host, space, an IP address — and is applied while capturing, before packets are even saved, versus a display filter which is applied after, to a capture you already have. On a two-VM Host-Only network with basically no background noise, you'll rarely need a capture filter; we're using display filters throughout this course so you can change your view without re-capturing anything.

That's the whole lesson. No lab snapshot needed here specifically — Wireshark installed and smoke-tested is itself the deliverable, rolled into the same tools-installed snapshot from Lesson 2.3 if you're doing both VMs' tool installs together."

## Practical Demonstration

```
# Linux VM — installing Wireshark and enabling non-root capture:
$ sudo apt install -y wireshark
...
Configuring wireshark-common
  "Should non-superusers be able to capture packets?" → <Yes>
$ sudo usermod -aG wireshark $USER
# log out and back in for the group change to take effect
```

```
# Linux VM — disposable HTTP server to generate traffic to observe:
$ python3 -m http.server 8000
Serving HTTP on 0.0.0.0 port 8000 (http://0.0.0.0:8000/) ...
127.0.0.1 - - [05/Nov/2026 10:02:11] "GET / HTTP/1.1" 200 -
```

```
# Wireshark display filter, after capturing on the Host-Only interface:
ip.addr == 192.168.56.102 && tcp
```
Expected packet-list rows (summarized):
```
No.  Time    Source             Destination         Protocol  Info
1    0.000   192.168.56.101     192.168.56.102      TCP       54231 → 8000 [SYN]
2    0.001   192.168.56.102     192.168.56.101      TCP       8000 → 54231 [SYN, ACK]
3    0.001   192.168.56.101     192.168.56.102      TCP       54231 → 8000 [ACK]
4    0.002   192.168.56.101     192.168.56.102      HTTP      GET / HTTP/1.1
5    0.003   192.168.56.102     192.168.56.101      HTTP      HTTP/1.0 200 OK
```

**Common error and fix — capture list is empty / "You don't have permission to capture":**
```
$ wireshark
(Wireshark:1234): dumpcap WARNING: Couldn't run /usr/bin/dumpcap in direct child mode: ...
```
Fix: the `wireshark` group membership from the install step hasn't taken effect yet in the current shell/session. Fully log out and back in (or reboot the VM), then confirm with `groups` that `wireshark` is listed before relaunching.

**Common error and fix — no packets appear at all:**
Check that the capture is running on the Host-Only interface (e.g. `enp0s3`), not `lo` (loopback) or a disconnected interface — Wireshark's interface list shows a small live traffic sparkline next to each interface name; the Host-Only one should show activity while the HTTP requests above are in flight.

## Hands-On Lab

Folded into `labs/lab-02-03-tool-smoketest.md` as its final section (Wireshark capture-and-filter check between the two lab VMs).

## Knowledge Assessment

1. **(MC)** What is the key difference between a capture filter and a display filter in Wireshark? **A)** They use identical syntax **B)** A capture filter discards non-matching packets before saving; a display filter changes what's shown from an already-captured set **C)** A display filter can only be applied before capturing **D)** There is no functional difference
   **Answer: B.**

2. **(Technical reasoning)** Why must the learner select the Host-Only interface specifically when starting a capture, rather than "all interfaces"?
   **Answer:** Host-Only networking isolates the VMs from the internet/real LAN, but it does not restrict what a packet-capture tool can see — capturing on a real physical interface (or "all interfaces") would show the host's actual network traffic, defeating the intended scope of a lab-only capture.

3. **(MC)** In the TCP three-way handshake observed in this lesson's demo, which packet comes second? **A)** ACK **B)** SYN **C)** SYN, ACK **D)** HTTP GET
   **Answer: C.**

4. **(Scenario)** A learner starts a Wireshark capture but sees zero packets even after generating HTTP traffic between the two VMs. What are the two most likely causes to check first?
   **Answer:** (1) The wrong interface is selected (e.g., loopback instead of the Host-Only adapter), or (2) non-root capture permissions haven't taken effect yet because the user hasn't logged out/in since being added to the `wireshark` group.

## Further Learning
- Wireshark User's Guide — https://www.wireshark.org/docs/wsug_html_chunked/
- Wireshark display filter reference — https://www.wireshark.org/docs/dfref/
- `../../../LAB_SAFETY.md` §4.1 (isolation requirements this capture habit supports).
- *Extension:* capture the same HTTP exchange again, this time with the server answering on HTTPS (a self-signed cert is fine for a lab) to see how much less Wireshark can show you without a decryption key — set up for the "why HTTPS covert channels are harder to detect passively" discussion in Module 6.

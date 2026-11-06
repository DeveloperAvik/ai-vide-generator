# Lesson 2.1 — Building an Isolated VM Lab (VirtualBox, Host-Only Networking, Snapshots)

## Lesson Metadata
- **Module:** 2 — Lab Setup and Tools
- **Lesson:** 1 of 5
- **Difficulty:** Foundational
- **Estimated duration:** 25 minutes
- **Prerequisites:** Module 1 complete, including Lesson 1.5's authorization statement (`LAB_SAFETY.md` §3 model on file).

## Learning Objectives
By the end of this lesson, the learner can:
1. Explain why Host-Only/internal-only networking is mandatory for every VM used in this course, and what it actually isolates.
2. Install a type-2 hypervisor (VirtualBox) and create a Host-Only network with a known, non-routable address range.
3. Create a VM, attach it to that Host-Only network only, and verify at the OS level that it has no path to the internet.
4. Take, name, and restore a VM snapshot, and explain why labs in this course assume snapshot-revert rather than manual cleanup.

## Conceptual Explanation

**Why isolation is the first thing you build, before any tool.** Every lesson from here through Module 11 assumes two things are already true: the VM you're about to run a sample or exploit in cannot reach the real internet, and it cannot reach any other device on your home/office network. Get this wrong once — a bridged adapter left on by accident, a Wi-Fi-shared NAT network — and every subsequent safety assumption in this course (`LAB_SAFETY.md` §4) is void, regardless of how careful you are inside the VM itself.

**Host-Only networking, concretely.** A type-2 hypervisor (VirtualBox, VMware) can attach a VM's virtual network adapter to several kinds of virtual switch. The three that matter here:
- **NAT** — the VM can reach the internet through the host, but the host and other VMs generally cannot initiate connections *into* it. Convenient for patching a fresh install, but it is still an outbound path to the real internet — **never used for an active lab exercise** in this course, only for one-time OS/tool installation, then switched off.
- **Bridged** — the VM gets its own address on your *real* physical network, indistinguishable from any other device on your LAN. This is explicitly forbidden for every lab VM in this course (`LAB_SAFETY.md` §4.1): a sample or exploit running on a bridged VM is one misconfigured firewall rule away from touching a real device.
- **Host-Only (VirtualBox) / an internal-only virtual switch (VMware: "Host-only" or a custom vSwitch not bound to a physical NIC)** — creates a private virtual network that only the host and VMs explicitly attached to it can see. Nothing on it is reachable from, or can reach, the real internet or your physical LAN. This is the *only* networking mode this course's labs use once the VM is built.

**Snapshots, and why this course assumes you use them instead of "cleaning up."** A snapshot captures the VM's full disk and memory state at a point in time. Reverting to it is instantaneous and perfect — unlike manually deleting files or killing processes, which can miss a scheduled task, a registry run-key, or a background service a lab exercise created. Every lab in this course (`LAB_SAFETY.md` §4.2) assumes you snapshot the clean state *before* the exercise and revert *after*, rather than trying to manually undo what you did. This also means a mistake during a lab — a process that won't die, a VM that becomes unresponsive — costs you a revert, not a full OS reinstall.

**The "clean snapshot" as a safety control, not just a convenience.** Reverting after every lab also means a sample, a partially-built exploit, or a tool you installed for one lesson doesn't silently accumulate and interact with the next lesson's exercise in an untested way. If a later lesson's lab explicitly says to keep a VM state for the next lesson in the same module (a few will), that's the one exception — called out explicitly in that lab's instructions.

## Instructor Script

"Before we open a debugger, run a sample, or write a single line of exploit code in this course, we're going to spend this entire lesson on something that looks almost too simple to deserve 25 minutes: building a network that cannot talk to anything except itself. I want to be upfront about why this comes first — every single safety assumption for the rest of this course rests on this one lesson being done correctly. Get the networking wrong once, and nothing else we do is actually contained, no matter how careful we are once we're inside the VM.

Let's talk about the three networking modes a hypervisor gives you, because this is the part people get wrong. NAT mode lets your VM reach the real internet through your host machine — useful for one thing only: downloading and patching a fresh OS install, which we'll do once, then immediately switch off before any lab exercise. Bridged mode is the dangerous one — it puts your VM directly on your real physical network, with its own address, completely indistinguishable from your laptop, your phone, or anyone else's device on that network. We will never use bridged mode for an active exercise in this course. Full stop.

What we actually want is Host-Only networking — VMware calls the equivalent an internal-only virtual switch. This creates a private network that exists only between your host machine and whichever VMs you explicitly attach to it. Nothing on the real internet can reach it. Nothing on your physical LAN can reach it. It is, for all practical purposes, its own tiny isolated universe, and that's exactly the property we need before we ever run something that behaves like malware.

Let's build one. I'm opening VirtualBox — version 7-point-something, free download, works the same way on Mac, Windows, or Linux hosts. First, before we even create a VM: File, Tools, Network Manager. We're going to create a Host-Only network here, explicitly, rather than relying on a default. I'll click Create, and VirtualBox gives it a name like vboxnet0 and an IPv4 address range — by default something like 192.168.56.1/24. That's a private, RFC1918 address range — nothing outside this network will ever route to it. I'm leaving DHCP enabled so our VMs get addresses automatically, but you could also assign static addresses if you prefer predictable IPs for scripting later.

Now let's create the actual VM. New, give it a name — I'll use 'malware-analysis-win' for this one — select the right OS type, allocate at least 4 gigs of RAM and 2 cores if your host can spare it, and for the disk, a dynamically allocated VDI of 60 gig or more. Here's the step that matters most: before we boot this thing even once, go into Settings, Network, Adapter 1, and set Attached to: Host-only Adapter, and pick the vboxnet0 network we just created. Not NAT. Not Bridged. Host-only. I'm going to say that one more time on screen because it's the single most important click in this entire lesson.

Let's boot it, install the OS — I'm using a time-limited Windows evaluation ISO here, which Microsoft provides specifically for exactly this kind of testing and training use — and once it's up, let's verify the isolation actually worked, because 'I selected Host-only' and 'it's actually isolated' are two different claims until you check. Inside the VM, open a command prompt and run ipconfig. You should see an address in the 192.168.56.x range we configured — that confirms it's on our private network. Now the real test: open a browser or just ping a known internet host. Ping, space, eight-eight-eight-eight — that's Google's public DNS. You should see... nothing. Request timed out, or 'could not find host.' That failure is the success condition. If that ping actually succeeds, stop — go back and check your adapter setting, because something is misconfigured, and you do not proceed to any lab exercise until this comes back negative.

Last piece: snapshots. With the VM freshly installed, patched if you want — though actually, for malware-analysis VMs we often deliberately under-patch, which Module 3 will explain — shut it down cleanly, right-click it in the VirtualBox manager, and choose Snapshot, Take. Name it something explicit, like 'clean-base-install', not 'snapshot 1', because in six months you want to know exactly what state that snapshot represents. From this point forward, every single lab in this course starts with 'revert to a known clean snapshot' and ends with 'revert again,' not 'manually undo what you did.' That's not a suggestion, it's how every lab in this course is actually written, so get comfortable doing it now."

## Practical Demonstration

Live build, narrated step by step, with the command/output pairs a learner should see on screen:

```
# Inside the hypervisor host, before creating any VM:
VirtualBox → File → Tools → Network Manager → Host-only Networks → Create
  Name: vboxnet0
  IPv4 Address: 192.168.56.1   Mask: 255.255.255.0
  DHCP Server: Enabled, range 192.168.56.100–192.168.56.199
```

```
# VM settings (shown on screen, not typed):
Settings → Network → Adapter 1
  Attached to: Host-only Adapter
  Name: vboxnet0
```

Isolation verification, run inside the guest VM once it's booted:

```
C:\> ipconfig
Ethernet adapter Ethernet:
   IPv4 Address. . . . . . . . . . . : 192.168.56.101
   Subnet Mask . . . . . . . . . . . : 255.255.255.0
   Default Gateway . . . . . . . . . :
```
*(No default gateway and an address inside the Host-Only range — expected.)*

```
C:\> ping 8.8.8.8

Pinging 8.8.8.8 with 32 bytes of data:
Request timed out.
Request timed out.
Request timed out.
Request timed out.

Ping statistics for 8.8.8.8:
    Packets: Sent = 4, Received = 0, Lost = 4 (100% loss)
```
*(This timeout is the correct, expected result — it confirms no internet path exists.)*

Snapshot creation and restore:

```
VirtualBox Manager → right-click VM → Snapshot → Take Snapshot
  Name: clean-base-install
  Description: Fresh Win10 eval install, patched, no analysis tools yet

# Later, to restore:
VirtualBox Manager → right-click VM → Snapshot → clean-base-install → Restore
```

## Hands-On Lab

See `labs/lab-02-01-vm-build.md` for the full step-by-step lab (build, isolation-verify, and snapshot both the Windows and Linux analysis VMs — the Linux build is completed in Lesson 2.2, but the Host-Only network and snapshot discipline are established here).

## Knowledge Assessment

1. **(MC)** Which VirtualBox networking mode is forbidden for an active lab exercise in this course? **A)** Host-only **B)** Internal network **C)** Bridged **D)** None of the above are forbidden
   **Answer: C.** Bridged puts the VM directly on the real physical LAN.

2. **(MC)** What does a successful isolation check for a Host-Only VM look like when pinging 8.8.8.8? **A)** Replies with low latency **B)** Replies with high latency **C)** Request timed out / 100% loss **D)** DNS resolution failure only, but ping succeeds
   **Answer: C.**

3. **(Technical reasoning)** Why does this course require you to revert a lab VM from a snapshot rather than manually deleting files/processes created during the exercise?
   **Answer:** Manual cleanup can miss persistence artifacts (scheduled tasks, registry run keys, background services) a lab exercise created, leaving residual state that could interact unpredictably with a later lesson; a snapshot revert restores the exact prior disk/memory state with no guesswork.

4. **(MC)** NAT networking mode is acceptable in this course for which purpose only? **A)** Running an active exploit lab **B)** One-time OS/tool installation and patching, then switched off **C)** Permanent internet access for the analysis VM **D)** Simulating C2 traffic
   **Answer: B.**

5. **(Scenario)** A learner's Windows analysis VM, set to Host-Only, successfully pings 8.8.8.8 after being rebuilt. What is the correct next action?
   **Answer:** Stop immediately — do not proceed to any lab exercise. Re-check the network adapter setting (it may have reverted to NAT/Bridged, or a second adapter was added), fix it, and re-verify the ping fails before continuing.

## Further Learning
- VirtualBox manual, "Virtual Networking" — https://www.virtualbox.org/manual/ch06.html
- VMware, "Choosing a Network Adapter for Your Virtual Machine" — https://docs.vmware.com/
- `../../../LAB_SAFETY.md` §4 (Lab environment requirements) — re-read before Lesson 2.2.
- *Extension:* repeat the isolation check from the host machine itself (can the host reach the VM's Host-Only address, and can the VM reach the host) to build a full mental model of what Host-Only actually permits.

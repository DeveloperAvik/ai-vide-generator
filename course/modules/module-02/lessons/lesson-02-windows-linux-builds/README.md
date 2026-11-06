# Lesson 2.2 — Windows and Linux Malware-Analysis VM Builds

## Lesson Metadata
- **Module:** 2 — Lab Setup and Tools
- **Lesson:** 2 of 5
- **Difficulty:** Foundational
- **Estimated duration:** 20 minutes
- **Prerequisites:** 2.1 (Host-Only network and VirtualBox installed)

## Learning Objectives
By the end of this lesson, the learner can:
1. Build a Windows analysis VM from a legitimate evaluation ISO and a Linux analysis VM from a current LTS image, both attached only to the Host-Only network from Lesson 2.1.
2. Explain why malware-analysis VMs are deliberately kept at a known, often older patch level rather than fully up to date.
3. Disable the specific Windows defenses (Defender real-time protection, SmartScreen, automatic updates) that would otherwise interfere with controlled analysis, and explain why this is safe *only* inside an isolated VM.
4. Install guest additions/tools and confirm shared-clipboard/drag-and-drop are disabled between host and guest where the lab calls for stricter isolation.

## Conceptual Explanation

**Two VMs, two roles.** This course's labs generally use a Windows VM (most consumer/enterprise malware still targets Windows, and most of the course's PE-analysis and exploit-development content is Windows-focused in Modules 3, 5, 7, 8) and a Linux VM (used as the attacker/tooling box — Ghidra, GDB, Python tooling, and later the sandbox in Lesson 2.5 — and for Linux-specific persistence/exploitation content in Modules 7–9). Both sit on the same Host-Only network from Lesson 2.1 so they can talk to *each other* but to nothing else.

**Why a malware-analysis VM is deliberately not "fully patched and secure."** A production machine wants every mitigation on: Defender real-time scanning, automatic updates, SmartScreen, firewall blocking. An analysis VM wants the *opposite* in specific, narrow ways: Defender's real-time protection will quarantine or delete the very sample you're trying to analyze the moment it touches disk, before you ever get to look at it in Ghidra or a debugger. This isn't "turning off security" in a dangerous way — it's safe precisely *because* the VM is Host-Only isolated (Lesson 2.1) and disposable (Lesson 2.1's snapshot discipline): the sample has nowhere to go and the whole VM gets reverted when you're done. The same configuration on an internet-connected production machine would be a real security hazard — the isolation is what makes it acceptable here, not a lower standard of care.

**Known-good patch baseline, not "intentionally vulnerable."** This course does not ask you to run an unpatched OS to make *OS-level* exploits easier — vulnerable *practice targets* (named, public, purpose-built binaries) are what Modules 7 and 8 use for that, not the OS itself. The point here is narrower: Defender off, automatic updates off (so a reboot mid-lesson doesn't silently patch something or reboot the VM), SmartScreen off (so it doesn't block running your own test tooling), so the VM behaves predictably across every lesson that reuses it.

**Guest additions and clipboard isolation.** VirtualBox Guest Additions (or VMware Tools) improve display resolution and performance and are genuinely useful for recording clean screen captures. They also, by default, often enable shared clipboard and drag-and-drop between host and guest — convenient, but it's a data path between your isolated VM and your real host. Several labs later in this course (notably sandbox and C2-simulation work in Lesson 2.5 and payload work in Module 6) explicitly disable shared clipboard/drag-and-drop for the duration of the exercise, to keep the isolation boundary meaningful rather than theoretical.

## Instructor Script

"Now that we have a Host-Only network that genuinely can't reach the internet, let's build the two VMs we'll actually use for the rest of this course: a Windows analysis box and a Linux box.

Starting with Windows. I'm downloading a Windows 10 or 11 evaluation ISO directly from Microsoft — they publish these specifically for testing and evaluation scenarios like this one, time-limited but fully functional, no product key needed up front. New VM in VirtualBox, same as last lesson — name it clearly, 'malware-analysis-win', 4 gig RAM minimum, I'd go higher if your host allows it since Ghidra and a debugger both want memory, 60-plus gig disk, and — this is the step we drilled into the ground last lesson — network adapter attached to Host-only, our vboxnet0 network, not NAT, not Bridged.

Boot from the ISO, install Windows normally. When it asks you to sign in with a Microsoft account, choose the offline/local account option instead — we don't want this VM tied to a real account, and we genuinely don't need internet access for it to be useful.

Once it's installed, here's where this VM starts to look different from your everyday laptop. Open Windows Security, go to Virus & threat protection settings, and turn off Real-time protection. I want to be very precise about why: the moment you drop an actual sample on this VM in Module 5, Defender's real-time engine will see it, flag it, and quarantine or delete it before you ever get to open it in a debugger. That's Defender doing exactly its job — but its job, on this one disposable, network-isolated VM, is actively in the way of the job we're here to do. This is safe only because of two things we already set up: this VM cannot reach the internet, so nothing here can call home, and it's disposable — we snapshot it clean and revert when we're done. Turn this off on your real laptop and you've created a real security hole. Turn it off on this VM and you've created a controlled analysis environment. Same setting, completely different risk, because of the isolation around it.

While we're in there, disable SmartScreen as well — it'll otherwise block us from running our own unsigned test tools — and turn off Windows Update, or at minimum set it to Pause, so an unexpected reboot doesn't interrupt a lab exercise. Install VirtualBox Guest Additions next for better display resolution and smoother screen capture — Devices menu, Insert Guest Additions CD image, run the installer inside the guest.

Now shut this VM down cleanly and take the snapshot — 'clean-base-install', exactly like last lesson — before you install a single analysis tool. That snapshot is your anchor; Lesson 2.3 installs Ghidra, x64dbg, and PEStudio on top of it, and we'll take a second snapshot after that, 'tools-installed', so you always have two clean restore points to fall back to.

Now Linux, which is faster. Download a current Ubuntu LTS or Kali image — Kali comes with a lot of the tooling we need pre-installed, which can save time, though we'll still walk through installing things explicitly so you understand what's actually there. Same VM creation flow, same Host-only network attachment, 4 gig RAM, 40 gig disk is plenty for this one. Install normally, run guest additions here too — on Linux that's typically apt install for the open-vm-tools or virtualbox-guest-utils package rather than a GUI installer.

One more thing before we snapshot both of these: shared clipboard and drag-and-drop. By default, Guest Additions often enable both between host and guest, which is convenient for day-to-day use but is a real data path crossing our isolation boundary. For this course, in Devices, Shared Clipboard and Drag and Drop, set both to Disabled as your default, and only re-enable one direction temporarily — host-to-guest only, to bring in a lab file — when a specific lab instruction tells you to. We'll call this out explicitly whenever it matters, like the sandbox lab in Lesson 2.5.

Snapshot both VMs now — 'clean-base-install' for each — and we're ready for Lesson 2.3, where we actually install the tools you'll use for the rest of this course."

## Practical Demonstration

```
# Windows guest — disabling Defender real-time protection (Settings UI, shown on screen):
Windows Security → Virus & threat protection → Manage settings → Real-time protection: Off

# Equivalent via PowerShell (run as Administrator), shown as an alternative for scripted rebuilds:
PS C:\> Set-MpPreference -DisableRealtimeMonitoring $true
PS C:\> Get-MpPreference | Select-Object DisableRealtimeMonitoring

DisableRealtimeMonitoring
--------------------------
                      True
```

```
# Windows guest — pausing updates and disabling SmartScreen (Settings UI):
Settings → Windows Update → Pause updates
Settings → Apps → Advanced app settings → Check apps and files: Off (SmartScreen for apps/files)
```

```
# Linux guest (Ubuntu) — installing guest utilities:
$ sudo apt update && sudo apt install -y open-vm-tools open-vm-tools-desktop
...
$ sudo reboot
```

```
# Verifying the Linux guest's network is still Host-Only only, after install:
$ ip addr show
2: enp0s3: <BROADCAST,MULTICAST,UP,LOWER_UP> ...
    inet 192.168.56.102/24 ...

$ ping -c 4 8.8.8.8
PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
--- 8.8.8.8 ping statistics ---
4 packets transmitted, 0 received, 100% packet loss, time 3062ms
```
*(100% packet loss confirms isolation held after installing packages — re-verify after every guest-side change that could touch networking.)*

```
# Disabling shared clipboard/drag-and-drop (VM Settings UI, VM powered off):
Settings → General → Advanced → Shared Clipboard: Disabled
Settings → General → Advanced → Drag'n'Drop: Disabled
```

**Common error and fix:** if `apt update` on the Linux guest appears to hang or times out, that is *expected* on a correctly Host-Only-only VM with no package mirror reachable — it is not a bug to "fix" by bridging the network. For any package installation step, temporarily switch the adapter to NAT, run the install, then switch back to Host-only and re-run the `ping 8.8.8.8` isolation check before any lab exercise. Never leave a lab VM on NAT.

## Hands-On Lab

See `labs/lab-02-01-vm-build.md` (shared lab covering both 2.1 and 2.2 — build, harden, and snapshot the Windows and Linux analysis VMs).

## Knowledge Assessment

1. **(MC)** Why is Windows Defender's real-time protection disabled on the malware-analysis VM? **A)** To make the VM faster for gaming **B)** Because it would quarantine/delete analysis samples before they can be examined **C)** Because Defender doesn't work in VirtualBox **D)** It isn't disabled; this is a trick question
   **Answer: B.**

2. **(Technical reasoning)** Why is disabling Defender's real-time protection safe on this VM but not on a learner's everyday laptop?
   **Answer:** The analysis VM is Host-Only isolated (no internet path) and disposable (snapshot-revert discipline), so a sample has nowhere to call home and any damage is undone by a revert; a production machine lacks both protections, so the same setting there creates genuine exposure.

3. **(MC)** What is the correct response if `apt update` hangs on a Linux guest that is correctly attached to the Host-Only network only? **A)** Switch the adapter to Bridged to get internet access **B)** This is expected; temporarily use NAT for the install only, then switch back to Host-only and re-verify isolation **C)** Leave it on NAT permanently for convenience **D)** Reinstall the OS
   **Answer: B.**

4. **(MC)** What does this course explicitly NOT ask you to do to the Windows analysis VM's OS to make exploitation easier? **A)** Disable Defender real-time protection **B)** Pause Windows Update **C)** Downgrade or leave unpatched the OS kernel itself to create exploitable OS vulnerabilities **D)** Disable SmartScreen
   **Answer: C.** OS-level vulnerability practice uses named, purpose-built practice targets (Modules 7–8), not an intentionally-unpatched OS kernel.

5. **(Scenario)** A learner wants to copy a lab file from their host machine into the isolated Windows guest. What is the correct, course-compliant way to do this given shared clipboard/drag-and-drop are disabled by default?
   **Answer:** Temporarily enable drag-and-drop or shared clipboard in the host-to-guest direction only, for that specific transfer, per the lab's explicit instruction, then disable it again — not leave it permanently bidirectional.

## Further Learning
- Microsoft, Windows evaluation ISOs — https://www.microsoft.com/evalcenter/
- Microsoft, `Set-MpPreference` documentation — https://learn.microsoft.com/powershell/module/defender/set-mppreference
- Kali Linux downloads — https://www.kali.org/get-kali/
- `../../../LAB_SAFETY.md` §4.1–§4.4.
- *Extension:* script the Windows hardening steps (Defender off, SmartScreen off, updates paused) as a single PowerShell script, run once per fresh install, and keep it alongside your lab notes for faster VM rebuilds later in the course.

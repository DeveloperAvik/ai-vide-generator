# Module 2 Assessment — Lab Setup and Tools

Cumulative, 12 questions spanning Lessons 2.1–2.5, plus a required practical component (screenshot evidence).

1. **(MC)** Which VirtualBox networking mode must every lab VM use for an active exercise in this course? **A)** NAT **B)** Bridged **C)** Host-only **D)** Any mode with internet access
   **Answer: C.**

2. **(MC)** What is the correct result of pinging `8.8.8.8` from a correctly isolated lab VM? **A)** Fast reply **B)** Slow reply **C)** Request timed out / 100% packet loss **D)** DNS error only
   **Answer: C.**

3. **(Technical reasoning)** Why does this course assume snapshot-revert rather than manual cleanup after every lab?
   **Answer:** Manual cleanup can miss persistence artifacts (scheduled tasks, services, registry keys) a lab exercise created; a snapshot revert restores the exact prior state with no guesswork, and makes "I didn't fully clean up" impossible as a failure mode.

4. **(MC)** Why is Windows Defender's real-time protection disabled on the Windows analysis VM specifically? **A)** To improve VM performance generally **B)** Because it would quarantine/delete analysis samples before they can be examined **C)** It has no effect inside a VM **D)** Defender cannot be disabled
   **Answer: B.**

5. **(Technical reasoning)** Explain why disabling Defender on the analysis VM is acceptable per this course's safety model, but would not be acceptable on an internet-connected production machine.
   **Answer:** The analysis VM has no path to the internet (Host-Only) and is disposable (snapshot-revert), so a sample has nowhere to communicate and any damage is undone by reverting; a production machine lacks both protections, so removing the same control there creates genuine, uncontained exposure.

6. **(MC)** What does PEStudio do? **A)** Executes a binary in a sandbox **B)** Performs static triage of a PE file without running it **C)** Captures network packets **D)** Decompiles ELF binaries only
   **Answer: B.**

7. **(MC)** Which tool pairing is correct for Linux exploit-development work in this course? **A)** x64dbg **B)** Ghidra alone **C)** GDB with GEF or pwndbg **D)** PEStudio
   **Answer: C.**

8. **(Scenario)** `apt update` hangs on the Linux analysis VM, which is correctly set to Host-only networking. What is the correct action? **A)** Switch permanently to Bridged **B)** This is expected; temporarily use NAT for the install only, then switch back and re-verify isolation **C)** Reinstall the OS **D)** Ignore it; packages aren't needed
   **Answer: B.**

9. **(MC)** Why must a Wireshark capture in this course be taken on the Host-Only interface specifically, not "all interfaces"? **A)** It's faster **B)** Capturing on a real physical interface would show the host's actual network traffic, defeating the lab-only scope **C)** Wireshark cannot capture on virtual interfaces **D)** There is no difference
   **Answer: B.**

10. **(Technical reasoning)** Describe the network pattern this module's beacon-simulation lab demonstrates, and name one way real-world C2 (previewed here, covered in Module 6) complicates detecting that pattern.
    **Answer:** A periodic outbound connection carrying a small request and a variable-size response (beaconing) — the connection/silence/connection rhythm stands out against normal, bursty human-driven traffic. Real C2 complicates this with jitter (randomized timing), blending into normal-looking protocols (DNS, HTTPS), and varying request/response sizes to avoid a fixed, obviously periodic signature.

11. **(Scenario)** A learner wants to modify the Lesson 2.5 beacon script to execute arbitrary commands it receives, to make the exercise "more realistic." Is this acceptable, and why/why not?
    **Answer:** Not acceptable. This crosses `LAB_SAFETY.md` §2 (no production-grade/weaponized tooling) and defeats the exercise's purpose, which is observing the benign network *pattern*, not building a functioning implant.

12. **(Submission requirement)** Attach: (a) the Host-Only isolation check output (`ping 8.8.8.8` failing) from both analysis VMs, (b) the Ghidra decompiler and x64dbg breakpoint screenshots from the tool smoke-test, and (c) the beacon-console and filtered-Wireshark screenshots from Lab 2.5. **Required to mark Module 2 complete.**

## Scoring
11 scored knowledge items (1 point each) + item 12 (pass/fail gate, not point-scored). Passing threshold: 9/11 on scored items **and** all three evidence screenshots present and consistent with a correctly isolated Host-Only lab.

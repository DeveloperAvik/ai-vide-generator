# Lab 2.3/2.4 — Tool Smoke-Test (Ghidra, x64dbg, GDB, PEStudio, Wireshark)

**Safety acknowledgment (restate before starting):** *"I will only perform these exercises in an isolated lab I own or am explicitly authorized to use, and I will not take any technique taught here outside that lab without separate written authorization."*

**Covers:** Lessons 2.3 (Core Static/Debug Tooling) and 2.4 (Wireshark).

## Objective
Verify Ghidra, x64dbg, PEStudio (Windows VM), GDB+GEF (Linux VM), and Wireshark (either/both VMs) are correctly installed and functioning, using only a trivial, learner-compiled binary and benign HTTP traffic — no real samples.

## Required tools
Tools installed per Lesson 2.3 (Ghidra, x64dbg, PEStudio, GDB, GEF or pwndbg) and Lesson 2.4 (Wireshark). A C compiler on each VM (Visual Studio Build Tools or MinGW on Windows; `gcc` on Linux).

## Environment setup
Revert both VMs to `clean-base-install` from `lab-02-01-vm-build.md` before installing tools, so the resulting `tools-installed` snapshot is built on a known-clean base.

## Exercise instructions

1. On both VMs, write a trivial C program (`smoketest.c`):
   ```c
   #include <stdio.h>
   int main(void) { printf("hello from the lab\n"); return 0; }
   ```
2. **Windows:** Compile with `cl smoketest.c` (or `gcc`), run it, confirm the printed output.
3. **PEStudio:** Drag `smoketest.exe` onto PEStudio. Confirm: valid PE header parsed, standard imports only (e.g. `KERNEL32.dll`), 0 indicators flagged.
4. **Ghidra:** Create a project, File → Import File → `smoketest.exe`, let auto-analysis finish, open `main` in the decompiler pane. Confirm the pseudocode shows a `printf`-equivalent call with the literal string and a `return 0`.
5. **x64dbg:** File → Open → `smoketest.exe`. Set a breakpoint at the entry point, run (F9), confirm it breaks and populates the disassembly/registers/stack panes. Step (F8) a few times and confirm the instruction pointer and registers change sensibly.
6. **Linux:** Compile with `gcc -g smoketest.c -o smoketest`. Run `gdb ./smoketest`, confirm GEF/pwndbg's colorized context view appears. `break main`, `run`, confirm it breaks at `main` with registers/stack/disassembly all visible.
7. **Wireshark (either VM with it installed):** Start a capture on the Host-Only interface only (confirm by name, e.g. `enp0s3`/Host-only adapter — never "all interfaces" or a real physical adapter). On the Linux VM run `python3 -m http.server 8000`; from the Windows VM's browser, request `http://<linux-vm-ip>:8000/`. Stop the capture. Apply display filter `ip.addr == <linux-vm-ip> && tcp`, then `http`. Confirm the TCP handshake and HTTP GET/response are visible.
8. Shut both VMs down cleanly. Take a snapshot on each named `tools-installed`.

## Expected observations
- All four static/debug tools open, load, and run against the smoke-test binary without error.
- PEStudio shows 0 flagged indicators on the trivial binary (expected — it's not malicious).
- Wireshark shows a clean 3-packet TCP handshake followed by an HTTP GET and 200 OK response, scoped only to the two lab VMs' Host-Only addresses.

## Validation steps
Instructor/peer review of: a screenshot of Ghidra's decompiler pane showing `main`, a screenshot of x64dbg stopped at a breakpoint with populated panes, a terminal capture of the GDB/GEF session, and a screenshot of the filtered Wireshark capture.

## Troubleshooting
- **Ghidra `UnsupportedClassVersionError`:** wrong JDK version — install the exact major version Ghidra's install guide specifies, set `JAVA_HOME`, retry.
- **GEF fails to load / Python import error in GDB:** re-run GEF's own installer rather than hand-editing `.gdbinit`; confirm GDB's embedded Python version matches GEF's requirement.
- **Wireshark shows "permission denied" or no capture devices:** the `wireshark` group membership added during install hasn't taken effect — log out/in (or reboot), confirm with `groups`.
- **Wireshark shows zero packets during the HTTP test:** wrong interface selected (check for a live traffic sparkline next to the Host-Only interface specifically), or the HTTP server isn't actually running — check its terminal for request log lines.

## Cleanup/reset
None — the `tools-installed` snapshot is this lab's deliverable. Use it as the starting point for Lesson 2.5's lab and for every Module 3+ lab that doesn't say otherwise.

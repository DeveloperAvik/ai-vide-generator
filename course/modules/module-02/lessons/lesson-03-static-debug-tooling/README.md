# Lesson 2.3 — Core Static/Debug Tooling: Ghidra, x64dbg, GDB, PEStudio

## Lesson Metadata
- **Module:** 2 — Lab Setup and Tools
- **Lesson:** 3 of 5
- **Difficulty:** Foundational
- **Estimated duration:** 25 minutes
- **Prerequisites:** 2.2 (both analysis VMs built, hardened, and snapshotted)

## Learning Objectives
By the end of this lesson, the learner can:
1. Install Ghidra, x64dbg, PEStudio on the Windows analysis VM and GDB (with GEF or pwndbg) on the Linux analysis VM.
2. Verify each tool is functional by opening/running a trivial, known-good binary — not a live sample.
3. Explain, at a high level, what each tool is for and which later module relies on it, so the toolchain's purpose is clear before it's used in anger.
4. Take a second, tools-installed snapshot distinct from the clean-base-install snapshot from Lesson 2.2.

## Conceptual Explanation

**Why install tools before you need them, and smoke-test with a trivial binary.** Installing Ghidra for the first time in the middle of a Module 5 analysis lesson means debugging two problems at once: the tool's own setup quirks (Java version mismatches, first-run project configuration) and the actual analysis task. This lesson isolates tool setup from tool use — every tool gets installed and verified against a trivial, known-good binary (a "hello world" compiled by the learner, not a real sample) so that by Module 5 the only new thing is the analysis technique, not the tool itself.

**What each tool is for, and where it reappears:**
- **Ghidra** (NSA, open-source, free) — a disassembler and decompiler: turns compiled machine code back into assembly and an approximate C-like pseudocode. Used heavily in Module 5 (static analysis/reverse engineering) and Module 8 (vulnerability research in binaries).
- **x64dbg** (free, open-source) — a Windows user-mode debugger with a GUI: lets you run a binary step by step, set breakpoints, inspect registers/memory/stack. Used in Modules 5, 7, and 8 for dynamic analysis and exploit development on Windows targets.
- **GDB**, usually paired with **GEF** or **pwndbg** (free extensions that add exploit-development-friendly views: colorized registers, stack/heap visualization, pointer-chasing) — the standard Linux debugger. Used in Modules 7 and 8 for Linux exploit development (stack overflows, ROP).
- **PEStudio** (free tier) — static triage of Windows PE (executable) files without running them: imports/exports, suspicious API usage, embedded strings, entropy, without ever executing the file. Used in Module 5 as the *first* step of analysis, before anything is run even in an isolated VM.

**Smoke-test discipline, not analysis.** This lesson's lab explicitly uses a trivial compiled binary (a basic "hello world" program the learner compiles themselves) for every tool — the goal is confirming the tool *runs and produces expected output*, not practicing analysis technique. Module 5 is where real (still de-fanged/illustrative) analysis targets appear.

## Instructor Script

"We've got two isolated, hardened VMs. Now let's put the actual toolkit on them — and I want to be clear about the goal of this lesson specifically: we are not analyzing anything interesting yet. We're installing four tools and confirming each one works, using the most boring possible test file, so that when Module 5 asks you to actually analyze something, the tool itself is already a known quantity.

Starting on the Windows VM. First, Ghidra — it's a Java application, so first, verify a JDK is installed; Ghidra's release notes specify the exact supported version, currently a recent OpenJDK LTS release. Download Ghidra as a zip, extract it anywhere, and run ghidraRun-dot-bat. First launch, it'll ask you to agree to its license and set up a project directory — call it something like 'module05-analysis'. We're not opening anything yet; we just want to confirm it launches without a Java version error.

Next, x64dbg — download the release zip, extract it, and run x32dbg or x64dbg depending on whether you're debugging 32- or 64-bit binaries; we'll mostly use the 64-bit one. Again, just confirm it launches to its main window.

PEStudio — single executable, no installer, just run it. It'll show you a clean interface with panes for indicators, imports, strings, and so on, all currently empty because we haven't loaded a file.

Now the smoke test, same on all three: I'm going to open a Visual Studio Build Tools command prompt — or if you don't have Visual Studio, MinGW's gcc works too — and compile the simplest possible C program.

I'll write a file, smoketest-dot-c, containing just a printf of 'hello from the lab' and a return zero. Compile it: cl smoketest-dot-c, or gcc smoketest-dot-c, dash o, smoketest-dot-exe. That gives us smoketest-dot-exe — a completely trivial, source-known binary. First, drag it into PEStudio. You should see a valid PE header, a handful of standard imports like kernel32-dot-dll and msvcrt-dot-dll, no suspicious indicators flagged — because there's nothing suspicious in a hello-world program. That's the expected, boring result, and that's exactly what confirms PEStudio itself is working correctly.

Now open the same file in Ghidra — File, Import File, point at smoketest-dot-exe, let it auto-analyze. Once that finishes, find the main function in the symbol tree and look at the decompiler pane — you should see Ghidra's reconstructed pseudocode roughly resembling our actual source: a printf call with our string, a return. If Ghidra's decompiler pane shows readable pseudocode that maps back to code we just wrote, Ghidra's working.

Now x64dbg — File, Open, same executable. Set a breakpoint on the entry point, hit F9 to run, and it should break right at the start, showing you the disassembly, registers, and stack panes all populated. Step through with F8 a few times; you should see the instruction pointer advancing and register values changing in a way that makes sense for a simple program's startup code.

Switching to the Linux VM for GDB. Install it straight from the package manager — sudo apt install gdb — then add GEF, which is a single Python script you source from your gdbinit file; the project's install page gives you a one-line curl-and-bash installer, which I'd actually encourage you to read before running, since 'pipe curl to bash' is worth being suspicious of as a general habit, even from a reputable project. Compile the same trivial hello-world program with gcc, this time with dash capital-G for debug symbols — gcc dash g smoketest-dot-c dash o smoketest — and run gdb smoketest. With GEF installed you should see its distinctive colorized context view — registers, stack, and disassembly all in one screen — the moment you break at main with 'break main' then 'run'. That colorized, multi-pane layout is GEF's signature and confirms it loaded correctly; stock GDB without GEF gives you a much plainer prompt.

Last step, and don't skip it: shut both VMs down cleanly and take a second snapshot on each, named 'tools-installed' — distinct from the 'clean-base-install' snapshot from Lesson 2.2. You now have two restore points: all the way back to a bare OS, or back to a fully tooled analysis box. Every lab from Module 5 onward assumes you're starting from 'tools-installed,' not rebuilding from scratch."

## Practical Demonstration

```
# Compiling the trivial smoke-test binary (Windows, Developer Command Prompt):
C:\lab> cl smoketest.c
Microsoft (R) C/C++ Optimizing Compiler ...
smoketest.c
Generating Code...
C:\lab> smoketest.exe
hello from the lab
```

```
# PEStudio: drag smoketest.exe onto the PEStudio window. Expected panes (summarized):
indicators: 0 flagged
imports:    KERNEL32.dll, MSVCRT.dll (or VCRUNTIME140.dll)
exports:    (none — not a DLL)
entropy:    ~5.8 (unpacked, plain binary — low/unremarkable)
```

```
# GDB + GEF smoke test (Linux):
$ gcc -g smoketest.c -o smoketest
$ gdb ./smoketest
GEF for linux ready, type `gef' to start, `gef config' to configure
gef>  break main
Breakpoint 1 at 0x1149: file smoketest.c, line 4.
gef>  run
Starting program: /home/lab/smoketest
─────────────────────────────── registers ────
$rax   : 0x0
$rbx   : 0x7fffffffe3b8
...
──────────────────────────────── stack ────────
0x7fffffffe280│+0x0000: 0x0000000000000000   ← $rsp
...
───────────────────────────── code:x86:64 ─────
 →  0x55555555514 <main+8>  mov edi, 0x...
Breakpoint 1, main () at smoketest.c:4
```

**Common error and fix — Ghidra won't launch, Java version error:**
```
$ ./ghidraRun
Exception in thread "main" java.lang.UnsupportedClassVersionError: ...
has been compiled by a more recent version of the Java Runtime ...
```
Fix: install the exact JDK major version Ghidra's release notes specify (check `docs/InstallationGuide.html` in the Ghidra distribution for the supported range), set `JAVA_HOME` to that JDK, and re-run — do not just install the newest JDK available, since Ghidra pins to a tested range.

**Common error and fix — GEF script fails to source:**
```
gdb ./smoketest
Traceback (most recent call last):
  File "/home/lab/.gdbinit-gef.py", line 1, in <module>
    ...
ModuleNotFoundError: No module named 'something'
```
Fix: GEF requires a specific Python 3 version bound to the system GDB build; re-run GEF's own installer script rather than hand-editing `.gdbinit`, and confirm with `gdb -q -ex 'pi import sys; print(sys.version)' -ex quit` that GDB's embedded Python matches what GEF expects.

## Hands-On Lab

See `labs/lab-02-03-tool-smoketest.md` for the full step-by-step smoke-test lab across all four tools, with expected-output checkpoints for each.

## Knowledge Assessment

1. **(MC)** What is PEStudio used for? **A)** Running and debugging a binary step by step **B)** Static triage of a Windows PE file without executing it **C)** Decompiling machine code to pseudocode **D)** Linux exploit development
   **Answer: B.**

2. **(MC)** Which tool pairing is correct? **A)** Ghidra = Windows-only debugger **B)** x64dbg = Linux disassembler **C)** GDB + GEF/pwndbg = Linux debugger with exploit-dev-friendly views **D)** PEStudio = dynamic sandbox execution
   **Answer: C.**

3. **(Technical reasoning)** Why does this lesson's smoke test use a hello-world binary the learner compiled themselves, rather than a downloaded sample?
   **Answer:** It isolates tool-setup verification from analysis technique and from any sample-handling risk — the binary's exact behavior is already known, so any unexpected tool output (crash, missing pane, wrong disassembly) is immediately attributable to a tool-configuration problem, not to the target.

4. **(Scenario)** Ghidra fails to launch with `UnsupportedClassVersionError`. What is the correct fix?
   **Answer:** Install the specific JDK major version Ghidra's own installation guide specifies (not simply the newest available), point `JAVA_HOME` at it, and relaunch — Ghidra pins to a tested JDK range rather than "any recent Java."

5. **(MC)** What confirms GEF (vs. stock GDB) loaded correctly when debugging the smoke-test binary? **A)** The program's own printed output **B)** A distinctive colorized, multi-pane context view (registers/stack/disassembly) appearing automatically at a breakpoint **C)** GDB exits with code 0 **D)** The binary runs faster
   **Answer: B.**

## Further Learning
- Ghidra official docs/installation guide — https://ghidra-sre.org/
- x64dbg — https://x64dbg.com/
- GEF — https://gef.readthedocs.io/ · pwndbg — https://github.com/pwndbg/pwndbg
- PEStudio — https://www.winitor.com/
- `requirements/ENVIRONMENT.md` (full tool/version list for the course).
- *Extension:* repeat the Ghidra and x64dbg smoke test against a slightly larger known-source program (e.g., a small multi-function C program) to see the symbol tree and call graph populate with more than one function before Module 5 introduces a real analysis target.

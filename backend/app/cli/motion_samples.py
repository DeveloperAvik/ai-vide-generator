"""Render the motion-graphics sample videos: python -m app.cli.motion_samples [--only NAME] [--stills F,F,...]
Real voice synthesis + the real Remotion adapter (same path as a lesson render), written to storage/motion_samples/.
Each sample is a tiny storyboard so it renders in about a minute; with --stills also dumps PNG frames for visual inspection."""
import argparse
import subprocess

from app.core.config import ROOT
from app.providers.voice import get_voice
from app.schemas.content import Scene, StoryboardData
from app.services import narration
from app.workers import remotion_adapter

OUT = ROOT / "storage" / "motion_samples"


def sc(i, type_, narr, text, **kw):
    return {"scene_id": f"scene_{i:03d}", "type": type_, "duration_seconds": 6, "narration": narr, "visual_description": text, "on_screen_text": text, **kw}


SAMPLES: dict[str, list[dict]] = {
    "technical_slide": [
        sc(1, "instructor", "Today we look at how input validation protects a web application.", "Input Validation"),
        sc(2, "slide", "There are three ideas to remember. First, never trust data that comes from the client. Second, validate on the server, because browser checks are easy to bypass. Third, encode output for the place where it is used.",
           "Three Rules of Input Handling", bullets=["Never trust client data", "Validate on the server", "Encode output for its context"],
           animation={"animation_profile": "standard", "camera_movement": "push_in", "narration_sync": {"mode": "anchored"},
                      "animation_sequence": [{"target": "bullet.0", "at_phrase": "never trust data"}, {"target": "bullet.1", "at_phrase": "Second"}, {"target": "bullet.2", "at_phrase": "Third"}]}),
        sc(3, "quiz", "Quick check. Which control stops injection at the source? Pause and think. The answer is parameterized queries, because the database never treats input as code.",
           "Which control stops injection?", bullets=["Hiding error messages", "Parameterized queries", "Longer passwords", "Client-side checks"], quiz_answer=1),
        sc(4, "summary", "To summarize. Treat all input as untrusted, validate on the server, and encode on output.", "Key Takeaways", bullets=["Untrusted by default", "Server-side validation", "Context-aware encoding"]),
    ],
    "architecture_diagram": [
        sc(1, "diagram", "A request starts at the browser. It passes through the load balancer, which forwards it to the web application. The application queries the database, and the result travels back the same way.",
           "Request Flow", mermaid="flowchart LR\nB[Browser] --> L[Load Balancer]\nL --> A[Web App]\nA --> D[Database]\nA --> C[Cache]"),
        sc(2, "diagram", "Authentication is a decision. If the credentials are valid, the user receives a session token. Otherwise the request is rejected and logged.",
           "Login Decision", mermaid="flowchart TD\nR[Login Request] --> V{Valid Credentials}\nV -- yes --> T[Issue Session Token]\nV -- no --> X[Reject and Log]"),
    ],
    "terminal_demo": [
        sc(1, "terminal", "First we check which services are running. Then we request the page and inspect the headers. Finally the server crashes with a segmentation fault, which tells us the input was not validated.",
           "Lab Demonstration", terminal_lines=["$ nmap -sV 10.0.0.5", "PORT   STATE SERVICE VERSION", "80/tcp open  http    Apache 2.4.49", "$ curl -I http://10.0.0.5/", "HTTP/1.1 200 OK", "Server: Apache/2.4.49", "$ ./vuln_server $(python3 -c 'print(\"A\"*300)')", "Segmentation fault (core dumped)"]),
    ],
    "browser_demo": [
        sc(1, "browser", "First the browser loads the login page. Then the form fields appear. Finally we click the submit button to send the credentials.",
           "Login Form", terminal_lines=["http://lab.local/login", "Username field", "Password field", "[Submit] button"]),
    ],
    "code_walkthrough": [
        sc(1, "code", "This function copies user input into a fixed size buffer. The buffer holds sixty four bytes. Then strcpy copies the input without checking its length. That missing check is the vulnerability.",
           "Unsafe Copy", language="c", code="void greet(char *name) {\n    char buf[64];\n    strcpy(buf, name);   // VULNERABLE: no length check\n    printf(\"Hello %s\\n\", buf);\n}"),
    ],
}

FB = "flowchart LR\nA[Input] --> B[Process]\nB --> C[Result]"  # flat fallback for the ffmpeg engine


def viz(i, narr, title, v):
    return sc(i, "diagram", narr, title, mermaid=FB, visualization=v)


SAMPLES.update({
    "buffer_overflow": [
        viz(1, "First, the function reserves a stack frame with a return address and a saved base pointer. Second, it declares a buffer of sixty four bytes. Third, the program copies eighty bytes of input into that buffer. "
               "Fourth, the copy does not stop at the end of the buffer, so the saved base pointer is overwritten. Fifth, the return address is overwritten too, which means the function returns to an address the attacker chose.",
            "Stack Buffer Overflow", {"kind": "buffer_overflow", "buffer_size": 64, "input_length": 80, "buffer_name": "buf", "original_return": "0x401176"}),
    ],
    "assembly_execution": [
        viz(1, "The first instruction loads forty two into rax. Next, rbx receives eight. Then add combines them, so rax becomes fifty. After that, sub removes two from rax. Finally, the value is copied into rdi, ready to be passed to a function.",
            "Instruction Execution", {"kind": "assembly", "registers": ["rax", "rbx", "rdi", "rsp", "rip"],
             "instructions": [{"addr": "0x401000", "text": "mov rax, 0x2a", "comment": "rax = 42"}, {"addr": "0x401007", "text": "mov rbx, 0x8"}, {"addr": "0x40100e", "text": "add rax, rbx", "comment": "rax += rbx"},
                              {"addr": "0x401011", "text": "sub rax, 0x2"}, {"addr": "0x401015", "text": "mov rdi, rax", "comment": "first argument"}],
             "steps": [{"line": 0, "set": [{"reg": "rax", "value": "0x2a"}]}, {"line": 1, "set": [{"reg": "rbx", "value": "0x8"}]}, {"line": 2, "set": [{"reg": "rax", "value": "0x32"}], "note": "add: 0x2a + 0x8 = 0x32"},
                       {"line": 3, "set": [{"reg": "rax", "value": "0x30"}]}, {"line": 4, "set": [{"reg": "rdi", "value": "0x30"}]}]}),
    ],
    "stack_and_heap": [
        viz(1, "The program starts in main. Then main calls parse, which adds a frame below it with its own return address and a local buffer. Finally parse calls copy, which adds one more frame with a small counter.",
            "Call Stack", {"kind": "stack_frames", "frames": [{"function": "main", "locals": [{"name": "argc", "size": 4}], "return_address": "0x7f12a0021d90"},
                                                              {"function": "parse", "args": ["char *input"], "locals": [{"name": "buf", "size": 64}], "return_address": "0x401176"},
                                                              {"function": "copy", "locals": [{"name": "i", "size": 4}], "return_address": "0x4011c4"}]}),
        viz(2, "First we allocate chunk A of seventy two bytes. Second, chunk B of seventy two bytes. Third, we free A, and it goes on the tcache list. Fourth, we free B, which is pushed in front of A. Fifth, the next allocation of that size returns B, the most recently freed chunk.",
            "Heap Allocation", {"kind": "heap", "ops": [{"op": "malloc", "chunk": "A", "size": 72}, {"op": "malloc", "chunk": "B", "size": 72}, {"op": "free", "chunk": "A"}, {"op": "free", "chunk": "B"}, {"op": "malloc", "chunk": "C", "size": 72, "note": "C reuses the chunk that B occupied: LIFO"}]}),
    ],
    "flow_and_network": [
        viz(1, "The program checks its input length first. If the input is too long, it jumps to the error handler. Otherwise it copies the data and then returns normally.",
            "Control Flow Graph", {"kind": "control_flow", "blocks": [{"id": "entry", "lines": ["cmp rdi, 0x40", "ja error"]}, {"id": "copy", "lines": ["mov rsi, rdi", "call memcpy"]}, {"id": "error", "lines": ["lea rdi, [msg]", "call puts"]}, {"id": "exit", "lines": ["xor eax, eax", "ret"]}],
             "edges": [{"a": "entry", "b": "copy", "label": "no"}, {"a": "entry", "b": "error", "label": "yes"}, {"a": "copy", "b": "exit"}, {"a": "error", "b": "exit"}], "path": ["entry", "error", "exit"]}),
        viz(2, "The client opens a connection with a SYN. The server answers with SYN ACK. The client confirms with ACK. Then the client sends an HTTP request, and the server replies with the page.",
            "TCP Handshake and Request", {"kind": "packet_flow", "nodes": [{"id": "c", "label": "Client"}, {"id": "s", "label": "Server"}],
             "packets": [{"src": "c", "dst": "s", "label": "SYN", "detail": "seq=100"}, {"src": "s", "dst": "c", "label": "SYN, ACK", "detail": "seq=300 ack=101"}, {"src": "c", "dst": "s", "label": "ACK", "detail": "ack=301"},
                         {"src": "c", "dst": "s", "label": "GET /index.html", "detail": "HTTP/1.1"}, {"src": "s", "dst": "c", "label": "200 OK", "detail": "text/html"}]}),
    ],
    "malware_and_binary": [
        viz(1, "A typical malware sample first arrives through a phishing attachment. Then it executes and decrypts its payload. Next it persists, so it survives a reboot. After that it contacts its command server. Finally it carries out its objective.",
            "Malware Execution Lifecycle", {"kind": "lifecycle", "stages": [{"label": "Delivery", "detail": "A phishing attachment or a drive-by download places the sample on the host."}, {"label": "Execution", "detail": "The user or an exploit runs it; a loader unpacks and decrypts the real payload in memory."},
                                                                          {"label": "Persistence", "detail": "A run key, scheduled task or service entry makes it start again after a reboot."}, {"label": "Command & Control", "detail": "It beacons to a remote server over HTTP or DNS and waits for tasks."}, {"label": "Actions", "detail": "Data theft, lateral movement or encryption: the actual objective."}]}),
        viz(2, "An ELF file begins with its header. Then the program headers describe how to map segments. Next comes the text section with code. After it, the data section holds initialized globals. Finally the section headers describe everything for tools.",
            "ELF File Structure", {"kind": "layout", "format": "elf", "regions": [{"name": "ELF header", "range": "0x0000", "note": "Magic 0x7f 'ELF', class, endianness, entry point and the offsets of both header tables."}, {"name": "Program headers", "range": "e_phoff", "note": "Tell the loader which segments to map into memory and with which permissions."},
                                                                                 {"name": ".text", "range": "0x1040", "flags": "R-X", "note": "Executable machine code, including the entry point _start."}, {"name": ".data", "range": "0x4000", "flags": "RW-", "note": "Initialized global and static variables."}, {"name": "Section headers", "range": "e_shoff", "note": "Used by linkers and debuggers; the loader does not need them at run time."}]}),
    ],
})


def build(name: str, stills: list[float]):
    out = OUT / name
    out.mkdir(parents=True, exist_ok=True)
    voice = get_voice()
    sb = StoryboardData.model_validate({"lesson_title": name.replace("_", " ").title(), "scenes": SAMPLES[name] if len(SAMPLES[name]) >= 2 else SAMPLES[name] + [sc(99, "summary", "That is the whole idea.", "Recap", bullets=["Done"])]})
    audio = {}
    for scn in sb.scenes:
        wav = out / f"{scn.scene_id}.wav"
        narration.synth_with_timing(voice, scn.narration, wav)
        audio[scn.scene_id] = wav
    res = remotion_adapter.render_long(storyboard=sb, assets_dir=out, scene_audio=audio, scene_video={}, out_dir=out / "render", portrait=ROOT / "avatar" / "assets" / "instructor.png", music=None, brand="CipherCast")
    print(name, "->", res["video"], f"{res['duration']:.1f}s", "voice:", voice.name)
    for t in stills:  # frames of the FINISHED mp4 (what a viewer sees), for visual inspection
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", str(res["video"]), "-frames:v", "1", str(out / f"frame_{t:05.1f}.png")], check=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=list(SAMPLES))
    ap.add_argument("--stills", default="", help="comma-separated seconds; dumps PNG frames of the finished video")
    a = ap.parse_args()
    for n in [a.only] if a.only else list(SAMPLES):
        build(n, [float(x) for x in a.stills.split(",") if x])


if __name__ == "__main__":
    main()

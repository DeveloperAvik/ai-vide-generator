"""Typed data for the technical visualizations (stack frames, buffer overflow, heap, registers, assembly, CFG, packets, process
lifecycle, binary/process layout). Pure data: bounded numbers, hex strings, short labels. The Remotion components own all
drawing and simulate the mechanics (e.g. heap chunk sizes, which bytes of a buffer overflow land on saved RBP / RET), so the
model supplies WHAT to teach, never how to draw it and never executable code.
Each visualization exposes `step_count`; the narration sync layer addresses its steps as targets `step.0 .. step.n-1`."""
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

HEX = re.compile(r"^0x[0-9a-fA-F]{1,16}$")
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,31}$")
Label = Annotated[str, Field(min_length=1, max_length=60)]
Note = Annotated[str, Field(max_length=140)]


class _S(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _hex(v: str, what: str) -> str:
    if not HEX.match(v):
        raise ValueError(f"{what} must be a hex value like 0x401136")
    return v


# ---- stack ----
class Local(_S):
    name: str = Field(pattern=IDENT.pattern)
    size: int = Field(ge=1, le=256)
    note: Note = ""


class Frame(_S):
    function: str = Field(pattern=IDENT.pattern)
    args: list[Label] = Field(default_factory=list, max_length=6)
    locals: list[Local] = Field(default_factory=list, max_length=8)
    return_address: str = "0x401136"
    note: Note = ""

    @model_validator(mode="after")
    def ok(self):
        _hex(self.return_address, "return_address")
        return self


class StackFrames(_S):
    kind: Literal["stack_frames"]
    arch: Literal["x86_64", "x86"] = "x86_64"
    frames: list[Frame] = Field(min_length=1, max_length=5)

    @property
    def step_count(self) -> int:
        return len(self.frames)


class BufferOverflow(_S):
    kind: Literal["buffer_overflow"]
    arch: Literal["x86_64", "x86"] = "x86_64"
    buffer_name: str = Field("buf", pattern=IDENT.pattern)
    buffer_size: int = Field(ge=8, le=256)
    input_length: int = Field(ge=0, le=512)
    fill_byte: str = Field("A", min_length=1, max_length=1)
    original_return: str = "0x401176"
    stack_canary: bool = False  # shows the canary slot between the buffer and saved RBP (and the check that catches the overwrite)

    @model_validator(mode="after")
    def ok(self):
        _hex(self.original_return, "original_return")
        if not self.fill_byte.isprintable():
            raise ValueError("fill_byte must be printable")
        return self

    @property
    def step_count(self) -> int:
        return 5


# ---- heap ----
class HeapOp(_S):
    op: Literal["malloc", "free"]
    chunk: str = Field(pattern=IDENT.pattern)
    size: int | None = Field(None, ge=1, le=4096)
    note: Note = ""

    @model_validator(mode="after")
    def ok(self):
        if self.op == "malloc" and self.size is None:
            raise ValueError("malloc needs size")
        return self


class Heap(_S):
    kind: Literal["heap"]
    ops: list[HeapOp] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def consistent(self):
        live: set[str] = set()
        for o in self.ops:
            if o.op == "malloc":
                if o.chunk in live:
                    raise ValueError(f"chunk {o.chunk} allocated twice")
                live.add(o.chunk)
            elif o.chunk not in live:
                raise ValueError(f"free of unallocated chunk {o.chunk}")
            else:
                live.discard(o.chunk)
        return self

    @property
    def step_count(self) -> int:
        return len(self.ops)


# ---- registers / assembly ----
class RegSet(_S):
    reg: str = Field(pattern=r"^[a-z][a-z0-9]{1,5}$")
    value: str

    @model_validator(mode="after")
    def ok(self):
        _hex(self.value, "register value")
        return self


class AsmInstr(_S):
    addr: str
    text: str = Field(min_length=1, max_length=60)
    comment: str = Field("", max_length=80)

    @model_validator(mode="after")
    def ok(self):
        _hex(self.addr, "addr")
        return self


class AsmStep(_S):
    line: int = Field(ge=0)
    set: list[RegSet] = Field(default_factory=list, max_length=6)
    note: Note = ""


class Assembly(_S):
    kind: Literal["assembly"]
    registers: list[str] = Field(default_factory=lambda: ["rax", "rbx", "rcx", "rdi", "rsp", "rip"], min_length=1, max_length=8)
    instructions: list[AsmInstr] = Field(min_length=1, max_length=14)
    steps: list[AsmStep] = Field(min_length=1, max_length=14)

    @model_validator(mode="after")
    def ok(self):
        for s in self.steps:
            if s.line >= len(self.instructions):
                raise ValueError("assembly step line out of range")
            for r in s.set:
                if r.reg not in self.registers:
                    raise ValueError(f"register {r.reg} is not in `registers`")
        return self

    @property
    def step_count(self) -> int:
        return len(self.steps)


# ---- control flow ----
class Block(_S):
    id: str = Field(pattern=IDENT.pattern)
    lines: list[Annotated[str, Field(max_length=48)]] = Field(min_length=1, max_length=5)


class CfgEdge(_S):
    a: str
    b: str
    label: str = Field("", max_length=12)


class ControlFlow(_S):
    kind: Literal["control_flow"]
    blocks: list[Block] = Field(min_length=2, max_length=9)
    edges: list[CfgEdge] = Field(min_length=1, max_length=14)
    path: list[str] = Field(min_length=1, max_length=12, description="block ids in the order execution visits them")

    @model_validator(mode="after")
    def ok(self):
        ids = {b.id for b in self.blocks}
        if len(ids) != len(self.blocks):
            raise ValueError("duplicate block id")
        if any(e.a not in ids or e.b not in ids for e in self.edges) or any(p not in ids for p in self.path):
            raise ValueError("edge/path references an unknown block")
        return self

    @property
    def step_count(self) -> int:
        return len(self.path)


# ---- packets ----
class PNode(_S):
    id: str = Field(pattern=IDENT.pattern)
    label: Label


class Packet(_S):
    src: str
    dst: str
    label: str = Field(min_length=1, max_length=40)
    detail: str = Field("", max_length=60)


class PacketFlow(_S):
    kind: Literal["packet_flow"]
    nodes: list[PNode] = Field(min_length=2, max_length=5)
    packets: list[Packet] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def ok(self):
        ids = {n.id for n in self.nodes}
        if any(p.src not in ids or p.dst not in ids or p.src == p.dst for p in self.packets):
            raise ValueError("packet endpoints must be two different known nodes")
        return self

    @property
    def step_count(self) -> int:
        return len(self.packets)


# ---- lifecycle / layout ----
class Stage(_S):
    label: str = Field(min_length=1, max_length=24)
    detail: str = Field("", max_length=160)


class Lifecycle(_S):
    kind: Literal["lifecycle"]
    stages: list[Stage] = Field(min_length=2, max_length=7)

    @property
    def step_count(self) -> int:
        return len(self.stages)


class Region(_S):
    name: str = Field(min_length=1, max_length=28)
    range: str = Field("", max_length=40)
    flags: str = Field("", max_length=12)
    note: Note = ""


class Layout(_S):
    kind: Literal["layout"]
    format: Literal["elf", "pe", "process"]
    regions: list[Region] = Field(min_length=2, max_length=9)

    @property
    def step_count(self) -> int:
        return len(self.regions)


Visualization = Annotated[StackFrames | BufferOverflow | Heap | Assembly | ControlFlow | PacketFlow | Lifecycle | Layout, Field(discriminator="kind")]


def clean_visualization(v):
    """LLM output: an invalid visualization is dropped (the scene falls back to its mermaid diagram) instead of failing the section."""
    from pydantic import TypeAdapter
    if v is None:
        return None
    try:
        return TypeAdapter(Visualization).validate_python(v).model_dump()
    except Exception:  # noqa: BLE001
        return None

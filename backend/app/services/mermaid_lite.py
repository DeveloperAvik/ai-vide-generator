"""Tiny offline Mermaid flowchart subset -> layout -> SVG. Handles `A[label] --> B{label}`, `-- text -->`, `-->|text|`.
Full Mermaid (sequence/class diagrams etc.) needs `mmdc`; if present visuals.py prefers it."""
import re
from dataclasses import dataclass, field
from html import escape

NODE = r"([A-Za-z_][\w]*)(?:(\[\[|\[|\{|\(\()([^\]\}\)]*)(?:\]\]|\]|\}|\)\)))?"
EDGE = re.compile(rf"^\s*{NODE}\s*(?:--\s*([^>-][^>]*?)\s*-->|-->\s*(?:\|([^|]*)\|)?|---)\s*{NODE}\s*$")


@dataclass
class Graph:
    direction: str = "LR"
    nodes: dict = field(default_factory=dict)   # id -> (label, shape)
    edges: list = field(default_factory=list)   # (a, b, label)


ARROW = re.compile(r"(\s*(?:--\s*[^>\-][^>]*?-->|-->(?:\s*\|[^|]*\|)?|---)\s*)")
HEADER = re.compile(r"^(?:flowchart|graph)\s+(LR|RL|TD|TB|BT)\b\s*(.*)$")


def _statements(src: str):
    """Valid Mermaid allows `;` between statements, a header followed by a statement, and chains `A --> B --> C`."""
    for raw in re.split(r"[\n]|;(?![^\[\]]*\])", src):
        line = raw.strip()
        if not line or line.startswith("%%"):
            continue
        m = HEADER.match(line)
        if m:
            yield ("header", m.group(1))
            line = m.group(2).strip()
            if not line:
                continue
        parts = ARROW.split(line)
        segs, ops = [x.strip() for x in parts[0::2]], parts[1::2]
        pieces = [_split_nodes(x) for x in segs]
        if len(parts) == 1 or any(p is None for p in pieces):
            yield ("edge", line)
            continue
        # a statement per arrow; `B --> C B --> D` on one line (models drop the newlines) puts two nodes between arrows
        left = pieces[0][-1]
        for op, nxt in zip(ops, pieces[1:]):
            yield ("edge", left + op + nxt[0])
            left = nxt[-1]


def _split_nodes(seg: str):
    """The 1-2 node tokens in a segment between arrows, or None if it is not just nodes."""
    toks = [m.group(0) for m in re.finditer(NODE, seg)]
    if not toks or len(toks) > 2 or re.sub(r"\s+", "", "".join(toks)) != re.sub(r"\s+", "", seg):
        return None
    return toks


def parse(src: str) -> Graph:
    g = Graph()
    for kind, line in _statements(src):
        if kind == "header":
            g.direction = "LR" if line in ("LR", "RL") else "TD"
            continue
        m = EDGE.match(line)
        if not m:
            raise ValueError(f"unsupported mermaid line: {line!r}")
        a, ab, al, lab1, lab2, b, bb, bl = m.groups()[0], m.group(2), m.group(3), m.group(4), m.group(5), m.group(6), m.group(7), m.group(8)
        for nid, br, lbl in ((a, ab, al), (b, bb, bl)):
            lbl = lbl.strip().strip('"') if lbl else lbl  # `A["Label"]` is valid Mermaid; the quotes are not part of the text
            shape = {"{": "diamond", "((": "circle"}.get(br or "", "box")
            if nid not in g.nodes or lbl:
                g.nodes[nid] = (lbl or g.nodes.get(nid, (nid, 0))[0], shape if br else g.nodes.get(nid, (0, "box"))[1])
        g.edges.append((a, b, (lab1 or lab2 or "").strip()))
    if not g.nodes:
        raise ValueError("empty diagram")
    return g


def layout(g: Graph, w=1500, h=700):
    layer = {n: 0 for n in g.nodes}
    for _ in range(len(g.nodes)):
        for a, b, _l in g.edges:
            if layer[b] < layer[a] + 1 and layer[a] + 1 < len(g.nodes):
                layer[b] = layer[a] + 1
    by = {}
    for n, l in layer.items():
        by.setdefault(l, []).append(n)
    nl = max(by) + 1
    bw, bh = 260, 90
    pos = {}
    for l, ids in by.items():
        for i, n in enumerate(ids):
            if g.direction == "LR":
                x = (l + 0.5) * w / nl
                y = (i + 0.5) * h / len(ids)
            else:
                x = (i + 0.5) * w / len(ids)
                y = (l + 0.5) * h / nl
            pos[n] = (x, y)
    return pos, (min(bw, w / nl - 40), bh)


def wrap(text: str, width=18) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for wd in words:
        if len(cur) + len(wd) + 1 > width and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = (cur + " " + wd).strip()
    return lines + [cur] if cur else lines


def to_svg(src: str, w=1500, h=700) -> str:
    g = parse(src)
    pos, (bw, bh) = layout(g, w, h)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" font-family="Helvetica, Arial, sans-serif">',
           '<defs><marker id="ar" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto"><path d="M0,0 L12,6 L0,12 z" fill="#7dd3fc"/></marker></defs>']
    for a, b, lab in g.edges:
        (x1, y1), (x2, y2) = pos[a], pos[b]
        if g.direction == "LR":
            x1, x2 = x1 + bw / 2, x2 - bw / 2
        else:
            y1, y2 = y1 + bh / 2, y2 - bh / 2
        out.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="#7dd3fc" stroke-width="4" marker-end="url(#ar)"/>')
        if lab:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            out.append(f'<rect x="{mx - len(lab) * 7.5 - 8:.0f}" y="{my - 18:.0f}" width="{len(lab) * 15 + 16:.0f}" height="36" rx="8" fill="#0b1220"/>')
            out.append(f'<text x="{mx:.0f}" y="{my + 9:.0f}" fill="#fbbf24" font-size="26" text-anchor="middle">{escape(lab)}</text>')
    for n, (lbl, shape) in g.nodes.items():
        x, y = pos[n]
        if shape == "diamond":
            pts = f"{x},{y - bh / 2 - 15} {x + bw / 2},{y} {x},{y + bh / 2 + 15} {x - bw / 2},{y}"
            out.append(f'<polygon points="{pts}" fill="#1e293b" stroke="#fbbf24" stroke-width="4"/>')
        else:
            rx = 45 if shape == "circle" else 14
            out.append(f'<rect x="{x - bw / 2:.0f}" y="{y - bh / 2:.0f}" width="{bw:.0f}" height="{bh}" rx="{rx}" fill="#1e293b" stroke="#38bdf8" stroke-width="4"/>')
        lines = wrap(lbl)
        for i, ln in enumerate(lines):
            dy = (i - (len(lines) - 1) / 2) * 30 + 9
            out.append(f'<text x="{x:.0f}" y="{y + dy:.0f}" fill="#f1f5f9" font-size="26" text-anchor="middle">{escape(ln)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def layout_payload(src: str, w=1500, h=700) -> dict:
    """Laid-out graph for the animated Remotion flowchart: node centres, edges (node-id pairs) and box size, in `w` x `h` units."""
    g = parse(src)
    pos, (bw, bh) = layout(g, w, h)
    return {"direction": g.direction, "w": w, "h": h, "bw": bw, "bh": bh,
            "nodes": [{"id": n, "label": lbl, "shape": shape, "x": round(pos[n][0], 1), "y": round(pos[n][1], 1)} for n, (lbl, shape) in g.nodes.items()],
            "edges": [{"a": a, "b": b, "label": lab} for a, b, lab in g.edges]}


def graph_3d(src: str) -> dict:
    """Nodes with 3D coordinates (x by layer, y by index within layer, z staggered for depth) for the Remotion 3D scene."""
    g = parse(src)
    layer = {n: 0 for n in g.nodes}
    for _ in range(len(g.nodes)):
        for a, b, _l in g.edges:
            if layer[b] < layer[a] + 1 and layer[a] + 1 < len(g.nodes):
                layer[b] = layer[a] + 1
    by = {}
    for n, l in layer.items():
        by.setdefault(l, []).append(n)
    nl = max(by) + 1
    nodes = []
    for l, ids in by.items():
        for i, n in enumerate(ids):
            x = (l - (nl - 1) / 2) * (12.4 / max(nl - 1, 1))
            y = ((len(ids) - 1) / 2 - i) * 2.4
            z = ((l % 2) - 0.5) * 0.8
            if g.direction == "TD":
                x, y = (i - (len(ids) - 1) / 2) * 3.4, ((nl - 1) / 2 - l) * 2.2
            nodes.append({"id": n, "label": g.nodes[n][0], "shape": g.nodes[n][1], "x": round(x, 2), "y": round(y, 2), "z": round(z, 2), "layer": l})
    return {"nodes": nodes, "edges": [{"a": a, "b": b, "label": lab} for a, b, lab in g.edges]}

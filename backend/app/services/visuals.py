"""Educational visual generator. Pillow renders slides/diagrams/code/terminal/quiz as 1920x1080 PNG (also used
as the fallback video engine's frames); diagrams additionally export SVG for reuse in Remotion/HTML."""
import platform
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from app.schemas.content import Scene
from app.services import mermaid_lite

W, H = 1920, 1080
BG, PANEL, FG, MUTED, ACCENT, WARN = "#0b1220", "#111c33", "#f1f5f9", "#94a3b8", "#38bdf8", "#fbbf24"

_SANS = ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"]
_SANS_B = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
_MONO = ["/System/Library/Fonts/Menlo.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "/System/Library/Fonts/Courier.ttc"]


def font(size: int, mono=False, bold=False) -> ImageFont.FreeTypeFont:
    for p in (_MONO if mono else (_SANS_B + _SANS if bold else _SANS)):
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default(size)


def wrap(draw, text, fnt, max_w):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for w in para.split(" "):
            t = (cur + " " + w).strip()
            if draw.textlength(t, font=fnt) <= max_w:
                cur = t
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def _base(title: str, footer: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 16, H], fill=ACCENT)
    d.text((90, 60), title, font=font(64, bold=True), fill=FG)
    d.rectangle([90, 145, 330, 151], fill=WARN)
    d.text((90, H - 50), footer, font=font(24), fill=MUTED)
    return img, d


_KW = re.compile(r"\b(def|return|import|from|if|else|for|while|class|SELECT|FROM|WHERE|const|let|var|function)\b")


def _code_block(d, code, x, y, w, h, size=30):
    d.rounded_rectangle([x, y, x + w, y + h], 18, fill=PANEL)
    f = font(size, mono=True)
    yy = y + 30
    for ln in code.split("\n"):
        color = "#64748b" if ln.strip().startswith(("#", "//", "--")) else ("#fca5a5" if "VULNERABLE" in ln else FG)
        d.text((x + 30, yy), ln[:80], font=f, fill=color)
        yy += size + 12


def render_scene_png(scene: Scene, lesson_title: str, out: Path, idx: int, total: int, portrait: Path | None = None, brand: str = "Teaching Studio", draft: bool = False) -> Path:
    footer = f"{lesson_title}  ·  {idx}/{total}  ·  Educational content - authorized labs only"
    title = scene.on_screen_text or lesson_title
    img, d = _base(title if scene.type != "instructor" else lesson_title, footer)
    t = scene.type
    if t == "instructor":
        if portrait and portrait.exists():
            p = Image.open(portrait).convert("RGB")
            p.thumbnail((700, 800))
            img.paste(p, (W - 800, 140))
        tf = font(76, bold=True)
        lines = wrap(d, scene.on_screen_text or lesson_title, tf, W - 900 - 120)
        for i, ln in enumerate(lines):
            d.text((90, 330 + i * 92), ln, font=tf, fill=FG)
        d.text((90, 350 + len(lines) * 92), brand, font=font(40), fill=ACCENT)
    elif t in ("slide", "summary", "quiz"):
        f = font(46)
        y = 230
        for b in (scene.bullets or []):
            if t != "quiz":  # draw the marker (font-independent; some system fonts lack the glyph)
                d.polygon([(120, y + 12), (120, y + 40), (142, y + 26)], fill=ACCENT)
            d.text((165 if t != "quiz" else 120, y), b, font=f, fill=WARN if t == "quiz" else FG)
            y += 100
        if t == "quiz":
            d.text((120, 760), "Pause the video and choose your answer", font=font(34), fill=MUTED)
    elif t == "diagram" and scene.mode3d == "stack":  # 2D fallback of the 3D layer stack (ffmpeg engine)
        layers = scene.bullets or []
        for i, b in enumerate(layers):
            y = 220 + i * 130
            hot = i == scene.highlight_layer
            d.rounded_rectangle([420, y, 1500, y + 100], 14, fill="#3b2a12" if hot else "#16233f", outline=WARN if hot else ACCENT, width=4)
            d.text((960, y + 50), b, font=font(38, bold=hot), fill=WARN if hot else FG, anchor="mm")
    elif t == "diagram":
        svg_png = _diagram_png(scene.mermaid or "")
        img.paste(svg_png.resize((1350, 630)), (285, 190))
    elif t == "code":
        _code_block(d, scene.code or "", 90, 190, W - 180, 630)
    elif t in ("terminal", "browser"):
        d.rounded_rectangle([90, 190, W - 90, 820], 18, fill="#000000", outline="#334155", width=3)
        for i, c in enumerate(("#ef4444", "#f59e0b", "#22c55e")):
            d.ellipse([120 + i * 40, 225, 144 + i * 40, 249], fill=c)
        f = font(32, mono=True)
        y = 290
        for ln in (scene.terminal_lines or [scene.visual_description]):
            d.text((130, y), ln[:95], font=f, fill="#4ade80" if ln.startswith("$") else "#e2e8f0")
            y += 52
        d.text((130, 775), "Illustrative / lab demonstration - not evidence of real-world results", font=font(24), fill=MUTED)
    if draft:
        _draft_banner(d, W)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


DRAFT_TEXT = "UNREVIEWED DRAFT - NOT FACT-CHECKED - DO NOT PUBLISH"


def _draft_banner(d, width: int, y: int = 0, h: int = 54) -> None:
    """Red strip across the top: a quick draft is visibly not a finished lesson on every frame."""
    d.rectangle([0, y, width, y + h], fill="#b91c1c")
    d.text((width // 2, y + h // 2), DRAFT_TEXT, font=font(30, bold=True), fill="#ffffff", anchor="mm")


def _diagram_png(src: str) -> Image.Image:
    g = mermaid_lite.parse(src)
    w, h = 1500, 700
    pos, (bw, bh) = mermaid_lite.layout(g, w, h)
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    f = font(26)
    for a, b, lab in g.edges:
        (x1, y1), (x2, y2) = pos[a], pos[b]
        if g.direction == "LR":
            x1, x2 = x1 + bw / 2, x2 - bw / 2
        else:
            y1, y2 = y1 + bh / 2, y2 - bh / 2
        d.line([x1, y1, x2, y2], fill="#7dd3fc", width=4)
        d.polygon([(x2, y2), (x2 - 18, y2 - 9), (x2 - 18, y2 + 9)] if g.direction == "LR" else [(x2, y2), (x2 - 9, y2 - 18), (x2 + 9, y2 - 18)], fill="#7dd3fc")
        if lab:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            tw = d.textlength(lab, font=f)
            d.rounded_rectangle([mx - tw / 2 - 8, my - 18, mx + tw / 2 + 8, my + 18], 8, fill=BG)  # opaque label plate over the line
            d.text((mx, my), lab, font=f, fill=WARN, anchor="mm")
    for n, (lbl, shape) in g.nodes.items():
        x, y = pos[n]
        if shape == "diamond":
            d.polygon([(x, y - bh / 2 - 15), (x + bw / 2, y), (x, y + bh / 2 + 15), (x - bw / 2, y)], fill="#1e293b", outline=WARN, width=4)
        else:
            d.rounded_rectangle([x - bw / 2, y - bh / 2, x + bw / 2, y + bh / 2], 14, fill="#1e293b", outline=ACCENT, width=4)
        lines = mermaid_lite.wrap(lbl)
        for i, ln in enumerate(lines):
            d.text((x, y + (i - (len(lines) - 1) / 2) * 30), ln, font=f, fill=FG, anchor="mm")
    return img


def default_portrait(out: Path) -> Path:
    """Neutral placeholder instructor portrait. Replace avatar/assets/instructor.png with your own image."""
    img = Image.new("RGB", (800, 900), "#13213f")
    d = ImageDraw.Draw(img)
    d.ellipse([260, 150, 540, 430], fill="#cbd5e1")
    d.rounded_rectangle([140, 470, 660, 900], 120, fill="#334155")
    d.text((400, 860), "Instructor (placeholder)", font=font(30), fill="#e2e8f0", anchor="mm")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


TW, TH, SS = 1280, 720, 2  # thumbnail size (YouTube standard) and supersampling factor for smooth edges
_ACCENT_RGB, _WARN_RGB = (56, 189, 248), (251, 191, 36)


def _thumb_background(w: int, h: int) -> Image.Image:
    """Diagonal navy->indigo gradient, a soft accent glow on the right (behind the portrait) and a faint dot grid."""
    big = max(w, h) * 2  # rotate an oversized gradient and crop the centre so no corner seams show
    base = Image.linear_gradient("L").resize((big, big)).rotate(35, resample=Image.BICUBIC).crop(((big - w) // 2, (big - h) // 2, (big + w) // 2, (big + h) // 2))
    img = Image.composite(Image.new("RGB", (w, h), (30, 41, 90)), Image.new("RGB", (w, h), (6, 10, 24)), base)
    glow = Image.new("RGB", (w, h), (0, 0, 0))
    ImageDraw.Draw(glow).ellipse([w * 0.58, h * 0.02, w * 1.12, h * 1.0], fill=(18, 92, 140))
    img = Image.blend(img, Image.composite(glow, img, glow.convert("L").point(lambda v: 255 if v else 0)).filter(ImageFilter.GaussianBlur(w * 0.09)), 0.75)
    d = ImageDraw.Draw(img)
    step = h // 18
    for x in range(step, w, step):
        for y in range(step, h, step):
            d.ellipse([x - 1.5, y - 1.5, x + 1.5, y + 1.5], fill=(38, 52, 96))
    return img


def _circle_portrait(portrait: Path, diameter: int) -> Image.Image:
    """Square head-and-shoulders crop (biased to the top of the image) masked to a circle."""
    p = ImageOps.fit(Image.open(portrait).convert("RGB"), (diameter, diameter), Image.LANCZOS, centering=(0.5, 0.2))
    mask = Image.new("L", (diameter * 2, diameter * 2), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, diameter * 2 - 1, diameter * 2 - 1], fill=255)
    out = p.convert("RGBA")
    out.putalpha(mask.resize((diameter, diameter), Image.LANCZOS))
    return out


def _fit_title(d, text: str, max_w: int, max_h: int, s: int):
    """Largest bold size (<=120px) where the wrapped uppercase title fits the box with every word whole, max 4 lines."""
    text = text.upper().strip()
    for size in range(120, 43, -4):
        f = font(size * s, bold=True)
        if max(d.textlength(w, font=f) for w in text.split()) > max_w * s:
            continue
        lines = wrap(d, text, f, max_w * s)
        if len(lines) <= 4 and len(lines) * size * 1.12 <= max_h:
            return f, size, lines
    f = font(44 * s, bold=True)
    return f, 44, wrap(d, text, f, max_w * s)[:4]


def render_thumbnail(text: str, subtitle: str, out: Path, portrait: Path | None = None, draft: bool = False, tag: str = "LESSON") -> Path:
    """1280x720 YouTube thumbnail: big high-contrast title (last line highlighted), studio badge, circular instructor
    portrait with an accent ring. Drawn at 2x and downsampled so text and curves are anti-aliased."""
    s = SS
    img = _thumb_background(TW * s, TH * s)
    has_portrait = bool(portrait and portrait.exists())
    d = ImageDraw.Draw(img)
    pad = 70
    text_w = 700 if has_portrait else 1100

    # accent edge + top-left badge
    d.rectangle([0, 0, 18 * s, TH * s], fill=_ACCENT_RGB)
    bf = font(26 * s, bold=True)
    label = (subtitle or "").upper()
    bw = int(d.textlength(label, font=bf)) + 64 * s
    by = 54 * s
    d.rounded_rectangle([pad * s, by, pad * s + bw, by + 54 * s], 27 * s, fill=(14, 40, 66), outline=_ACCENT_RGB, width=2 * s)
    d.ellipse([pad * s + 22 * s, by + 21 * s, pad * s + 34 * s, by + 33 * s], fill=_ACCENT_RGB)
    d.text((pad * s + 46 * s, by + 27 * s), label, font=bf, fill=(224, 242, 254), anchor="lm")

    # title block, vertically centred in the space below the badge
    f, size, lines = _fit_title(d, text, text_w, 400, s)
    lh = int(size * 1.12 * s)
    block_h = lh * len(lines)
    y0 = 140 * s + (420 * s - block_h) // 2
    hl_from = len(lines) - 1 if len(lines) > 1 else len(lines)  # highlight the final line as the "hook"
    for i, ln in enumerate(lines):
        y = y0 + i * lh
        d.text((pad * s + 4 * s, y + 5 * s), ln, font=f, fill=(0, 0, 0))  # hard shadow for contrast on busy backgrounds
        d.text((pad * s, y), ln, font=f, fill=_WARN_RGB if i >= hl_from else (248, 250, 252))
    d.rounded_rectangle([pad * s, y0 + block_h + 14 * s, (pad + 150) * s, y0 + block_h + 22 * s], 4 * s, fill=_ACCENT_RGB)

    # portrait: glow, accent ring, circular crop
    if has_portrait:
        dia, cx, cy = 430 * s, 1005 * s, 372 * s
        ring = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse([cx - dia // 2 - 18 * s, cy - dia // 2 - 18 * s, cx + dia // 2 + 18 * s, cy + dia // 2 + 18 * s], fill=_ACCENT_RGB + (150,))
        img.paste(Image.alpha_composite(img.convert("RGBA"), ring.filter(ImageFilter.GaussianBlur(26 * s))).convert("RGB"))
        d = ImageDraw.Draw(img)
        d.ellipse([cx - dia // 2 - 9 * s, cy - dia // 2 - 9 * s, cx + dia // 2 + 9 * s, cy + dia // 2 + 9 * s], fill=_WARN_RGB)
        d.ellipse([cx - dia // 2 - 4 * s, cy - dia // 2 - 4 * s, cx + dia // 2 + 4 * s, cy + dia // 2 + 4 * s], fill=(8, 14, 32))
        img.paste(_circle_portrait(portrait, dia), (cx - dia // 2, cy - dia // 2), _circle_portrait(portrait, dia))

    # footer strip + tag
    d = ImageDraw.Draw(img)
    d.rectangle([0, (TH - 10) * s, TW * s, TH * s], fill=_ACCENT_RGB)
    tf = font(24 * s, bold=True)
    tw = int(d.textlength(tag, font=tf)) + 40 * s
    d.rounded_rectangle([(TW - 70) * s - tw, 54 * s, (TW - 70) * s, 100 * s], 10 * s, fill=_WARN_RGB)
    d.text(((TW - 70) * s - tw // 2, 77 * s), tag, font=tf, fill=(15, 23, 42), anchor="mm")

    img = img.resize((TW, TH), Image.LANCZOS)
    if draft:
        _draft_banner(ImageDraw.Draw(img), TW, h=48)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=92, subsampling=0)
    return out

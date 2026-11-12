"""Frame-by-frame motion renderer for reels: animated backgrounds, graded Ken Burns photos, word-highlight pop captions,
animated headlines, scene transitions, beat-synced zoom pulse, film grain and a progress bar.

Everything is a pure function of time `t`, so frames are deterministic. Backgrounds are computed at low resolution and upscaled (cheap and
naturally soft); text is drawn with Pillow. numpy does the blending."""
import math
import random
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

from app.services import visuals

W, H, FPS = 1080, 1920, 30
Color = tuple[int, int, int]


@dataclass(frozen=True)
class Theme:
    base: Color
    blobs: tuple[Color, ...]
    accent: Color
    pulse: float  # beat zoom strength
    grain: int
    vignette: float
    case: str  # upper | lower | title
    transitions: tuple[str, ...]
    tint: Color | None = None  # warm/cool grade applied to photos
    energy: float = 1.0  # background motion speed


THEMES: dict[str, Theme] = {
    "trending": Theme((18, 8, 40), ((255, 40, 130), (255, 150, 30), (40, 200, 255), (150, 60, 255)), (255, 226, 60), 0.035, 9, 0.35, "upper", ("flash", "slide", "wipe", "fade"), None, 1.4),
    "lofi": Theme((28, 18, 48), ((255, 140, 120), (150, 90, 200), (255, 190, 130), (80, 100, 200)), (255, 205, 160), 0.0, 16, 0.55, "lower", ("fade",), (255, 200, 170), 0.5),
    "educational": Theme((8, 22, 48), ((30, 120, 255), (0, 200, 190), (100, 80, 255), (0, 150, 255)), (90, 235, 255), 0.012, 6, 0.3, "title", ("slide", "fade", "wipe"), None, 0.9),
    "motivational": Theme((10, 10, 14), ((240, 170, 40), (200, 80, 30), (120, 80, 20), (255, 210, 120)), (255, 200, 60), 0.03, 12, 0.55, "upper", ("fade", "flash"), (255, 225, 190), 0.8),
    "storytelling": Theme((16, 14, 30), ((150, 60, 110), (60, 70, 150), (200, 120, 90), (40, 40, 80)), (255, 170, 190), 0.01, 14, 0.55, "title", ("fade", "wipe"), (235, 215, 230), 0.6),
    "promo": Theme((6, 40, 44), ((20, 200, 180), (255, 200, 50), (255, 110, 70), (40, 120, 255)), (255, 235, 80), 0.03, 6, 0.25, "upper", ("slide", "wipe", "flash"), None, 1.2),
}


# ---------------------------------------------------------------- helpers
def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def ease_out_back(x: float) -> float:
    x = clamp(x)
    c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def ease_in_out(x: float) -> float:
    x = clamp(x)
    return x * x * (3 - 2 * x)


_CAP_FONTS = ("/System/Library/Fonts/Supplemental/Impact.ttf", "/Library/Fonts/Impact.ttf", "/System/Library/Fonts/Supplemental/Arial Black.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")


@lru_cache(maxsize=96)
def font(size: int) -> ImageFont.FreeTypeFont:
    for p in _CAP_FONTS:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return visuals.font(size, bold=True)


def _case(text: str, mode: str) -> str:
    return text.upper() if mode == "upper" else text.lower() if mode == "lower" else text


# ---------------------------------------------------------------- backgrounds
class Background:
    """Drifting colour blobs and bokeh particles over a vertical gradient (computed at 216x384, upscaled)."""
    LW, LH = 216, 384

    def __init__(self, theme: Theme, seed: int):
        rng = random.Random(seed)
        self.theme = theme
        yy, xx = np.mgrid[0:self.LH, 0:self.LW]
        self.X, self.Y = (xx / self.LW).astype(np.float32), (yy / self.LH).astype(np.float32)
        top = np.array(theme.base, np.float32) * 1.25
        bot = np.array(theme.base, np.float32) * 0.55
        self.grad = (top[None, None, :] * (1 - self.Y[..., None]) + bot[None, None, :] * self.Y[..., None]).astype(np.float32)
        cols = list(theme.blobs)
        rng.shuffle(cols)
        self.blobs = [(np.array(c, np.float32), rng.uniform(0, 6.28), rng.uniform(0, 6.28), rng.uniform(0.18, 0.42), rng.uniform(0.15, 0.36), rng.uniform(0.22, 0.4))
                      for c in cols]  # colour, phase x, phase y, freq x, freq y, radius
        self.parts = [(rng.random(), rng.random(), rng.uniform(0.012, 0.03), rng.uniform(0.02, 0.07), rng.uniform(0, 6.28)) for _ in range(12)]
        self.white = np.array((255, 255, 255), np.float32)

    def frame(self, t: float, beat: float = 0.0) -> np.ndarray:
        f = self.grad.copy()
        sp = self.theme.energy
        for col, px, py, fx, fy, r in self.blobs:
            cx, cy = 0.5 + 0.36 * math.sin(fx * sp * t * 2 + px), 0.5 + 0.38 * math.sin(fy * sp * t * 2 + py)
            rr = r * (1 + 0.25 * beat)
            d2 = ((self.X - cx) * 0.5625) ** 2 + (self.Y - cy) ** 2
            g = (np.exp(-d2 / (rr * rr * 0.32)) * 0.85)[..., None]
            f = f * (1 - g) + col * g
        for x0, y0, r, v, ph in self.parts:  # bokeh drifting upward
            cy = (y0 - v * sp * t) % 1.0
            cx = x0 + 0.03 * math.sin(t * 0.8 + ph)
            d2 = ((self.X - cx) * 0.5625) ** 2 + (self.Y - cy) ** 2
            g = (np.exp(-d2 / (r * r)) * (0.28 + 0.12 * math.sin(t * 2 + ph)))[..., None]
            f = f * (1 - g) + self.white * g
        img = Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
        return np.asarray(img)


def prep_photo(path: Path, theme: Theme) -> Image.Image:
    """Cover-crop to 1.3x the frame (zoom headroom) and grade: a touch more contrast/saturation, optional warm tint."""
    im = ImageOps.fit(Image.open(path).convert("RGB"), (int(W * 1.3), int(H * 1.3)), Image.LANCZOS, centering=(0.5, 0.42))
    im = ImageEnhance.Color(ImageEnhance.Contrast(im).enhance(1.1)).enhance(1.12)
    if theme.tint:
        im = Image.blend(im, Image.new("RGB", im.size, theme.tint), 0.10)
    return im


def ken_burns(src: Image.Image, p: float, motion: str, extra_zoom: float) -> np.ndarray:
    sw, sh = src.size
    zz = {"in": 1.0 + 0.16 * p, "out": 1.16 - 0.16 * p, "left": 1.12, "right": 1.12}[motion] + extra_zoom
    vw, vh = sw / zz / 1.3 * 1.0, sh / zz / 1.3 * 1.0  # at zz=1 the view is exactly frame-sized * 1.0
    vw, vh = W * (1.3 / zz), H * (1.3 / zz)
    vw, vh = min(vw, sw), min(vh, sh)
    cx, cy = sw / 2, sh / 2
    span = sw - vw
    if motion == "left":
        cx = vw / 2 + span * (0.2 + 0.6 * p)
    elif motion == "right":
        cx = vw / 2 + span * (0.8 - 0.6 * p)
    x0, y0 = cx - vw / 2, cy - vh / 2
    out = src.transform((W, H), Image.AFFINE, (vw / W, 0, x0, 0, vh / H, y0), resample=Image.BICUBIC)
    return np.asarray(out)


# ---------------------------------------------------------------- scene model
@dataclass
class SceneFx:
    start: float
    dur: float
    headline: str
    chunks: list[list[tuple[str, float, float]]]  # caption chunks -> (word, t_start, t_end), absolute seconds
    photo: Image.Image | None
    motion: str
    bg: Background | None = None
    _layouts: dict = field(default_factory=dict)


def _shade_masks(theme: Theme) -> tuple[np.ndarray, np.ndarray]:
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    nx, ny = (xx / W - 0.5) * 2, (yy / H - 0.5) * 2
    vig = 1 - theme.vignette * np.clip((nx ** 2 * 0.7 + ny ** 2 * 0.9) - 0.25, 0, 1)
    bottom = 1 - 0.5 * np.clip((yy / H - 0.5) / 0.5, 0, 1) ** 1.3  # darken lower half so captions read on any photo
    top = 1 - 0.25 * np.clip((0.2 - yy / H) / 0.2, 0, 1)
    to_u = lambda m: np.clip(m * 256, 0, 256).astype(np.uint16)[..., None]  # noqa: E731
    return to_u(vig), to_u(vig * bottom * top)


def _shade(frame: np.ndarray, mask: np.ndarray) -> np.ndarray:
    return ((frame.astype(np.uint16) * mask) >> 8).astype(np.uint8)


# ---------------------------------------------------------------- text
def _layout(words: list[str], size: int, max_w: int, d: ImageDraw.ImageDraw):
    """Greedy wrap; returns [(index, cx, cy)] relative to the block centre, and the block height."""
    f = font(size)
    sp = max(d.textlength(" ", font=f), size * 0.34)
    lines, cur, cw = [], [], 0.0
    for i, w in enumerate(words):
        ww = d.textlength(w, font=f)
        if cur and cw + sp + ww > max_w:
            lines.append((cur, cw))
            cur, cw = [], 0.0
        cw += (sp if cur else 0) + ww
        cur.append((i, ww))
    lines.append((cur, cw))
    lh = size * 1.12
    out = []
    y0 = -(len(lines) - 1) * lh / 2
    for li, (ln, lw) in enumerate(lines):
        x = -lw / 2
        for i, ww in ln:
            out.append((i, x + ww / 2, y0 + li * lh))
            x += ww + sp
    return out, lh * len(lines)


def _stroke_text(d, xy, text, size, fill, alpha, stroke=9):
    d.text(xy, text, font=font(size), fill=(*fill, alpha), anchor="mm", stroke_width=stroke, stroke_fill=(0, 0, 0, int(alpha * 0.92)))


def draw_caption(img: Image.Image, sc: SceneFx, chunk, t: float, theme: Theme):
    a_in = clamp((t - chunk[0][1]) / 0.12)
    words = [_case(w.strip(".,;:"), theme.case) for w, _, _ in chunk]
    key = tuple(words)
    layer = Image.new("RGBA", (W, 640), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if key not in sc._layouts:
        size = 104 if len(" ".join(words)) <= 18 else 92 if len(" ".join(words)) <= 26 else 80
        sc._layouts[key] = (size, *_layout(words, size, W - 190, d))
    size, pos, _ = sc._layouts[key]
    pop_in = 0.86 + 0.14 * ease_out_back(a_in)
    for i, cx, cy in pos:
        _, w0, w1 = chunk[i]
        if t < w0:
            col, al, s = (255, 255, 255), 150, 1.0
        elif t < w1:
            k = clamp((t - w0) / 0.16)
            col, al, s = theme.accent, 255, 1 + 0.10 * math.sin(math.pi * k)
        else:
            col, al, s = (255, 255, 255), 255, 1.0
        _stroke_text(d, (W / 2 + cx * pop_in, 320 + cy * pop_in), words[i], max(20, int(size * s * pop_in)), col, int(al * a_in))
    img.paste(layer, (0, 1290 - 320), layer)


def draw_pill(img: Image.Image, text: str, lt: float, theme: Theme):
    e = ease_out_back(lt / 0.45)
    al = int(255 * clamp(lt / 0.25))
    if al <= 0:
        return
    f = font(50)
    t = _case(text, "upper" if theme.case != "lower" else "lower")
    layer = Image.new("RGBA", (W, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    tw = d.textlength(t, font=f)
    y = 100 + (1 - e) * -70
    d.rounded_rectangle([W / 2 - tw / 2 - 40, y - 48, W / 2 + tw / 2 + 40, y + 48], 48, fill=(*theme.accent, al))
    d.text((W / 2, y + 2), t, font=f, fill=(15, 15, 25, al), anchor="mm")
    img.paste(layer, (0, 150), layer)


def draw_title(img: Image.Image, sc: SceneFx, lt: float, theme: Theme):
    """Big kinetic title for scenes without a photo: words pop in one by one, accent underline wipes across."""
    words = [_case(w, theme.case if theme.case != "title" else "upper") for w in sc.headline.split()] or [""]
    layer = Image.new("RGBA", (W, 900), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    size = 150
    while size > 70:
        pos, bh = _layout(words, size, W - 170, d)
        if bh <= 3 * size * 1.12:
            break
        size -= 10
    pos, bh = _layout(words, size, W - 170, d)
    hot = max(range(len(words)), key=lambda i: len(words[i]))
    for i, cx, cy in pos:
        k = (lt - 0.08 - i * 0.09) / 0.35
        if k <= 0:
            continue
        e = ease_out_back(k)
        _stroke_text(d, (W / 2 + cx, 450 + cy + (1 - clamp(k)) * 40), words[i], max(20, int(size * (0.55 + 0.45 * e))), theme.accent if i == hot else (255, 255, 255), int(255 * clamp(k * 2)), 10)
    bw = int(clamp((lt - 0.55) / 0.4) * 360)
    if bw > 0:
        d.rounded_rectangle([W / 2 - bw / 2, 450 + bh / 2 + 34, W / 2 + bw / 2, 450 + bh / 2 + 50], 8, fill=(*theme.accent, 255))
    img.paste(layer, (0, 320), layer)


# ---------------------------------------------------------------- transitions
def transition(a: np.ndarray, b: np.ndarray, p: float, kind: str, accent: Color) -> np.ndarray:
    e = ease_in_out(p)
    if kind == "slide":
        s = int(W * e)
        out = np.empty_like(a)
        out[:, :W - s], out[:, W - s:] = a[:, s:], b[:, :s]
        return out
    if kind == "wipe":
        y = int(H * (1 - e))
        out = a.copy()
        out[y:] = b[y:]
        out[max(y - 6, 0):y] = accent
        return out
    if kind == "flash":
        white = 255
        k = e * 2 if e < 0.5 else (1 - e) * 2
        src = a if e < 0.5 else b
        return (src.astype(np.uint16) * int((1 - 0.92 * k) * 256) + int(white * 0.92 * k * 256) >> 8).astype(np.uint8)
    k = int(e * 256)
    return ((a.astype(np.uint16) * (256 - k) + b.astype(np.uint16) * k) >> 8).astype(np.uint8)


# ---------------------------------------------------------------- canvas
class ReelCanvas:
    T = 0.4  # transition length (s)

    def __init__(self, scenes: list[SceneFx], style: str, total: float, bpm: int | None):
        self.scenes, self.theme, self.total, self.bpm = scenes, THEMES[style], total, bpm
        self.vig, self.photo_shade = _shade_masks(self.theme)
        rng = np.random.default_rng(3)
        g = self.theme.grain
        self.noise = [rng.integers(-g, g + 1, (H, W, 1), dtype=np.int16) for _ in range(4)] if g else []
        for i, s in enumerate(scenes):
            if s.photo is None:
                s.bg = Background(self.theme, seed=i * 7 + 1)
        self.bounds = [s.start for s in scenes[1:]]

    def _beat(self, t: float) -> float:
        return math.exp(-9 * (t % (60 / self.bpm))) if self.bpm and self.theme.pulse else 0.0

    def scene_frame(self, i: int, t: float, fidx: int) -> np.ndarray:
        s = self.scenes[i]
        lt = t - s.start
        p = clamp(lt / s.dur)
        beat = self._beat(t)
        if s.photo is not None:
            arr = _shade(ken_burns(s.photo, p, s.motion, self.theme.pulse * beat), self.photo_shade)
        else:
            arr = _shade(s.bg.frame(t, beat), self.vig)
        if self.noise:
            arr = np.clip(arr.astype(np.int16) + self.noise[fidx % 4], 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)
        if lt >= 0:
            if s.photo is None:
                draw_title(img, s, lt, self.theme)
            elif s.headline:
                draw_pill(img, s.headline, lt, self.theme)
        for ch in s.chunks:
            if ch[0][1] <= t < ch[-1][2] + 0.08:
                draw_caption(img, s, ch, t, self.theme)
                break
        return np.asarray(img)

    def frame(self, fidx: int) -> np.ndarray:
        t = fidx / FPS
        out = None
        for j, b in enumerate(self.bounds):
            if abs(t - b) < self.T / 2:
                kind = self.theme.transitions[j % len(self.theme.transitions)]
                out = transition(self.scene_frame(j, t, fidx), self.scene_frame(j + 1, t, fidx), (t - (b - self.T / 2)) / self.T, kind, self.theme.accent)
                break
        if out is None:
            i = max((k for k, s in enumerate(self.scenes) if s.start <= t), default=0)
            out = self.scene_frame(i, t, fidx)
        out = np.array(out)  # writable copy
        pw = int((W - 120) * clamp(t / self.total))
        reg = out[96:108, 60:W - 60]
        reg[:] = (reg.astype(np.uint16) * 184 + 255 * 72 >> 8).astype(np.uint8)
        out[96:108, 60:60 + pw] = self.theme.accent
        return out

import logging
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps

logger = logging.getLogger(__name__)

CANVAS_SIZE = (1080, 1350)  # Instagram/TikTok carousel — 4:5 portrait
ACCENT_COLOR = (245, 197, 24)  # amber/gold, matches the brand's "shock" callouts
WHITE = (255, 255, 255)
FOOTER_GRAY = (215, 215, 215)
MARGIN = 64

# Checked in order; the first one that exists on disk is used. Covers the
# GitHub Actions Ubuntu runner (dejavu/liberation), macOS, and Windows dev
# machines so local runs degrade gracefully instead of crashing.
_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
]
_REGULAR_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
]


def _find_font(candidates: list[str]) -> Optional[str]:
    for path in candidates:
        if Path(path).exists():
            return path
    return None


def _cover_resize(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(img, size, Image.LANCZOS)


def _gradient_overlay(size: tuple[int, int]) -> Image.Image:
    """Transparent at the top, darkening toward the bottom so white text
    stays readable over any photo without hiding the image itself."""
    w, h = size
    gradient = Image.new("L", (1, h))
    for y in range(h):
        t = max(0.0, min(1.0, (y - h * 0.28) / (h * 0.72)))
        gradient.putpixel((0, y), int(t * 215))
    gradient = gradient.resize((w, h))
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    overlay.putalpha(gradient)
    return overlay


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_headline(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: str,
    max_width: int,
    max_height: int,
    start_size: int = 92,
    min_size: int = 44,
) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    size = start_size
    while size >= min_size:
        font = ImageFont.truetype(font_path, size)
        lines = _wrap_text(draw, text, font, max_width)
        line_height = int(size * 1.22)
        if line_height * len(lines) <= max_height:
            return font, lines, line_height
        size -= 4
    font = ImageFont.truetype(font_path, min_size)
    return font, _wrap_text(draw, text, font, max_width), int(min_size * 1.22)


def render_slide(
    photo_path: str,
    headline: str,
    out_path: str,
    slide_num: int,
    total_slides: int,
    credit: str = "",
) -> bool:
    """Composite the downloaded stock photo + headline text + brand chrome
    into a finished, ready-to-post slide image (overwrites out_path).
    Returns False (and leaves the raw photo untouched) if no usable font is
    found on this machine, rather than crashing the run for a cosmetic step."""
    bold_font_path = _find_font(_BOLD_CANDIDATES)
    regular_font_path = _find_font(_REGULAR_CANDIDATES)
    if not bold_font_path or not regular_font_path:
        logger.warning("No usable font found — leaving slide as the raw stock photo")
        return False

    try:
        photo = Image.open(photo_path).convert("RGB")
        canvas = _cover_resize(photo, CANVAS_SIZE).convert("RGBA")
        canvas = Image.alpha_composite(canvas, _gradient_overlay(CANVAS_SIZE))
        draw = ImageDraw.Draw(canvas)

        text_area_width = CANVAS_SIZE[0] - MARGIN * 2
        text_area_height = int(CANVAS_SIZE[1] * 0.38)
        font, lines, line_height = _fit_headline(
            draw, headline.upper(), bold_font_path, text_area_width, text_area_height
        )

        y = CANVAS_SIZE[1] - MARGIN - 100 - line_height * len(lines)
        for line in lines:
            draw.text(
                (MARGIN, y), line, font=font, fill=WHITE,
                stroke_width=3, stroke_fill=(0, 0, 0),
            )
            y += line_height

        counter_font = ImageFont.truetype(bold_font_path, 34)
        counter_text = f"{slide_num}/{total_slides}"
        counter_width = draw.textlength(counter_text, font=counter_font)
        draw.text(
            (CANVAS_SIZE[0] - MARGIN - counter_width, MARGIN),
            counter_text, font=counter_font, fill=ACCENT_COLOR,
            stroke_width=2, stroke_fill=(0, 0, 0),
        )

        brand_font = ImageFont.truetype(regular_font_path, 26)
        draw.text(
            (MARGIN, CANVAS_SIZE[1] - MARGIN - 26),
            "MECANISMO AMERICANO", font=brand_font, fill=WHITE,
            stroke_width=2, stroke_fill=(0, 0, 0),
        )

        if credit:
            credit_font = ImageFont.truetype(regular_font_path, 20)
            credit_width = draw.textlength(credit, font=credit_font)
            draw.text(
                (CANVAS_SIZE[0] - MARGIN - credit_width, CANVAS_SIZE[1] - MARGIN - 22),
                credit, font=credit_font, fill=FOOTER_GRAY,
                stroke_width=1, stroke_fill=(0, 0, 0),
            )

        canvas.convert("RGB").save(out_path, "JPEG", quality=92)
        return True
    except Exception as e:
        logger.error(f"Failed to render finished slide for {photo_path}: {e}")
        return False

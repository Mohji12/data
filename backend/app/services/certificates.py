from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_ASSETS_ROOT = Path(__file__).resolve().parent.parent / "assets" / "certificate"
_LEGACY_ROOT = Path(__file__).resolve().parents[4] / "resources" / "assets" / "certificate"
_IMAGES_DIR = _ASSETS_ROOT / "images"
_FONTS_DIR = _ASSETS_ROOT / "fonts"

_NAVY_TEMPLATE = "template-navy.jpeg"
_NAME_FONT = "OpenSans-Italic.ttf"


@dataclass(frozen=True)
class TextRegion:
    y: int
    size: int
    cover_box: tuple[int, int, int, int]
    max_width: int
    bold: bool = False
    color: tuple[int, int, int] = (26, 35, 126)


@dataclass(frozen=True)
class TemplateLayout:
    name_y: int
    name_size: int
    name_color: tuple[int, int, int]
    batch: TextRegion | None = None
    course: TextRegion | None = None
    program: TextRegion | None = None


_LAYOUTS: dict[str, TemplateLayout] = {
    "template-navy.jpeg": TemplateLayout(
        name_y=354,
        name_size=20,
        name_color=(0, 0, 0),
        course=TextRegion(
            y=392,
            size=13,
            cover_box=(110, 376, 1060, 408),
            max_width=900,
            bold=True,
        ),
        program=TextRegion(
            y=430,
            size=12,
            cover_box=(110, 414, 1060, 446),
            max_width=920,
        ),
        batch=TextRegion(
            y=463,
            size=16,
            cover_box=(110, 448, 1060, 486),
            max_width=760,
            bold=True,
        ),
    ),
    "batch-12.jpg": TemplateLayout(
        name_y=502,
        name_size=32,
        name_color=(0, 0, 0),
    ),
    "default-large": TemplateLayout(
        name_y=502,
        name_size=34,
        name_color=(0, 0, 0),
        batch=TextRegion(
            y=640,
            size=20,
            cover_box=(320, 620, 1280, 670),
            max_width=980,
            bold=True,
        ),
    ),
}

_DEFAULT_COURSE_LINE = "has completed MASTER CLASSES IN CRITICAL CARE MEDICINE"
_DEFAULT_PROGRAM_LINE = (
    "An online education & training program offered by Dr. Harish Mallapura Maheshwarappa"
)


def _assets_images_dir() -> Path:
    if _IMAGES_DIR.is_dir():
        return _IMAGES_DIR
    legacy = _LEGACY_ROOT / "images"
    return legacy if legacy.is_dir() else _IMAGES_DIR


def _assets_fonts_dir() -> Path:
    if _FONTS_DIR.is_dir():
        return _FONTS_DIR
    legacy = _LEGACY_ROOT / "fonts"
    return legacy if legacy.is_dir() else _FONTS_DIR


def _normalize_display_name(full_name: str) -> str:
    name = " ".join((full_name or "").split()).strip()
    if not name:
        return name
    if not name.lower().startswith(("dr.", "dr ", "mr.", "mr ", "mrs.", "mrs ", "ms.", "ms ")):
        name = f"Dr. {name}"
    return name.upper()


def _apply_placeholders(text: str, subscription: str | None) -> str:
    sub = (subscription or "").strip()
    return (text or "").replace("{batch_name}", sub).strip()


def _batch_label_text(
    subscription: str | None,
    certificate_batch_label: str | None,
) -> str:
    label = _apply_placeholders(certificate_batch_label or "", subscription)
    if label:
        return label
    sub = (subscription or "").strip()
    if sub:
        return sub
    return "Master Classes in Critical Care Medicine"


def _template_candidates(subscription: str | None) -> list[str]:
    sub = (subscription or "").strip()
    if not sub:
        return [_NAVY_TEMPLATE]

    slug = re.sub(r"[^a-z0-9]+", "-", sub.lower()).strip("-")
    num_match = re.search(r"(\d+)", sub)
    batch_num = num_match.group(1) if num_match else ""

    names: list[str] = []
    if batch_num:
        names.extend(
            [
                f"Batch-{batch_num}.jpg",
                f"Batch-{batch_num}.jpeg",
                f"batch-{batch_num}.jpg",
                f"batch-{batch_num}.jpeg",
            ]
        )
    if slug:
        names.extend([f"{slug}.jpg", f"{slug}.jpeg"])
    names.append(_NAVY_TEMPLATE)
    return names


def _resolve_template_path(subscription: str | None) -> tuple[Path, bool]:
    images_dir = _assets_images_dir()
    for name in _template_candidates(subscription):
        path = images_dir / name
        if path.is_file():
            return path, name != _NAVY_TEMPLATE
    return images_dir / _NAVY_TEMPLATE, False


def _layout_for_template(path: Path, name_only: bool) -> TemplateLayout:
    key = path.name.lower()
    if key in _LAYOUTS:
        layout = _LAYOUTS[key]
    else:
        try:
            with Image.open(path) as img:
                layout = _LAYOUTS["default-large"] if img.width >= 1500 else _LAYOUTS[_NAVY_TEMPLATE]
        except OSError:
            layout = _LAYOUTS[_NAVY_TEMPLATE]
    if name_only:
        return TemplateLayout(
            name_y=layout.name_y,
            name_size=layout.name_size,
            name_color=layout.name_color,
        )
    return layout


def _load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    fonts_dir = _assets_fonts_dir()
    candidates: list[str] = []
    if bold:
        candidates.extend(["OpenSans-Bold.ttf", "arialbd.ttf"])
    else:
        candidates.append(_NAME_FONT)
    candidates.extend(["OpenSans-Regular.ttf", "arial.ttf"])
    for filename in candidates:
        path = fonts_dir / filename
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _sample_background(image: Image.Image, box: tuple[int, int, int, int]) -> tuple[int, int, int]:
    crop = image.crop(box)
    pixels = list(crop.getdata())
    if not pixels:
        return (238, 247, 250)
    r = sum(p[0] for p in pixels) // len(pixels)
    g = sum(p[1] for p in pixels) // len(pixels)
    b = sum(p[2] for p in pixels) // len(pixels)
    return (r, g, b)


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    y: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int],
    width: int,
    max_width: int | None = None,
) -> None:
    line = text
    if max_width:
        while line:
            bbox = draw.textbbox((0, 0), line, font=font)
            if (bbox[2] - bbox[0]) <= max_width:
                break
            if len(line) <= 12:
                break
            line = line[:-4].rstrip() + "…"
    bbox = draw.textbbox((0, 0), line, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = max(0, (width - text_w) // 2)
    draw.text((x, y - text_h // 2), line, font=font, fill=fill)


def _draw_bottom_right_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int],
    width: int,
    height: int,
    margin_x: int = 36,
    margin_y: int = 28,
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = max(0, width - text_w - margin_x)
    y = max(0, height - text_h - margin_y)
    draw.text((x, y), text, font=font, fill=fill)


def _paint_region(
    draw: ImageDraw.ImageDraw,
    image: Image.Image,
    region: TextRegion,
    text: str,
) -> None:
    cover = region.cover_box
    bg = _sample_background(
        image,
        (cover[0], max(0, cover[1] - 16), cover[0] + 20, max(0, cover[1] - 4)),
    )
    draw.rectangle(cover, fill=bg)
    font = _load_font(region.size, bold=region.bold)
    _draw_centered_text(
        draw,
        text,
        y=region.y,
        font=font,
        fill=region.color,
        width=image.width,
        max_width=region.max_width,
    )


def _resolve_name_size(raw: str | int | None, template_default: int) -> int:
    if raw is None or raw == "":
        return template_default
    try:
        size = int(str(raw).strip())
    except ValueError:
        return template_default
    return max(12, min(48, size))


def render_certificate_image(
    full_name: str,
    subscription: str | None,
    certificate_batch_label: str | None = None,
    certificate_date_text: str | None = None,
    certificate_course_line: str | None = None,
    certificate_program_line: str | None = None,
    certificate_show_date: bool = False,
    certificate_name_size: str | int | None = None,
) -> Image.Image:
    template_path, name_only = _resolve_template_path(subscription)
    if not template_path.is_file():
        raise FileNotFoundError(f"Certificate template not found: {template_path}")

    image = Image.open(template_path).convert("RGB")
    layout = _layout_for_template(template_path, name_only)
    draw = ImageDraw.Draw(image)
    display_name = _normalize_display_name(full_name)
    batch_line = _batch_label_text(subscription, certificate_batch_label)
    course_line = _apply_placeholders(certificate_course_line or _DEFAULT_COURSE_LINE, subscription)
    program_line = _apply_placeholders(certificate_program_line or _DEFAULT_PROGRAM_LINE, subscription)

    name_size = _resolve_name_size(certificate_name_size, layout.name_size)
    name_font = _load_font(name_size)
    _draw_centered_text(
        draw,
        display_name,
        y=layout.name_y,
        font=name_font,
        fill=layout.name_color,
        width=image.width,
    )

    if not name_only:
        if layout.course and course_line:
            _paint_region(draw, image, layout.course, course_line)
        if layout.program and program_line:
            _paint_region(draw, image, layout.program, program_line)
        if layout.batch and batch_line:
            _paint_region(draw, image, layout.batch, batch_line)

        if certificate_show_date and (certificate_date_text or "").strip():
            date_font = _load_font(11)
            margin_x = max(28, int(image.width * 0.03))
            margin_y = max(22, int(image.height * 0.03))
            _draw_bottom_right_text(
                draw,
                f"Date: {certificate_date_text.strip()}",
                font=date_font,
                fill=(60, 60, 60),
                width=image.width,
                height=image.height,
                margin_x=margin_x,
                margin_y=margin_y,
            )

    return image


def _image_to_pdf_bytes(image: Image.Image) -> bytes:
    """Wrap the certificate image in a PDF (Pillow PDF 1.4 — opens reliably in Chrome)."""
    rgb = image.convert("RGB")
    buf = io.BytesIO()
    rgb.save(buf, format="PDF")
    return buf.getvalue()


def build_certificate_pdf(
    full_name: str,
    subscription: str | None,
    certificate_batch_label: str | None = None,
    certificate_date_text: str | None = None,
    certificate_course_line: str | None = None,
    certificate_program_line: str | None = None,
    certificate_show_date: bool = False,
    certificate_name_size: str | int | None = None,
) -> bytes:
    image = render_certificate_image(
        full_name=full_name,
        subscription=subscription,
        certificate_batch_label=certificate_batch_label,
        certificate_date_text=certificate_date_text,
        certificate_course_line=certificate_course_line,
        certificate_program_line=certificate_program_line,
        certificate_show_date=certificate_show_date,
        certificate_name_size=certificate_name_size,
    )
    return _image_to_pdf_bytes(image)

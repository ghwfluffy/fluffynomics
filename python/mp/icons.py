import hashlib
import io
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

MAX_ICON_DIMENSION = 64


def normalize_icon_png(raw_bytes: bytes) -> bytes:
    with Image.open(io.BytesIO(raw_bytes)) as img:
        converted = img.convert("RGBA")
        converted.thumbnail((MAX_ICON_DIMENSION, MAX_ICON_DIMENSION))
        buffer = io.BytesIO()
        converted.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()


def digest_icon(icon_png: bytes) -> str:
    return hashlib.sha256(icon_png).hexdigest()


def _hash_bytes(seed: str) -> bytes:
    return hashlib.sha256(seed.encode("utf-8")).digest()


def _color_from_seed(seed: str) -> tuple[int, int, int]:
    digest = _hash_bytes(seed)
    # Keep color vivid but not too dark/light.
    return (64 + digest[0] % 128, 64 + digest[1] % 128, 64 + digest[2] % 128)


def _initials_from_organization(name: str) -> str:
    trimmed = name.strip()
    if not trimmed:
        return "??"
    capitals = [ch for ch in trimmed if ch.isalpha() and ch.isupper()]
    if len(capitals) >= 2:
        return f"{capitals[0]}{capitals[1]}"
    letters = [ch for ch in trimmed if ch.isalpha()]
    if len(letters) >= 2:
        return f"{letters[0]}{letters[1]}".upper()
    if len(letters) == 1:
        return f"{letters[0]}?"
    return "??"


def generate_initials_icon(organization_name: str) -> bytes:
    bg = _color_from_seed(f"initials:{organization_name}")
    image = Image.new("RGBA", (MAX_ICON_DIMENSION, MAX_ICON_DIMENSION), (*bg, 255))
    text = _initials_from_organization(organization_name)

    font = ImageFont.load_default()
    for font_path in (
        "DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            font = ImageFont.truetype(font_path, size=56)
            break
        except Exception:
            continue

    # Render onto oversized transparent canvas, crop to actual ink bounds,
    # then scale into target box to avoid baseline clipping artifacts.
    canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    canvas_draw = ImageDraw.Draw(canvas)
    canvas_draw.text((24, 24), text, fill=(255, 255, 255, 255), font=font)
    alpha_bbox = canvas.split()[-1].getbbox()

    if alpha_bbox is None:
        glyph = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    else:
        glyph = canvas.crop(alpha_bbox)

    target_w, target_h = 38, 30
    scale = min(target_w / max(1, glyph.width), target_h / max(1, glyph.height))
    resized = glyph.resize(
        (max(1, int(glyph.width * scale)), max(1, int(glyph.height * scale))),
        resample=Image.Resampling.LANCZOS,
    )
    x = (MAX_ICON_DIMENSION - resized.width) // 2
    y = (MAX_ICON_DIMENSION - resized.height) // 2
    image.paste(resized, (x, y), resized)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def generate_identicon(organization_name: str) -> bytes:
    digest = _hash_bytes(f"identicon:{organization_name}")
    fg = _color_from_seed(f"fg:{organization_name}")
    bg = (245, 247, 250, 255)
    size = MAX_ICON_DIMENSION
    grid = 5
    padding = 6
    cell = (size - padding * 2) // grid
    image = Image.new("RGBA", (size, size), bg)
    draw = ImageDraw.Draw(image)

    bit_index = 0
    for row in range(grid):
        for col in range((grid + 1) // 2):
            byte_index = bit_index // 8
            mask = 1 << (bit_index % 8)
            bit_index += 1
            fill = (digest[byte_index] & mask) != 0
            if not fill:
                continue
            x = padding + col * cell
            y = padding + row * cell
            draw.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(*fg, 255))
            mirror_col = grid - 1 - col
            if mirror_col != col:
                mx = padding + mirror_col * cell
                draw.rectangle([mx, y, mx + cell - 1, y + cell - 1], fill=(*fg, 255))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def generate_algorithmic_icon(
    variant: Literal["initials", "identicon"], organization_name: str
) -> bytes:
    if variant == "initials":
        return generate_initials_icon(organization_name)
    if variant == "identicon":
        return generate_identicon(organization_name)
    raise ValueError(f"Unsupported icon variant: {variant}")

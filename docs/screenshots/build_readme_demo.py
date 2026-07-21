"""Build the README walkthrough GIF from the real GUI screenshots.

The source screenshots are kept for auditability.  This renderer applies
irreversible pixelation to paths, vault identifiers, and unmasked diff rows,
then adds a cursor, click feedback, and bilingual step labels.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter, ImageFont


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "content-masking-demo.gif"
TARGET_WIDTH = 860

FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")

NAVY = (15, 30, 52, 238)
CYAN = (41, 171, 226, 255)
GREEN = (24, 150, 92, 255)
WHITE = (255, 255, 255, 255)


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


LABEL_FONT = font(FONT_BOLD, 25)
SUBLABEL_FONT = font(FONT_REGULAR, 16)
BADGE_FONT = font(FONT_BOLD, 13)
END_FONT = font(FONT_BOLD, 38)
END_SUBFONT = font(FONT_REGULAR, 20)


def pixelate(image: Image.Image, box: tuple[int, int, int, int]) -> None:
    """Irreversibly obscure a sensitive region rather than merely soft-blur it."""
    left, top, right, bottom = box
    region = image.crop(box)
    tiny = region.resize(
        (max(1, region.width // 24), max(1, region.height // 14)),
        Image.Resampling.BILINEAR,
    )
    obscured = tiny.resize(region.size, Image.Resampling.NEAREST)
    obscured = obscured.filter(ImageFilter.GaussianBlur(2.2)).convert("RGBA")
    veil = Image.new("RGBA", region.size, (226, 232, 240, 170))
    obscured = Image.alpha_composite(obscured, veil)
    image.alpha_composite(obscured, (left, top))


def privacy_badge(image: Image.Image, xy: tuple[int, int]) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    x, y = xy
    label = "PRIVATE / 已模糊"
    bounds = draw.textbbox((0, 0), label, font=BADGE_FONT)
    width = bounds[2] - bounds[0] + 22
    height = 25
    draw.rounded_rectangle((x, y, x + width, y + height), 10, fill=(67, 78, 96, 218))
    draw.text((x + 11, y + 4), label, font=BADGE_FONT, fill=WHITE)


def sanitized(name: str) -> Image.Image:
    image = Image.open(HERE / name).convert("RGBA")

    boxes: dict[str, list[tuple[int, int, int, int]]] = {
        "02_mask_preview_diff.png": [
            (16, 541, 963, 603),
            (17, 701, 961, 727),
            (17, 770, 961, 796),
            (17, 815, 961, 840),
        ],
        "03_mask_committed.png": [
            (16, 531, 963, 580),
            (92, 582, 470, 607),
            (17, 701, 961, 727),
            (17, 770, 961, 796),
            (17, 815, 961, 840),
        ],
        "04_restore_confirm.png": [
            (16, 506, 963, 557),
            (17, 650, 961, 678),
            (17, 719, 961, 747),
            (17, 764, 961, 793),
            (17, 808, 961, 837),
        ],
    }
    for box in boxes.get(name, []):
        pixelate(image, box)

    if name in boxes:
        privacy_badge(image, (24, 545 if name != "04_restore_confirm.png" else 510))
    return image


def draw_step(
    image: Image.Image,
    step: int,
    title: str,
    subtitle: str,
    accent: tuple[int, int, int, int] = CYAN,
) -> None:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    width = 650
    height = 86
    left = (image.width - width) // 2
    top = 176
    shadow = (left + 5, top + 6, left + width + 5, top + height + 6)
    draw.rounded_rectangle(shadow, 19, fill=(0, 0, 0, 45))
    draw.rounded_rectangle((left, top, left + width, top + height), 19, fill=NAVY)
    draw.rounded_rectangle((left + 18, top + 18, left + 68, top + 68), 15, fill=accent)
    step_text = str(step)
    step_box = draw.textbbox((0, 0), step_text, font=LABEL_FONT)
    draw.text(
        (left + 43 - (step_box[2] - step_box[0]) / 2, top + 24),
        step_text,
        font=LABEL_FONT,
        fill=WHITE,
    )
    draw.text((left + 84, top + 12), title, font=LABEL_FONT, fill=WHITE)
    draw.text((left + 84, top + 49), subtitle, font=SUBLABEL_FONT, fill=(220, 231, 242, 255))
    image.alpha_composite(overlay)


def draw_cursor(
    image: Image.Image,
    xy: tuple[float, float],
    click_radius: int | None = None,
) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    x, y = int(xy[0]), int(xy[1])
    if click_radius is not None:
        alpha = max(55, 210 - click_radius * 8)
        draw.ellipse(
            (x - click_radius, y - click_radius, x + click_radius, y + click_radius),
            outline=(41, 171, 226, alpha),
            width=5,
        )
        draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill=(41, 171, 226, 120))

    pointer = [(x, y), (x + 2, y + 31), (x + 9, y + 23), (x + 17, y + 40),
               (x + 24, y + 36), (x + 16, y + 19), (x + 28, y + 17)]
    draw.polygon(pointer, fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
    inner = [(x + 3, y + 4), (x + 5, y + 25), (x + 10, y + 18),
             (x + 18, y + 35), (x + 21, y + 33), (x + 13, y + 16),
             (x + 23, y + 15)]
    draw.polygon(inner, fill=(19, 27, 38, 255))


def frame(
    base: Image.Image,
    step: tuple[int, str, str] | None,
    cursor: tuple[float, float] | None = None,
    click_radius: int | None = None,
) -> Image.Image:
    image = base.copy()
    if step:
        draw_step(image, *step)
    if cursor:
        draw_cursor(image, cursor, click_radius)
    return image


def tween(start: tuple[int, int], end: tuple[int, int], count: int) -> Iterable[tuple[float, float]]:
    for index in range(1, count + 1):
        t = index / count
        eased = 1 - (1 - t) ** 3
        yield (
            start[0] + (end[0] - start[0]) * eased,
            start[1] + (end[1] - start[1]) * eased,
        )


def add_hold(
    frames: list[Image.Image],
    durations: list[int],
    image: Image.Image,
    duration: int,
) -> None:
    frames.append(image)
    durations.append(duration)


def add_transition(
    frames: list[Image.Image],
    durations: list[int],
    before: Image.Image,
    after: Image.Image,
    count: int = 7,
) -> None:
    for index in range(1, count + 1):
        frames.append(Image.blend(before, after, index / count))
        durations.append(65)


def end_card(base: Image.Image) -> Image.Image:
    image = base.copy()
    veil = Image.new("RGBA", image.size, (8, 18, 32, 204))
    image = Image.alpha_composite(image, veil)
    draw = ImageDraw.Draw(image, "RGBA")
    cx = image.width // 2
    cy = image.height // 2
    draw.ellipse((cx - 55, cy - 135, cx + 55, cy - 25), fill=GREEN)
    draw.line((cx - 27, cy - 80, cx - 6, cy - 57), fill=WHITE, width=11)
    draw.line((cx - 7, cy - 57, cx + 32, cy - 101), fill=WHITE, width=11)

    title = "Masked. Reviewed. Restored."
    title_box = draw.textbbox((0, 0), title, font=END_FONT)
    draw.text((cx - (title_box[2] - title_box[0]) / 2, cy + 2), title, font=END_FONT, fill=WHITE)
    subtitle = "本地脱敏 · 人工确认 · 精确还原"
    subtitle_box = draw.textbbox((0, 0), subtitle, font=END_SUBFONT)
    draw.text(
        (cx - (subtitle_box[2] - subtitle_box[0]) / 2, cy + 62),
        subtitle,
        font=END_SUBFONT,
        fill=(207, 225, 240, 255),
    )
    return image


def main() -> None:
    main_screen = sanitized("01_main_window.png")
    preview_screen = sanitized("02_mask_preview_diff.png")
    committed_screen = sanitized("03_mask_committed.png")
    restore_screen = sanitized("04_restore_confirm.png")

    s1 = (1, "Add a document", "拖入或选择 MD / TXT / DOCX / PDF")
    s2 = (2, "Review the privacy preview", "红色原文 → 绿色脱敏令牌；敏感内容已模糊")
    s3 = (3, "Confirm to create", "人工确认后才写入脱敏文件与本地 Vault")
    s4 = (4, "Restore exact originals", "再次拖入 .masked 文件，按需精确还原")

    frames: list[Image.Image] = []
    durations: list[int] = []

    cursor = (810, 130)
    add_hold(frames, durations, frame(main_screen, s1, cursor), 850)
    for cursor in tween(cursor, (502, 292), 10):
        add_hold(frames, durations, frame(main_screen, s1, cursor), 65)
    for radius in (10, 18, 27, 36):
        add_hold(frames, durations, frame(main_screen, s1, cursor, radius), 75)
    add_hold(frames, durations, frame(main_screen, s1, cursor), 350)

    before = frame(main_screen, s1, cursor)
    after = frame(preview_screen, s2, (502, 292))
    add_transition(frames, durations, before, after)
    add_hold(frames, durations, after, 1250)
    cursor = (502, 292)
    for cursor in tween(cursor, (466, 632), 11):
        add_hold(frames, durations, frame(preview_screen, s2, cursor), 65)
    for radius in (10, 18, 27, 36):
        add_hold(frames, durations, frame(preview_screen, s2, cursor, radius), 75)

    before = frame(preview_screen, s2, cursor)
    after = frame(committed_screen, s3, cursor)
    add_transition(frames, durations, before, after)
    add_hold(frames, durations, after, 1450)
    for cursor in tween(cursor, (502, 292), 9):
        add_hold(frames, durations, frame(committed_screen, s3, cursor), 65)
    for radius in (10, 18, 27, 36):
        add_hold(frames, durations, frame(committed_screen, s3, cursor, radius), 75)

    before = frame(committed_screen, s3, cursor)
    after = frame(restore_screen, s4, (502, 292))
    add_transition(frames, durations, before, after)
    add_hold(frames, durations, after, 1050)
    cursor = (502, 292)
    for cursor in tween(cursor, (447, 529), 9):
        add_hold(frames, durations, frame(restore_screen, s4, cursor), 65)
    for radius in (10, 18, 27, 36):
        add_hold(frames, durations, frame(restore_screen, s4, cursor, radius), 75)

    end = end_card(restore_screen)
    add_transition(frames, durations, frame(restore_screen, s4, cursor), end, count=8)
    add_hold(frames, durations, end, 1800)

    scaled: list[Image.Image] = []
    for item in frames:
        height = round(item.height * TARGET_WIDTH / item.width)
        scaled.append(item.resize((TARGET_WIDTH, height), Image.Resampling.LANCZOS).convert("RGB"))

    palette_strip = Image.new("RGB", (TARGET_WIDTH * 4, scaled[0].height))
    for index, sample in enumerate((scaled[0], scaled[18], scaled[38], scaled[-1])):
        palette_strip.paste(sample, (TARGET_WIDTH * index, 0))
    palette = palette_strip.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    quantized = [
        item.quantize(palette=palette, dither=Image.Dither.NONE)
        for item in scaled
    ]

    quantized[0].save(
        OUTPUT,
        save_all=True,
        append_images=quantized[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size / 1024 / 1024:.2f} MiB, {len(frames)} frames)")


if __name__ == "__main__":
    main()

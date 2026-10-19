#!/usr/bin/env python3
"""Draw a concise Learn review card as PNG and SVG with local fonts and Pillow."""

from __future__ import annotations

import argparse
import base64
import io
import json
import math
import os
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


WIDTH, HEIGHT, MARGIN = 1080, 1350, 72
INK, MUTED, PAPER, RULE = "#202A30", "#59666D", "#F7F7F2", "#DADFD9"
PROFILES = {
    "technical": ("工具与方法", "#176B61", "#E6F0EB"),
    "overview": ("概念与观点", "#94611F", "#F3ECDD"),
    "catalog": ("清单与选择", "#365B92", "#E9EEF6"),
    "visual": ("图例与动作", "#9A493C", "#F4EAE5"),
}


def card_errors(bundle: dict[str, Any]) -> list[str]:
    """Validate the optional card without importing the rendering dependency."""
    if "learning_card" not in bundle:
        return []  # Bundles produced before 0.3.3 remain usable.
    card = bundle["learning_card"]
    if not isinstance(card, dict):
        return ["learning_card must be an object"]
    errors: list[str] = []
    content_items = bundle.get("content_items", [])
    content_items = content_items if isinstance(content_items, list) else []
    for field in ("title", "takeaway"):
        if not isinstance(card.get(field), str) or not card[field].strip():
            errors.append(f"learning_card.{field} requires plain text")
    points = card.get("points", [])
    if not isinstance(points, list) or len(points) > 4:
        errors.append("learning_card.points must contain at most four points")
        points = []
    numbers: list[int] = []
    for index, point in enumerate(points):
        if not isinstance(point, dict):
            errors.append(f"learning_card.points[{index}] must be an object")
            continue
        for field in ("label", "text"):
            if not isinstance(point.get(field), str) or not point[field].strip():
                errors.append(f"learning_card.points[{index}].{field} requires plain text")
        if bundle.get("content_profile") == "catalog":
            number = point.get("item_number")
            count = len(content_items)
            if type(number) is not int or not 1 <= number <= count:
                errors.append("Each catalog card point must identify its source item_number (one-based)")
            else:
                numbers.append(number)
    if len(set(numbers)) != len(numbers):
        errors.append("Catalog card item_number values must be unique")
    flow = card.get("flow", [])
    if not isinstance(flow, list) or (flow and not 2 <= len(flow) <= 4):
        errors.append("learning_card.flow must contain two to four labels when present")
    elif any(not isinstance(label, str) or not label.strip() for label in flow):
        errors.append("learning_card.flow labels must be non-empty strings")
    if "loop" in card and not isinstance(card["loop"], bool):
        errors.append("learning_card.loop must be a boolean")
    if card.get("loop") and not flow:
        errors.append("learning_card.loop requires a flow")
    if "scope" in card and not isinstance(card["scope"], str):
        errors.append("learning_card.scope must be plain text")
    ids = card.get("visual_ids", [])
    if not isinstance(ids, list) or len(ids) > 2 or any(not isinstance(value, str) for value in ids):
        errors.append("learning_card.visual_ids must contain at most two source visual IDs")
        ids = []
    if len(set(ids)) != len(ids):
        errors.append("learning_card.visual_ids must be unique")
    known: set[str] = set()
    for collection in ("original_images", "keyframes", "experiment_figures"):
        values = bundle.get(collection, [])
        if isinstance(values, list):
            known.update(str(value["id"]) for value in values if isinstance(value, dict) and value.get("id"))
    if any(value not in known for value in ids):
        errors.append("learning_card.visual_ids must reference acquired visuals")
    if bundle.get("content_profile") == "catalog" and not points:
        errors.append("A catalog card requires selected item points")
    if bundle.get("content_profile") == "visual":
        item_ids = {item.get("visual_id") for item in content_items if isinstance(item, dict)}
        if not ids or any(value not in item_ids for value in ids):
            errors.append("A visual card requires one or two representative content-item images")
        if flow or len(points) > 2:
            errors.append("A visual card uses images and at most two points, without a flow")
    elif ids:
        errors.append("Card source photographs are supported by the visual profile")
    return errors


def find_fonts(explicit: str | None = None) -> tuple[Path, Path]:
    override = explicit or os.environ.get("LEARN_CARD_FONT")
    if override:
        regular = Path(override).expanduser().resolve()
        bold = Path(os.environ.get("LEARN_CARD_BOLD_FONT", str(regular))).expanduser().resolve()
        if not regular.is_file() or not bold.is_file():
            raise ValueError("The selected card font does not exist")
        return regular, bold
    windows = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    pairs = [
        (windows / "msyh.ttc", windows / "msyhbd.ttc"),
        (Path("/System/Library/Fonts/PingFang.ttc"), Path("/System/Library/Fonts/PingFang.ttc")),
        (Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"), Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")),
        (Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"), Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc")),
    ]
    for regular, bold in pairs:
        if regular.is_file():
            return regular, bold if bold.is_file() else regular
    raise ValueError("No Chinese-capable font found. Set LEARN_CARD_FONT or pass --font with a CJK font.")


def wrap_text(text: str, font: Any, width: float) -> list[str]:
    lines: list[str] = []
    no_start = set("，。！？；：、）】》」』”’.,!?;:)]}")
    no_end = set("（【《「『“‘([{")
    for paragraph in text.split("\n"):
        paragraph_start = len(lines)
        line = ""
        tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_./+@#:-]*|[^\x00-\x7f]|\s+|.", paragraph)
        for token in tokens:
            parts = list(token) if font.getlength(token) > width else [token]
            for part in parts:
                if line and font.getlength(line + part) > width:
                    carry = ""
                    if part in no_start or line[-1:] in no_end:
                        carry, line = line[-1:], line[:-1]
                    if line.strip():
                        lines.append(line.rstrip())
                    line = carry + part.lstrip()
                else:
                    line += part if line else part.lstrip()
        if line.strip():
            lines.append(line.rstrip())
        # Prefer a clause boundary over a final line containing only a few characters.
        if len(lines) - paragraph_start >= 2 and font.getlength(lines[-1]) < width * 0.23:
            previous, last = lines[-2:]
            candidates = []
            for boundary in re.finditer(r"[，；：、。！？,;: ]", previous):
                left, right = previous[:boundary.end()].rstrip(), previous[boundary.end():] + last
                if left and right and font.getlength(right) <= width:
                    candidates.append((abs(font.getlength(left) - font.getlength(right)), left, right))
            if candidates:
                _, lines[-2], lines[-1] = min(candidates)
    return lines or [""]


class Canvas:
    """Use the same measured layout for raster and editable vector output."""

    def __init__(self, regular: Path, bold: Path, title: str, description: str):
        from PIL import Image, ImageDraw, ImageFont

        self.image = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
        self.draw = ImageDraw.Draw(self.image)
        self.fonts = (regular, bold)
        self.font_class = ImageFont
        self.cache: dict[tuple[int, bool], Any] = {}
        self.svg = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">',
            f"<title id=\"title\">{escape(title)}</title><desc id=\"desc\">{escape(description)}</desc>",
            f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{PAPER}"/>',
        ]

    def font(self, size: int, bold: bool = False) -> Any:
        key = (size, bold)
        if key not in self.cache:
            self.cache[key] = self.font_class.truetype(str(self.fonts[bool(bold)]), size)
        return self.cache[key]

    def rect(self, x: float, y: float, w: float, h: float, fill: str, radius: int = 0) -> None:
        self.draw.rounded_rectangle((x, y, x + w, y + h), radius=radius, fill=fill)
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}"/>')

    def line(self, points: list[tuple[float, float]], fill: str, width: int = 2) -> None:
        self.draw.line(points, fill=fill, width=width)
        coordinates = " ".join(f"{x},{y}" for x, y in points)
        self.svg.append(f'<polyline points="{coordinates}" fill="none" stroke="{fill}" stroke-width="{width}"/>')

    def arrow(self, start: tuple[float, float], end: tuple[float, float], fill: str) -> None:
        self.line([start, end], fill, 2)
        angle = math.atan2(end[1] - start[1], end[0] - start[0])
        points = [end] + [(end[0] - 10 * math.cos(angle + d), end[1] - 10 * math.sin(angle + d)) for d in (-0.45, 0.45)]
        self.draw.polygon(points, fill=fill)
        coordinates = " ".join(f"{x},{y}" for x, y in points)
        self.svg.append(f'<polygon points="{coordinates}" fill="{fill}"/>')

    def text(self, text: str, x: float, y: float, size: int, fill: str = INK, bold: bool = False) -> None:
        font = self.font(size, bold)
        baseline = y + font.getmetrics()[0]
        self.draw.text((x, baseline), text, font=font, fill=fill, anchor="ls")
        family = escape(font.getname()[0], quote=True)
        weight = 700 if bold else 400
        self.svg.append(f'<text x="{x}" y="{baseline}" fill="{fill}" font-family="{family}, Noto Sans CJK SC, sans-serif" font-size="{size}" font-weight="{weight}" xml:space="preserve">{escape(text)}</text>')

    def block(self, text: str, x: float, y: float, width: float, size: int, *, fill: str = INK, bold: bool = False, max_lines: int = 0) -> float:
        lines = wrap_text(text, self.font(size, bold), width)
        if max_lines and len(lines) > max_lines:
            raise ValueError(f"Card text is too dense; rewrite without truncation: {text}")
        height = math.ceil(size * 1.40)
        for line in lines:
            self.text(line, x, y, size, fill, bold)
            y += height
        return y

    def photograph(self, source: Path, x: int, y: int, w: int, h: int) -> None:
        from PIL import Image, ImageOps

        with Image.open(source) as image:
            contained = ImageOps.contain(ImageOps.exif_transpose(image).convert("RGB"), (w, h), Image.Resampling.LANCZOS)
        px, py = x + (w - contained.width) // 2, y + (h - contained.height) // 2
        self.image.paste(contained, (px, py))
        encoded = io.BytesIO()
        contained.info.clear()
        contained.save(encoded, format="PNG")
        data = base64.b64encode(encoded.getvalue()).decode("ascii")
        self.svg.append(f'<image x="{px}" y="{py}" width="{contained.width}" height="{contained.height}" href="data:image/png;base64,{data}"/>')


@dataclass
class CardOutput:
    png: bytes
    svg: bytes
    title: str
    plain_text: str


def create_card(bundle: dict[str, Any], evidence_dir: Path, font: str | None = None) -> CardOutput:
    from PIL.PngImagePlugin import PngInfo

    errors = card_errors(bundle)
    if errors or "learning_card" not in bundle:
        raise ValueError("; ".join(errors) or "learning_card is required to render a card")
    profile = bundle.get("content_profile")
    if profile not in PROFILES:
        raise ValueError("A card requires a valid content_profile")
    card = bundle["learning_card"]
    points = card.get("points", [])
    scope = card.get("scope", "").strip()
    source = bundle.get("source", {})
    plain_text = "\n".join([card["title"], card["takeaway"], *card.get("flow", []), *[f'{p["label"]}：{p["text"]}' for p in points], scope]).strip()
    canvas = Canvas(*find_fonts(font), card["title"], plain_text)
    category, accent, tint = PROFILES[profile]
    content_width = WIDTH - MARGIN * 2
    canvas.rect(MARGIN, 66, 7, 29, accent, 3)
    canvas.text(category, MARGIN + 22, 61, 23, accent, True)
    brand = "LEARN  /  学习小卡"
    canvas.text(brand, WIDTH - MARGIN - canvas.font(21).getlength(brand), 64, 21, MUTED)
    y = canvas.block(card["title"], MARGIN, 127, content_width, 62, bold=True, max_lines=2)
    y += 25
    lines = wrap_text(card["takeaway"], canvas.font(35), content_width - 52)
    if len(lines) > 3:
        raise ValueError("Card takeaway exceeds three readable lines; rewrite the synthesis")
    box_height = len(lines) * 49 + 44
    canvas.rect(MARGIN, y, content_width, box_height, tint, 18)
    canvas.block(card["takeaway"], MARGIN + 26, y + 18, content_width - 52, 35, max_lines=3)
    y += box_height + 38

    flow = card.get("flow", [])
    if flow:
        gap, box_height = 32, 88
        box_width = (content_width - gap * (len(flow) - 1)) / len(flow)
        for index, label in enumerate(flow):
            x = MARGIN + index * (box_width + gap)
            canvas.rect(x, y, box_width, box_height, "#FFFFFF", 12)
            labels = wrap_text(label, canvas.font(28, True), box_width - 24)
            if len(labels) > 2:
                raise ValueError("A flow label needs to be shorter")
            ty = y + (box_height - len(labels) * 39) / 2 - 2
            for line in labels:
                tx = x + (box_width - canvas.font(28, True).getlength(line)) / 2
                canvas.text(line, tx, ty, 28, accent, True)
                ty += 39
            if index:
                canvas.arrow((x - gap + 7, y + 44), (x - 7, y + 44), accent)
        if card.get("loop"):
            left, right = MARGIN + box_width / 2, WIDTH - MARGIN - box_width / 2
            canvas.line([(right, y + box_height), (right, y + box_height + 23), (left, y + box_height + 23)], accent, 2)
            canvas.arrow((left, y + box_height + 23), (left, y + box_height + 3), accent)
            y += 25
        y += box_height + 36

    coverage = ""
    if profile == "catalog":
        total, selected = len(bundle.get("content_items", [])), len(points)
        coverage = f"完整 {total} 项" if selected == total else f"精选 {selected}/{total} 项 · 完整清单见笔记"
    elif profile == "visual":
        ids = card["visual_ids"]
        index = {str(item.get("id")): item for collection in ("original_images", "keyframes") for item in bundle.get(collection, []) if isinstance(item, dict)}
        items = {item.get("visual_id"): item for item in bundle.get("content_items", [])}
        gap, photo_height = 24, 420
        frame_width = (content_width - gap * (len(ids) - 1)) // len(ids)
        for number, visual_id in enumerate(ids):
            local = index[visual_id].get("local_path")
            if not local:
                raise ValueError("A visual card requires locally acquired source images")
            image = Path(str(local)).expanduser()
            image = image if image.is_absolute() else evidence_dir / image
            if not image.is_file():
                raise ValueError(f"Card source image is missing: {image}")
            x = MARGIN + number * (frame_width + gap)
            canvas.rect(x, y, frame_width, photo_height, tint, 10)
            canvas.photograph(image, x + 6, int(y + 6), frame_width - 12, photo_height - 12)
            canvas.block(str(items[visual_id].get("name", "")), x, y + photo_height + 10, frame_width, 24, bold=True, max_lines=1)
        y += photo_height + 64
        coverage = f"图例 {len(ids)}/{len(items)} · 全部方案见笔记"
    if coverage:
        canvas.text(coverage, MARGIN, y, 22, accent, True)
        y += 48

    body_size = 31 if len(points) == 4 or profile == "visual" else 33
    for number, point in enumerate(points, 1):
        if profile == "catalog":
            badge = str(point["item_number"]).zfill(2)
            canvas.text(badge, MARGIN, y + 1, 24, accent, True)
            x, width = MARGIN + 60, content_width - 60
        else:
            canvas.rect(MARGIN, y + 12, 6, 20, accent, 2)
            x, width = MARGIN + 22, content_width - 22
        y = canvas.block(point["label"], x, y, width, 26, fill=accent, bold=True, max_lines=1)
        y += 3
        y = canvas.block(point["text"], x, y, width, body_size, max_lines=3)
        y += 21 if len(points) == 4 else 23
    if scope:
        y += 1
        scope_lines = wrap_text(scope, canvas.font(25), content_width - 40)
        if len(scope_lines) > 3:
            raise ValueError("Card context is too long; keep the condition that changes the conclusion")
        box_height = len(scope_lines) * 35 + 30
        canvas.rect(MARGIN, y, content_width, box_height, "#EDEFE9", 12)
        y = canvas.block(scope, MARGIN + 20, y + 12, content_width - 40, 25, fill=MUTED) + 18
    if y > 1208:
        raise ValueError(f"Card content reaches {int(y)}px; shorten or select fewer points instead of shrinking text")

    canvas.line([(MARGIN, 1240), (WIDTH - MARGIN, 1240)], RULE)
    platform = {"bilibili": "Bilibili", "wechat": "微信公众号", "xiaohongshu": "小红书", "web": "网页", "local": "本地资料"}.get(str(source.get("platform")), "来源")
    byline = " · ".join(value for value in (platform, str(source.get("author", "")).strip()) if value)
    canvas.block(byline, MARGIN, 1255, content_width, 21, fill=MUTED, max_lines=1)
    url = str(source.get("url", ""))
    parsed = urlparse(url)
    visible_url = (parsed.netloc.removeprefix("www.") + parsed.path).rstrip("/") if parsed.scheme in {"http", "https"} else "完整资料与原文见笔记"
    if canvas.font(21).getlength(visible_url) > content_width:
        visible_url = parsed.netloc or "完整资料见笔记"
    if parsed.scheme in {"http", "https"}:
        canvas.svg.append(f'<a href="{escape(url, quote=True)}">')
    canvas.text(visible_url, MARGIN, 1290, 21, MUTED)
    if parsed.scheme in {"http", "https"}:
        canvas.svg.append("</a>")
    canvas.svg.append("</svg>")
    metadata = PngInfo()
    metadata.add_text("Title", card["title"])
    metadata.add_text("Description", plain_text)
    if parsed.scheme in {"http", "https"}:
        metadata.add_text("Source", url)
    data = io.BytesIO()
    canvas.image.save(data, format="PNG", pnginfo=metadata)
    return CardOutput(data.getvalue(), "\n".join(canvas.svg).encode("utf-8"), card["title"], plain_text)


def write_output(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError(f"Refusing to overwrite a different card: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--output", required=True, help="destination PNG")
    parser.add_argument("--svg-output", help="optional editable SVG with embedded source photographs")
    parser.add_argument("--font", help="local CJK-capable TrueType/OpenType font")
    args = parser.parse_args()
    try:
        evidence = Path(args.evidence).expanduser().resolve()
        bundle = json.loads(evidence.read_text(encoding="utf-8"))
        card = create_card(bundle, evidence.parent, args.font)
        png = Path(args.output).expanduser().resolve()
        if png.suffix.lower() != ".png":
            raise ValueError("--output must be a PNG path")
        write_output(png, card.png)
        svg = Path(args.svg_output).expanduser().resolve() if args.svg_output else None
        if svg:
            if svg.suffix.lower() != ".svg":
                raise ValueError("--svg-output must be an SVG path")
            write_output(svg, card.svg)
        print(json.dumps({"png": str(png), "svg": str(svg) if svg else None, "width": WIDTH, "height": HEIGHT}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

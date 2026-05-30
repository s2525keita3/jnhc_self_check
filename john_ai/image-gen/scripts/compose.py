#!/usr/bin/env python3
"""Composite a foreground cutout (e.g. the presenter) onto a background, with
an optional logo, and crop to a target aspect.

Designed for the JNHC thumbnail / SNS workflow: gpt-image makes the brand
BACKGROUND, the real person's photo is used as a transparent-PNG CUTOUT, and
text is added afterwards in an editor. This tool does the background+subject+
logo compositing so the person's real face is never re-synthesized.

Usage:
    python compose.py \
        --bg out/yt-bg.png \
        --fg assets/people/jon/jon-suit-cutout.png \
        --fg-anchor bottom-right --fg-scale 0.95 \
        --logo assets/logo/jnhc-horizontal-reverse.png \
        --logo-anchor top-left --logo-scale 0.16 \
        --size 1280x720 \
        --out out/thumb.png

Notes:
    --fg should be a PNG with transparency (a clean cutout). If it has no
    alpha, it is pasted as-is (you probably want to remove its background first;
    see assets/people/jon/README.md).
"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    raise SystemExit("error: Pillow is required.  pip install pillow")

ANCHORS = {
    "top-left", "top", "top-right",
    "left", "center", "right",
    "bottom-left", "bottom", "bottom-right",
}


def _place(canvas_w: int, canvas_h: int, w: int, h: int, anchor: str,
           dx: int, dy: int) -> tuple[int, int]:
    if "left" in anchor:
        x = 0
    elif "right" in anchor:
        x = canvas_w - w
    else:
        x = (canvas_w - w) // 2
    if "top" in anchor:
        y = 0
    elif "bottom" in anchor:
        y = canvas_h - h
    else:
        y = (canvas_h - h) // 2
    return x + dx, y + dy


def _fit_cover(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Resize+center-crop img to exactly target size (cover)."""
    src_ratio = img.width / img.height
    dst_ratio = target_w / target_h
    if src_ratio > dst_ratio:
        new_h = target_h
        new_w = round(target_h * src_ratio)
    else:
        new_w = target_w
        new_h = round(target_w / src_ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def _overlay(canvas: Image.Image, layer_path: str, anchor: str,
             scale: float, dx: int, dy: int) -> None:
    layer = Image.open(layer_path).convert("RGBA")
    w = round(canvas.width * scale)
    h = round(w * layer.height / layer.width)
    layer = layer.resize((w, h), Image.LANCZOS)
    x, y = _place(canvas.width, canvas.height, w, h, anchor, dx, dy)
    canvas.alpha_composite(layer, (x, y))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Composite bg + cutout + logo")
    p.add_argument("--bg", required=True, help="background image path")
    p.add_argument("--fg", help="foreground cutout PNG (transparent)")
    p.add_argument("--fg-anchor", default="bottom-right", choices=sorted(ANCHORS))
    p.add_argument("--fg-scale", type=float, default=0.95,
                   help="foreground width as fraction of canvas width")
    p.add_argument("--fg-x", type=int, default=0, help="x nudge (px)")
    p.add_argument("--fg-y", type=int, default=0, help="y nudge (px)")
    p.add_argument("--logo", help="optional logo PNG")
    p.add_argument("--logo-anchor", default="top-left", choices=sorted(ANCHORS))
    p.add_argument("--logo-scale", type=float, default=0.16)
    p.add_argument("--logo-x", type=int, default=24)
    p.add_argument("--logo-y", type=int, default=24)
    p.add_argument("--size", default="1280x720",
                   help="output WxH (cover-cropped); e.g. 1280x720, 1080x1080")
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)

    tw, th = (int(v) for v in args.size.lower().split("x"))
    canvas = _fit_cover(Image.open(args.bg).convert("RGBA"), tw, th)

    if args.fg:
        # fg is anchored and scaled relative to canvas WIDTH by default;
        # for a person you usually want it scaled to canvas HEIGHT instead.
        fg = Image.open(args.fg).convert("RGBA")
        h = round(canvas.height * args.fg_scale)
        w = round(h * fg.width / fg.height)
        fg = fg.resize((w, h), Image.LANCZOS)
        x, y = _place(canvas.width, canvas.height, w, h,
                      args.fg_anchor, args.fg_x, args.fg_y)
        canvas.alpha_composite(fg, (x, y))

    if args.logo:
        _overlay(canvas, args.logo, args.logo_anchor, args.logo_scale,
                 args.logo_x, args.logo_y)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out, quality=95)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

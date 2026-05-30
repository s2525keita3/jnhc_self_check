#!/usr/bin/env python3
"""gpt-image generation / editing CLI.

This is a thin, agent-friendly wrapper around the OpenAI Images API
(``images.generate`` / ``images.edit``). It is meant to be driven by an
agent (e.g. Codex) that crafts a high-quality prompt from the user's intent,
rather than called directly by a human with a terse prompt.

Usage:
    # text -> image
    python image_gen.py generate \
        --prompt "..." \
        --size landscape \
        --out out/thumb.png

    # image(+optional mask) -> edited image
    python image_gen.py edit \
        --image base.png \
        --prompt "..." \
        --mask mask.png \
        --out out/edited.png

Environment:
    OPENAI_API_KEY        required
    OPENAI_IMAGE_MODEL    optional, default "gpt-image-1"
                          (set to "gpt-image-2" etc. if available to you)
"""

from __future__ import annotations

import argparse
import base64
import datetime as _dt
import os
import sys
from pathlib import Path

DEFAULT_MODEL = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")

# Convenient aspect presets. gpt-image-1 supports these concrete sizes.
SIZE_PRESETS = {
    "square": "1024x1024",       # 1:1   icons, avatars
    "landscape": "1536x1024",    # 3:2   slides, YouTube thumbnails (16:9-ish)
    "portrait": "1024x1536",     # 2:3   stories, posters
    "auto": "auto",              # let the model decide
}


def _eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def _resolve_size(size: str) -> str:
    return SIZE_PRESETS.get(size, size)


def _default_out(prefix: str, ext: str) -> Path:
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = Path("out")
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{prefix}-{ts}.{ext}"


def _save_results(data, out: Path) -> list[Path]:
    """Decode b64 image payload(s) and write them to disk.

    gpt-image models always return base64 (no hosted URL). When more than one
    image is requested, files are suffixed with -1, -2, ...
    """
    saved: list[Path] = []
    n = len(data)
    for i, item in enumerate(data):
        b64 = getattr(item, "b64_json", None)
        if b64 is None:
            _eprint("warning: response item had no b64_json; skipping")
            continue
        raw = base64.b64decode(b64)
        if n == 1:
            target = out
        else:
            target = out.with_name(f"{out.stem}-{i + 1}{out.suffix}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        saved.append(target)
    return saved


def _client():
    try:
        from openai import OpenAI
    except ImportError:
        _eprint(
            "error: the 'openai' package is required.\n"
            "       install it with:  pip install -r requirements.txt"
        )
        raise SystemExit(2)
    if not os.environ.get("OPENAI_API_KEY"):
        _eprint("error: OPENAI_API_KEY is not set.")
        raise SystemExit(2)
    return OpenAI()


def cmd_generate(args: argparse.Namespace) -> int:
    client = _client()
    size = _resolve_size(args.size)
    out = Path(args.out) if args.out else _default_out("gen", args.format)

    kwargs = dict(
        model=args.model,
        prompt=args.prompt,
        size=size,
        n=args.n,
    )
    # These params are supported by gpt-image-* but not by older models.
    if args.quality:
        kwargs["quality"] = args.quality
    if args.background:
        kwargs["background"] = args.background
    if args.format:
        kwargs["output_format"] = args.format

    _eprint(f"[generate] model={args.model} size={size} n={args.n} -> {out}")
    result = client.images.generate(**kwargs)
    saved = _save_results(result.data, out)
    for p in saved:
        print(p)
    return 0 if saved else 1


def cmd_edit(args: argparse.Namespace) -> int:
    client = _client()
    size = _resolve_size(args.size)
    out = Path(args.out) if args.out else _default_out("edit", args.format)

    image_files = [open(p, "rb") for p in args.image]
    mask_file = open(args.mask, "rb") if args.mask else None
    try:
        kwargs = dict(
            model=args.model,
            image=image_files if len(image_files) > 1 else image_files[0],
            prompt=args.prompt,
            size=size,
            n=args.n,
        )
        if mask_file is not None:
            kwargs["mask"] = mask_file
        if args.quality:
            kwargs["quality"] = args.quality

        _eprint(
            f"[edit] model={args.model} size={size} "
            f"images={args.image} mask={args.mask} -> {out}"
        )
        result = client.images.edit(**kwargs)
    finally:
        for f in image_files:
            f.close()
        if mask_file is not None:
            mask_file.close()

    saved = _save_results(result.data, out)
    for p in saved:
        print(p)
    return 0 if saved else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="gpt-image generation / editing CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"image model (default: {DEFAULT_MODEL}; "
        "override via OPENAI_IMAGE_MODEL)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    size_help = (
        "size preset (square|landscape|portrait|auto) or an explicit "
        "WxH like 1024x1024"
    )

    g = sub.add_parser("generate", help="text -> image")
    g.add_argument("--prompt", required=True, help="full image description")
    g.add_argument("--size", default="square", help=size_help)
    g.add_argument(
        "--quality",
        choices=["low", "medium", "high", "auto"],
        default="high",
        help="render quality (default: high)",
    )
    g.add_argument(
        "--background",
        choices=["transparent", "opaque", "auto"],
        help="background handling (transparent needs png/webp)",
    )
    g.add_argument(
        "--format",
        choices=["png", "jpeg", "webp"],
        default="png",
        help="output file format (default: png)",
    )
    g.add_argument("--n", type=int, default=1, help="number of images")
    g.add_argument("--out", help="output path (default: out/gen-<ts>.<fmt>)")
    g.set_defaults(func=cmd_generate)

    e = sub.add_parser("edit", help="image(+mask) -> image")
    e.add_argument(
        "--image",
        required=True,
        nargs="+",
        help="one or more input image paths (first is the base)",
    )
    e.add_argument("--prompt", required=True, help="what to change / produce")
    e.add_argument(
        "--mask",
        help="optional PNG mask; transparent areas are the regions to edit",
    )
    e.add_argument("--size", default="auto", help=size_help)
    e.add_argument(
        "--quality",
        choices=["low", "medium", "high", "auto"],
        default="high",
        help="render quality (default: high)",
    )
    e.add_argument(
        "--format",
        choices=["png", "jpeg", "webp"],
        default="png",
        help="output file format for the default filename (default: png)",
    )
    e.add_argument("--n", type=int, default=1, help="number of images")
    e.add_argument("--out", help="output path (default: out/edit-<ts>.<fmt>)")
    e.set_defaults(func=cmd_edit)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

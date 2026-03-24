#!/usr/bin/env python3
"""MKV Turbo Beta 1 Python CLI.

Python-first beta client:
1) upload file to VDS via SCP,
2) run remote ffmpeg with settings from CLI args,
3) download result back.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class EncodeConfig:
    video_codec: str = "libx265"
    crf: int = 22
    preset: str = "medium"
    pix_fmt: str = "yuv420p"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    audio_maps: list[str] = field(default_factory=lambda: ["0:a?"])
    subtitle_maps: list[str] = field(default_factory=list)
    video_map: str = "0:v:0"
    container: str = "mkv"
    extra_ffmpeg: list[str] = field(default_factory=list)


def split_maps(value: str) -> list[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def run(command: list[str], dry_run: bool = False) -> None:
    printable = " ".join(shlex.quote(x) for x in command)
    print(f"$ {printable}")
    if dry_run:
        return

    proc = subprocess.run(command, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {printable}")


def make_ffmpeg_command(src: str, dst: str, cfg: EncodeConfig) -> str:
    parts: list[str] = [
        "ffmpeg",
        "-y",
        "-threads",
        "0",
        "-i",
        src,
        "-map",
        cfg.video_map,
    ]

    for m in cfg.audio_maps:
        parts += ["-map", m]

    for m in cfg.subtitle_maps:
        parts += ["-map", m]

    parts += [
        "-c:v",
        cfg.video_codec,
        "-preset",
        cfg.preset,
        "-crf",
        str(cfg.crf),
        "-pix_fmt",
        cfg.pix_fmt,
        "-c:a",
        cfg.audio_codec,
        "-b:a",
        cfg.audio_bitrate,
    ]

    parts += cfg.extra_ffmpeg
    parts += [dst]

    return " ".join(shlex.quote(x) for x in parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MKV Turbo Python Beta client")
    parser.add_argument("input", type=Path, help="Path to input .mkv")
    parser.add_argument("--host", required=True, help="VDS host")
    parser.add_argument("--user", required=True, help="SSH user")
    parser.add_argument("--port", type=int, default=22, help="SSH port")
    parser.add_argument("--remote-base", default="~/mkv_jobs", help="Remote base directory")
    parser.add_argument("--output-dir", type=Path, default=Path("./out"), help="Local output directory")
    parser.add_argument("--dry-run", action="store_true", help="Print commands only")

    parser.add_argument("--video-codec", default="libx265")
    parser.add_argument("--crf", type=int, default=22)
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--pix-fmt", default="yuv420p")
    parser.add_argument("--audio-codec", default="aac")
    parser.add_argument("--audio-bitrate", default="192k")
    parser.add_argument("--video-map", default="0:v:0", help="ffmpeg map for video stream")
    parser.add_argument("--audio-maps", default="0:a?", help="comma-separated ffmpeg audio maps")
    parser.add_argument("--subtitle-maps", default="", help="comma-separated ffmpeg subtitle maps")
    parser.add_argument("--container", default="mkv")
    parser.add_argument("--extra-ffmpeg", action="append", default=[], help="extra ffmpeg arg(s), can be repeated")

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.input.exists():
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 2
    if args.input.suffix.lower() != ".mkv":
        print("Input file must be .mkv", file=sys.stderr)
        return 2

    cfg = EncodeConfig(
        video_codec=args.video_codec,
        crf=args.crf,
        preset=args.preset,
        pix_fmt=args.pix_fmt,
        audio_codec=args.audio_codec,
        audio_bitrate=args.audio_bitrate,
        audio_maps=split_maps(args.audio_maps),
        subtitle_maps=split_maps(args.subtitle_maps),
        video_map=args.video_map,
        container=args.container,
        extra_ffmpeg=args.extra_ffmpeg,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    job_id = datetime.now(timezone.utc).strftime("job_%Y%m%dT%H%M%SZ")
    remote_dir = f"{args.remote_base.rstrip('/')}/{job_id}"
    remote_input = f"{remote_dir}/{args.input.name}"
    output_name = f"{args.input.stem}.pybeta1.{cfg.container}"
    remote_output = f"{remote_dir}/{output_name}"
    local_output = args.output_dir / output_name

    ssh_base = ["ssh", "-p", str(args.port), f"{args.user}@{args.host}"]

    try:
        run(ssh_base + [f"mkdir -p {shlex.quote(remote_dir)}"], dry_run=args.dry_run)
        run(["scp", "-P", str(args.port), str(args.input), f"{args.user}@{args.host}:{remote_input}"], dry_run=args.dry_run)

        ffmpeg = make_ffmpeg_command(remote_input, remote_output, cfg)
        run(ssh_base + [ffmpeg], dry_run=args.dry_run)

        run(["scp", "-P", str(args.port), f"{args.user}@{args.host}:{remote_output}", str(local_output)], dry_run=args.dry_run)
    except RuntimeError as err:
        print(str(err), file=sys.stderr)
        return 1

    print(f"Done: {local_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

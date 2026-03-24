#!/usr/bin/env python3
"""MKV Turbo Beta 1 Python CLI."""

from __future__ import annotations

import argparse
import json
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


def probe_stream_maps(input_file: Path) -> tuple[str, list[str], list[str]]:
    cmd = ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", str(input_file)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)

    video_map = "0:v:0"
    audio_maps: list[str] = []
    subtitle_maps: list[str] = []

    for s in data.get("streams", []):
        idx = s.get("index")
        stype = s.get("codec_type")
        if idx is None or stype is None:
            continue
        m = f"0:{idx}"
        if stype == "video" and video_map == "0:v:0":
            video_map = m
        elif stype == "audio":
            audio_maps.append(m)
        elif stype == "subtitle":
            subtitle_maps.append(m)

    if not audio_maps:
        audio_maps = ["0:a?"]

    return video_map, audio_maps, subtitle_maps


def run(command: list[str], dry_run: bool = False) -> None:
    printable = " ".join(shlex.quote(x) for x in command)
    print(f"$ {printable}")
    if dry_run:
        return
    proc = subprocess.run(command, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {printable}")


def make_ffmpeg_command(src: str, dst: str, cfg: EncodeConfig) -> str:
    parts: list[str] = ["ffmpeg", "-y", "-threads", "0", "-i", src, "-map", cfg.video_map]
    for m in cfg.audio_maps:
        parts += ["-map", m]
    for m in cfg.subtitle_maps:
        parts += ["-map", m]
    parts += [
        "-c:v", cfg.video_codec,
        "-preset", cfg.preset,
        "-crf", str(cfg.crf),
        "-pix_fmt", cfg.pix_fmt,
        "-c:a", cfg.audio_codec,
        "-b:a", cfg.audio_bitrate,
    ]
    parts += cfg.extra_ffmpeg
    parts += [dst]
    return " ".join(shlex.quote(x) for x in parts)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="MKV Turbo Python Beta client")
    p.add_argument("input", type=Path, help="Path to input .mkv")
    p.add_argument("--host", required=False)
    p.add_argument("--user", required=False)
    p.add_argument("--port", type=int, default=22)
    p.add_argument("--ssh-key", default="", help="Path to SSH private key")
    p.add_argument("--ssh-option", action="append", default=[], help="Extra -o option for ssh/scp")
    p.add_argument("--remote-base", default="~/mkv_jobs")
    p.add_argument("--output-dir", type=Path, default=Path("./out"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--analyze-only", action="store_true")
    p.add_argument("--auto-map-from-ffprobe", action="store_true")

    p.add_argument("--video-codec", default="libx265")
    p.add_argument("--crf", type=int, default=22)
    p.add_argument("--preset", default="medium")
    p.add_argument("--pix-fmt", default="yuv420p")
    p.add_argument("--audio-codec", default="aac")
    p.add_argument("--audio-bitrate", default="192k")
    p.add_argument("--video-map", default="0:v:0")
    p.add_argument("--audio-maps", default="0:a?")
    p.add_argument("--subtitle-maps", default="")
    p.add_argument("--container", default="mkv")
    p.add_argument("--extra-ffmpeg", action="append", default=[])
    return p.parse_args()


def build_ssh_common(args: argparse.Namespace) -> list[str]:
    common: list[str] = []
    if args.ssh_key:
        common += ["-i", args.ssh_key]
    for opt in args.ssh_option:
        common += ["-o", opt]
    return common


def main() -> int:
    args = parse_args()
    if not args.input.exists():
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 2
    if args.input.suffix.lower() != ".mkv":
        print("Input file must be .mkv", file=sys.stderr)
        return 2

    if args.analyze_only or args.auto_map_from_ffprobe:
        try:
            v, a, s = probe_stream_maps(args.input)
            print("ffprobe analysis:")
            print(f"  video_map={v}")
            print(f"  audio_maps={','.join(a)}")
            print(f"  subtitle_maps={','.join(s) if s else '(none)'}")
        except Exception as exc:
            print(f"ffprobe analysis failed: {exc}", file=sys.stderr)
            return 1
        if args.analyze_only:
            return 0
        args.video_map = v
        args.audio_maps = ",".join(a)
        args.subtitle_maps = ",".join(s)

    if not args.host or not args.user:
        print("--host and --user are required unless --analyze-only is used", file=sys.stderr)
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

    login = f"{args.user}@{args.host}"
    ssh_common = build_ssh_common(args)
    ssh_base = ["ssh", "-p", str(args.port)] + ssh_common + [login]
    scp_base = ["scp", "-P", str(args.port)] + ssh_common

    try:
        run(ssh_base + [f"mkdir -p {shlex.quote(remote_dir)}"], dry_run=args.dry_run)
        run(scp_base + [str(args.input), f"{login}:{remote_input}"], dry_run=args.dry_run)
        ffmpeg = make_ffmpeg_command(remote_input, remote_output, cfg)
        run(ssh_base + [ffmpeg], dry_run=args.dry_run)
        run(scp_base + [f"{login}:{remote_output}", str(local_output)], dry_run=args.dry_run)
    except RuntimeError as err:
        print(str(err), file=sys.stderr)
        return 1

    print(f"Done: {local_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

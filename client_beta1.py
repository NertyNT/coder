#!/usr/bin/env python3
"""Beta 1 CLI client for MKV Turbo Pipeline.

Flow:
1) Upload MKV from local machine to Ubuntu VDS via SCP
2) Run ffmpeg on VDS with a JSON profile
3) Download encoded file back to local machine
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Profile:
    video_codec: str = "libx265"
    crf: int = 22
    preset: str = "medium"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    container: str = "mkv"

    @classmethod
    def load(cls, path: Path) -> "Profile":
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            video_codec=raw.get("video_codec", cls.video_codec),
            crf=int(raw.get("crf", cls.crf)),
            preset=raw.get("preset", cls.preset),
            audio_codec=raw.get("audio_codec", cls.audio_codec),
            audio_bitrate=raw.get("audio_bitrate", cls.audio_bitrate),
            container=raw.get("container", cls.container),
        )


def run(command: list[str], dry_run: bool = False) -> None:
    printable = " ".join(shlex.quote(x) for x in command)
    print(f"$ {printable}")
    if dry_run:
        return

    result = subprocess.run(command, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {printable}")


def make_ffmpeg_command(src: str, dst: str, profile: Profile) -> str:
    parts = [
        "ffmpeg",
        "-y",
        "-threads",
        "0",
        "-i",
        src,
        "-map",
        "0",
        "-c:v",
        profile.video_codec,
        "-preset",
        profile.preset,
        "-crf",
        str(profile.crf),
        "-c:a",
        profile.audio_codec,
        "-b:a",
        profile.audio_bitrate,
        dst,
    ]
    return " ".join(shlex.quote(x) for x in parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MKV Turbo Beta 1 client")
    parser.add_argument("input", type=Path, help="Path to input .mkv")
    parser.add_argument("--host", required=True, help="VDS host")
    parser.add_argument("--user", required=True, help="SSH user")
    parser.add_argument("--port", type=int, default=22, help="SSH port")
    parser.add_argument("--profile", type=Path, required=True, help="Path to JSON profile")
    parser.add_argument("--remote-base", default="~/mkv_jobs", help="Remote base directory")
    parser.add_argument("--output-dir", type=Path, default=Path("./out"), help="Local output directory")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without execution")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.input.exists():
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 2
    if args.input.suffix.lower() != ".mkv":
        print("Input file must be .mkv", file=sys.stderr)
        return 2
    if not args.profile.exists():
        print(f"Profile not found: {args.profile}", file=sys.stderr)
        return 2

    profile = Profile.load(args.profile)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    job_id = datetime.now(timezone.utc).strftime("job_%Y%m%dT%H%M%SZ")
    remote_dir = f"{args.remote_base.rstrip('/')}/{job_id}"
    remote_input = f"{remote_dir}/{args.input.name}"
    output_name = f"{args.input.stem}.beta1.{profile.container}"
    remote_output = f"{remote_dir}/{output_name}"
    local_output = args.output_dir / output_name

    ssh_base = ["ssh", "-p", str(args.port), f"{args.user}@{args.host}"]

    try:
        run(ssh_base + [f"mkdir -p {shlex.quote(remote_dir)}"], dry_run=args.dry_run)
        run(["scp", "-P", str(args.port), str(args.input), f"{args.user}@{args.host}:{remote_input}"], dry_run=args.dry_run)

        ffmpeg = make_ffmpeg_command(remote_input, remote_output, profile)
        run(ssh_base + [ffmpeg], dry_run=args.dry_run)

        run(["scp", "-P", str(args.port), f"{args.user}@{args.host}:{remote_output}", str(local_output)], dry_run=args.dry_run)
    except RuntimeError as err:
        print(str(err), file=sys.stderr)
        return 1

    print(f"Done: {local_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

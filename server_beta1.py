#!/usr/bin/env python3
"""MKV Turbo Server Beta 1 (Python/FastAPI).

Simple server endpoints for probing and encoding on Ubuntu VDS.
"""

from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="MKV Turbo Server Beta 1", version="0.1.0-beta")


class ProbeRequest(BaseModel):
    input_path: str


class EncodeRequest(BaseModel):
    input_path: str
    output_path: Optional[str] = None
    video_codec: str = "libx265"
    crf: int = 22
    preset: str = "medium"
    pix_fmt: str = "yuv420p"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    video_map: str = "0:v:0"
    audio_maps: List[str] = Field(default_factory=lambda: ["0:a?"])
    subtitle_maps: List[str] = Field(default_factory=list)
    extra_ffmpeg: List[str] = Field(default_factory=list)


def ffprobe_maps(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(str(path))

    cmd = ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", str(path)]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    data = json.loads(out)

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

    return {
        "video_map": video_map,
        "audio_maps": audio_maps,
        "subtitle_maps": subtitle_maps,
        "streams_count": len(data.get("streams", [])),
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/probe")
def probe(payload: ProbeRequest) -> dict:
    try:
        return ffprobe_maps(Path(payload.input_path))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="input file not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"probe failed: {exc}")


@app.post("/encode")
def encode(payload: EncodeRequest) -> dict:
    in_path = Path(payload.input_path)
    if not in_path.exists():
        raise HTTPException(status_code=404, detail="input file not found")

    out_path = Path(payload.output_path) if payload.output_path else in_path.with_name(f"{in_path.stem}.serverbeta.mkv")

    cmd = [
        "ffmpeg",
        "-y",
        "-threads",
        "0",
        "-i",
        str(in_path),
        "-map",
        payload.video_map,
    ]

    for m in payload.audio_maps:
        cmd += ["-map", m]
    for m in payload.subtitle_maps:
        cmd += ["-map", m]

    cmd += [
        "-c:v",
        payload.video_codec,
        "-preset",
        payload.preset,
        "-crf",
        str(payload.crf),
        "-pix_fmt",
        payload.pix_fmt,
        "-c:a",
        payload.audio_codec,
        "-b:a",
        payload.audio_bitrate,
    ]
    cmd += payload.extra_ffmpeg
    cmd += [str(out_path)]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"encode execution error: {exc}")

    return {
        "ok": proc.returncode == 0,
        "return_code": proc.returncode,
        "output_path": str(out_path),
        "command": " ".join(shlex.quote(x) for x in cmd),
        "stdout_tail": "\n".join(proc.stdout.splitlines()[-40:]),
        "stderr_tail": "\n".join(proc.stderr.splitlines()[-40:]),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server_beta1:app", host="0.0.0.0", port=8080)

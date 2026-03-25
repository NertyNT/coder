#!/usr/bin/env python3
"""Auto-installer and launcher for MKV Turbo client (Windows/Linux)."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(cmd: list[str]) -> bool:
    print("$", " ".join(cmd))
    return subprocess.run(cmd).returncode == 0


def ensure_python_deps() -> None:
    req = ROOT / "requirements.txt"
    if req.exists():
        run([sys.executable, "-m", "pip", "install", "-r", str(req)])


def ensure_windows_system_deps() -> None:
    if platform.system().lower() != "windows":
        return

    if shutil.which("ssh") is None or shutil.which("scp") is None:
        run(["powershell", "-NoProfile", "-Command", "Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0"])
    if shutil.which("ffprobe") is None:
        run(["winget", "install", "-e", "--id", "Gyan.FFmpeg"])


def main() -> int:
    ensure_python_deps()
    ensure_windows_system_deps()
    client = ROOT / "client_gui_beta1.py"
    return subprocess.run([sys.executable, str(client)]).returncode


if __name__ == "__main__":
    raise SystemExit(main())

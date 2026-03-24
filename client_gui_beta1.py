#!/usr/bin/env python3
"""Modern Python GUI client with queue and full ffmpeg settings."""

from __future__ import annotations

import json
import queue
import subprocess
import threading
import shutil
from dataclasses import dataclass
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import customtkinter as ctk
except Exception:
    ctk = None


@dataclass
class QueueJob:
    input_path: str
    host: str
    user: str
    port: str
    ssh_key: str
    ssh_options: str
    remote_base: str
    output_dir: str
    video_codec: str
    crf: str
    preset: str
    pix_fmt: str
    audio_codec: str
    audio_bitrate: str
    video_map: str
    audio_maps: str
    subtitle_maps: str
    container: str
    extra_ffmpeg: str
    auto_map_from_probe: bool


class App:
    def __init__(self) -> None:
        if ctk is None:
            raise RuntimeError("customtkinter is not installed. Run: pip install customtkinter")

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("MKV Turbo Python Beta GUI")
        self.root.geometry("1120x780")

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.jobs: list[QueueJob] = []
        self.queue_running = False

        self.input_path = tk.StringVar()
        self.output_dir = tk.StringVar(value=str(Path("out").resolve()))
        self.host = tk.StringVar()
        self.user = tk.StringVar()
        self.port = tk.StringVar(value="22")
        self.remote_base = tk.StringVar(value="~/mkv_jobs")
        self.ssh_key = tk.StringVar(value="")
        self.ssh_options = tk.StringVar(value="ServerAliveInterval=30,ServerAliveCountMax=6")

        self.video_codec = tk.StringVar(value="libx265")
        self.crf = tk.StringVar(value="22")
        self.preset = tk.StringVar(value="medium")
        self.pix_fmt = tk.StringVar(value="yuv420p")
        self.audio_codec = tk.StringVar(value="aac")
        self.audio_bitrate = tk.StringVar(value="192k")
        self.video_map = tk.StringVar(value="0:v:0")
        self.audio_maps = tk.StringVar(value="0:a?")
        self.subtitle_maps = tk.StringVar(value="")
        self.container = tk.StringVar(value="mkv")
        self.extra_ffmpeg = tk.StringVar(value="")
        self.auto_map_from_probe = tk.BooleanVar(value=True)

        self._build_ui()
        self._poll_logs()

    def _build_ui(self) -> None:
        wrap = ctk.CTkFrame(self.root, corner_radius=12)
        wrap.pack(fill="both", expand=True, padx=14, pady=14)

        ctk.CTkLabel(wrap, text="MKV Turbo • Python Beta", font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w", padx=16, pady=(12, 4))
        ctk.CTkLabel(wrap, text="Очередь задач + ffprobe авто-анализ + полные ffmpeg настройки", text_color=("#888", "#bbb")).pack(anchor="w", padx=16, pady=(0, 10))

        tabs = ctk.CTkTabview(wrap)
        tabs.pack(fill="both", expand=True, padx=14, pady=10)

        t_job = tabs.add("Задача")
        t_ff = tabs.add("FFmpeg")
        t_queue = tabs.add("Очередь")
        t_logs = tabs.add("Логи")

        self._build_job_tab(t_job)
        self._build_ffmpeg_tab(t_ff)
        self._build_queue_tab(t_queue)
        self._build_logs_tab(t_logs)


    def _missing_bins(self, names: list[str]) -> list[str]:
        return [n for n in names if shutil.which(n) is None]

    def _build_job_tab(self, tab) -> None:
        frm = ctk.CTkFrame(tab)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        self._path_row(frm, "MKV файл", self.input_path, self._pick_input, 0)
        self._path_row(frm, "Папка результата", self.output_dir, self._pick_output, 1)
        self._entry_row(frm, "Host", self.host, 2)
        self._entry_row(frm, "User", self.user, 3)
        self._entry_row(frm, "Port", self.port, 4)
        self._entry_row(frm, "Remote base", self.remote_base, 5)
        self._path_row(frm, "SSH key (private)", self.ssh_key, self._pick_ssh_key, 6)
        self._entry_row(frm, "SSH options (csv)", self.ssh_options, 7)

        btns = ctk.CTkFrame(frm, fg_color="transparent")
        btns.grid(row=8, column=0, columnspan=3, sticky="w", padx=12, pady=14)
        ctk.CTkButton(btns, text="Анализировать ffprobe", command=self.analyze_local_file).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btns, text="Проверить SSH", command=self.test_connection).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btns, text="Добавить в очередь", command=self.add_to_queue, fg_color="#2563eb", hover_color="#1d4ed8").pack(side="left", padx=(0, 8))
        ctk.CTkButton(btns, text="Старт очереди", command=self.start_queue).pack(side="left")

    def _build_ffmpeg_tab(self, tab) -> None:
        frm = ctk.CTkFrame(tab)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        self._entry_row(frm, "Video codec", self.video_codec, 0)
        self._entry_row(frm, "CRF", self.crf, 1)
        self._entry_row(frm, "Preset", self.preset, 2)
        self._entry_row(frm, "Pixel format", self.pix_fmt, 3)
        self._entry_row(frm, "Audio codec", self.audio_codec, 4)
        self._entry_row(frm, "Audio bitrate", self.audio_bitrate, 5)
        self._entry_row(frm, "Video map", self.video_map, 6)
        self._entry_row(frm, "Audio maps (csv)", self.audio_maps, 7)
        self._entry_row(frm, "Subtitle maps (csv)", self.subtitle_maps, 8)
        self._entry_row(frm, "Container", self.container, 9)
        self._entry_row(frm, "Extra ffmpeg args", self.extra_ffmpeg, 10)

        ctk.CTkCheckBox(frm, text="Авто-подстановка map из ffprobe перед запуском", variable=self.auto_map_from_probe).grid(row=11, column=0, columnspan=2, sticky="w", padx=12, pady=(4, 8))
        info = "Пример extra args: -movflags +faststart -max_muxing_queue_size 4096"
        ctk.CTkLabel(frm, text=info, text_color=("#777", "#aaa")).grid(row=12, column=0, columnspan=3, sticky="w", padx=12, pady=(8, 8))

    def _build_queue_tab(self, tab) -> None:
        frm = ctk.CTkFrame(tab)
        frm.pack(fill="both", expand=True, padx=10, pady=10)
        self.queue_list = tk.Listbox(frm, height=18)
        self.queue_list.pack(fill="both", expand=True, padx=10, pady=10)

        btns = ctk.CTkFrame(frm, fg_color="transparent")
        btns.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(btns, text="Удалить выбранное", command=self.remove_selected_job).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btns, text="Очистить очередь", command=self.clear_queue).pack(side="left")

    def _build_logs_tab(self, tab) -> None:
        frm = ctk.CTkFrame(tab)
        frm.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_box = ctk.CTkTextbox(frm, wrap="word")
        self.log_box.pack(fill="both", expand=True, padx=8, pady=8)

    def _entry_row(self, parent, label: str, var: tk.StringVar, row: int) -> None:
        ctk.CTkLabel(parent, text=label, width=220, anchor="w").grid(row=row, column=0, sticky="w", padx=12, pady=8)
        ctk.CTkEntry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", padx=12, pady=8)
        parent.grid_columnconfigure(1, weight=1)

    def _path_row(self, parent, label: str, var: tk.StringVar, callback, row: int) -> None:
        ctk.CTkLabel(parent, text=label, width=220, anchor="w").grid(row=row, column=0, sticky="w", padx=12, pady=8)
        ctk.CTkEntry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", padx=12, pady=8)
        ctk.CTkButton(parent, text="Выбрать", width=100, command=callback).grid(row=row, column=2, padx=10, pady=8)
        parent.grid_columnconfigure(1, weight=1)

    def _pick_input(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("MKV", "*.mkv"), ("All", "*.*")])
        if path:
            self.input_path.set(path)

    def _pick_output(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.output_dir.set(path)

    def _pick_ssh_key(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("PEM/KEY", "*.pem *.key"), ("All", "*.*")])
        if path:
            self.ssh_key.set(path)

    def analyze_local_file(self) -> None:
        src = self.input_path.get().strip()
        if not src:
            messagebox.showwarning("Нет файла", "Выбери локальный MKV файл")
            return

        cmd = ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", src]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
            data = json.loads(out)
        except Exception as exc:
            messagebox.showerror("ffprobe", f"Ошибка анализа: {exc}")
            return

        video = "0:v:0"
        audios: list[str] = []
        subs: list[str] = []
        for s in data.get("streams", []):
            idx = s.get("index")
            stype = s.get("codec_type")
            if idx is None or stype is None:
                continue
            m = f"0:{idx}"
            if stype == "video" and video == "0:v:0":
                video = m
            elif stype == "audio":
                audios.append(m)
            elif stype == "subtitle":
                subs.append(m)

        self.video_map.set(video)
        self.audio_maps.set(",".join(audios) if audios else "0:a?")
        self.subtitle_maps.set(",".join(subs))
        self.log_queue.put(f"[FFPROBE] maps: video={video}, audio={self.audio_maps.get()}, subs={self.subtitle_maps.get() or '(none)'}\n")

    def _build_job_from_form(self) -> QueueJob:
        return QueueJob(
            input_path=self.input_path.get().strip(),
            host=self.host.get().strip(),
            user=self.user.get().strip(),
            port=self.port.get().strip(),
            remote_base=self.remote_base.get().strip(),
            ssh_key=self.ssh_key.get().strip(),
            ssh_options=self.ssh_options.get().strip(),
            output_dir=self.output_dir.get().strip(),
            video_codec=self.video_codec.get().strip(),
            crf=self.crf.get().strip(),
            preset=self.preset.get().strip(),
            pix_fmt=self.pix_fmt.get().strip(),
            audio_codec=self.audio_codec.get().strip(),
            audio_bitrate=self.audio_bitrate.get().strip(),
            video_map=self.video_map.get().strip(),
            audio_maps=self.audio_maps.get().strip(),
            subtitle_maps=self.subtitle_maps.get().strip(),
            container=self.container.get().strip(),
            extra_ffmpeg=self.extra_ffmpeg.get().strip(),
            auto_map_from_probe=self.auto_map_from_probe.get(),
        )

    def add_to_queue(self) -> None:
        job = self._build_job_from_form()
        if not job.input_path or not job.host or not job.user:
            messagebox.showerror("Ошибка", "Нужны минимум: MKV, Host, User")
            return

        self.jobs.append(job)
        self.queue_list.insert("end", f"{Path(job.input_path).name} -> {job.host} ({job.video_codec}, crf={job.crf})")
        self.log_queue.put(f"[QUEUE] added: {job.input_path}\n")

    def remove_selected_job(self) -> None:
        selected = self.queue_list.curselection()
        if not selected:
            return
        idx = selected[0]
        self.queue_list.delete(idx)
        self.jobs.pop(idx)

    def clear_queue(self) -> None:
        self.jobs.clear()
        self.queue_list.delete(0, "end")

    def test_connection(self) -> None:
        missing = self._missing_bins(["ssh"])
        if missing:
            messagebox.showerror("Missing binary", f"Not found in PATH: {', '.join(missing)}\nInstall OpenSSH Client on Windows.")
            return

        cmd = ["ssh", "-p", self.port.get().strip()]
        if self.ssh_key.get().strip():
            cmd += ["-i", self.ssh_key.get().strip()]
        for opt in [x.strip() for x in self.ssh_options.get().split(",") if x.strip()]:
            cmd += ["-o", opt]
        cmd += [f"{self.user.get().strip()}@{self.host.get().strip()}", "echo", "OK"]
        self._run_and_log(cmd, "SSH check")

    def start_queue(self) -> None:
        missing = self._missing_bins(["ssh", "scp", "ffprobe"])
        if missing:
            messagebox.showerror("Missing binaries", f"Not found in PATH: {', '.join(missing)}")
            return

        if self.queue_running:
            messagebox.showinfo("Инфо", "Очередь уже выполняется")
            return
        if not self.jobs:
            messagebox.showwarning("Пусто", "Очередь пустая")
            return

        self.queue_running = True
        threading.Thread(target=self._queue_worker, daemon=True).start()

    def _queue_worker(self) -> None:
        while self.jobs:
            job = self.jobs.pop(0)
            self.queue_list.delete(0)
            cmd = self._job_to_cli(job)
            ok = self._run_and_log(cmd, f"JOB {Path(job.input_path).name}")
            if not ok:
                self.log_queue.put("[QUEUE] stopped because of failure\n")
                break
        self.queue_running = False
        self.log_queue.put("[QUEUE] done\n")

    def _job_to_cli(self, job: QueueJob) -> list[str]:
        cli_script = str(Path(__file__).with_name("client_beta1.py"))
        cmd = [
            sys.executable,
            cli_script,
            job.input_path,
            "--host",
            job.host,
            "--user",
            job.user,
            "--port",
            job.port,
            "--remote-base",
            job.remote_base,
            "--ssh-key",
            job.ssh_key,
            "--output-dir",
            job.output_dir,
            "--video-codec",
            job.video_codec,
            "--crf",
            job.crf,
            "--preset",
            job.preset,
            "--pix-fmt",
            job.pix_fmt,
            "--audio-codec",
            job.audio_codec,
            "--audio-bitrate",
            job.audio_bitrate,
            "--video-map",
            job.video_map,
            "--audio-maps",
            job.audio_maps,
            "--subtitle-maps",
            job.subtitle_maps,
            "--container",
            job.container,
        ]

        for opt in [x.strip() for x in job.ssh_options.split(",") if x.strip()]:
            cmd += ["--ssh-option", opt]

        if job.auto_map_from_probe:
            cmd += ["--auto-map-from-ffprobe"]

        if job.extra_ffmpeg:
            for token in job.extra_ffmpeg.split():
                cmd += ["--extra-ffmpeg", token]
        return cmd

    def _run_and_log(self, cmd: list[str], title: str) -> bool:
        self.log_queue.put(f"\n--- {title} ---\n$ {' '.join(cmd)}\n")
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        except FileNotFoundError as exc:
            self.log_queue.put(f"❌ {title} failed: {exc}.\n")
            self.log_queue.put("Install missing tools (ssh/scp/ffmpeg) and restart app.\n")
            return False

        assert proc.stdout is not None
        for line in proc.stdout:
            self.log_queue.put(line)
        code = proc.wait()
        self.log_queue.put(("✅" if code == 0 else "❌") + f" {title} finished (code={code})\n")
        return code == 0

    def _poll_logs(self) -> None:
        while not self.log_queue.empty():
            self.log_box.insert("end", self.log_queue.get())
            self.log_box.see("end")
        self.root.after(150, self._poll_logs)

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    try:
        app = App()
    except RuntimeError as err:
        print(err)
        return 1
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

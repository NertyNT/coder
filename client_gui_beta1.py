#!/usr/bin/env python3
"""Modern GUI client (Beta 1) for MKV Turbo Pipeline."""

from __future__ import annotations

import queue
import subprocess
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import customtkinter as ctk
except Exception:  # fallback is handled in runtime messaging
    ctk = None


class App:
    def __init__(self) -> None:
        if ctk is None:
            raise RuntimeError(
                "customtkinter is not installed. Run: pip install customtkinter"
            )

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("MKV Turbo Client • Beta 1 GUI")
        self.root.geometry("980x700")

        self.log_queue: queue.Queue[str] = queue.Queue()

        self.input_path = tk.StringVar()
        self.profile_path = tk.StringVar(value=str(Path("profile.beta1.json").resolve()))
        self.output_dir = tk.StringVar(value=str(Path("out").resolve()))
        self.host = tk.StringVar()
        self.user = tk.StringVar()
        self.port = tk.StringVar(value="22")
        self.remote_base = tk.StringVar(value="~/mkv_jobs")

        self._build_ui()
        self._poll_logs()

    def _build_ui(self) -> None:
        container = ctk.CTkFrame(self.root, corner_radius=14)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        title = ctk.CTkLabel(
            container,
            text="MKV Turbo • Beta 1",
            font=ctk.CTkFont(size=28, weight="bold"),
        )
        title.pack(anchor="w", padx=16, pady=(14, 6))

        subtitle = ctk.CTkLabel(
            container,
            text="Windows → VDS Ubuntu → ffmpeg → auto download",
            text_color=("#999999", "#BBBBBB"),
        )
        subtitle.pack(anchor="w", padx=16, pady=(0, 12))

        tabs = ctk.CTkTabview(container, corner_radius=12)
        tabs.pack(fill="both", expand=True, padx=16, pady=12)

        tab_job = tabs.add("Задача")
        tab_server = tabs.add("Сервер")
        tab_logs = tabs.add("Логи")

        self._build_job_tab(tab_job)
        self._build_server_tab(tab_server)
        self._build_logs_tab(tab_logs)

    def _build_job_tab(self, tab: ctk.CTkFrame) -> None:
        form = ctk.CTkFrame(tab)
        form.pack(fill="both", expand=True, padx=12, pady=12)

        self._path_row(form, "MKV файл", self.input_path, self._pick_input, row=0)
        self._path_row(form, "Профиль JSON", self.profile_path, self._pick_profile, row=1)
        self._path_row(form, "Папка результата", self.output_dir, self._pick_output, row=2)

        button_row = ctk.CTkFrame(form, fg_color="transparent")
        button_row.grid(row=3, column=0, columnspan=3, sticky="ew", padx=12, pady=20)

        test_btn = ctk.CTkButton(button_row, text="Проверить SSH", command=self.test_connection)
        test_btn.pack(side="left", padx=(0, 10))

        run_btn = ctk.CTkButton(
            button_row,
            text="Старт кодирования",
            command=self.start_job,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(weight="bold"),
        )
        run_btn.pack(side="left")

        note = ctk.CTkLabel(
            form,
            text="Совет: сначала нажми 'Проверить SSH', потом 'Старт кодирования'.",
            text_color=("#666666", "#AAAAAA"),
        )
        note.grid(row=4, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 10))

    def _build_server_tab(self, tab: ctk.CTkFrame) -> None:
        frm = ctk.CTkFrame(tab)
        frm.pack(fill="both", expand=True, padx=12, pady=12)

        self._entry_row(frm, "Host", self.host, 0)
        self._entry_row(frm, "User", self.user, 1)
        self._entry_row(frm, "Port", self.port, 2)
        self._entry_row(frm, "Remote base", self.remote_base, 3)

    def _build_logs_tab(self, tab: ctk.CTkFrame) -> None:
        frm = ctk.CTkFrame(tab)
        frm.pack(fill="both", expand=True, padx=12, pady=12)

        self.log_box = ctk.CTkTextbox(frm, wrap="word", corner_radius=10)
        self.log_box.pack(fill="both", expand=True, padx=8, pady=8)

    def _entry_row(self, parent: ctk.CTkFrame, label: str, var: tk.StringVar, row: int) -> None:
        ctk.CTkLabel(parent, text=label, width=140, anchor="w").grid(row=row, column=0, padx=12, pady=10, sticky="w")
        ctk.CTkEntry(parent, textvariable=var).grid(row=row, column=1, padx=12, pady=10, sticky="ew")
        parent.grid_columnconfigure(1, weight=1)

    def _path_row(self, parent: ctk.CTkFrame, label: str, var: tk.StringVar, callback, row: int) -> None:
        ctk.CTkLabel(parent, text=label, width=140, anchor="w").grid(row=row, column=0, padx=12, pady=10, sticky="w")
        ctk.CTkEntry(parent, textvariable=var).grid(row=row, column=1, padx=12, pady=10, sticky="ew")
        ctk.CTkButton(parent, text="Выбрать", width=110, command=callback).grid(row=row, column=2, padx=12, pady=10)
        parent.grid_columnconfigure(1, weight=1)

    def _pick_input(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("MKV", "*.mkv"), ("All", "*.*")])
        if path:
            self.input_path.set(path)

    def _pick_profile(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if path:
            self.profile_path.set(path)

    def _pick_output(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.output_dir.set(path)

    def test_connection(self) -> None:
        cmd = ["ssh", "-p", self.port.get().strip(), f"{self.user.get().strip()}@{self.host.get().strip()}", "echo OK"]
        self._run_threaded(cmd, "Проверка SSH")

    def start_job(self) -> None:
        if not self.input_path.get().strip() or not self.host.get().strip() or not self.user.get().strip() or not self.profile_path.get().strip():
            messagebox.showerror("Ошибка", "Заполни поля: MKV, host, user, profile")
            return

        cmd = [
            "python",
            "client_beta1.py",
            self.input_path.get().strip(),
            "--host",
            self.host.get().strip(),
            "--user",
            self.user.get().strip(),
            "--port",
            self.port.get().strip(),
            "--profile",
            self.profile_path.get().strip(),
            "--remote-base",
            self.remote_base.get().strip(),
            "--output-dir",
            self.output_dir.get().strip(),
        ]
        self._run_threaded(cmd, "Кодирование")

    def _run_threaded(self, cmd: list[str], title: str) -> None:
        def worker() -> None:
            self.log_queue.put(f"\n--- {title} ---\n$ {' '.join(cmd)}\n")
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            assert proc.stdout is not None
            for line in proc.stdout:
                self.log_queue.put(line)
            code = proc.wait()
            if code == 0:
                self.log_queue.put(f"\n✅ {title} завершено успешно\n")
            else:
                self.log_queue.put(f"\n❌ {title} завершилось с ошибкой (code={code})\n")

        threading.Thread(target=worker, daemon=True).start()

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
        print(err, file=sys.stderr)
        return 1
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

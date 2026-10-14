#!/usr/bin/env python3
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import traceback
from dataclasses import dataclass
from pathlib import Path


def bundled_root() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


APP_ROOT = bundled_root()
PIPELINE_SCRIPT = APP_ROOT / "Internal_DO_NOT_DELETE" / "scripts" / "run_sorting_pipeline.py"
DEFAULT_RULES_FILE = APP_ROOT / "Internal_DO_NOT_DELETE" / "project_rules" / "sorting_rules.md"
DEFAULT_ARCHIVE_NAME = "Архив"
SCRIPTS_DIR = APP_ROOT / "Internal_DO_NOT_DELETE" / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_sorting_pipeline


@dataclass
class LaunchConfig:
    source_dir: str
    output_dir: str
    archive_name: str
    mode: str


class PipelineRunner:
    def __init__(self) -> None:
        self._running = False
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen[str] | None = None

    def is_running(self) -> bool:
        return self._running

    def terminate(self) -> None:
        process = self._process
        if process is not None and process.poll() is None:
            process.terminate()

    def start(
        self,
        config: LaunchConfig,
        on_line,
        on_status,
        on_finish,
    ) -> None:
        if self.is_running():
            raise RuntimeError("Pipeline is already running.")

        env = os.environ.copy()
        env["SORTING_RULES_FILE"] = str(ensure_rules_file())

        def _reader() -> None:
            self._running = True
            try:
                command = pipeline_command([
                    "--source",
                    config.source_dir,
                    "--output",
                    config.output_dir,
                    "--archive-name",
                    config.archive_name,
                    "--mode",
                    config.mode,
                ])
                self._process = subprocess.Popen(
                    command,
                    cwd=str(APP_ROOT),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                )
                assert self._process.stdout is not None
                for raw_line in self._process.stdout:
                    line = raw_line.rstrip()
                    if not line:
                        continue
                    on_line(line)
                    phase = parse_phase(line)
                    if phase:
                        on_status(f"Phase: {phase}")
                code = self._process.wait()
                on_finish(code)
            except Exception:
                on_line(traceback.format_exc().rstrip())
                on_finish(1)
            finally:
                self._process = None
                self._running = False

        self._thread = threading.Thread(target=_reader, daemon=True)
        self._thread.start()


def parse_phase(line: str) -> str | None:
    prefix = "[phase] "
    if line.startswith(prefix):
        return line[len(prefix):].strip()
    return None


def pipeline_command(args: list[str]) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--run-pipeline", *args]
    return [sys.executable, str(Path(__file__).resolve()), "--run-pipeline", *args]


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "SortingFilesNativeApp"
    return APP_ROOT / ".runtime" / "SortingFilesNativeApp"


def ensure_rules_file() -> Path:
    target = app_data_dir() / "sorting_rules.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return target
    if DEFAULT_RULES_FILE.exists():
        target.write_text(DEFAULT_RULES_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        target.write_text("# Правила сортировки\n", encoding="utf-8")
    return target


def validate_config(source_dir: str, output_dir: str, archive_name: str) -> str | None:
    if not PIPELINE_SCRIPT.exists():
        return f"Pipeline script not found: {PIPELINE_SCRIPT}"
    if not source_dir:
        return "Choose a source folder."
    if not output_dir:
        return "Choose an output folder."
    if not archive_name.strip():
        return "Enter an archive name."
    if not Path(source_dir).expanduser().exists():
        return f"Source folder not found: {source_dir}"
    if not Path(output_dir).expanduser().exists():
        return f"Output folder not found: {output_dir}"
    return None


def launch_with_pyside6() -> bool:
    try:
        from PySide6 import QtCore, QtWidgets
    except ImportError:
        return False

    class Window(QtWidgets.QWidget):
        line_signal = QtCore.Signal(str)
        status_signal = QtCore.Signal(str)
        finish_signal = QtCore.Signal(int)

        def __init__(self) -> None:
            super().__init__()
            self.runner = PipelineRunner()
            self.setWindowTitle("Sorting Files Launcher")
            self.resize(860, 620)

            self.source_edit = QtWidgets.QLineEdit()
            self.output_edit = QtWidgets.QLineEdit()
            self.archive_edit = QtWidgets.QLineEdit(DEFAULT_ARCHIVE_NAME)
            self.mode_combo = QtWidgets.QComboBox()
            self.mode_combo.addItems(["copy", "move"])
            self.status_label = QtWidgets.QLabel("Ready")
            self.log_view = QtWidgets.QPlainTextEdit()
            self.log_view.setReadOnly(True)
            self.start_button = QtWidgets.QPushButton("Start")
            self.stop_button = QtWidgets.QPushButton("Stop")
            self.stop_button.setEnabled(False)

            layout = QtWidgets.QVBoxLayout(self)
            layout.addLayout(self._row("Source", self.source_edit, self._browse_button(self._choose_source)))
            layout.addLayout(self._row("Output", self.output_edit, self._browse_button(self._choose_output)))
            layout.addLayout(self._row("Archive name", self.archive_edit))
            layout.addLayout(self._row("Mode", self.mode_combo))

            actions = QtWidgets.QHBoxLayout()
            actions.addWidget(self.start_button)
            actions.addWidget(self.stop_button)
            actions.addStretch(1)
            layout.addLayout(actions)
            layout.addWidget(self.status_label)
            layout.addWidget(self.log_view, 1)

            self.start_button.clicked.connect(self._start)
            self.stop_button.clicked.connect(self._stop)
            self.line_signal.connect(self.log_view.appendPlainText)
            self.status_signal.connect(self.status_label.setText)
            self.finish_signal.connect(self._on_finish)

        def _row(self, label: str, field, extra=None):
            row = QtWidgets.QHBoxLayout()
            row.addWidget(QtWidgets.QLabel(label))
            row.addWidget(field, 1)
            if extra is not None:
                row.addWidget(extra)
            return row

        def _browse_button(self, handler):
            button = QtWidgets.QPushButton("Browse")
            button.clicked.connect(handler)
            return button

        def _choose_source(self) -> None:
            path = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose source folder", self.source_edit.text() or str(APP_ROOT))
            if path:
                self.source_edit.setText(path)

        def _choose_output(self) -> None:
            path = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose output folder", self.output_edit.text() or str(APP_ROOT))
            if path:
                self.output_edit.setText(path)

        def _set_running(self, running: bool) -> None:
            self.start_button.setEnabled(not running)
            self.stop_button.setEnabled(running)

        def _start(self) -> None:
            config = LaunchConfig(
                source_dir=self.source_edit.text().strip(),
                output_dir=self.output_edit.text().strip(),
                archive_name=self.archive_edit.text().strip(),
                mode=self.mode_combo.currentText(),
            )
            error = validate_config(config.source_dir, config.output_dir, config.archive_name)
            if error:
                QtWidgets.QMessageBox.critical(self, "Launcher", error)
                return
            self.log_view.clear()
            self.status_label.setText("Starting...")
            self._set_running(True)
            self.runner.start(
                config,
                on_line=self.line_signal.emit,
                on_status=self.status_signal.emit,
                on_finish=self.finish_signal.emit,
            )

        def _stop(self) -> None:
            self.runner.terminate()
            self.status_label.setText("Stopping...")

        def _on_finish(self, code: int) -> None:
            self._set_running(False)
            if code == 0:
                self.status_label.setText("Finished successfully")
            else:
                self.status_label.setText(f"Finished with exit code {code}")

    app = QtWidgets.QApplication(sys.argv)
    window = Window()
    window.show()
    app.exec()
    return True


def launch_with_tkinter() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk

    runner = PipelineRunner()
    root = tk.Tk()
    root.title("Sorting Files Launcher")
    root.geometry("860x620")

    source_var = tk.StringVar()
    output_var = tk.StringVar()
    archive_var = tk.StringVar(value=DEFAULT_ARCHIVE_NAME)
    mode_var = tk.StringVar(value="copy")
    status_var = tk.StringVar(value="Ready")
    messages: "queue.Queue[tuple[str, object]]" = queue.Queue()

    main = ttk.Frame(root, padding=12)
    main.pack(fill=tk.BOTH, expand=True)
    main.columnconfigure(1, weight=1)
    main.rowconfigure(5, weight=1)

    def add_row(row: int, label: str, variable: tk.StringVar, browse_command=None) -> None:
        ttk.Label(main, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(main, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)
        if browse_command is not None:
            ttk.Button(main, text="Browse", command=browse_command).grid(row=row, column=2, sticky="ew", pady=4)

    def choose_source() -> None:
        path = filedialog.askdirectory(initialdir=source_var.get() or str(APP_ROOT))
        if path:
            source_var.set(path)

    def choose_output() -> None:
        path = filedialog.askdirectory(initialdir=output_var.get() or str(APP_ROOT))
        if path:
            output_var.set(path)

    add_row(0, "Source", source_var, choose_source)
    add_row(1, "Output", output_var, choose_output)
    add_row(2, "Archive name", archive_var)

    ttk.Label(main, text="Mode").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
    mode_box = ttk.Combobox(main, textvariable=mode_var, values=["copy", "move"], state="readonly")
    mode_box.grid(row=3, column=1, sticky="w", pady=4)

    actions = ttk.Frame(main)
    actions.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(8, 8))
    start_button = ttk.Button(actions, text="Start")
    stop_button = ttk.Button(actions, text="Stop", state=tk.DISABLED)
    start_button.pack(side=tk.LEFT)
    stop_button.pack(side=tk.LEFT, padx=(8, 0))

    ttk.Label(main, textvariable=status_var).grid(row=5, column=0, columnspan=3, sticky="w", pady=(0, 8))
    log_view = scrolledtext.ScrolledText(main, wrap=tk.WORD)
    log_view.grid(row=6, column=0, columnspan=3, sticky="nsew")
    main.rowconfigure(6, weight=1)

    def set_running(running: bool) -> None:
        start_button.configure(state=tk.DISABLED if running else tk.NORMAL)
        stop_button.configure(state=tk.NORMAL if running else tk.DISABLED)

    def append_log(line: str) -> None:
        log_view.insert(tk.END, line + "\n")
        log_view.see(tk.END)

    def pump_queue() -> None:
        try:
            while True:
                event, payload = messages.get_nowait()
                if event == "line":
                    append_log(str(payload))
                elif event == "status":
                    status_var.set(str(payload))
                elif event == "finish":
                    code = int(payload)
                    set_running(False)
                    status_var.set("Finished successfully" if code == 0 else f"Finished with exit code {code}")
        except queue.Empty:
            pass
        root.after(100, pump_queue)

    def start() -> None:
        config = LaunchConfig(
            source_dir=source_var.get().strip(),
            output_dir=output_var.get().strip(),
            archive_name=archive_var.get().strip(),
            mode=mode_var.get().strip() or "copy",
        )
        error = validate_config(config.source_dir, config.output_dir, config.archive_name)
        if error:
            messagebox.showerror("Launcher", error)
            return
        log_view.delete("1.0", tk.END)
        status_var.set("Starting...")
        set_running(True)
        runner.start(
            config,
            on_line=lambda line: messages.put(("line", line)),
            on_status=lambda text: messages.put(("status", text)),
            on_finish=lambda code: messages.put(("finish", code)),
        )

    def stop() -> None:
        runner.terminate()
        status_var.set("Stopping...")

    def on_close() -> None:
        if runner.is_running():
            runner.terminate()
        root.destroy()

    start_button.configure(command=start)
    stop_button.configure(command=stop)
    root.protocol("WM_DELETE_WINDOW", on_close)
    pump_queue()
    root.mainloop()


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--run-pipeline":
        return run_sorting_pipeline.main(sys.argv[2:])
    if launch_with_pyside6():
        return 0
    launch_with_tkinter()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

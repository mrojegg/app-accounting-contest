from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys


APP_ROOT = Path(__file__).resolve().parents[2]
WINDOWS_APP_DIR = APP_ROOT / "src" / "windows_app"
SCRIPTS_DIR = APP_ROOT / "Internal_DO_NOT_DELETE" / "scripts"
for path in (WINDOWS_APP_DIR, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import launcher


class WindowsLauncherTests(unittest.TestCase):
    def test_bundled_root_uses_meipass_when_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_exe = Path(tmpdir) / "SortingFilesWindows.exe"
            fake_exe.write_text("x", encoding="utf-8")
            with mock.patch.object(sys, "frozen", True, create=True), \
                 mock.patch.object(sys, "_MEIPASS", tmpdir, create=True), \
                 mock.patch.object(sys, "executable", str(fake_exe)):
                self.assertEqual(launcher.bundled_root(), Path(tmpdir))

    def test_terminate_stops_running_subprocess(self) -> None:
        class FakeProcess:
            def __init__(self) -> None:
                self.terminated = False

            def poll(self):
                return None

            def terminate(self) -> None:
                self.terminated = True

        runner = launcher.PipelineRunner()
        fake = FakeProcess()
        runner._process = fake

        runner.terminate()

        self.assertTrue(fake.terminated)

    def test_pipeline_command_uses_internal_runner_mode(self) -> None:
        command = launcher.pipeline_command(["--source", "s", "--output", "o"])

        self.assertIn("--run-pipeline", command)
        self.assertEqual(command[-4:], ["--source", "s", "--output", "o"])


if __name__ == "__main__":
    unittest.main()

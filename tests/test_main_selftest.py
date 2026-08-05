"""Tests for main.py's --self-test flag.

This is the exact check CI runs against the frozen .exe before it is
allowed to reach a release — it catches the "ModuleNotFoundError: No
module named 'api'" class of bug at build time instead of shipping it.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


class TestSelfTestFunction:
    def test_passes_in_dev_environment(self):
        import main as main_module

        assert main_module.self_test() == 0

    def test_fails_when_ui_dir_missing(self, monkeypatch, tmp_path):
        import main as main_module

        monkeypatch.setattr(main_module, "UI_DIR", tmp_path / "no-such-ui")
        assert main_module.self_test() == 1

    def test_reports_each_check_by_label(self, capsys):
        import main as main_module

        main_module.self_test()
        out = capsys.readouterr().out
        assert "AnalyzerApi has analyzeZip" in out
        assert "index.html present" in out


class TestSelfTestCliFlag:
    def test_exits_zero_via_subprocess(self):
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "main.py"), "--self-test"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr

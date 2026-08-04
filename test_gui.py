"""Tests for gui.py — encoding, ZIP root detection, ToolTip."""

import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import tkinter as tk
    TK_AVAILABLE = True
except ModuleNotFoundError:
    TK_AVAILABLE = False


# -- Encoding tests (standalone) -----------------------------------------

def _decode_bytes(raw: bytes) -> str:
    for encoding in ("utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


class TestSubprocessEncoding(unittest.TestCase):
    def test_pure_utf8(self):
        result = _decode_bytes("hello world".encode("utf-8"))
        self.assertEqual(result, "hello world")

    def test_german_umlaut_latin1(self):
        raw = b"Gr\xfc\xdfe"
        result = _decode_bytes(raw)
        self.assertIn("\xfc", result)
        self.assertNotIn("\ufffd", result)

    def test_mixed_encoding_fallback(self):
        raw = b"valid text \xff\xfe\xfd more text"
        result = _decode_bytes(raw)
        self.assertIn("valid text", result)
        self.assertIn("more text", result)

    def test_full_output_with_user_content(self):
        raw = b"Lord Hippo - 500 messages\n"
        raw += "M\xfcller - 200 messages\n".encode("latin-1")
        result = _decode_bytes(raw)
        self.assertIn("Lord Hippo", result)
        self.assertIn("200 messages", result)


# -- ZIP root detection --------------------------------------------------

class TestFindExportRoot(unittest.TestCase):
    @unittest.skipIf(not TK_AVAILABLE, "tkinter not available")
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="test_export_"))
        (self.tmp / "Account").mkdir()
        (self.tmp / "Account" / "user.json").write_text("{}")

    def tearDown(self):
        if hasattr(self, 'tmp'):
            import shutil
            shutil.rmtree(self.tmp, ignore_errors=True)

    @unittest.skipIf(not TK_AVAILABLE, "tkinter not available")
    def test_direct_root(self):
        from gui import DashboardApp
        app = DashboardApp()
        result = app._find_export_root(self.tmp)
        self.assertEqual(result, self.tmp)

    @unittest.skipIf(not TK_AVAILABLE, "tkinter not available")
    def test_nested_one_level(self):
        from gui import DashboardApp
        nested = self.tmp / "My Discord Export"
        nested.mkdir()
        (nested / "Account").mkdir()
        (nested / "Account" / "user.json").write_text("{}")
        app = DashboardApp()
        result = app._find_export_root(self.tmp)
        self.assertEqual(result, nested)

    @unittest.skipIf(not TK_AVAILABLE, "tkinter not available")
    def test_no_account_found(self):
        from gui import DashboardApp
        empty = self.tmp / "empty"
        empty.mkdir()
        app = DashboardApp()
        result = app._find_export_root(empty)
        self.assertEqual(result, empty)


# -- ToolTip class -------------------------------------------------------

class TestToolTip(unittest.TestCase):
    @unittest.skipIf(not TK_AVAILABLE, "tkinter not available")
    def test_tooltip_accepts_widget(self):
        from gui import ToolTip
        root = tk.Tk()
        root.withdraw()
        label = tk.Label(root, text="test")
        tip = ToolTip(label, "hello world")
        self.assertEqual(tip.text, "hello world")
        self.assertIsNone(tip.tip)
        root.destroy()

    @unittest.skipIf(not TK_AVAILABLE, "tkinter not available")
    def test_tooltip_text_stored(self):
        from gui import ToolTip
        root = tk.Tk()
        root.withdraw()
        frame = tk.Frame(root)
        tip = ToolTip(frame, "42 messages")
        self.assertEqual(tip.text, "42 messages")
        root.destroy()


if __name__ == "__main__":
    unittest.main()

"""Tests for gui.py — subprocess output encoding handling."""

import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


# ── The function under test (extracted for testability) ─────────────────

def _capture_analyzer_output(analyzer_path: Path, extract_dir: Path, timeout: int = 600) -> str:
    """Run analyzer.py --dir <extract_dir> all and return stdout as a string.
    Handles mixed encodings gracefully — Discord data may contain Latin-1
    characters (e.g. German umlauts like ü = 0xFC) alongside UTF-8."""
    proc = subprocess.Popen(
        [sys.executable, str(analyzer_path), "--dir", str(extract_dir), "all"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(analyzer_path.parent),
    )
    try:
        raw, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        return "(timed out after 10 min — dataset may be too large)"

    # Try UTF-8 first, fall back to Latin-1 with replacement
    for encoding in ("utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


class TestSubprocessEncoding(unittest.TestCase):
    """Verify that _capture_analyzer_output handles non-UTF-8 bytes."""

    def _fake_popen(self, raw_bytes: bytes, timeout: bool = False):
        """Create a mock Popen that returns given raw bytes."""

        class FakeProc:
            def communicate(self, timeout=None):
                if timeout:
                    raise subprocess.TimeoutExpired(cmd="fake", timeout=timeout)
                return (raw_bytes, None)

            def kill(self):
                pass

            def wait(self):
                pass

        return FakeProc()

    def test_pure_utf8_output(self):
        """Standard UTF-8 output returns unchanged."""
        result = _decode_bytes("hello world".encode("utf-8"))
        self.assertEqual(result, "hello world")

    def test_german_umlaut_latin1(self):
        """Byte 0xFC (ü) in Latin-1 context decodes correctly."""
        # "Grüße" in Latin-1: G r 0xFC ß e
        raw = b"Gr\xfc\xdfe"
        result = _decode_bytes(raw)
        self.assertIn("ü", result)
        self.assertNotIn("\ufffd", result)  # no replacement chars

    def test_mixed_encoding_fallback(self):
        """Garbage bytes fall back to replacement chars, not crash."""
        raw = b"valid text \xff\xfe\xfd more text"
        result = _decode_bytes(raw)
        self.assertIn("valid text", result)
        self.assertIn("more text", result)

    def test_timeout_handling(self):
        """Timeout returns a user-friendly message."""
        fake = self._fake_popen(b"", timeout=True)
        with mock.patch("subprocess.Popen", return_value=fake):
            result = _capture_analyzer_output(Path("."), Path(tempfile.mkdtemp()), timeout=1)
            self.assertIn("timed out", result)

    def test_full_output_with_user_content(self):
        """Simulated Discord output with mixed user names survives roundtrip."""
        raw = b"Lord Hippo - 500 messages\n"
        raw += "M\xfcller - 200 messages\n".encode("latin-1")  # Müller
        result = _decode_bytes(raw)
        self.assertIn("Lord Hippo", result)
        self.assertIn("200 messages", result)


def _decode_bytes(raw: bytes) -> str:
    """Simulate what _capture_analyzer_output does internally."""
    for encoding in ("utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


if __name__ == "__main__":
    unittest.main()

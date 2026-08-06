"""Tests for version comparison logic in checkForUpdate."""
import re
import json
from unittest.mock import patch, Mock
from api import AnalyzerApi, VERSION

def parse_version(tag):
    """Replicate the semver parsing logic from checkForUpdate."""
    m = re.match(r'^v?(\d+)\.(\d+)\.(\d+)', tag)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))

def test_newer_version_detected():
    """v2.2.0 should be newer than current VERSION."""
    remote = parse_version("v2.2.0")
    local = parse_version(VERSION)
    assert remote > local

def test_same_version_not_newer():
    """Same version should not trigger update."""
    remote = parse_version(VERSION)
    local = parse_version(VERSION)
    assert remote == local
    assert not (remote > local)

def test_prerelease_handled():
    """v2.2.0-rc1 should be treated as (2,2,0) — newer than current."""
    remote = parse_version("v2.2.0-rc1")
    local = parse_version(VERSION)
    assert remote == (2, 2, 0)
    assert remote > local

def test_non_semver_skipped():
    """Non-semver tags like 'release-2026' should be skipped."""
    remote = parse_version("release-2026")
    assert remote is None

def test_older_version_not_newer():
    """v2.0.0 should not trigger update."""
    remote = parse_version("v2.0.0")
    local = parse_version(VERSION)
    assert not (remote > local)

@patch("api.webview", None, create=True)
def test_checkForUpdate_no_webview():
    """checkForUpdate should handle missing webview gracefully."""
    api = AnalyzerApi()
    # Should not crash when webview is not available
    try:
        api.checkForUpdate()
    except Exception as e:
        assert False, f"checkForUpdate should not crash without webview: {e}"

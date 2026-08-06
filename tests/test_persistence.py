"""Tests for saveAnalysis / getSavedAnalysis persistence methods."""
import json
import os
import tempfile
from pathlib import Path
from api import AnalyzerApi

def test_save_and_load_roundtrip():
    """Save analysis data then load it back — should match."""
    os.environ["APPDATA"] = tempfile.mkdtemp()
    api = AnalyzerApi()
    data = {"msg": {"total": 100}, "servers": [["s1", 50]], "voice": {"total_sessions": 5}}
    assert api.saveAnalysis(data) is True
    loaded = api.getSavedAnalysis()
    assert loaded == data

def test_load_when_no_file():
    """getSavedAnalysis returns None when no saved file exists."""
    os.environ["APPDATA"] = tempfile.mkdtemp()
    api = AnalyzerApi()
    assert api.getSavedAnalysis() is None

def test_load_corrupted_file():
    """getSavedAnalysis returns None for corrupted JSON."""
    appdata = tempfile.mkdtemp()
    os.environ["APPDATA"] = appdata
    save_dir = Path(appdata) / "Discord-Personal-Data-Analyzer"
    save_dir.mkdir(parents=True, exist_ok=True)
    (save_dir / "last-analysis.json").write_text("not valid json {{{", encoding="utf-8")
    api = AnalyzerApi()
    assert api.getSavedAnalysis() is None

def test_save_no_appdata():
    """saveAnalysis returns False when APPDATA is not set."""
    if "APPDATA" in os.environ:
        del os.environ["APPDATA"]
    api = AnalyzerApi()
    assert api.saveAnalysis({"test": 1}) is False

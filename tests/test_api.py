"""Tests for api.py — AnalyzerApi bridge class."""

import json
import zipfile
from pathlib import Path

import pytest

from api import AnalyzerApi


class TestAnalyzerApi:
    def test_instantiation(self):
        api = AnalyzerApi()
        assert hasattr(api, "selectFile")
        assert hasattr(api, "analyzeZip")
        assert hasattr(api, "_find_export_root")

    def test_analyze_zip_invalid_path(self):
        api = AnalyzerApi()
        result = api.analyzeZip("/nonexistent/path.zip")
        assert "error" in result
        assert result["error"] == "Invalid ZIP file"

    def test_analyze_zip_non_zip_file(self, tmp_path):
        api = AnalyzerApi()
        f = tmp_path / "test.txt"
        f.write_text("not a zip")
        result = api.analyzeZip(str(f))
        assert "error" in result

    def test_analyze_zip_valid(self, tmp_path, mock_export_dir):
        api = AnalyzerApi()
        zip_path = tmp_path / "test_export.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in mock_export_dir.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(mock_export_dir))

        result = api.analyzeZip(str(zip_path))
        assert "error" not in result
        assert "msg" in result
        assert "dm_users" in result
        assert "servers" in result
        assert "timeline" in result
        assert "voice" in result
        assert result["msg"]["total_messages"] == 9
        assert result["msg"]["dm_total"] == 8

    def test_analyze_zip_bad_zip(self, tmp_path):
        api = AnalyzerApi()
        bad = tmp_path / "bad.zip"
        bad.write_text("not a zip file at all")
        result = api.analyzeZip(str(bad))
        assert "error" in result

    def test_find_export_root_direct(self, tmp_path):
        api = AnalyzerApi()
        d = tmp_path / "export"
        d.mkdir()
        (d / "Account").mkdir()
        result = api._find_export_root(d)
        assert result == d

    def test_find_export_root_nested(self, tmp_path):
        api = AnalyzerApi()
        outer = tmp_path / "outer"
        outer.mkdir()
        inner = outer / "My Discord Export"
        inner.mkdir()
        (inner / "Account").mkdir()
        result = api._find_export_root(outer)
        assert result == inner

    def test_find_export_root_no_account(self, tmp_path):
        api = AnalyzerApi()
        d = tmp_path / "empty"
        d.mkdir()
        result = api._find_export_root(d)
        assert result == d

    def test_analyze_zip_result_is_json_serializable(self, tmp_path, mock_export_dir):
        api = AnalyzerApi()
        zip_path = tmp_path / "test2.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in mock_export_dir.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(mock_export_dir))

        result = api.analyzeZip(str(zip_path))
        serialized = json.dumps(result)
        assert len(serialized) > 0
        roundtripped = json.loads(serialized)
        assert roundtripped["msg"]["total_messages"] == result["msg"]["total_messages"]
        assert roundtripped["msg"]["dm_total"] == result["msg"]["dm_total"]
        assert len(roundtripped["dm_users"]) == len(result["dm_users"])
        assert len(roundtripped["servers"]) == len(result["servers"])

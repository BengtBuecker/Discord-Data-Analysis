import json
import zipfile
from pathlib import Path

import pytest

from api import AnalyzerApi

APP_JS = Path(__file__).parents[1] / "ui" / "app.js"


def test_import_never_falls_back_to_browser_path_prompt():
    source = APP_JS.read_text(encoding="utf-8")

    assert 'prompt("Enter ZIP path:")' not in source
    assert "pywebviewready" in source
    assert "const api = window.pywebview?.api ||" not in source


def test_import_resolves_bridge_when_action_runs():
    source = APP_JS.read_text(encoding="utf-8")

    assert "await getPywebviewApi()" in source
    assert "api.selectFile()" in source
    assert "api.analyzeZip(path)" in source


class TestBarWidthMath:
    """Simulate JS barRow(value / max * 100) to catch zero-width bugs."""

    @pytest.fixture
    def api_result(self, tmp_path, mock_export_dir):
        zip_path = tmp_path / "export.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in mock_export_dir.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(mock_export_dir))
        api = AnalyzerApi()
        return api.analyzeZip(str(zip_path))

    def test_dm_bar_widths_nonzero(self, api_result):
        users = api_result["dm_users"]
        if not users:
            pytest.skip("No DM data in fixture")
        max_val = users[0][1]
        for name, count in users:
            w = (count / max_val * 100) if max_val else 0
            assert w > 0, f"DM bar for '{name}' computed {w:.2f}% (count={count}, max={max_val})"

    def test_server_bar_widths_nonzero(self, api_result):
        servers = sorted(
            [s for s in api_result["servers"] if s[0] not in ("Direct Messages", "Unknown")],
            key=lambda s: s[1], reverse=True,
        )
        if not servers:
            pytest.skip("No server data in fixture")
        max_val = max(s[1] for s in servers)
        if max_val == 0:
            pytest.skip("All server counts are zero in fixture")
        for name, count in servers:
            if count == 0:
                continue
            w = (count / max_val * 100) if max_val else 0
            assert w > 0, f"Server bar for '{name}' computed {w:.2f}% (count={count}, max={max_val})"

    def test_voice_bar_widths_nonzero(self, api_result):
        ch = api_result["voice"]["channel_durations"]
        dm_entries = [c for c in ch if c["name_type"] == "dm"]
        if not dm_entries:
            pytest.skip("No voice DM data in fixture")
        max_val = dm_entries[0]["duration_seconds"]
        for entry in dm_entries:
            dur = entry["duration_seconds"]
            w = (dur / max_val * 100) if max_val else 0
            assert w > 0, f"Voice bar for '{entry['name']}' computed {w:.2f}% (dur={dur}, max={max_val})"

    def test_timeline_bar_heights_nonzero(self, api_result):
        tl = api_result["timeline"]
        if not tl:
            pytest.skip("No timeline data in fixture")
        entries = sorted(tl.items())
        max_count = max(count for _, count in entries)
        for period, count in entries:
            h = (count / max_count * 100) if max_count else 0
            assert h > 0, f"Timeline bar for '{period}' computed {h:.2f}% (count={count}, max={max_count})"

    def test_response_is_json_serializable(self, api_result):
        serialized = json.dumps(api_result)
        assert len(serialized) > 0
        rt = json.loads(serialized)
        assert rt["msg"]["total_messages"] == api_result["msg"]["total_messages"]
        assert rt["dm_users"] == [list(u) for u in api_result["dm_users"]]
        assert rt["servers"] == [list(s) for s in api_result["servers"]]
        assert rt["timeline"] == api_result["timeline"]

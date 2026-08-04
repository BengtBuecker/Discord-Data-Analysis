from pathlib import Path


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

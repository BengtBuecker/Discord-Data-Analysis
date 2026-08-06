#!/usr/bin/env python3
"""Discord Personal Data Analyzer -- PyWebView Entry Point

Renders the dashboard via native OS webview (Edge WebView2 on Windows).
Supports both dev (python main.py) and PyInstaller-frozen (.exe) modes.
"""

import sys
import threading
from pathlib import Path

if getattr(sys, "frozen", False):
    UI_DIR = Path(sys._MEIPASS) / "ui"
else:
    UI_DIR = Path(__file__).parent / "ui"

try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False

from api import AnalyzerApi  # top-level so PyInstaller's static analysis finds it


def run_webview():
    api = AnalyzerApi()

    html_path = str(UI_DIR / "index.html")

    window = webview.create_window(
        title="Discord Personal Data Analyzer",
        url=html_path,
        js_api=api,
        width=1100,
        height=780,
        min_size=(640, 500),
        resizable=True,
    )
    threading.Thread(target=api.checkForUpdate, daemon=True).start()
    webview.start(debug=False, private_mode=False)


def self_test() -> int:
    """Verify the running environment can serve the app: modules import
    and UI assets are present. Run via `--self-test` (used by CI against
    the frozen .exe before it ships in a release).
    """
    checks = [
        ("AnalyzerApi has analyzeZip", hasattr(AnalyzerApi, "analyzeZip")),
        ("AnalyzerApi has selectFile", hasattr(AnalyzerApi, "selectFile")),
        ("UI_DIR exists", UI_DIR.exists()),
        ("index.html present", (UI_DIR / "index.html").exists()),
        ("app.js present", (UI_DIR / "app.js").exists()),
        ("style.css present", (UI_DIR / "style.css").exists()),
    ]
    all_passed = True
    for label, passed in checks:
        print(f"  [{'OK' if passed else 'FAIL'}] {label}")
        all_passed = all_passed and passed
    return 0 if all_passed else 1


def main():
    if "--self-test" in sys.argv:
        sys.exit(self_test())

    if not HAS_WEBVIEW:
        print("=" * 60)
        print("  Discord Personal Data Analyzer")
        print("=" * 60)
        print()
        print("  pywebview not installed.")
        print()
        print("  Install it with:")
        print("    pip install pywebview")
        print()
        print("  Then run: python main.py")
        print()
        print("=" * 60)
        sys.exit(1)

    if not UI_DIR.exists():
        print(f"Error: UI directory not found at {UI_DIR}")
        sys.exit(1)

    run_webview()


if __name__ == "__main__":
    main()

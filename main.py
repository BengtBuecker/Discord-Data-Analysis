#!/usr/bin/env python3
"""Discord Data Analyzer -- PyWebView Entry Point

Renders the dashboard via native OS webview (Edge WebView2 on Windows).
Supports both dev (python main.py) and PyInstaller-frozen (.exe) modes.
"""

import sys
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


def run_webview():
    from api import AnalyzerApi
    api = AnalyzerApi()

    html_path = str(UI_DIR / "index.html")

    window = webview.create_window(
        title="Discord Data Analyzer",
        url=html_path,
        js_api=api,
        width=1100,
        height=780,
        min_size=(640, 500),
        resizable=True,
    )
    webview.start(debug=False, private_mode=False)


def main():
    if not HAS_WEBVIEW:
        print("=" * 60)
        print("  Discord Data Analyzer")
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

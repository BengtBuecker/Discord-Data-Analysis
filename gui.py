#!/usr/bin/env python3
"""Discord Data Analyzer — GUI Edition.

Zero-dependency web UI: upload your Discord GDPR ZIP, get the full report.
Start with:  python gui.py
Then open:   http://localhost:8080
"""

import html
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ANALYZER_DIR = Path(__file__).parent.resolve()
TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Discord Data Analyzer</title>
<style>
* { box-sizing:border-box; margin:0; padding:0 }
body { font-family:system-ui,sans-serif; background:#1e1e2e; color:#cdd6f4; padding:2rem; max-width:900px; margin:0 auto }
h1 { text-align:center; margin-bottom:0.25rem }
.sub { text-align:center; color:#6c7086; margin-bottom:2rem; font-size:0.9rem }
.upload-box { background:#313244; border:2px dashed #45475a; border-radius:12px; padding:2.5rem; text-align:center; margin-bottom:2rem; transition:border-color 0.2s }
.upload-box.dragover { border-color:#89b4fa }
.upload-box p { color:#a6adc8; margin-bottom:1rem }
input[type=file] { display:block; margin:0 auto 1rem; color:#cdd6f4 }
button { background:#89b4fa; color:#1e1e2e; border:none; padding:0.75rem 2rem; border-radius:8px; font-size:1rem; font-weight:600; cursor:pointer }
button:hover { background:#b4d0fb }
.spinner { display:none; margin:1rem auto; width:2rem; height:2rem; border:3px solid #45475a; border-top-color:#89b4fa; border-radius:50%; animation:spin 0.75s linear infinite }
@keyframes spin { to { transform:rotate(360deg) } }
.error { background:#f38ba8; color:#1e1e2e; padding:1rem; border-radius:8px; margin-bottom:1rem }
.output { background:#11111b; border:1px solid #313244; border-radius:8px; padding:1.5rem; white-space:pre-wrap; font-family:monospace; font-size:0.82rem; line-height:1.5; overflow-x:auto; max-height:80vh; overflow-y:auto }
.output h2 { color:#89b4fa; font-size:1rem; margin-top:1.5rem; margin-bottom:0.5rem }
.output h2:first-child { margin-top:0 }
.sep { color:#45475a; margin:0 0.5rem }
.footer { text-align:center; color:#585b70; margin-top:2rem; font-size:0.85rem }
</style>
</head>
<body>
<h1>Discord Data Analyzer</h1>
<p class="sub">Upload your Discord GDPR export ZIP &middot; 100% local &middot; zero data leaves your machine</p>

<form id="uploadForm" action="/" method="post" enctype="multipart/form-data">
  <div class="upload-box" id="dropZone">
    <p>Drop your Discord data ZIP here or click to select</p>
    <input type="file" id="zipfile" name="zipfile" accept=".zip" required>
    <button type="submit">Analyze</button>
    <div class="spinner" id="spinner"></div>
  </div>
</form>

<div id="error"></div>
<div id="result"></div>

<footer class="footer">Data stays on your machine. Zero external dependencies.</footer>

<script>
const dz = document.getElementById('dropZone');
const fileInput = document.getElementById('zipfile');
const spinner = document.getElementById('spinner');
const errorEl = document.getElementById('error');
const resultEl = document.getElementById('result');
const form = document.getElementById('uploadForm');

['dragenter','dragover'].forEach(e => dz.addEventListener(e, ev => { ev.preventDefault(); dz.classList.add('dragover') }));
['dragleave','drop'].forEach(e => dz.addEventListener(e, ev => { ev.preventDefault(); dz.classList.remove('dragover') }));
dz.addEventListener('drop', ev => { fileInput.files = ev.dataTransfer.files });

form.addEventListener('submit', () => {
  errorEl.innerHTML = '';
  resultEl.innerHTML = '';
  spinner.style.display = 'block';
});
</script>
</body>
</html>"""


def _parse_multipart(body: bytes, boundary: str) -> dict:
    """Parse multipart/form-data manually (no cgi module). Returns {field_name: (filename, data)}."""
    boundary_bytes = boundary.encode()
    parts = body.split(b"--" + boundary_bytes)
    result = {}
    for part in parts:
        if part in (b"", b"--", b"--\r\n"):
            continue
        header_end = part.find(b"\r\n\r\n")
        if header_end == -1:
            continue
        headers_raw = part[:header_end].decode(errors="replace")
        content = part[header_end + 4 :]
        if content.endswith(b"\r\n"):
            content = content[:-2]

        name_match = re.search(r'name="([^"]+)"', headers_raw)
        if not name_match:
            continue
        name = name_match.group(1)
        filename_match = re.search(r'filename="([^"]*)"', headers_raw)
        if filename_match:
            result[name] = (filename_match.group(1), content)
        else:
            result[name] = (None, content.decode(errors="replace"))
    return result


def _run_analysis(extract_dir: Path) -> str:
    """Run analyzer.py --dir <extract_dir> all and return captured output."""
    proc = subprocess.run(
        [sys.executable, str(ANALYZER_DIR / "analyzer.py"), "--dir", str(extract_dir), "all"],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(ANALYZER_DIR),
    )
    if proc.returncode != 0 and not proc.stdout:
        return f"Error: {proc.stderr}"
    return proc.stdout


def _format_html(text: str) -> str:
    """Convert analyzer plain-text output to simple HTML with section highlighting."""
    escaped = html.escape(text)
    lines = escaped.split("\n")
    out = []
    for line in lines:
        if line.startswith("===") or line.startswith("---"):
            # Separator lines → thin divider
            prev = out[-1] if out else ""
            if prev and not prev.startswith("</h2>"):
                out.append(f'<span style="color:#45475a">{line}</span>')
            else:
                out.append(f'<span style="color:#45475a">{line}</span>')
        elif line.startswith("  ") and not line.startswith("   "):
            # Section header (indented by 2 spaces, like "  DM Call Duration...")
            stripped = line.strip()
            if stripped and not stripped.startswith("─") and not stripped.startswith("="):
                out.append(f"<h2>{stripped}</h2>")
            else:
                out.append(line)
        else:
            out.append(line)
    return "\n".join(out)


class RequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(TEMPLATE.encode())

    def do_POST(self):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._send_html(400, '<div class="error">Invalid request. Use the upload form.</div>')
            return

        boundary_match = re.search(r"boundary=([^;]+)", content_type)
        if not boundary_match:
            self._send_html(400, '<div class="error">Missing form boundary.</div>')
            return

        boundary = boundary_match.group(1).strip()
        if boundary.startswith('"') and boundary.endswith('"'):
            boundary = boundary[1:-1]

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        fields = _parse_multipart(body, boundary)
        zip_entry = fields.get("zipfile")
        if not zip_entry or not zip_entry[1]:
            self._send_html(400, '<div class="error">No file uploaded.</div>')
            return

        filename, zip_data = zip_entry
        if not filename.lower().endswith(".zip"):
            self._send_html(400, '<div class="error">Please upload a .zip file.</div>')
            return

        extract_dir = Path(tempfile.mkdtemp(prefix="discord_export_"))

        try:
            with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                zf.extractall(extract_dir)
        except (zipfile.BadZipFile, OSError) as e:
            shutil.rmtree(extract_dir, ignore_errors=True)
            self._send_html(400, f'<div class="error">Invalid ZIP file: {html.escape(str(e))}</div>')
            return

        output = _run_analysis(extract_dir)
        shutil.rmtree(extract_dir, ignore_errors=True)

        formatted = _format_html(output)
        html_output = f'<div class="output">{formatted}</div>'
        self._send_html(200, html_output)

    def _send_html(self, status: int, body: str):
        page = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Discord Data Analyzer</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0 }}
body {{ font-family:system-ui,sans-serif; background:#1e1e2e; color:#cdd6f4; padding:2rem; max-width:900px; margin:0 auto }}
h1 {{ text-align:center; margin-bottom:0.25rem }}
.sub {{ text-align:center; color:#6c7086; margin-bottom:2rem; font-size:0.9rem }}
a {{ color:#89b4fa }}
.error {{ background:#f38ba8; color:#1e1e2e; padding:1rem; border-radius:8px; margin-bottom:1rem }}
.output {{ background:#11111b; border:1px solid #313244; border-radius:8px; padding:1.5rem; white-space:pre-wrap; font-family:monospace; font-size:0.82rem; line-height:1.5; overflow-x:auto }}
.output h2 {{ color:#89b4fa; font-size:1rem; margin-top:1.5rem; margin-bottom:0.5rem }}
.output h2:first-child {{ margin-top:0 }}
.back-link {{ text-align:center; margin-top:1.5rem }}
</style>
</head>
<body>
<h1>Discord Data Analyzer</h1>
<p class="sub">100% local &middot; your data never leaves your machine</p>
{body}
<p class="back-link"><a href="/">Analyze another</a></p>
</body>
</html>"""
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(page.encode())

    def log_message(self, format, *args):
        pass  # Suppress access logs


def main():
    port = 8080
    server = HTTPServer(("0.0.0.0", port), RequestHandler)
    print(f"\n  Discord Data Analyzer GUI")
    print(f"  Open http://localhost:{port} in your browser")
    print(f"  Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down.")
        server.server_close()


if __name__ == "__main__":
    main()

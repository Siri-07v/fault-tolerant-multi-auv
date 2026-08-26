"""
serve.py — Simple HTTP server for the AUV Swarm Dashboard.

Run from anywhere:
    python dashboard/serve.py

Serves:
  - /            → dashboard/index.html
  - /style.css   → dashboard/style.css
  - /app.js      → dashboard/app.js
  - /dashboard_runs/*  → archived images & JSON
"""
import http.server
import os
import sys
import webbrowser
import threading

PORT = 8050

# Resolve paths relative to the project root (parent of this script's dir)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler that serves dashboard files and archived run data."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PROJECT_ROOT, **kwargs)

    def translate_path(self, path):
        """Route requests to the correct filesystem paths."""
        # Strip query string
        path = path.split("?")[0]

        # Dashboard static files → dashboard/ directory
        if path in ("/", "/index.html"):
            return os.path.join(SCRIPT_DIR, "index.html")
        if path == "/style.css":
            return os.path.join(SCRIPT_DIR, "style.css")
        if path == "/app.js":
            return os.path.join(SCRIPT_DIR, "app.js")

        # Everything else (dashboard_runs/, etc.) → project root
        return super().translate_path(path)

    def end_headers(self):
        """Add CORS and cache-control headers."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def log_message(self, format, *args):
        """Suppress noisy request logs; only show errors."""
        if args and "404" in str(args[1] if len(args) > 1 else ""):
            super().log_message(format, *args)


def main():
    # Ensure dashboard_runs directory exists
    os.makedirs(os.path.join(PROJECT_ROOT, "dashboard_runs"), exist_ok=True)

    server = http.server.HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    url = f"http://localhost:{PORT}"

    print(f"\n{'='*60}")
    print(f"  AUV Swarm Dashboard")
    print(f"  Serving at: {url}")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    # Open browser after a short delay
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dashboard server.")
        server.shutdown()


if __name__ == "__main__":
    main()

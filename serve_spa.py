"""Simple SPA-aware static file server for Vite builds."""
import http.server
import os
import sys

DIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FrontEnd", "dist")

class SPAHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)

    def do_GET(self):
        # If path has a file extension, serve normally
        path = self.path.split("?")[0]
        file_path = os.path.join(DIST_DIR, path.lstrip("/"))
        if os.path.isfile(file_path):
            return super().do_GET()
        # Otherwise serve index.html (SPA fallback)
        self.path = "/index.html"
        return super().do_GET()

    def log_message(self, format, *args):
        pass  # Quiet

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
    server = http.server.HTTPServer(("0.0.0.0", port), SPAHandler)
    print(f"SPA server running on http://0.0.0.0:{port}")
    server.serve_forever()

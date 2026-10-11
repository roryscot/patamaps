"""Disposable loopback UI fixture, serving only two generated synthetic reports.

Unlike file URLs or a general file server, no request can access a host path.
There is no traversal, directory listing, write endpoint, proxy or remote fetch.
Reports are read once from the fixed acceptance fixture and held in memory.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
pages={f'/{name}':(ROOT/'docs/acceptance'/f'inspection-{name}.html').read_bytes() for name in ['rejected','viable']}
assert all(len(v)<16777216 for v in pages.values())
class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        content=pages.get(self.path)
        self.send_response(200 if content is not None else 404)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers()
        if content is not None:self.wfile.write(content)
    def log_message(self,*args):pass
server=HTTPServer(('127.0.0.1',0),Fixture)
print(f'http://127.0.0.1:{server.server_address[1]}',flush=True)
try:server.serve_forever()
except KeyboardInterrupt:pass
finally:server.server_close()

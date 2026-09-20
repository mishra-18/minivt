"""Serve the repo so web/ can read models/.  python serve.py"""
import http.server, socketserver, os, webbrowser

PORT = 8000
os.chdir(os.path.dirname(os.path.abspath(__file__)))
H = http.server.SimpleHTTPRequestHandler
H.extensions_map.update({'.js': 'text/javascript', '.mjs': 'text/javascript'})
url = f"http://localhost:{PORT}/web/?bg=checker"
with socketserver.TCPServer(("", PORT), H) as httpd:
    print("OpenVT web ->", url)
    print("OBS browser source ->", f"http://localhost:{PORT}/web/")
    webbrowser.open(url)
    httpd.serve_forever()
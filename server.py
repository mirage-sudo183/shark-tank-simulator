#!/usr/bin/env python3
"""Simple HTTPS server for local development with speech recognition"""

import http.server
import ssl
import os

PORT = 8443
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain('cert.pem', 'key.pem')

print(f"\n🚀 HTTPS Server running at: https://localhost:{PORT}")
print("⚠️  You'll see a security warning - click 'Advanced' → 'Proceed to localhost'\n")

with http.server.HTTPServer(('', PORT), Handler) as httpd:
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    httpd.serve_forever()


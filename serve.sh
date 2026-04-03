#!/bin/bash
cd "$(dirname "$0")/docs"
exec python3 -c "import http.server,socketserver;socketserver.TCPServer(('',8080),http.server.SimpleHTTPRequestHandler).serve_forever()"

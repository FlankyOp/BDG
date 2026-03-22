#!/usr/bin/env python3
'''
BDG Predictor - Frontend Server
Static file server for dashboard.html + auto-open browser.
'''

import http.server
import socketserver
import webbrowser
import threading
import time
import os
from urllib.parse import urlparse, parse_qs

PORT = 8000
HOST = '127.0.0.1'
DIRECTORY = '.'

class FrontendHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

if __name__ == '__main__':
    # Start server in thread
    def start_server():
        with socketserver.TCPServer((HOST, PORT), FrontendHandler) as httpd:
            print(f"🌐 Frontend Dashboard running at http://{HOST}:{PORT}")
            print(f"📱 Open: http://{HOST}:{PORT}/dashboard.html")
            httpd.serve_forever()
    
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Auto-open browser after 1s
    time.sleep(1)
    webbrowser.open(f'http://{HOST}:{PORT}/dashboard.html')
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Frontend server stopped")


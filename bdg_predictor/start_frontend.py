"""
Frontend Server Module
Simple HTTP server to serve the BDG Prediction Dashboard.
"""

import os
import sys
import json
import argparse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional

from error_logger import get_logger

logger = get_logger()


class DashboardHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler for the dashboard."""
    
    def do_GET(self):
        """Handle GET requests."""
        # Health check endpoint
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            
            response = {
                "status": "healthy",
                "service": "BDG Dashboard Frontend",
                "timestamp": __import__('datetime').datetime.now().isoformat()
            }
            self.wfile.write(json.dumps(response).encode())
            return
        
        # Serve index.html for root
        if self.path == "/" or self.path == "":
            self.path = "/index.html"
        
        # Call parent implementation for file serving
        super().do_GET()
    
    def log_message(self, format, *args):
        """Custom logging."""
        logger.debug(f"{self.client_address[0]} - {format % args}")


class FrontendServer:
    """Frontend HTTP server wrapper."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        """Initialize frontend server."""
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
    
    def start(self) -> bool:
        """Start the frontend server."""
        try:
            # Change to the directory where index.html is located
            # (This script should be in the same directory as index.html)
            
            # Create server
            self.server = HTTPServer((self.host, self.port), DashboardHandler)
            
            logger.info("="*70)
            logger.info("STARTING FRONTEND SERVER")
            logger.info("="*70)
            logger.info(f"Frontend server started at http://{self.host}:{self.port}")
            logger.info(f"Dashboard: http://{self.host}:{self.port}/index.html")
            logger.info(f"Health endpoint: http://{self.host}:{self.port}/health")
            logger.info("Press Ctrl+C to stop")
            logger.info("="*70)
            
            print(f"\n✓ Frontend Server running at http://{self.host}:{self.port}")
            print(f"  Dashboard: http://{self.host}:{self.port}/index.html\n")
            
            self.server.serve_forever()
            return True
        
        except OSError as e:
            msg = f"Cannot start frontend server on {self.host}:{self.port}: {e}"
            logger.error(msg, error_code="FRONTEND_START_ERROR")
            return False
        except KeyboardInterrupt:
            logger.info("Frontend server stopped by user")
            return True
        except Exception as e:
            msg = f"Frontend server error: {e}"
            logger.error(msg, error_code="FRONTEND_ERROR")
            return False
        finally:
            if self.server:
                self.server.server_close()
                logger.info("Frontend server closed")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="BDG Dashboard Frontend Server")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    
    args = parser.parse_args()
    
    server = FrontendServer(args.host, args.port)
    success = server.start()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

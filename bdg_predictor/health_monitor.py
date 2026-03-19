"""
Health Monitor Module
Real-time monitoring of backend and frontend server health.
"""

import json
import time
import sys
import urllib.request
import urllib.error
from typing import Dict, Optional
from datetime import datetime

from error_logger import get_logger

logger = get_logger()


class HealthMonitor:
    """Monitor health of multiple servers."""
    
    def __init__(self, config_path: str = "startup_config.json"):
        """Initialize health monitor."""
        self.config = self._load_config(config_path)
        self.servers = self.config.get("servers", {})
        self.health_config = self.config.get("health_check", {})
        self.health_status: Dict[str, Dict] = {}
    
    def _load_config(self, config_path: str) -> Dict:
        """Load startup configuration."""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load config: {e}")
            return {}
    
    def check_server_health(self, server_name: str, server_config: Dict) -> Dict:
        """Check health of a single server."""
        host = server_config.get("host", "127.0.0.1")
        port = server_config.get("port")
        
        if not port:
            return {"status": "unknown", "error": "No port configured"}
        
        health_url = f"http://{host}:{port}/health"
        timeout = self.health_config.get("timeout_seconds", 3)
        
        try:
            req = urllib.request.Request(health_url)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode())
                return {
                    "status": data.get("status", "unknown"),
                    "service": data.get("service", server_name),
                    "timestamp": datetime.now().isoformat(),
                    "url": health_url,
                    "response_code": response.status
                }
        
        except urllib.error.URLError as e:
            return {
                "status": "offline",
                "error": str(e),
                "url": health_url,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "url": health_url,
                "timestamp": datetime.now().isoformat()
            }
    
    def monitor_continuous(self, duration_seconds: Optional[int] = None) -> None:
        """Continuously monitor server health."""
        interval = self.health_config.get("interval_seconds", 5)
        
        logger.info("="*70)
        logger.info("HEALTH MONITORING STARTED")
        logger.info("="*70)
        
        start_time = time.time()
        check_count = 0
        
        try:
            while True:
                if duration_seconds and (time.time() - start_time) > duration_seconds:
                    break
                
                check_count += 1
                self._perform_health_check()
                self._display_status(check_count)
                
                time.sleep(interval)
        
        except KeyboardInterrupt:
            logger.info("Health monitoring stopped by user")
        except Exception as e:
            logger.error(f"Monitor error: {e}", error_code="MONITOR_ERROR")
        finally:
            self._print_summary(check_count)
    
    def _perform_health_check(self) -> None:
        """Perform health check on all servers."""
        for server_name, server_config in self.servers.items():
            status = self.check_server_health(server_name, server_config)
            self.health_status[server_name] = status
            
            # Log errors if configured
            if self.health_config.get("log_errors") and status["status"] != "healthy":
                logger.warning(
                    f"Server {server_name} status: {status['status']} - {status.get('error', 'unknown')}"
                )
    
    def _display_status(self, check_number: int) -> None:
        """Display current health status."""
        print("\n" + "="*70)
        print(f" HEALTH CHECK #{check_number} - {datetime.now().strftime('%H:%M:%S')}")
        print("="*70)
        
        all_healthy = True
        
        for server_name, status in self.health_status.items():
            status_str = status.get("status", "unknown").upper()
            
            # Color coding (simple text indicators)
            if status["status"] == "healthy":
                indicator = "✓"
            elif status["status"] == "offline":
                indicator = "✗"
                all_healthy = False
            else:
                indicator = "?"
                all_healthy = False
            
            print(f"\n{indicator} {server_name}")
            print(f"   Status: {status_str}")
            
            if "service" in status:
                print(f"   Service: {status['service']}")
            if "url" in status:
                print(f"   URL: {status['url']}")
            if "error" in status:
                print(f"   Error: {status['error']}")
            
            print(f"   Checked: {status.get('timestamp', 'unknown')}")
        
        print("\n" + "="*70)
        
        if all_healthy:
            print("✓ All systems operational")
        else:
            print("⚠ Some services may be unavailable")
        
        print("="*70)
    
    def _print_summary(self, total_checks: int) -> None:
        """Print monitoring summary."""
        print("\n" + "="*70)
        print(" HEALTH MONITORING SUMMARY")
        print("="*70)
        print(f"Total health checks: {total_checks}")
        print(f"Servers monitored: {len(self.servers)}")
        print(f"Final status:")
        
        for server_name, status in self.health_status.items():
            status_str = status.get("status", "unknown").upper()
            print(f"  • {server_name}: {status_str}")
        
        print("="*70 + "\n")
    
    def get_status_summary(self) -> Dict:
        """Get current status summary."""
        return {
            "timestamp": datetime.now().isoformat(),
            "servers": self.health_status,
            "all_healthy": all(
                s.get("status") == "healthy" 
                for s in self.health_status.values()
            )
        }


def main():
    """Main entry point for health monitor."""
    import argparse
    
    parser = argparse.ArgumentParser(description="BDG Health Monitor")
    parser.add_argument("--duration", type=int, help="Monitor for N seconds")
    
    args = parser.parse_args()
    
    monitor = HealthMonitor()
    monitor.monitor_continuous(duration_seconds=args.duration)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

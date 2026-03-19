"""
Environment Check Module
Pre-flight validation of Python version, dependencies, and configuration.
"""

import os
import sys
import json
import subprocess
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from error_logger import get_logger

logger = get_logger()


class EnvironmentChecker:
    """Check system environment and project dependencies."""
    
    def __init__(self, config_path: str = "startup_config.json"):
        """Initialize environment checker."""
        self.config_path = config_path
        self.config = self._load_config()
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def _load_config(self) -> Dict:
        """Load startup configuration."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load config: {e}, using defaults")
            return {"python": {"min_version": "3.8"}, "paths": {}}
    
    def check_python_version(self) -> bool:
        """Check if Python version meets requirements."""
        min_version = self.config.get("python", {}).get("min_version", "3.8")
        min_major, min_minor = map(int, min_version.split('.'))
        curr_major, curr_minor = sys.version_info[:2]
        
        logger.info(f"Python version: {curr_major}.{curr_minor}.{sys.version_info.micro}")
        
        if (curr_major, curr_minor) < (min_major, min_minor):
            msg = f"Python {min_version}+ required, found {curr_major}.{curr_minor}"
            logger.error(msg, error_code="PYTHON_VERSION_ERROR")
            self.errors.append(msg)
            return False
        
        logger.info("✓ Python version check passed")
        return True
    
    def check_pip_installed(self) -> bool:
        """Check if pip is available."""
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            logger.info("✓ pip is available")
            return True
        except Exception as e:
            msg = f"pip not available: {e}"
            logger.error(msg, error_code="PIP_NOT_FOUND")
            self.errors.append(msg)
            return False
    
    def check_requirements(self) -> Tuple[bool, List[str]]:
        """Check if all required packages are installed."""
        req_file = self.config.get("paths", {}).get("requirements", "requirements.txt")
        
        if not os.path.exists(req_file):
            msg = f"Requirements file not found: {req_file}"
            logger.warning(msg)
            self.warnings.append(msg)
            return True, []
        
        missing_packages = []
        
        try:
            with open(req_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    # Extract package name (handle version specs)
                    pkg_name = line.split('>=')[0].split('==')[0].split('<')[0].split('>')[0].strip()
                    
                    try:
                        __import__(pkg_name)
                    except ImportError:
                        missing_packages.append(pkg_name)
                        logger.warning(f"Missing package: {pkg_name}")
        
        except Exception as e:
            logger.warning(f"Error checking requirements: {e}")
            return False, []
        
        if missing_packages:
            logger.warning(f"Missing packages: {', '.join(missing_packages)}")
            self.warnings.append(f"Missing {len(missing_packages)} package(s)")
            return False, missing_packages
        
        logger.info(f"✓ All required packages found")
        return True, []
    
    def check_firebase_config(self) -> bool:
        """Check if Firebase configuration exists."""
        firebase_path = self.config.get("paths", {}).get("firebase_config", "firebase-adminsdk.json")
        
        if os.path.exists(firebase_path):
            try:
                with open(firebase_path, 'r') as f:
                    json.load(f)
                logger.info(f"✓ Firebase config found: {firebase_path}")
                return True
            except Exception as e:
                msg = f"Firebase config invalid: {e}"
                logger.warning(msg)
                self.warnings.append(msg)
                return False
        else:
            msg = f"Firebase config not found: {firebase_path}"
            logger.warning(msg)
            self.warnings.append(msg)
            return False
    
    def check_ports_available(self) -> bool:
        """Check if required ports are available."""
        import socket
        
        servers = self.config.get("servers", {})
        ports_ok = True
        
        for server_name, server_config in servers.items():
            port = server_config.get("port")
            host = server_config.get("host", "127.0.0.1")
            
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                sock.close()
                
                if result == 0:
                    msg = f"Port {port} already in use (for {server_name})"
                    logger.warning(msg)
                    self.warnings.append(msg)
                    ports_ok = False
                else:
                    logger.info(f"✓ Port {port} available for {server_name}")
            except Exception as e:
                logger.debug(f"Could not check port {port}: {e}")
        
        return ports_ok
    
    def check_directories(self) -> bool:
        """Check if required directories exist and are writable."""
        log_dir = self.config.get("paths", {}).get("logs_dir", "logs")
        
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir)
                logger.info(f"✓ Created logs directory: {log_dir}")
            except Exception as e:
                msg = f"Cannot create logs directory: {e}"
                logger.error(msg, error_code="DIR_CREATE_ERROR")
                self.errors.append(msg)
                return False
        
        # Check write permissions
        try:
            test_file = os.path.join(log_dir, ".write_test")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            logger.info(f"✓ Logs directory is writable: {log_dir}")
            return True
        except Exception as e:
            msg = f"Logs directory not writable: {e}"
            logger.error(msg, error_code="DIR_WRITE_ERROR")
            self.errors.append(msg)
            return False
    
    def run_all_checks(self) -> Dict[str, bool]:
        """Run all environment checks."""
        logger.info("="*70)
        logger.info("RUNNING PRE-FLIGHT ENVIRONMENT CHECKS")
        logger.info("="*70)
        
        results = {
            "python_version": self.check_python_version(),
            "pip_installed": self.check_pip_installed(),
            "requirements": self.check_requirements()[0],
            "firebase_config": self.check_firebase_config(),
            "ports_available": self.check_ports_available(),
            "directories": self.check_directories(),
        }
        
        logger.info("="*70)
        
        return results
    
    def report(self) -> bool:
        """Print check report. Returns True if all critical checks passed."""
        print("\n" + "="*70)
        print(" ENVIRONMENT CHECK REPORT")
        print("="*70 + "\n")
        
        if not self.errors and not self.warnings:
            print("✓ All checks passed! System is ready to start.")
            print("="*70 + "\n")
            return True
        
        if self.errors:
            print("❌ CRITICAL ERRORS (must fix):\n")
            for error in self.errors:
                print(f"  • {error}")
            print()
        
        if self.warnings:
            print("⚠ WARNINGS (non-critical):\n")
            for warning in self.warnings:
                print(f"  • {warning}")
            print()
        
        print("="*70)
        print(f"Log file: {logger.log_file}")
        print("="*70 + "\n")
        
        return len(self.errors) == 0


def main():
    """Run environment checks."""
    checker = EnvironmentChecker()
    checker.run_all_checks()
    success = checker.report()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

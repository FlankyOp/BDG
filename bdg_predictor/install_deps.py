"""
Dependency Installer Module
Automatically install missing Python packages.
"""

import subprocess
import sys
import os
from typing import List, Optional

from error_logger import get_logger

logger = get_logger()


class DependencyInstaller:
    """Handle automatic installation of project dependencies."""
    
    def __init__(self, requirements_file: str = "requirements.txt"):
        """Initialize dependency installer."""
        self.requirements_file = requirements_file
    
    def check_package_installed(self, package_name: str) -> bool:
        """Check if a package is installed."""
        try:
            __import__(package_name)
            return True
        except ImportError:
            return False
    
    def get_missing_packages(self) -> List[str]:
        """Get list of missing packages from requirements.txt."""
        if not os.path.exists(self.requirements_file):
            logger.warning(f"Requirements file not found: {self.requirements_file}")
            return []
        
        missing = []
        
        try:
            with open(self.requirements_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    # Extract package name (handle version specs)
                    pkg_name = line.split('>=')[0].split('==')[0].split('<')[0].split('>')[0].split('[')[0].strip()
                    
                    if pkg_name and not self.check_package_installed(pkg_name):
                        missing.append(pkg_name)
                        logger.debug(f"Missing: {pkg_name}")
        
        except Exception as e:
            logger.error(f"Error reading requirements: {e}", error_code="REQ_READ_ERROR")
        
        return missing
    
    def install_package(self, package_spec: str) -> bool:
        """Install a single package using pip."""
        try:
            logger.info(f"Installing {package_spec}...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package_spec, "-q"],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                logger.info(f"✓ Successfully installed {package_spec}")
                return True
            else:
                msg = f"Failed to install {package_spec}: {result.stderr}"
                logger.error(msg, error_code="INSTALL_ERROR")
                return False
        
        except subprocess.TimeoutExpired:
            msg = f"Installation timeout for {package_spec}"
            logger.error(msg, error_code="INSTALL_TIMEOUT")
            return False
        except Exception as e:
            msg = f"Installation failed for {package_spec}: {e}"
            logger.error(msg, error_code="INSTALL_EXCEPTION")
            return False
    
    def install_all(self) -> bool:
        """Install all requirements from requirements.txt."""
        logger.info("="*70)
        logger.info("INSTALLING DEPENDENCIES")
        logger.info("="*70)
        
        try:
            logger.info(f"Running: pip install -r {self.requirements_file}")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", self.requirements_file],
                capture_output=False,
                text=True,
                timeout=600
            )
            
            if result.returncode == 0:
                logger.info("✓ All dependencies installed successfully")
                return True
            else:
                logger.error("Some dependencies failed to install", error_code="BULK_INSTALL_ERROR")
                return False
        
        except subprocess.TimeoutExpired:
            logger.error("Installation timeout", error_code="INSTALL_TIMEOUT")
            return False
        except Exception as e:
            logger.error(f"Installation failed: {e}", error_code="INSTALL_EXCEPTION")
            return False
    
    def upgrade_pip(self) -> bool:
        """Upgrade pip to the latest version."""
        try:
            logger.info("Upgrading pip...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "pip", "-q"],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                logger.info("✓ pip upgraded successfully")
                return True
            else:
                logger.warning(f"pip upgrade warning: {result.stderr}")
                return True  # Non-critical
        
        except Exception as e:
            logger.warning(f"pip upgrade failed: {e}")
            return True  # Non-critical


def main():
    """Main entry point for dependency installation."""
    installer = DependencyInstaller()
    
    print("\n" + "="*70)
    print(" DEPENDENCY INSTALLATION")
    print("="*70 + "\n")
    
    # Check for missing packages
    missing = installer.get_missing_packages()
    
    if missing:
        print(f"Found {len(missing)} missing package(s):")
        for pkg in missing:
            print(f"  • {pkg}")
        print()
        
        # Install all
        success = installer.install_all()
        
        if success:
            print("\n✓ All dependencies installed!")
            return 0
        else:
            print("\n❌ Some dependencies failed to install")
            return 1
    else:
        print("✓ All dependencies are already installed")
        return 0


if __name__ == "__main__":
    sys.exit(main())

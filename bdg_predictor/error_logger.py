"""
Error Logger Module
Centralized error logging and reporting for startup and runtime errors.
"""

import logging
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional


class ErrorLogger:
    """Centralized error logging with file and console output."""
    
    def __init__(self, log_dir: str = "logs"):
        """Initialize error logger."""
        self.log_dir = log_dir
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        log_file = os.path.join(
            log_dir,
            f"startup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        
        # Configure logging
        self.logger = logging.getLogger("BDGStartup")
        self.logger.setLevel(logging.DEBUG)
        
        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self.log_file = log_file
        self.errors: Dict[str, Any] = {}
    
    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, error_code: Optional[str] = None, **kwargs: Any) -> None:
        """Log error message and track it."""
        self.logger.error(message, **kwargs)
        if error_code:
            self.errors[error_code] = {
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "severity": "error"
            }
    
    def critical(self, message: str, error_code: Optional[str] = None, **kwargs: Any) -> None:
        """Log critical error and track it."""
        self.logger.critical(message, **kwargs)
        if error_code:
            self.errors[error_code] = {
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "severity": "critical"
            }
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self.logger.debug(message, **kwargs)
    
    def report_errors(self) -> bool:
        """Print error report. Returns True if there are errors."""
        if not self.errors:
            return False
        
        print("\n" + "="*70)
        print(" STARTUP ERRORS DETECTED")
        print("="*70)
        
        for code, details in self.errors.items():
            severity = details.get("severity", "error").upper()
            print(f"\n[{severity}] {code}")
            print(f"  Message: {details.get('message')}")
            print(f"  Time: {details.get('timestamp')}")
        
        print("\n" + "="*70)
        print(f"Log file: {self.log_file}")
        print("="*70 + "\n")
        
        return True
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get error summary as dictionary."""
        return {
            "total_errors": len(self.errors),
            "errors": self.errors,
            "log_file": self.log_file,
            "timestamp": datetime.now().isoformat()
        }


# Global instance
_global_logger: Optional[ErrorLogger] = None


def get_logger(log_dir: str = "logs") -> ErrorLogger:
    """Get or create global error logger."""
    global _global_logger
    if _global_logger is None:
        _global_logger = ErrorLogger(log_dir)
    return _global_logger


if __name__ == "__main__":
    # Test the error logger
    logger = get_logger()
    logger.info("Testing error logger")
    logger.warning("This is a warning")
    logger.error("This is an error", error_code="TEST_ERR_001")
    logger.critical("This is critical", error_code="TEST_ERR_002")
    logger.report_errors()

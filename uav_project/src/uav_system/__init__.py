"""
UAV System Package

A professional UAV control and monitoring system.
"""

__version__ = "1.0.0"
__author__ = "UAV Development Team"

# Import core components for easy access
from .core.exceptions import UAVException, ConnectionError, TelemetryError
from .core.logging_config import get_logger

# Package level logger
logger = get_logger(__name__)

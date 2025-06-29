"""
Custom exceptions for the UAV system.
"""


class UAVException(Exception):
    """Base exception for all UAV system errors."""
    pass


class ConnectionError(UAVException):
    """Raised when there are connection issues with the UAV."""
    pass


class TelemetryError(UAVException):
    """Raised when there are telemetry data issues."""
    pass


class FlightControlError(UAVException):
    """Raised when there are flight control issues."""
    pass


class SensorError(UAVException):
    """Raised when there are sensor-related issues."""
    pass


class ComputerVisionError(UAVException):
    """Raised when there are computer vision processing issues."""
    pass


class ConfigurationError(UAVException):
    """Raised when there are configuration issues."""
    pass


class HardwareError(UAVException):
    """Raised when there are hardware-related issues."""
    pass

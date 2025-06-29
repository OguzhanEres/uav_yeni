"""
Application settings and configuration management.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings class."""
    
    # Base paths
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
    SRC_ROOT = PROJECT_ROOT / "src"
    DATA_ROOT = PROJECT_ROOT / "data"
    CONFIG_ROOT = PROJECT_ROOT / "config"
    
    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///data/uav_system.db")
    
    # Hardware settings
    DEFAULT_SERIAL_PORT: str = os.getenv("DEFAULT_SERIAL_PORT", "COM8")
    DEFAULT_BAUD_RATE: int = int(os.getenv("DEFAULT_BAUD_RATE", "57600"))
    CAMERA_INDEX: int = int(os.getenv("CAMERA_INDEX", "0"))
    
    # Network settings
    MAVLINK_UDP_PORT: int = int(os.getenv("MAVLINK_UDP_PORT", "14550"))
    WEB_SERVER_PORT: int = int(os.getenv("WEB_SERVER_PORT", "8000"))
    MAP_SERVER_PORT: int = int(os.getenv("MAP_SERVER_PORT", "8150"))
    
    # Logging settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE_PATH: str = os.getenv("LOG_FILE_PATH", "data/logs/system.log")
    
    # Computer Vision settings
    YOLO_MODEL_PATH: str = os.getenv(
        "YOLO_MODEL_PATH", 
        "src/uav_system/computer_vision/models/pretrained/best.pt"
    )
    DETECTION_CONFIDENCE_THRESHOLD: float = float(
        os.getenv("DETECTION_CONFIDENCE_THRESHOLD", "0.5")
    )
    TRACKING_UPDATE_INTERVAL: int = int(os.getenv("TRACKING_UPDATE_INTERVAL", "15"))
    
    # Flight Control settings
    MAX_ALTITUDE: float = float(os.getenv("MAX_ALTITUDE", "500"))
    DEFAULT_TAKEOFF_ALTITUDE: float = float(os.getenv("DEFAULT_TAKEOFF_ALTITUDE", "50"))
    GEOFENCE_RADIUS: float = float(os.getenv("GEOFENCE_RADIUS", "1000"))
    
    # Telemetry settings
    TELEMETRY_UPDATE_RATE: int = int(os.getenv("TELEMETRY_UPDATE_RATE", "200"))
    MAP_UPDATE_RATE: int = int(os.getenv("MAP_UPDATE_RATE", "1000"))
    
    @classmethod
    def get_absolute_path(cls, relative_path: str) -> Path:
        """Convert relative path to absolute path from project root."""
        return cls.PROJECT_ROOT / relative_path
    
    @classmethod
    def ensure_directory(cls, path: Path) -> None:
        """Ensure directory exists."""
        path.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def get_config_dict(cls) -> Dict[str, Any]:
        """Get all settings as a dictionary."""
        return {
            key: getattr(cls, key)
            for key in dir(cls)
            if not key.startswith('_') and not callable(getattr(cls, key))
        }


# Global settings instance
settings = Settings()

# Ensure required directories exist
settings.ensure_directory(settings.DATA_ROOT / "logs")
settings.ensure_directory(settings.DATA_ROOT / "recordings" / "video")
settings.ensure_directory(settings.DATA_ROOT / "recordings" / "telemetry")
settings.ensure_directory(settings.DATA_ROOT / "maps")
settings.ensure_directory(settings.DATA_ROOT / "calibration")

"""
System constants for the UAV system.
"""

# Flight modes
FLIGHT_MODES = {
    'MANUAL': 'Manual',
    'AUTO': 'Auto',
    'GUIDED': 'Guided',
    'LOITER': 'Loiter',
    'RTL': 'Return to Launch',
    'TAKEOFF': 'Takeoff',
    'LAND': 'Land',
    'STABILIZE': 'Stabilize',
    'ALT_HOLD': 'Altitude Hold'
}

# MAVLink message types
MAVLINK_MESSAGES = {
    'HEARTBEAT': 0,
    'SYS_STATUS': 1,
    'SYSTEM_TIME': 2,
    'GPS_RAW_INT': 24,
    'ATTITUDE': 30,
    'GLOBAL_POSITION_INT': 33,
    'VFR_HUD': 74,
    'COMMAND_LONG': 76,
    'COMMAND_ACK': 77
}

# Serial communication settings
SERIAL_TIMEOUTS = {
    'CONNECT': 15,
    'READ': 5,
    'WRITE': 5
}

BAUD_RATES = [1200, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]

# Computer vision constants
DETECTION_CLASSES = {
    0: 'person',
    1: 'bicycle',
    2: 'car',
    # Add more as needed
}

COLOR_CHANNELS = {
    'BGR': 3,
    'RGB': 3,
    'GRAY': 1
}

# UI constants
DEFAULT_WINDOW_SIZE = (1280, 720)
DEFAULT_MAP_SIZE = (640, 480)
DEFAULT_HUD_SIZE = (320, 240)

# Update intervals (milliseconds)
UPDATE_INTERVALS = {
    'TELEMETRY': 200,
    'HUD': 100,
    'MAP': 500,
    'CAMERA': 33,  # ~30 FPS
    'STATUS': 1000
}

# Network timeouts (seconds)
NETWORK_TIMEOUTS = {
    'CONNECTION': 10,
    'READ': 5,
    'WRITE': 5,
    'MAP_SERVER': 20
}

# File extensions
SUPPORTED_VIDEO_FORMATS = ['.mp4', '.avi', '.mov', '.mkv']
SUPPORTED_IMAGE_FORMATS = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
SUPPORTED_LOG_FORMATS = ['.log', '.txt', '.csv']

# Safety limits
SAFETY_LIMITS = {
    'MAX_ALTITUDE': 500,  # meters
    'MIN_BATTERY_VOLTAGE': 10.5,  # volts
    'MAX_WIND_SPEED': 15,  # m/s
    'MIN_GPS_SATELLITES': 6
}

# Error codes
ERROR_CODES = {
    'CONNECTION_FAILED': 1001,
    'SENSOR_FAILURE': 1002,
    'COMMUNICATION_TIMEOUT': 1003,
    'INVALID_COMMAND': 1004,
    'SAFETY_VIOLATION': 1005,
    'HARDWARE_ERROR': 1006,
    'SOFTWARE_ERROR': 1007
}

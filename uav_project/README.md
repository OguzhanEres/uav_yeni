# UAV Control System

A professional, modular UAV (Unmanned Aerial Vehicle) control and monitoring system with real-time telemetry, computer vision, and ground control station capabilities.

## Features

- **Flight Control**: Complete flight control with multiple modes (AUTO, GUIDED, RTL, TAKEOFF)
- **Real-time Telemetry**: Live data streaming and monitoring
- **Computer Vision**: Object detection and tracking using YOLO and KCF
- **Ground Control Station**: Professional PyQt5-based GUI interface
- **Communication**: MAVLink and DroneKit protocol support
- **Map Integration**: Leaflet-based mapping with live UAV tracking
- **Camera System**: Real-time video streaming and processing
- **Mission Planning**: Waypoint management and autonomous flight

## 🚀 Quick Start

### Windows Users
The easiest way to run the application on Windows:
```powershell
# Double-click run_gcs.bat or run in PowerShell:
.\run_gcs.bat

# Or manually:
python main.py
```

### Linux/Mac Users  
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application  
python3 main.py
```

### Prerequisites

## Architecture

The system follows a modular architecture with clear separation of concerns:

- `src/uav_system/core/`: Foundation classes and utilities
- `src/uav_system/flight_control/`: Flight control algorithms
- `src/uav_system/communication/`: Protocol implementations
- `src/uav_system/sensors/`: Sensor interfaces
- `src/uav_system/computer_vision/`: Detection and tracking
- `src/uav_system/ui/`: User interfaces (Desktop, Web, CLI)

## Documentation

- [Installation Guide](docs/installation.md)
- [User Guide](docs/user_guide.md)
- [Developer Guide](docs/developer_guide.md)
- [API Reference](docs/api_reference/)

## License

MIT License - see LICENSE file for details.

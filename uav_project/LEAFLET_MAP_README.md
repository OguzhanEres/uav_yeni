# Hüma UAV Ground Control Station - Leaflet Map Integration

## 🗺️ Map System Refactoring

This refactoring replaces the previous black-screen, non-rendering canvas map with a smooth, online **Leaflet.js map integration** that provides real-time UAV tracking and mission planning capabilities.

## ✨ Key Improvements

### 1. **Online Leaflet Map (`leaflet_map_widget.py`)**
- 🌐 **Real tile-based mapping** using OpenStreetMap and satellite imagery
- 📍 **Live UAV position tracking** with animated markers
- ✈️ **Flight path visualization** with smooth polylines
- 🎯 **Interactive waypoint management**
- 📱 **Responsive design** that handles window resizing
- 🔄 **Auto-refresh capabilities**

### 2. **Enhanced Main Application (`main.py`)**
- ⚡ **QtWebEngine optimization** with GPU issue workarounds
- 🚀 **Improved startup sequence** with splash screen
- 🛠️ **Better error handling** and fallback mechanisms
- 📋 **Enhanced dependency checking**

### 3. **Upgraded Main Window (`main_window.py`)**
- 🔗 **Seamless map integration** with automatic resizing
- 📡 **Real-time telemetry updates** to map display
- 🎮 **Enhanced drone controls** (DroneKit + MAVLink fallback)
- 🔄 **Live GPS tracking** with auto-centering

## 🚀 Quick Start

### Prerequisites
```bash
pip install -r requirements.txt
```

Required packages:
- `PyQt5>=5.15.0`
- `PyQtWebEngine>=5.15.0`
- `dronekit>=2.9.2`
- `pymavlink>=2.4.37`

### Running the Application
```bash
python main.py
```

## 🛠️ Technical Architecture

### Map Widget Structure
```
LeafletOnlineMap (QWidget)
├── Control Panel (buttons for satellite/street view, flight path, etc.)
├── QWebEngineView (displays Leaflet map)
├── Loading/Error States
└── JavaScript Bridge (Qt ↔ Leaflet communication)
```

### Map Features
- **📍 UAV Marker**: Animated red circle with pulse effect
- **✈️ Flight Path**: Real-time polyline showing UAV track history
- **📌 Waypoints**: Interactive blue markers for mission planning
- **🗺️ Tile Layers**: Street and satellite view switching
- **🎯 Click Handling**: Coordinate display and interaction feedback

### JavaScript Integration
The map uses a robust JavaScript bridge that provides:
```javascript
// Core functions callable from Python
window.updateUAVPosition(lat, lon, heading)
window.centerOnUAV()
window.clearFlightPath()
window.addWaypoint(lat, lon, name, id)
window.removeWaypoint(id)
window.setMapCenter(lat, lon, zoom)
window.toggleSatelliteLayer()
window.forceResize()
```

## 🔧 Troubleshooting

### Common Issues

**Black screen or map not loading:**
```bash
# Install missing WebEngine
pip install PyQtWebEngine

# Check internet connection
# Ensure firewall allows the application
```

**Import errors:**
```bash
# Ensure all dependencies are installed
pip install -r requirements.txt

# Check Python path includes src/
```

**GPS/Telemetry not updating:**
- Verify drone connection string
- Check MAVLink/DroneKit setup
- Ensure telemetry timer is running

### Testing
Run the system test to verify everything is working:
```bash
python test_system.py
```

## 📁 File Structure
```
uav_project/
├── main.py                     # 🚀 Enhanced application entry point
├── requirements.txt             # 📦 Updated dependencies  
├── test_system.py              # 🧪 System verification script
└── src/uav_system/ui/desktop/
    ├── leaflet_map_widget.py   # 🗺️ NEW: Leaflet online map
    ├── main_window.py          # 🔄 UPDATED: Enhanced GCS window
    └── resources/              # 📁 Map HTML storage
        └── leaflet_map.html    # 🌐 Generated map file
```

## 🌟 Key Features

### Real-time UAV Tracking
- GPS position updates every 100ms (configurable)
- Smooth marker animation and movement
- Flight path history with configurable max points
- Auto-centering on first GPS fix

### Interactive Map Controls
- **Street/Satellite toggle**: Switch between OpenStreetMap and Esri satellite
- **Flight path toggle**: Show/hide UAV track history
- **Center on UAV**: Quick navigation to current UAV position
- **Clear track**: Reset flight path history
- **Refresh**: Force map redraw and resize

### Robust Connection Handling
1. **Primary**: DroneKit connection for COM ports
2. **Fallback**: MAVLink client for UDP/TCP
3. **Auto-retry**: Connection persistence
4. **Status updates**: Real-time connection feedback

### Window Management
- **Auto-resize**: Map fills container on window resize
- **Responsive layout**: Controls adapt to window size
- **Error handling**: Graceful fallbacks for missing components

## 🔮 Future Enhancements

Planned improvements include:
- 🛡️ **No-fly zone overlays**
- 📐 **Mission planning tools**
- 📊 **Telemetry data logging**
- 🎥 **Video overlay integration**
- 🗺️ **Offline map caching**

## 💬 Support

For issues or questions:
1. Run `python test_system.py` to diagnose problems
2. Check log files in `data/logs/system.log`
3. Verify all dependencies are correctly installed
4. Ensure internet connectivity for map tiles

---
🚁 **Happy Flying with Hüma UAV GCS!** 🚁

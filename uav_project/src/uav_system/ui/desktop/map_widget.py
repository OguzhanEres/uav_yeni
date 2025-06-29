"""
Leaflet Map Widget for UAV Ground Control Station
Provides interactive map display with UAV tracking and mission planning.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt5.QtCore import QTimer, pyqtSignal, QUrl, pyqtSlot
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEngineProfile
from ...core.logging_config import get_logger

logger = get_logger(__name__)


class LeafletMap(QWidget):
    """Interactive map widget using Leaflet.js through QWebEngine."""
    
    # Signals
    map_clicked = pyqtSignal(float, float)  # lat, lon
    waypoint_added = pyqtSignal(float, float, str)  # lat, lon, name
    waypoint_removed = pyqtSignal(str)  # waypoint_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Map state
        self.current_lat = 39.9334  # Default: Ankara
        self.current_lon = 32.8597
        self.zoom_level = 13
        self.map_loaded = False
        
        # UAV tracking
        self.uav_position = None
        self.uav_track = []
        self.max_track_points = 1000
        
        # Waypoints and missions
        self.waypoints = {}
        self.current_mission = []
        
        # Map layers
        self.show_satellite = True
        self.show_flight_path = True
        self.show_restricted_zones = False
        
        self.setup_ui()
        self.setup_map()
        
        logger.info("Leaflet Map Widget initialized")
    
    def setup_ui(self):
        """Setup the map user interface."""
        layout = QVBoxLayout(self)
        
        # Control panel
        control_layout = QHBoxLayout()
        
        # Map type buttons
        self.btn_satellite = QPushButton("Satellite")
        self.btn_satellite.setCheckable(True)
        self.btn_satellite.setChecked(True)
        self.btn_satellite.clicked.connect(self.toggle_satellite_layer)
        control_layout.addWidget(self.btn_satellite)
        
        self.btn_street = QPushButton("Street")
        self.btn_street.setCheckable(True)
        self.btn_street.clicked.connect(self.toggle_street_layer)
        control_layout.addWidget(self.btn_street)
        
        # Flight path toggle
        self.btn_flight_path = QPushButton("Flight Path")
        self.btn_flight_path.setCheckable(True)
        self.btn_flight_path.setChecked(True)
        self.btn_flight_path.clicked.connect(self.toggle_flight_path)
        control_layout.addWidget(self.btn_flight_path)
        
        # Clear track button
        self.btn_clear_track = QPushButton("Clear Track")
        self.btn_clear_track.clicked.connect(self.clear_track)
        control_layout.addWidget(self.btn_clear_track)
        
        # Center on UAV button
        self.btn_center_uav = QPushButton("Center on UAV")
        self.btn_center_uav.clicked.connect(self.center_on_uav)
        control_layout.addWidget(self.btn_center_uav)
        
        control_layout.addStretch()
        
        # Coordinates display
        self.lbl_coordinates = QLabel("Lat: 0.000000, Lon: 0.000000")
        control_layout.addWidget(self.lbl_coordinates)
        
        layout.addLayout(control_layout)
        
        # Web engine view for map
        self.web_view = QWebEngineView()
        self.web_view.setMinimumSize(800, 600)
        
        # Configure web engine settings
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        
        layout.addWidget(self.web_view)
        
        self.setLayout(layout)
    
    def setup_map(self):
        """Initialize the Leaflet map."""
        try:
            # Create map HTML
            map_html = self.create_map_html()
            
            # Save to temporary file
            map_file_path = Path(__file__).parent / "resources" / "map.html"
            map_file_path.parent.mkdir(exist_ok=True)
            
            with open(map_file_path, 'w', encoding='utf-8') as f:
                f.write(map_html)
            
            # Load map
            self.web_view.load(QUrl.fromLocalFile(str(map_file_path.absolute())))
            self.web_view.loadFinished.connect(self.on_map_loaded)
            
            logger.info(f"Map HTML created at: {map_file_path}")
            
        except Exception as e:
            logger.error(f"Failed to setup map: {e}")
    
    def create_map_html(self) -> str:
        """Create the HTML content for the Leaflet map."""
        html_template = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>UAV Map</title>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            
            <!-- Leaflet CSS -->
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
                  integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
                  crossorigin=""/>
            
            <style>
                body { margin: 0; padding: 0; }
                #map { height: 100vh; width: 100vw; }
                .leaflet-control-custom {
                    background: white;
                    padding: 5px;
                    border-radius: 5px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.3);
                }
            </style>
        </head>
        <body>
            <div id="map"></div>
            
            <!-- Leaflet JavaScript -->
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
                    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
                    crossorigin=""></script>
            
            <script>
                // Initialize map
                var map = L.map('map').setView([{lat}, {lon}], {zoom});
                
                // Base layers
                var streetLayer = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    attribution: '© OpenStreetMap contributors'
                }});
                
                var satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                    attribution: 'Tiles © Esri'
                }});
                
                // Add default layer
                satelliteLayer.addTo(map);
                
                // UAV marker and track
                var uavIcon = L.icon({{
                    iconUrl: 'data:image/svg+xml;base64,' + btoa(`
                        <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
                            <polygon points="16,2 24,10 20,14 16,10 12,14 8,10" fill="red" stroke="white" stroke-width="2"/>
                            <circle cx="16" cy="16" r="2" fill="white"/>
                        </svg>
                    `),
                    iconSize: [32, 32],
                    iconAnchor: [16, 16]
                }});
                
                var uavMarker = null;
                var flightPath = L.polyline([], {{color: 'red', weight: 3, opacity: 0.8}});
                flightPath.addTo(map);
                
                // Waypoint markers
                var waypoints = {{}};
                var waypointGroup = L.layerGroup().addTo(map);
                
                // Layer control
                var baseLayers = {{
                    "Street": streetLayer,
                    "Satellite": satelliteLayer
                }};
                
                var overlays = {{
                    "Flight Path": flightPath,
                    "Waypoints": waypointGroup
                }};
                
                L.control.layers(baseLayers, overlays).addTo(map);
                
                // Map click handler
                map.on('click', function(e) {{
                    // This will be handled by Qt
                    console.log('Map clicked:', e.latlng.lat, e.latlng.lng);
                }});
                
                // Functions callable from Qt
                window.updateUAVPosition = function(lat, lon, heading) {{
                    if (uavMarker) {{
                        map.removeLayer(uavMarker);
                    }}
                    
                    uavMarker = L.marker([lat, lon], {{
                        icon: uavIcon,
                        rotationAngle: heading
                    }}).addTo(map);
                    
                    // Add to flight path
                    flightPath.addLatLng([lat, lon]);
                    
                    console.log('UAV position updated:', lat, lon, heading);
                }};
                
                window.centerOnUAV = function() {{
                    if (uavMarker) {{
                        map.setView(uavMarker.getLatLng(), map.getZoom());
                    }}
                }};
                
                window.clearFlightPath = function() {{
                    flightPath.setLatLngs([]);
                }};
                
                window.addWaypoint = function(lat, lon, name, id) {{
                    var waypoint = L.marker([lat, lon]).addTo(waypointGroup);
                    waypoint.bindPopup(`<b>${{name}}</b><br>Lat: ${{lat.toFixed(6)}}<br>Lon: ${{lon.toFixed(6)}}`);
                    waypoints[id] = waypoint;
                    console.log('Waypoint added:', id, lat, lon, name);
                }};
                
                window.removeWaypoint = function(id) {{
                    if (waypoints[id]) {{
                        waypointGroup.removeLayer(waypoints[id]);
                        delete waypoints[id];
                        console.log('Waypoint removed:', id);
                    }}
                }};
                
                window.setMapCenter = function(lat, lon, zoom) {{
                    map.setView([lat, lon], zoom || map.getZoom());
                }};
                
                console.log('Map initialized');
            </script>
        </body>
        </html>
        '''.format(
            lat=self.current_lat,
            lon=self.current_lon,
            zoom=self.zoom_level
        )
        
        return html_template
    
    def on_map_loaded(self, success: bool):
        """Handle map load completion."""
        if success:
            self.map_loaded = True
            logger.info("Map loaded successfully")
            
            # Initialize with current position if available
            if self.uav_position:
                self.update_uav_position(
                    self.uav_position['lat'],
                    self.uav_position['lon'],
                    self.uav_position.get('heading', 0)
                )
        else:
            logger.error("Failed to load map")
    
    @pyqtSlot()
    def toggle_satellite_layer(self):
        """Toggle satellite layer."""
        self.show_satellite = self.btn_satellite.isChecked()
        if self.map_loaded:
            # Switch to satellite or street view
            layer_name = "Satellite" if self.show_satellite else "Street"
            self.web_view.page().runJavaScript(f"map.eachLayer(function(layer) {{ if (layer._url && layer._url.includes('arcgis')) {{ layer.remove(); }} }})")
            if self.show_satellite:
                self.web_view.page().runJavaScript("satelliteLayer.addTo(map)")
    
    @pyqtSlot()
    def toggle_street_layer(self):
        """Toggle street layer."""
        if self.btn_street.isChecked():
            self.btn_satellite.setChecked(False)
            self.show_satellite = False
            if self.map_loaded:
                self.web_view.page().runJavaScript("streetLayer.addTo(map)")
    
    @pyqtSlot()
    def toggle_flight_path(self):
        """Toggle flight path visibility."""
        self.show_flight_path = self.btn_flight_path.isChecked()
        if self.map_loaded:
            if self.show_flight_path:
                self.web_view.page().runJavaScript("flightPath.addTo(map)")
            else:
                self.web_view.page().runJavaScript("map.removeLayer(flightPath)")
    
    @pyqtSlot()
    def clear_track(self):
        """Clear the UAV flight track."""
        self.uav_track.clear()
        if self.map_loaded:
            self.web_view.page().runJavaScript("clearFlightPath()")
        logger.info("Flight track cleared")
    
    @pyqtSlot()
    def center_on_uav(self):
        """Center map on UAV position."""
        if self.map_loaded and self.uav_position:
            self.web_view.page().runJavaScript("centerOnUAV()")
            logger.info("Map centered on UAV")
    
    def update_uav_position(self, lat: float, lon: float, heading: float = 0):
        """Update UAV position on map."""
        try:
            self.uav_position = {'lat': lat, 'lon': lon, 'heading': heading}
            
            # Add to track
            self.uav_track.append((lat, lon))
            if len(self.uav_track) > self.max_track_points:
                self.uav_track.pop(0)
            
            # Update coordinates display
            self.lbl_coordinates.setText(f"Lat: {lat:.6f}, Lon: {lon:.6f}")
            
            # Update map if loaded
            if self.map_loaded:
                self.web_view.page().runJavaScript(
                    f"updateUAVPosition({lat}, {lon}, {heading})"
                )
            
            logger.debug(f"UAV position updated: {lat:.6f}, {lon:.6f}, heading: {heading:.1f}°")
            
        except Exception as e:
            logger.error(f"Error updating UAV position: {e}")
    
    def add_waypoint(self, lat: float, lon: float, name: str = None, waypoint_id: str = None):
        """Add a waypoint to the map."""
        try:
            if waypoint_id is None:
                waypoint_id = f"wp_{len(self.waypoints)}"
            
            if name is None:
                name = f"Waypoint {len(self.waypoints) + 1}"
            
            self.waypoints[waypoint_id] = {
                'lat': lat,
                'lon': lon,
                'name': name
            }
            
            if self.map_loaded:
                self.web_view.page().runJavaScript(
                    f"addWaypoint({lat}, {lon}, '{name}', '{waypoint_id}')"
                )
            
            self.waypoint_added.emit(lat, lon, name)
            logger.info(f"Waypoint added: {name} at {lat:.6f}, {lon:.6f}")
            
        except Exception as e:
            logger.error(f"Error adding waypoint: {e}")
    
    def remove_waypoint(self, waypoint_id: str):
        """Remove a waypoint from the map."""
        try:
            if waypoint_id in self.waypoints:
                del self.waypoints[waypoint_id]
                
                if self.map_loaded:
                    self.web_view.page().runJavaScript(f"removeWaypoint('{waypoint_id}')")
                
                self.waypoint_removed.emit(waypoint_id)
                logger.info(f"Waypoint removed: {waypoint_id}")
                
        except Exception as e:
            logger.error(f"Error removing waypoint: {e}")
    
    def set_map_center(self, lat: float, lon: float, zoom: int = None):
        """Set map center and zoom level."""
        try:
            self.current_lat = lat
            self.current_lon = lon
            if zoom is not None:
                self.zoom_level = zoom
            
            if self.map_loaded:
                zoom_param = zoom if zoom is not None else "null"
                self.web_view.page().runJavaScript(
                    f"setMapCenter({lat}, {lon}, {zoom_param})"
                )
            
            logger.info(f"Map center set to: {lat:.6f}, {lon:.6f}")
            
        except Exception as e:
            logger.error(f"Error setting map center: {e}")
    
    def load_mission(self, mission_waypoints: List[Dict[str, Any]]):
        """Load a mission with multiple waypoints."""
        try:
            # Clear existing waypoints
            for waypoint_id in list(self.waypoints.keys()):
                self.remove_waypoint(waypoint_id)
            
            # Add mission waypoints
            for i, wp in enumerate(mission_waypoints):
                waypoint_id = f"mission_wp_{i}"
                self.add_waypoint(
                    wp['lat'],
                    wp['lon'],
                    wp.get('name', f"Mission WP {i+1}"),
                    waypoint_id
                )
            
            self.current_mission = mission_waypoints
            logger.info(f"Mission loaded with {len(mission_waypoints)} waypoints")
            
        except Exception as e:
            logger.error(f"Error loading mission: {e}")
    
    def get_map_bounds(self) -> Dict[str, float]:
        """Get current map bounds."""
        # This would require JavaScript communication for real implementation
        return {
            'north': self.current_lat + 0.01,
            'south': self.current_lat - 0.01,
            'east': self.current_lon + 0.01,
            'west': self.current_lon - 0.01
        }

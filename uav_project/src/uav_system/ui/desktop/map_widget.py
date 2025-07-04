"""
Simple Canvas Map Widget for UAV Ground Control Station
Provides interactive map display with UAV tracking and mission planning using HTML5 Canvas.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QStackedWidget
from PyQt5.QtCore import QTimer, pyqtSignal, QUrl, pyqtSlot, Qt
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEngineProfile
from ...core.logging_config import get_logger

logger = get_logger(__name__)


class SimpleCanvasMap(QWidget):
    """Interactive map widget using HTML5 Canvas for fast rendering."""
    
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
        self.setup_debug_console()
        
        logger.info("Simple Canvas Map Widget initialized")
    
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
        
        # Test button for debugging
        self.btn_test_map = QPushButton("Test Map")
        self.btn_test_map.clicked.connect(self.test_map_functionality)
        control_layout.addWidget(self.btn_test_map)
        
        # Refresh button
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.force_refresh_map)
        control_layout.addWidget(self.btn_refresh)
        
        control_layout.addStretch()
        
        # Coordinates display
        self.lbl_coordinates = QLabel("Lat: 0.000000, Lon: 0.000000")
        control_layout.addWidget(self.lbl_coordinates)
        
        layout.addLayout(control_layout)
        
        # Web engine view for map
        self.web_view = QWebEngineView()
        self.web_view.setMinimumSize(800, 600)
        
        # Add loading status label
        self.loading_label = QLabel("Harita yükleniyor...")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 0.8);
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 20px;
                border-radius: 10px;
            }
        """)
        self.loading_label.setVisible(True)
        
        # Configure web engine settings
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.ErrorPageEnabled, True)
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        
        # Create a stacked layout for web view and loading label
        self.map_stack = QStackedWidget()
        self.map_stack.addWidget(self.loading_label)
        self.map_stack.addWidget(self.web_view)
        self.map_stack.setCurrentWidget(self.loading_label)
        
        layout.addWidget(self.map_stack)
        
        self.setLayout(layout)
    
    def setup_map(self):
        """Initialize the Canvas-based map."""
        try:
            self.loading_label.setText("Harita HTML dosyası oluşturuluyor...")
            
            # Create map HTML
            map_html = self.create_map_html()
            
            # Save to temporary file
            map_file_path = Path(__file__).parent / "resources" / "simple_map.html"
            map_file_path.parent.mkdir(exist_ok=True)
            
            with open(map_file_path, 'w', encoding='utf-8') as f:
                f.write(map_html)
            
            self.loading_label.setText("Harita yükleniyor...")
            
            # Load map with error handling
            self.web_view.loadFinished.connect(self.on_map_loaded)
            
            # Set up page load error handling
            def on_load_error():
                logger.error("Web page failed to load")
                self.loading_label.setText("Harita yükleme hatası!\nLütfen uygulamayı yeniden başlatın.")
                self.loading_label.setStyleSheet("""
                    QLabel {
                        background-color: rgba(255, 0, 0, 0.8);
                        color: white;
                        font-size: 14px;
                        font-weight: bold;
                        padding: 20px;
                        border-radius: 10px;
                    }
                """)
            
            # Set timeout for loading
            self.load_timeout = QTimer()
            self.load_timeout.timeout.connect(on_load_error)
            self.load_timeout.setSingleShot(True)
            self.load_timeout.start(10000)  # 10 second timeout
            
            # Load map
            file_url = QUrl.fromLocalFile(str(map_file_path.absolute()))
            self.web_view.load(file_url)
            
            logger.info(f"Simple map HTML created at: {map_file_path}")
            logger.info(f"Loading map from URL: {file_url.toString()}")
            
        except Exception as e:
            logger.error(f"Failed to setup map: {e}")
            self.loading_label.setText(f"Harita kurulum hatası:\n{str(e)}")
            self.loading_label.setStyleSheet("""
                QLabel {
                    background-color: rgba(255, 0, 0, 0.8);
                    color: white;
                    font-size: 12px;
                    padding: 20px;
                    border-radius: 10px;
                }
            """)
    
    def create_map_html(self) -> str:
        """Create the HTML content for a simple Canvas-based map."""
        html_template = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>UAV Map</title>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            
            <style>
                body {{ 
                    margin: 0; 
                    padding: 0; 
                    font-family: Arial, sans-serif;
                    background: #f0f0f0;
                    overflow: hidden;
                }}
                #mapContainer {{ 
                    height: 100vh; 
                    width: 100vw; 
                    position: relative;
                    overflow: hidden;
                    display: flex;
                    flex-direction: column;
                }}
                #map {{ 
                    width: 100%; 
                    height: 100%; 
                    background: #87CEEB;
                    cursor: crosshair;
                    display: block;
                }}
                .map-controls {{
                    position: absolute;
                    top: 10px;
                    left: 10px;
                    z-index: 1000;
                    background: rgba(255,255,255,0.9);
                    padding: 10px;
                    border-radius: 5px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                    font-size: 12px;
                }}
                .coordinates {{
                    position: absolute;
                    bottom: 10px;
                    left: 10px;
                    background: rgba(0,0,0,0.7);
                    color: white;
                    padding: 5px 10px;
                    border-radius: 3px;
                    font-size: 12px;
                    font-family: monospace;
                }}
                .uav-marker {{
                    position: absolute;
                    width: 20px;
                    height: 20px;
                    background: #ff0000;
                    border: 2px solid white;
                    border-radius: 50%;
                    transform: translate(-50%, -50%);
                    z-index: 100;
                    box-shadow: 0 0 10px rgba(255, 0, 0, 0.5);
                    animation: pulse 2s infinite;
                }}
                @keyframes pulse {{
                    0% {{ box-shadow: 0 0 0 0 rgba(255, 0, 0, 0.7); }}
                    70% {{ box-shadow: 0 0 0 10px rgba(255, 0, 0, 0); }}
                    100% {{ box-shadow: 0 0 0 0 rgba(255, 0, 0, 0); }}
                }}
                .waypoint-marker {{
                    position: absolute;
                    width: 12px;
                    height: 12px;
                    background: #0066cc;
                    border: 2px solid white;
                    border-radius: 50%;
                    transform: translate(-50%, -50%);
                    z-index: 50;
                    cursor: pointer;
                    transition: all 0.2s ease;
                }}
                .waypoint-marker:hover {{
                    width: 16px;
                    height: 16px;
                    background: #0088ff;
                }}
                .flight-path {{
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    pointer-events: none;
                    z-index: 10;
                }}
                .status-info {{
                    position: absolute;
                    top: 10px;
                    right: 10px;
                    background: rgba(0,0,0,0.7);
                    color: white;
                    padding: 8px 12px;
                    border-radius: 5px;
                    font-size: 11px;
                    font-family: monospace;
                }}
            </style>
        </head>
        <body onload="resizeCanvas()";
            <div id="mapContainer">
                <canvas id="map"></canvas>
                <canvas id="flightPath" class="flight-path"></canvas>
                <div class="map-controls">
                    <div><strong>Zoom:</strong> <span id="zoomLevel">{zoom}</span></div>
                    <div><strong>Center:</strong> <span id="mapCenter">{lat:.4f}, {lon:.4f}</span></div>
                </div>
                <div class="coordinates" id="coordinates">Lat: {lat:.6f}, Lon: {lon:.6f}</div>
                <div class="status-info">
                    <div>Canvas Map v2.0</div>
                    <div id="canvasSize">Canvas: Loading...</div>
                    <div id="mousePos">Mouse: --</div>
                </div>
            </div>
            
            <script>
                // Map configuration
                var mapConfig = {{
                    centerLat: {lat},
                    centerLon: {lon},
                    zoom: {zoom},
                    pixelsPerDegree: 111000 // Approximate meters per degree
                }};
                
                var canvas = document.getElementById('map');
                var ctx = canvas.getContext('2d');
                var flightCanvas = document.getElementById('flightPath');
                var flightCtx = flightCanvas.getContext('2d');
                
                var uavPosition = null;
                var flightPath = [];
                var waypoints = {{}};
                var mapMarkers = document.getElementById('mapContainer');
                
                // Resize canvas to fit container
                function resizeCanvas() {{
                    var container = document.getElementById('mapContainer');
                    var rect = container.getBoundingClientRect();
                    
                    // Set canvas dimensions to match container
                    canvas.width = rect.width;
                    canvas.height = rect.height;
                    flightCanvas.width = rect.width;
                    flightCanvas.height = rect.height;
                    
                    // Update status display
                    document.getElementById('canvasSize').textContent = 
                        `Canvas: ${{canvas.width}}x${{canvas.height}}`;
                    
                    // Redraw everything
                    drawMap();
                    drawFlightPath();
                    updateAllMarkers();
                    
                    console.log('Canvas resized to:', canvas.width, 'x', canvas.height);
                }}
                
                // Convert lat/lon to pixel coordinates
                function latLonToPixel(lat, lon) {{
                    var scale = Math.pow(2, mapConfig.zoom);
                    var x = (lon - mapConfig.centerLon) * scale * 100 + canvas.width / 2;
                    var y = (mapConfig.centerLat - lat) * scale * 100 + canvas.height / 2;
                    return {{x: x, y: y}};
                }}
                
                // Convert pixel coordinates to lat/lon
                function pixelToLatLon(x, y) {{
                    var scale = Math.pow(2, mapConfig.zoom);
                    var lon = (x - canvas.width / 2) / (scale * 100) + mapConfig.centerLon;
                    var lat = mapConfig.centerLat - (y - canvas.height / 2) / (scale * 100);
                    return {{lat: lat, lon: lon}};
                }}
                
                // Draw grid map
                function drawMap() {{
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    
                    // Background
                    ctx.fillStyle = '#87CEEB';
                    ctx.fillRect(0, 0, canvas.width, canvas.height);
                    
                    // Grid lines
                    ctx.strokeStyle = '#ffffff';
                    ctx.lineWidth = 1;
                    ctx.globalAlpha = 0.3;
                    
                    var gridSize = 50;
                    for (var x = 0; x < canvas.width; x += gridSize) {{
                        ctx.beginPath();
                        ctx.moveTo(x, 0);
                        ctx.lineTo(x, canvas.height);
                        ctx.stroke();
                    }}
                    
                    for (var y = 0; y < canvas.height; y += gridSize) {{
                        ctx.beginPath();
                        ctx.moveTo(0, y);
                        ctx.lineTo(canvas.width, y);
                        ctx.stroke();
                    }}
                    
                    ctx.globalAlpha = 1;
                    
                    // Center crosshair
                    ctx.strokeStyle = '#ff0000';
                    ctx.lineWidth = 2;
                    var centerX = canvas.width / 2;
                    var centerY = canvas.height / 2;
                    
                    ctx.beginPath();
                    ctx.moveTo(centerX - 10, centerY);
                    ctx.lineTo(centerX + 10, centerY);
                    ctx.moveTo(centerX, centerY - 10);
                    ctx.lineTo(centerX, centerY + 10);
                    ctx.stroke();
                }}
                
                // Draw flight path
                function drawFlightPath() {{
                    flightCtx.clearRect(0, 0, flightCanvas.width, flightCanvas.height);
                    
                    if (flightPath.length < 2) return;
                    
                    flightCtx.strokeStyle = '#ff0000';
                    flightCtx.lineWidth = 3;
                    flightCtx.globalAlpha = 0.8;
                    
                    flightCtx.beginPath();
                    var firstPoint = latLonToPixel(flightPath[0].lat, flightPath[0].lon);
                    flightCtx.moveTo(firstPoint.x, firstPoint.y);
                    
                    for (var i = 1; i < flightPath.length; i++) {{
                        var point = latLonToPixel(flightPath[i].lat, flightPath[i].lon);
                        flightCtx.lineTo(point.x, point.y);
                    }}
                    
                    flightCtx.stroke();
                    flightCtx.globalAlpha = 1;
                }}
                
                // Mouse move handler for coordinates
                canvas.addEventListener('mousemove', function(e) {{
                    var rect = canvas.getBoundingClientRect();
                    var x = e.clientX - rect.left;
                    var y = e.clientY - rect.top;
                    var coords = pixelToLatLon(x, y);
                    
                    // Update coordinates display
                    document.getElementById('coordinates').textContent = 
                        `Lat: ${{coords.lat.toFixed(6)}}, Lon: ${{coords.lon.toFixed(6)}}`;
                    
                    // Update mouse position display
                    document.getElementById('mousePos').textContent = 
                        `Mouse: ${{Math.round(x)}},${{Math.round(y)}}`;
                }});
                
                // Map click handler
                canvas.addEventListener('click', function(e) {{
                    var rect = canvas.getBoundingClientRect();
                    var x = e.clientX - rect.left;
                    var y = e.clientY - rect.top;
                    var coords = pixelToLatLon(x, y);
                    
                    // Keep coordinates displayed
                    document.getElementById('coordinates').textContent = 
                        `Lat: ${{coords.lat.toFixed(6)}}, Lon: ${{coords.lon.toFixed(6)}}`;
                    
                    // Flash the clicked position
                    var clickMarker = document.createElement('div');
                    clickMarker.style.position = 'absolute';
                    clickMarker.style.left = (x - 5) + 'px';
                    clickMarker.style.top = (y - 5) + 'px';
                    clickMarker.style.width = '10px';
                    clickMarker.style.height = '10px';
                    clickMarker.style.backgroundColor = '#ffff00';
                    clickMarker.style.border = '2px solid #ff0000';
                    clickMarker.style.borderRadius = '50%';
                    clickMarker.style.zIndex = '200';
                    clickMarker.style.pointerEvents = 'none';
                    
                    document.getElementById('mapContainer').appendChild(clickMarker);
                    
                    // Remove click marker after animation
                    setTimeout(function() {{
                        if (clickMarker.parentNode) {{
                            clickMarker.parentNode.removeChild(clickMarker);
                        }}
                    }}, 1000);
                    
                    console.log('Map clicked at:', coords.lat.toFixed(6), coords.lon.toFixed(6));
                }});
                
                // Zoom with mouse wheel
                canvas.addEventListener('wheel', function(e) {{
                    e.preventDefault();
                    var delta = e.deltaY > 0 ? -1 : 1;
                    mapConfig.zoom = Math.max(1, Math.min(20, mapConfig.zoom + delta));
                    document.getElementById('zoomLevel').textContent = mapConfig.zoom;
                    drawMap();
                    drawFlightPath();
                    updateAllMarkers();
                }});
                
                // Functions callable from Qt
                window.updateUAVPosition = function(lat, lon, heading) {{
                    uavPosition = {{lat: lat, lon: lon, heading: heading}};
                    
                    // Add to flight path
                    flightPath.push({{lat: lat, lon: lon}});
                    if (flightPath.length > 1000) {{
                        flightPath.shift();
                    }}
                    
                    drawFlightPath();
                    updateUAVMarker();
                    
                    console.log('UAV position updated:', lat, lon, heading);
                }};
                
                function updateUAVMarker() {{
                    // Remove existing UAV marker
                    var existingMarker = document.querySelector('.uav-marker');
                    if (existingMarker) {{
                        existingMarker.remove();
                    }}
                    
                    if (uavPosition) {{
                        var pixel = latLonToPixel(uavPosition.lat, uavPosition.lon);
                        var marker = document.createElement('div');
                        marker.className = 'uav-marker';
                        marker.style.left = pixel.x + 'px';
                        marker.style.top = pixel.y + 'px';
                        marker.title = `UAV: ${{uavPosition.lat.toFixed(6)}}, ${{uavPosition.lon.toFixed(6)}}`;
                        mapMarkers.appendChild(marker);
                    }}
                }}
                
                function updateAllMarkers() {{
                    updateUAVMarker();
                    // Update waypoint markers
                    Object.keys(waypoints).forEach(function(id) {{
                        updateWaypointMarker(id);
                    }});
                }}
                
                function updateWaypointMarker(id) {{
                    var existingMarker = document.getElementById('waypoint-' + id);
                    if (existingMarker) {{
                        existingMarker.remove();
                    }}
                    
                    if (waypoints[id]) {{
                        var wp = waypoints[id];
                        var pixel = latLonToPixel(wp.lat, wp.lon);
                        var marker = document.createElement('div');
                        marker.className = 'waypoint-marker';
                        marker.id = 'waypoint-' + id;
                        marker.style.left = pixel.x + 'px';
                        marker.style.top = pixel.y + 'px';
                        marker.title = `${{wp.name}}: ${{wp.lat.toFixed(6)}}, ${{wp.lon.toFixed(6)}}`;
                        mapMarkers.appendChild(marker);
                    }}
                }}
                
                window.centerOnUAV = function() {{
                    if (uavPosition) {{
                        mapConfig.centerLat = uavPosition.lat;
                        mapConfig.centerLon = uavPosition.lon;
                        document.getElementById('mapCenter').textContent = 
                            `${{mapConfig.centerLat.toFixed(4)}}, ${{mapConfig.centerLon.toFixed(4)}}`;
                        drawMap();
                        drawFlightPath();
                        updateAllMarkers();
                    }}
                }};
                
                window.clearFlightPath = function() {{
                    flightPath = [];
                    drawFlightPath();
                }};
                
                window.addWaypoint = function(lat, lon, name, id) {{
                    waypoints[id] = {{lat: lat, lon: lon, name: name}};
                    updateWaypointMarker(id);
                    console.log('Waypoint added:', id, lat, lon, name);
                }};
                
                window.removeWaypoint = function(id) {{
                    delete waypoints[id];
                    var marker = document.getElementById('waypoint-' + id);
                    if (marker) {{
                        marker.remove();
                    }}
                    console.log('Waypoint removed:', id);
                }};
                
                window.setMapCenter = function(lat, lon, zoom) {{
                    mapConfig.centerLat = lat;
                    mapConfig.centerLon = lon;
                    if (zoom !== null) {{
                        mapConfig.zoom = zoom;
                        document.getElementById('zoomLevel').textContent = mapConfig.zoom;
                    }}
                    document.getElementById('mapCenter').textContent = 
                        `${{mapConfig.centerLat.toFixed(4)}}, ${{mapConfig.centerLon.toFixed(4)}}`;
                    drawMap();
                    drawFlightPath();
                    updateAllMarkers();
                }};
                
                // Initialize map when page loads
                window.addEventListener('resize', function() {{
                    console.log('Window resized, updating canvas...');
                    resizeCanvas();
                }});
                
                // DOM content loaded handler
                document.addEventListener('DOMContentLoaded', function() {{
                    console.log('DOM content loaded');
                    resizeCanvas();
                }});
                
                // Initial setup
                console.log('Initializing map...');
                
                // Add debug information
                console.log('Canvas element:', canvas);
                console.log('Flight canvas element:', flightCanvas);
                console.log('Map config:', mapConfig);
                
                // Test the map with initial data after a short delay
                setTimeout(function() {{
                    console.log('Adding test UAV position...');
                    if (typeof updateUAVPosition === 'function') {{
                        updateUAVPosition({lat}, {lon}, 45);
                    }}
                    
                    console.log('Adding test waypoint...');
                    if (typeof addWaypoint === 'function') {{
                        addWaypoint({lat} + 0.001, {lon} + 0.001, 'Test Point', 'test_wp_1');
                    }}
                }}, 1000);
                
                console.log('Simple map initialized successfully');
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
        # Stop the timeout timer
        if hasattr(self, 'load_timeout'):
            self.load_timeout.stop()
            
        if success:
            self.map_loaded = True
            logger.info("Map loaded successfully")
            
            # Show a loading message for JavaScript initialization
            self.loading_label.setText("JavaScript başlatılıyor...")
            
            # Wait longer before switching to map view to ensure canvas is ready
            def switch_to_map():
                self.map_stack.setCurrentWidget(self.web_view)
                logger.info("Switched to map view")
                
                # Check if JavaScript is working after another delay
                def check_js_functionality():
                    self.web_view.page().runJavaScript(
                        "typeof window.updateUAVPosition !== 'undefined'",
                        self.on_js_check_complete
                    )
                
                QTimer.singleShot(1000, check_js_functionality)
            
            QTimer.singleShot(3000, switch_to_map)  # Wait 3 seconds before switching
            
            # Initialize with current position if available (with longer delay)
            if self.uav_position:
                QTimer.singleShot(5000, lambda: self.update_uav_position(
                    self.uav_position['lat'],
                    self.uav_position['lon'],
                    self.uav_position.get('heading', 0)
                ))
        else:
            logger.error("Failed to load map")
            self.loading_label.setText("Harita yükleme başarısız!\nWeb engine sorunu olabilir.")
            self.loading_label.setStyleSheet("""
                QLabel {
                    background-color: rgba(255, 0, 0, 0.8);
                    color: white;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 20px;
                    border-radius: 10px;
                }
            """)
    
    def on_js_check_complete(self, result):
        """Handle JavaScript functionality check result."""
        if result:
            logger.info("JavaScript functions are working correctly")
        else:
            logger.warning("JavaScript functions not available - map may not work correctly")
            self.loading_label.setText("JavaScript hatası!\nHarita fonksiyonları çalışmayabilir.")
            self.loading_label.setStyleSheet("""
                QLabel {
                    background-color: rgba(255,165,0,0.8);
                    color: white;
                    font-size: 12px;
                    padding: 15px;
                    border-radius: 10px;
                }
            """)
            # Show warning for 3 seconds then hide
            QTimer.singleShot(3000, lambda: self.map_stack.setCurrentWidget(self.web_view))
    
    @pyqtSlot()
    def toggle_satellite_layer(self):
        """Toggle satellite layer (Grid view in simple map)."""
        self.show_satellite = self.btn_satellite.isChecked()
        if self.map_loaded:
            # Toggle background style
            bg_color = "#87CEEB" if self.show_satellite else "#90EE90"
            self.web_view.page().runJavaScript(f"ctx.fillStyle = '{bg_color}'; drawMap()")
    
    @pyqtSlot()
    def toggle_street_layer(self):
        """Toggle street layer (Standard grid view)."""
        if self.btn_street.isChecked():
            self.btn_satellite.setChecked(False)
            self.show_satellite = False
            if self.map_loaded:
                self.web_view.page().runJavaScript("ctx.fillStyle = '#90EE90'; drawMap()")
    
    @pyqtSlot()
    def toggle_flight_path(self):
        """Toggle flight path visibility."""
        self.show_flight_path = self.btn_flight_path.isChecked()
        if self.map_loaded:
            if self.show_flight_path:
                self.web_view.page().runJavaScript("flightCanvas.style.display = 'block'; drawFlightPath()")
            else:
                self.web_view.page().runJavaScript("flightCanvas.style.display = 'none'")
    
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
    
    def set_webengine_status(self, available: bool):
        """Set WebEngine availability status and configure fallback if needed."""
        if not available:
            logger.warning("WebEngine not available - using fallback map display")
            self.loading_label.setText("WebEngine mevcut değil!\nHarita görüntüsü sınırlı olacak.")
            self.loading_label.setStyleSheet("""
                QLabel {
                    background-color: rgba(255,165,0,0.8);
                    color: white;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 20px;
                    border-radius: 10px;
                }
            """)
            
            # Disable map-related buttons
            self.btn_satellite.setEnabled(False)
            self.btn_street.setEnabled(False)
            self.btn_flight_path.setEnabled(False)
            
            # Show basic coordinate display
            self.lbl_coordinates.setText("WebEngine desteği gerekiyor")
    
    def show_error_message(self, message: str):
        """Show error message on the map area."""
        self.loading_label.setText(message)
        self.loading_label.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 0, 0, 0.8);
                color: white;
                font-size: 12px;
                padding: 15px;
                border-radius: 10px;
            }
        """)
        self.map_stack.setCurrentWidget(self.loading_label)
    
    def show_loading_message(self, message: str):
        """Show loading message on the map area."""
        self.loading_label.setText(message)
        self.loading_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 0.8);
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 20px;
                border-radius: 10px;
            }
        """)
        self.map_stack.setCurrentWidget(self.loading_label)
    
    def test_map_functionality(self):
        """Test map with sample data."""
        if self.map_loaded:
            logger.info("Testing map functionality...")
            
            # Test UAV position update
            test_lat = 39.9334
            test_lon = 32.8597
            self.update_uav_position(test_lat, test_lon, 45)
            
            # Test waypoint addition
            self.add_waypoint(test_lat + 0.001, test_lon + 0.001, "Test Waypoint", "test_wp")
            
            logger.info("Map functionality test completed")
        else:
            logger.warning("Cannot test map - not loaded yet")
    
    def force_refresh_map(self):
        """Force refresh the map display."""
        if self.map_loaded:
            self.web_view.page().runJavaScript("resizeCanvas(); drawMap(); drawFlightPath(); updateAllMarkers();")
            logger.info("Map refreshed")
    
    def setup_debug_console(self):
        """Setup debug console for web view."""
        try:
            # Enable console messages
            def console_message(level, message, line, source):
                logger.info(f"Web Console [{level}]: {message} (Line: {line}, Source: {source})")
            
            self.web_view.page().javaScriptConsoleMessage = console_message
            logger.info("Debug console setup completed")
            
        except Exception as e:
            logger.error(f"Failed to setup debug console: {e}")

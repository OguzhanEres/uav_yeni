"""
Leaflet Online Map Widget for UAV Ground Control Station
Provides interactive online map display with UAV tracking using Leaflet.js
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


class LeafletOnlineMap(QWidget):
    """Interactive online map widget using Leaflet.js for smooth rendering."""
    
    # Signals
    map_clicked = pyqtSignal(float, float)  # lat, lon
    waypoint_added = pyqtSignal(float, float, str)  # lat, lon, name
    waypoint_removed = pyqtSignal(str)  # waypoint_id
    map_ready = pyqtSignal(bool)  # Map loading status
    
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
        self.show_satellite = False
        self.show_flight_path = False  # Default to false - no flight path shown
        self.show_restricted_zones = False
        
        # Web view
        self.web_view = None
        self.loading_label = None
        self.map_stack = None
        
        # Remove widget margins and padding
        self.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet("""
            LeafletOnlineMap {
                margin: 0px;
                padding: 0px;
                border: none;
            }
        """)
        
        self.setup_ui()
        self.setup_map()
        
        logger.info("Leaflet Online Map Widget initialized")
    
    def setup_ui(self):
        """Setup the map user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # Remove all margins
        layout.setSpacing(1)  # Minimal spacing between elements
        
        # Control panel with reduced height
        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(2, 2, 2, 2)  # Minimal margins for controls
        
        # Map type buttons - smaller and more compact
        self.btn_street = QPushButton("🗺️")
        self.btn_street.setCheckable(True)
        self.btn_street.setChecked(True)
        self.btn_street.setMaximumSize(40, 25)
        self.btn_street.setToolTip("Street Map")
        self.btn_street.clicked.connect(self.toggle_street_layer)
        control_layout.addWidget(self.btn_street)
        
        self.btn_satellite = QPushButton("🛰️")
        self.btn_satellite.setCheckable(True)
        self.btn_satellite.setMaximumSize(40, 25)
        self.btn_satellite.setToolTip("Satellite View")
        self.btn_satellite.clicked.connect(self.toggle_satellite_layer)
        control_layout.addWidget(self.btn_satellite)
        
        # Flight path toggle
        self.btn_flight_path = QPushButton("✈️")
        self.btn_flight_path.setCheckable(True)
        self.btn_flight_path.setChecked(False)
        self.btn_flight_path.setMaximumSize(40, 25)
        self.btn_flight_path.setToolTip("Flight Path")
        self.btn_flight_path.clicked.connect(self.toggle_flight_path)
        control_layout.addWidget(self.btn_flight_path)
        
        # Clear track button
        self.btn_clear_track = QPushButton("🗑️")
        self.btn_clear_track.setMaximumSize(40, 25)
        self.btn_clear_track.setToolTip("Clear Track")
        self.btn_clear_track.clicked.connect(self.clear_track)
        control_layout.addWidget(self.btn_clear_track)
        
        # Center on UAV button
        self.btn_center_uav = QPushButton("🎯")
        self.btn_center_uav.setMaximumSize(40, 25)
        self.btn_center_uav.setToolTip("Center on UAV")
        self.btn_center_uav.clicked.connect(self.center_on_uav)
        control_layout.addWidget(self.btn_center_uav)
        
        # Refresh button
        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setMaximumSize(40, 25)
        self.btn_refresh.setToolTip("Refresh Map")
        self.btn_refresh.clicked.connect(self.force_refresh_map)
        control_layout.addWidget(self.btn_refresh)
        
        control_layout.addStretch()
        
        # Compact coordinates display
        self.lbl_coordinates = QLabel("📍 0.0000, 0.0000")
        self.lbl_coordinates.setStyleSheet("font-family: monospace; font-size: 10px; color: #ecf0f1;")
        self.lbl_coordinates.setMaximumHeight(20)
        control_layout.addWidget(self.lbl_coordinates)
        
        # Set maximum height for control panel
        control_widget = QWidget()
        control_widget.setLayout(control_layout)
        control_widget.setMaximumHeight(30)
        control_widget.setStyleSheet("""
            QWidget { 
                background: rgba(44, 62, 80, 0.8); 
                border-radius: 3px; 
            }
            QPushButton { 
                border: 1px solid #34495e; 
                border-radius: 3px; 
                background: #3498db;
                color: white;
                font-weight: bold;
            }
            QPushButton:checked { 
                background: #e74c3c; 
            }
            QPushButton:hover { 
                background: #2980b9; 
            }
        """)
        
        layout.addWidget(control_widget)
        
        # Web engine view for map - maximum space
        self.web_view = QWebEngineView()
        self.web_view.setMinimumSize(600, 400)  # Increased minimum size
        self.web_view.setSizePolicy(self.web_view.sizePolicy().Expanding, self.web_view.sizePolicy().Expanding)
        
        # Add loading status label
        self.loading_label = QLabel("🗺️ Leaflet haritası yükleniyor...")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3498db, stop:1 #2980b9);
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 30px;
                border-radius: 15px;
                border: 2px solid #2c3e50;
            }
        """)
        self.loading_label.setVisible(True)
        
        # Configure web engine settings for better performance
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.ErrorPageEnabled, True)
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.AllowGeolocationOnInsecureOrigins, True)
        settings.setAttribute(QWebEngineSettings.ShowScrollBars, False)  # Hide scrollbars
        
        # Create a stacked layout for web view and loading label
        self.map_stack = QStackedWidget()
        self.map_stack.addWidget(self.loading_label)
        self.map_stack.addWidget(self.web_view)
        self.map_stack.setCurrentWidget(self.loading_label)
        
        # Ensure the stacked widget expands to fill available space
        self.map_stack.setSizePolicy(self.map_stack.sizePolicy().Expanding, self.map_stack.sizePolicy().Expanding)
        
        layout.addWidget(self.map_stack, 1)  # Give map maximum space (stretch factor 1)
        
        self.setLayout(layout)
        
        # Force proper size policies
        from PyQt5.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        logger.info("Leaflet map UI setup completed")
    
    def setup_map(self):
        """Initialize the Leaflet-based online map."""
        try:
            self.loading_label.setText("🔗 Leaflet HTML dosyası oluşturuluyor...")
            
            # Create map HTML
            map_html = self.create_leaflet_html()
            
            # Save to temporary file
            map_file_path = Path(__file__).parent / "resources" / "leaflet_map.html"
            map_file_path.parent.mkdir(exist_ok=True)
            
            with open(map_file_path, 'w', encoding='utf-8') as f:
                f.write(map_html)
            
            self.loading_label.setText("🌐 Online harita yükleniyor...")
            
            # Load map with error handling
            self.web_view.loadFinished.connect(self.on_map_loaded)
            
            # Set up page load error handling
            def on_load_error():
                logger.error("Leaflet map failed to load")
                self.loading_label.setText("❌ Harita yükleme hatası!\n\nİnternet bağlantınızı kontrol edin\nveya uygulamayı yeniden başlatın.")
                self.loading_label.setStyleSheet("""
                    QLabel {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #e74c3c, stop:1 #c0392b);
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
            self.load_timeout.start(15000)  # 15 second timeout for online map
            
            # Load map
            file_url = QUrl.fromLocalFile(str(map_file_path.absolute()))
            self.web_view.load(file_url)
            
            logger.info(f"Leaflet map HTML created at: {map_file_path}")
            logger.info(f"Loading map from URL: {file_url.toString()}")
            
        except Exception as e:
            logger.error(f"Failed to setup Leaflet map: {e}")
            self.loading_label.setText(f"❌ Harita kurulum hatası:\n{str(e)}")
            self.loading_label.setStyleSheet("""
                QLabel {
                    background-color: rgba(231, 76, 60, 0.9);
                    color: white;
                    font-size: 12px;
                    padding: 20px;
                    border-radius: 10px;
                }
            """)
    
    def create_leaflet_html(self) -> str:
        """Create the HTML content for Leaflet online map."""
        html_template = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Hüma UAV - Leaflet Map</title>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            
            <!-- Leaflet CSS -->
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
                integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
                crossorigin=""/>
            
            <!-- Leaflet JavaScript -->
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
                integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
                crossorigin=""></script>
            
            <style>
                html, body {{
                    margin: 0;
                    padding: 0;
                    height: 100%;
                    width: 100%;
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    overflow: hidden;
                }}
                #map {{
                    height: 100vh;
                    width: 100vw;
                    position: absolute;
                    top: 0;
                    left: 0;
                    z-index: 1;
                }}
                .custom-div-icon {{
                    background: none;
                    border: none;
                }}
                .uav-marker {{
                    width: 30px;
                    height: 30px;
                    background: #e74c3c;
                    border: 3px solid white;
                    border-radius: 50%;
                    box-shadow: 0 0 15px rgba(231, 76, 60, 0.6);
                    animation: pulse 2s infinite;
                }}
                @keyframes pulse {{
                    0% {{ box-shadow: 0 0 0 0 rgba(231, 76, 60, 0.7); }}
                    70% {{ box-shadow: 0 0 0 20px rgba(231, 76, 60, 0); }}
                    100% {{ box-shadow: 0 0 0 0 rgba(231, 76, 60, 0); }}
                }}
                .waypoint-marker {{
                    width: 20px;
                    height: 20px;
                    background: #3498db;
                    border: 2px solid white;
                    border-radius: 50%;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.3);
                }}
                .heading-arrow {{
                    background: none;
                    border: none;
                    pointer-events: none;
                }}
                .info-panel {{
                    position: absolute;
                    top: 10px;
                    right: 10px;
                    background: rgba(44, 62, 80, 0.9);
                    color: white;
                    padding: 10px;
                    border-radius: 8px;
                    z-index: 1000;
                    font-size: 12px;
                    min-width: 200px;
                }}
                .loading-overlay {{
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    background: rgba(52, 152, 219, 0.9);
                    color: white;
                    padding: 20px 30px;
                    border-radius: 10px;
                    z-index: 2000;
                    font-size: 16px;
                    font-weight: bold;
                    display: none;
                }}
            </style>
        </head>
        <body onload="initMap()">
            <div id="map"></div>
            <div class="info-panel" id="infoPanel">
                <div><strong>🗺️ Leaflet Online Map</strong></div>
                <div>Zoom: <span id="zoomLevel">{self.zoom_level}</span></div>
                <div>Center: <span id="mapCenter">{self.current_lat:.4f}, {self.current_lon:.4f}</span></div>
                <div>UAV: <span id="uavStatus">Bağlantı bekleniyor</span></div>
            </div>
            <div class="loading-overlay" id="loadingOverlay">
                🌐 Harita yükleniyor...
            </div>
            
            <script>
                var map;
                var uavMarker;
                var flightPath = [];
                var flightPolyline;
                var headingLine;
                var headingArrow;
                var waypoints = {{}};
                var streetLayer, satelliteLayer;
                var currentLayer = 'street';
                
                function initMap() {{
                    try {{
                        console.log('Initializing Leaflet map...');
                        
                        // Show loading
                        document.getElementById('loadingOverlay').style.display = 'block';
                        
                        // Initialize map
                        map = L.map('map', {{
                            center: [{self.current_lat}, {self.current_lon}],
                            zoom: {self.zoom_level},
                            zoomControl: true,
                            scrollWheelZoom: true,
                            doubleClickZoom: true,
                            dragging: true
                        }});
                        
                        // Define tile layers
                        streetLayer = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                            attribution: '© OpenStreetMap contributors',
                            maxZoom: 19
                        }});
                        
                        satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                            attribution: '© Esri, Maxar, Earthstar Geographics',
                            maxZoom: 19
                        }});
                        
                        // Add default layer
                        streetLayer.addTo(map);
                        
                        // Initialize flight path (disabled by default)
                        flightPolyline = L.polyline([], {{
                            color: '#e74c3c',
                            weight: 3,
                            opacity: 0.8
                        }});
                        // Do not add to map by default - user can enable it with the flight path button
                        
                        // Map event listeners
                        map.on('click', function(e) {{
                            var lat = e.latlng.lat.toFixed(6);
                            var lng = e.latlng.lng.toFixed(6);
                            console.log('Map clicked at:', lat, lng);
                            
                            // Update center display
                            document.getElementById('mapCenter').textContent = lat + ', ' + lng;
                            
                            // Create temporary click marker
                            var clickMarker = L.circleMarker([e.latlng.lat, e.latlng.lng], {{
                                color: '#f1c40f',
                                fillColor: '#f39c12',
                                fillOpacity: 0.8,
                                radius: 8
                            }}).addTo(map);
                            
                            setTimeout(function() {{
                                map.removeLayer(clickMarker);
                            }}, 2000);
                        }});
                        
                        map.on('zoomend', function() {{
                            document.getElementById('zoomLevel').textContent = map.getZoom();
                        }});
                        
                        map.on('moveend', function() {{
                            var center = map.getCenter();
                            document.getElementById('mapCenter').textContent = 
                                center.lat.toFixed(4) + ', ' + center.lng.toFixed(4);
                        }});
                        
                        // Handle resize
                        function onResize() {{
                            console.log('Map resize triggered');
                            setTimeout(function() {{
                                map.invalidateSize();
                            }}, 100);
                        }}
                        
                        window.addEventListener('resize', onResize);
                        
                        // Hide loading after initialization
                        setTimeout(function() {{
                            document.getElementById('loadingOverlay').style.display = 'none';
                            console.log('Leaflet map initialized successfully');
                        }}, 1000);
                        
                    }} catch (error) {{
                        console.error('Error initializing map:', error);
                        document.getElementById('loadingOverlay').innerHTML = 
                            '❌ Harita başlatma hatası<br>' + error.message;
                    }}
                }}
                
                // Functions callable from Qt
                window.updateUAVPosition = function(lat, lon, heading) {{
                    try {{
                        if (!map) {{
                            console.log('Map not initialized yet, deferring UAV position update');
                            setTimeout(function() {{
                                updateUAVPosition(lat, lon, heading);
                            }}, 1000);
                            return;
                        }}
                        
                        console.log('Updating UAV position:', lat, lon, heading);
                        
                        // Remove existing UAV marker and heading line
                        if (uavMarker) {{
                            map.removeLayer(uavMarker);
                        }}
                        if (headingLine) {{
                            map.removeLayer(headingLine);
                        }}
                        if (headingArrow) {{
                            map.removeLayer(headingArrow);
                        }}
                        
                        // Create UAV marker
                        var uavIcon = L.divIcon({{
                            className: 'custom-div-icon',
                            html: '<div class="uav-marker"></div>',
                            iconSize: [30, 30],
                            iconAnchor: [15, 15]
                        }});
                        
                        uavMarker = L.marker([lat, lon], {{icon: uavIcon}})
                            .addTo(map)
                            .bindPopup(`🚁 UAV<br>Lat: ${{lat.toFixed(6)}}<br>Lon: ${{lon.toFixed(6)}}<br>Heading: ${{heading.toFixed(1)}}°`);
                        
                        // Create heading line (burun yönelimi)
                        var headingDistance = 0.001; // Yaklaşık 100 metre (coğrafi koordinatlarda)
                        var headingRad = (heading * Math.PI) / 180; // Dereceyi radyana çevir
                        
                        // Heading yönünde nokta hesapla (kuzey = 0°, saat yönü pozitif)
                        var headingEndLat = lat + (headingDistance * Math.cos(headingRad));
                        var headingEndLon = lon + (headingDistance * Math.sin(headingRad));
                        
                        // Heading çizgisini oluştur
                        headingLine = L.polyline([
                            [lat, lon],
                            [headingEndLat, headingEndLon]
                        ], {{
                            color: '#ff6b35',  // Turuncu renk
                            weight: 4,
                            opacity: 0.9
                        }}).addTo(map);
                        
                        // Heading çizgisinin ucuna ok işareti ekle
                        var arrowIcon = L.divIcon({{
                            className: 'heading-arrow',
                            html: '<div style="width: 0; height: 0; border-left: 6px solid transparent; border-right: 6px solid transparent; border-bottom: 12px solid #ff6b35; transform: rotate(' + heading + 'deg);"></div>',
                            iconSize: [12, 12],
                            iconAnchor: [6, 6]
                        }});
                        
                        headingArrow = L.marker([headingEndLat, headingEndLon], {{icon: arrowIcon}}).addTo(map);
                        
                        // Add to flight path
                        flightPath.push([lat, lon]);
                        if (flightPath.length > 1000) {{
                            flightPath.shift();
                        }}
                        
                        // Update flight path polyline
                        if (flightPolyline) {{
                            flightPolyline.setLatLngs(flightPath);
                        }}
                        
                        // Update status
                        var statusElement = document.getElementById('uavStatus');
                        if (statusElement) {{
                            statusElement.textContent = `${{lat.toFixed(4)}}, ${{lon.toFixed(4)}}`;
                        }}
                        
                    }} catch (error) {{
                        console.error('Error updating UAV position:', error);
                    }}
                }};
                
                window.centerOnUAV = function() {{
                    try {{
                        if (!map) {{
                            console.log('Map not initialized yet');
                            return;
                        }}
                        if (uavMarker) {{
                            map.setView(uavMarker.getLatLng(), map.getZoom());
                            console.log('Map centered on UAV');
                        }}
                    }} catch (error) {{
                        console.error('Error centering on UAV:', error);
                    }}
                }};
                
                window.clearFlightPath = function() {{
                    try {{
                        flightPath = [];
                        if (flightPolyline) {{
                            flightPolyline.setLatLngs([]);
                        }}
                        console.log('Flight path cleared');
                    }} catch (error) {{
                        console.error('Error clearing flight path:', error);
                    }}
                }};
                
                window.addWaypoint = function(lat, lon, name, id) {{
                    try {{
                        if (!map) {{
                            console.log('Map not initialized yet, deferring waypoint addition');
                            setTimeout(function() {{
                                addWaypoint(lat, lon, name, id);
                            }}, 1000);
                            return;
                        }}
                        
                        var waypointIcon = L.divIcon({{
                            className: 'custom-div-icon',
                            html: '<div class="waypoint-marker"></div>',
                            iconSize: [20, 20],
                            iconAnchor: [10, 10]
                        }});
                        
                        var marker = L.marker([lat, lon], {{icon: waypointIcon}})
                            .addTo(map)
                            .bindPopup(`📍 ${{name}}<br>Lat: ${{lat.toFixed(6)}}<br>Lon: ${{lon.toFixed(6}}`);
                        
                        waypoints[id] = marker;
                        console.log('Waypoint added:', id, name);
                        
                    }} catch (error) {{
                        console.error('Error adding waypoint:', error);
                    }}
                }};
                
                window.removeWaypoint = function(id) {{
                    try {{
                        if (!map) {{
                            console.log('Map not initialized yet');
                            return;
                        }}
                        if (waypoints[id]) {{
                            map.removeLayer(waypoints[id]);
                            delete waypoints[id];
                            console.log('Waypoint removed:', id);
                        }}
                    }} catch (error) {{
                        console.error('Error removing waypoint:', error);
                    }}
                }};
                
                window.setMapCenter = function(lat, lon, zoom) {{
                    try {{
                        if (!map) {{
                            console.log('Map not initialized yet');
                            return;
                        }}
                        if (zoom) {{
                            map.setView([lat, lon], zoom);
                        }} else {{
                            map.setView([lat, lon]);
                        }}
                    }} catch (error) {{
                        console.error('Error setting map center:', error);
                    }}
                }};
                
                window.toggleSatelliteLayer = function() {{
                    if (currentLayer === 'street') {{
                        map.removeLayer(streetLayer);
                        satelliteLayer.addTo(map);
                        currentLayer = 'satellite';
                        console.log('Switched to satellite layer');
                    }} else {{
                        map.removeLayer(satelliteLayer);
                        streetLayer.addTo(map);
                        currentLayer = 'street';
                        console.log('Switched to street layer');
                    }}
                }};
                
                window.toggleFlightPath = function(show) {{
                    if (show) {{
                        flightPolyline.addTo(map);
                    }} else {{
                        map.removeLayer(flightPolyline);
                    }}
                }};
                
                // Force map resize
                window.forceResize = function() {{
                    setTimeout(function() {{
                        map.invalidateSize();
                        console.log('Map size invalidated');
                    }}, 100);
                }};
                
                // Add some test data after initialization
                setTimeout(function() {{
                    if (typeof updateUAVPosition === 'function') {{
                        updateUAVPosition({self.current_lat}, {self.current_lon}, 45);
                        addWaypoint({self.current_lat + 0.001}, {self.current_lon + 0.001}, 'Test Waypoint', 'test_wp_1');
                    }}
                }}, 2000);
                
            </script>
        </body>
        </html>
        '''
        
        return html_template
    
    def on_map_loaded(self, success: bool):
        """Handle map load completion."""
        # Stop the timeout timer
        if hasattr(self, 'load_timeout'):
            self.load_timeout.stop()
            
        if success:
            self.map_loaded = True
            logger.info("Leaflet map loaded successfully")
            
            # Wait for JavaScript initialization and immediately switch to map
            def switch_to_map():
                self.map_stack.setCurrentWidget(self.web_view)
                # Force map resize and invalidation after switching
                QTimer.singleShot(500, self.force_map_resize)
                QTimer.singleShot(1000, self.force_map_resize)  # Extra resize after 1 second
                logger.info("Switched to Leaflet map view")
                self.map_ready.emit(True)
                
            # Check if JavaScript is working
            def check_js_functionality():
                self.web_view.page().runJavaScript(
                    "typeof window.updateUAVPosition !== 'undefined'",
                    self.on_js_check_complete
                )
            
            # Immediate switch to reduce loading time
            QTimer.singleShot(1000, check_js_functionality)
            QTimer.singleShot(1500, switch_to_map)
            
        else:
            logger.error("Failed to load Leaflet map")
            self.loading_label.setText("❌ Harita yükleniyor...")
            self.loading_label.setStyleSheet("""
                QLabel {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #e74c3c, stop:1 #c0392b);
                    color: white;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 20px;
                    border-radius: 10px;
                }
            """)
            self.map_ready.emit(False)
    
    def force_map_resize(self):
        """Force map to resize and redraw properly."""
        if self.map_loaded and self.web_view:
            resize_js = """
                if (typeof map !== 'undefined' && map) {
                    setTimeout(function() {
                        map.invalidateSize(true);
                        map.getContainer().style.height = '100%';
                        map.getContainer().style.width = '100%';
                        console.log('Map resize triggered');
                    }, 100);
                }
            """
            self.web_view.page().runJavaScript(resize_js)
    
    def on_js_check_complete(self, result):
        """Handle JavaScript functionality check result."""
        if result:
            logger.info("JavaScript functions are working correctly")
        else:
            logger.warning("JavaScript functions not available - map may not work correctly")
    
    @pyqtSlot()
    def toggle_satellite_layer(self):
        """Toggle satellite layer."""
        self.show_satellite = self.btn_satellite.isChecked()
        if self.btn_satellite.isChecked():
            self.btn_street.setChecked(False)
        else:
            self.btn_street.setChecked(True)
            
        if self.map_loaded:
            self.web_view.page().runJavaScript("toggleSatelliteLayer()")
    
    @pyqtSlot()
    def toggle_street_layer(self):
        """Toggle street layer."""
        if self.btn_street.isChecked():
            self.btn_satellite.setChecked(False)
            self.show_satellite = False
        else:
            self.btn_satellite.setChecked(True)
            self.show_satellite = True
            
        if self.map_loaded:
            self.web_view.page().runJavaScript("toggleSatelliteLayer()")
    
    @pyqtSlot()
    def toggle_flight_path(self):
        """Toggle flight path visibility."""
        self.show_flight_path = self.btn_flight_path.isChecked()
        if self.map_loaded:
            show = "true" if self.show_flight_path else "false"
            self.web_view.page().runJavaScript(f"toggleFlightPath({show})")
    
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
            self.lbl_coordinates.setText(f"📍 Lat: {lat:.6f}, Lon: {lon:.6f}")
            
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
    
    @pyqtSlot()
    def force_refresh_map(self):
        """Force refresh the entire map."""
        if self.web_view and self.map_loaded:
            # Reload the map page completely
            self.map_loaded = False
            self.map_stack.setCurrentWidget(self.loading_label)
            self.loading_label.setText("🔄 Harita yenileniyor...")
            
            # Reload the page
            QTimer.singleShot(500, lambda: self.web_view.reload())
            logger.info("Map refresh initiated")
        else:
            logger.warning("Cannot refresh map - not loaded yet")
    
    def resizeEvent(self, event):
        """Handle widget resize events."""
        super().resizeEvent(event)
        # Force map resize when widget is resized
        if self.map_loaded:
            QTimer.singleShot(100, self.force_map_resize)
    
    def showEvent(self, event):
        """Handle widget show events."""
        super().showEvent(event)
        # Force map resize when widget becomes visible
        if self.map_loaded:
            QTimer.singleShot(500, self.force_map_resize)
    
    def set_webengine_status(self, available: bool):
        """Set WebEngine availability status."""
        if not available:
            logger.warning("WebEngine not available - Leaflet map cannot be loaded")
            self.loading_label.setText("❌ WebEngine mevcut değil!\n\nPyQtWebEngine gerekli\npip install PyQtWebEngine")
            self.loading_label.setStyleSheet("""
                QLabel {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #e67e22, stop:1 #d35400);
                    color: white;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 20px;
                    border-radius: 10px;
                }
            """)
            
            # Disable map-related buttons
            for btn in [self.btn_satellite, self.btn_street, self.btn_flight_path, 
                       self.btn_clear_track, self.btn_center_uav, self.btn_refresh]:
                btn.setEnabled(False)

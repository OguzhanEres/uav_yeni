"""
Modern Ground Control Station Main Window
Refactored from the original arayuz_fonksiyon.py with improved architecture.
"""

import sys
import os
import time
import math
import serial.tools.list_ports
import subprocess
import psutil
import collections
import collections.abc
from pathlib import Path
from typing import Dict, Any, Optional

# Fix for collections compatibility
if not hasattr(collections, 'MutableMapping'):
    collections.MutableMapping = collections.abc.MutableMapping

# Third-party imports
import dronekit
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, 
    QMessageBox, QInputDialog
)
from PyQt5.QtCore import QTimer, QDateTime, QUrl, Qt, pyqtSlot
from PyQt5 import QtCore, uic
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEngineProfile

# Internal imports
from ...core.logging_config import get_logger
from ...core.exceptions import ConnectionError, UAVException
from ...communication.mavlink.mavlink_client import MAVLinkClient
# Import settings from config module at the project root
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))
try:
    from config.settings import settings
except ImportError:
    # Fallback settings
    class Settings:
        PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
        TELEMETRY_UPDATE_RATE = 100
        MAP_SERVER_PORT = 8080
        DEFAULT_BAUD_RATE = 57600
    settings = Settings()

logger = get_logger(__name__)

# Try to import optional components
try:
    from .leaflet_map_widget import LeafletOnlineMap
    LEAFLET_MAP_AVAILABLE = True
except ImportError:
    logger.warning("LeafletOnlineMap not available")
    LeafletOnlineMap = None
    LEAFLET_MAP_AVAILABLE = False

try:
    from .map_widget import SimpleCanvasMap
except ImportError:
    logger.warning("SimpleCanvasMap not available")
    SimpleCanvasMap = None

try:
    from .hud_widget import HUDWidget
except ImportError:
    logger.warning("HUDWidget not available")
    HUDWidget = None


class HumaGCS(QMainWindow):
    """Modern Ground Control Station with improved architecture."""
    
    def __init__(self):
        super().__init__()
        
        # Initialize core attributes
        self.uav = None
        self.connection_active = False
        self.map_loaded = False
        self.webengine_available = True
        
        # UAV telemetry data
        self.current_telemetry = {
            'lat': 39.9334,
            'lon': 32.8597,
            'alt': 0,
            'heading': 0,
            'ground_speed': 0,
            'air_speed': 0,
            'battery_voltage': 0,
            'battery_current': 0,
            'flight_mode': 'UNKNOWN',
            'armed': False,
            'gps_fix': 0,
            'satellites': 0
        }
        
        # UI components
        self.canvas_map = None
        self.hud_widget = None
        self.map_widget = None
        self.leaflet_map = None
        
        # Processes and threads
        self.camera_process = None
        self.camera_window_process = None
        self.server_thread = None
        self.check_server_thread = None
        
        # Communication
        self.mavlink_client = None
        
        # Initialize UI and systems
        self.setup_ui()
        self.setup_communication()
        self.setup_components()
        
        logger.info("Hüma GCS initialized successfully")
    
    def setup_ui(self):
        """Initialize the user interface."""
        try:
            # Load UI from file
            ui_file_path = Path(__file__).parent / "resources" / "huma_gcs.ui"
            if ui_file_path.exists():
                uic.loadUi(str(ui_file_path), self)
                logger.info(f"UI loaded from: {ui_file_path}")
            else:
                logger.error(f"UI file not found: {ui_file_path}")
                self.setup_fallback_ui()
            
            # Set window properties
            self.setWindowTitle("Hüma GCS - İnsansız Hava Aracı Kontrol İstasyonu v2.0")
            
            # Setup port list
            self.setup_port_list()
            
            # Setup UI connections
            self.setup_ui_connections()
            
            # Setup timers
            self.setup_timers()
            
        except Exception as e:
            logger.error(f"Failed to setup UI: {e}")
            self.setup_fallback_ui()
    
    def setup_fallback_ui(self):
        """Setup a minimal fallback UI if main UI file is not available."""
        self.setWindowTitle("Hüma GCS - Fallback Mode")
        self.setGeometry(100, 100, 800, 600)
        
        # Create central widget with basic layout
        central_widget = QLabel("UI dosyası bulunamadı. Fallback modunda çalışıyor.")
        central_widget.setAlignment(Qt.AlignCenter)
        self.setCentralWidget(central_widget)
    
    def setup_port_list(self):
        """Setup the COM port list."""
        if not hasattr(self, 'portList'):
            logger.warning("portList widget not found in UI")
            return
        
        try:
            ports = serial.tools.list_ports.comports()
            
            # Add default UDP option
            self.portList.addItem("UDP (127.0.0.1:14550)")
            
            # Add COM ports with detailed information
            for port in ports:
                port_info = f"{port.device}"
                if port.description and port.description != "n/a":
                    port_info += f" ({port.description})"
                self.portList.addItem(port_info)
            
            logger.info(f"Available COM ports: {[p.device for p in ports]}")
            
            # Select COM8 by default if available (for Pixhawk)
            for i in range(self.portList.count()):
                if "COM8" in self.portList.itemText(i):
                    self.portList.setCurrentIndex(i)
                    logger.info("COM8 selected by default")
                    break
                    
        except Exception as e:
            logger.error(f"Failed to setup port list: {e}")
    
    def setup_communication(self):
        """Initialize communication systems."""
        try:
            # Initialize MAVLink client
            self.mavlink_client = MAVLinkClient()
            if self.mavlink_client.initialize():
                logger.info("MAVLink client initialized successfully")
            else:
                logger.error("Failed to initialize MAVLink client")
                
        except Exception as e:
            logger.error(f"Failed to setup communication: {e}")
            self.mavlink_client = None
    
    def setup_components(self):
        """Initialize UI components."""
        try:
            # Setup map view
            self.setup_map_view()
            
            # Setup HUD view
            self.setup_hud_view()
            
            # Initialize map in separate thread
            self.initialize_map()
            
        except Exception as e:
            logger.error(f"Failed to setup components: {e}")
    
    def setup_map_view(self):
        """Setup the map view component with Leaflet online map."""
        if not hasattr(self, 'label'):
            logger.warning("Map label widget not found")
            return
        
        try:
            # Show loading message
            self.label.setText("🗺️ Leaflet haritası yükleniyor...\nLütfen bekleyin.")
            self.label.setStyleSheet("""
                QLabel {
                    color: white;
                    font-size: 16pt;
                    font-weight: bold;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #3498db, stop:1 #2980b9);
                    padding: 20px;
                    border-radius: 10px;
                    border: 2px solid #2c3e50;
                }
            """)
            
            # Try to create Leaflet online map first
            if LEAFLET_MAP_AVAILABLE and self.webengine_available:
                self.create_leaflet_map()
            else:
                logger.warning("Leaflet map not available, falling back to offline map")
                self.create_offline_map()
            
            logger.info("Map view setup completed")
            
        except Exception as e:
            logger.error(f"Map view setup failed: {e}")
            self.show_map_error(f"Harita kurulumu hatası: {str(e)}")
    
    def create_leaflet_map(self):
        """Create Leaflet online map."""
        try:
            logger.info("Creating Leaflet online map...")
            
            # Create Leaflet map widget as a child of the main window, not the label
            self.leaflet_map = LeafletOnlineMap(self)
            
            # Create a layout for the label if it doesn't have one
            if self.label.layout() is None:
                from PyQt5.QtWidgets import QVBoxLayout
                layout = QVBoxLayout(self.label)
                layout.setContentsMargins(0, 0, 0, 0)  # Remove all margins
                layout.setSpacing(0)  # Remove spacing between widgets
                self.label.setLayout(layout)
            
            # Clear existing layout contents
            layout = self.label.layout()
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            
            # Add the map widget to the label's layout
            layout.addWidget(self.leaflet_map)
            
            # Ensure the label has proper sizing and no borders/margins
            from PyQt5.QtWidgets import QSizePolicy
            self.label.setMinimumSize(400, 300)
            self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.label.setContentsMargins(0, 0, 0, 0)  # Remove label margins
            
            # Remove any styling that might add padding or borders
            self.label.setStyleSheet("""
                QLabel {
                    margin: 0px;
                    padding: 0px;
                    border: none;
                    background: transparent;
                }
            """)
            
            # Connect signals
            self.leaflet_map.map_ready.connect(self.on_leaflet_map_ready)
            self.leaflet_map.map_clicked.connect(self.on_map_clicked)
            self.leaflet_map.waypoint_added.connect(self.on_waypoint_added)
            self.leaflet_map.waypoint_removed.connect(self.on_waypoint_removed)
            
            # Set WebEngine status
            self.leaflet_map.set_webengine_status(self.webengine_available)
            
            # Clear any text from the label
            self.label.setText("")
            
            # Show map widget
            self.leaflet_map.show()
            
            logger.info("Leaflet map created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create Leaflet map: {e}")
            self.create_offline_map()
    
    def on_leaflet_map_ready(self, success: bool):
        """Handle Leaflet map ready signal."""
        if success:
            logger.info("Leaflet map is ready and functional")
            self.map_loaded = True
            self.map_widget = self.leaflet_map
            
            # Start telemetry updates if drone is connected
            if self.connection_active and self.current_telemetry:
                self.update_map_with_uav_data(self.current_telemetry)
        else:
            logger.error("Leaflet map failed to initialize")
            self.create_offline_map()
    
    def on_map_clicked(self, lat: float, lon: float):
        """Handle map click events."""
        logger.info(f"Map clicked at: {lat:.6f}, {lon:.6f}")
        # You can add waypoint creation logic here if needed
    
    def on_waypoint_added(self, lat: float, lon: float, name: str):
        """Handle waypoint added events."""
        logger.info(f"Waypoint added: {name} at {lat:.6f}, {lon:.6f}")
    
    def on_waypoint_removed(self, waypoint_id: str):
        """Handle waypoint removed events."""
        logger.info(f"Waypoint removed: {waypoint_id}")
    
    def create_offline_map(self):
        """Create a simple offline map using static HTML and basic drawing."""
        try:
            # Create a simple map HTML without external dependencies
            offline_map_html = self.generate_offline_map_html()
            
            # Save to temp file
            map_file_path = Path(__file__).parent / "resources" / "offline_map.html"
            map_file_path.parent.mkdir(exist_ok=True)
            
            with open(map_file_path, 'w', encoding='utf-8') as f:
                f.write(offline_map_html)
            
            # Create web view if label exists
            if hasattr(self, 'label') and self.label:
                from PyQt5.QtWebEngineWidgets import QWebEngineView
                from PyQt5.QtWidgets import QVBoxLayout
                
                self.map_widget = QWebEngineView(self.label)
                
                # Create layout for the label if it doesn't exist
                if self.label.layout() is None:
                    layout = QVBoxLayout(self.label)
                    layout.setContentsMargins(0, 0, 0, 0)  # Remove all margins
                    layout.setSpacing(0)  # Remove spacing
                    self.label.setLayout(layout)
                
                # Clear existing layout contents
                layout = self.label.layout()
                while layout.count():
                    child = layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                
                # Add map widget to layout
                layout.addWidget(self.map_widget)
                
                # Remove label margins and styling
                self.label.setContentsMargins(0, 0, 0, 0)
                self.label.setStyleSheet("""
                    QLabel {
                        margin: 0px;
                        padding: 0px;
                        border: none;
                        background: transparent;
                    }
                """)
                
                # Configure web settings for offline use
                settings_web = self.map_widget.settings()
                settings_web.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
                settings_web.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
                settings_web.setAttribute(QWebEngineSettings.ShowScrollBars, False)
                
                # Load offline map
                self.map_widget.load(QUrl.fromLocalFile(str(map_file_path.absolute())))
                self.map_widget.loadFinished.connect(self.on_offline_map_loaded)
                
                # Show map widget
                self.map_widget.show()
                
                logger.info("Offline map created and loaded")
            else:
                logger.warning("Map label not found, using text fallback")
                self.show_simple_map_fallback()
            
        except Exception as e:
            logger.error(f"Failed to create offline map: {e}")
            self.show_simple_map_fallback()
    
    def generate_offline_map_html(self) -> str:
        """Generate simple offline map HTML."""
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>UAV Offline Map</title>
            <meta charset="utf-8">
            <style>
                body { 
                    margin: 0; 
                    padding: 0; 
                    background-color: #2d2d30;
                    font-family: Arial, sans-serif;
                    color: white;
                }
                .map-container {
                    width: 100%;
                    height: 100vh;
                    position: relative;
                    background: linear-gradient(45deg, #1e3c72, #2a5298);
                }
                .map-grid {
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background-image: 
                        linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px);
                    background-size: 50px 50px;
                }
                .uav-marker {
                    position: absolute;
                    width: 20px;
                    height: 20px;
                    background-color: #ff4444;
                    border: 2px solid white;
                    border-radius: 50%;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    animation: pulse 2s infinite;
                }
                @keyframes pulse {
                    0% { box-shadow: 0 0 0 0 rgba(255, 68, 68, 0.7); }
                    70% { box-shadow: 0 0 0 10px rgba(255, 68, 68, 0); }
                    100% { box-shadow: 0 0 0 0 rgba(255, 68, 68, 0); }
                }
                .compass {
                    position: absolute;
                    top: 20px;
                    right: 20px;
                    width: 80px;
                    height: 80px;
                    border: 2px solid white;
                    border-radius: 50%;
                    background-color: rgba(0,0,0,0.7);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 14px;
                    font-weight: bold;
                }
                .coordinates {
                    position: absolute;
                    bottom: 20px;
                    left: 20px;
                    background-color: rgba(0,0,0,0.7);
                    padding: 10px;
                    border-radius: 5px;
                    font-size: 12px;
                }
                .status {
                    position: absolute;
                    top: 20px;
                    left: 20px;
                    background-color: rgba(0,0,0,0.7);
                    padding: 10px;
                    border-radius: 5px;
                    font-size: 12px;
                }
                .offline-notice {
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -60%);
                    text-align: center;
                    background-color: rgba(0,0,0,0.8);
                    padding: 20px;
                    border-radius: 10px;
                    border: 1px solid #444;
                }
            </style>
        </head>
        <body>
            <div class="map-container">
                <div class="map-grid"></div>
                <div class="uav-marker"></div>
                
                <div class="compass">N</div>
                
                <div class="status">
                    <div>Durum: Çevrimdışı</div>
                    <div>Mod: Simülasyon</div>
                </div>
                
                <div class="coordinates">
                    <div>Lat: 39.9334°</div>
                    <div>Lon: 32.8597°</div>
                    <div>Alt: 0 m</div>
                </div>
                
                <div class="offline-notice">
                    <h3>🗺️ Çevrimdışı Harita</h3>
                    <p>İnternet bağlantısı gerekli değil</p>
                    <p>Temel navigasyon ve UAV konumu gösterimi</p>
                    <small>Online harita için internet bağlantınızı kontrol edin</small>
                </div>
            </div>
            
            <script>
                // Simple JavaScript for offline map functionality
                console.log("Offline map loaded successfully");
                
                // Update coordinates periodically (simulation)
                function updateCoordinates() {
                    const coordDiv = document.querySelector('.coordinates');
                    const lat = (39.9334 + (Math.random() - 0.5) * 0.001).toFixed(6);
                    const lon = (32.8597 + (Math.random() - 0.5) * 0.001).toFixed(6);
                    const alt = Math.floor(Math.random() * 100);
                    
                    coordDiv.innerHTML = `
                        <div>Lat: ${lat}°</div>
                        <div>Lon: ${lon}°</div>
                        <div>Alt: ${alt} m</div>
                    `;
                }
                
                // Update every 5 seconds
                setInterval(updateCoordinates, 5000);
                
                // Hide offline notice after 5 seconds
                setTimeout(() => {
                    const notice = document.querySelector('.offline-notice');
                    if (notice) {
                        notice.style.transition = 'opacity 1s';
                        notice.style.opacity = '0';
                        setTimeout(() => notice.remove(), 1000);
                    }
                }, 5000);
            </script>
        </body>
        </html>
        '''
    
    def show_simple_map_fallback(self):
        """Show a simple text-based map fallback."""
        fallback_text = """
🗺️ HANGİ HARITA MODU:

📍 Konum Bilgisi:
   Enlem: 39.9334°
   Boylam: 32.8597°
   İrtifa: 0 m

🔄 Durum: Çevrimdışı
📡 Bağlantı: Yok

ℹ️ Harita yüklenemiyor
   • İnternet bağlantısını kontrol edin
   • Güvenlik duvarı ayarlarını kontrol edin
   • Daha sonra tekrar deneyin

UAV kontrolleri normal çalışmaya devam edecek.
        """
        
        if hasattr(self, 'label'):
            self.label.setText(fallback_text)
            self.label.setStyleSheet("""
                color: #00ff00; 
                font-size: 11pt; 
                font-family: 'Courier New', monospace;
                background-color: #1e1e1e; 
                padding: 20px;
                border: 1px solid #444;
            """)
    
    def on_offline_map_loaded(self, success):
        """Handle offline map load completion."""
        if success:
            self.label.setText("")
            self.label.setStyleSheet("background: transparent;")
            logger.info("Offline map loaded successfully")
        else:
            logger.warning("Offline map failed to load, showing fallback")
            self.show_simple_map_fallback()
    
    def setup_hud_view(self):
        """Setup the HUD (Heads-Up Display) component."""
        if not hasattr(self, 'label_2') or not HUDWidget:
            logger.warning("HUD widget not available")
            return
        
        try:
            # Create HUD widget with label_2 as parent
            self.hud_widget = HUDWidget(self.label_2)
            
            # Configure HUD to completely fill label_2
            self.hud_widget.setGeometry(0, 0, self.label_2.width(), self.label_2.height())
            self.hud_widget.resize(self.label_2.size())
            
            # Set size policies to ensure HUD expands to fill the entire space
            from PyQt5.QtWidgets import QSizePolicy
            self.hud_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.hud_widget.setMinimumSize(self.label_2.size())
            self.hud_widget.setMaximumSize(self.label_2.size())
            
            # Clear label content and make it transparent
            self.label_2.setText("")
            self.label_2.setStyleSheet("border: none; background: transparent;")
            
            # Make sure label_2 also expands properly
            self.label_2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            
            # Show HUD and bring to front
            self.hud_widget.show()
            self.hud_widget.raise_()
            
            # Set initial connection state
            self.hud_widget.setConnectionState(False)
            
            # Connect resize event to update HUD size when label_2 is resized
            self.label_2.resizeEvent = self.on_hud_container_resize
            
            logger.info("HUD view setup completed")
            
        except Exception as e:
            logger.error(f"HUD setup failed: {e}")
            if hasattr(self, 'label_2'):
                self.label_2.setText(f"HUD yüklenemedi: {str(e)}")
                self.label_2.setStyleSheet("color: red; font-size: 12pt;")
    
    def setup_ui_connections(self):
        """Setup UI button connections and signals."""
        try:
            # Connection buttons
            if hasattr(self, 'baglan'):
                self.baglan.clicked.connect(self.connect_drone)
            if hasattr(self, 'baglantiKapat'):
                self.baglantiKapat.clicked.connect(self.disconnect_drone)
            if hasattr(self, 'armDisarm'):
                self.armDisarm.clicked.connect(self.toggle_arm_disarm)
            
            # Flight mode buttons
            if hasattr(self, 'AUTO'):
                self.AUTO.clicked.connect(lambda: self.set_flight_mode("AUTO"))
            if hasattr(self, 'GUIDED'):
                self.GUIDED.clicked.connect(lambda: self.set_flight_mode("GUIDED"))
            if hasattr(self, 'RTL'):
                self.RTL.clicked.connect(lambda: self.set_flight_mode("RTL"))
            if hasattr(self, 'TAKEOFF'):
                self.TAKEOFF.clicked.connect(lambda: self.set_flight_mode("TAKEOFF"))
            
            # Camera control
            if hasattr(self, 'kameraAc'):
                self.kameraAc.clicked.connect(self.open_camera_window)
            
            logger.info("UI connections setup completed")
            
        except Exception as e:
            logger.error(f"Failed to setup UI connections: {e}")
    
    def setup_timers(self):
        """Setup update timers."""
        try:
            # Clock timer
            self.clock_timer = QTimer(self)
            self.clock_timer.timeout.connect(self.update_server_time)
            self.clock_timer.start(1000)  # Update every second
            
            # Telemetry timer
            self.telemetry_timer = QTimer(self)
            self.telemetry_timer.timeout.connect(self.update_telemetry_display)
            self.telemetry_timer.start(settings.TELEMETRY_UPDATE_RATE)
            
            logger.info("Timers setup completed")
            
        except Exception as e:
            logger.error(f"Failed to setup timers: {e}")
    
    def initialize_map(self):
        """Initialize the map component with fallback options."""
        # Skip complex map initialization, use simple offline map instead
        logger.info("Map initialization completed (offline mode)")
        
        # Optional: Try to detect internet connectivity
        try:
            import urllib.request
            urllib.request.urlopen('https://www.google.com', timeout=3)
            logger.info("Internet connection detected - online maps could be enabled")
        except:
            logger.info("No internet connection - using offline map mode")
    
    def start_map_server(self):
        """Disabled - using offline map instead."""
        logger.info("Map server not needed for offline mode")
    
    def connect_drone(self):
        """Connect to the drone."""
        if not hasattr(self, 'ihaInformer'):
            logger.error("UI informer widget not found")
            return
        
        try:
            self.ihaInformer.append("🔄 İHA'ya bağlanılıyor...")
            
            # Get connection string from UI
            connection_string = self.get_connection_string()
            
            # Try DroneKit first for COM ports
            if "COM" in connection_string.upper():
                success = self.connect_dronekit(connection_string)
            else:
                success = False
            
            # Fallback to MAVLink
            if not success and self.mavlink_client:
                success = self.mavlink_client.connect(connection_string)
                if success:
                    self.connection_active = True
                    self.ihaInformer.append("✅ İHA bağlantısı başarılı! (MAVLink)")
            
            if success:
                # Enable flight controls
                self.enable_flight_controls()
                
                # Update connection status
                if hasattr(self, 'baglanti'):
                    self.baglanti.setText("Bağlantı: 🟢 Aktif")
                    
                # Start telemetry updates
                self.setup_telemetry_timer()
                
                # Get initial telemetry and update map
                initial_telemetry = self.get_current_telemetry()
                if initial_telemetry:
                    self.update_map_with_uav_data(initial_telemetry)
                    
                self.ihaInformer.append(f"📡 Telemetri verisi alınıyor...")
                logger.info("Drone connection successful, telemetry started")
            else:
                self.ihaInformer.append("❌ Bağlantı başarısız! Ayarları kontrol edin.")
                
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.ihaInformer.append(f"🚫 Bağlantı hatası: {str(e)}")
    
    def setup_telemetry_timer(self):
        """Setup telemetry update timer."""
        if not hasattr(self, 'telemetry_timer'):
            self.telemetry_timer = QTimer()
            self.telemetry_timer.timeout.connect(self.update_telemetry_display)
        
        # Start telemetry updates at configured rate
        update_rate = getattr(settings, 'TELEMETRY_UPDATE_RATE', 100)  # Default 100ms
        self.telemetry_timer.start(update_rate)
        logger.info(f"Telemetry timer started with {update_rate}ms interval")
    
    def connect_dronekit(self, connection_string: str) -> bool:
        """Connect using DroneKit."""
        try:
            self.uav = dronekit.connect(connection_string, wait_ready=True, timeout=15)
            if self.uav:
                self.connection_active = True
                logger.info("DroneKit connection successful")
                return True
        except Exception as e:
            logger.error(f"DroneKit connection failed: {e}")
        return False
    
    def get_connection_string(self) -> str:
        """Get connection string from UI selection."""
        if not hasattr(self, 'portList'):
            return "udp:127.0.0.1:14550"
        
        try:
            selected_port = self.portList.currentText().strip()
            
            if "COM" in selected_port.upper():
                # Extract COM port
                if "(" in selected_port:
                    com_port = selected_port.split()[0]
                else:
                    com_port = selected_port
                return f"{com_port},{settings.DEFAULT_BAUD_RATE}"
            else:
                return "udp:127.0.0.1:14550"
                
        except Exception as e:
            logger.error(f"Failed to get connection string: {e}")
            return "udp:127.0.0.1:14550"
    
    def disconnect_drone(self):
        """Disconnect from the drone."""
        try:
            self.connection_active = False
            
            # Stop telemetry updates
            if hasattr(self, 'telemetry_timer'):
                self.telemetry_timer.stop()
                logger.info("Telemetry timer stopped")
            
            # Close DroneKit connection
            if self.uav:
                self.uav.close()
                self.uav = None
                logger.info("DroneKit connection closed")
            
            # Close MAVLink connection
            if self.mavlink_client:
                self.mavlink_client.disconnect()
                logger.info("MAVLink connection closed")
            
            # Update UI
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append("📡 İHA bağlantısı kesildi.")
            if hasattr(self, 'baglanti'):
                self.baglanti.setText("Bağlantı: 🔴 Kapalı")
            
            self.disable_flight_controls()
            logger.info("Drone disconnected successfully")
            
        except Exception as e:
            logger.error(f"Disconnection failed: {e}")
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append(f"🚫 Bağlantı kesme hatası: {str(e)}")
    
    def set_flight_mode(self, mode: str):
        """Set flight mode."""
        if not self.connection_active:
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append("İHA bağlı değil!")
            return
        
        try:
            success = False
            
            # Try DroneKit first
            if self.uav:
                from dronekit import VehicleMode
                self.uav.mode = VehicleMode(mode)
                success = True
                logger.info(f"Set mode to {mode} via DroneKit")
            
            # Fallback to MAVLink
            elif self.mavlink_client:
                success = self.mavlink_client.set_mode(mode)
                logger.info(f"Set mode to {mode} via MAVLink")
            
            if hasattr(self, 'ihaInformer'):
                if success:
                    self.ihaInformer.append(f"Uçuş modu {mode} olarak ayarlandı")
                else:
                    self.ihaInformer.append(f"Uçuş modu değiştirilemedi: {mode}")
                    
        except Exception as e:
            logger.error(f"Failed to set flight mode: {e}")
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append(f"Uçuş modu hatası: {str(e)}")
    
    def toggle_arm_disarm(self):
        """Toggle arm/disarm state."""
        if not self.connection_active:
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append("İHA bağlı değil!")
            return
        
        try:
            success = False
            
            # Try DroneKit first
            if self.uav:
                current_armed = self.uav.armed
                if current_armed:
                    self.uav.armed = False
                    action = "disarm"
                else:
                    if self.uav.is_armable:
                        self.uav.armed = True
                        action = "arm"
                    else:
                        if hasattr(self, 'ihaInformer'):
                            self.ihaInformer.append("İHA arm edilemiyor! Gerekli şartlar sağlanmadı.")
                        return
                success = True
                
            # Fallback to MAVLink
            elif self.mavlink_client:
                telemetry = self.mavlink_client.get_telemetry_data()
                current_armed = telemetry.get("armed", False)
                success = self.mavlink_client.arm_disarm(not current_armed)
                action = "disarm" if current_armed else "arm"
            
            if hasattr(self, 'ihaInformer'):
                if success:
                    self.ihaInformer.append(f"İHA {action} komutu gönderildi.")
                else:
                    self.ihaInformer.append("Arm/Disarm komutu gönderilemedi.")
                    
        except Exception as e:
            logger.error(f"Arm/Disarm failed: {e}")
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append(f"Arm/Disarm hatası: {str(e)}")
    
    def enable_flight_controls(self):
        """Enable flight control buttons."""
        controls = ['AUTO', 'GUIDED', 'RTL', 'TAKEOFF', 'armDisarm']
        for control in controls:
            if hasattr(self, control):
                getattr(self, control).setEnabled(True)
    
    def disable_flight_controls(self):
        """Disable flight control buttons."""
        controls = ['AUTO', 'GUIDED', 'RTL', 'TAKEOFF', 'armDisarm']
        for control in controls:
            if hasattr(self, control):
                getattr(self, control).setEnabled(False)
    
    def open_camera_window(self):
        """Open antenna system and video receiver window."""
        try:
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append("🔄 Anten sistemi başlatılıyor...")
            
            # Import antenna controller and video receiver
            from ...communication.antenna_controller import AntennaController
            from .video_receiver_widget import VideoDisplayWidget
            
            # Initialize antenna controller if not exists
            if not hasattr(self, 'antenna_controller'):
                self.antenna_controller = AntennaController()
            
            # Start antenna system (PowerBeam listening + Rocket M5 streaming)
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append("🔧 PowerBeam 5AC Gen2 dinleme moduna alınıyor...")
            
            antenna_success = self.antenna_controller.start_antenna_system()
            
            if antenna_success:
                if hasattr(self, 'ihaInformer'):
                    self.ihaInformer.append("✅ PowerBeam 5AC Gen2 dinleme modunda")
                    self.ihaInformer.append("✅ Rocket M5 video akışı başlatıldı")
                    self.ihaInformer.append("🎥 Video görüntüleyici açılıyor...")
                
                # Create video receiver window
                self.video_window = VideoDisplayWidget()
                self.video_window.setWindowTitle("Rocket M5 Video Akışı - Hüma UAV")
                self.video_window.setMinimumSize(800, 600)
                self.video_window.show()
                
                # Auto-start video reception
                self.video_window.start_video_stream()
                
                logger.info("Antenna system and video receiver started successfully")
                
                if hasattr(self, 'ihaInformer'):
                    self.ihaInformer.append("✅ Rocket M5 görüntüsü alınmaya başladı!")
            else:
                if hasattr(self, 'ihaInformer'):
                    self.ihaInformer.append("❌ Anten sistemi başlatılamadı!")
                    self.ihaInformer.append("🔍 PowerBeam ve Rocket M5 bağlantılarını kontrol edin")
                logger.error("Failed to start antenna system")
            
        except ImportError as e:
            logger.error(f"Failed to import antenna modules: {e}")
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append(f"❌ Anten modülleri yüklenemedi: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to open antenna system: {e}")
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append(f"❌ Anten sistemi hatası: {str(e)}")
    
    def start_camera_process(self):
        """Start camera process."""
        try:
            # Define camera script path
            camera_script = settings.PROJECT_ROOT / "src" / "uav_system" / "computer_vision" / "camera_system.py"
            
            if camera_script.exists():
                self.camera_process = subprocess.Popen(
                    [sys.executable, str(camera_script)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                logger.info("Camera process started")
            else:
                logger.error(f"Camera script not found: {camera_script}")
                
        except Exception as e:
            logger.error(f"Failed to start camera process: {e}")
    
    def update_server_time(self):
        """Update server time display."""
        if hasattr(self, 'sunucuSaati'):
            current_time = QDateTime.currentDateTime().toString('yyyy-MM-dd hh:mm:ss')
            self.sunucuSaati.setText(f"Sunucu Saati: {current_time}")
    
    def update_telemetry_display(self):
        """Update telemetry display."""
        if not self.connection_active:
            return
        
        try:
            # Get telemetry data
            telemetry = self.get_current_telemetry()
            
            if not telemetry:
                return
            
            # Update HUD if available
            if self.hud_widget:
                self.hud_widget.updateData(telemetry)
                self.hud_widget.setConnectionState(self.connection_active)
            
            # Update UI labels
            self.update_ui_labels(telemetry)
            
            # Update map with UAV data - use the new method
            self.update_map_with_uav_data({
                'lat': telemetry.get('lat', self.current_telemetry['lat']),
                'lon': telemetry.get('lon', self.current_telemetry['lon']),
                'alt': telemetry.get('altitude', self.current_telemetry['alt']),
                'yaw': telemetry.get('yaw', self.current_telemetry['heading']),
                'mode': telemetry.get('flightMode', self.current_telemetry['flight_mode']),
                'armed': telemetry.get('armed', self.current_telemetry['armed'])
            })
                
        except Exception as e:
            logger.error(f"Telemetry update failed: {e}")
    
    def get_current_telemetry(self) -> Dict[str, Any]:
        """Get current telemetry data."""
        telemetry = {}
        
        try:
            # Try DroneKit first
            if self.uav:
                telemetry = {
                    "lat": float(self.uav.location.global_relative_frame.lat or 0),
                    "lon": float(self.uav.location.global_relative_frame.lon or 0),
                    "altitude": float(self.uav.location.global_relative_frame.alt or 0),
                    "roll": math.degrees(float(self.uav.attitude.roll or 0)),
                    "pitch": math.degrees(float(self.uav.attitude.pitch or 0)),
                    "yaw": math.degrees(float(self.uav.attitude.yaw or 0)),
                    "airspeed": float(self.uav.airspeed or 0),
                    "groundspeed": float(self.uav.groundspeed or 0),
                    "armed": bool(self.uav.armed),
                    "flightMode": str(self.uav.mode.name),
                    "batteryLevel": float(self.uav.battery.level or 0),
                    "batteryVoltage": float(self.uav.battery.voltage or 0),
                    "gps_fix": int(self.uav.gps_0.fix_type if hasattr(self.uav, 'gps_0') else 0),
                    "satellites": int(self.uav.gps_0.satellites_visible if hasattr(self.uav, 'gps_0') else 0),
                }
                
                # Update current telemetry cache
                self.current_telemetry.update(telemetry)
            
            # Fallback to MAVLink
            elif self.mavlink_client:
                telemetry = self.mavlink_client.get_telemetry_data()
                if telemetry:
                    self.current_telemetry.update(telemetry)
                    
        except Exception as e:
            logger.error(f"Failed to get telemetry: {e}")
        
        return telemetry or self.current_telemetry
    
    def update_map_with_uav_data(self, uav_data: Dict[str, Any]):
        """Update map with UAV position and data."""
        try:
            if not uav_data:
                return
                
            lat = uav_data.get('lat', self.current_telemetry['lat'])
            lon = uav_data.get('lon', self.current_telemetry['lon'])
            alt = uav_data.get('alt', self.current_telemetry['alt'])
            heading = uav_data.get('yaw', self.current_telemetry['heading'])
            
            # Update Leaflet map if available
            if hasattr(self, 'leaflet_map') and self.leaflet_map and self.leaflet_map.map_loaded:
                self.leaflet_map.update_uav_position(lat, lon, heading)
                
                # Auto-center on UAV if this is the first position update
                if not hasattr(self, '_map_centered_on_uav'):
                    self.leaflet_map.set_map_center(lat, lon, 15)
                    self._map_centered_on_uav = True
                    
            # Update other map widget if available
            elif hasattr(self, 'map_widget') and self.map_widget:
                try:
                    js_code = f"""
                    if (typeof updateUAVPosition === 'function') {{
                        updateUAVPosition({lat}, {lon}, {heading});
                    }}
                    if (typeof map !== 'undefined' && map && map.setView) {{
                        map.setView([{lat}, {lon}], map.getZoom());
                    }}
                    """
                    self.map_widget.page().runJavaScript(js_code)
                except Exception as e:
                    logger.debug(f"JavaScript execution failed: {e}")
            
            # Update current telemetry cache
            self.current_telemetry.update({
                'lat': lat,
                'lon': lon,
                'alt': alt,
                'heading': heading
            })
            
            logger.debug(f"Map updated with UAV position: {lat:.6f}, {lon:.6f}, heading: {heading:.1f}°")
            
        except Exception as e:
            logger.error(f"Failed to update map with UAV data: {e}")
    
    def toggle_arm_disarm(self):
        """Toggle arm/disarm state."""
        if not self.connection_active:
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append("İHA bağlı değil!")
            return
        
        try:
            success = False
            current_armed = False
            
            # Get current armed state
            if self.uav:
                current_armed = self.uav.armed
            elif self.mavlink_client:
                telemetry = self.mavlink_client.get_telemetry_data()
                current_armed = telemetry.get('armed', False) if telemetry else False
            
            # Toggle arm/disarm
            if current_armed:
                # Disarm
                if self.uav:
                    self.uav.armed = False
                    success = True
                    action = "Disarmed"
                elif self.mavlink_client:
                    success = self.mavlink_client.disarm()
                    action = "Disarmed"
            else:
                # Arm
                if self.uav:
                    self.uav.armed = True
                    success = True
                    action = "Armed"
                elif self.mavlink_client:
                    success = self.mavlink_client.arm()
                    action = "Armed"
            
            if hasattr(self, 'ihaInformer'):
                if success:
                    self.ihaInformer.append(f"İHA {action}")
                    # Update button text
                    if hasattr(self, 'armDisarm'):
                        self.armDisarm.setText("DISARM" if not current_armed else "ARM")
                else:
                    self.ihaInformer.append(f"Arm/Disarm işlemi başarısız")
                    
        except Exception as e:
            logger.error(f"Failed to toggle arm/disarm: {e}")
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append(f"Arm/Disarm hatası: {str(e)}")
    
    def update_ui_labels(self, telemetry: Dict[str, Any]):
        """Update UI labels with telemetry data."""
        try:
            labels = {
                'enlem': f"Lat: {telemetry.get('lat', 0):.6f}°",
                'boylam': f"Lon: {telemetry.get('lon', 0):.6f}°",
                'irtifa': f"Alt: {telemetry.get('altitude', 0):.1f}m",
                'roll': f"Roll: {telemetry.get('roll', 0):+.1f}°",
                'pitch': f"Pitch: {telemetry.get('pitch', 0):+.1f}°",
                'yaw': f"Yaw: {telemetry.get('yaw', 0):.1f}°",
                'havaHizi': f"AS: {telemetry.get('airspeed', 0):.1f}m/s",
                'yerHizi': f"GS: {telemetry.get('groundspeed', 0):.1f}m/s",
                'mevcutUcusModu': f"Mode: {telemetry.get('flightMode', 'UNKNOWN')}",
                'armDurum': f"{'ARMED' if telemetry.get('armed', False) else 'DISARMED'}",
            }
            
            for label_name, text in labels.items():
                if hasattr(self, label_name):
                    getattr(self, label_name).setText(text)
            
            # Update HUD widget if available
            if hasattr(self, 'hud_widget') and self.hud_widget:
                self.hud_widget.updateData(telemetry)
                    
        except Exception as e:
            logger.error(f"Failed to update UI labels: {e}")
    
    def show_map_error(self, error_msg: str):
        """Show map error message."""
        if hasattr(self, 'label'):
            self.label.setText(f"Harita Hatası: {error_msg}")
            self.label.setStyleSheet("color: red; font-size: 12pt; padding: 20px;")
    
    def on_map_timeout(self):
        """Handle map loading timeout - fallback to offline mode."""
        logger.warning("Map loading timeout - switching to offline mode")
        self.show_simple_map_fallback()
    
    def closeEvent(self, event):
        """Handle application close event."""
        try:
            # Show confirmation dialog
            reply = QMessageBox.question(
                self, 'Çıkış', 'Uygulamayı kapatmak istediğinize emin misiniz?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Cleanup antenna system first
                self.close_antenna_system()
                
                # Cleanup drone connection
                self.disconnect_drone()
                
                # Stop processes
                if self.camera_process:
                    self.camera_process.terminate()
                if self.camera_window_process:
                    self.camera_window_process.terminate()
                
                event.accept()
                logger.info("Application closed")
            else:
                event.ignore()
                
        except Exception as e:
            logger.error(f"Close event error: {e}")
            event.accept()
    
    def on_hud_container_resize(self, event):
        """Handle resize events for the HUD container (label_2)."""
        if hasattr(self, 'hud_widget') and self.hud_widget:
            # Update HUD widget size to match its container
            container_size = self.label_2.size()
            self.hud_widget.setGeometry(0, 0, container_size.width(), container_size.height())
            self.hud_widget.resize(container_size)
            self.hud_widget.setMinimumSize(container_size)
            self.hud_widget.setMaximumSize(container_size)
            self.hud_widget.raise_()  # Keep HUD on top
            self.hud_widget.update()  # Force repaint
        
        # Call the original resize event if it exists
        if hasattr(self.label_2.__class__, 'resizeEvent'):
            super(self.label_2.__class__, self.label_2).resizeEvent(event)
    
    def resizeEvent(self, event):
        """Handle window resize events to keep map widget fitted."""
        super().resizeEvent(event)
        
        try:
            # Resize Leaflet map if it exists - force refresh for proper scaling
            if hasattr(self, 'leaflet_map') and self.leaflet_map:
                # Ensure the map widget fills the entire label area
                if hasattr(self, 'label') and self.label:
                    # Update label layout to ensure no margins
                    if self.label.layout():
                        self.label.layout().setContentsMargins(0, 0, 0, 0)
                        self.label.layout().setSpacing(0)
                    
                    # Force map resize after a small delay
                    QTimer.singleShot(100, lambda: self.leaflet_map.force_refresh_map() if self.leaflet_map else None)
            
            # Resize offline map widget if it exists
            elif hasattr(self, 'map_widget') and self.map_widget and hasattr(self, 'label'):
                # Ensure map widget uses the entire label area
                if self.label.layout():
                    # Layout handles the sizing automatically
                    self.label.layout().setContentsMargins(0, 0, 0, 0)
                    self.label.layout().setSpacing(0)
                else:
                    # Manual sizing if no layout
                    self.map_widget.setGeometry(0, 0, self.label.width(), self.label.height())
                    self.map_widget.resize(self.label.size())
                
        except Exception as e:
            logger.error(f"Error in resizeEvent: {e}")
    
    def set_webengine_status(self, available: bool):
        """Set WebEngine availability status."""
        self.webengine_available = available
        logger.info(f"WebEngine availability set to: {available}")
        
        # Update map widget if it exists
        if hasattr(self, 'leaflet_map') and self.leaflet_map:
            self.leaflet_map.set_webengine_status(available)
    
    def close_antenna_system(self):
        """Close antenna system and video receiver."""
        try:
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append("🔄 Anten sistemi kapatılıyor...")
            
            # Stop antenna system
            if hasattr(self, 'antenna_controller'):
                antenna_stopped = self.antenna_controller.stop_antenna_system()
                
                if antenna_stopped:
                    if hasattr(self, 'ihaInformer'):
                        self.ihaInformer.append("✅ PowerBeam 5AC Gen2 normal moda döndürüldü")
                        self.ihaInformer.append("✅ Rocket M5 video akışı durduruldu")
                else:
                    if hasattr(self, 'ihaInformer'):
                        self.ihaInformer.append("⚠️ Anten sistemi kısmen kapatıldı")
            
            # Close video window
            if hasattr(self, 'video_window'):
                self.video_window.stop_video_stream()
                self.video_window.close()
                delattr(self, 'video_window')
                
                if hasattr(self, 'ihaInformer'):
                    self.ihaInformer.append("✅ Video görüntüleyici kapatıldı")
            
            logger.info("Antenna system closed successfully")
            
        except Exception as e:
            logger.error(f"Error closing antenna system: {e}")
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append(f"❌ Anten sistemi kapatma hatası: {str(e)}")


def main():
    """Main application entry point."""
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("Hüma GCS")
        app.setApplicationVersion("2.0")
        
        # Create and show main window
        window = HumaGCS()
        window.show()
        
        # Run application
        sys.exit(app.exec_())
        
    except Exception as e:
        logger.error(f"Application failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

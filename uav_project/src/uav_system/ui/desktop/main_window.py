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
    QMessageBox, QInputDialog, QMenu, QShortcut
)
from PyQt5.QtCore import QTimer, QDateTime, QUrl, Qt, pyqtSlot
from PyQt5 import QtCore, uic
from PyQt5.QtGui import QDesktopServices, QKeySequence
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
        
        # Status tracking
        self.last_status_update = 0
        
        # Initialize UI and systems
        self.setup_ui()
        self.setup_communication()
        self.setup_components()
        
        # Setup autonomous operations
        self.setup_autonomous_operations_menu()
        self.setup_keyboard_shortcuts()
        self.add_autonomous_operations_to_ui()
        
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
            
            # Initialize the client
            if self.mavlink_client.initialize():
                self.mavlink_client.start()
                logger.info("MAVLink client initialized successfully")
            else:
                logger.error("Failed to initialize MAVLink client")
                
        except Exception as e:
            logger.error(f"Failed to setup communication: {e}")
    
    def setup_components(self):
        """Initialize UI components."""
        try:
            # Setup map view
            self.setup_map_view()
            
            # Setup HUD view
            self.setup_hud_view()
            
            logger.info("Components setup completed")
            
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
                self.TAKEOFF.clicked.connect(self.autonomous_takeoff_handler)
            
            # Camera control
            if hasattr(self, 'kameraAc'):
                self.kameraAc.clicked.connect(self.open_camera_window)
            
            # Additional autonomous operation buttons
            # We'll use existing buttons and add new functionality
            
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
            self.telemetry_timer.timeout.connect(self.update_telemetry)
            self.telemetry_timer.start(settings.TELEMETRY_UPDATE_RATE)  # Update based on settings
            
            # Status display timer
            self.status_timer = QTimer(self)
            self.status_timer.timeout.connect(self.display_flight_status)
            self.status_timer.start(10000)  # Update every 10 seconds
            
            logger.info("Timers setup completed")
            
        except Exception as e:
            logger.error(f"Failed to setup timers: {e}")
    
    def update_server_time(self):
        """Update server time display."""
        try:
            if hasattr(self, 'serverTime'):
                current_time = QDateTime.currentDateTime()
                self.serverTime.setText(current_time.toString("hh:mm:ss"))
        except Exception as e:
            logger.error(f"Failed to update server time: {e}")
    
    def update_telemetry(self):
        """Update telemetry data and UI."""
        try:
            if not self.connection_active or not self.mavlink_client:
                return
            
            # Get telemetry data
            telemetry = self.mavlink_client.get_telemetry_data()
            
            # Update current telemetry
            if telemetry:
                self.current_telemetry.update(telemetry)
                
                # Update UI labels
                self.update_ui_labels(telemetry)
                
                # Update map with UAV data
                self.update_map_with_uav_data(telemetry)
                
        except Exception as e:
            logger.error(f"Failed to update telemetry: {e}")

    def autonomous_takeoff_handler(self):
        """Handle autonomous takeoff button click."""
        if not self.connection_active:
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append("❌ İHA bağlı değil!")
            return
        
        try:
            # Get takeoff altitude from user
            altitude, ok = QInputDialog.getDouble(
                self, 
                'Otonom Kalkış', 
                'Kalkış irtifasını girin (metre):', 
                value=50.0, 
                min=10.0, 
                max=500.0, 
                decimals=1
            )
            
            if not ok:
                return
            
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append(f"🚁 Otonom kalkış başlatılıyor - İrtifa: {altitude}m")
            
            # Perform autonomous takeoff
            success = False
            
            # Try MAVLink client first
            if self.mavlink_client:
                success = self.mavlink_client.autonomous_takeoff(altitude)
                
            if success:
                if hasattr(self, 'ihaInformer'):
                    self.ihaInformer.append("✅ Otonom kalkış komutu başarıyla gönderildi!")
                    self.ihaInformer.append(f"🎯 Hedef irtifa: {altitude}m")
                    self.ihaInformer.append("📡 Uçuş modu: AUTO")
                logger.info(f"Autonomous takeoff initiated to {altitude}m")
            else:
                if hasattr(self, 'ihaInformer'):
                    self.ihaInformer.append("❌ Otonom kalkış başarısız!")
                    self.ihaInformer.append("🔍 Bağlantı ve GPS durumunu kontrol edin")
                logger.error("Autonomous takeoff failed")
                
        except Exception as e:
            logger.error(f"Autonomous takeoff handler error: {e}")
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append(f"❌ Otonom kalkış hatası: {str(e)}")

    def autonomous_land_handler(self):
        """Handle autonomous landing."""
        if not self.connection_active:
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append("❌ İHA bağlı değil!")
            return
        
        try:
            # Get current location and altitude
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append("🔍 Mevcut konum alınıyor...")
            
            location = None
            current_alt = None
            
            if self.mavlink_client:
                location = self.mavlink_client.get_location()
                current_alt = self.mavlink_client.get_current_altitude()
            
            if not location:
                if hasattr(self, 'ihaInformer'):
                    self.ihaInformer.append("❌ Mevcut konum alınamadı!")
                return
            
            lat, lon = location
            
            # Use current altitude if available, otherwise default
            if current_alt is None:
                current_alt = 100.0  # Default altitude
            
            # Get cruise altitude for approach
            cruise_alt, ok = QInputDialog.getDouble(
                self, 
                'Otonom İniş', 
                'Yaklaşma irtifasını girin (metre):', 
                value=50.0, 
                min=20.0, 
                max=200.0, 
                decimals=1
            )
            
            if not ok:
                return
            
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append(f"🛬 Otonom iniş başlatılıyor...")
                self.ihaInformer.append(f"📍 İniş konumu: {lat:.6f}, {lon:.6f}")
                self.ihaInformer.append(f"🎯 Yaklaşma irtifası: {cruise_alt}m")
            
            # Perform autonomous landing
            success = False
            
            if self.mavlink_client:
                success = self.mavlink_client.autonomous_land(lon, lat, current_alt, cruise_alt)
                
            if success:
                if hasattr(self, 'ihaInformer'):
                    self.ihaInformer.append("✅ Otonom iniş komutu başarıyla gönderildi!")
                    self.ihaInformer.append("🎯 İniş sırası: Yaklaşma → İniş")
                    self.ihaInformer.append("📡 Uçuş modu: AUTO")
                logger.info(f"Autonomous landing initiated at {lat:.6f}, {lon:.6f}")
            else:
                if hasattr(self, 'ihaInformer'):
                    self.ihaInformer.append("❌ Otonom iniş başarısız!")
                    self.ihaInformer.append("🔍 Bağlantı ve GPS durumunu kontrol edin")
                logger.error("Autonomous landing failed")
                
        except Exception as e:
            logger.error(f"Autonomous landing handler error: {e}")
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append(f"❌ Otonom iniş hatası: {str(e)}")

    def emergency_stop_handler(self):
        """Handle emergency stop."""
        if not self.connection_active:
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append("❌ İHA bağlı değil!")
            return
        
        try:
            # Show confirmation dialog
            reply = QMessageBox.question(
                self, 
                'Acil Durum', 
                'ACİL DURUM: İHA\'yı RTL moduna geçir?\n\n' +
                'Bu komut İHA\'yı ev konumuna geri döndürür.',
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                if hasattr(self, 'ihaInformer'):
                    self.ihaInformer.append("🚨 ACİL DURUM: RTL modu etkinleştiriliyor...")
                
                success = False
                
                if self.mavlink_client:
                    success = self.mavlink_client.emergency_stop()
                
                if success:
                    if hasattr(self, 'ihaInformer'):
                        self.ihaInformer.append("✅ İHA RTL moduna geçirildi!")
                        self.ihaInformer.append("🏠 İHA ev konumuna dönüyor...")
                    logger.info("Emergency stop activated - RTL mode")
                else:
                    if hasattr(self, 'ihaInformer'):
                        self.ihaInformer.append("❌ Acil durum komutu başarısız!")
                    logger.error("Emergency stop failed")
                    
        except Exception as e:
            logger.error(f"Emergency stop handler error: {e}")
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append(f"❌ Acil durum hatası: {str(e)}")

    def setup_autonomous_operations_menu(self):
        """Setup autonomous operations menu or buttons."""
        try:
            # Create autonomous operations menu if menubar exists
            if hasattr(self, 'menubar'):
                autonomous_menu = self.menubar.addMenu('Otonom İşlemler')
                
                # Takeoff action
                takeoff_action = autonomous_menu.addAction('🚁 Otonom Kalkış')
                takeoff_action.triggered.connect(self.autonomous_takeoff_handler)
                
                # Landing action
                landing_action = autonomous_menu.addAction('🛬 Otonom İniş')
                landing_action.triggered.connect(self.autonomous_land_handler)
                
                # Emergency stop action
                autonomous_menu.addSeparator()
                emergency_action = autonomous_menu.addAction('🚨 Acil Durum (RTL)')
                emergency_action.triggered.connect(self.emergency_stop_handler)
                
                logger.info("Autonomous operations menu created")
            else:
                logger.warning("No menubar found for autonomous operations menu")
                
        except Exception as e:
            logger.error(f"Failed to setup autonomous operations menu: {e}")

    def setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for autonomous operations."""
        try:
            from PyQt5.QtGui import QKeySequence
            from PyQt5.QtWidgets import QShortcut
            
            # Autonomous takeoff - Ctrl+T
            takeoff_shortcut = QShortcut(QKeySequence('Ctrl+T'), self)
            takeoff_shortcut.activated.connect(self.autonomous_takeoff_handler)
            
            # Autonomous landing - Ctrl+L
            landing_shortcut = QShortcut(QKeySequence('Ctrl+L'), self)
            landing_shortcut.activated.connect(self.autonomous_land_handler)
            
            # Emergency stop - Ctrl+E
            emergency_shortcut = QShortcut(QKeySequence('Ctrl+E'), self)
            emergency_shortcut.activated.connect(self.emergency_stop_handler)
            
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append("⌨️ Klavye kısayolları:")
                self.ihaInformer.append("   Ctrl+T: Otonom Kalkış")
                self.ihaInformer.append("   Ctrl+L: Otonom İniş")
                self.ihaInformer.append("   Ctrl+E: Acil Durum (RTL)")
            
            logger.info("Keyboard shortcuts setup completed")
            
        except Exception as e:
            logger.error(f"Failed to setup keyboard shortcuts: {e}")

    def add_autonomous_operations_to_ui(self):
        """Add autonomous operations to the existing UI."""
        try:
            # Override RTL button to also support autonomous landing
            if hasattr(self, 'RTL'):
                # Disconnect existing RTL connection
                try:
                    self.RTL.clicked.disconnect()
                except:
                    pass
                
                # Connect to new handler that provides both RTL and autonomous landing
                self.RTL.clicked.connect(self.rtl_and_landing_handler)
                
                # Update button text to show dual functionality
                self.RTL.setText("RTL / İniş")
                self.RTL.setToolTip("Sol tık: RTL modu\nSağ tık: Otonom İniş")
            
            # Setup context menu for RTL button
            if hasattr(self, 'RTL'):
                self.RTL.setContextMenuPolicy(Qt.CustomContextMenu)
                self.RTL.customContextMenuRequested.connect(self.rtl_context_menu)
            
            logger.info("Autonomous operations added to UI")
            
        except Exception as e:
            logger.error(f"Failed to add autonomous operations to UI: {e}")

    def rtl_and_landing_handler(self):
        """Handle RTL button click - shows menu for RTL or autonomous landing."""
        try:
            from PyQt5.QtWidgets import QMenu
            
            # Create context menu
            menu = QMenu(self)
            
            # Add RTL action
            rtl_action = menu.addAction("🏠 RTL Modu")
            rtl_action.triggered.connect(lambda: self.set_flight_mode("RTL"))
            
            # Add autonomous landing action
            landing_action = menu.addAction("🛬 Otonom İniş")
            landing_action.triggered.connect(self.autonomous_land_handler)
            
            # Show menu at button position
            if hasattr(self, 'RTL'):
                menu.exec_(self.RTL.mapToGlobal(self.RTL.rect().bottomLeft()))
                
        except Exception as e:
            logger.error(f"RTL and landing handler error: {e}")

    def rtl_context_menu(self, position):
        """Show context menu for RTL button."""
        try:
            from PyQt5.QtWidgets import QMenu
            
            menu = QMenu(self)
            
            # Add RTL action
            rtl_action = menu.addAction("🏠 RTL Modu")
            rtl_action.triggered.connect(lambda: self.set_flight_mode("RTL"))
            
            # Add autonomous landing action
            landing_action = menu.addAction("🛬 Otonom İniş")
            landing_action.triggered.connect(self.autonomous_land_handler)
            
            # Add emergency stop action
            menu.addSeparator()
            emergency_action = menu.addAction("🚨 Acil Durum")
            emergency_action.triggered.connect(self.emergency_stop_handler)
            
            # Show menu
            if hasattr(self, 'RTL'):
                menu.exec_(self.RTL.mapToGlobal(position))
                
        except Exception as e:
            logger.error(f"RTL context menu error: {e}")

    def display_flight_status(self):
        """Display current flight status and autonomous operation status."""
        try:
            if not self.connection_active or not self.mavlink_client:
                return
            
            # Get current telemetry
            telemetry = self.mavlink_client.get_telemetry_data()
            
            # Display flight status
            if hasattr(self, 'ihaInformer'):
                flight_mode = telemetry.get('flight_mode', 'UNKNOWN')
                armed = telemetry.get('armed', False)
                altitude = telemetry.get('altitude', 0)
                lat = telemetry.get('lat', 0)
                lon = telemetry.get('lon', 0)
                
                status_text = f"📊 Uçuş Durumu:"
                status_text += f"\n   Mod: {flight_mode}"
                status_text += f"\n   Silahlanma: {'✅ Armed' if armed else '❌ Disarmed'}"
                status_text += f"\n   İrtifa: {altitude:.1f}m"
                status_text += f"\n   Konum: {lat:.6f}, {lon:.6f}"
                
                # Display if there's space in the informer
                if hasattr(self, 'last_status_update'):
                    if time.time() - self.last_status_update > 10:  # Update every 10 seconds
                        self.ihaInformer.append(status_text)
                        self.last_status_update = time.time()
                else:
                    self.ihaInformer.append(status_text)
                    self.last_status_update = time.time()
                
        except Exception as e:
            logger.error(f"Error displaying flight status: {e}")

    def connect_drone(self):
        """Connect to the drone."""
        try:
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append("📡 İHA'ya bağlanılıyor...")
            
            # Get connection string
            connection_string = self.get_connection_string()
            
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append(f"🔗 Bağlantı: {connection_string}")
            
            # Connect MAVLink client
            success = False
            if self.mavlink_client:
                success = self.mavlink_client.connect(connection_string)
            
            if success:
                self.connection_active = True
                if hasattr(self, 'ihaInformer'):
                    self.ihaInformer.append("✅ İHA bağlantısı kuruldu!")
                    
                if hasattr(self, 'baglanti'):
                    self.baglanti.setText("Bağlantı: 🟢 Aktif")
                
                self.enable_flight_controls()
                logger.info("Drone connected successfully")
            else:
                if hasattr(self, 'ihaInformer'):
                    self.ihaInformer.append("❌ İHA bağlantısı başarısız!")
                    
                if hasattr(self, 'baglanti'):
                    self.baglanti.setText("Bağlantı: 🔴 Başarısız")
                logger.error("Drone connection failed")
                
        except Exception as e:
            logger.error(f"Connection error: {e}")
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append(f"🚫 Bağlantı hatası: {str(e)}")
    
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
            
            # Use MAVLink client
            if self.mavlink_client:
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
            
            # Use MAVLink client
            if self.mavlink_client:
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
                'mevcutUcusModu': f"Mode: {telemetry.get('flight_mode', 'UNKNOWN')}",
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
    
    def update_map_with_uav_data(self, telemetry: Dict[str, Any]):
        """Update map with UAV data."""
        try:
            # Update leaflet map if available
            if hasattr(self, 'leaflet_map') and self.leaflet_map:
                lat = telemetry.get('lat', 0)
                lon = telemetry.get('lon', 0)
                heading = telemetry.get('heading', 0)
                if lat != 0 and lon != 0:
                    self.leaflet_map.update_uav_position(lat, lon, heading)
                    
        except Exception as e:
            logger.error(f"Failed to update map with UAV data: {e}")
    
    def open_camera_window(self):
        """Open antenna system and video receiver window."""
        try:
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append("🔄 Kamera sistemi başlatılıyor...")
            
            # Placeholder for camera opening logic
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append("📷 Kamera penceresi açılıyor...")
            
            logger.info("Camera window opened")
            
        except Exception as e:
            logger.error(f"Failed to open camera window: {e}")
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append(f"❌ Kamera hatası: {str(e)}")

    def closeEvent(self, event):
        """Handle application close event."""
        try:
            # Show confirmation dialog
            reply = QMessageBox.question(
                self, 'Çıkış', 'Uygulamayı kapatmak istediğinize emin misiniz?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Cleanup drone connection
                self.disconnect_drone()
                
                # Stop timers
                if hasattr(self, 'telemetry_timer'):
                    self.telemetry_timer.stop()
                if hasattr(self, 'clock_timer'):
                    self.clock_timer.stop()
                if hasattr(self, 'status_timer'):
                    self.status_timer.stop()
                
                # Cleanup MAVLink client
                if self.mavlink_client:
                    self.mavlink_client.cleanup()
                
                event.accept()
                logger.info("Application closed")
            else:
                event.ignore()
                
        except Exception as e:
            logger.error(f"Close event error: {e}")
            event.accept()

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

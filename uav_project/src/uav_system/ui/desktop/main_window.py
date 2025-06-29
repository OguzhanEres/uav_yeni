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
    from .map_widget import LeafletMap
except ImportError:
    logger.warning("LeafletMap not available")
    LeafletMap = None

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
        
        # UI components
        self.leaflet_map = None
        self.hud_widget = None
        self.map_widget = None
        
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
        """Setup the map view component."""
        if not hasattr(self, 'label'):
            logger.warning("Map label widget not found")
            return
        
        try:
            # Show loading message
            self.label.setText("Harita yükleniyor...\nLütfen bekleyin.")
            self.label.setStyleSheet(
                "color: blue; font-size: 14pt; background-color: #f0f0f0; padding: 20px;"
            )
            
            # Create web engine profile
            profile = QWebEngineProfile.defaultProfile()
            profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)
            profile.setHttpCacheType(QWebEngineProfile.MemoryHttpCache)
            
            # Create web view for map
            self.map_widget = QWebEngineView(self.label)
            
            # Configure web settings
            settings_web = self.map_widget.settings()
            settings_web.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            settings_web.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
            settings_web.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
            settings_web.setAttribute(QWebEngineSettings.ShowScrollBars, False)
            
            # Hide initially
            self.map_widget.hide()
            
            # Setup timeout timer
            self.map_timeout_timer = QTimer(self)
            self.map_timeout_timer.timeout.connect(self.on_map_timeout)
            self.map_timeout_timer.setSingleShot(True)
            self.map_timeout_timer.start(30000)  # 30 second timeout
            
            logger.info("Map view setup completed")
            
        except Exception as e:
            logger.error(f"Map view setup failed: {e}")
            self.show_map_error(f"Harita kurulumu hatası: {str(e)}")
    
    def setup_hud_view(self):
        """Setup the HUD (Heads-Up Display) component."""
        if not hasattr(self, 'label_2') or not HUDWidget:
            logger.warning("HUD widget not available")
            return
        
        try:
            # Create HUD widget
            self.hud_widget = HUDWidget(self.label_2)
            
            # Configure HUD
            self.hud_widget.setGeometry(0, 0, self.label_2.width(), self.label_2.height())
            self.hud_widget.resize(self.label_2.size())
            
            # Clear label content
            self.label_2.setText("")
            self.label_2.setStyleSheet("border: none; background: transparent;")
            
            # Show HUD
            self.hud_widget.show()
            self.hud_widget.raise_()
            
            # Set initial connection state
            self.hud_widget.setConnectionState(False)
            
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
        """Initialize the map component."""
        if not LeafletMap:
            self.show_map_error("Harita modülü bulunamadı.")
            return
        
        try:
            # Create map instance
            self.leaflet_map = LeafletMap()
            
            # Start map server in background thread
            import threading
            self.server_thread = threading.Thread(
                target=self.start_map_server,
                daemon=True
            )
            self.server_thread.start()
            
            logger.info("Map initialization started")
            
        except Exception as e:
            logger.error(f"Map initialization failed: {e}")
            self.show_map_error(f"Harita yüklenemedi: {str(e)}")
    
    def start_map_server(self):
        """Start the map server."""
        try:
            if self.leaflet_map:
                self.leaflet_map.start_map(port_no=settings.MAP_SERVER_PORT)
        except Exception as e:
            logger.error(f"Map server failed: {e}")
    
    def connect_drone(self):
        """Connect to the drone."""
        if not hasattr(self, 'ihaInformer'):
            logger.error("UI informer widget not found")
            return
        
        try:
            self.ihaInformer.append("İHA'ya bağlanılıyor...")
            
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
                    self.ihaInformer.append("✓ İHA bağlantısı başarılı! (MAVLink)")
            
            if success:
                self.enable_flight_controls()
                if hasattr(self, 'baglanti'):
                    self.baglanti.setText("Bağlantı: Aktif")
            else:
                self.ihaInformer.append("✗ Bağlantı başarısız!")
                
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.ihaInformer.append(f"Bağlantı hatası: {str(e)}")
    
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
            
            # Close DroneKit connection
            if self.uav:
                self.uav.close()
                self.uav = None
            
            # Close MAVLink connection
            if self.mavlink_client:
                self.mavlink_client.disconnect()
            
            # Update UI
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append("İHA bağlantısı kesildi.")
            if hasattr(self, 'baglanti'):
                self.baglanti.setText("Bağlantı: Kapalı")
            
            self.disable_flight_controls()
            logger.info("Drone disconnected")
            
        except Exception as e:
            logger.error(f"Disconnection failed: {e}")
    
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
        """Open camera window."""
        try:
            # Start camera process if not running
            self.start_camera_process()
            
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append("Kamera penceresi açılıyor...")
            
            logger.info("Camera window opened")
            
        except Exception as e:
            logger.error(f"Failed to open camera: {e}")
            if hasattr(self, 'ihaInformer'):
                self.ihaInformer.append(f"Kamera açma hatası: {str(e)}")
    
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
            
            # Update HUD if available
            if self.hud_widget:
                self.hud_widget.updateData(telemetry)
                self.hud_widget.setConnectionState(self.connection_active)
            
            # Update UI labels
            self.update_ui_labels(telemetry)
            
            # Update map
            if self.leaflet_map and telemetry:
                self.leaflet_map.droneCoord(
                    telemetry.get('lat', 0),
                    telemetry.get('lon', 0),
                    telemetry.get('yaw', 0)
                )
                
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
                }
            
            # Fallback to MAVLink
            elif self.mavlink_client:
                telemetry = self.mavlink_client.get_telemetry_data()
                
        except Exception as e:
            logger.error(f"Failed to get telemetry: {e}")
        
        return telemetry
    
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
                    
        except Exception as e:
            logger.error(f"Failed to update UI labels: {e}")
    
    def show_map_error(self, error_msg: str):
        """Show map error message."""
        if hasattr(self, 'label'):
            self.label.setText(f"Harita Hatası: {error_msg}")
            self.label.setStyleSheet("color: red; font-size: 12pt; padding: 20px;")
    
    def on_map_timeout(self):
        """Handle map loading timeout."""
        self.show_map_error("Harita yükleme zaman aşımına uğradı.")
    
    def closeEvent(self, event):
        """Handle application close event."""
        try:
            # Show confirmation dialog
            reply = QMessageBox.question(
                self, 'Çıkış', 'Uygulamayı kapatmak istediğinize emin misiniz?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Cleanup
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

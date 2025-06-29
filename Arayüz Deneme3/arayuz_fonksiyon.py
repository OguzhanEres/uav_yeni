# -*- coding: utf-8 -*-
import sys, serial.tools.list_ports
import serial  # Add serial import for port checking
import os
import collections
import collections.abc
import subprocess  # Add subprocess import
import psutil      # Add psutil import for process management

# Geriye dönük uyumluluk için collections'a MutableMapping ekle
if not hasattr(collections, 'MutableMapping'):
    collections.MutableMapping = collections.abc.MutableMapping

# Düzeltmeden sonra dronekit'i içe aktar
import dronekit
import time, pickle
import threading
import socket
import logging
import urllib.request
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QMessageBox, QInputDialog
from PyQt5.QtCore import QTimer, QDateTime, QUrl, Qt, pyqtSlot
from PyQt5 import QtCore, uic
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebEngineWidgets import QWebEngineSettings, QWebEngineProfile

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('HumaGCS')

from leaflet_map import LeafletMap
from hud_widget import HUDWidget

# MAVLink Client modülünü içe aktar
try:
    from mavlink_client import MAVLinkClient
    logger.info("MAVLink client loaded successfully")
    mavlink_client = MAVLinkClient()
except ImportError:
    logger.error("MAVLink client not found, using simulation")
    mavlink_client = None

# Bağlantı durumunu takip et
uav_connection = False
class HumaGCS(QMainWindow):
    def __init__(self):
        super().__init__()
        # Load UI from huma_gcs.ui file
        uic.loadUi(os.path.join(os.path.dirname(os.path.abspath(__file__)), "huma_gcs.ui"), self)
        self.setWindowTitle("Hüma GCS - İnsansız Hava Aracı Kontrol İstasyonu")
        # Bağlı değilken demo güncellemeleri duracak
        
        # Initialize variables
        self.uav = None
        self.uav2 = None
        self.map_loaded = False
        self.leaflet_map = None
        self.server_thread = None
        self.check_server_thread = None
        self.mavlink_client = mavlink_client
        self.connection_active = False
        self.camera_process = None  # Add camera process tracking
        self.camera_window_process = None  # Add separate camera window process tracking
        
        ports = serial.tools.list_ports.comports()
        
        # Add a default UDP option first
        self.portList.addItem("UDP (127.0.0.1:14550)")
        
        # Add COM ports with detailed information
        for port in ports:
            port_info = f"{port.device}"
            if port.description and port.description != "n/a":
                port_info += f" ({port.description})"
            self.portList.addItem(port_info)
        
        # Log available ports for debugging
        logger.info(f"Available COM ports: {[p.device for p in ports]}")
        
        # If COM8 is available, select it by default (for Pixhawk)
        for i in range(self.portList.count()):
            if "COM8" in self.portList.itemText(i):
                self.portList.setCurrentIndex(i)
                logger.info("COM8 selected by default")
                break
        
        # Map view setup
        self.setupMapView()
        
        # HUD view setup
        self.setupHUDView()
        
        # Connect UI buttons
        self.setupConnections()
        
        # Set up timers
        self.setupTimers()
        
        # Initialize the map in a separate thread
        self.initializeMap()
    
    def setupMapView(self):
        """Set up the map view with QWebEngineView"""
        try:
            # Başlangıçta yükleniyor mesajı göster
            self.label.setText("Harita yükleniyor...\nLütfen bekleyin.")
            self.label.setStyleSheet("color: blue; font-size: 14pt; background-color: #f0f0f0; padding: 20px;")
            
            # Create profile settings for QWebEngineView
            profile = QWebEngineProfile.defaultProfile()
            profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)
            profile.setHttpCacheType(QWebEngineProfile.MemoryHttpCache)
            
            # Create web view for map - huma_gcs.ui'de mapLabel yerine label kullanıyor
            self.map_widget = QWebEngineView(self.label)
            
            # Set web page settings
            settings = self.map_widget.settings()
            settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
            settings.setAttribute(QWebEngineSettings.AllowGeolocationOnInsecureOrigins, True)
            settings.setAttribute(QWebEngineSettings.ShowScrollBars, False)
            settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
            
            # Set size and position - will be updated in resizeEvent
            self.updateMapSize()
            self.map_widget.hide()  # Will be shown when map is loaded
            
            # Timeout timer ekle - harita 30 saniyede yüklenmezse hata göster
            self.map_timeout_timer = QTimer(self)
            self.map_timeout_timer.timeout.connect(self.on_map_timeout)
            self.map_timeout_timer.setSingleShot(True)
            self.map_timeout_timer.start(30000)  # 30 saniye timeout
            
        except Exception as e:
            logger.error(f"Map setup error: {e}")
            self.show_map_error(f"Harita kurulumu hatası: {str(e)}")

    def updateMapSize(self):
        """Update map widget size to match its container"""
        if hasattr(self, 'map_widget') and self.map_widget:
            self.map_widget.resize(self.label.size())
            self.map_widget.setGeometry(0, 0, self.label.width(), self.label.height())

    def setupHUDView(self):
        """HUD (Heads-Up Display) ekranını ayarla"""
        try:
            # HUD widget'ını oluştur ve label_2'yi parent olarak ayarla
            self.hud_widget = HUDWidget(self.label_2)
            
            # HUD widget'ını label_2'nin tam boyutuna ayarla
            self.hud_widget.setGeometry(0, 0, self.label_2.width(), self.label_2.height())
            self.hud_widget.resize(self.label_2.size())
            
            # Widget'ın boyut politikasını ayarla - tamamen genişleyecek şekilde
            from PyQt5.QtWidgets import QSizePolicy
            self.hud_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            
            # HUD'u label_2'nin tam alanını kaplayacak şekilde ayarla
            self.hud_widget.setMinimumSize(self.label_2.size())
            self.hud_widget.setMaximumSize(self.label_2.size())
            
            # Label_2'nin içeriğini temizle ve HUD'u tek child olarak ayarla
            self.label_2.setText("")  # Herhangi bir text içeriğini temizle
            self.label_2.setStyleSheet("border: none; background: transparent;")  # Border'ları kaldır
            
            # Yeniden boyutlandırma olayında HUD'un da yeniden boyutlandırılması için bağlantı kur
            self.label_2.resizeEvent = self.onHUDContainerResize
            
            # HUD'u göster ve en üste getir
            self.hud_widget.show()
            self.hud_widget.raise_()
            
            # HUD'un label_2'yi tamamen kaplaması için ek kontrol
            self.hud_widget.setAutoFillBackground(True)
            
            # Başlangıçta bağlantı durumunu false olarak ayarla
            self.hud_widget.setConnectionState(False)
            
            # Telemetri güncelleme timer'ını başlat - reduced frequency for better performance
            self.telemetryTimer = QTimer(self)
            self.telemetryTimer.timeout.connect(self.updateHUDWithTelemetryData)
            self.telemetryTimer.start(200)  # 200ms aralıklarla güncelle (5 fps) - less CPU intensive
            
            # Initialize map update counter for less frequent map updates
            self._map_update_counter = 0
            
        except Exception as e:
            logger.error(f"HUD setup error: {e}")
            self.label_2.setText(f"HUD yüklenemedi: {str(e)}")
            self.label_2.setStyleSheet("color: red; font-size: 12pt;")
    
    def onHUDContainerResize(self, event):
        """label_2 yeniden boyutlandırıldığında HUD'u da yeniden boyutlandır"""
        if hasattr(self, "hud_widget") and self.hud_widget:
            # HUD'u label_2'nin tam boyutuna ayarla - event'ten yeni boyutu al
            new_size = event.size()
            self.hud_widget.setGeometry(0, 0, new_size.width(), new_size.height())
            self.hud_widget.resize(new_size)
            self.hud_widget.setMinimumSize(new_size)
            self.hud_widget.setMaximumSize(new_size)
            self.hud_widget.raise_()  # HUD'u en üste getir
            
            # HUD widget'ının update edilmesini zorla
            self.hud_widget.update()
            
        # Orijinal resizeEvent fonksiyonunu çağır
        QLabel.resizeEvent(self.label_2, event)

    def updateHUDSize(self):
        """Update HUD widget size to match its container"""
        if hasattr(self, 'hud_widget') and self.hud_widget and hasattr(self, 'label_2'):
            # HUD'u label_2'nin tam boyutuna ayarla
            container_size = self.label_2.size()
            self.hud_widget.setGeometry(0, 0, container_size.width(), container_size.height())
            self.hud_widget.resize(container_size)
            self.hud_widget.setMinimumSize(container_size)
            self.hud_widget.setMaximumSize(container_size)
            self.hud_widget.raise_()  # HUD'u en üste getir
            self.hud_widget.update()  # Güncellemeyi zorla

    def updateHUDWithTelemetryData(self):
        """Update HUD with simplified telemetry data"""
        import random
        import math
        
        # Check if we have an active connection (dronekit or MAVLink)
        real_data_available = False
        telemetry = {}
        
        # Try to get data from dronekit first
        if hasattr(self, 'uav') and self.uav and self.connection_active:
            try:
                telemetry = {
                    "lat": float(self.uav.location.global_relative_frame.lat or 0),
                    "lon": float(self.uav.location.global_relative_frame.lon or 0),
                    "roll": float(self.uav.attitude.roll or 0),
                    "pitch": float(self.uav.attitude.pitch or 0),
                    "yaw": float(self.uav.attitude.yaw or 0),
                    "airspeed": float(self.uav.airspeed or 0),
                    "groundspeed": float(self.uav.groundspeed or 0),
                    "altitude": float(self.uav.location.global_relative_frame.alt or 0),
                    "throttle": float(getattr(self.uav, 'throttle', 0) * 100),
                    "battery_level": float(self.uav.battery.level or 0),
                    "battery_voltage": float(self.uav.battery.voltage or 0),
                    "armed": bool(self.uav.armed),
                    "flight_mode": str(self.uav.mode.name),
                    "gps_fix": int(getattr(self.uav.gps_0, 'fix_type', 0)),
                    "satellites": int(getattr(self.uav.gps_0, 'satellites_visible', 0))
                }
                real_data_available = True
            except Exception as e:
                logger.warning(f"Dronekit telemetry error: {e}")
        
        # Fallback to MAVLink if dronekit not available
        elif self.mavlink_client and self.mavlink_client.is_connected():
            try:
                telemetry = self.mavlink_client.get_telemetry_data()
                telemetry = {
                    "lat": telemetry["lat"],
                    "lon": telemetry["lon"],
                    "roll": telemetry["roll"],
                    "pitch": telemetry["pitch"],
                    "yaw": telemetry["yaw"],
                    "airspeed": telemetry["airspeed"],
                    "groundspeed": telemetry["groundspeed"],
                    "altitude": telemetry["altitude"],
                    "throttle": telemetry["throttle"],
                    "battery_level": telemetry["battery_level"],
                    "battery_voltage": telemetry["battery_voltage"],
                    "armed": telemetry["armed"],
                    "flight_mode": telemetry["flight_mode"],
                    "gps_fix": telemetry["gps_fix"],
                    "satellites": telemetry["satellites"]
                }
                real_data_available = True
            except Exception as e:
                logger.warning(f"MAVLink telemetry error: {e}")
        
        if real_data_available:
            # Process real telemetry data
            data = {
                "lat": round(telemetry["lat"], 6),
                "lon": round(telemetry["lon"], 6),
                "roll": round(math.degrees(telemetry["roll"]) if isinstance(telemetry["roll"], float) else telemetry["roll"], 1),
                "pitch": round(math.degrees(telemetry["pitch"]) if isinstance(telemetry["pitch"], float) else telemetry["pitch"], 1),
                "yaw": round(math.degrees(telemetry["yaw"]) if isinstance(telemetry["yaw"], float) else telemetry["yaw"], 1),
                "airspeed": round(telemetry["airspeed"], 1),
                "groundspeed": round(telemetry["groundspeed"], 1),
                "altitude": round(telemetry["altitude"], 1),
                "throttle": round(telemetry["throttle"], 0),
                "batteryLevel": round(telemetry["battery_level"], 0),
                "batteryVoltage": round(telemetry["battery_voltage"], 1),
                "armed": telemetry["armed"],
                "flightMode": telemetry["flight_mode"],
                "gpsStatus": min(2, telemetry["gps_fix"]),
                "gpsSatellites": telemetry["satellites"]
            }
            
            # Update connection indicator
            self.hud_widget.setConnectionState(True)
            
        else:
            # No fake data when not connected - use static default values
            data = {
                "lat": 0.0,
                "lon": 0.0,
                "roll": 0.0,
                "pitch": 0.0,
                "yaw": 0.0,
                "airspeed": 0.0,
                "groundspeed": 0.0,
                "altitude": 0.0,
                "throttle": 0.0,
                "batteryLevel": 0.0,
                "batteryVoltage": 0.0,
                "armed": False,
                "flightMode": "UNKNOWN",
                "gpsStatus": 0,
                "gpsSatellites": 0
            }
            
            # Update connection indicator
            self.hud_widget.setConnectionState(False)
            
        # Update HUD widget with simplified data
        self.hud_widget.updateData(data)
            
        # Update UI labels with cleaner formatting
        self.enlem.setText(f"Lat: {data['lat']:.4f}°")
        self.boylam.setText(f"Lon: {data['lon']:.4f}°")
        self.roll.setText(f"Roll: {data['roll']:+.1f}°")
        self.pitch.setText(f"Pitch: {data['pitch']:+.1f}°")
        self.yaw.setText(f"Yaw: {data['yaw']:.1f}°")
        self.irtifa.setText(f"Alt: {data['altitude']:.1f}m")
        self.havaHizi.setText(f"AS: {data['airspeed']:.1f}m/s")
        self.yerHizi.setText(f"GS: {data['groundspeed']:.1f}m/s")
        self.mevcutUcusModu.setText(f"Mode: {data['flightMode']}")
        self.armDurum.setText(f"{'ARMED' if data['armed'] else 'DISARMED'}")
        self.isArmable.setText(f"GPS: {data['gpsSatellites']} sats")
        
        # Update map if available (less frequent updates)
        if self.leaflet_map and hasattr(self, '_map_update_counter'):
            self._map_update_counter = getattr(self, '_map_update_counter', 0) + 1
            if self._map_update_counter % 5 == 0:  # Update map every 500ms instead of 100ms
                self.leaflet_map.droneCoord(data['lat'], data['lon'], data['yaw'])
        elif self.leaflet_map:
            self._map_update_counter = 0
            self.leaflet_map.droneCoord(data['lat'], data['lon'], data['yaw'])
    
    def setupConnections(self):
        """Set up button connections and signals"""
        # Connection buttons
        self.baglan.clicked.connect(self.connectDrone)
        self.armDisarm.clicked.connect(self.toggleArmDisarm)
        self.baglantiKapat.clicked.connect(self.BaglantiKapat)
        
        # Flight mode buttons
        self.AUTO.clicked.connect(lambda: self.setFlightMode("AUTO"))
        self.TAKEOFF.clicked.connect(lambda: self.setFlightMode("TAKEOFF"))
        self.GUIDED.clicked.connect(lambda: self.setFlightMode("GUIDED"))
        self.RTL.clicked.connect(lambda: self.setFlightMode("RTL"))
        
        # Operation command buttons
        self.komut_Onay.clicked.connect(self.confirmCommand)
        
        # Server connection buttons
        self.sunucuBaglan.clicked.connect(self.connectToServer)
        self.sunucuAyril.clicked.connect(self.disconnectFromServer)
        self.iletisimBaslat.clicked.connect(self.startCommunication)
        
        # Mission control
        self.gorevBitir.clicked.connect(self.endMission)
        
        # Camera control
        self.kameraAc.clicked.connect(self.openCameraWindow)
    
    def setupTimers(self):
        """Set up timers for updating UI elements"""
        self.clockTimer = QTimer(self)
        self.clockTimer.timeout.connect(self.updateServerTime)
        self.clockTimer.start(1000)  # Update every second
    
    def updateServerTime(self):
        """Update the server time display"""
        current_time = QDateTime.currentDateTime().toString('yyyy-MM-dd hh:mm:ss')
        self.sunucuSaati.setText(f"Sunucu Saati: {current_time}")
    
    def initializeMap(self):
        """Initialize the Leaflet map in a separate thread"""
        if LeafletMap is None:
            self.label.setText("Harita modülü bulunamadı. leaflet_map.py dosyası mevcut olmalıdır.")
            self.label.setStyleSheet("color: red; font-size: 12pt;")
            return

        try:
            # Create LeafletMap instance
            self.leaflet_map = LeafletMap()
            
            # Create a thread for the map server
            self.server_thread = threading.Thread(
                target=self.start_map_server,
                daemon=True
            )
            self.server_thread.start()
            
            # Start a separate thread to check if server is ready and load map
            self.check_server_thread = threading.Thread(
                target=self.check_server_and_load_map,
                daemon=True
            )
            self.check_server_thread.start()
        except Exception as e:
            logger.error(f"Map initialization error: {e}")
            self.label.setText(f"Harita yüklenemedi. Hata: {str(e)}")
            self.label.setStyleSheet("color: red; font-size: 12pt;")
    
    def start_map_server(self):
        """Start the map server in a separate thread"""
        try:
            port = 8150
            # Check if port is already in use
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.bind(('localhost', port))
            except socket.error as e:
                if e.errno == 10048:  # Port already in use
                    logger.warning(f"Port {port} is already in use. Map server may already be running.")
                else:
                    logger.error(f"Socket error: {e}")
            finally:
                s.close()
                
            # Start the map server
            self.leaflet_map.start_map(port_no=port)
        except Exception as e:
            logger.error(f"Map server error: {e}")
            # Update UI on the main thread
            QtCore.QMetaObject.invokeMethod(
                self, 
                "show_map_error", 
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(str, str(e))
            )
    
    def check_server_and_load_map(self):
        """Check if server is ready and load map when ready"""
        # Create a separate thread to check server availability
        thread = threading.Thread(target=self._check_server_thread, daemon=True)
        thread.start()
    
    def _check_server_thread(self):
        """Thread to check server availability"""
        start_time = time.time()
        timeout = 20  # Increase timeout to 20 seconds
        check_interval = 0.5  # seconds
        
        while time.time() - start_time < timeout:
            try:
                # First try with socket connection
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    result = s.connect_ex(('127.0.0.1', 8150))
                    if result == 0:  # Port is open and accepting connections
                        # Additional check - try to fetch content
                        try:
                            with urllib.request.urlopen('http://localhost:8150/', timeout=2) as response:
                                if response.getcode() == 200:
                                    logger.info("Map server is ready, loading map...")
                                    QtCore.QMetaObject.invokeMethod(
                                        self, 
                                        "start_map", 
                                        QtCore.Qt.QueuedConnection
                                    )
                                    return
                        except Exception as fetch_error:
                            logger.debug(f"Server content check failed: {fetch_error}")
            except Exception as e:
                logger.debug(f"Server check error (will retry): {e}")
            
            time.sleep(check_interval)
        
        # If we get here, server didn't start in time
        error_msg = f"Harita sunucusu {timeout} saniye içinde başlatılamadı."
        logger.error(error_msg)
        QtCore.QMetaObject.invokeMethod(
            self, 
            "show_map_error", 
            QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(str, error_msg)
        )
    
    @pyqtSlot()
    def start_map(self):
        """Display the map in the UI (called from main thread)"""
        try:
            # First, clear any existing content
            for child in self.label.children():
                if isinstance(child, (QLabel, QPushButton)):
                    child.deleteLater()
            
            # Create info label
            info_label = QLabel(self.label)
            info_label.setText(f"Harita URL'si: http://localhost:8150/\nYükleniyor...")
            info_label.setStyleSheet("background-color: rgba(255,255,255,180); color: black; padding: 5px;")
            info_label.setAlignment(Qt.AlignTop)
            info_label.setFixedHeight(40)
            info_label.setFixedWidth(self.label.width())
            info_label.show()
            self.info_label = info_label
            
            # Create the web view for the map with proper sizing
            self.updateMapSize()
            self.map_widget.show()
            
            # Explicit load with local URL 
            map_url = "http://localhost:8150/"
            logger.info(f"Loading map from URL: {map_url}")
            self.map_widget.load(QUrl(map_url))
            
            # Connect signals to track loading status
            self.map_widget.loadStarted.connect(self.on_map_load_started)
            self.map_widget.loadFinished.connect(self.on_map_load_finished)
            self.map_widget.loadProgress.connect(self.on_map_load_progress)
        except Exception as e:
            logger.error(f"Map display error: {e}")
            self.show_map_error(str(e))
    
    @pyqtSlot()
    def on_map_load_started(self):
        """Called when map starts loading"""
        logger.info("Map loading started")
        if hasattr(self, 'info_label'):
            self.info_label.setText("Harita yükleniyor... (0%)")
    
    @pyqtSlot(int)
    def on_map_load_progress(self, progress):
        """Called during map loading progress"""
        if hasattr(self, 'info_label'):
            self.info_label.setText(f"Harita yükleniyor... ({progress}%)")
    
    @pyqtSlot(bool)
    def on_map_load_finished(self, success):
        """Handle map loading result"""
        # Timeout timer'ını durdur
        if hasattr(self, 'map_timeout_timer'):
            self.map_timeout_timer.stop()
    
        if success:
            logger.info("Map loaded successfully")
            self.map_loaded = True
            if hasattr(self, 'info_label'):
                self.info_label.setText("Harita başarıyla yüklendi")
                QTimer.singleShot(2000, lambda: self.info_label.hide())
        else:
            logger.error("Failed to load map")
            self.show_map_error("Harita yüklenemedi. İnternet bağlantınızı kontrol edin.")
    
    @pyqtSlot(str)
    def show_map_error(self, error_msg):
        """Display error message in the map area with fallback options"""
        self.label.setText(f"Harita Hatası: {error_msg}\n\n"
                           "Lütfen harita sunucusunun çalıştığından emin olun.\n\n"
                           "Aşağıdaki seçenekleri deneyebilirsiniz:")
        self.label.setStyleSheet("color: red; font-size: 12pt; padding: 20px; background-color: #ffe0e0;")
        
        # Add a retry button with relative positioning
        retry_button = QPushButton("Yeniden Dene", self.label)
        retry_button.setGeometry(20, 150, 120, 30)
        retry_button.clicked.connect(self.retry_load_map)
        retry_button.show()
        
        # Add a button to open in browser with relative positioning
        browser_button = QPushButton("Tarayıcıda Aç", self.label)
        browser_button.setGeometry(150, 150, 120, 30)
        browser_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("http://localhost:8150/")))
        browser_button.show()
    
    def retry_load_map(self):
        """Retry loading the map"""
        self.label.setText("Yeniden bağlanılıyor...")
        self.label.setStyleSheet("color: blue; font-size: 14pt;")
        
        # Clear any buttons or widgets on the map label
        for child in self.label.children():
            if isinstance(child, (QPushButton, QLabel)):
                child.deleteLater()
        
        # Try to reconnect
        QTimer.singleShot(500, lambda: self.check_server_and_load_map())
    
    def connectDrone(self):
        """Connect to the drone using MAVLink or direct dronekit connection"""
        self.ihaInformer.append("İHA'ya bağlanılıyor...")
        
        # Start camera process in background when connecting
        self.startCameraProcess()
        
        # Get connection parameters from UI
        try:
            # Get selected port from portList
            if hasattr(self, 'portList') and self.portList.currentText():
                selected_port = self.portList.currentText().strip()
                
                # Extract COM port from the description if it has one
                if "COM" in selected_port.upper():
                    if "(" in selected_port:
                        # Format: "COM8 (USB Serial Port)"
                        com_port = selected_port.split()[0]  # Get first part (COM8)
                    else:
                        # Format: "COM8"
                        com_port = selected_port
                    
                    port_type = "COM"
                    port = com_port
                    ip_address = ""
                    self.ihaInformer.append(f"COM port seçildi: {com_port}")
                else:
                    # UDP default for non-COM selections
                    port_type = "UDP"
                    ip_address = "127.0.0.1"
                    port = "14550"
                    self.ihaInformer.append("COM port seçilmedi, UDP moduna geçiliyor")
            else:
                # Fallback to UDP if no port selected
                port_type = "UDP"
                ip_address = "127.0.0.1"
                port = "14550"
                self.ihaInformer.append("Port listesi boş, UDP varsayılan ayarları kullanılıyor")
                
        except Exception as e:
            self.ihaInformer.append(f"Port seçimi hatası: {e}")
            # Use default values
            port_type = "UDP"
            ip_address = "127.0.0.1"
            port = "14550"
        
        # Build connection string
        if port_type == "UDP":
            connection_string = f"udp:{ip_address}:{port}"
        elif port_type == "TCP":
            connection_string = f"tcp:{ip_address}:{port}"
        else:  # COM port
            # For COM ports, use the full COM port name with baud rate
            if not port.upper().startswith('COM'):
                connection_string = f"COM{port}"
            else:
                connection_string = port.upper()
            # Add baud rate for serial connection (try Mission Planner's baud rate first)
            connection_string = f"{connection_string},1200"
        
        self.ihaInformer.append(f"Bağlantı dizesi: {connection_string}")
        
        # First try to connect using direct dronekit for COM ports
        if port_type == "COM":
            try:
                self.ihaInformer.append("COM portu ile direkt dronekit bağlantısı deneniyor...")
                
                # Check if COM port exists and is available
                available_ports = [port.device for port in serial.tools.list_ports.comports()]
                com_port = connection_string.split(',')[0]  # Get COM port without baud rate
                
                if com_port not in available_ports:
                    self.ihaInformer.append(f"Hata: {com_port} portu bulunamadı!")
                    self.ihaInformer.append(f"Mevcut portlar: {', '.join(available_ports)}")
                    return
                
                self.ihaInformer.append(f"Port {com_port} bulundu, bağlanılıyor...")
                
                # Check if port is already in use (like Mission Planner)
                try:
                    test_serial = serial.Serial(com_port, 1200, timeout=1)
                    test_serial.close()
                    self.ihaInformer.append(f"Port {com_port} müsait.")
                except serial.SerialException as se:
                    if "already open" in str(se).lower() or "access denied" in str(se).lower():
                        self.ihaInformer.append(f"HATA: {com_port} portu başka bir uygulama tarafından kullanılıyor!")
                        self.ihaInformer.append("Mission Planner veya başka GCS uygulamasını kapatın ve tekrar deneyin.")
                        return
                    else:
                        self.ihaInformer.append(f"Port test hatası: {str(se)}")
                except Exception as e:
                    self.ihaInformer.append(f"Port kontrol hatası: {str(e)}")
                
                # Try different baud rates commonly used with Pixhawk (including Mission Planner's 1200)
                baud_rates = [1200, 57600, 115200, 921600]
                for baud_rate in baud_rates:
                    try:
                        self.ihaInformer.append(f"Baud rate {baud_rate} ile deneniyor...")
                        connection_str = f"{com_port},{baud_rate}"
                        
                        # Direct dronekit connection with timeout
                        self.uav = dronekit.connect(connection_str, wait_ready=True, timeout=15)
                        
                        if self.uav:
                            self.connection_active = True
                            self.ihaInformer.append(f"✓ İHA bağlantısı başarılı! (Baud: {baud_rate})")
                            self.ihaInformer.append(f"✓ Araç tipi: {self.uav.system_status.state}")
                            self.ihaInformer.append(f"✓ Mod: {self.uav.mode.name}")
                            self.ihaInformer.append(f"✓ Armed: {self.uav.armed}")
                            
                            if hasattr(self, 'baglanti'):
                                self.baglanti.setText("Bağlantı: Aktif")
                            
                            # Enable flight control buttons
                            self.enable_flight_controls()
                            return
                            
                    except Exception as e:
                        self.ihaInformer.append(f"✗ Baud rate {baud_rate} başarısız: {str(e)}")
                        if self.uav:
                            try:
                                self.uav.close()
                            except:
                                pass
                            self.uav = None
                        continue
                
                # If all baud rates failed
                self.ihaInformer.append("✗ Tüm baud rate'ler denendi, bağlantı başarısız!")
                self.ihaInformer.append("Kontrol listesi:")
                self.ihaInformer.append("1. Mission Planner'ı kapatın")
                self.ihaInformer.append("2. Pixhawk USB kablosunu çıkarıp takın")
                self.ihaInformer.append("3. COM port numarasını kontrol edin")
                return
                
            except Exception as e:
                self.ihaInformer.append(f"COM port bağlantı hatası: {str(e)}")
                # Fall back to MAVLink client if available
        
        # Try MAVLink client for other connection types or as fallback
        if self.mavlink_client:
            try:
                success = self.mavlink_client.connect(connection_string)
                
                if success:
                    self.connection_active = True
                    self.ihaInformer.append("İHA bağlantısı başarılı! (MAVLink)")
                    if hasattr(self, 'baglanti'):
                        self.baglanti.setText("Bağlantı: Aktif")
                    
                    self.enable_flight_controls()
                else:
                    self.ihaInformer.append("MAVLink bağlantısı başarısız!")
                    if hasattr(self, 'baglanti'):
                        self.baglanti.setText("Bağlantı: Kapalı")
                    
            except Exception as e:
                self.ihaInformer.append(f"MAVLink bağlantı hatası: {str(e)}")
                if hasattr(self, 'baglanti'):
                    self.baglanti.setText("Bağlantı: Hata")
        else:
            self.ihaInformer.append("MAVLink istemcisi mevcut değil!")
    
    def enable_flight_controls(self):
        """Enable flight control buttons after successful connection"""
        if hasattr(self, 'AUTO'):
            self.AUTO.setEnabled(True)
        if hasattr(self, 'GUIDED'):
            self.GUIDED.setEnabled(True)
        if hasattr(self, 'LOITER'):
            self.LOITER.setEnabled(True)
        if hasattr(self, 'RTL'):
            self.RTL.setEnabled(True)
        if hasattr(self, 'armDisarm'):
            self.armDisarm.setEnabled(True)
        if hasattr(self, 'TAKEOFF'):
            self.TAKEOFF.setEnabled(True)
    
    def BaglantiKapat(self):
        """Disconnect from the drone"""
        try:
            # Close dronekit connection if exists
            if hasattr(self, 'uav') and self.uav:
                self.uav.close()
                self.uav = None
                self.ihaInformer.append("Dronekit bağlantısı kapatıldı.")
            
            # Close MAVLink connection if exists
            if self.mavlink_client:
                self.mavlink_client.disconnect()
                self.ihaInformer.append("MAVLink bağlantısı kapatıldı.")
            
            # Close background camera process when disconnecting
            self.stopCameraProcess()
            
            self.connection_active = False
            self.ihaInformer.append("İHA bağlantısı kesildi.")
            
            if hasattr(self, 'baglanti'):
                self.baglanti.setText("Bağlantı: Kapalı")
            
            # Disable flight control buttons
            self.disable_flight_controls()
            
        except Exception as e:
            self.ihaInformer.append(f"Bağlantı kapatma hatası: {str(e)}")
    
    def disable_flight_controls(self):
        """Disable flight control buttons when disconnected"""
        if hasattr(self, 'AUTO'):
            self.AUTO.setEnabled(False)
        if hasattr(self, 'GUIDED'):
            self.GUIDED.setEnabled(False)
        if hasattr(self, 'LOITER'):
            self.LOITER.setEnabled(False)
        if hasattr(self, 'RTL'):
            self.RTL.setEnabled(False)
        if hasattr(self, 'armDisarm'):
            self.armDisarm.setEnabled(False)
        if hasattr(self, 'TAKEOFF'):
            self.TAKEOFF.setEnabled(False)
    
    def setFlightMode(self, mode):
        """Set the flight mode using dronekit or MAVLink"""
        if not self.connection_active:
            self.ihaInformer.append("İHA bağlı değil!")
            return
        
        try:
            # Try dronekit first
            if hasattr(self, 'uav') and self.uav:
                # Import VehicleMode for dronekit
                from dronekit import VehicleMode
                
                self.uav.mode = VehicleMode(mode)
                self.ihaInformer.append(f"Uçuş modu {mode} olarak ayarlanıyor... (Dronekit)")
                return
            
            # Fallback to MAVLink
            elif self.mavlink_client:
                success = self.mavlink_client.set_mode(mode)
                if success:
                    self.ihaInformer.append(f"Uçuş modu {mode} olarak ayarlanıyor... (MAVLink)")
                else:
                    self.ihaInformer.append(f"Uçuş modu değiştirilemedi: {mode}")
            else:
                self.ihaInformer.append("Bağlantı mevcut değil!")
                
        except Exception as e:
            self.ihaInformer.append(f"Uçuş modu değiştirme hatası: {str(e)}")
    
    def toggleArmDisarm(self):
        """Toggle arm/disarm using dronekit or MAVLink"""
        if not self.connection_active:
            self.ihaInformer.append("İHA bağlı değil!")
            return
        
        try:
            # Try dronekit first
            if hasattr(self, 'uav') and self.uav:
                current_armed = self.uav.armed
                
                if current_armed:
                    # Disarm
                    self.uav.armed = False
                    self.ihaInformer.append("İHA disarm komutu gönderildi.")
                else:
                    # Arm - check if armable first
                    if self.uav.is_armable:
                        self.uav.armed = True
                        self.ihaInformer.append("İHA arm komutu gönderildi.")
                    else:
                        self.ihaInformer.append("İHA arm edilemiyor! Gerekli şartlar sağlanmadı.")
                return
            
            # Fallback to MAVLink
            elif self.mavlink_client:
                # Get current arm status from telemetry
                telemetry = self.mavlink_client.get_telemetry_data()
                current_armed = telemetry.get("armed", False)
                
                # Toggle arm state
                success = self.mavlink_client.arm_disarm(not current_armed)
                
                if success:
                    action = "disarm" if current_armed else "arm"
                    self.ihaInformer.append(f"İHA {action} komutu gönderildi.")
                else:
                    self.ihaInformer.append("Arm/Disarm komutu gönderilemedi.")
            else:
                self.ihaInformer.append("Bağlantı mevcut değil!")
                
        except Exception as e:
            self.ihaInformer.append(f"Arm/Disarm hatası: {str(e)}")

    def confirmCommand(self, event):
        """Confirm and send the selected command"""
        if not hasattr(self, 'komut_Secim'):
            self.ihaInformer.append("Komut seçim menüsü bulunamadı!")
            return
        
        command = self.komut_Secim.currentText()
        if command == "Otonom Kalkış":
            altitude_value, ok = QInputDialog.getInt(None, "İrtifa Girin", "Hedef İrtifa:")
            if ok and self.mavlink_client and self.connection_active:
                # Add takeoff functionality to MAVLink client
                from pymavlink.dialects.v20 import common as mavlink
                success = self.mavlink_client.send_command_long(
                    mavlink.MAV_CMD_NAV_TAKEOFF,
                    0, 0, 0, 0, 0, 0, altitude_value
                )
                if success:
                    self.ihaInformer.append(f"Kalkış komutu gönderildi - Hedef İrtifa: {altitude_value}m")
                else:
                    self.ihaInformer.append("Kalkış komutu gönderilemedi!")
        
        self.ihaInformer.append(f"{command} komutu gönderiliyor...")
        if hasattr(self, 'mevcutOperasyon'):
            self.mevcutOperasyon.setText(f"Mevcut Operasyon: {command}")
    
    def connectToServer(self):
        """Connect to the server"""
        username = self.kadi.text() or "admin"
        password = self.sifre.text() or "••••••"
        self.ihaInformer.append(f"Sunucuya bağlanılıyor, Kullanıcı: {username}")
        self.ihaInformer.append("Sunucu bağlantısı başarılı!")
    
    def disconnectFromServer(self):
        """Disconnect from the server"""
        self.ihaInformer.append("Sunucu bağlantısı kesildi.")
    
    def startCommunication(self):
        """Start communication with the server"""
        self.ihaInformer.append("Sunucu ile iletişim başlatıldı.")
    
    def endMission(self):
        """End the current mission"""
        self.ihaInformer.append("Görev sonlandırılıyor...")
        self.ihaInformer.append("Görev sonlandırıldı.")
        self.mevcutOperasyon.setText("Mevcut Operasyon: Yok")
    
    def startCameraProcess(self):
        """Start camera process in background when connecting to drone (no display window)"""
        try:
            # Define the path to main.py in Temiz folder
            main_py_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Temiz", "HUMA_UAV", "main.py")
            
            # Check if main.py exists
            if not os.path.exists(main_py_path):
                self.ihaInformer.append(f"Hata: {main_py_path} dosyası bulunamadı!")
                logger.error(f"Camera main.py not found at: {main_py_path}")
                return
            
            # Check if camera is already running
            if self.camera_process and self.camera_process.poll() is None:
                self.ihaInformer.append("Kamera süreci zaten çalışıyor!")
                logger.info("Camera process is already running")
                return
            
            # Change to the HUMA_UAV directory
            huma_uav_dir = os.path.dirname(main_py_path)
            
            self.ihaInformer.append("Kamera süreci arka planda başlatılıyor...")
            logger.info(f"Starting background camera from: {main_py_path}")
            
            # Start the camera process in background (no display window, no console window)
            try:
                # Use subprocess.Popen to run main.py in background with no display
                self.camera_process = subprocess.Popen(
                    [sys.executable, "main.py", "--no-display"],  # Add no-display flag
                    cwd=huma_uav_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0  # No console window
                )
                
                self.ihaInformer.append("✓ Kamera süreci arka planda başlatıldı! (Görüntü henüz gösterilmiyor)")
                logger.info(f"Background camera process started with PID: {self.camera_process.pid}")
                
                # Start a timer to check if camera process is still running
                self.camera_check_timer = QTimer(self)
                self.camera_check_timer.timeout.connect(self.checkCameraProcess)
                self.camera_check_timer.start(2000)  # Check every 2 seconds
                
            except FileNotFoundError:
                self.ihaInformer.append("Hata: Python yorumlayıcısı bulunamadı!")
                logger.error("Python interpreter not found")
            except Exception as e:
                self.ihaInformer.append(f"Kamera başlatma hatası: {str(e)}")
                logger.error(f"Camera startup error: {e}")
                
        except Exception as e:
            self.ihaInformer.append(f"Kamera açma hatası: {str(e)}")
            logger.error(f"Camera open error: {e}")
    
    def openCameraWindow(self):
        """Open camera display window to show video stream from running camera process"""
        try:
            # Check if main camera process is running
            if not self.camera_process or self.camera_process.poll() is not None:
                self.ihaInformer.append("Kamera süreci çalışmıyor! Önce İHA'ya bağlanın.")
                return
            
            # Check if camera window is already open
            if self.camera_window_process and self.camera_window_process.poll() is None:
                self.ihaInformer.append("Kamera penceresi zaten açık!")
                return
            
            # Define the path to main.py in Temiz folder for display window
            main_py_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Temiz", "HUMA_UAV", "main.py")
            huma_uav_dir = os.path.dirname(main_py_path)
            
            self.ihaInformer.append("Kamera görüntüsü açılıyor...")
            logger.info("Opening camera display window")
            
            try:
                # Start a separate camera display window process
                self.camera_window_process = subprocess.Popen(
                    [sys.executable, "main.py", "--display-only"],  # Add display-only flag
                    cwd=huma_uav_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
                )
                
                self.ihaInformer.append("✓ Kamera görüntüsü açıldı!")
                logger.info(f"Camera display window process started with PID: {self.camera_window_process.pid}")
                
                # Update button text to indicate camera window is open
                self.kameraAc.setText("Kamera Kapat")
                self.kameraAc.clicked.disconnect()  # Disconnect old connection
                self.kameraAc.clicked.connect(self.closeCameraWindow)  # Connect to close function
                
                # Start a timer to check if camera window process is still running
                self.camera_window_check_timer = QTimer(self)
                self.camera_window_check_timer.timeout.connect(self.checkCameraWindowProcess)
                self.camera_window_check_timer.start(2000)  # Check every 2 seconds
                
            except Exception as e:
                self.ihaInformer.append(f"Kamera görüntüsü açma hatası: {str(e)}")
                logger.error(f"Camera display window startup error: {e}")
                
        except Exception as e:
            self.ihaInformer.append(f"Kamera görüntüsü hatası: {str(e)}")
            logger.error(f"Camera display window error: {e}")
    
    def closeCameraWindow(self):
        """Close the camera display window (but keep background camera process running)"""
        try:
            if self.camera_window_process and self.camera_window_process.poll() is None:
                # Terminate the camera display window process
                self.camera_window_process.terminate()
                
                # Wait for process to terminate (with timeout)
                try:
                    self.camera_window_process.wait(timeout=5)
                    self.ihaInformer.append("✓ Kamera görüntüsü kapatıldı. (Arka plan süreci devam ediyor)")
                    logger.info("Camera display window process terminated successfully")
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't terminate gracefully
                    self.camera_window_process.kill()
                    self.ihaInformer.append("✓ Kamera görüntüsü zorla kapatıldı. (Arka plan süreci devam ediyor)")
                    logger.warning("Camera display window process was force-killed")
                
                self.camera_window_process = None
            else:
                self.ihaInformer.append("Kamera görüntüsü zaten kapalı.")
            
            # Reset button
            self.resetCameraButton()
            
            # Stop the check timer for window
            if hasattr(self, 'camera_window_check_timer'):
                self.camera_window_check_timer.stop()
                
        except Exception as e:
            self.ihaInformer.append(f"Kamera görüntüsü kapatma hatası: {str(e)}")
            logger.error(f"Camera display window close error: {e}")
    
    def checkCameraProcess(self):
        """Check if background camera process is still running"""
        try:
            if self.camera_process:
                if self.camera_process.poll() is not None:
                    # Process has ended
                    self.ihaInformer.append("Kamera süreci sonlandı.")
                    self.camera_process = None
                    
                    # Stop the check timer
                    if hasattr(self, 'camera_check_timer'):
                        self.camera_check_timer.stop()
        except Exception as e:
            logger.error(f"Camera process check error: {e}")
    
    def checkCameraWindowProcess(self):
        """Check if camera display window process is still running"""
        try:
            if self.camera_window_process:
                if self.camera_window_process.poll() is not None:
                    # Process has ended
                    self.ihaInformer.append("Kamera görüntüsü penceresi kapatıldı.")
                    self.camera_window_process = None
                    self.resetCameraButton()
                    
                    # Stop the check timer
                    if hasattr(self, 'camera_window_check_timer'):
                        self.camera_window_check_timer.stop()
        except Exception as e:
            logger.error(f"Camera display window process check error: {e}")
    
    def resetCameraButton(self):
        """Reset camera button to its original state"""
        try:
            self.kameraAc.setText("Kamera Aç")
            self.kameraAc.clicked.disconnect()  # Disconnect any existing connections
            self.kameraAc.clicked.connect(self.openCameraWindow)  # Reconnect to open function
        except Exception as e:
            logger.error(f"Camera button reset error: {e}")
    
    def stopCameraProcess(self):
        """Stop the background camera process and any display window"""
        try:
            # Close camera display window first if it's open
            if self.camera_window_process and self.camera_window_process.poll() is None:
                self.closeCameraWindow()
            
            # Close background camera process
            if self.camera_process and self.camera_process.poll() is None:
                # Terminate the camera process
                self.camera_process.terminate()
                
                # Wait for process to terminate (with timeout)
                try:
                    self.camera_process.wait(timeout=5)
                    self.ihaInformer.append("✓ Kamera süreci kapatıldı.")
                    logger.info("Camera process terminated successfully")
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't terminate gracefully
                    self.camera_process.kill()
                    self.ihaInformer.append("✓ Kamera süreci zorla kapatıldı.")
                    logger.warning("Camera process was force-killed")
                
                self.camera_process = None
            
            # Stop the check timer
            if hasattr(self, 'camera_check_timer'):
                self.camera_check_timer.stop()
                
            # Reset camera button to original state
            self.resetCameraButton()
                
        except Exception as e:
            self.ihaInformer.append(f"Kamera kapatma hatası: {str(e)}")
            logger.error(f"Camera close error: {e}")
    
    def closeEvent(self, event):
        """Handle application close event"""
        close = QMessageBox()
        close.setText("Kapatmak istediğine emin misin?")
        close.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        close = close.exec()

        if close == QMessageBox.Yes:
            # Close all camera processes if running
            try:
                if hasattr(self, 'camera_window_process') and self.camera_window_process and self.camera_window_process.poll() is None:
                    self.camera_window_process.terminate()
                    try:
                        self.camera_window_process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        self.camera_window_process.kill()
                    self.ihaInformer.append("Kamera penceresi kapatıldı.")
                
                if hasattr(self, 'camera_process') and self.camera_process and self.camera_process.poll() is None:
                    self.camera_process.terminate()
                    try:
                        self.camera_process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        self.camera_process.kill()
                    self.ihaInformer.append("Kamera süreci kapatıldı.")
            except Exception as e:
                logger.error(f"Error closing camera processes on exit: {e}")
            
            event.accept()
            self.label.clear()
            self.label_2.clear()
        else:
            event.ignore()
        
    def on_map_timeout(self):
        """Harita yüklenme timeout durumunda çağırılır"""
        if not self.map_loaded:
            self.show_map_error("Harita yüklenme zaman aşımına uğradı. İnternet bağlantınızı kontrol edin.")
        
# Run the application
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HumaGCS()
    window.show()
    sys.exit(app.exec_())

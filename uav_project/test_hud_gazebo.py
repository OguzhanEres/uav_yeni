#!/usr/bin/env python3
"""
HUD Widget Test Script
Bu script HUD widget'ın telemetri güncellemelerini test eder.
"""

import sys
import time
import math
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont

from src.uav_system.ui.desktop.hud_widget import HUDWidget


class HUDTestWindow(QMainWindow):
    """Test window for HUD widget."""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.setup_test_data()
        self.start_simulation()
        
    def init_ui(self):
        """Initialize the UI."""
        self.setWindowTitle("HUD Widget Test - Gazebo Simülasyon Testi")
        self.setGeometry(100, 100, 1000, 700)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create layout
        layout = QVBoxLayout(central_widget)
        
        # Add title
        title = QLabel("HUD Widget Test - Gazebo Simülasyon Verisi")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setStyleSheet("color: white; background-color: #2c3e50; padding: 10px; margin: 5px;")
        layout.addWidget(title)
        
        # Create HUD widget
        self.hud_widget = HUDWidget()
        self.hud_widget.setMinimumSize(800, 500)
        layout.addWidget(self.hud_widget)
        
        # Add control buttons
        button_layout = QVBoxLayout()
        
        self.connect_btn = QPushButton("Simülasyonu Başlat")
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
        """)
        button_layout.addWidget(self.connect_btn)
        
        self.status_label = QLabel("Durum: Simülasyon bekleniyor")
        self.status_label.setStyleSheet("color: #e74c3c; font-size: 12px; padding: 5px;")
        button_layout.addWidget(self.status_label)
        
        layout.addLayout(button_layout)
        
        # Set dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2c3e50;
            }
            QWidget {
                background-color: #2c3e50;
                color: white;
            }
        """)
        
    def setup_test_data(self):
        """Setup test telemetry data."""
        self.connected = False
        self.simulation_time = 0
        self.test_timer = QTimer()
        self.test_timer.timeout.connect(self.update_simulation)
        
    def start_simulation(self):
        """Start the simulation timer."""
        # Initially disconnected
        self.hud_widget.setConnectionState(False)
        
    def toggle_connection(self):
        """Toggle connection state."""
        if not self.connected:
            self.connected = True
            self.connect_btn.setText("Simülasyonu Durdur")
            self.connect_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 10px;
                    border: none;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
            """)
            self.status_label.setText("Durum: Gazebo simülasyonu aktif - Telemetri alınıyor")
            self.status_label.setStyleSheet("color: #27ae60; font-size: 12px; padding: 5px;")
            
            # Start telemetry simulation
            self.hud_widget.setConnectionState(True)
            self.test_timer.start(50)  # 20 Hz update rate
        else:
            self.connected = False
            self.connect_btn.setText("Simülasyonu Başlat")
            self.connect_btn.setStyleSheet("""
                QPushButton {
                    background-color: #27ae60;
                    color: white;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 10px;
                    border: none;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #2ecc71;
                }
            """)
            self.status_label.setText("Durum: Simülasyon durduruldu")
            self.status_label.setStyleSheet("color: #e74c3c; font-size: 12px; padding: 5px;")
            
            # Stop telemetry simulation
            self.test_timer.stop()
            self.hud_widget.setConnectionState(False)
    
    def update_simulation(self):
        """Update simulated telemetry data."""
        self.simulation_time += 0.05  # 50ms increment
        
        # Generate realistic flight telemetry data
        # Simulate a circular flight pattern
        radius = 100  # meters
        angular_velocity = 0.1  # rad/s
        angle = self.simulation_time * angular_velocity
        
        # Base position (Ankara coordinates)
        base_lat = 39.9334
        base_lon = 32.8597
        
        # Calculate position (simple circular pattern)
        lat_offset = (radius * math.cos(angle)) / 111320  # Approximate meters to degrees
        lon_offset = (radius * math.sin(angle)) / (111320 * math.cos(math.radians(base_lat)))
        
        # Simulate varying altitude
        base_altitude = 100
        altitude_variation = 20 * math.sin(self.simulation_time * 0.3)
        
        # Simulate attitude (banking turn)
        bank_angle = 15 * math.sin(angle) 
        pitch_angle = 5 * math.sin(self.simulation_time * 0.2)
        yaw_angle = math.degrees(angle) % 360
        
        # Simulate speeds
        base_airspeed = 25  # m/s
        airspeed_variation = 5 * math.sin(self.simulation_time * 0.15)
        groundspeed = base_airspeed + airspeed_variation - 2  # Account for wind
        
        # Battery simulation (slowly decreasing)
        battery_level = max(20, 100 - (self.simulation_time * 0.5))
        battery_voltage = 12.6 - (100 - battery_level) * 0.02
        
        # GPS simulation
        gps_status = 3 if self.simulation_time > 5 else 2  # Good fix after 5 seconds
        satellites = min(12, int(8 + self.simulation_time * 0.1))
        
        # Flight mode simulation
        flight_modes = ["AUTO", "GUIDED", "LOITER", "RTL"]
        mode_index = int(self.simulation_time / 30) % len(flight_modes)
        
        # Create telemetry data
        telemetry_data = {
            "lat": base_lat + lat_offset,
            "lon": base_lon + lon_offset,
            "altitude": base_altitude + altitude_variation,
            "roll": bank_angle,
            "pitch": pitch_angle,
            "yaw": yaw_angle,
            "heading": yaw_angle,
            "airspeed": base_airspeed + airspeed_variation,
            "groundspeed": groundspeed,
            "armed": True,
            "armable": True,
            "flightMode": flight_modes[mode_index],
            "batteryLevel": battery_level,
            "batteryVoltage": battery_voltage,
            "batteryCurrent": 5.5 + 2 * math.sin(self.simulation_time * 0.5),
            "gpsStatus": gps_status,
            "gpsSatellites": satellites,
            "throttle": 65 + 15 * math.sin(self.simulation_time * 0.3),
            "waypointDist": abs(50 + 30 * math.cos(self.simulation_time * 0.2)),
            "targetBearing": (yaw_angle + 45) % 360
        }
        
        # Update HUD with new data
        self.hud_widget.updateData(telemetry_data)
        
        # Update status with some key metrics
        self.status_label.setText(
            f"Durum: Alt={telemetry_data['altitude']:.1f}m, "
            f"Speed={telemetry_data['groundspeed']:.1f}m/s, "
            f"Mode={telemetry_data['flightMode']}, "
            f"Bat={telemetry_data['batteryLevel']:.1f}%"
        )


def main():
    """Main function to run the test."""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("HUD Widget Test")
    app.setApplicationVersion("1.0")
    
    # Create and show test window
    window = HUDTestWindow()
    window.show()
    
    print("HUD Widget Test Started")
    print("Bu test HUD widget'ın Gazebo simülasyonu ile çalışıp çalışmadığını kontrol eder.")
    print("'Simülasyonu Başlat' butonuna tıklayarak test edin.")
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

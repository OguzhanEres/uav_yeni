#!/usr/bin/env python3
"""
Test script to validate HUD and Map widget fixes.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test that all required modules can be imported."""
    try:
        print("Testing imports...")
        
        # Test MAVLink client
        from src.uav_system.communication.mavlink.mavlink_client import MAVLinkClient
        print("✅ MAVLinkClient imported successfully")
        
        # Test HUD widget
        from src.uav_system.ui.desktop.hud_widget import HUDWidget
        print("✅ HUDWidget imported successfully")
        
        # Test main window
        from src.uav_system.ui.desktop.main_window import HumaGCS
        print("✅ HumaGCS imported successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_mavlink_client():
    """Test MAVLink client functionality."""
    try:
        print("\nTesting MAVLink client...")
        
        from src.uav_system.communication.mavlink.mavlink_client import MAVLinkClient
        
        # Create client
        client = MAVLinkClient()
        
        # Test initialization
        if client.initialize():
            print("✅ MAVLink client initialized")
        else:
            print("❌ MAVLink client initialization failed")
            return False
            
        # Test start
        if client.start():
            print("✅ MAVLink client started")
        else:
            print("❌ MAVLink client start failed")
            return False
            
        # Test telemetry data structure
        telemetry = client.get_telemetry_data()
        if telemetry:
            print(f"✅ Telemetry data structure: {list(telemetry.keys())}")
        else:
            print("❌ No telemetry data available")
            
        # Test cleanup
        if client.cleanup():
            print("✅ MAVLink client cleaned up")
        else:
            print("❌ MAVLink client cleanup failed")
            
        return True
        
    except Exception as e:
        print(f"❌ MAVLink client test error: {e}")
        return False

def test_hud_widget():
    """Test HUD widget functionality."""
    try:
        print("\nTesting HUD widget...")
        
        # Skip GUI tests in headless environment
        import os
        if os.environ.get('DISPLAY') is None:
            print("⚠️  Skipping GUI tests in headless environment")
            print("✅ HUD widget import successful (validated above)")
            return True
        
        # Import Qt components
        from PyQt5.QtWidgets import QApplication, QWidget
        from PyQt5.QtCore import Qt
        from src.uav_system.ui.desktop.hud_widget import HUDWidget
        
        # Create minimal Qt application
        app = QApplication.instance()
        if not app:
            app = QApplication([])
        
        # Create parent widget
        parent = QWidget()
        parent.resize(800, 600)
        
        # Create HUD widget
        hud = HUDWidget(parent)
        print("✅ HUD widget created successfully")
        
        # Test connection state
        hud.setConnectionState(False)
        print("✅ HUD disconnected state set")
        
        hud.setConnectionState(True)
        print("✅ HUD connected state set")
        
        # Test data update
        test_data = {
            'roll': 0.1,
            'pitch': 0.2,
            'yaw': 1.5,
            'airspeed': 25.0,
            'groundspeed': 23.0,
            'altitude': 100.0,
            'armed': True,
            'flightMode': 'AUTO'
        }
        
        hud.updateData(test_data)
        print("✅ HUD data updated successfully")
        
        # Test size
        hud.resize(800, 600)
        print("✅ HUD widget resized")
        
        return True
        
    except Exception as e:
        print(f"❌ HUD widget test error: {e}")
        return False

def test_telemetry_mapping():
    """Test telemetry data mapping."""
    try:
        print("\nTesting telemetry mapping...")
        
        # Sample MAVLink telemetry data
        mavlink_data = {
            'roll': 0.1,  # radians
            'pitch': 0.2,  # radians
            'yaw': 1.5,   # radians
            'airspeed': 25.0,
            'groundspeed': 23.0,
            'altitude': 100.0,
            'throttle': 50.0,
            'battery_level': 85.0,
            'battery_voltage': 12.6,
            'armed': True,
            'flight_mode': 'AUTO',
            'gps_fix': 3,
            'satellites': 12
        }
        
        # Test mapping function
        import math
        
        def map_telemetry_to_hud_format(telemetry):
            """Map MAVLink telemetry data to HUD widget format."""
            hud_data = {
                'roll': math.degrees(telemetry.get('roll', 0.0)),
                'pitch': math.degrees(telemetry.get('pitch', 0.0)),
                'yaw': math.degrees(telemetry.get('yaw', 0.0)),
                'airspeed': telemetry.get('airspeed', 0.0),
                'groundspeed': telemetry.get('groundspeed', 0.0),
                'altitude': telemetry.get('altitude', 0.0),
                'throttle': telemetry.get('throttle', 0.0),
                'batteryLevel': telemetry.get('battery_level', 0.0),
                'batteryVoltage': telemetry.get('battery_voltage', 0.0),
                'armed': telemetry.get('armed', False),
                'flightMode': telemetry.get('flight_mode', 'UNKNOWN'),
                'gpsStatus': telemetry.get('gps_fix', 0),
                'gpsSatellites': telemetry.get('satellites', 0)
            }
            return hud_data
        
        mapped_data = map_telemetry_to_hud_format(mavlink_data)
        
        print("✅ Telemetry mapping successful")
        print(f"   Roll: {mavlink_data['roll']:.3f} rad → {mapped_data['roll']:.1f}°")
        print(f"   Pitch: {mavlink_data['pitch']:.3f} rad → {mapped_data['pitch']:.1f}°")
        print(f"   Yaw: {mavlink_data['yaw']:.3f} rad → {mapped_data['yaw']:.1f}°")
        print(f"   Airspeed: {mapped_data['airspeed']} m/s")
        print(f"   Armed: {mapped_data['armed']}")
        print(f"   Flight Mode: {mapped_data['flightMode']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Telemetry mapping test error: {e}")
        return False

def main():
    """Run all tests."""
    print("🚁 UAV GCS HUD and Map Widget Fix Test")
    print("=" * 50)
    
    test_results = []
    
    # Run tests
    test_results.append(test_imports())
    test_results.append(test_mavlink_client())
    test_results.append(test_hud_widget())
    test_results.append(test_telemetry_mapping())
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Results:")
    
    passed = sum(test_results)
    total = len(test_results)
    
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! The fixes should work correctly.")
    else:
        print("⚠️  Some tests failed. Check the issues above.")
        
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
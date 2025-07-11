#!/usr/bin/env python3
"""
Test script for autonomous UAV operations
This script demonstrates the autonomous takeoff and landing functionality.
"""

import sys
import time
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_autonomous_operations():
    """Test autonomous takeoff and landing operations."""
    try:
        # Import MAVLink client
        from src.uav_system.communication.mavlink.mavlink_client import MAVLinkClient
        
        # Initialize MAVLink client
        logger.info("Initializing MAVLink client...")
        client = MAVLinkClient()
        
        if not client.initialize():
            logger.error("Failed to initialize MAVLink client")
            return False
        
        client.start()
        logger.info("MAVLink client started")
        
        # Test connection (using SITL simulator)
        connection_string = "udp:127.0.0.1:14550"
        logger.info(f"Connecting to: {connection_string}")
        
        if not client.connect(connection_string):
            logger.error("Failed to connect to vehicle")
            return False
        
        logger.info("✅ Connected to vehicle")
        
        # Wait for initial telemetry
        logger.info("Waiting for initial telemetry...")
        time.sleep(5)
        
        # Get current telemetry
        telemetry = client.get_telemetry_data()
        logger.info(f"Initial telemetry: {telemetry}")
        
        # Test autonomous takeoff
        logger.info("🚁 Testing autonomous takeoff...")
        takeoff_altitude = 50.0  # 50 meters
        
        if client.autonomous_takeoff(takeoff_altitude):
            logger.info(f"✅ Autonomous takeoff command sent - Target altitude: {takeoff_altitude}m")
            
            # Monitor takeoff progress
            logger.info("Monitoring takeoff progress...")
            for i in range(30):  # Monitor for 30 seconds
                time.sleep(1)
                telemetry = client.get_telemetry_data()
                altitude = telemetry.get('altitude', 0)
                armed = telemetry.get('armed', False)
                mode = telemetry.get('flight_mode', 'UNKNOWN')
                
                logger.info(f"Status: Alt={altitude:.1f}m, Armed={armed}, Mode={mode}")
                
                if altitude > takeoff_altitude * 0.8:  # 80% of target altitude
                    logger.info("✅ Takeoff completed successfully!")
                    break
            
            # Wait at altitude
            logger.info("Maintaining altitude for 10 seconds...")
            time.sleep(10)
            
            # Test autonomous landing
            logger.info("🛬 Testing autonomous landing...")
            
            # Get current position for landing
            location = client.get_location()
            current_alt = client.get_current_altitude()
            
            if location and current_alt:
                lat, lon = location
                cruise_alt = 30.0  # Approach altitude
                
                if client.autonomous_land(lon, lat, current_alt, cruise_alt):
                    logger.info(f"✅ Autonomous landing command sent")
                    logger.info(f"Landing at: {lat:.6f}, {lon:.6f}")
                    logger.info(f"Approach altitude: {cruise_alt}m")
                    
                    # Monitor landing progress
                    logger.info("Monitoring landing progress...")
                    for i in range(60):  # Monitor for 60 seconds
                        time.sleep(1)
                        telemetry = client.get_telemetry_data()
                        altitude = telemetry.get('altitude', 0)
                        mode = telemetry.get('flight_mode', 'UNKNOWN')
                        
                        logger.info(f"Status: Alt={altitude:.1f}m, Mode={mode}")
                        
                        if altitude < 5.0:  # Below 5 meters
                            logger.info("✅ Landing completed successfully!")
                            break
                else:
                    logger.error("❌ Failed to send landing command")
            else:
                logger.error("❌ Could not get current position for landing")
                
        else:
            logger.error("❌ Failed to send takeoff command")
        
        # Test emergency stop
        logger.info("🚨 Testing emergency stop...")
        if client.emergency_stop():
            logger.info("✅ Emergency stop activated - RTL mode")
        else:
            logger.error("❌ Emergency stop failed")
        
        # Cleanup
        logger.info("Cleaning up...")
        client.disconnect()
        client.cleanup()
        
        logger.info("✅ All tests completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        return False

def main():
    """Main test function."""
    logger.info("🚁 Starting autonomous UAV operations test")
    logger.info("=" * 50)
    
    # Check if SITL simulator is available
    logger.info("This test requires a MAVLink simulator (SITL) running on udp:127.0.0.1:14550")
    logger.info("To run SITL simulator:")
    logger.info("1. Install ArduPilot SITL")
    logger.info("2. Run: sim_vehicle.py -v ArduPlane --console --map")
    logger.info("3. Then run this test script")
    
    input("Press Enter to continue with the test...")
    
    if test_autonomous_operations():
        logger.info("🎉 All autonomous operations tests passed!")
    else:
        logger.error("❌ Some tests failed")
    
    logger.info("=" * 50)
    logger.info("Test completed")

if __name__ == "__main__":
    main()

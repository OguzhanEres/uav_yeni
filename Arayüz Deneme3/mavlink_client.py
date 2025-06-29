import socket
import threading
import time
import logging
from pymavlink import mavutil
from pymavlink.dialects.v20 import common as mavlink

logger = logging.getLogger('MAVLinkClient')

class MAVLinkClient:
    def __init__(self):
        self.connection = None
        self.connected = False
        self.telemetry_data = {}
        self.telemetry_thread = None
        self.running = False
        
        # Initialize telemetry data structure
        self.reset_telemetry_data()
    
    def reset_telemetry_data(self):
        """Reset telemetry data to default values"""
        self.telemetry_data = {
            "lat": 0.0,
            "lon": 0.0,
            "altitude": 0.0,
            "roll": 0.0,
            "pitch": 0.0,
            "yaw": 0.0,
            "airspeed": 0.0,
            "groundspeed": 0.0,
            "heading": 0.0,
            "throttle": 0.0,
            "battery_level": 0.0,
            "battery_voltage": 0.0,
            "armed": False,
            "armable": False,
            "flight_mode": "UNKNOWN",
            "gps_fix": 0,
            "satellites": 0,
            "last_heartbeat": 0
        }
    
    def connect(self, connection_string="udp:127.0.0.1:14550"):
        """Connect to MAVLink stream"""
        try:
            logger.info(f"Attempting to connect to {connection_string}")
            
            # Create MAVLink connection
            self.connection = mavutil.mavlink_connection(connection_string)
            
            # Wait for heartbeat to confirm connection
            logger.info("Waiting for heartbeat...")
            heartbeat = self.connection.wait_heartbeat(timeout=10)
            
            if heartbeat:
                self.connected = True
                logger.info(f"Connected to vehicle with system ID: {heartbeat.get_srcSystem()}")
                
                # Start telemetry thread
                self.start_telemetry_thread()
                return True
            else:
                logger.error("No heartbeat received - connection failed")
                return False
                
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from MAVLink stream"""
        self.running = False
        self.connected = False
        
        if self.telemetry_thread and self.telemetry_thread.is_alive():
            self.telemetry_thread.join(timeout=2)
        
        if self.connection:
            self.connection.close()
            self.connection = None
        
        logger.info("Disconnected from MAVLink")
    
    def start_telemetry_thread(self):
        """Start background thread for reading telemetry"""
        self.running = True
        # Telemetry loop removed - no automatic data collection
        logger.info("Telemetry thread functionality disabled")
    
    def get_telemetry_data(self):
        """Get current telemetry data (thread-safe)"""
        return self.telemetry_data.copy()
    
    def is_connected(self):
        """Check if connection is active"""
        return self.connected
    
    def send_command_long(self, command, param1=0, param2=0, param3=0, param4=0, param5=0, param6=0, param7=0):
        """Send a MAVLink command"""
        if not self.connected or not self.connection:
            return False
        
        try:
            self.connection.mav.command_long_send(
                self.connection.target_system,
                self.connection.target_component,
                command,
                0,  # confirmation
                param1, param2, param3, param4, param5, param6, param7
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send command: {e}")
            return False
    
    def arm_disarm(self, arm=True):
        """Arm or disarm the vehicle"""
        param1 = 1.0 if arm else 0.0
        return self.send_command_long(mavlink.MAV_CMD_COMPONENT_ARM_DISARM, param1)
    
    def set_mode(self, mode_name):
        """Set flight mode"""
        if not self.connected or not self.connection:
            return False
        
        try:
            # Get mode number from name
            mode_mapping = self.connection.mode_mapping()
            if mode_name in mode_mapping:
                mode_id = mode_mapping[mode_name]
                self.connection.set_mode(mode_id)
                return True
            else:
                logger.error(f"Unknown mode: {mode_name}")
                return False
        except Exception as e:
            logger.error(f"Failed to set mode: {e}")
            return False

    def get_location(self):
        print("Waiting for current location...")
        while True:
            msg = self.connection.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=5)
            if msg:
                lat = msg.lat / 1e7
                lon = msg.lon / 1e7
                print(f"Current location: lat={lat}, lon={lon}")
                return lat, lon
    def takeoff(self, altitude):
        self.set_mode('GUIDED')
        self.arm_disarm(arm=True)
        lat, lon = self.get_location()
        self.connection.mav.mission_clear_all_send(self.connection.target_system, self.connection.target_component)
        time.sleep(1)
        self.connection.mav.mission_count_send(self.connection.target_system, self.connection.target_component, 1)
        time.sleep(0.5)

        self.connection.mav.mission_item_send(
            self.connection.target_system,
            self.connection.target_component,
            0,  # sequence
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0, 1,    # current=0, autocontinue=1
            0, 0, 0, 0,  # params 1-4 unused here
            lat, lon, altitude  # location and altitude
        )
        print("Waiting for mission ACK...")
        """while True:
            ack_msg = self.connection.recv_match(type='MISSION_ACK', blocking=True, timeout=5)
            if ack_msg:
                print("✅ Mission ACK received.")
                break"""
        """Send takeoff command"""
        """self.connection.mav.command_long_send(
            self.connection.target_system,
            self.connection.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1, 0, 0, 0, 0, 0, 0
        )"""
        while True:
            msg = self.connection.recv_match(type='HEARTBEAT', blocking=True, timeout=5)
            if msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED:
                print("✅ Plane is armed.")
                break
        self.set_mode('AUTO')
        return True

    def land(self):
        """Send land command"""
        return self.send_command_long(mavlink.MAV_CMD_NAV_LAND)

    def return_to_launch(self):
        """Send return to launch command"""
        return self.send_command_long(mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH)
    def get_location(self):
        print("Waiting for current location...")
        while True:
            msg = self.connection.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=5)
            if msg:
                lat = msg.lat / 1e7
                lon = msg.lon / 1e7
                print(f"Current location: lat={lat}, lon={lon}")
                return lat, lon
    def takeoff(self, altitude):
        self.set_mode('GUIDED')
        self.arm_disarm(arm=True)
        lat, lon = self.get_location()
        self.connection.mav.mission_clear_all_send(self.connection.target_system, self.connection.target_component)
        time.sleep(1)
        self.connection.mav.mission_count_send(self.connection.target_system, self.connection.target_component, 1)
        time.sleep(0.5)

        self.connection.mav.mission_item_send(
            self.connection.target_system,
            self.connection.target_component,
            0,  # sequence
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0, 1,    # current=0, autocontinue=1
            0, 0, 0, 0,  # params 1-4 unused here
            lat, lon, altitude  # location and altitude
        )
        print("Waiting for mission ACK...")
        """while True:
            ack_msg = self.connection.recv_match(type='MISSION_ACK', blocking=True, timeout=5)
            if ack_msg:
                print("✅ Mission ACK received.")
                break"""
        """Send takeoff command"""
        """self.connection.mav.command_long_send(
            self.connection.target_system,
            self.connection.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1, 0, 0, 0, 0, 0, 0
        )"""
        while True:
            msg = self.connection.recv_match(type='HEARTBEAT', blocking=True, timeout=5)
            if msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED:
                print("✅ Plane is armed.")
                break
        self.set_mode('AUTO')
        return True

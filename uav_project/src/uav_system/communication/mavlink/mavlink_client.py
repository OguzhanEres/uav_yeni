"""
Improved MAVLink Client for UAV communication.
"""

import socket
import threading
import time
from typing import Dict, Any, Optional, Callable, Tuple
from pymavlink import mavutil
from pymavlink.dialects.v20 import common as mavlink

from ...core.base_classes import BaseProtocol
from ...core.exceptions import ConnectionError, TelemetryError
from ...core.logging_config import get_logger

logger = get_logger(__name__)


class MAVLinkClient(BaseProtocol):
    """Enhanced MAVLink client with improved error handling and telemetry."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("MAVLinkClient", config)
        self.connection = None
        self.telemetry_data = {}
        self.telemetry_thread = None
        self.message_handlers = {}
        self.last_heartbeat = 0
        self.system_id = 0
        self.component_id = 0
        
        # Initialize telemetry data structure
        self.reset_telemetry_data()
        
        # Setup default message handlers
        self._setup_message_handlers()
    
    def initialize(self) -> bool:
        """Initialize the MAVLink client."""
        try:
            self.reset_telemetry_data()
            self._initialized = True
            self.logger.info("MAVLink client initialized")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize MAVLink client: {e}")
            return False
    
    def start(self) -> bool:
        """Start the MAVLink client."""
        if not self._initialized:
            self.logger.error("MAVLink client not initialized")
            return False
        
        try:
            self._running = True
            self.logger.info("MAVLink client started")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start MAVLink client: {e}")
            return False
    
    def stop(self) -> bool:
        """Stop the MAVLink client."""
        try:
            self._running = False
            self.disconnect()
            self.logger.info("MAVLink client stopped")
            return True
        except Exception as e:
            self.logger.error(f"Failed to stop MAVLink client: {e}")
            return False
    
    def cleanup(self) -> bool:
        """Clean up MAVLink client resources."""
        try:
            self.stop()
            self.message_handlers.clear()
            self.logger.info("MAVLink client cleaned up")
            return True
        except Exception as e:
            self.logger.error(f"Failed to cleanup MAVLink client: {e}")
            return False
    
    def reset_telemetry_data(self):
        """Reset telemetry data to default values."""
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
            "last_heartbeat": 0,
            "system_status": "UNKNOWN"
        }
    
    def connect(self, connection_string: str = "udp:127.0.0.1:14550") -> bool:
        """Connect to MAVLink stream."""
        try:
            self.logger.info(f"Attempting to connect to {connection_string}")
            
            # Create MAVLink connection
            self.connection = mavutil.mavlink_connection(
                connection_string,
                timeout=10
            )
            
            if not self.connection:
                raise ConnectionError("Failed to create MAVLink connection")
            
            # Wait for heartbeat to confirm connection
            self.logger.info("Waiting for heartbeat...")
            heartbeat = self.connection.wait_heartbeat(timeout=10)
            
            if heartbeat:
                self._connected = True
                self.system_id = heartbeat.get_srcSystem()
                self.component_id = heartbeat.get_srcComponent()
                self.last_heartbeat = time.time()
                
                self.logger.info(f"Connected to vehicle with system ID: {self.system_id}")
                
                # Start telemetry thread
                self.start_telemetry_thread()
                return True
            else:
                raise ConnectionError("No heartbeat received - connection failed")
                
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self._connected = False
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from MAVLink stream."""
        try:
            self._running = False
            self._connected = False
            
            # Stop telemetry thread
            if self.telemetry_thread and self.telemetry_thread.is_alive():
                self.telemetry_thread.join(timeout=2)
            
            # Close connection
            if self.connection:
                self.connection.close()
                self.connection = None
            
            self.logger.info("Disconnected from MAVLink")
            return True
            
        except Exception as e:
            self.logger.error(f"Disconnection failed: {e}")
            return False
    
    def send_data(self, data: Any) -> bool:
        """Send data using MAVLink protocol."""
        # This is a generic interface - specific commands should use dedicated methods
        return False
    
    def receive_data(self) -> Any:
        """Receive data using MAVLink protocol."""
        if not self.is_connected or not self.connection:
            return None
        
        try:
            msg = self.connection.recv_match(blocking=False, timeout=1)
            return msg
        except Exception as e:
            self.logger.error(f"Failed to receive data: {e}")
            return None
    
    def start_telemetry_thread(self):
        """Start background thread for reading telemetry."""
        if self.telemetry_thread and self.telemetry_thread.is_alive():
            return
        
        self._running = True
        self.telemetry_thread = threading.Thread(
            target=self._telemetry_loop,
            daemon=True
        )
        self.telemetry_thread.start()
        self.logger.info("Telemetry thread started")
    
    def _telemetry_loop(self):
        """Background telemetry reading loop."""
        while self._running and self._connected:
            try:
                msg = self.connection.recv_match(blocking=False, timeout=0.1)
                if msg:
                    self._process_message(msg)
                time.sleep(0.01)  # Small delay to prevent CPU overload
                
            except Exception as e:
                self.logger.error(f"Telemetry loop error: {e}")
                time.sleep(0.1)
    
    def _process_message(self, msg):
        """Process received MAVLink message."""
        try:
            msg_type = msg.get_type()
            
            # Update last heartbeat time
            if msg_type == 'HEARTBEAT':
                self.last_heartbeat = time.time()
                self._handle_heartbeat(msg)
            
            # Call registered handler if available
            if msg_type in self.message_handlers:
                self.message_handlers[msg_type](msg)
                
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
    
    def _setup_message_handlers(self):
        """Setup default message handlers."""
        self.message_handlers = {
            'HEARTBEAT': self._handle_heartbeat,
            'SYS_STATUS': self._handle_sys_status,
            'GPS_RAW_INT': self._handle_gps_raw,
            'ATTITUDE': self._handle_attitude,
            'GLOBAL_POSITION_INT': self._handle_global_position,
            'VFR_HUD': self._handle_vfr_hud,
        }
    
    def _handle_heartbeat(self, msg):
        """Handle HEARTBEAT message."""
        self.telemetry_data['armed'] = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
        self.telemetry_data['flight_mode'] = mavutil.mode_string_v10(msg)
        self.telemetry_data['system_status'] = mavutil.mavlink.enums['MAV_STATE'][msg.system_status].name
    
    def _handle_sys_status(self, msg):
        """Handle SYS_STATUS message."""
        if hasattr(msg, 'battery_remaining'):
            self.telemetry_data['battery_level'] = msg.battery_remaining
        if hasattr(msg, 'voltage_battery'):
            self.telemetry_data['battery_voltage'] = msg.voltage_battery / 1000.0
    
    def _handle_gps_raw(self, msg):
        """Handle GPS_RAW_INT message."""
        self.telemetry_data['gps_fix'] = msg.fix_type
        self.telemetry_data['satellites'] = msg.satellites_visible
    
    def _handle_attitude(self, msg):
        """Handle ATTITUDE message."""
        self.telemetry_data['roll'] = msg.roll
        self.telemetry_data['pitch'] = msg.pitch
        self.telemetry_data['yaw'] = msg.yaw
    
    def _handle_global_position(self, msg):
        """Handle GLOBAL_POSITION_INT message."""
        self.telemetry_data['lat'] = msg.lat / 1e7
        self.telemetry_data['lon'] = msg.lon / 1e7
        self.telemetry_data['altitude'] = msg.alt / 1000.0
        self.telemetry_data['heading'] = msg.hdg / 100.0
    
    def _handle_vfr_hud(self, msg):
        """Handle VFR_HUD message."""
        self.telemetry_data['airspeed'] = msg.airspeed
        self.telemetry_data['groundspeed'] = msg.groundspeed
        self.telemetry_data['throttle'] = msg.throttle
    
    def get_telemetry_data(self) -> Dict[str, Any]:
        """Get current telemetry data (thread-safe)."""
        return self.telemetry_data.copy()
    
    def register_message_handler(self, msg_type: str, handler: Callable):
        """Register a custom message handler."""
        self.message_handlers[msg_type] = handler
    
    def send_command_long(self, command: int, param1: float = 0, param2: float = 0, 
                         param3: float = 0, param4: float = 0, param5: float = 0, 
                         param6: float = 0, param7: float = 0) -> bool:
        """Send a MAVLink COMMAND_LONG message."""
        if not self.is_connected or not self.connection:
            self.logger.error("Cannot send command - not connected")
            return False
        
        try:
            self.connection.mav.command_long_send(
                self.connection.target_system,
                self.connection.target_component,
                command,
                0,  # confirmation
                param1, param2, param3, param4, param5, param6, param7
            )
            self.logger.debug(f"Sent command {command}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to send command: {e}")
            return False
    
    def arm_disarm(self, arm: bool = True) -> bool:
        """Arm or disarm the vehicle."""
        param1 = 1.0 if arm else 0.0
        action = "arm" if arm else "disarm"
        self.logger.info(f"Sending {action} command")
        return self.send_command_long(mavlink.MAV_CMD_COMPONENT_ARM_DISARM, param1)
    
    def set_mode(self, mode_name: str) -> bool:
        """Set flight mode."""
        if not self.is_connected or not self.connection:
            self.logger.error("Cannot set mode - not connected")
            return False
        
        try:
            # Get mode number from name
            mode_mapping = self.connection.mode_mapping()
            if mode_name not in mode_mapping:
                self.logger.error(f"Unknown mode: {mode_name}")
                return False
            
            mode_id = mode_mapping[mode_name]
            self.logger.info(f"Setting mode to {mode_name} (ID: {mode_id})")
            
            # Send mode change command
            self.connection.set_mode(mode_id)
            
            # Wait for mode change confirmation
            timeout = 10  # 10 second timeout
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    msg = self.connection.recv_match(type='HEARTBEAT', blocking=True, timeout=1)
                    if msg:
                        current_mode = mavutil.mode_string_v10(msg)
                        if current_mode == mode_name:
                            self.logger.info(f"Mode successfully changed to {mode_name}")
                            return True
                        else:
                            self.logger.debug(f"Current mode: {current_mode}, waiting for {mode_name}...")
                except Exception as e:
                    self.logger.warning(f"Error checking mode change: {e}")
                
                time.sleep(0.1)
            
            # If we get here, mode change failed
            self.logger.error(f"Mode change to {mode_name} timed out")
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to set mode: {e}")
            return False
    
    def takeoff(self, altitude: float) -> bool:
        """Send takeoff command."""
        self.logger.info(f"Sending takeoff command for altitude {altitude}m")
        return self.send_command_long(
            mavlink.MAV_CMD_NAV_TAKEOFF,
            0, 0, 0, 0, 0, 0, altitude
        )
    
    def land(self) -> bool:
        """Send land command."""
        self.logger.info("Sending land command")
        return self.send_command_long(mavlink.MAV_CMD_NAV_LAND)
    
    def return_to_launch(self) -> bool:
        """Send return to launch command."""
        self.logger.info("Sending RTL command")
        return self.send_command_long(mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH)
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get detailed connection status."""
        return {
            'connected': self._connected,
            'system_id': self.system_id,
            'component_id': self.component_id,
            'last_heartbeat': self.last_heartbeat,
            'time_since_heartbeat': time.time() - self.last_heartbeat if self.last_heartbeat else 0,
            'running': self._running
        }

    def get_location(self) -> Optional[Tuple[float, float]]:
        """Get current location from UAV."""
        if not self.is_connected or not self.connection:
            self.logger.error("Cannot get location - not connected")
            return None
        
        print("Waiting for current location...")
        retries = 0
        max_retries = 10
        
        while retries < max_retries:
            try:
                msg = self.connection.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=5)
                if msg:
                    lat = msg.lat / 1e7
                    lon = msg.lon / 1e7
                    print(f"Current location: lat={lat}, lon={lon}")
                    self.logger.info(f"Location obtained: lat={lat}, lon={lon}")
                    return lat, lon
                else:
                    retries += 1
                    self.logger.warning(f"No location message received, retry {retries}/{max_retries}")
            except Exception as e:
                retries += 1
                self.logger.error(f"Error getting location: {e}, retry {retries}/{max_retries}")
                
        self.logger.error("Failed to get location after maximum retries")
        return None

    def autonomous_takeoff(self, altitude: float) -> bool:
        """Perform autonomous takeoff sequence."""
        if not self.is_connected or not self.connection:
            self.logger.error("Cannot takeoff - not connected")
            return False
        
        try:
            self.logger.info(f"Starting autonomous takeoff to {altitude}m")
            
            # Step 1: Set mode to GUIDED
            if not self.set_mode('GUIDED'):
                self.logger.error("Failed to set GUIDED mode")
                return False
            time.sleep(1)  # Wait for mode change to take effect
            
            # Step 2: Arm the vehicle
            if not self.arm_disarm(arm=True):
                self.logger.error("Failed to arm vehicle")
                return False
            
            # Step 3: Wait for vehicle to be armed
            timeout = 30  # 30 second timeout
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    msg = self.connection.recv_match(type='HEARTBEAT', blocking=True, timeout=2)
                    if msg and (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED):
                        print("✅ Plane is armed.")
                        self.logger.info("Vehicle armed successfully")
                        break
                except Exception as e:
                    self.logger.warning(f"Error checking arm status: {e}")
            else:
                self.logger.error("Vehicle failed to arm within timeout")
                return False
            
            # Step 4: Get current location
            location = self.get_location()
            if not location:
                self.logger.error("Failed to get current location")
                return False
            
            lat, lon = location
            
            # Step 5: Clear existing mission
            self.logger.info("Clearing existing mission...")
            self.connection.mav.mission_clear_all_send(
                self.connection.target_system, 
                self.connection.target_component
            )
            
            # Wait for mission clear acknowledgment
            mission_ack_timeout = 10
            start_time = time.time()
            while time.time() - start_time < mission_ack_timeout:
                try:
                    msg = self.connection.recv_match(type='MISSION_ACK', blocking=True, timeout=2)
                    if msg:
                        if msg.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
                            self.logger.info("Mission cleared successfully")
                            break
                        else:
                            self.logger.warning(f"Mission clear failed with type: {msg.type}")
                            return False
                except Exception as e:
                    self.logger.warning(f"Error waiting for mission clear ACK: {e}")
            
            # Step 6: Set mission count
            self.logger.info("Setting mission count...")
            self.connection.mav.mission_count_send(
                self.connection.target_system, 
                self.connection.target_component, 
                1
            )
            
            # Step 7: Wait for mission request
            start_time = time.time()
            while time.time() - start_time < mission_ack_timeout:
                try:
                    msg = self.connection.recv_match(type='MISSION_REQUEST', blocking=True, timeout=2)
                    if msg and msg.seq == 0:
                        self.logger.info("Mission request received for item 0")
                        break
                except Exception as e:
                    self.logger.warning(f"Error waiting for mission request: {e}")
            else:
                self.logger.error("No mission request received")
                return False
            
            # Step 8: Send takeoff mission item
            self.logger.info(f"Sending takeoff mission item to {altitude}m")
            self.connection.mav.mission_item_int_send(
                self.connection.target_system,
                self.connection.target_component,
                0,  # sequence
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                1, 1,    # current=1, autocontinue=1 (first item should be current)
                0, 0, 0, 0,  # params 1-4 unused for takeoff
                int(lat * 1e7),   # lat in int format
                int(lon * 1e7),   # lon in int format
                altitude  # altitude
            )
            
            # Step 9: Wait for mission acknowledgment
            print("Waiting for mission ACK...")
            self.logger.info("Waiting for mission acknowledgment...")
            
            start_time = time.time()
            while time.time() - start_time < mission_ack_timeout:
                try:
                    msg = self.connection.recv_match(type='MISSION_ACK', blocking=True, timeout=2)
                    if msg:
                        if msg.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
                            self.logger.info("Mission accepted successfully")
                            break
                        else:
                            self.logger.error(f"Mission rejected with type: {msg.type}")
                            return False
                except Exception as e:
                    self.logger.warning(f"Error waiting for mission ACK: {e}")
            else:
                self.logger.error("No mission acknowledgment received")
                return False
            
            # Step 10: Set mode to AUTO to execute mission
            self.logger.info("Setting mode to AUTO...")
            if not self.set_mode('AUTO'):
                self.logger.error("Failed to set AUTO mode")
                return False
            
            # Step 11: Verify mode change
            time.sleep(2)  # Wait for mode change to stabilize
            mode_verified = False
            for _ in range(10):  # Try for 10 seconds
                try:
                    msg = self.connection.recv_match(type='HEARTBEAT', blocking=True, timeout=1)
                    if msg:
                        current_mode = mavutil.mode_string_v10(msg)
                        if current_mode == 'AUTO':
                            self.logger.info("Successfully switched to AUTO mode")
                            mode_verified = True
                            break
                        else:
                            self.logger.info(f"Current mode: {current_mode}, waiting for AUTO...")
                except Exception as e:
                    self.logger.warning(f"Error checking mode: {e}")
                time.sleep(1)
            
            if not mode_verified:
                self.logger.error("Failed to verify AUTO mode switch")
                return False
            
            self.logger.info("Autonomous takeoff sequence completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Autonomous takeoff failed: {e}")
            return False

    def send_mission_item(self, seq: int, frame: int, command: int, current: int, 
                         autocontinue: int, param1: float, param2: float, param3: float, 
                         param4: float, x: float, y: float, z: float) -> bool:
        """Send a mission item to the vehicle."""
        if not self.is_connected or not self.connection:
            self.logger.error("Cannot send mission item - not connected")
            return False
        
        try:
            self.connection.mav.mission_item_int_send(
                self.connection.target_system,
                self.connection.target_component,
                seq,
                frame,
                command,
                current,
                autocontinue,
                param1, param2, param3, param4,
                int(x * 1e7),  # lat
                int(y * 1e7),  # lon
                z             # alt
            )
            self.logger.debug(f"Mission item {seq} sent successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to send mission item: {e}")
            return False

    def autonomous_land(self, lon: float, lat: float, current_alt: float, cruise_alt: float) -> bool:
        """Perform autonomous landing sequence."""
        if not self.is_connected or not self.connection:
            self.logger.error("Cannot land - not connected")
            return False
        
        try:
            self.logger.info(f"Starting autonomous landing sequence at lat={lat}, lon={lon}")
            
            # Step 1: Clear existing mission
            self.connection.mav.mission_clear_all_send(
                self.connection.target_system, 
                self.connection.target_component
            )
            time.sleep(1)
            
            # Step 2: Set mission count (3 items: takeoff, waypoint, land)
            self.connection.mav.mission_count_send(
                self.connection.target_system, 
                self.connection.target_component, 
                3
            )
            time.sleep(0.5)
            
            # Step 3: Send takeoff mission item (current position)
            success = self.send_mission_item(
                seq=0,
                frame=mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                command=mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                current=1,
                autocontinue=1,
                param1=0, param2=0, param3=0, param4=0,
                x=lat,
                y=lon,
                z=current_alt
            )
            
            if not success:
                self.logger.error("Failed to send takeoff mission item")
                return False
            
            # Wait for mission request
            try:
                msg = self.connection.recv_match(type='MISSION_REQUEST', blocking=True, timeout=5)
                if not msg:
                    self.logger.warning("No mission request received for item 1")
            except Exception as e:
                self.logger.warning(f"Error waiting for mission request: {e}")
            
            # Step 4: Send waypoint mission item
            success = self.send_mission_item(
                seq=1,
                frame=mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                command=mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                current=0,
                autocontinue=1,
                param1=0, param2=0, param3=0, param4=0,
                x=lat + 0.0005,  # Small offset for approach
                y=lon + 0.0005,
                z=cruise_alt
            )
            
            if not success:
                self.logger.error("Failed to send waypoint mission item")
                return False
            
            # Wait for mission request
            try:
                msg = self.connection.recv_match(type='MISSION_REQUEST', blocking=True, timeout=5)
                if not msg:
                    self.logger.warning("No mission request received for item 2")
            except Exception as e:
                self.logger.warning(f"Error waiting for mission request: {e}")
            
            # Step 5: Send land mission item
            success = self.send_mission_item(
                seq=2,
                frame=mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                command=mavutil.mavlink.MAV_CMD_NAV_LAND,
                current=0,
                autocontinue=1,
                param1=0, param2=0, param3=0, param4=0,
                x=lat,
                y=lon,
                z=0
            )
            
            if not success:
                self.logger.error("Failed to send land mission item")
                return False
            
            # Wait for mission acknowledgment
            try:
                msg = self.connection.recv_match(type='MISSION_ACK', blocking=True, timeout=10)
                if msg:
                    self.logger.info("Mission acknowledged by vehicle")
                else:
                    self.logger.warning("No mission acknowledgment received")
            except Exception as e:
                self.logger.warning(f"Error waiting for mission ACK: {e}")
            
            # Step 6: Set mode to AUTO to execute mission
            if not self.set_mode("AUTO"):
                self.logger.error("Failed to set AUTO mode")
                return False
            
            self.logger.info("Autonomous landing sequence initiated successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Autonomous landing failed: {e}")
            return False

    def get_current_altitude(self) -> Optional[float]:
        """Get current altitude from vehicle."""
        if not self.is_connected or not self.connection:
            return None
        
        try:
            msg = self.connection.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=5)
            if msg:
                return msg.alt / 1000.0  # Convert from mm to meters
        except Exception as e:
            self.logger.error(f"Error getting altitude: {e}")
        
        return None

    def emergency_stop(self) -> bool:
        """Emergency stop - switch to RTL mode."""
        if not self.is_connected or not self.connection:
            self.logger.error("Cannot emergency stop - not connected")
            return False
        
        try:
            self.logger.warning("EMERGENCY STOP - Switching to RTL mode")
            return self.set_mode('RTL')
        except Exception as e:
            self.logger.error(f"Emergency stop failed: {e}")
            return False

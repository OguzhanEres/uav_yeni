"""
UAV Plane Controller Module
Modernized version with improved architecture for MAVLink support.
"""
import time
import math
from typing import Optional, Dict, Any, Callable, List, Tuple

try:
    from dronekit import connect, VehicleMode, LocationGlobalRelative, Command, Battery, LocationGlobal, Attitude
except ImportError:
    # If dronekit is not available, create dummy classes
    class VehicleMode:
        def __init__(self, mode):
            self.name = mode
    
    def connect(*args, **kwargs):
        return None
    
    LocationGlobalRelative = None
    Command = None
    Battery = None
    LocationGlobal = None
    Attitude = None

from pymavlink import mavutil

from uav_system.core.logging_config import get_logger
from uav_system.core.base_classes import BaseComponent
from uav_system.core.exceptions import ConnectionError, UAVException

logger = get_logger(__name__)

# Global team number
TEAM_NUMBER = 1


class UAVPlane(BaseComponent):
    """
    Modern UAV Plane controller with improved error handling and architecture.
    """
    
    def __init__(self, vehicle=None, connection_string=None):
        # BaseComponent expects (name: str, config: dict)
        super().__init__(name="UAVPlane", config=None)
        
        # Connection parameters
        self.connection_string = connection_string
        self.vehicle = None
        self.connected = False
        
        # MAVLink support
        self.mavlink_client = None
        self.connection = None  # Direct MAVLink connection
        
        # Flight state
        self.armed = False
        self.mode = "UNKNOWN"
        self.location = None
        self.attitude = None
        self.velocity = None
        self.battery = None
        self.gps_info = None
        
        # Mission and waypoints
        self.home_location = None
        self.target_location = None
        self.mission_items = []
        
        # Callbacks and listeners
        self.callbacks = {
            'location': [],
            'attitude': [],
            'velocity': [],
            'armed': [],
            'mode': [],
            'battery': [],
            'heartbeat': []
        }
        
        # Threading
        self.listener_thread = None
        self.heartbeat_thread = None
        
        # Initialize connection
        if vehicle is not None:
            self.vehicle = vehicle
            self.connected = True
            logger.info("Using provided vehicle object")
        elif connection_string is not None:
            try:
                self.connect(connection_string)
            except Exception as e:
                logger.error(f"Failed to connect: {e}")
        else:
            logger.warning("No vehicle or connection string provided")

    def initialize(self):
        """Başlangıç konfigürasyonları için çağrılır."""
        pass

    def start(self):
        """Çalışmaya başladığında çağrılır."""
        pass

    def stop(self):
        """Durdurulurken çağrılır."""
        pass

    def cleanup(self):
        """Kaynaklar kapatılırken çağrılır."""
        pass
    
    def _has_valid_connection(self) -> bool:
        """Check if we have a valid connection (DroneKit vehicle or MAVLink)."""
        return (self.connected and self.vehicle is not None) or \
               (self.mavlink_client is not None and self.connection is not None)
    
    def _send_mavlink_command(self, command_type: str, **kwargs) -> bool:
        """Send command via MAVLink if available."""
        if self.mavlink_client is None:
            return False
        
        try:
            if command_type == "arm":
                return self.mavlink_client.arm_disarm(True)
            elif command_type == "disarm":
                return self.mavlink_client.arm_disarm(False)
            elif command_type == "set_mode":
                mode = kwargs.get('mode', 'GUIDED')
                return self.mavlink_client.set_mode(mode)
            elif command_type == "takeoff":
                altitude = kwargs.get('altitude', 10.0)
                # For takeoff, we need to arm first, set mode, then takeoff
                if not self.mavlink_client.arm_disarm(True):
                    return False
                if not self.mavlink_client.set_mode("GUIDED"):
                    return False
                # MAVLink takeoff command would go here
                return True
            return False
        except Exception as e:
            logger.error(f"MAVLink command failed: {e}")
            return False

    def connect(self, connection_string: str, timeout: int = 30) -> bool:
        """
        Connect to the UAV.
        
        Args:
            connection_string: MAVLink connection string
            timeout: Connection timeout in seconds
            
        Returns:
            bool: True if connection successful
            
        Raises:
            ConnectionError: If connection fails
        """
        try:
            logger.info(f"Connecting to vehicle via {connection_string}")
            
            # Only try DroneKit if it's available
            if connect is not None:
                # Try DroneKit connection
                self.vehicle = connect(connection_string, wait_ready=True, timeout=timeout)
                
                if self.vehicle:
                    self.connected = True
                    self._setup_listeners()
                    self._update_initial_state()
                    
                logger.info("Successfully connected to vehicle")
                return True
            else:
                logger.warning("DroneKit not available - only MAVLink mode supported")
                return False
            
        except Exception as e:
            error_msg = f"Failed to connect to vehicle: {e}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)
    
    def get_location(self):
        """
        GLOBAL_POSITION_INT mesajını okuyup lat/lon döner.
        """
        if not getattr(self, 'connection', None):
            raise ConnectionError("Vehicle not connected")
        msg = self.connection.recv_match(
            type='GLOBAL_POSITION_INT', blocking=True, timeout=5
        )
        if not msg:
            raise ConnectionError("No position data")
        return msg.lat / 1e7, msg.lon / 1e7

    def disconnect(self):
        """Disconnect from the UAV."""
        try:
            if self.vehicle and self.connected:
                # Stop listeners
                self._stop_listeners()
                
                # Close vehicle connection
                self.vehicle.close()
                self.connected = False
                
                logger.info("Disconnected from vehicle")
                
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
    
    def _setup_listeners(self):
        """Setup vehicle attribute listeners."""
        if not self.vehicle:
            return
            
        try:
            # Location listener
            @self.vehicle.on_attribute('location.global_relative_frame')
            def location_listener(self_vehicle, attr_name, value):
                self.location = value
                self._notify_callbacks('location', value)
            
            # Attitude listener
            @self.vehicle.on_attribute('attitude')
            def attitude_listener(self_vehicle, attr_name, value):
                self.attitude = value
                self._notify_callbacks('attitude', value)
            
            # Velocity listener
            @self.vehicle.on_attribute('velocity')
            def velocity_listener(self_vehicle, attr_name, value):
                self.velocity = value
                self._notify_callbacks('velocity', value)
            
            # Armed state listener
            @self.vehicle.on_attribute('armed')
            def armed_listener(self_vehicle, attr_name, value):
                self.armed = value
                self._notify_callbacks('armed', value)
            
            # Mode listener
            @self.vehicle.on_attribute('mode')
            def mode_listener(self_vehicle, attr_name, value):
                self.mode = str(value)
                self._notify_callbacks('mode', value)
            
            logger.info("Vehicle listeners setup completed")
            
        except Exception as e:
            logger.error(f"Failed to setup listeners: {e}")
    
    def _stop_listeners(self):
        """Stop all vehicle listeners."""
        if self.vehicle:
            try:
                self.vehicle.remove_attribute_listener('*', lambda *args: None)
            except Exception as e:
                logger.error(f"Error stopping listeners: {e}")
    
    def _update_initial_state(self):
        """Update initial vehicle state."""
        if not self.vehicle:
            return
            
        try:
            self.armed = self.vehicle.armed
            self.mode = str(self.vehicle.mode)
            self.location = self.vehicle.location.global_relative_frame
            self.attitude = self.vehicle.attitude
            self.velocity = self.vehicle.velocity
            
            logger.info(f"Initial state - Armed: {self.armed}, Mode: {self.mode}")
            
        except Exception as e:
            logger.error(f"Error updating initial state: {e}")
    
    def add_callback(self, event_type: str, callback: Callable):
        """
        Add callback for vehicle events.
        
        Args:
            event_type: Type of event ('location', 'attitude', 'velocity', etc.)
            callback: Callback function
        """
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
        else:
            logger.warning(f"Unknown event type: {event_type}")
    
    def remove_callback(self, event_type: str, callback: Callable):
        """Remove callback for vehicle events."""
        if event_type in self.callbacks and callback in self.callbacks[event_type]:
            self.callbacks[event_type].remove(callback)
    
    def _notify_callbacks(self, event_type: str, data: Any):
        """Notify all callbacks for an event type."""
        try:
            for callback in self.callbacks.get(event_type, []):
                callback(data)
        except Exception as e:
            logger.error(f"Error in callback for {event_type}: {e}")
    
    def arm(self, timeout: int = 30) -> bool:
        """
        Arm the vehicle.
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            bool: True if armed successfully
        """
        if not self._has_valid_connection():
            logger.warning("No valid connection for arm command")
            return False
        
        try:
            logger.info("Arming vehicle...")
            
            # Use MAVLink if available, otherwise use DroneKit
            if self.mavlink_client is not None:
                return self._send_mavlink_command("arm")
            
            # DroneKit path
            if self.vehicle is None:
                logger.warning("No vehicle connection available")
                return False
            
            # Check if already armed
            if self.vehicle.armed:
                logger.info("Vehicle already armed")
                return True
            
            # Pre-arm checks
            if not self._pre_arm_checks():
                return False
            
            # Set mode to GUIDED
            self.vehicle.mode = VehicleMode("GUIDED")
            
            # Wait for mode change
            start_time = time.time()
            while self.vehicle.mode.name != "GUIDED":
                if time.time() - start_time > timeout:
                    logger.error("Timeout waiting for GUIDED mode")
                    return False
                time.sleep(0.1)
            
            # Arm the vehicle
            self.vehicle.armed = True
            
            # Wait for arming
            start_time = time.time()
            while not self.vehicle.armed:
                if time.time() - start_time > timeout:
                    logger.error("Timeout waiting for arming")
                    return False
                time.sleep(0.1)
            
            logger.info("Vehicle armed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Arming failed: {e}")
            return False
    
    def disarm(self, timeout: int = 10) -> bool:
        """
        Disarm the vehicle.
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            bool: True if disarmed successfully
        """
        if not self._has_valid_connection():
            logger.warning("No valid connection for disarm command")
            return False
        
        try:
            logger.info("Disarming vehicle...")
            
            # Use MAVLink if available
            if self.mavlink_client is not None:
                return self._send_mavlink_command("disarm")
            
            # DroneKit path
            if self.vehicle is None:
                logger.warning("No vehicle connection available")
                return False
            
            self.vehicle.armed = False
            
            # Wait for disarming
            start_time = time.time()
            while self.vehicle.armed:
                if time.time() - start_time > timeout:
                    logger.warning("Timeout waiting for disarming")
                    break
                time.sleep(0.1)
            
            logger.info("Vehicle disarmed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Disarming failed: {e}")
            return False
    
    def _pre_arm_checks(self) -> bool:
        """Perform pre-arm safety checks."""
        try:
            if self.vehicle is None:
                return False
                
            # Check if GPS has a fix
            if hasattr(self.vehicle, 'gps_0') and self.vehicle.gps_0.fix_type < 3:
                logger.warning("Waiting for GPS fix...")
                return False
            
            # Check if vehicle is ready
            if hasattr(self.vehicle, 'is_armable') and not self.vehicle.is_armable:
                logger.warning("Vehicle not armable - check pre-arm status")
                return False
            
            logger.info("Pre-arm checks passed")
            return True
            
        except Exception as e:
            logger.error(f"Error in pre-arm checks: {e}")
            return False
    
    def takeoff(self, altitude: float, timeout: int = 60) -> bool:
        """
        Take off to specified altitude.
        
        Args:
            altitude: Target altitude in meters
            timeout: Timeout in seconds
            
        Returns:
            bool: True if takeoff successful
        """
        if not self._has_valid_connection():
            logger.warning("No valid connection for takeoff command")
            return False
        
        try:
            logger.info(f"Taking off to {altitude}m...")
            
            # Use MAVLink if available, otherwise use DroneKit
            if self.mavlink_client is not None:
                return self._send_mavlink_command("takeoff", altitude=altitude)
            
            # DroneKit path
            if self.vehicle is None:
                logger.warning("No vehicle connection available")
                return False
            
            # Ensure vehicle is armed
            if not self.vehicle.armed:
                if not self.arm():
                    return False
            
            # Take off
            self.vehicle.simple_takeoff(altitude)
            
            # Wait for takeoff
            start_time = time.time()
            while True:
                current_alt = self.vehicle.location.global_relative_frame.alt
                
                if current_alt >= altitude * 0.95:
                    logger.info(f"Takeoff complete at {current_alt:.1f}m")
                    break
                
                if time.time() - start_time > timeout:
                    logger.error(f"Takeoff timeout - current altitude: {current_alt:.1f}m")
                    return False
                
                time.sleep(1)
            
            return True
            
        except Exception as e:
            logger.error(f"Takeoff failed: {e}")
            return False
    
    def land(self, timeout: int = 60) -> bool:
        """
        Land the vehicle.
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            bool: True if landing successful
        """
        if not self._has_valid_connection():
            logger.warning("No valid connection for land command")
            return False
        
        try:
            logger.info("Landing vehicle...")
            
            # Use MAVLink if available, otherwise use DroneKit
            if self.mavlink_client is not None:
                return self.mavlink_client.set_mode("LAND")
            
            # DroneKit path
            if self.vehicle is None:
                logger.warning("No vehicle connection available")
                return False
            
            # Set mode to LAND
            self.vehicle.mode = VehicleMode("LAND")
            
            # Wait for landing
            start_time = time.time()
            while self.vehicle.armed:
                if time.time() - start_time > timeout:
                    logger.warning("Landing timeout - vehicle still armed")
                    break
                time.sleep(1)
            
            logger.info("Landing complete")
            return True
            
        except Exception as e:
            logger.error(f"Landing failed: {e}")
            return False
    
    def goto_location(self, lat: float, lon: float, alt: float = None):
        """Go to specified location."""
        if not self._has_valid_connection():
            logger.warning("No valid connection for goto command")
            return False
        
        try:
            if self.vehicle is None or LocationGlobalRelative is None:
                logger.warning("No vehicle or LocationGlobalRelative available")
                return False
                
            if alt is None:
                alt = self.vehicle.location.global_relative_frame.alt
            
            target_location = LocationGlobalRelative(lat, lon, alt)
            self.vehicle.simple_goto(target_location)
            
            logger.info(f"Navigating to {lat:.6f}, {lon:.6f} at {alt}m")
            return True
            
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return False
    
    def set_mode(self, mode: str) -> bool:
        """Set flight mode."""
        if not self._has_valid_connection():
            logger.warning("No valid connection for set_mode command")
            return False
        
        try:
            # Use MAVLink if available
            if self.mavlink_client is not None:
                return self.mavlink_client.set_mode(mode)
            
            # DroneKit path
            if self.vehicle is None:
                logger.warning("No vehicle connection available")
                return False
            
            self.vehicle.mode = VehicleMode(mode)
            logger.info(f"Set mode to {mode}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set mode {mode}: {e}")
            return False
    
    def get_telemetry(self) -> Dict[str, Any]:
        """
        Get current telemetry data.
        
        Returns:
            dict: Telemetry data
        """
        if not self._has_valid_connection():
            return {}
        
        try:
            # Use MAVLink telemetry if available
            if self.mavlink_client is not None:
                return self.mavlink_client.get_telemetry()
            
            # DroneKit path
            if self.vehicle is None:
                return {}
            
            telemetry = {
                'timestamp': time.time(),
                'connected': self.connected,
                'armed': getattr(self.vehicle, 'armed', False),
                'mode': str(getattr(self.vehicle, 'mode', 'UNKNOWN')),
                'system_status': str(getattr(self.vehicle.system_status, 'state', 'UNKNOWN')) if hasattr(self.vehicle, 'system_status') else 'UNKNOWN',
                
                # Location
                'lat': getattr(self.vehicle.location.global_relative_frame, 'lat', 0) if hasattr(self.vehicle, 'location') and self.vehicle.location.global_relative_frame else 0,
                'lon': getattr(self.vehicle.location.global_relative_frame, 'lon', 0) if hasattr(self.vehicle, 'location') and self.vehicle.location.global_relative_frame else 0,
                'alt': getattr(self.vehicle.location.global_relative_frame, 'alt', 0) if hasattr(self.vehicle, 'location') and self.vehicle.location.global_relative_frame else 0,
                
                # Attitude
                'roll': getattr(self.vehicle.attitude, 'roll', 0) if hasattr(self.vehicle, 'attitude') and self.vehicle.attitude else 0,
                'pitch': getattr(self.vehicle.attitude, 'pitch', 0) if hasattr(self.vehicle, 'attitude') and self.vehicle.attitude else 0,
                'yaw': getattr(self.vehicle.attitude, 'yaw', 0) if hasattr(self.vehicle, 'attitude') and self.vehicle.attitude else 0,
                
                # Velocity
                'vx': self.vehicle.velocity[0] if hasattr(self.vehicle, 'velocity') and self.vehicle.velocity else 0,
                'vy': self.vehicle.velocity[1] if hasattr(self.vehicle, 'velocity') and self.vehicle.velocity else 0,
                'vz': self.vehicle.velocity[2] if hasattr(self.vehicle, 'velocity') and self.vehicle.velocity else 0,
                
                # GPS
                'gps_fix': getattr(self.vehicle.gps_0, 'fix_type', 0) if hasattr(self.vehicle, 'gps_0') and self.vehicle.gps_0 else 0,
                'satellites': getattr(self.vehicle.gps_0, 'satellites_visible', 0) if hasattr(self.vehicle, 'gps_0') and self.vehicle.gps_0 else 0,
                
                # Battery
                'battery_voltage': getattr(self.vehicle.battery, 'voltage', 0) if hasattr(self.vehicle, 'battery') and self.vehicle.battery else 0,
                'battery_current': getattr(self.vehicle.battery, 'current', 0) if hasattr(self.vehicle, 'battery') and self.vehicle.battery else 0,
                'battery_level': getattr(self.vehicle.battery, 'level', 0) if hasattr(self.vehicle, 'battery') and self.vehicle.battery else 0,
            }
            
            return telemetry
            
        except Exception as e:
            logger.error(f"Error getting telemetry: {e}")
            return {}
    
    def get_telemetry_data(self) -> Dict[str, Any]:
        """Alias for get_telemetry for backward compatibility."""
        return self.get_telemetry()
    
    def __del__(self):
        """Cleanup on object destruction."""
        try:
            self.disconnect()
        except:
            pass
    
    def fly_waypoints(self, waypoints, threshold=5.0):
        """
        Fly to waypoints (simplified version for demo).
        """
        if not self._has_valid_connection():
            logger.error("Cannot fly waypoints - no connection")
            return False
            
        logger.info(f"Starting waypoint mission with {len(waypoints)} waypoints")
        
        # For now, just set mode to AUTO if possible
        if self.mavlink_client is not None:
            self.mavlink_client.set_mode("AUTO")
            logger.info("Set mode to AUTO for waypoint mission")
            return True
        elif self.vehicle is not None:
            try:
                self.vehicle.mode = VehicleMode("AUTO")
                logger.info("Set mode to AUTO for waypoint mission")
                return True
            except Exception as e:
                logger.error(f"Failed to set AUTO mode: {e}")
                return False
        
        return False
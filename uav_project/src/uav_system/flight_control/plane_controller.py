"""
UAV Plane Controller Module
Modernized version of the original plane.py with improved architecture.
"""

import time
import math
import copy
import threading
import argparse
import socket
from typing import Optional, Dict, Any, Callable, List, Tuple
from dronekit import connect, VehicleMode, LocationGlobalRelative, Command, Battery, LocationGlobal, Attitude
from pymavlink import mavutil
from threading import Timer
import numpy as np
import psutil

from core.logging_config import get_logger
from core.base_classes import BaseModule
from core.exceptions import ConnectionError, UAVException

logger = get_logger(__name__)

# Global team number
TEAM_NUMBER = 1

import math
import time
from pymavlink import mavutil

class WaypointNavigator:
    def __init__(self, waypoints, threshold=5.0):
        self.waypoints = waypoints
        self.threshold = threshold
        self.current_index = 0

    def distance(self, p1, p2):
        return math.sqrt((p1[0] - p2[0])**2 +
                         (p1[1] - p2[1])**2 +
                         (p1[2] - p2[2])**2)

    def update(self, current_pos):
        if self.current_index >= len(self.waypoints):
            return None
        target = self.waypoints[self.current_index]
        dist = self.distance(current_pos, target)
        # overshoot veya threshold’a ulaşıldıysa bir sonrakine geç
        if dist <= self.threshold or getattr(self, 'prev_dist', None) and dist > self.prev_dist:
            self.current_index += 1
            if self.current_index >= len(self.waypoints):
                return None
            target = self.waypoints[self.current_index]
        self.prev_dist = dist
        return target
class UAVPlane(BaseModule):
    """
    Modern UAV Plane controller with improved error handling and architecture.
    """
    
    def __init__(self, connection_string: Optional[str] = None, vehicle=None):
        """
        Initialize the UAV plane controller.
        
        Args:
            connection_string: MAVLink connection string (e.g., tcp:127.0.0.1:5760)
            vehicle: Existing dronekit vehicle object
        """
        super().__init__()
        
        # Connection parameters
        self.connection_string = connection_string
        self.vehicle = None
        self.connected = False
        
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
            self.connect(connection_string)
        else:
            logger.warning("No vehicle or connection string provided")
    
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
            logger.info(f"Connecting to vehicle at: {connection_string}")
            
            self.vehicle = connect(connection_string, wait_ready=True, timeout=timeout)
            self.connection_string = connection_string
            self.connected = True
            
            # Setup listeners
            self._setup_listeners()
            
            # Get initial state
            self._update_initial_state()
            
            logger.info("Successfully connected to vehicle")
            return True
            
        except Exception as e:
            error_msg = f"Failed to connect to vehicle: {e}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)
    
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
            
            # Battery listener
            @self.vehicle.on_attribute('battery')
            def battery_listener(self_vehicle, attr_name, value):
                self.battery = value
                self._notify_callbacks('battery', value)
            
            logger.info("Vehicle listeners setup complete")
            
        except Exception as e:
            logger.error(f"Error setting up listeners: {e}")
    
    def _stop_listeners(self):
        """Stop all vehicle listeners."""
        if self.vehicle:
            try:
                # Remove all listeners
                self.vehicle.remove_attribute_listener('location.global_relative_frame', 
                                                     self.vehicle._attribute_listeners['location.global_relative_frame'])
                self.vehicle.remove_attribute_listener('attitude', 
                                                     self.vehicle._attribute_listeners['attitude'])
                self.vehicle.remove_attribute_listener('velocity', 
                                                     self.vehicle._attribute_listeners['velocity'])
                self.vehicle.remove_attribute_listener('armed', 
                                                     self.vehicle._attribute_listeners['armed'])
                self.vehicle.remove_attribute_listener('mode', 
                                                     self.vehicle._attribute_listeners['mode'])
                self.vehicle.remove_attribute_listener('battery', 
                                                     self.vehicle._attribute_listeners['battery'])
                
                logger.info("Vehicle listeners stopped")
                
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
            self.battery = self.vehicle.battery
            self.home_location = self.vehicle.home_location
            
            logger.info(f"Initial state - Mode: {self.mode}, Armed: {self.armed}")
            
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
            logger.debug(f"Callback added for {event_type}")
        else:
            logger.warning(f"Unknown event type: {event_type}")
    
    def remove_callback(self, event_type: str, callback: Callable):
        """Remove callback for vehicle events."""
        if event_type in self.callbacks and callback in self.callbacks[event_type]:
            self.callbacks[event_type].remove(callback)
            logger.debug(f"Callback removed for {event_type}")
    
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
        if not self.connected or not self.vehicle:
            raise UAVException("Vehicle not connected")
        
        try:
            logger.info("Arming vehicle...")
            
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
                    raise UAVException("Timeout waiting for GUIDED mode")
                time.sleep(0.1)
            
            # Arm the vehicle
            self.vehicle.armed = True
            
            # Wait for arming
            start_time = time.time()
            while not self.vehicle.armed:
                if time.time() - start_time > timeout:
                    raise UAVException("Timeout waiting for arming")
                time.sleep(0.1)
            
            logger.info("Vehicle armed successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to arm vehicle: {e}"
            logger.error(error_msg)
            raise UAVException(error_msg)
    
    def disarm(self, timeout: int = 10) -> bool:
        """
        Disarm the vehicle.
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            bool: True if disarmed successfully
        """
        if not self.connected or not self.vehicle:
            raise UAVException("Vehicle not connected")
        
        try:
            logger.info("Disarming vehicle...")
            
            if not self.vehicle.armed:
                logger.info("Vehicle already disarmed")
                return True
            
            # Disarm the vehicle
            self.vehicle.armed = False
            
            # Wait for disarming
            start_time = time.time()
            while self.vehicle.armed:
                if time.time() - start_time > timeout:
                    raise UAVException("Timeout waiting for disarming")
                time.sleep(0.1)
            
            logger.info("Vehicle disarmed successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to disarm vehicle: {e}"
            logger.error(error_msg)
            raise UAVException(error_msg)
    
    def _pre_arm_checks(self) -> bool:
        """Perform pre-arm safety checks."""
        try:
            # Check GPS fix
            if self.vehicle.gps_0.fix_type < 3:
                logger.warning("GPS fix not available (3D fix required)")
                return False
            
            # Check home location
            if self.vehicle.home_location is None:
                logger.warning("Home location not set")
                return False
            
            # Check battery voltage
            if self.vehicle.battery.voltage < 10.0:  # Minimum voltage check
                logger.warning(f"Low battery voltage: {self.vehicle.battery.voltage}V")
                return False
            
            # Check system status
            if not self.vehicle.system_status.state == 'STANDBY':
                logger.warning(f"System not in STANDBY state: {self.vehicle.system_status.state}")
            
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
        if not self.connected or not self.vehicle:
            raise UAVException("Vehicle not connected")
        
        try:
            logger.info(f"Taking off to {altitude}m...")
            
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
                    raise UAVException(f"Takeoff timeout - current altitude: {current_alt:.1f}m")
                
                time.sleep(1)
            
            return True
            
        except Exception as e:
            error_msg = f"Takeoff failed: {e}"
            logger.error(error_msg)
            raise UAVException(error_msg)
    
    def land(self, timeout: int = 60) -> bool:
        """
        Land the vehicle.
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            bool: True if landing successful
        """
        if not self.connected or not self.vehicle:
            raise UAVException("Vehicle not connected")
        
        try:
            logger.info("Landing vehicle...")
            
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
            error_msg = f"Landing failed: {e}"
            logger.error(error_msg)
            raise UAVException(error_msg)
    
    def goto_location(self, lat: float, lon: float, alt: float = None):
        """
        Go to specified location.
        
        Args:
            lat: Latitude
            lon: Longitude
            alt: Altitude (optional, uses current if not specified)
        """
        if not self.connected or not self.vehicle:
            raise UAVException("Vehicle not connected")
        
        try:
            if alt is None:
                alt = self.vehicle.location.global_relative_frame.alt
            
            target_location = LocationGlobalRelative(lat, lon, alt)
            self.vehicle.simple_goto(target_location)
            
            logger.info(f"Going to location: {lat:.6f}, {lon:.6f}, {alt:.1f}m")
            
        except Exception as e:
            error_msg = f"Failed to go to location: {e}"
            logger.error(error_msg)
            raise UAVException(error_msg)
    
    def set_mode(self, mode: str) -> bool:
        """
        Set vehicle flight mode.
        
        Args:
            mode: Flight mode name
            
        Returns:
            bool: True if mode set successfully
        """
        if not self.connected or not self.vehicle:
            raise UAVException("Vehicle not connected")
        
        try:
            logger.info(f"Setting mode to: {mode}")
            
            self.vehicle.mode = VehicleMode(mode)
            
            # Wait for mode change
            start_time = time.time()
            while self.vehicle.mode.name != mode:
                if time.time() - start_time > 10:
                    raise UAVException(f"Timeout setting mode to {mode}")
                time.sleep(0.1)
            
            logger.info(f"Mode set to: {mode}")
            return True
            
        except Exception as e:
            error_msg = f"Failed to set mode to {mode}: {e}"
            logger.error(error_msg)
            raise UAVException(error_msg)
    
    def get_telemetry(self) -> Dict[str, Any]:
        """
        Get current telemetry data.
        
        Returns:
            dict: Telemetry data
        """
        if not self.connected or not self.vehicle:
            return {}
        
        try:
            telemetry = {
                'timestamp': time.time(),
                'connected': self.connected,
                'armed': self.vehicle.armed,
                'mode': str(self.vehicle.mode),
                'system_status': str(self.vehicle.system_status.state),
                
                # Location
                'lat': self.vehicle.location.global_relative_frame.lat if self.vehicle.location.global_relative_frame else 0,
                'lon': self.vehicle.location.global_relative_frame.lon if self.vehicle.location.global_relative_frame else 0,
                'alt': self.vehicle.location.global_relative_frame.alt if self.vehicle.location.global_relative_frame else 0,
                
                # Attitude
                'pitch': math.degrees(self.vehicle.attitude.pitch) if self.vehicle.attitude else 0,
                'roll': math.degrees(self.vehicle.attitude.roll) if self.vehicle.attitude else 0,
                'yaw': math.degrees(self.vehicle.attitude.yaw) if self.vehicle.attitude else 0,
                
                # Velocity
                'vx': self.vehicle.velocity[0] if self.vehicle.velocity else 0,
                'vy': self.vehicle.velocity[1] if self.vehicle.velocity else 0,
                'vz': self.vehicle.velocity[2] if self.vehicle.velocity else 0,
                'groundspeed': self.vehicle.groundspeed if hasattr(self.vehicle, 'groundspeed') else 0,
                'airspeed': self.vehicle.airspeed if hasattr(self.vehicle, 'airspeed') else 0,
                'climb': -self.vehicle.velocity[2] if self.vehicle.velocity else 0,
                
                # Battery
                'voltage': self.vehicle.battery.voltage if self.vehicle.battery else 0,
                'current': self.vehicle.battery.current if self.vehicle.battery else 0,
                'level': self.vehicle.battery.level if self.vehicle.battery else 0,
                
                # GPS
                'fix_type': self.vehicle.gps_0.fix_type if hasattr(self.vehicle, 'gps_0') else 0,
                'satellites_visible': self.vehicle.gps_0.satellites_visible if hasattr(self.vehicle, 'gps_0') else 0,
                'eph': self.vehicle.gps_0.eph if hasattr(self.vehicle, 'gps_0') else 0,
                'epv': self.vehicle.gps_0.epv if hasattr(self.vehicle, 'gps_0') else 0,
                
                # Home location
                'home_lat': self.vehicle.home_location.lat if self.vehicle.home_location else 0,
                'home_lon': self.vehicle.home_location.lon if self.vehicle.home_location else 0,
                'home_alt': self.vehicle.home_location.alt if self.vehicle.home_location else 0,
            }
            
            return telemetry
            
        except Exception as e:
            logger.error(f"Error getting telemetry: {e}")
            return {}
    
    def __del__(self):
        """Cleanup on object destruction."""
        try:
            self.disconnect()
        except:
            pass
    
    def fly_waypoints(self, waypoints, threshold=5.0):
        """
        Gerçek-zamanlı olarak waypoint’leri sırasıyla gönderir.
        """
        nav = WaypointNavigator(waypoints, threshold)
        while True:
            # 1) pozisyon & irtifa al
            lat, lon = self.get_location()
            telem = self.get_telemetry_data()
            alt = telem.get("altitude", 0.0)

            # 2) bir sonraki hedefi al
            tgt = nav.update((lat, lon, alt))
            if tgt is None:
                return True
            tgt_lat, tgt_lon, tgt_alt = tgt

            # 3) gönder
            ok = self.send_mission_item(
                seq=nav.current_index - 1,
                frame=mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                command=mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                current=0, autocontinue=1,
                param1=0, param2=0, param3=0, param4=0,
                x=tgt_lat, y=tgt_lon, z=tgt_alt
            )
            if not ok:
                return False

            # 5) küçük bekleme, gerçek-zamanlılık için non-blocking
            time.sleep(0.1)

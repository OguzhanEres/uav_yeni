"""
PowerBeam and Rocket M5 Antenna Communication Module
Handles antenna configuration and video streaming from Rocket M5
"""

import socket
import time
import logging
import requests
import subprocess
import threading
from typing import Optional, Dict, Any
import json

logger = logging.getLogger(__name__)

class AntennaController:
    """Controller for PowerBeam 5AC Gen2 and Rocket M5 antennas"""
    
    def __init__(self):
        self.powerbeam_ip = "192.168.1.20"  # PowerBeam 5AC Gen2 IP
        self.rocket_m5_ip = "192.168.1.21"  # Rocket M5 IP
        self.powerbeam_user = "ubnt"
        self.powerbeam_pass = "ubnt"
        self.rocket_user = "ubnt"
        self.rocket_pass = "ubnt"
        
        # Video streaming settings
        self.video_stream_port = 5005
        self.video_stream_ip = "192.168.88.10"  # Local IP for receiving video
        
        # Antenna states
        self.powerbeam_listening = False
        self.rocket_streaming = False
        
    def configure_powerbeam_listening_mode(self) -> bool:
        """Configure PowerBeam 5AC Gen2 to listening mode"""
        try:
            logger.info("Configuring PowerBeam 5AC Gen2 to listening mode...")
            
            # PowerBeam configuration API endpoint
            config_url = f"http://{self.powerbeam_ip}/api/config"
            
            # Listening mode configuration
            listening_config = {
                "wireless": {
                    "mode": "sta",  # Station mode for listening
                    "frequency": "5180",  # 5.18 GHz
                    "channel_width": "40",
                    "power": "23",
                    "antenna_gain": "25"
                },
                "network": {
                    "role": "bridge",
                    "management_vlan": "1"
                }
            }
            
            # Send configuration via HTTP API
            response = requests.post(
                config_url,
                json=listening_config,
                auth=(self.powerbeam_user, self.powerbeam_pass),
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("✓ PowerBeam 5AC Gen2 configured to listening mode")
                self.powerbeam_listening = True
                
                # Apply configuration
                apply_url = f"http://{self.powerbeam_ip}/api/system/apply"
                apply_response = requests.post(
                    apply_url,
                    auth=(self.powerbeam_user, self.powerbeam_pass),
                    timeout=10
                )
                
                if apply_response.status_code == 200:
                    logger.info("✓ PowerBeam configuration applied successfully")
                    time.sleep(5)  # Wait for antenna to reconfigure
                    return True
                else:
                    logger.error(f"Failed to apply PowerBeam configuration: {apply_response.status_code}")
                    return False
            else:
                logger.error(f"Failed to configure PowerBeam: {response.status_code}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"PowerBeam communication error: {e}")
            return False
        except Exception as e:
            logger.error(f"PowerBeam configuration error: {e}")
            return False
    
    def start_rocket_video_stream(self) -> bool:
        """Start video streaming from Rocket M5"""
        try:
            logger.info("Starting video stream from Rocket M5...")
            
            # Rocket M5 video stream API endpoint
            stream_url = f"http://{self.rocket_m5_ip}/api/video/start"
            
            # Video streaming configuration
            stream_config = {
                "video": {
                    "resolution": "720p",
                    "framerate": "30",
                    "bitrate": "2000",
                    "encoding": "h264"
                },
                "network": {
                    "protocol": "udp",
                    "destination_ip": self.video_stream_ip,
                    "destination_port": self.video_stream_port
                }
            }
            
            # Start video streaming
            response = requests.post(
                stream_url,
                json=stream_config,
                auth=(self.rocket_user, self.rocket_pass),
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("✓ Rocket M5 video streaming started")
                self.rocket_streaming = True
                return True
            else:
                logger.error(f"Failed to start Rocket M5 video stream: {response.status_code}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Rocket M5 communication error: {e}")
            return False
        except Exception as e:
            logger.error(f"Rocket M5 streaming error: {e}")
            return False
    
    def stop_rocket_video_stream(self) -> bool:
        """Stop video streaming from Rocket M5"""
        try:
            logger.info("Stopping video stream from Rocket M5...")
            
            # Stop video streaming
            stop_url = f"http://{self.rocket_m5_ip}/api/video/stop"
            response = requests.post(
                stop_url,
                auth=(self.rocket_user, self.rocket_pass),
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("✓ Rocket M5 video streaming stopped")
                self.rocket_streaming = False
                return True
            else:
                logger.error(f"Failed to stop Rocket M5 video stream: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error stopping Rocket M5 video stream: {e}")
            return False
    
    def configure_powerbeam_normal_mode(self) -> bool:
        """Configure PowerBeam 5AC Gen2 back to normal mode"""
        try:
            logger.info("Configuring PowerBeam 5AC Gen2 to normal mode...")
            
            config_url = f"http://{self.powerbeam_ip}/api/config"
            
            # Normal mode configuration
            normal_config = {
                "wireless": {
                    "mode": "ap",  # Access Point mode
                    "frequency": "5180",
                    "channel_width": "40",
                    "power": "23",
                    "antenna_gain": "25"
                },
                "network": {
                    "role": "router",
                    "management_vlan": "1"
                }
            }
            
            response = requests.post(
                config_url,
                json=normal_config,
                auth=(self.powerbeam_user, self.powerbeam_pass),
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("✓ PowerBeam 5AC Gen2 configured to normal mode")
                self.powerbeam_listening = False
                
                # Apply configuration
                apply_url = f"http://{self.powerbeam_ip}/api/system/apply"
                apply_response = requests.post(
                    apply_url,
                    auth=(self.powerbeam_user, self.powerbeam_pass),
                    timeout=10
                )
                
                return apply_response.status_code == 200
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error configuring PowerBeam to normal mode: {e}")
            return False
    
    def check_antenna_status(self) -> Dict[str, Any]:
        """Check status of both antennas"""
        status = {
            "powerbeam": {
                "connected": False,
                "listening_mode": False,
                "signal_strength": 0
            },
            "rocket_m5": {
                "connected": False,
                "streaming": False,
                "video_quality": "unknown"
            }
        }
        
        # Check PowerBeam status
        try:
            powerbeam_response = requests.get(
                f"http://{self.powerbeam_ip}/api/status",
                auth=(self.powerbeam_user, self.powerbeam_pass),
                timeout=5
            )
            
            if powerbeam_response.status_code == 200:
                status["powerbeam"]["connected"] = True
                status["powerbeam"]["listening_mode"] = self.powerbeam_listening
                
                # Parse signal strength if available
                pb_data = powerbeam_response.json()
                if "wireless" in pb_data and "signal" in pb_data["wireless"]:
                    status["powerbeam"]["signal_strength"] = pb_data["wireless"]["signal"]
                    
        except Exception as e:
            logger.debug(f"PowerBeam status check failed: {e}")
        
        # Check Rocket M5 status
        try:
            rocket_response = requests.get(
                f"http://{self.rocket_m5_ip}/api/status",
                auth=(self.rocket_user, self.rocket_pass),
                timeout=5
            )
            
            if rocket_response.status_code == 200:
                status["rocket_m5"]["connected"] = True
                status["rocket_m5"]["streaming"] = self.rocket_streaming
                
                # Parse video quality if available
                rocket_data = rocket_response.json()
                if "video" in rocket_data and "quality" in rocket_data["video"]:
                    status["rocket_m5"]["video_quality"] = rocket_data["video"]["quality"]
                    
        except Exception as e:
            logger.debug(f"Rocket M5 status check failed: {e}")
        
        return status
    
    def start_antenna_system(self) -> bool:
        """Start the complete antenna system"""
        try:
            logger.info("Starting antenna system...")
            
            # Step 1: Configure PowerBeam to listening mode
            if not self.configure_powerbeam_listening_mode():
                logger.error("Failed to configure PowerBeam to listening mode")
                return False
            
            # Step 2: Start Rocket M5 video streaming
            if not self.start_rocket_video_stream():
                logger.error("Failed to start Rocket M5 video streaming")
                # Try to revert PowerBeam configuration
                self.configure_powerbeam_normal_mode()
                return False
            
            logger.info("✓ Antenna system started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error starting antenna system: {e}")
            return False
    
    def stop_antenna_system(self) -> bool:
        """Stop the complete antenna system"""
        try:
            logger.info("Stopping antenna system...")
            
            # Stop Rocket M5 video streaming
            rocket_stopped = self.stop_rocket_video_stream()
            
            # Configure PowerBeam back to normal mode
            powerbeam_normal = self.configure_powerbeam_normal_mode()
            
            if rocket_stopped and powerbeam_normal:
                logger.info("✓ Antenna system stopped successfully")
                return True
            else:
                logger.warning("Some antenna components may not have stopped properly")
                return False
                
        except Exception as e:
            logger.error(f"Error stopping antenna system: {e}")
            return False

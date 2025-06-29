"""
Main Computer Vision Module for UAV
Combines YOLO detection with KCF tracking for target identification and tracking.
"""

import cv2
import time
import socket
import threading
import numpy as np
from typing import Optional, Tuple, Dict, Any, List
from pathlib import Path

from ...core.logging_config import get_logger
from ...core.base_classes import BaseModule
from ...core.exceptions import UAVException
from .detection.yolo_detector import YOLODetector
from .tracking.kcf_tracker import KCFTracker

logger = get_logger(__name__)


class ComputerVisionSystem(BaseModule):
    """
    Main computer vision system combining detection and tracking.
    """
    
    def __init__(self, model_path: Optional[str] = None, camera_index: int = 0):
        """
        Initialize the computer vision system.
        
        Args:
            model_path: Path to YOLO model file
            camera_index: Camera device index
        """
        super().__init__()
        
        # Components
        self.detector = None
        self.tracker = None
        self.camera = None
        
        # State
        self.running = False
        self.tracking_active = False
        self.target_bbox = None
        self.target_center = None
        
        # Configuration
        self.camera_index = camera_index
        self.model_path = model_path or self._find_model_file()
        self.frame_width = 640
        self.frame_height = 480
        self.fps = 30
        
        # Network streaming
        self.udp_socket = None
        self.target_ip = "192.168.88.10"
        self.target_port = 5005
        self.stream_active = False
        
        # Performance metrics
        self.fps_counter = 0
        self.fps_start_time = time.time()
        self.current_fps = 0
        
        # Threading
        self.capture_thread = None
        self.processing_thread = None
        
        self.initialize_components()
    
    def _find_model_file(self) -> str:
        """Find the YOLO model file."""
        possible_paths = [
            Path(__file__).parent.parent.parent.parent / "models" / "best.pt",
            Path(__file__).parent / "models" / "best.pt",
            Path("best.pt"),
            Path("models/best.pt")
        ]
        
        for path in possible_paths:
            if path.exists():
                logger.info(f"Found model file: {path}")
                return str(path)
        
        logger.warning("No model file found, using default")
        return "best.pt"
    
    def initialize_components(self):
        """Initialize detection and tracking components."""
        try:
            # Initialize YOLO detector
            self.detector = YOLODetector(model_path=self.model_path)
            logger.info("YOLO detector initialized")
            
            # Initialize KCF tracker
            self.tracker = KCFTracker()
            logger.info("KCF tracker initialized")
            
            # Initialize camera
            self.initialize_camera()
            
            # Initialize UDP socket
            self.initialize_udp()
            
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise UAVException(f"Computer vision initialization failed: {e}")
    
    def initialize_camera(self):
        """Initialize camera capture."""
        try:
            self.camera = cv2.VideoCapture(self.camera_index)
            
            if not self.camera.isOpened():
                raise UAVException(f"Failed to open camera {self.camera_index}")
            
            # Set camera properties
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
            self.camera.set(cv2.CAP_PROP_FPS, self.fps)
            
            logger.info(f"Camera initialized: {self.frame_width}x{self.frame_height} @ {self.fps}fps")
            
        except Exception as e:
            logger.error(f"Camera initialization failed: {e}")
            raise UAVException(f"Camera initialization failed: {e}")
    
    def initialize_udp(self):
        """Initialize UDP socket for streaming."""
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            logger.info(f"UDP socket initialized for {self.target_ip}:{self.target_port}")
            
        except Exception as e:
            logger.error(f"UDP initialization failed: {e}")
    
    def start(self, display_window: bool = True, stream_udp: bool = True):
        """
        Start the computer vision system.
        
        Args:
            display_window: Show video display window
            stream_udp: Stream video over UDP
        """
        try:
            if self.running:
                logger.warning("Computer vision system already running")
                return
            
            self.running = True
            self.stream_active = stream_udp
            
            # Start processing thread
            self.processing_thread = threading.Thread(
                target=self._processing_loop,
                args=(display_window,),
                daemon=True
            )
            self.processing_thread.start()
            
            logger.info("Computer vision system started")
            
        except Exception as e:
            logger.error(f"Failed to start computer vision system: {e}")
            raise UAVException(f"Failed to start computer vision system: {e}")
    
    def stop(self):
        """Stop the computer vision system."""
        try:
            self.running = False
            self.tracking_active = False
            
            # Wait for threads to finish
            if self.processing_thread and self.processing_thread.is_alive():
                self.processing_thread.join(timeout=2)
            
            # Release camera
            if self.camera:
                self.camera.release()
            
            # Close UDP socket
            if self.udp_socket:
                self.udp_socket.close()
            
            # Close display windows
            cv2.destroyAllWindows()
            
            logger.info("Computer vision system stopped")
            
        except Exception as e:
            logger.error(f"Error stopping computer vision system: {e}")
    
    def _processing_loop(self, display_window: bool):
        """Main processing loop."""
        logger.info("Starting processing loop")
        
        while self.running:
            try:
                # Capture frame
                ret, frame = self.camera.read()
                if not ret:
                    logger.warning("Failed to capture frame")
                    time.sleep(0.1)
                    continue
                
                # Process frame
                processed_frame = self._process_frame(frame)
                
                # Display frame
                if display_window:
                    cv2.imshow("HUMA UAV - Computer Vision", processed_frame)
                    
                    # Handle key presses
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        self.running = False
                    elif key == ord('r'):
                        self.reset_tracking()
                    elif key == ord('s'):
                        self.start_tracking()
                
                # Stream frame via UDP
                if self.stream_active:
                    self._stream_frame(processed_frame)
                
                # Update FPS counter
                self._update_fps_counter()
                
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                time.sleep(0.1)
    
    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Process a single frame with detection and tracking.
        
        Args:
            frame: Input frame
            
        Returns:
            Processed frame with annotations
        """
        try:
            processed_frame = frame.copy()
            
            # Draw target area
            processed_frame = self._draw_target_area(processed_frame)
            
            # Detection phase
            if not self.tracking_active:
                detections = self.detector.detect(frame)
                
                if detections:
                    # Get best detection
                    best_detection = max(detections, key=lambda x: x['confidence'])
                    
                    if best_detection['confidence'] > 0.5:  # Confidence threshold
                        bbox = best_detection['bbox']
                        self.target_bbox = bbox
                        
                        # Initialize tracker
                        if self.tracker.initialize(frame, bbox):
                            self.tracking_active = True
                            self.target_center = self._get_bbox_center(bbox)
                            logger.info(f"Tracking started with confidence: {best_detection['confidence']:.2f}")
                        
                        # Draw detection
                        processed_frame = self._draw_detection(processed_frame, best_detection)
            
            # Tracking phase
            else:
                success, bbox = self.tracker.update(frame)
                
                if success:
                    self.target_bbox = bbox
                    self.target_center = self._get_bbox_center(bbox)
                    
                    # Draw tracking
                    processed_frame = self._draw_tracking(processed_frame, bbox)
                    
                    # Send target information via UDP
                    if self.stream_active:
                        self._send_target_info(self.target_center, bbox)
                        
                else:
                    # Tracking lost
                    self.tracking_active = False
                    self.target_bbox = None
                    self.target_center = None
                    logger.warning("Tracking lost")
            
            # Draw status information
            processed_frame = self._draw_status(processed_frame)
            
            return processed_frame
            
        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            return frame
    
    def _draw_target_area(self, frame: np.ndarray) -> np.ndarray:
        """Draw target area on frame."""
        h, w = frame.shape[:2]
        
        # Target area (yellow rectangle)
        x1 = int(w * 0.25)
        y1 = int(h * 0.10)
        x2 = int(w * 0.75)
        y2 = int(h * 0.90)
        
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
        
        # Label
        text = "AV: Hedef Vurus Alani"
        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
        text_x = x1 + (x2 - x1 - text_size[0]) // 2
        cv2.putText(frame, text, (text_x, y2 - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        
        return frame
    
    def _draw_detection(self, frame: np.ndarray, detection: Dict[str, Any]) -> np.ndarray:
        """Draw detection on frame."""
        bbox = detection['bbox']
        confidence = detection['confidence']
        class_name = detection.get('class', 'object')
        
        x1, y1, x2, y2 = map(int, bbox)
        
        # Draw bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # Draw label
        label = f"{class_name}: {confidence:.2f}"
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
        cv2.rectangle(frame, (x1, y1 - label_size[1] - 10), 
                     (x1 + label_size[0], y1), (0, 255, 0), -1)
        cv2.putText(frame, label, (x1, y1 - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        
        return frame
    
    def _draw_tracking(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> np.ndarray:
        """Draw tracking on frame."""
        x1, y1, x2, y2 = map(int, bbox)
        
        # Draw tracking box (red)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
        
        # Draw center point
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        cv2.circle(frame, (center_x, center_y), 5, (0, 0, 255), -1)
        
        # Draw tracking label
        label = "TRACKING"
        cv2.putText(frame, label, (x1, y1 - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        
        return frame
    
    def _draw_status(self, frame: np.ndarray) -> np.ndarray:
        """Draw status information on frame."""
        # FPS
        fps_text = f"FPS: {self.current_fps:.1f}"
        cv2.putText(frame, fps_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Status
        status = "TRACKING" if self.tracking_active else "DETECTING"
        status_color = (0, 0, 255) if self.tracking_active else (0, 255, 0)
        cv2.putText(frame, status, (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        
        # Target center coordinates
        if self.target_center:
            center_text = f"Target: ({self.target_center[0]}, {self.target_center[1]})"
            cv2.putText(frame, center_text, (10, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return frame
    
    def _get_bbox_center(self, bbox: Tuple[int, int, int, int]) -> Tuple[int, int]:
        """Get center point of bounding box."""
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)
    
    def _stream_frame(self, frame: np.ndarray):
        """Stream frame via UDP."""
        try:
            # Encode frame
            _, encoded_frame = cv2.imencode('.jpg', frame, 
                                          [cv2.IMWRITE_JPEG_QUALITY, 80])
            
            # Send via UDP (split into chunks if needed)
            data = encoded_frame.tobytes()
            if len(data) < 65000:  # Max UDP packet size
                self.udp_socket.sendto(data, (self.target_ip, self.target_port))
            
        except Exception as e:
            logger.error(f"Error streaming frame: {e}")
    
    def _send_target_info(self, center: Tuple[int, int], bbox: Tuple[int, int, int, int]):
        """Send target information via UDP."""
        try:
            if not center:
                return
            
            # Create target info message
            message = f"TARGET:{center[0]},{center[1]},{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
            
            self.udp_socket.sendto(message.encode(), (self.target_ip, self.target_port + 1))
            
        except Exception as e:
            logger.error(f"Error sending target info: {e}")
    
    def _update_fps_counter(self):
        """Update FPS counter."""
        self.fps_counter += 1
        
        if time.time() - self.fps_start_time >= 1.0:
            self.current_fps = self.fps_counter
            self.fps_counter = 0
            self.fps_start_time = time.time()
    
    def start_tracking(self):
        """Manually start tracking on detected object."""
        if not self.tracking_active and self.target_bbox:
            # Get current frame
            ret, frame = self.camera.read()
            if ret and self.tracker.initialize(frame, self.target_bbox):
                self.tracking_active = True
                logger.info("Manual tracking started")
    
    def reset_tracking(self):
        """Reset tracking."""
        self.tracking_active = False
        self.target_bbox = None
        self.target_center = None
        logger.info("Tracking reset")
    
    def get_target_info(self) -> Optional[Dict[str, Any]]:
        """
        Get current target information.
        
        Returns:
            Target information dictionary
        """
        if not self.target_center or not self.target_bbox:
            return None
        
        return {
            'center': self.target_center,
            'bbox': self.target_bbox,
            'tracking': self.tracking_active,
            'timestamp': time.time()
        }
    
    def __del__(self):
        """Cleanup on destruction."""
        self.stop()

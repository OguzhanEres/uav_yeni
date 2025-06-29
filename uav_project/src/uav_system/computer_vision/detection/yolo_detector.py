"""
Enhanced YOLO object detector.
"""

import os
import pathlib
import sys
from typing import Any, Dict, List, Optional
import torch
import numpy as np
import cv2

from ..base_detector import BaseDetector
from ...core.exceptions import ComputerVisionError
from ...core.logging_config import get_logger

logger = get_logger(__name__)


class YOLODetector(BaseDetector):
    """YOLO-based object detector with enhanced error handling."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("YOLODetector", config)
        self.model_path = config.get('model_path') if config else None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.class_names = {}
        
    def initialize(self) -> bool:
        """Initialize the YOLO detector."""
        try:
            success = self.load_model(self.model_path)
            if success:
                self._initialized = True
                self.logger.info(f"YOLO detector initialized on {self.device}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to initialize YOLO detector: {e}")
            return False
    
    def start(self) -> bool:
        """Start the YOLO detector."""
        if not self._initialized:
            return False
        self._running = True
        return True
    
    def stop(self) -> bool:
        """Stop the YOLO detector."""
        self._running = False
        return True
    
    def cleanup(self) -> bool:
        """Clean up YOLO detector resources."""
        try:
            if self.model:
                del self.model
                torch.cuda.empty_cache() if torch.cuda.is_available() else None
            self._initialized = False
            self.logger.info("YOLO detector cleaned up")
            return True
        except Exception as e:
            self.logger.error(f"Failed to cleanup YOLO detector: {e}")
            return False
    
    def load_model(self, model_path: Optional[str] = None) -> bool:
        """Load YOLO model."""
        try:
            # Windows pathlib compatibility fix
            if sys.platform == "win32":
                temp = pathlib.PosixPath
                pathlib.PosixPath = pathlib.WindowsPath
            
            if model_path and os.path.exists(model_path):
                # Load custom model
                self.logger.info(f"Loading custom model from: {model_path}")
                self.model = torch.hub.load(
                    'ultralytics/yolov5', 
                    'custom', 
                    path=model_path, 
                    device=self.device, 
                    force_reload=True
                )
                self.logger.info("Custom YOLO model loaded successfully")
            else:
                # Load default model
                self.logger.info("Loading default YOLOv5n model")
                self.model = torch.hub.load(
                    'ultralytics/yolov5', 
                    'yolov5n', 
                    pretrained=True
                ).to(self.device)
                self.logger.info("Default YOLO model loaded successfully")
            
            # Restore pathlib if modified
            if sys.platform == "win32":
                pathlib.PosixPath = temp
            
            # Set confidence threshold
            self.model.conf = self.confidence_threshold
            
            # Get class names
            self.class_names = self.model.names if hasattr(self.model, 'names') else {}
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load YOLO model: {e}")
            if sys.platform == "win32":
                pathlib.PosixPath = temp
            return False
    
    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect objects in the frame.
        
        Args:
            frame: Input image frame (BGR format)
            
        Returns:
            List of detections with bbox, confidence, and class information
        """
        if not self._initialized or not self.model:
            raise ComputerVisionError("YOLO detector not initialized")
        
        try:
            # Preprocess frame
            processed_frame = self.preprocess_frame(frame)
            
            # Run inference
            results = self.model(processed_frame)
            
            # Parse results
            detections = []
            if len(results.xyxy[0]) > 0:
                for detection in results.xyxy[0].cpu().numpy():
                    x1, y1, x2, y2, confidence, class_id = detection
                    
                    # Filter by confidence
                    if confidence >= self.confidence_threshold:
                        bbox = {
                            'x': int(x1),
                            'y': int(y1),
                            'w': int(x2 - x1),
                            'h': int(y2 - y1)
                        }
                        
                        detection_dict = {
                            'bbox': bbox,
                            'confidence': float(confidence),
                            'class_id': int(class_id),
                            'class_name': self.class_names.get(int(class_id), f"class_{int(class_id)}")
                        }
                        detections.append(detection_dict)
            
            return self.postprocess_detections(detections)
            
        except Exception as e:
            self.logger.error(f"Detection failed: {e}")
            return []
    
    def detect_single_object(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Detect single object (highest confidence) in frame.
        
        Args:
            frame: Input image frame
            
        Returns:
            Single detection or None
        """
        detections = self.detect(frame)
        if detections:
            # Return detection with highest confidence
            return max(detections, key=lambda x: x['confidence'])
        return None
    
    def detect_bbox_format(self, frame: np.ndarray) -> Optional[tuple]:
        """
        Detect single object and return in (x, y, w, h) format for compatibility.
        
        Args:
            frame: Input image frame
            
        Returns:
            Tuple (x, y, w, h) or None
        """
        detection = self.detect_single_object(frame)
        if detection:
            bbox = detection['bbox']
            return (bbox['x'], bbox['y'], bbox['w'], bbox['h'])
        return None
    
    def set_confidence_threshold(self, threshold: float) -> None:
        """Set confidence threshold."""
        self.confidence_threshold = max(0.0, min(1.0, threshold))
        if self.model:
            self.model.conf = self.confidence_threshold
        self.logger.info(f"Confidence threshold set to {self.confidence_threshold}")
    
    def preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """Preprocess frame for YOLO (can be overridden for specific needs)."""
        # YOLO expects RGB, OpenCV uses BGR
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return frame
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        if not self.model:
            return {}
        
        return {
            'device': self.device,
            'confidence_threshold': self.confidence_threshold,
            'class_names': self.class_names,
            'num_classes': len(self.class_names),
            'model_type': type(self.model).__name__
        }
    
    def draw_detections(self, frame: np.ndarray, detections: List[Dict[str, Any]], 
                       draw_confidence: bool = True, draw_class: bool = True) -> np.ndarray:
        """
        Draw detections on frame.
        
        Args:
            frame: Input frame
            detections: List of detections
            draw_confidence: Whether to draw confidence scores
            draw_class: Whether to draw class names
            
        Returns:
            Frame with drawn detections
        """
        result_frame = frame.copy()
        
        for detection in detections:
            bbox = detection['bbox']
            confidence = detection['confidence']
            class_name = detection['class_name']
            
            # Draw bounding box
            cv2.rectangle(
                result_frame,
                (bbox['x'], bbox['y']),
                (bbox['x'] + bbox['w'], bbox['y'] + bbox['h']),
                (0, 255, 0), 2
            )
            
            # Prepare label
            label_parts = []
            if draw_class:
                label_parts.append(class_name)
            if draw_confidence:
                label_parts.append(f"{confidence:.2f}")
            
            if label_parts:
                label = " ".join(label_parts)
                cv2.putText(
                    result_frame, label,
                    (bbox['x'], bbox['y'] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1
                )
        
        return result_frame

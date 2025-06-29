"""
Base classes for computer vision components.
"""

import abc
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from ..core.base_classes import BaseComponent


class BaseDetector(BaseComponent):
    """Base class for object detection components."""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.confidence_threshold = config.get('confidence_threshold', 0.5) if config else 0.5
        self.model = None
        self.device = "cpu"
    
    @abc.abstractmethod
    def load_model(self, model_path: Optional[str] = None) -> bool:
        """Load the detection model."""
        pass
    
    @abc.abstractmethod
    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect objects in the frame.
        
        Args:
            frame: Input image frame
            
        Returns:
            List of detections with bbox, confidence, and class information
        """
        pass
    
    @abc.abstractmethod
    def set_confidence_threshold(self, threshold: float) -> None:
        """Set the confidence threshold for detections."""
        pass
    
    def preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """Preprocess frame before detection (can be overridden)."""
        return frame
    
    def postprocess_detections(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Postprocess detections (can be overridden)."""
        return detections


class BaseTracker(BaseComponent):
    """Base class for object tracking components."""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.initialized = False
        self.tracking = False
        self.current_bbox = None
        self.template = None
    
    @abc.abstractmethod
    def init_tracker(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> bool:
        """
        Initialize tracker with first frame and bounding box.
        
        Args:
            frame: Initial frame
            bbox: Initial bounding box (x, y, w, h)
            
        Returns:
            Success status
        """
        pass
    
    @abc.abstractmethod
    def update_tracker(self, frame: np.ndarray) -> Tuple[bool, Optional[Tuple[int, int, int, int]]]:
        """
        Update tracker with new frame.
        
        Args:
            frame: New frame
            
        Returns:
            Tuple of (success, bbox) where bbox is (x, y, w, h)
        """
        pass
    
    @abc.abstractmethod
    def reset_tracker(self) -> bool:
        """Reset tracker state."""
        pass
    
    def is_tracking(self) -> bool:
        """Check if tracker is actively tracking."""
        return self.tracking and self.initialized
    
    def get_current_bbox(self) -> Optional[Tuple[int, int, int, int]]:
        """Get current bounding box."""
        return self.current_bbox

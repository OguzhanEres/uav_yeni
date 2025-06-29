"""
Enhanced KCF-based tracker implementation.
"""

from typing import Dict, Any, Optional, Tuple
import cv2
import numpy as np

from ..base_detector import BaseTracker
from ...core.exceptions import ComputerVisionError
from ...core.logging_config import get_logger

logger = get_logger(__name__)


class KCFTracker(BaseTracker):
    """Enhanced KCF-like tracker with improved robustness."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("KCFTracker", config)
        self.template = None
        self.search_factor = config.get('search_factor', 1.5) if config else 1.5
        self.template_update_rate = config.get('template_update_rate', 0.2) if config else 0.2
        self.confidence_threshold = config.get('confidence_threshold', 0.3) if config else 0.3
        self.high_confidence_threshold = config.get('high_confidence_threshold', 0.7) if config else 0.7
        self.max_template_age = config.get('max_template_age', 50) if config else 50
        self.template_age = 0
        self.last_confidence = 0.0
        self.lost_track_count = 0
        self.max_lost_frames = config.get('max_lost_frames', 5) if config else 5
    
    def initialize(self) -> bool:
        """Initialize the KCF tracker."""
        try:
            self.reset_tracker()
            self._initialized = True
            self.logger.info("KCF tracker initialized")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize KCF tracker: {e}")
            return False
    
    def start(self) -> bool:
        """Start the KCF tracker."""
        if not self._initialized:
            return False
        self._running = True
        return True
    
    def stop(self) -> bool:
        """Stop the KCF tracker."""
        self._running = False
        self.tracking = False
        return True
    
    def cleanup(self) -> bool:
        """Clean up KCF tracker resources."""
        try:
            self.reset_tracker()
            self._initialized = False
            self.logger.info("KCF tracker cleaned up")
            return True
        except Exception as e:
            self.logger.error(f"Failed to cleanup KCF tracker: {e}")
            return False
    
    def init_tracker(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> bool:
        """
        Initialize tracker with first frame and bounding box.
        
        Args:
            frame: Initial frame (grayscale or BGR)
            bbox: Initial bounding box (x, y, w, h)
            
        Returns:
            Success status
        """
        try:
            # Validate and correct bbox
            corrected_bbox = self._validate_bbox(frame, bbox)
            if corrected_bbox is None:
                self.logger.error("Invalid bounding box provided")
                return False
            
            x, y, w, h = corrected_bbox
            
            # Convert to grayscale if needed
            if len(frame.shape) == 3:
                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray_frame = frame
            
            # Extract template
            self.template = gray_frame[y:y+h, x:x+w].copy()
            
            if self.template.size == 0:
                self.logger.error("Empty template extracted")
                return False
            
            self.current_bbox = corrected_bbox
            self.initialized = True
            self.tracking = True
            self.template_age = 0
            self.lost_track_count = 0
            self.last_confidence = 1.0
            
            self.logger.info(f"Tracker initialized with bbox: {corrected_bbox}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize tracker: {e}")
            return False
    
    def update_tracker(self, frame: np.ndarray) -> Tuple[bool, Optional[Tuple[int, int, int, int]]]:
        """
        Update tracker with new frame.
        
        Args:
            frame: New frame
            
        Returns:
            Tuple of (success, bbox) where bbox is (x, y, w, h)
        """
        if not self.initialized or not self.tracking or self.template is None:
            return False, None
        
        try:
            # Convert to grayscale if needed
            if len(frame.shape) == 3:
                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray_frame = frame
            
            x, y, w, h = self.current_bbox
            
            # Define search region
            search_w = int(w * self.search_factor)
            search_h = int(h * self.search_factor)
            
            # Calculate search boundaries
            search_x = max(0, x - (search_w - w) // 2)
            search_y = max(0, y - (search_h - h) // 2)
            search_x2 = min(frame.shape[1], search_x + search_w)
            search_y2 = min(frame.shape[0], search_y + search_h)
            
            # Extract search region
            search_region = gray_frame[search_y:search_y2, search_x:search_x2]
            
            if search_region.shape[0] < h or search_region.shape[1] < w:
                self.lost_track_count += 1
                if self.lost_track_count > self.max_lost_frames:
                    self.tracking = False
                    self.logger.warning("Tracking lost: search region too small")
                return False, self.current_bbox
            
            # Template matching
            result = cv2.matchTemplate(search_region, self.template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            
            self.last_confidence = max_val
            
            # Check if match quality is sufficient
            if max_val < self.confidence_threshold:
                self.lost_track_count += 1
                if self.lost_track_count > self.max_lost_frames:
                    self.tracking = False
                    self.logger.warning(f"Tracking lost: low confidence ({max_val:.3f})")
                return False, self.current_bbox
            
            # Reset lost track counter on successful tracking
            self.lost_track_count = 0
            
            # Update bbox position
            new_x = search_x + max_loc[0]
            new_y = search_y + max_loc[1]
            self.current_bbox = (new_x, new_y, w, h)
            
            # Update template if confidence is high and template is not too old
            if (max_val > self.high_confidence_threshold and 
                self.template_age < self.max_template_age):
                self._update_template(gray_frame, new_x, new_y, w, h)
            
            self.template_age += 1
            
            return True, self.current_bbox
            
        except Exception as e:
            self.logger.error(f"Tracker update failed: {e}")
            self.lost_track_count += 1
            return False, self.current_bbox
    
    def reset_tracker(self) -> bool:
        """Reset tracker state."""
        try:
            self.template = None
            self.current_bbox = None
            self.initialized = False
            self.tracking = False
            self.template_age = 0
            self.last_confidence = 0.0
            self.lost_track_count = 0
            self.logger.info("Tracker reset")
            return True
        except Exception as e:
            self.logger.error(f"Failed to reset tracker: {e}")
            return False
    
    def _validate_bbox(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> Optional[Tuple[int, int, int, int]]:
        """Validate and correct bounding box."""
        if len(bbox) != 4:
            return None
        
        x, y, w, h = bbox
        frame_h, frame_w = frame.shape[:2]
        
        # Correct negative values
        x = max(0, int(x))
        y = max(0, int(y))
        w = max(1, int(w))
        h = max(1, int(h))
        
        # Ensure bbox is within frame boundaries
        x = min(x, frame_w - 1)
        y = min(y, frame_h - 1)
        w = min(w, frame_w - x)
        h = min(h, frame_h - y)
        
        # Check minimum size
        if w < 10 or h < 10:
            self.logger.warning(f"Bounding box too small: {w}x{h}")
            return None
        
        return (x, y, w, h)
    
    def _update_template(self, frame: np.ndarray, x: int, y: int, w: int, h: int):
        """Update template with current region."""
        try:
            new_template = frame[y:y+h, x:x+w]
            if (new_template.shape[:2] == self.template.shape[:2] and 
                new_template.size > 0):
                # Blend old and new template
                self.template = cv2.addWeighted(
                    self.template, 
                    1.0 - self.template_update_rate,
                    new_template, 
                    self.template_update_rate, 
                    0
                )
                self.template_age = 0  # Reset age after update
        except Exception as e:
            self.logger.warning(f"Template update failed: {e}")
    
    def get_tracking_info(self) -> Dict[str, Any]:
        """Get detailed tracking information."""
        return {
            'tracking': self.tracking,
            'initialized': self.initialized,
            'current_bbox': self.current_bbox,
            'last_confidence': self.last_confidence,
            'template_age': self.template_age,
            'lost_track_count': self.lost_track_count,
            'search_factor': self.search_factor,
            'confidence_threshold': self.confidence_threshold
        }
    
    def set_search_factor(self, factor: float):
        """Set search region factor."""
        self.search_factor = max(1.1, min(3.0, factor))
        self.logger.info(f"Search factor set to {self.search_factor}")
    
    def set_confidence_threshold(self, threshold: float):
        """Set confidence threshold."""
        self.confidence_threshold = max(0.1, min(0.9, threshold))
        self.logger.info(f"Confidence threshold set to {self.confidence_threshold}")


def create_kcf_tracker(config: Optional[Dict[str, Any]] = None) -> KCFTracker:
    """Factory function to create KCF tracker."""
    return KCFTracker(config)


def init_tracker(tracker: KCFTracker, frame: np.ndarray, 
                 init_bbox: Tuple[int, int, int, int]) -> KCFTracker:
    """
    Initialize tracker with validation (compatibility function).
    
    Args:
        tracker: KCF tracker instance
        frame: Initial frame
        init_bbox: Initial bounding box (x, y, w, h)
        
    Returns:
        Initialized tracker
    """
    success = tracker.init_tracker(frame, init_bbox)
    if not success:
        logger.error("Failed to initialize tracker")
    return tracker


def update_tracker(tracker: KCFTracker, frame: np.ndarray) -> Tuple[bool, Optional[Tuple[int, int, int, int]]]:
    """
    Update tracker (compatibility function).
    
    Args:
        tracker: KCF tracker instance
        frame: New frame
        
    Returns:
        Tuple of (success, bbox)
    """
    return tracker.update_tracker(frame)

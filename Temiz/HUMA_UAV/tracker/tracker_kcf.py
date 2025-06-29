import cv2
import numpy as np

class SimpleKCFLikeTracker:
    def __init__(self):
        self.template = None
        self.bbox = None
        self.initialized = False
    
    def init(self, frame, bbox):
        x, y, w, h = [int(v) for v in bbox]
        if w <= 0 or h <= 0 or x < 0 or y < 0:
            return False
        
        # Extract template from initial bbox
        self.template = frame[y:y+h, x:x+w].copy()
        self.bbox = bbox
        self.initialized = True
        return True
    
    def update(self, frame):
        if not self.initialized or self.template is None:
            return False, None
        
        x, y, w, h = [int(v) for v in self.bbox]
        
        # Define search region (slightly larger than current bbox)
        search_factor = 1.5
        search_w = int(w * search_factor)
        search_h = int(h * search_factor)
        
        # Calculate search region boundaries
        search_x = max(0, x - (search_w - w) // 2)
        search_y = max(0, y - (search_h - h) // 2)
        search_x2 = min(frame.shape[1], search_x + search_w)
        search_y2 = min(frame.shape[0], search_y + search_h)
        
        # Extract search region
        search_region = frame[search_y:search_y2, search_x:search_x2]
        
        if search_region.shape[0] < h or search_region.shape[1] < w:
            return False, None
        
        # Template matching
        result = cv2.matchTemplate(search_region, self.template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        
        # If match quality is too low, tracking failed
        if max_val < 0.3:
            return False, None
        
        # Update bbox position
        new_x = search_x + max_loc[0]
        new_y = search_y + max_loc[1]
        self.bbox = (new_x, new_y, w, h)
        
        # Update template with current region for adaptation
        if max_val > 0.7:  # Only update if very confident
            new_template = frame[new_y:new_y+h, new_x:new_x+w]
            if new_template.shape[:2] == self.template.shape[:2]:
                # Blend old and new template
                self.template = cv2.addWeighted(self.template, 0.8, new_template, 0.2, 0)
        
        return True, self.bbox

def create_kcf_tracker():
    """Create a KCF-like tracker using template matching"""
    print("Using custom KCF-like tracker (template matching based)")
    return SimpleKCFLikeTracker()

def init_tracker(tracker, frame, init_bbox):
    # bbox formatını kontrol edelim ve düzeltelim
    if len(init_bbox) == 4:
        x, y, w, h = init_bbox
        # Negatif değerleri düzeltelim
        x = max(0, x)
        y = max(0, y)
        w = max(1, w)  # En az 1 piksel genişlik
        h = max(1, h)  # En az 1 piksel yükseklik
        
        # Frame sınırlarını kontrol edelim
        frame_h, frame_w = frame.shape[:2]
        x = min(x, frame_w - 1)
        y = min(y, frame_h - 1)
        w = min(w, frame_w - x)
        h = min(h, frame_h - y)
        
        corrected_bbox = (x, y, w, h)
        print(f"Initializing tracker with bbox: {corrected_bbox}")
        success = tracker.init(frame, corrected_bbox)
        
        if not success:
            print("Tracker initialization failed!")
        else:
            print("KCF-like tracker initialized successfully!")
        return tracker
    else:
        raise ValueError(f"Invalid bbox format: {init_bbox}")

def update_tracker(tracker, frame):
    try:
        return tracker.update(frame)
    except Exception as e:
        print(f"Tracker update failed: {e}")
        return False, None

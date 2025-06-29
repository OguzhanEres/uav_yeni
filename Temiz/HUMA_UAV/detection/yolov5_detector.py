import torch
import os
import pathlib
import sys

def load_yolov5_model(device="cpu"):
    # Windows pathlib patch for PosixPath compatibility
    if sys.platform == "win32":
        temp = pathlib.PosixPath
        pathlib.PosixPath = pathlib.WindowsPath
    
    # Custom model path - using the best.pt in HUMA_UAV folder
    model_path = os.path.join(os.path.dirname(__file__), '..', 'best.pt')
    model_path = os.path.abspath(model_path)
    
    if os.path.exists(model_path):
        try:
            # Load custom trained model with force_reload to avoid cache issues
            model = torch.hub.load('ultralytics/yolov5', 'custom', path=model_path, device=device, force_reload=True)
            print(f"Custom model loaded from: {model_path}")
        except Exception as e:
            print(f"Error loading custom model: {e}")
            print("Using default YOLOv5n model instead")
            model = torch.hub.load('ultralytics/yolov5', 'yolov5n', pretrained=True).to(device)
    else:
        # Fallback to default model if custom model not found
        model = torch.hub.load('ultralytics/yolov5', 'yolov5n', pretrained=True).to(device)
        print(f"Custom model not found at: {model_path}")
        print("Using default YOLOv5n model")
    
    # Restore original PosixPath if we changed it
    if sys.platform == "win32":
        pathlib.PosixPath = temp
    
    return model

def detect_object(model, frame):
    results = model(frame)
    if results.xyxy[0].shape[0] > 0:
        bbox = results.xyxy[0][0][:4].tolist()  # [x1, y1, x2, y2]
        x = int(bbox[0])
        y = int(bbox[1])
        w = int(bbox[2] - bbox[0])
        h = int(bbox[3] - bbox[1])
        return (x, y, w, h)
    else:
        return None

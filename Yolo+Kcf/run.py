import pathlib
import sys

if sys.platform.startswith('win'):
    pathlib.PosixPath = pathlib.WindowsPath

import numpy as np
import cv2
import torch
from time import time
import kcftracker
import os
import yolov5

def load_yolo_model():
    model_path = 'C:\\Users\\erolo\\Desktop\\UAV_Arayuz\\Yolo+Kcf\\best.pt'  
    if not os.path.exists(model_path):
        print(f"[HATA] Model dosyası bulunamadı: {model_path}")
        sys.exit(1)
    try:
        model = yolov5.load(model_path)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model.to(device)
        print(f"YOLO: {str(device).upper()} | KCF: CPU")
        return model, device
    except Exception as e:
        print(f"[HATA] YOLO modeli yüklenemedi: {e}")
        sys.exit(1)

def detect_objects_yolo(model, device, frame, confidence_threshold=0.5):
    results = model(frame)
    detections = []
    
    # YOLOv5 results format
    for *xyxy, conf, cls in results.xyxy[0].cpu().numpy():
        if conf >= confidence_threshold:
            x1, y1, x2, y2 = map(int, xyxy)
            bbox = [x1, y1, x2-x1, y2-y1]
            detections.append({'bbox': bbox, 'confidence': float(conf), 'class': int(cls)})
    
    return detections

def start_kcf_tracker(frame, bbox):
    tracker = kcftracker.KCFTracker(True, True, True)
    tracker.init(bbox, frame)
    return tracker

if __name__ == '__main__':
    yolo_model, yolo_device = load_yolo_model()
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[HATA] Kamera açılamadı!")
        sys.exit(1)

    frame_counter = 0
    tracker = None
    tracking = False
    bbox = None
    confidence_threshold = 0.5
    fps = 0
    duration = 0.01

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("[HATA] Kamera verisi alınamıyor!")
            break
        t0 = time()

        if not tracking:
            detections = detect_objects_yolo(yolo_model, yolo_device, frame, confidence_threshold)
            if len(detections) > 0:
                obj = detections[0]
                bbox = obj['bbox']
                last_detection = obj
                tracker = start_kcf_tracker(frame, bbox)
                tracking = True
                frame_counter = 0
                cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[0]+bbox[2], bbox[1]+bbox[3]), (0,255,0), 2)
        else:
            bbox_kcf = tracker.update(frame)
            bbox_kcf = list(map(int, bbox_kcf))
            cv2.rectangle(frame, (bbox_kcf[0], bbox_kcf[1]), (bbox_kcf[0]+bbox_kcf[2], bbox_kcf[1]+bbox_kcf[3]), (255,0,0), 2)
            cv2.putText(frame, "KCF Takip", (bbox_kcf[0], bbox_kcf[1]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,0,0), 2)
            
            frame_counter += 1
            t1 = time()
            duration = 0.8 * duration + 0.2 * (t1 - t0)
            fps = 1.0 / duration if duration > 0 else 0
            if frame_counter >= 15:
                detections = detect_objects_yolo(yolo_model, yolo_device, frame, confidence_threshold)
                if len(detections) > 0:
                    obj = detections[0]
                    bbox = obj['bbox']
                    last_detection = obj
                    tracker = start_kcf_tracker(frame, bbox)
                    frame_counter = 0
                else:
                    tracking = False
                    tracker = None
                    bbox = None
                    frame_counter = 0

        fps_text = f"FPS: {fps:.1f}"
        cv2.putText(frame, fps_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        cv2.imshow('YOLO + KCF Otomatik Takip', frame)
        c = cv2.waitKey(1) & 0xFF
        if c == 27 or c == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
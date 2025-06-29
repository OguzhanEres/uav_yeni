import cv2
import sys
import time
import torch
import os
import numpy as np
import socket
import argparse

from detection.yolov5_detector import load_yolov5_model, detect_object
from tracker.tracker_kcf import create_kcf_tracker, init_tracker, update_tracker

# ————— UDP AYARLARI —————
TARGET_IP   = "192.168.88.10"   # Alıcı PC'nin IP'si
TARGET_PORT = 5005              # Alıcı portu
UDP_SOCK    = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# ————————————————————————

def draw_target_area(frame):
    h, w = frame.shape[:2]
    yellow_x1 = int(w * 0.25)
    yellow_y1 = int(h * 0.10)
    yellow_x2 = int(w * 0.75)
    yellow_y2 = int(h * 0.90)
    cv2.rectangle(frame, (yellow_x1, yellow_y1), (yellow_x2, yellow_y2), (0, 255, 255), 2)
    av_text = "AV: Hedef Vurus Alani"
    av_size = cv2.getTextSize(av_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
    av_x = yellow_x1 + (yellow_x2 - yellow_x1 - av_size[0]) // 2
    cv2.putText(frame, av_text, (av_x, yellow_y2 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    return frame

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='HUMA UAV Camera System')
    parser.add_argument('--no-display', action='store_true', 
                       help='Run in background without displaying video window')
    parser.add_argument('--display-only', action='store_true',
                       help='Only display video stream from UDP source')
    args = parser.parse_args()
    
    # Initialize camera or UDP stream
    if args.display_only:
        # For display-only mode, read from UDP stream
        cap = cv2.VideoCapture('udp://localhost:11111')  # Adjust port as needed
    else:
        # Normal camera initialization
        print("Webcam açılıyor...")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Webcam açılamadı, video dosyası kullanılacak")
            video_path = '/home/oguzhan/Desktop/Temiz/HUMA_UAV/kamera3.mp4'
            if os.path.exists(video_path):
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    print(f"Video dosyası açılamadı: {video_path}")
                    sys.exit(1)
                print(f"Video dosyası açıldı: {video_path}")
            else:
                print("Video dosyası bulunamadı!")
                sys.exit(1)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = load_yolov5_model(device)

    ok, frame = cap.read()
    if not ok:
        print("Videodan kare okunamadı!")
        cap.release()
        sys.exit(1)

    frame = cv2.resize(frame, (640, 480))
    init_bbox = detect_object(model, frame)
    if init_bbox is None:
        h, w = frame.shape[:2]
        init_bbox = [w//4, h//4, w//2, h//2]

    init_w, init_h = init_bbox[2], init_bbox[3]
    tracker = create_kcf_tracker()
    tracker = init_tracker(tracker, frame, init_bbox)

    detection_interval = 15
    frame_count = 0
    last_region = None
    first_print = True
    paused = False
    last_frame = frame.copy()

    print("\nKontroller:")
    print("  Space: Video akışını duraklat/devam ettir")
    print("  R: Manuel nesne tespiti yap")
    print("  ESC: Programdan çık")

    while True:
        if not paused:
            ok, frame = cap.read()
            if not ok:
                print("Video sona erdi")
                break
            frame = cv2.resize(frame, (640, 480))
            last_frame = frame.copy()
            frame_count += 1
            t0 = time.time()

            if frame_count % detection_interval == 0:
                new_bbox = detect_object(model, frame)
                if new_bbox is not None:
                    init_bbox = new_bbox
                    init_w, init_h = init_bbox[2], init_bbox[3]
                    tracker = create_kcf_tracker()
                    tracker = init_tracker(tracker, frame, init_bbox)
                    cv2.putText(frame, "Detection", (init_bbox[0], init_bbox[1]-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)
                    cv2.rectangle(frame, (init_bbox[0], init_bbox[1]),
                                  (init_bbox[0]+init_bbox[2], init_bbox[1]+init_bbox[3]),
                                  (0,255,0), 2)

            ok, bbox_ret = update_tracker(tracker, frame)
            if ok:
                x, y, w_ret, h_ret = [int(v) for v in bbox_ret]
                cx, cy = x + w_ret//2, y + h_ret//2
                nx, ny = cx - init_w//2, cy - init_h//2
                frame = draw_target_area(frame)
                cv2.rectangle(frame, (nx, ny), (nx+init_w, ny+init_h), (255,0,0), 2)
                cv2.putText(frame, "Tracking", (nx, ny-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,0,0), 2)

                # ROI bölge hesaplama ve yazdırma...
                # (Mevcut koddaki bölge hesaplama kısmını aynen buraya ekleyebilirsiniz.)

            else:
                frame = draw_target_area(frame)
                cv2.putText(frame, "Tracking failure detected", (100,80),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0,0,255), 2)

            fps = 1.0 / (time.time() - t0)

        else:
            frame = last_frame.copy()
            frame = draw_target_area(frame)
            cv2.putText(frame, "PAUSED", (frame.shape[1]//2-60, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0,0,255), 2)

        # ————— Buraya UDP yayın bloğu eklenir —————
        try:
            _, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
            data = buf.tobytes()
            for i in range(0, len(data), 30000):
                UDP_SOCK.sendto(data[i:i+30000], (TARGET_IP, TARGET_PORT))
        except Exception as e:
            print("[UDP ERROR]", e)
        # ————————————————————————————————

        cv2.putText(frame, f"FPS: {int(fps) if not paused else 0}", (100,50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (50,170,50), 2)
        cv2.putText(frame, "KCF Tracker", (100,20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (50,170,50), 2)
        cv2.putText(frame, "Space: Duraklat/Devam | R: Manuel Tespit | ESC: Çıkış", 
                    (10, frame.shape[0]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)

        # Only show window if not in no-display mode
        if not args.no_display:
            cv2.imshow("Tracking", frame)
            k = cv2.waitKey(1 if not paused else 0) & 0xff
            if k == 27:
                print("Programdan çıkılıyor.")
                break
            elif k == ord('r'):
                new_bbox = detect_object(model, frame)
                if new_bbox is not None:
                    init_bbox = new_bbox
                    init_w, init_h = init_bbox[2], init_bbox[3]
                    tracker = create_kcf_tracker()
                    tracker = init_tracker(tracker, frame, init_bbox)
            elif k == 32:
                paused = not paused
                print("Video " + ("duraklatıldı" if paused else "devam ediyor"))
        else:
            # In no-display mode, just wait a bit to control frame rate
            time.sleep(0.033)  # ~30 FPS
            
            # Check for basic commands in background mode
            # You could implement a different control mechanism here if needed

    cap.release()
    if not args.no_display:
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()

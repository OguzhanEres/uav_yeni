import cv2
import socket
import numpy as np

target_ip = "192.168.88.10"  # Alıcı IP
target_port = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

cap = cv2.VideoCapture(0)  # 0 = Varsayılan webcam

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Görüntüyü sıkıştır (JPEG)
    _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
    data = buffer.tobytes()

    # Veriyi küçük parçalara böl (UDP sınırı: ~65KB ama ideal parça 30KB)
    for i in range(0, len(data), 30000):
        sock.sendto(data[i:i+30000], (target_ip, target_port))

"""
Video Receiver Module for Rocket M5 Video Stream
Receives and displays video stream from Rocket M5 antenna
"""

import cv2
import socket
import numpy as np
import threading
import time
import logging
from typing import Optional, Callable
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt5.QtCore import QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QImage, QPixmap

logger = logging.getLogger(__name__)

class VideoStreamReceiver(QThread):
    """Thread for receiving video stream from Rocket M5"""
    
    frame_received = pyqtSignal(np.ndarray)
    connection_status_changed = pyqtSignal(bool)
    
    def __init__(self, ip="192.168.88.10", port=5005):
        super().__init__()
        self.ip = ip
        self.port = port
        self.running = False
        self.socket = None
        self.frame_buffer = b""
        
    def run(self):
        """Main thread loop for receiving video"""
        self.running = True
        self.setup_socket()
        
        while self.running:
            try:
                self.receive_and_process_frames()
            except Exception as e:
                logger.error(f"Video receiver error: {e}")
                time.sleep(1)  # Wait before retrying
        
        self.cleanup()
    
    def setup_socket(self):
        """Setup UDP socket for video reception"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.ip, self.port))
            self.socket.settimeout(1.0)  # 1 second timeout
            
            logger.info(f"Video receiver socket bound to {self.ip}:{self.port}")
            self.connection_status_changed.emit(True)
            
        except Exception as e:
            logger.error(f"Failed to setup video receiver socket: {e}")
            self.connection_status_changed.emit(False)
    
    def receive_and_process_frames(self):
        """Receive and process video frames"""
        try:
            # Receive data chunk
            data, addr = self.socket.recvfrom(65536)  # Max UDP packet size
            
            # Add to frame buffer
            self.frame_buffer += data
            
            # Try to decode frame from buffer
            self.try_decode_frame()
            
        except socket.timeout:
            # Timeout is normal, continue
            pass
        except Exception as e:
            logger.error(f"Error receiving video data: {e}")
    
    def try_decode_frame(self):
        """Try to decode a complete frame from buffer"""
        # Look for JPEG markers
        start_marker = b'\xff\xd8'  # JPEG start
        end_marker = b'\xff\xd9'    # JPEG end
        
        start_pos = self.frame_buffer.find(start_marker)
        if start_pos == -1:
            return
        
        end_pos = self.frame_buffer.find(end_marker, start_pos)
        if end_pos == -1:
            return
        
        # Extract complete JPEG frame
        frame_data = self.frame_buffer[start_pos:end_pos + 2]
        
        # Remove processed data from buffer
        self.frame_buffer = self.frame_buffer[end_pos + 2:]
        
        # Decode JPEG frame
        try:
            frame_array = np.frombuffer(frame_data, dtype=np.uint8)
            frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
            
            if frame is not None:
                self.frame_received.emit(frame)
                
        except Exception as e:
            logger.error(f"Error decoding video frame: {e}")
    
    def stop(self):
        """Stop video receiver"""
        self.running = False
    
    def cleanup(self):
        """Cleanup resources"""
        if self.socket:
            self.socket.close()
        self.connection_status_changed.emit(False)
        logger.info("Video receiver stopped")


class VideoDisplayWidget(QWidget):
    """Widget for displaying video from Rocket M5"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.video_receiver = None
        self.current_frame = None
        
        self.setup_ui()
        self.setup_video_receiver()
    
    def setup_ui(self):
        """Setup user interface"""
        layout = QVBoxLayout()
        
        # Video display label
        self.video_label = QLabel("Video görüntüsü bekleniyor...")
        self.video_label.setMinimumSize(640, 480)
        self.video_label.setStyleSheet("""
            QLabel {
                border: 2px solid #3498db;
                background-color: #2c3e50;
                color: white;
                font-size: 14px;
                text-align: center;
            }
        """)
        layout.addWidget(self.video_label)
        
        # Control buttons
        control_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Rocket M5 Görüntüsünü Başlat")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 10px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:pressed {
                background-color: #229954;
            }
        """)
        self.start_button.clicked.connect(self.start_video_stream)
        
        self.stop_button = QPushButton("Görüntüyü Durdur")
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 10px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #ec7063;
            }
            QPushButton:pressed {
                background-color: #cb4335;
            }
        """)
        self.stop_button.clicked.connect(self.stop_video_stream)
        self.stop_button.setEnabled(False)
        
        self.status_label = QLabel("Durum: Hazır")
        self.status_label.setStyleSheet("color: #3498db; font-weight: bold;")
        
        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(self.status_label)
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        self.setLayout(layout)
    
    def setup_video_receiver(self):
        """Setup video receiver thread"""
        self.video_receiver = VideoStreamReceiver()
        self.video_receiver.frame_received.connect(self.update_video_display)
        self.video_receiver.connection_status_changed.connect(self.update_connection_status)
    
    def start_video_stream(self):
        """Start video stream reception"""
        try:
            if not self.video_receiver.isRunning():
                self.video_receiver.start()
                self.start_button.setEnabled(False)
                self.stop_button.setEnabled(True)
                self.status_label.setText("Durum: Video akışı başlatılıyor...")
                logger.info("Video stream reception started")
            else:
                logger.warning("Video receiver already running")
                
        except Exception as e:
            logger.error(f"Failed to start video stream: {e}")
            self.status_label.setText(f"Hata: {str(e)}")
    
    def stop_video_stream(self):
        """Stop video stream reception"""
        try:
            if self.video_receiver.isRunning():
                self.video_receiver.stop()
                self.video_receiver.wait(5000)  # Wait up to 5 seconds
                
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.status_label.setText("Durum: Durduruldu")
            self.video_label.setText("Video görüntüsü durduruldu")
            logger.info("Video stream reception stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop video stream: {e}")
            self.status_label.setText(f"Hata: {str(e)}")
    
    def update_video_display(self, frame):
        """Update video display with new frame"""
        try:
            # Convert OpenCV frame to Qt format
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Create QImage
            qt_image = QImage(frame_rgb.data, width, height, bytes_per_line, QImage.Format_RGB888)
            
            # Scale to fit label
            label_size = self.video_label.size()
            pixmap = QPixmap.fromImage(qt_image).scaled(
                label_size, 
                aspectRatioMode=1  # Keep aspect ratio
            )
            
            # Update label
            self.video_label.setPixmap(pixmap)
            self.current_frame = frame
            
        except Exception as e:
            logger.error(f"Error updating video display: {e}")
    
    def update_connection_status(self, connected):
        """Update connection status"""
        if connected:
            self.status_label.setText("Durum: Bağlı - Video akışı alınıyor")
            self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self.status_label.setText("Durum: Bağlantı yok")
            self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
    
    def closeEvent(self, event):
        """Handle widget close event"""
        self.stop_video_stream()
        super().closeEvent(event)
    
    def get_current_frame(self):
        """Get current video frame"""
        return self.current_frame

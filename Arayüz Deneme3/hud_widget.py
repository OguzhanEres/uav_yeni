# hud_widget.py
# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import QWidget, QSizePolicy
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QFont, QPainterPath, 
    QFontMetrics, QPolygon, QRadialGradient, QBrush, QLinearGradient
)
from PyQt5.QtCore import Qt, QRectF, QLineF, QPointF, QPoint, QRect
import math

class HUDWidget(QWidget):
    def __init__(self, parent=None):
        super(HUDWidget, self).__init__(parent)
        
        # Uçuş bilgileri
        self._roll = 0.0
        self._pitch = 0.0
        self._yaw = 0.0
        self._airspeed = 0.0
        self._altitude = 0.0
        self._groundspeed = 0.0
        self._heading = 0.0
        self._throttle = 0.0
        self._batteryLevel = 100.0
        self._batteryVoltage = 12.6
        self._batteryCurrent = 0.0
        self._armable = False
        self._armed = False
        self._flightMode = "UNKNOWN"
        self._gpsStatus = 0        # 0=No fix, 1=GPS fix, 2=DGPS
        self._gpsSatellites = 0    # Görünür uydu sayısı
        self._waypointDist = 0.0   # Hedef noktaya mesafe
        self._targetBearing = 0.0  # Hedef yönü
        
        # Koyu tema renkleri
        self._backgroundColor = QColor(10, 10, 20)  # Çok koyu lacivert
        self._horizonColor = QColor(0, 200, 0)      # Parlak yeşil
        self._skyColor = QColor(0, 30, 60)          # Koyu mavi
        self._groundColor = QColor(80, 40, 10)      # Koyu kahverengi
        
        # HUD bileşen renkleri
        self._primaryColor = QColor(0, 255, 0)      # Ana yeşil renk
        self._warningColor = QColor(255, 165, 0)    # Turuncu uyarı rengi
        self._dangerColor = QColor(255, 0, 0)       # Kırmızı tehlike rengi
        self._textColor = QColor(255, 255, 255)     # Beyaz metin rengi
        
        # Bu widget'ın arka planını koyu lacivert yap
        self.setStyleSheet("background-color: rgb(10, 10, 20);")
        
        # Size policy'yi ayarlayarak widget'ın parent'ı tamamen doldurmasını sağla
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Telemetri verilerini saklayacak dict:
        self._data = {
            "roll": self._roll,                  # Euler açıları (derece)
            "pitch": self._pitch,  
            "yaw": self._yaw,  
            "airspeed": self._airspeed,          # m/s
            "groundspeed": self._groundspeed,    # m/s
            "altitude": self._altitude,          # metre
            "throttle": self._throttle,          # % (0-100)
            "batteryLevel": self._batteryLevel,  # % (0-100)
            "batteryVoltage": self._batteryVoltage, # Volt
            "batteryCurrent": self._batteryCurrent, # Amper
            "armed": self._armed,                # True/False
            "armable": self._armable,            # True/False
            "flightMode": self._flightMode,      # "AUTO", "LOITER", vb.
            "gpsStatus": self._gpsStatus,        # 0=No fix, 1=GPS fix, 2=DGPS
            "gpsSatellites": self._gpsSatellites, # Görünür uydu sayısı
            "waypointDist": self._waypointDist,  # metre
            "targetBearing": self._targetBearing # derece
        }
        
        # Bağlantı durumu - telemetri verisinin gerçek olup olmadığını belirtir
        self._isConnected = False
    
    def setConnectionState(self, connected):
        """Bağlantı durumunu ayarla"""
        self._isConnected = connected
        self.update()  # HUD görüntüsünü yenile

    def updateData(self, data: dict):
        """Dışarıdan gelen telemetri verilerini al ve yeniden çiz."""
        self._data.update(data)
        self.update()
        
    def paintEvent(self, event):
        # Get widget dimensions
        w = self.width()
        h = self.height()
        
        # Calculate center x and center y
        cx = w / 2
        cy = h / 2
        
        # Define layout zones with proper margins
        margin = 20
        header_height = 60
        footer_height = 60
        side_width = 80
        
        # Calculate artificial horizon size (central focus)
        horizon_radius = min((w - 2 * side_width - 4 * margin) / 3, 
                           (h - header_height - footer_height - 2 * margin) / 3)
        
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        # Arka planı siyah olarak ayarla
        p.fillRect(event.rect(), QColor(0, 0, 0))
        
        # Bağlantı yoksa, bağlantı mesajını göster
        if not self._isConnected:
            p.setPen(QColor(255, 0, 0))  # Kırmızı renk
            font = p.font()
            font.setPointSize(14)
            p.setFont(font)
            
            # Ekran merkezinde uyarı mesajını göster
            p.drawText(self.rect(), Qt.AlignCenter, "UAV TELEMETRY CONNECTION REQUIRED")
            
            # Küçük bir açıklama
            font.setPointSize(10)
            p.setFont(font)
            p.drawText(self.rect(), Qt.AlignCenter | Qt.TextFlag.TextSingleLine, 
                       "\n\n\nPress 'Connect' button to establish connection")
            return
    
        # === HEADER SECTION (Top) ===
        # Flight mode and armed status - Top center
        self.drawFlightMode(p, cx, margin + 25, 
                      self._data["flightMode"], 
                      self._data["armed"])
        
        # GPS status - Top left
        self.drawGpsStatus(p, margin, margin, 120, 35, 
                     self._data["gpsStatus"], 
                     self._data["gpsSatellites"])
        
        # Battery status - Top right
        self.drawBatteryStatus(p, w - margin - 120, margin, 120, 35, 
                         self._data["batteryLevel"],
                         self._data["batteryVoltage"],
                         self._data["batteryCurrent"])
        
        # === CENTRAL SECTION (Main display area) ===
        # Artificial Horizon - Center (main focus)
        self.drawArtificialHorizon(p, cx, cy, 
                               self._data["roll"], 
                               self._data["pitch"], 
                               span=horizon_radius)
        
        # Compass - Above artificial horizon with proper spacing
        compass_y = margin + header_height + 20
        self.drawCompass(p, cx, compass_y, w * 0.35, 
                     self._data["yaw"])
        
        # Airspeed indicator - Left side, vertically centered
        airspeed_x = margin + side_width/2
        airspeed_height = h * 0.4
        self.drawAirspeedIndicator(p, airspeed_x, cy, airspeed_height,
                             self._data["airspeed"])
        
        # Altitude indicator - Right side, vertically centered
        altitude_x = w - margin - side_width/2
        self.drawAltitudeIndicator(p, altitude_x, cy, airspeed_height, 
                             self._data["altitude"])
        
        # === FOOTER SECTION (Bottom) ===
        footer_y = h - footer_height
        
        # Throttle indicator - Bottom left
        self.drawThrottleIndicator(p, margin, footer_y + 20, 120, 25, 
                           self._data["throttle"])
        
        # Ground speed - Bottom center
        self.drawGroundspeedIndicator(p, cx, footer_y + 30, 
                               self._data["groundspeed"])
        
        # Waypoint info - Bottom right
        self.drawWaypointInfo(p, w - margin - 120, footer_y + 15, 120, 35,
                        self._data["waypointDist"], 
                        self._data["targetBearing"])
        
        p.end()
        
    def drawArtificialHorizon(self, p: QPainter,
                             cx: float, cy: float,
                             roll: float, pitch: float,
                             span: float = 150.0):
        """Gelişmiş yapay ufuk (attitude indicator) gösterimi - Optimized for better layout"""
        p.save()
        
        # Ana pencere çerçevesi - Adjusted size for better spacing
        rect_size = span * 2
        outer_rect = QRectF(cx - span, cy - span, rect_size, rect_size)
        
        # Yuvarlak bir kırpma alanı oluştur
        clip_path = QPainterPath()
        clip_path.addEllipse(outer_rect)
        p.setClipPath(clip_path)
        
        # Ortaya taşı ve roll/pitch uygula
        p.translate(cx, cy)
        p.rotate(-roll)  # Roll açısını uygula
        
        # Pitch faktörü - açı başına kaç piksel (reduced for better visibility)
        pitch_factor = 2.5
        pitch_offset = pitch * pitch_factor
        p.translate(0, pitch_offset)  # Pitch açısını uygula

        # Gökyüzü ve zemin (dikey olarak genişletilmiş)
        sky_rect = QRectF(-span*2, -span*4, span*4, span*4)
        ground_rect = QRectF(-span*2, 0, span*4, span*4)
        p.fillRect(sky_rect, self._skyColor)
        p.fillRect(ground_rect, self._groundColor)

        # Ufuk çizgisi - Enhanced visibility
        horizon_pen = QPen(self._primaryColor)
        horizon_pen.setWidth(4)
        p.setPen(horizon_pen)
        p.drawLine(QLineF(-span*1.5, 0, span*1.5, 0))
        
        # Pitch çizgileri - Simplified for better readability
        p.setFont(QFont("Arial", 9, QFont.Bold))
        pitch_pen = QPen(self._primaryColor)
        pitch_pen.setWidth(2)
        p.setPen(pitch_pen)
        
        # Pitch açı aralıkları - Reduced density
        for angle in range(-60, 61, 10):
            if angle == 0:
                continue  # Ufuk çizgisi zaten çizildi
                
            y = -angle * pitch_factor  # Pitch değerini piksel konumuna çevir
            
            if angle % 30 == 0:
                # 30 derece bölmeler için uzun çizgiler
                width = span * 0.7
                p.setPen(QPen(self._primaryColor, 3))
            else:
                # 10 derece bölmeler için orta çizgiler
                width = span * 0.4
                p.setPen(QPen(self._primaryColor, 2))
                
            # Yatay çizgiyi çiz
            p.drawLine(QLineF(-width/2, y, width/2, y))
            
            # Açı etiketlerini ekle (20 derecelik artışlarla)
            if angle != 0 and angle % 20 == 0:
                text = f"{abs(angle)}°"
                fm = QFontMetrics(p.font())
                text_width = fm.width(text)
                p.drawText(int(-width/2 - text_width - 8), int(y + 4), text)
                p.drawText(int(width/2 + 8), int(y + 4), text)
        
        # Attitude indicator'ın ortasında sabit merkez sembolü - Enhanced design
        p.resetTransform()
        p.translate(cx, cy)
        
        center_indicator_pen = QPen(self._primaryColor)
        center_indicator_pen.setWidth(3)
        p.setPen(center_indicator_pen)
        
        # Merkez sembol - Aircraft symbol
        symbol_size = span * 0.12
        p.drawLine(QLineF(-symbol_size, 0, -symbol_size/2, symbol_size/4))
        p.drawLine(QLineF(-symbol_size/2, symbol_size/4, 0, 0))
        p.drawLine(QLineF(0, 0, symbol_size/2, symbol_size/4))
        p.drawLine(QLineF(symbol_size/2, symbol_size/4, symbol_size, 0))
        
        # Merkez nokta
        p.setBrush(QBrush(self._primaryColor))
        p.drawEllipse(QPointF(0, 0), 3, 3)
        
        # Yatay referans çizgileri - Extended for better visibility
        horizon_ref_length = span * 1.8
        p.drawLine(QLineF(-horizon_ref_length, 0, -span*1.1, 0))
        p.drawLine(QLineF(span*1.1, 0, horizon_ref_length, 0))
        
        p.restore()
        
        # Döner dış çerçeve (roll göstergesi) - Enhanced design
        p.save()
        p.translate(cx, cy)
        
        # Dış çerçeveyi çiz - Thicker for better visibility
        pen = QPen(self._primaryColor)
        pen.setWidth(3)
        p.setPen(pen)
        p.drawEllipse(QPointF(0, 0), span, span)
        
        # Roll açı göstergelerini çiz - Simplified
        for angle in range(0, 360, 30):
            p.save()
            p.rotate(angle)
            
            if angle == 0:
                # Üstteki işaret (0 derece) - Prominent triangle
                p.setBrush(QBrush(self._primaryColor))
                points = [
                    QPoint(0, int(-span - 20)),
                    QPoint(-12, int(-span)),
                    QPoint(12, int(-span))
                ]
                p.drawPolygon(QPolygon(points))
            elif angle == 180:
                # Alttaki işaret (180 derece) - Small marker
                p.drawLine(QLineF(0, -span, 0, -span - 8))
            elif angle % 90 == 0:
                # 90 ve 270 derece işaretleri - Medium lines
                p.drawLine(QLineF(0, -span, 0, -span - 12))
            else:
                # Diğer işaretler - Small lines
                p.drawLine(QLineF(0, -span, 0, -span - 8))
                
            p.restore()
        
        # Roll göstergesi (üstte hareketli işaret) - Enhanced visibility
        p.rotate(-roll)
        p.setBrush(QBrush(self._warningColor))
        p.setPen(QPen(self._warningColor, 2))
        indicator_points = [
            QPoint(0, int(-span - 20)),
            QPoint(-10, int(-span)),
            QPoint(10, int(-span))
        ]
        p.drawPolygon(QPolygon(indicator_points))
        
        p.restore()

    def drawCompass(self, p: QPainter, cx: float, cy: float, width: float, heading: float):
        """Optimized compass display with better spacing"""
        p.save()
        
        # Pusula şeridinin genişliği - Reduced height for better spacing
        band_height = 25
        
        # Dış çerçeve
        rect = QRectF(cx - width/2, cy - band_height/2, width, band_height)
        
        # Arka plan - Enhanced gradient
        bg_gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        bg_gradient.setColorAt(0, QColor(40, 40, 70))
        bg_gradient.setColorAt(1, QColor(20, 20, 45))
        p.fillRect(rect, bg_gradient)
        
        # Çerçeve - Enhanced visibility
        p.setPen(QPen(self._primaryColor, 2))
        p.drawRect(rect)
        
        # Görünür pusula aralığı (derece) - Reduced for better detail
        visible_range = 90
        degree_width = width / visible_range
        
        # Heading değeri 0-360 aralığında normalleştir
        heading_norm = heading % 360
        start_angle = (heading_norm + visible_range / 2) % 360
        
        # Açı işaretlerini ve etiketleri çiz
        p.setFont(QFont("Arial", 9, QFont.Bold))
        p.setPen(self._primaryColor)
        
        for i in range(visible_range + 20):
            angle = (start_angle - i) % 360
            x = cx - width/2 + i * degree_width
            
            if x < cx - width/2 or x > cx + width/2:
                continue
                
            if angle % 30 == 0:
                # Main directions - Enhanced visibility
                p.setPen(QPen(self._primaryColor, 3))
                p.drawLine(QLineF(x, cy - band_height/2, x, cy - band_height/2 + band_height*0.6))
                
                # Direction labels - Cleaner display
                direction = ""
                if angle == 0:
                    direction = "N"
                elif angle == 90:
                    direction = "E"
                elif angle == 180:
                    direction = "S"
                elif angle == 270:
                    direction = "W"
                    
                if direction:
                    p.setFont(QFont("Arial", 10, QFont.Bold))
                    p.drawText(QRectF(x - 12, cy - band_height/2 + band_height*0.65, 24, band_height*0.35), 
                              Qt.AlignCenter, direction)
                    p.setFont(QFont("Arial", 9, QFont.Bold))
            elif angle % 15 == 0:
                # 15 degree markers
                p.setPen(QPen(self._primaryColor, 2))
                p.drawLine(QLineF(x, cy - band_height/2, x, cy - band_height/2 + band_height*0.4))
        
        # Center indicator - Enhanced triangle
        p.setBrush(QBrush(self._warningColor))
        p.setPen(QPen(self._warningColor, 2))
        
        triangle = QPolygon([
            QPoint(int(cx), int(cy - band_height/2 - 12)),
            QPoint(int(cx - 8), int(cy - band_height/2)),
            QPoint(int(cx + 8), int(cy - band_height/2))
        ])
        p.drawPolygon(triangle)
        
        # Heading value - Positioned below for clarity
        p.setPen(self._textColor)
        p.setFont(QFont("Arial", 11, QFont.Bold))
        p.drawText(QRectF(cx - 40, cy + band_height/2 + 5, 80, 18), 
                  Qt.AlignCenter, f"{int(heading_norm)}°")
        
        p.restore()

    def drawAirspeedIndicator(self, p: QPainter, x: float, cy: float, height: float, airspeed: float):
        """Enhanced airspeed indicator with better spacing"""
        p.save()
        
        # Optimized width for side panel
        width = 60
        
        # Ana çerçeve
        rect = QRectF(x - width/2, cy - height/2, width, height)
        
        # Enhanced background
        bg_gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        bg_gradient.setColorAt(0, QColor(25, 25, 45))
        bg_gradient.setColorAt(1, QColor(45, 45, 65))
        p.fillRect(rect, bg_gradient)
        
        # Enhanced border
        p.setPen(QPen(self._primaryColor, 2))
        p.drawRect(rect)
        
        # Title label - positioned outside for clarity
        p.setPen(self._textColor)
        p.setFont(QFont("Arial", 9, QFont.Bold))
        title_rect = QRectF(x - width/2, cy - height/2 - 25, width, 20)
        p.drawText(title_rect, Qt.AlignCenter, "AIRSPEED")
        
        # Speed scale - optimized range
        p.setFont(QFont("Arial", 8))
        
        # Visible range centered on current speed
        visible_range = 40  # m/s
        min_speed = max(0, airspeed - visible_range/2)
        max_speed = min_speed + visible_range
        scale_factor = height / visible_range
        
        # Scale lines and values
        for speed in range(int(min_speed), int(max_speed) + 1, 5):
            if speed < 0:
                continue
                
            # Y position
            y = cy + height/2 - (speed - min_speed) * scale_factor
            
            if y < cy - height/2 or y > cy + height/2:
                continue
            
            # Major markers every 10 units
            if speed % 10 == 0:
                p.setPen(QPen(self._primaryColor, 2))
                p.drawLine(QLineF(x - width/2 + 5, y, x - width/2 + width*0.4, y))
                p.setPen(self._textColor)
                p.drawText(QRectF(x - width/2 + width*0.45, y - 8, width*0.5, 16), 
                          Qt.AlignLeft | Qt.AlignVCenter, f"{speed}")
            else:
                # Minor markers
                p.setPen(QPen(self._primaryColor, 1))
                p.drawLine(QLineF(x - width/2 + 5, y, x - width/2 + width*0.25, y))
        
        # Current speed indicator
        indicator_y = cy + height/2 - (airspeed - min_speed) * scale_factor
        
        if indicator_y >= cy - height/2 and indicator_y <= cy + height/2:
            p.setBrush(QBrush(self._warningColor))
            p.setPen(QPen(self._warningColor, 2))
            
            triangle = QPolygon([
                QPoint(int(x - width/2 - 8), int(indicator_y)),
                QPoint(int(x - width/2 + 2), int(indicator_y - 6)),
                QPoint(int(x - width/2 + 2), int(indicator_y + 6))
            ])
            p.drawPolygon(triangle)
        
        # Current speed display box - positioned below
        box_rect = QRectF(x - width/2, cy + height/2 + 8, width, 22)
        p.setBrush(QBrush(QColor(0, 0, 0, 200)))
        p.setPen(QPen(self._primaryColor, 1))
        p.drawRoundedRect(box_rect, 3, 3)
        
        p.setPen(self._textColor)
        p.setFont(QFont("Arial", 10, QFont.Bold))
        p.drawText(box_rect, Qt.AlignCenter, f"{airspeed:.1f}")
        
        # Units label
        p.setFont(QFont("Arial", 8))
        units_rect = QRectF(x - width/2, cy + height/2 + 32, width, 15)
        p.drawText(units_rect, Qt.AlignCenter, "m/s")
        
        p.restore()

    def drawAltitudeIndicator(self, p: QPainter, x: float, cy: float, height: float, altitude: float):
        """Enhanced altitude indicator with better spacing"""
        p.save()
        
        # Optimized width for side panel
        width = 60
        
        # Ana çerçeve
        rect = QRectF(x - width/2, cy - height/2, width, height)
        
        # Enhanced background
        bg_gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        bg_gradient.setColorAt(0, QColor(25, 25, 45))
        bg_gradient.setColorAt(1, QColor(45, 45, 65))
        p.fillRect(rect, bg_gradient)
        
        # Enhanced border
        p.setPen(QPen(self._primaryColor, 2))
        p.drawRect(rect)
        
        # Title label - positioned outside for clarity
        p.setPen(self._textColor)
        p.setFont(QFont("Arial", 9, QFont.Bold))
        title_rect = QRectF(x - width/2, cy - height/2 - 25, width, 20)
        p.drawText(title_rect, Qt.AlignCenter, "ALTITUDE")
        
        # Altitude scale - optimized range
        p.setFont(QFont("Arial", 8))
        
        # Visible range centered on current altitude
        visible_range = 80  # meters
        min_alt = max(0, altitude - visible_range/2)
        max_alt = min_alt + visible_range
        scale_factor = height / visible_range
        
        # Scale lines and values
        for alt in range(int(min_alt), int(max_alt) + 1, 10):
            if alt < 0:
                continue
                
            # Y position
            y = cy + height/2 - (alt - min_alt) * scale_factor
            
            if y < cy - height/2 or y > cy + height/2:
                continue
            
            # Major markers every 20 meters
            if alt % 20 == 0:
                p.setPen(QPen(self._primaryColor, 2))
                p.drawLine(QLineF(x + width/2 - 5, y, x + width/2 - width*0.4, y))
                p.setPen(self._textColor)
                p.drawText(QRectF(x + width/2 - width*0.95, y - 8, width*0.5, 16), 
                          Qt.AlignRight | Qt.AlignVCenter, f"{alt}")
            else:
                # Minor markers
                p.setPen(QPen(self._primaryColor, 1))
                p.drawLine(QLineF(x + width/2 - 5, y, x + width/2 - width*0.25, y))
        
        # Current altitude indicator
        indicator_y = cy + height/2 - (altitude - min_alt) * scale_factor
        
        if indicator_y >= cy - height/2 and indicator_y <= cy + height/2:
            p.setBrush(QBrush(self._warningColor))
            p.setPen(QPen(self._warningColor, 2))
            
            triangle = QPolygon([
                QPoint(int(x + width/2 + 8), int(indicator_y)),
                QPoint(int(x + width/2 - 2), int(indicator_y - 6)),
                QPoint(int(x + width/2 - 2), int(indicator_y + 6))
            ])
            p.drawPolygon(triangle)
        
        # Current altitude display box - positioned below
        box_rect = QRectF(x - width/2, cy + height/2 + 8, width, 22)
        p.setBrush(QBrush(QColor(0, 0, 0, 200)))
        p.setPen(QPen(self._primaryColor, 1))
        p.drawRoundedRect(box_rect, 3, 3)
        
        p.setPen(self._textColor)
        p.setFont(QFont("Arial", 10, QFont.Bold))
        p.drawText(box_rect, Qt.AlignCenter, f"{altitude:.1f}")
        
        # Units label
        p.setFont(QFont("Arial", 8))
        units_rect = QRectF(x - width/2, cy + height/2 + 32, width, 15)
        p.drawText(units_rect, Qt.AlignCenter, "m")
        
        p.restore()
        p.setFont(QFont("Arial", 10, QFont.Bold))
        p.drawText(box_rect, Qt.AlignCenter, f"{altitude:.1f} m")
        
        p.restore()

    def drawBatteryStatus(self, p: QPainter, x: float, y: float, width: float, height: float, 
                         level: float, voltage: float, current: float):
        """Batarya durumu göstergesi"""
        p.save()
        
        # Arka plan
        rect = QRectF(x, y, width, height)
        p.setBrush(QBrush(QColor(0, 0, 0, 180)))
        p.setPen(QPen(self._primaryColor))
        p.drawRect(rect)
        
        # Batarya ikonu
        icon_width = 30
        icon_margin = 5
        icon_rect = QRectF(x + icon_margin, y + icon_margin, 
                          icon_width, height - 2*icon_margin)
        
        # Batarya gövdesi
        p.setBrush(QBrush(QColor(30, 30, 30)))
        p.setPen(QPen(self._primaryColor))
        p.drawRect(icon_rect)
        
        # Batarya üst kısmı
        cap_width = icon_width / 4
        cap_height = height / 3
        cap_rect = QRectF(x + icon_margin + (icon_width - cap_width)/2, 
                         y + icon_margin - cap_height/4, 
                         cap_width, cap_height/2)
        p.drawRect(cap_rect)
        
        # Batarya doluluğu
        fill_width = icon_width - 4
        fill_height = height - 2*icon_margin - 4
        level_pct = max(0.0, min(1.0, level / 100.0))
        fill_rect = QRectF(x + icon_margin + 2, 
                          y + icon_margin + 2 + (1.0 - level_pct) * fill_height, 
                          fill_width, level_pct * fill_height)
        
        # Batarya seviyesine göre renk değişimi
        if level > 50:
            p.setBrush(QBrush(QColor(0, 255, 0)))
        elif level > 25:
            p.setBrush(QBrush(QColor(255, 165, 0)))
        else:
            p.setBrush(QBrush(QColor(255, 0, 0)))
            
        p.setPen(Qt.NoPen)
        p.drawRect(fill_rect)
        
        # Batarya yüzdesi ve voltaj bilgisi
        text_x = x + icon_margin + icon_width + 10
        text_width = width - icon_width - icon_margin - 10
        
        p.setPen(self._textColor)
        p.setFont(QFont("Arial", 8, QFont.Bold))
        
        # Yüzde
        percent_rect = QRectF(text_x, y + 2, text_width, height/2 - 2)
        p.drawText(percent_rect, Qt.AlignLeft | Qt.AlignVCenter, f"{int(level)}%")
        
        # Voltaj
        voltage_rect = QRectF(text_x, y + height/2, text_width, height/2 - 2)
        p.drawText(voltage_rect, Qt.AlignLeft | Qt.AlignVCenter, f"{voltage:.1f}V")
        
        p.restore()

    def drawGpsStatus(self, p: QPainter, x: float, y: float, width: float, height: float, 
                     status: int, satellites: int):
        """GPS durumu göstergesi"""
        p.save()
        
        # Arka plan
        rect = QRectF(x, y, width, height)
        p.setBrush(QBrush(QColor(0, 0, 0, 180)))
        p.setPen(QPen(self._primaryColor))
        p.drawRect(rect)
        
        # GPS ikonu
        icon_size = min(width, height) - 10
        icon_x = x + 5
        icon_y = y + (height - icon_size) / 2
        
        # GPS sinyal gücü göstergesi
        p.setPen(QPen(self._primaryColor, 2))
        
        # GPS durumuna göre renk
        if status == 0:  # No Fix
            signal_color = self._dangerColor
            status_text = "NO FIX"
        elif status == 1:  # GPS Fix
            signal_color = self._warningColor
            status_text = "GPS"
        else:  # DGPS veya daha iyi
            signal_color = self._primaryColor
            status_text = "DGPS"
            
        p.setPen(QPen(signal_color, 2))
        
        # Sinyal çubukları (4 çubuk)
        bar_width = icon_size / 6
        bar_spacing = icon_size / 12
        bar_max_height = icon_size * 0.8
        
        # GPS çeşitliliği ve uydu sayısını görselleştir
        for i in range(4):
            bar_height = bar_max_height * (i+1) / 4
            
            # Eğer uydu sayısı yeterli değilse, çubukları soluk göster
            if satellites >= (i+1) * 2:
                p.setBrush(signal_color)
            else:
                p.setBrush(QColor(80, 80, 80))
                
            bar_x = icon_x + i * (bar_width + bar_spacing)
            bar_y = icon_y + icon_size - bar_height
            bar_rect = QRectF(bar_x, bar_y, bar_width, bar_height)
            p.drawRect(bar_rect)
        
        # GPS bilgisi
        text_x = x + icon_size + 10
        text_width = width - icon_size - 15
        
        p.setPen(self._textColor)
        p.setFont(QFont("Arial", 8, QFont.Bold))
        
        # GPS durumu
        status_rect = QRectF(text_x, y + 2, text_width, height/2 - 2)
        p.drawText(status_rect, Qt.AlignLeft | Qt.AlignVCenter, status_text)
        
        # Uydu sayısı
        sat_rect = QRectF(text_x, y + height/2, text_width, height/2 - 2)
        p.drawText(sat_rect, Qt.AlignLeft | Qt.AlignVCenter, f"SAT: {satellites}")
        
        p.restore()

    def drawFlightMode(self, p: QPainter, cx: float, y: float, mode: str, armed: bool):
        """Enhanced flight mode display for header area"""
        p.save()
        
        # Enhanced dimensions for better visibility
        width = 140
        height = 35
        rect = QRectF(cx - width/2, y - height/2, width, height)
        
        # Enhanced background with better visual feedback
        if armed:
            bg_color = QColor(0, 120, 0, 200)  # Bright green for armed
            border_color = self._primaryColor
        else:
            bg_color = QColor(120, 60, 0, 200)  # Orange for disarmed
            border_color = self._warningColor
        
        p.setBrush(QBrush(bg_color))
        p.setPen(QPen(border_color, 2))
        p.drawRoundedRect(rect, 5, 5)
        
        # Mode text - larger and more prominent
        p.setPen(self._textColor)
        p.setFont(QFont("Arial", 13, QFont.Bold))
        mode_rect = QRectF(cx - width/2, y - height/2 + 2, width, height/2 + 5)
        p.drawText(mode_rect, Qt.AlignCenter, mode)
        
        # Armed/Disarmed status - smaller but visible
        p.setFont(QFont("Arial", 9, QFont.Bold))
        status_rect = QRectF(cx - width/2, y + 2, width, height/2 - 2)
        status_text = "● ARMED" if armed else "○ DISARMED"
        p.drawText(status_rect, Qt.AlignCenter, status_text)
        
        p.restore()

    def drawThrottleIndicator(self, p: QPainter, x: float, y: float, width: float, height: float, throttle: float):
        """Enhanced throttle indicator for footer area"""
        p.save()
        
        # Enhanced frame
        rect = QRectF(x, y, width, height)
        bg_gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        bg_gradient.setColorAt(0, QColor(25, 25, 45))
        bg_gradient.setColorAt(1, QColor(45, 45, 65))
        p.fillRect(rect, bg_gradient)
        p.setPen(QPen(self._primaryColor, 2))
        p.drawRoundedRect(rect, 3, 3)
        
        # Title - positioned above
        p.setPen(self._textColor)
        p.setFont(QFont("Arial", 9, QFont.Bold))
        p.drawText(QRectF(x, y - 20, width, 18), 
                  Qt.AlignCenter, "THROTTLE")
        
        # Inner area for the bar
        inner_margin = 3
        inner_rect = QRectF(x + inner_margin, y + inner_margin, 
                           width - 2*inner_margin, height - 2*inner_margin)
        
        # Scale markers
        p.setPen(QPen(self._primaryColor, 1))
        for i in range(6):  # 0%, 20%, 40%, 60%, 80%, 100%
            tick_x = x + inner_margin + (width - 2*inner_margin) * i / 5
            p.drawLine(QLineF(tick_x, y + inner_margin, tick_x, y + inner_margin + 4))
            
            # Labels for 0%, 50%, 100%
            if i in [0, 2, 5]:
                p.setFont(QFont("Arial", 8))
                p.drawText(QRectF(tick_x - 15, y + height - 15, 30, 12), 
                          Qt.AlignCenter, f"{i*20}%")
        
        # Throttle fill bar
        throttle_pct = max(0.0, min(1.0, throttle / 100.0))
        fill_width = (width - 2*inner_margin) * throttle_pct
        
        # Color based on throttle level
        if throttle_pct <= 0.3:
            fill_color = QColor(0, 255, 0)  # Green
        elif throttle_pct <= 0.7:
            fill_color = QColor(255, 165, 0)  # Orange
        else:
            fill_color = QColor(255, 0, 0)  # Red
            
        fill_rect = QRectF(x + inner_margin, y + inner_margin + 4, 
                          fill_width, height - 2*inner_margin - 4 - 12)
        
        p.setBrush(QBrush(fill_color))
        p.setPen(Qt.NoPen)
        p.drawRect(fill_rect)
        
        # Throttle percentage - centered
        p.setPen(self._textColor)
        p.setFont(QFont("Arial", 10, QFont.Bold))
        text_rect = QRectF(x, y + inner_margin + 4, width, height - 2*inner_margin - 4 - 12)
        p.drawText(text_rect, Qt.AlignCenter, f"{int(throttle)}%")
                
        p.restore()

    def drawGroundspeedIndicator(self, p: QPainter, cx: float, y: float, groundspeed: float):
        """Enhanced ground speed indicator for footer center"""
        p.save()
        
        width = 120
        height = 30
        
        # Enhanced frame
        rect = QRectF(cx - width/2, y - height/2, width, height)
        bg_gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        bg_gradient.setColorAt(0, QColor(25, 25, 45))
        bg_gradient.setColorAt(1, QColor(45, 45, 65))
        p.fillRect(rect, bg_gradient)
        p.setPen(QPen(self._primaryColor, 2))
        p.drawRoundedRect(rect, 3, 3)
        
        # Title - positioned above
        p.setPen(self._textColor)
        p.setFont(QFont("Arial", 9, QFont.Bold))
        title_rect = QRectF(cx - width/2, y - height/2 - 22, width, 18)
        p.drawText(title_rect, Qt.AlignCenter, "GROUND SPEED")
        
        # Speed value - larger and centered
        p.setFont(QFont("Arial", 12, QFont.Bold))
        p.drawText(rect, Qt.AlignCenter, f"{groundspeed:.1f} m/s")
        
        p.restore()

    def drawInfoPanel(self, p: QPainter, cx: float, y: float, width: float, height: float):
        """Ana bilgi paneli - çeşitli telemetri verilerini gösterir"""
        p.save()
        
        # Ana çerçeve
        rect = QRectF(cx - width/2, y - height/2, width, height)
        p.setBrush(QBrush(QColor(0, 0, 0, 180)))
        p.setPen(QPen(self._primaryColor))
        p.drawRect(rect)
        
        # İçeriği 3 sütuna böl
        col_width = width / 3
        
        # Font ayarları
        p.setPen(self._textColor)
        p.setFont(QFont("Arial", 9))
        
        # 1. Sütun - Roll/Pitch/Yaw
        col1_x = cx - width/2
        
        p.drawText(QRectF(col1_x + 5, y - height/2 + 5, col_width - 5, 15), 
                  Qt.AlignLeft, f"Roll: {self._data['roll']:.1f}°")
                  
        p.drawText(QRectF(col1_x + 5, y - height/2 + 20, col_width - 5, 15), 
                  Qt.AlignLeft, f"Pitch: {self._data['pitch']:.1f}°")
                  
        p.drawText(QRectF(col1_x + 5, y - height/2 + 35, col_width - 5, 15), 
                  Qt.AlignLeft, f"Yaw: {self._data['yaw']:.1f}°")
        
        # 2. Sütun - GPS Konum
        col2_x = cx - width/2 + col_width
        
        # Koordinat değerlerini burada göstermiyoruz çünkü 
        # veri modeli şu anda bunları içermiyor. Gerektiğinde eklenebilir.
        p.drawText(QRectF(col2_x + 5, y - height/2 + 5, col_width - 5, 15), 
                  Qt.AlignLeft, "GPS Position:")
                  
        p.drawText(QRectF(col2_x + 5, y - height/2 + 20, col_width - 5, 15), 
                  Qt.AlignLeft, f"Lat: -")
                  
        p.drawText(QRectF(col2_x + 5, y - height/2 + 35, col_width - 5, 15), 
                  Qt.AlignLeft, f"Lon: -")
        
        # 3. Sütun - İrtifa ve Hız
        col3_x = cx - width/2 + col_width * 2
        
        p.drawText(QRectF(col3_x + 5, y - height/2 + 5, col_width - 10, 15), 
                  Qt.AlignRight, f"Alt: {self._data['altitude']:.1f} m")
                  
        p.drawText(QRectF(col3_x + 5, y - height/2 + 20, col_width - 10, 15), 
                  Qt.AlignRight, f"AS: {self._data['airspeed']:.1f} m/s")
                  
        p.drawText(QRectF(col3_x + 5, y - height/2 + 35, col_width - 10, 15), 
                  Qt.AlignRight, f"GS: {self._data['groundspeed']:.1f} m/s")
        
        p.restore()

    def drawWaypointInfo(self, p: QPainter, x: float, y: float, width: float, height: float, 
                        distance: float, bearing: float):
        """Enhanced waypoint information display for footer area"""
        p.save()
        
        # Enhanced frame
        rect = QRectF(x, y, width, height)
        bg_gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        bg_gradient.setColorAt(0, QColor(25, 25, 45))
        bg_gradient.setColorAt(1, QColor(45, 45, 65))
        p.fillRect(rect, bg_gradient)
        p.setPen(QPen(self._primaryColor, 2))
        p.drawRoundedRect(rect, 3, 3)
        
        # Title - positioned above
        p.setPen(self._textColor)
        p.setFont(QFont("Arial", 9, QFont.Bold))
        p.drawText(QRectF(x, y - 22, width, 18), 
                  Qt.AlignCenter, "WAYPOINT")
        
        # Compass indicator - smaller and positioned right
        compass_size = height - 8
        compass_x = x + width - compass_size - 4
        compass_y = y + 4
        
        # Compass circle
        p.setPen(QPen(self._primaryColor, 2))
        compass_center = QPointF(compass_x + compass_size/2, compass_y + compass_size/2)
        p.drawEllipse(compass_center, compass_size/2, compass_size/2)
        
        # Direction arrow
        p.save()
        p.translate(compass_center)
        p.rotate(bearing)
        
        # Enhanced arrow design
        arrow_size = compass_size * 0.35
        path = QPainterPath()
        path.moveTo(0, -arrow_size)
        path.lineTo(arrow_size * 0.3, arrow_size * 0.2)
        path.lineTo(0, 0)
        path.lineTo(-arrow_size * 0.3, arrow_size * 0.2)
        path.closeSubpath()
        
        p.setBrush(QBrush(self._warningColor))
        p.setPen(QPen(self._warningColor, 2))
        p.drawPath(path)
        
        p.restore()
        
        # Information text area
        text_width = compass_x - x - 8
        
        # Distance display
        p.setPen(self._textColor)
        p.setFont(QFont("Arial", 9, QFont.Bold))
        
        # Format distance
        if distance < 1000:
            distance_text = f"{int(distance)} m"
        else:
            distance_text = f"{distance/1000:.1f} km"
            
        dist_rect = QRectF(x + 4, y + 4, text_width, height/2 - 2)
        p.drawText(dist_rect, Qt.AlignLeft | Qt.AlignVCenter, f"D: {distance_text}")
                  
        # Bearing display
        bearing_rect = QRectF(x + 4, y + height/2 + 2, text_width, height/2 - 6)
        p.drawText(bearing_rect, Qt.AlignLeft | Qt.AlignVCenter, f"B: {int(bearing)}°")
                  
        p.restore()

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
        # Eğer eski updateData ve setConnectionState silindiyse, yeniden ekle:
        self.roll_value = 0.0
        self.pitch_value = 0.0
        self.yaw_value = 0.0
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
        self.setStyleSheet("background-color: rgb(10, 10, 20); border: 2px solid red;")
        
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
    """def updateData(self, data: dict):
        super().updateData(data)
    """
    """def setConnectionState(self, connected: bool):
        super().setConnectionState(connected)
    """
    
    def updateData(self, data: dict):
        """
        HUD’un internal _data sözlüğünü günceller ve
        paint/update() metodunu çağırır.
        """
        self._data.update(data)
        self.update()

    def setConnectionState(self, connected: bool):
        """
        Bağlantı durumunu HUD içindeki flag’e yazar
        ve yeniden çizer.
        """
        self._isConnected = connected
        self.update()
    
    def update_flight_data(self, data: dict):
        """
        data içindeki alanları field_mapping üzerinden
        HUD’in internal _data sözlüğüne map’ler ve updateData()’yı çağırır.
        """
        field_mapping = {
            'roll': 'roll',
            'pitch': 'pitch', 
            'yaw': 'yaw',
            'airspeed': 'airspeed',
            'groundspeed': 'groundspeed',
            'altitude': 'altitude',
            'throttle': 'throttle',
            'batteryLevel': 'batteryLevel',
            'batteryVoltage': 'batteryVoltage',
            'batteryCurrent': 'batteryCurrent',
            'armed': 'armed',
            'armable': 'armable',
            'flightMode': 'flightMode',
            'gpsStatus': 'gpsStatus',
            'gpsSatellites': 'gpsSatellites',
            'waypointDist': 'waypointDist',
            'targetBearing': 'targetBearing'
        }
        
        mapped = {}
        for src, dst in field_mapping.items():
            if src in data:
                mapped[dst] = data[src]        
        self.updateData(mapped)

    def set_connection_status(self, connected: bool):
        """Bağlantı durumunu HUD’e bildirir."""
        self.setConnectionState(connected)
        
    def paintEvent(self, event):
        # Debug: HUD çizimi başlıyor
        print(f"HUD paintEvent called - size: {self.width()}x{self.height()}")
        
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
            p.drawText(self.rect().adjusted(0, 40, 0, 0), Qt.AlignCenter, 
                       "Press 'Connect' button to establish connection")
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
        """Yapay ufuk göstergesi"""
        p.save()
        
        # Ana çerçeve
        rect_size = span * 0.8
        horizon_rect = QRectF(cx - rect_size/2, cy - rect_size/2, rect_size, rect_size)
        
        # Arka plan
        p.fillRect(horizon_rect, self._skyColor)
        
        # Ufuk çizgisi
        p.setPen(QPen(self._horizonColor, 2))
        p.drawLine(int(cx - rect_size/2), int(cy), int(cx + rect_size/2), int(cy))
        
        # Merkez nokta
        p.setPen(QPen(self._primaryColor, 3))
        center_size = 10
        p.drawLine(int(cx - center_size), int(cy), int(cx + center_size), int(cy))
        p.drawLine(int(cx), int(cy - center_size), int(cx), int(cy + center_size))
        
        # Çerçeve
        p.setPen(QPen(self._primaryColor, 2))
        p.drawRect(horizon_rect)
        
        p.restore()
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
        """Pusula göstergesi"""
        p.save()
        
        # Pusula çerçevesi
        compass_rect = QRectF(cx - width/2, cy - 30, width, 60)
        p.setPen(QPen(self._primaryColor, 2))
        p.drawRect(compass_rect)
        
        # Yön yazısı
        p.setFont(QFont("Arial", 12, QFont.Bold))
        p.setPen(self._textColor)
        heading_text = f"HDG: {heading:.0f}°"
        p.drawText(compass_rect, Qt.AlignCenter, heading_text)
        
        p.restore()

    def drawAirspeedIndicator(self, p: QPainter, x: float, cy: float, height: float, airspeed: float):
        """Hava hızı göstergesi"""
        p.save()
        
        # Gösterge alanı
        indicator_rect = QRectF(x - 40, cy - height/2, 80, height)
        p.setPen(QPen(self._primaryColor, 2))
        p.drawRect(indicator_rect)
        
        # Hız değeri
        p.setFont(QFont("Arial", 10, QFont.Bold))
        p.setPen(self._textColor)
        p.drawText(indicator_rect.adjusted(5, 5, -5, -height/2), Qt.AlignTop, "AIRSPEED")
        
        speed_text = f"{airspeed:.1f} m/s"
        p.drawText(indicator_rect, Qt.AlignCenter, speed_text)
        
        p.restore()

    def drawAltitudeIndicator(self, p: QPainter, x: float, cy: float, height: float, altitude: float):
        """İrtifa göstergesi"""
        p.save()
        
        # Gösterge alanı
        indicator_rect = QRectF(x - 40, cy - height/2, 80, height)
        p.setPen(QPen(self._primaryColor, 2))
        p.drawRect(indicator_rect)
        
        # İrtifa değeri
        p.setFont(QFont("Arial", 10, QFont.Bold))
        p.setPen(self._textColor)
        p.drawText(indicator_rect.adjusted(5, 5, -5, -height/2), Qt.AlignTop, "ALTITUDE")
        
        alt_text = f"{altitude:.1f} m"
        p.drawText(indicator_rect, Qt.AlignCenter, alt_text)
        
        p.restore()

    def drawBatteryStatus(self, p: QPainter, x: float, y: float, width: float, height: float, 
                         level: float, voltage: float, current: float):
        """Batarya durumu göstergesi"""
        p.save()
        
        # Batarya çerçevesi
        battery_rect = QRectF(x, y, width, height)
        p.setPen(QPen(self._primaryColor, 2))
        p.drawRect(battery_rect)
        
        # Batarya seviyesi rengi
        if level > 50:
            fill_color = self._primaryColor
        elif level > 20:
            fill_color = self._warningColor
        else:
            fill_color = self._dangerColor
        
        # Batarya dolgu seviyesi
        fill_width = (width - 4) * (level / 100.0)
        fill_rect = QRectF(x + 2, y + 2, fill_width, height - 4)
        p.fillRect(fill_rect, fill_color)
        
        # Batarya metni
        p.setFont(QFont("Arial", 9))
        p.setPen(self._textColor)
        battery_text = f"BAT: {level:.0f}%\n{voltage:.1f}V"
        p.drawText(battery_rect, Qt.AlignCenter, battery_text)
        
        p.restore()

    def drawGpsStatus(self, p: QPainter, x: float, y: float, width: float, height: float, 
                     status: int, satellites: int):
        """GPS durumu göstergesi"""
        p.save()
        
        # GPS çerçevesi
        gps_rect = QRectF(x, y, width, height)
        p.setPen(QPen(self._primaryColor, 2))
        p.drawRect(gps_rect)
        
        # GPS durumu rengi
        if status >= 2:
            status_color = self._primaryColor
            status_text = "GPS: FIX"
        elif status == 1:
            status_color = self._warningColor
            status_text = "GPS: WEAK"
        else:
            status_color = self._dangerColor
            status_text = "GPS: NO FIX"
        
        # GPS metni
        p.setFont(QFont("Arial", 9))
        p.setPen(status_color)
        gps_info = f"{status_text}\nSAT: {satellites}"
        p.drawText(gps_rect, Qt.AlignCenter, gps_info)
        
        p.restore()

    def drawFlightMode(self, p: QPainter, cx: float, y: float, mode: str, armed: bool):
        """Uçuş modu göstergesi"""
        p.save()
        
        # Uçuş modu metni
        p.setFont(QFont("Arial", 12, QFont.Bold))
        
        # Armed durumuna göre renk
        if armed:
            p.setPen(self._dangerColor)
            mode_text = f"{mode} - ARMED"
        else:
            p.setPen(self._primaryColor)
            mode_text = f"{mode} - DISARMED"
        
        # Metin çerçevesi
        fm = QFontMetrics(p.font())
        text_width = fm.width(mode_text)
        text_height = fm.height()
        
        text_rect = QRectF(cx - text_width/2 - 10, y - text_height/2 - 5, 
                          text_width + 20, text_height + 10)
        
        p.setPen(QPen(self._primaryColor, 2))
        p.drawRect(text_rect)
        
        # Metni çiz
        if armed:
            p.setPen(self._dangerColor)
        else:
            p.setPen(self._primaryColor)
        
        p.drawText(text_rect, Qt.AlignCenter, mode_text)
        
        p.restore()

    def drawThrottleIndicator(self, p: QPainter, x: float, y: float, width: float, height: float, throttle: float):
        """Gaz kelebeği göstergesi"""
        p.save()
        
        # Throttle çerçevesi
        throttle_rect = QRectF(x, y, width, height)
        p.setPen(QPen(self._primaryColor, 2))
        p.drawRect(throttle_rect)
        
        # Throttle seviyesi
        fill_width = (width - 4) * (throttle / 100.0)
        fill_rect = QRectF(x + 2, y + 2, fill_width, height - 4)
        p.fillRect(fill_rect, self._primaryColor)
        
        # Throttle metni
        p.setFont(QFont("Arial", 9))
        p.setPen(self._textColor)
        throttle_text = f"THR: {throttle:.0f}%"
        p.drawText(throttle_rect, Qt.AlignCenter, throttle_text)
        
        p.restore()

    def drawGroundspeedIndicator(self, p: QPainter, cx: float, y: float, groundspeed: float):
        """Yer hızı göstergesi"""
        p.save()
        
        # Yer hızı metni
        p.setFont(QFont("Arial", 10, QFont.Bold))
        p.setPen(self._textColor)
        
        speed_text = f"GND SPD: {groundspeed:.1f} m/s"
        fm = QFontMetrics(p.font())
        text_width = fm.width(speed_text)
        
        text_rect = QRectF(cx - text_width/2 - 5, y - 10, text_width + 10, 20)
        p.setPen(QPen(self._primaryColor, 1))
        p.drawRect(text_rect)
        
        p.setPen(self._textColor)
        p.drawText(text_rect, Qt.AlignCenter, speed_text)
        
        p.restore()

    def drawWaypointInfo(self, p: QPainter, x: float, y: float, width: float, height: float, 
                        distance: float, bearing: float):
        """Waypoint bilgi göstergesi"""
        p.save()
        
        # Waypoint çerçevesi
        wp_rect = QRectF(x, y, width, height)
        p.setPen(QPen(self._primaryColor, 2))
        p.drawRect(wp_rect)
        
        # Waypoint metni
        p.setFont(QFont("Arial", 9))
        p.setPen(self._textColor)
        wp_text = f"WP DIST\n{distance:.0f}m\n{bearing:.0f}°"
        p.drawText(wp_rect, Qt.AlignCenter, wp_text)
        
        p.restore()

    def drawInfoPanel(self, p: QPainter, cx: float, y: float, width: float, height: float):
        """Bilgi paneli"""
        p.save()
        
        # Panel çerçevesi
        panel_rect = QRectF(cx - width/2, y, width, height)
        p.setPen(QPen(self._primaryColor, 2))
        p.drawRect(panel_rect)
        
        # Sistem bilgileri
        p.setFont(QFont("Arial", 9))
        p.setPen(self._textColor)
        info_text = "HUD ACTIVE\nSYSTEM READY"
        p.drawText(panel_rect, Qt.AlignCenter, info_text)
        
        p.restore()

    # Uyumluluk metodları
    def update_flight_data(self, data: dict):
        """Uçuş verilerini güncelle"""
        self.updateData(data)

    def set_connection_status(self, connected: bool):
        """Bağlantı durumunu ayarla"""
        self.setConnectionState(connected)

    def showEvent(self, event):
        """Widget gösterildiğinde"""
        super().showEvent(event)
        print(f"HUD Widget shown - size: {self.size()}")

    def resizeEvent(self, event):
        """Widget boyutu değiştiğinde"""
        super().resizeEvent(event)
        print(f"HUD Widget resized to: {self.size()}")

    def update_attitude(self, roll: float, pitch: float, yaw: float):
        """Attitude verilerini güncelle"""
        data = {
            'roll': roll,
            'pitch': pitch,
            'yaw': yaw
        }
        self.updateData(data)

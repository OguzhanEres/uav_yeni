# 🚁 Hüma UAV Otonom Kalkış ve İniş Sistemi

Bu döküman, Hüma UAV Ground Control Station'a eklenen otonom kalkış ve iniş özelliklerini açıklar.

## ✨ Yeni Özellikler

### 🚀 Otonom Kalkış
- **Otomatik silahlanma**: UAV'yi otomatik olarak arm eder
- **GPS konumu alma**: Mevcut konumu otomatik olarak alır
- **Misyon planlaması**: Kalkış misyonunu otomatik olarak oluşturur
- **Uçuş modu kontrolü**: GUIDED → AUTO mod geçişi
- **Güvenlik kontrolleri**: Arm edilebilirlik ve GPS durumu kontrolü

### 🛬 Otonom İniş
- **Yaklaşma rotası**: Güvenli iniş için yaklaşma noktası belirleme
- **Çok aşamalı iniş**: Takeoff → Waypoint → Landing sırası
- **Konum bazlı iniş**: Mevcut konuma veya belirlenen konuma iniş
- **Akıllı misyon planlaması**: Otomatik 3-aşamalı misyon oluşturma

### 🚨 Acil Durum Sistemi
- **RTL modu**: Return to Launch otomatik aktivasyonu
- **Güvenlik önceliği**: Anında güvenli konuma dönüş
- **Hızlı müdahale**: Tek tuşla acil durum aktivasyonu

## 🎮 Kullanım Kılavuzu

### Arayüz Entegrasyonu

#### 1. Buton Kontrolü
- **TAKEOFF Butonu**: Artık otonom kalkış yapar
- **RTL Butonu**: Hem RTL hem de otonom iniş seçenekleri
- **Sağ Tık Menüsü**: RTL butonuna sağ tıklayarak otonom iniş seçenekleri

#### 2. Klavye Kısayolları
- **Ctrl+T**: Otonom Kalkış
- **Ctrl+L**: Otonom İniş
- **Ctrl+E**: Acil Durum (RTL)

#### 3. Menü Sistemi
- **Otonom İşlemler** menüsü otomatik eklenir
- Tüm otonom operasyonlara kolay erişim

### Adım Adım Kullanım

#### 🚁 Otonom Kalkış
1. **Bağlantı Kontrolü**: UAV'nin bağlı olduğundan emin olun
2. **TAKEOFF Butonuna Tıklayın** veya **Ctrl+T** basın
3. **İrtifa Girin**: İstenilen kalkış irtifasını girin (10-500m)
4. **Onaylayın**: Sistem otomatik olarak:
   - GUIDED moda geçer
   - UAV'yi arm eder
   - GPS konumunu alır
   - Kalkış misyonunu oluşturur
   - AUTO moda geçer

#### 🛬 Otonom İniş
1. **Bağlantı Kontrolü**: UAV'nin bağlı olduğundan emin olun
2. **RTL Butonuna Sağ Tıklayın** veya **Ctrl+L** basın
3. **"Otonom İniş" Seçin**
4. **Yaklaşma İrtifası Girin**: İniş yaklaşma irtifasını girin (20-200m)
5. **Onaylayın**: Sistem otomatik olarak:
   - Mevcut konumu alır
   - 3-aşamalı iniş misyonu oluşturur
   - AUTO moda geçer

#### 🚨 Acil Durum
1. **Ctrl+E** basın veya **Otonom İşlemler → Acil Durum**
2. **Onaylayın**: Sistem anında RTL moduna geçer

## 📊 Sistem Gereksinimleri

### Donanım
- **GPS**: Konum bilgisi için gerekli
- **Telemetri**: MAVLink bağlantısı
- **Autopilot**: ArduPilot uyumlu flight controller

### Yazılım
- **Python 3.8+**
- **PyQt5**
- **pymavlink**
- **dronekit**

## 🔧 Teknik Detaylar

### MAVLink İletişimi
```python
# Otonom kalkış
mavlink_client.autonomous_takeoff(altitude=50.0)

# Otonom iniş
mavlink_client.autonomous_land(lon, lat, current_alt, cruise_alt)

# Acil durum
mavlink_client.emergency_stop()
```

### Misyon Yapısı
```
Kalkış Misyonu:
- Sequence 0: MAV_CMD_NAV_TAKEOFF

İniş Misyonu:
- Sequence 0: MAV_CMD_NAV_TAKEOFF (mevcut pozisyon)
- Sequence 1: MAV_CMD_NAV_WAYPOINT (yaklaşma noktası)
- Sequence 2: MAV_CMD_NAV_LAND (iniş noktası)
```

## 🛡️ Güvenlik Önlemleri

### Otonom Kalkış Güvenliği
- **GPS Fix Kontrolü**: GPS sinyali gerekli
- **Arm Kontrolü**: Arm edilebilirlik kontrolleri
- **Timeout Koruması**: 30 saniye timeout
- **Mod Kontrolü**: GUIDED mod gerekliliği

### Otonom İniş Güvenliği
- **Konum Doğrulama**: GPS konumu zorunlu
- **Yaklaşma Rotası**: Güvenli yaklaşma için offset
- **Çok Aşamalı İniş**: Kontrollü iniş süreci
- **Acil Durum Hazırlığı**: Herhangi bir anda RTL modu

### Acil Durum Protokolü
- **Onay Gerekliliği**: Yanlışlıkla aktivasyon engelleme
- **Hızlı Müdahale**: Anında RTL modu
- **Güvenli Dönüş**: Ev konumuna otomatik dönüş

## 🔍 Sorun Giderme

### Yaygın Sorunlar

#### Kalkış Başarısız
- **GPS Sinyali**: GPS fix olduğundan emin olun
- **Arm Durumu**: UAV arm edilebilir durumda mı?
- **Bağlantı**: MAVLink bağlantısını kontrol edin

#### İniş Başarısız
- **Konum Bilgisi**: GPS konumu alınabilir mi?
- **Mod Durumu**: AUTO mod aktif mi?
- **Misyon Onayı**: Misyon ACK alındı mı?

#### Bağlantı Sorunları
- **Port Kontrolü**: COM portu veya UDP bağlantısı
- **Baud Rate**: Doğru baud rate (varsayılan: 57600)
- **Telemetri**: Telemetri akışı aktif mi?

### Hata Kodları
```
❌ İHA bağlı değil! → Bağlantı kurulması gerekli
❌ Mevcut konum alınamadı! → GPS sorunu
❌ Otonom kalkış başarısız! → GPS veya arm sorunu
❌ Otonom iniş başarısız! → Konum veya misyon sorunu
```

## 📝 Geliştirici Notları

### Kod Yapısı
- **MAVLinkClient**: Otonom operasyonlar için genişletildi
- **MainWindow**: UI entegrasyonu eklendi
- **Autonomous Methods**: Yeni handler metodları

### Genişletme Olanakları
- **Waypoint Sistemi**: Çoklu waypoint desteği
- **Kamera Entegrasyonu**: Görüntü bazlı iniş
- **Telemetri Logging**: Detaylı log sistemi
- **Failsafe Mekanizması**: Gelişmiş güvenlik

### Test Sistemi
```bash
# Test scriptini çalıştırma
cd uav_project
python test_autonomous_operations.py
```

## 📞 Destek

Herhangi bir sorun veya öneri için:
- **GitHub Issues**: Repository üzerinden issue açın
- **Dokümantasyon**: Bu README'yi inceleyin
- **Test Scripti**: Sistemizi test edin

---

**© 2024 Hüma UAV - Otonom Uçuş Sistemi**

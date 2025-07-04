#!/usr/bin/env python3
"""
Test script for antenna system
Tests PowerBeam 5AC Gen2 and Rocket M5 functionality
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.uav_system.communication.antenna_controller import AntennaController
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_antenna_system():
    """Test the complete antenna system"""
    print("🚁 Hüma UAV - Anten Sistemi Test")
    print("=" * 40)
    
    # Initialize antenna controller
    antenna_controller = AntennaController()
    
    # Test 1: Check antenna status
    print("\n1️⃣ Anten durumu kontrol ediliyor...")
    status = antenna_controller.check_antenna_status()
    
    print(f"PowerBeam 5AC Gen2:")
    print(f"  ├─ Bağlı: {'✅' if status['powerbeam']['connected'] else '❌'}")
    print(f"  ├─ Dinleme Modu: {'✅' if status['powerbeam']['listening_mode'] else '❌'}")
    print(f"  └─ Sinyal Gücü: {status['powerbeam']['signal_strength']} dBm")
    
    print(f"\nRocket M5:")
    print(f"  ├─ Bağlı: {'✅' if status['rocket_m5']['connected'] else '❌'}")
    print(f"  ├─ Video Akışı: {'✅' if status['rocket_m5']['streaming'] else '❌'}")
    print(f"  └─ Görüntü Kalitesi: {status['rocket_m5']['video_quality']}")
    
    # Test 2: Start antenna system
    print("\n2️⃣ Anten sistemi başlatılıyor...")
    try:
        success = antenna_controller.start_antenna_system()
        if success:
            print("✅ Anten sistemi başarıyla başlatıldı!")
        else:
            print("❌ Anten sistemi başlatılamadı!")
            return False
    except Exception as e:
        print(f"❌ Hata: {e}")
        return False
    
    # Test 3: Monitor for 30 seconds
    print("\n3️⃣ 30 saniye sistem izleniyor...")
    for i in range(6):
        time.sleep(5)
        status = antenna_controller.check_antenna_status()
        print(f"  📊 {(i+1)*5}s - PowerBeam: {'🟢' if status['powerbeam']['connected'] else '🔴'} | "
              f"Rocket M5: {'🟢' if status['rocket_m5']['connected'] else '🔴'}")
    
    # Test 4: Stop antenna system
    print("\n4️⃣ Anten sistemi durduruluyor...")
    try:
        success = antenna_controller.stop_antenna_system()
        if success:
            print("✅ Anten sistemi başarıyla durduruldu!")
        else:
            print("⚠️ Anten sistemi kısmen durduruldu!")
    except Exception as e:
        print(f"❌ Hata: {e}")
        return False
    
    print("\n🎉 Test tamamlandı!")
    return True

if __name__ == "__main__":
    try:
        success = test_antenna_system()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n🛑 Test kullanıcı tarafından durduruldu")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test hatası: {e}")
        sys.exit(1)

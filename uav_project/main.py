#!/usr/bin/env python3
"""
Hüma UAV Ground Control Station
Main application entry point.
"""

import sys
import os
import logging
from pathlib import Path

# Add project root and src to Python path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_path))

# Set up logging early
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def check_webengine_availability():
    """Check if QtWebEngine is available and working."""
    try:
        from PyQt5.QtWebEngineWidgets import QWebEngineView
        from PyQt5.QtCore import QUrl
        return True
    except ImportError as e:
        logging.error(f"QtWebEngine not available: {e}. Map functionality will be limited.")
        return False
    except Exception as e:
        logging.error(f"QtWebEngine error: {e}")
        return False

def setup_webengine_args():
    """Setup QtWebEngine arguments to avoid GPU issues."""
    webengine_args = [
        "--disable-gpu",
        "--disable-software-rasterizer", 
        "--disable-gpu-sandbox",
        "--disable-web-security",
        "--disable-features=VizDisplayCompositor",
        "--ignore-gpu-blacklist",
        "--enable-logging",
        "--log-level=0"
    ]
    
    # Set environment variables for QtWebEngine
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = ' '.join(webengine_args)
    os.environ['QT_LOGGING_RULES'] = 'qt.webenginecontext.debug=true'
    
    logging.info(f"QtWebEngine args set: {' '.join(webengine_args)}")

def main():
    """Main application entry point."""
    try:
        # Setup QtWebEngine arguments early
        setup_webengine_args()
        
        from PyQt5.QtWidgets import QApplication, QMessageBox, QSplashScreen, QLabel
        from PyQt5.QtCore import Qt, QCoreApplication, QTimer
        from PyQt5.QtGui import QPixmap, QFont
        
        # Enable high DPI scaling and OpenGL context sharing (for QtWebEngine)
        QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseSoftwareOpenGL, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        
        # Create application
        app = QApplication(sys.argv)
        app.setApplicationName("Hüma GCS")
        app.setApplicationVersion("2.0")
        app.setOrganizationName("Hüma UAV")
        
        # Create splash screen
        splash = QSplashScreen()
        splash.resize(400, 300)
        splash.setStyleSheet("""
            QSplashScreen {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2c3e50, stop:1 #34495e);
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 10px;
            }
        """)
        
        # Create splash label
        splash_label = QLabel("🚁 Hüma UAV Ground Control Station\n\nSistem başlatılıyor...", splash)
        splash_label.setAlignment(Qt.AlignCenter)
        splash_label.setStyleSheet("color: white; font-size: 16px; font-weight: bold; padding: 20px;")
        splash_label.resize(400, 300)
        
        splash.show()
        app.processEvents()
        
        # Check WebEngine availability
        splash_label.setText("🚁 Hüma UAV Ground Control Station\n\n🔍 WebEngine kontrol ediliyor...")
        app.processEvents()
        
        webengine_available = check_webengine_availability()
        if not webengine_available:
            splash_label.setText("🚁 Hüma UAV Ground Control Station\n\n⚠️ Uyarı: Harita desteği sınırlı!\nPyQtWebEngine yüklenemedi.")
            app.processEvents()
            QTimer.singleShot(2000, lambda: None)  # Wait 2 seconds
            
        # Import and create main window
        splash_label.setText("🚁 Hüma UAV Ground Control Station\n\n🏗️ Ana pencere yükleniyor...")
        app.processEvents()
        
        try:
            from src.uav_system.ui.desktop.main_window import HumaGCS
        except ImportError:
            # Fallback import
            from src.uav_system.ui.desktop.main_window import HumaGCS
        
        # Create main window with webengine status
        splash_label.setText("🚁 Hüma UAV Ground Control Station\n\n⚡ Sistem başlatılıyor...")
        app.processEvents()
        
        main_window = HumaGCS()
        
        # Set webengine status
        if hasattr(main_window, 'set_webengine_status'):
            main_window.set_webengine_status(webengine_available)
        
        splash_label.setText("🚁 Hüma UAV Ground Control Station\n\n🗺️ Harita sistemi yükleniyor...")
        app.processEvents()
        
        # Show main window and close splash after a delay
        main_window.show()
        
        def close_splash():
            splash.close()
            logging.info("Application started successfully")
            
        # Close splash screen after 4 seconds
        QTimer.singleShot(4000, close_splash)
        
        # Start application event loop
        sys.exit(app.exec_())
        
    except ImportError as e:
        print(f"❌ Failed to import required modules: {e}")
        print("Please make sure all dependencies are installed:")
        print("pip install -r requirements.txt")
        print("\nMissing dependencies might include:")
        print("- PyQt5")
        print("- PyQtWebEngine")
        print("- dronekit")
        print("- pymavlink")
        sys.exit(1)
        
    except Exception as e:
        print(f"❌ Failed to start application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

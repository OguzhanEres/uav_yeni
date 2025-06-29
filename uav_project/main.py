#!/usr/bin/env python3
"""
Hüma UAV Ground Control Station
Main application entry point.
"""

import sys
import os
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set up logging early
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Main application entry point."""
    try:
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import Qt, QCoreApplication
        
        # Enable high DPI scaling and OpenGL context sharing (for QtWebEngine)
        QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        
        # Create application
        app = QApplication(sys.argv)
        app.setApplicationName("Hüma GCS")
        app.setApplicationVersion("2.0")
        app.setOrganizationName("Hüma UAV")
        
        # Import and create main window
        from src.uav_system.ui.desktop.main_window import HumaGCS
        
        # Create and show main window
        main_window = HumaGCS()
        main_window.show()
        
        # Start application event loop
        sys.exit(app.exec_())
        
    except ImportError as e:
        print(f"Failed to import required modules: {e}")
        print("Please make sure all dependencies are installed:")
        print("pip install -r requirements.txt")
        sys.exit(1)
        
    except Exception as e:
        print(f"Failed to start application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

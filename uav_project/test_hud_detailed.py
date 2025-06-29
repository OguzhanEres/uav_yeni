#!/usr/bin/env python3
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Test step by step
try:
    print("Step 1: Importing PyQt5...")
    from PyQt5.QtWidgets import QWidget, QSizePolicy
    print("✓ PyQt5 imports successful")
    
    print("Step 2: Importing hud_widget module...")
    import src.uav_system.ui.desktop.hud_widget as hud_module
    print("✓ Module imported successfully")
    
    print("Step 3: Checking module attributes...")
    attrs = dir(hud_module)
    print(f"Module attributes: {[attr for attr in attrs if not attr.startswith('_')]}")
    
    print("Step 4: Looking for HUDWidget class...")
    if hasattr(hud_module, 'HUDWidget'):
        print("✓ HUDWidget class found")
        HUDWidget = hud_module.HUDWidget
        print(f"HUDWidget class: {HUDWidget}")
    else:
        print("✗ HUDWidget class not found in module")
        
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

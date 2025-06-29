#!/usr/bin/env python3
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print(f"Project root: {project_root}")
print(f"Python path: {sys.path[:3]}")

try:
    from src.uav_system.ui.desktop.hud_widget import HUDWidget
    print("✓ HUD widget imported successfully")
    print(f"HUD widget class: {HUDWidget}")
except ImportError as e:
    print(f"✗ Import error: {e}")
    import traceback
    traceback.print_exc()

#!/usr/bin/env python3
# Simple test to identify the issue with HUD widget

try:
    exec(open('src/uav_system/ui/desktop/hud_widget.py').read())
    print("✓ HUD widget file executed successfully")
    
    # Check if HUDWidget is defined in locals
    if 'HUDWidget' in locals():
        print("✓ HUDWidget class is defined")
        print(f"HUDWidget: {HUDWidget}")
    else:
        print("✗ HUDWidget class not found in locals")
        print(f"Available names: {[name for name in locals().keys() if not name.startswith('_')]}")
        
except Exception as e:
    print(f"✗ Error executing HUD widget file: {e}")
    import traceback
    traceback.print_exc()

"""
Migration script to help move existing UAV code to the new modular structure.
Run this script to automatically migrate your existing code.
"""

import os
import shutil
from pathlib import Path

# Define source and destination mappings
MIGRATION_MAP = {
    # Source file -> New location
    "Arayüz Deneme3/arayuz_fonksiyon.py": "src/uav_system/ui/desktop/main_window.py",
    "Arayüz Deneme3/hud_widget.py": "src/uav_system/ui/desktop/hud_widget.py",
    "Arayüz Deneme3/leaflet_map.py": "src/uav_system/ui/desktop/map_widget.py",
    "Arayüz Deneme3/mavlink_client.py": "src/uav_system/communication/mavlink/legacy_client.py",
    "Arayüz Deneme3/plane.py": "src/uav_system/flight_control/plane_controller.py",
    "Arayüz Deneme3/huma_gcs.ui": "src/uav_system/ui/desktop/resources/huma_gcs.ui",
    "Arayüz Deneme3/assets/": "src/uav_system/ui/desktop/resources/assets/",
    
    # Computer Vision
    "Temiz/HUMA_UAV/detection/yolov5_detector.py": "src/uav_system/computer_vision/detection/legacy_yolo.py",
    "Temiz/HUMA_UAV/tracker/tracker_kcf.py": "src/uav_system/computer_vision/tracking/legacy_kcf.py",
    "Temiz/HUMA_UAV/main.py": "src/uav_system/computer_vision/camera_system.py",
    "Temiz/HUMA_UAV/util/webcam.py": "src/uav_system/sensors/camera/webcam.py",
    "Temiz/HUMA_UAV/best.pt": "src/uav_system/computer_vision/models/pretrained/best.pt",
    "Temiz/HUMA_UAV/requirements.txt": "config/cv_requirements.txt",
    
    # Other modules
    "Yolo+Kcf/run.py": "scripts/legacy_yolo_kcf.py",
    "requirements.txt": "config/legacy_requirements.txt",
}

def migrate_files(source_root: str, dest_root: str):
    """Migrate files from old structure to new structure."""
    source_path = Path(source_root)
    dest_path = Path(dest_root)
    
    print(f"Migrating from: {source_path}")
    print(f"Migrating to: {dest_path}")
    print("-" * 50)
    
    migrated_count = 0
    skipped_count = 0
    
    for source_rel, dest_rel in MIGRATION_MAP.items():
        source_file = source_path / source_rel
        dest_file = dest_path / dest_rel
        
        if source_file.exists():
            # Create destination directory if it doesn't exist
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                if source_file.is_file():
                    # Copy file
                    shutil.copy2(source_file, dest_file)
                    print(f"✓ Migrated: {source_rel} -> {dest_rel}")
                    migrated_count += 1
                elif source_file.is_dir():
                    # Copy directory
                    if dest_file.exists():
                        shutil.rmtree(dest_file)
                    shutil.copytree(source_file, dest_file)
                    print(f"✓ Migrated directory: {source_rel} -> {dest_rel}")
                    migrated_count += 1
            except Exception as e:
                print(f"✗ Failed to migrate {source_rel}: {e}")
                skipped_count += 1
        else:
            print(f"⚠ Source not found: {source_rel}")
            skipped_count += 1
    
    print("-" * 50)
    print(f"Migration complete: {migrated_count} migrated, {skipped_count} skipped")
    
    return migrated_count, skipped_count

def create_init_files(dest_root: str):
    """Create __init__.py files for Python packages."""
    dest_path = Path(dest_root)
    
    # Find all directories that should be Python packages
    for root, dirs, files in os.walk(dest_path / "src"):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != '__pycache__']
        
        init_file = Path(root) / "__init__.py"
        if not init_file.exists():
            init_file.touch()
            print(f"Created: {init_file.relative_to(dest_path)}")

def generate_migration_report(dest_root: str):
    """Generate a migration report with next steps."""
    report = """
# Migration Report

## Successfully Migrated Files

Your existing UAV code has been migrated to the new modular structure. Here's what you need to do next:

## 1. Update Import Statements

The migrated files will need their import statements updated. For example:

### Old imports:
```python
from leaflet_map import LeafletMap
from hud_widget import HUDWidget
from mavlink_client import MAVLinkClient
```

### New imports:
```python
from ...ui.desktop.map_widget import LeafletMap
from ...ui.desktop.hud_widget import HUDWidget
from ...communication.mavlink.mavlink_client import MAVLinkClient
```

## 2. Update Configuration

1. Copy `.env.example` to `.env` and update with your settings
2. Review `config/settings.py` for any additional configuration needed
3. Update paths in your code to use the new structure

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## 4. Test the Migration

1. Run the new main window:
```bash
python -m src.uav_system.ui.desktop.main_window
```

2. Test individual components:
```bash
# Test MAVLink connection
python -m src.uav_system.communication.mavlink.mavlink_client

# Test computer vision
python -m src.uav_system.computer_vision.detection.yolo_detector
```

## 5. Gradual Code Updates

The migration preserves your original functionality while providing a foundation for improvements:

1. Start by updating the main UI file to use the new imports
2. Gradually refactor components to use the new base classes
3. Take advantage of improved error handling and logging
4. Add unit tests using the new structure

## 6. Benefits of the New Structure

- **Modularity**: Each component is self-contained
- **Testability**: Easy to write unit tests for individual components
- **Maintainability**: Clear separation of concerns
- **Scalability**: Easy to add new features
- **Configuration**: Centralized configuration management
- **Logging**: Professional logging system
- **Error Handling**: Robust error handling throughout

## Next Steps

1. Review the migrated code in `src/uav_system/ui/desktop/main_window.py`
2. Update imports and test basic functionality
3. Gradually migrate to use the new improved components
4. Add tests for critical functionality
5. Consider containerization using the provided Docker files

Happy coding! 🚁
"""
    
    report_file = Path(dest_root) / "MIGRATION_REPORT.md"
    report_file.write_text(report)
    print(f"\n📋 Migration report saved to: {report_file}")

def main():
    """Main migration function."""
    # Get current directory (should be uav_yeni)
    current_dir = Path.cwd()
    source_root = current_dir
    dest_root = current_dir / "uav_project"
    
    print("🚁 UAV Project Migration Tool")
    print("=" * 50)
    
    # Perform migration
    migrated, skipped = migrate_files(str(source_root), str(dest_root))
    
    # Create __init__.py files
    print("\n📦 Creating Python package files...")
    create_init_files(str(dest_root))
    
    # Generate migration report
    generate_migration_report(str(dest_root))
    
    print(f"\n🎉 Migration completed!")
    print(f"📁 New project location: {dest_root}")
    print(f"📋 See MIGRATION_REPORT.md for next steps")

if __name__ == "__main__":
    main()

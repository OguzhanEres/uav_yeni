#!/usr/bin/env python3
"""
Quick test runner for UAV GCS with Gazebo simulation
"""

import sys
import os
import subprocess
from pathlib import Path

def print_header():
    """Print application header."""
    print("🚁 UAV Ground Control Station - Quick Test Runner")
    print("=" * 60)

def check_requirements():
    """Check if all requirements are installed."""
    print("Checking requirements...")
    
    try:
        import PyQt5
        print("✅ PyQt5 installed")
    except ImportError:
        print("❌ PyQt5 not installed")
        return False
    
    try:
        # Check pymavlink without importing dronekit (has compatibility issues)
        import pymavlink
        print("✅ pymavlink installed")
    except ImportError:
        print("❌ pymavlink not installed")
        return False
    
    print("✅ Core requirements check passed")
    return True

def run_tests():
    """Run validation tests."""
    print("\nRunning validation tests...")
    
    # Run HUD and Map widget tests
    print("Testing HUD and Map widgets...")
    result = subprocess.run([sys.executable, "test_hud_map_fix.py"], 
                          capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ HUD and Map widget tests passed")
    else:
        print("❌ HUD and Map widget tests failed")
        print(result.stdout)
        print(result.stderr)
        return False
    
    # Run Gazebo connection test
    print("\nTesting Gazebo connection...")
    result = subprocess.run([sys.executable, "test_gazebo_connection.py"], 
                          capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Gazebo connection test passed")
    else:
        print("❌ Gazebo connection test failed")
        print(result.stdout)
        print(result.stderr)
        return False
    
    return True

def run_application():
    """Run the main application."""
    print("\n" + "=" * 60)
    print("🚀 Starting UAV Ground Control Station")
    print("=" * 60)
    print()
    print("Instructions:")
    print("1. Make sure Gazebo simulation is running")
    print("2. In the application, click 'Connect' button")
    print("3. Select 'UDP (127.0.0.1:14550)' from dropdown")
    print("4. HUD and Map widgets should show live data")
    print()
    print("Starting application...")
    print("Press Ctrl+C to stop")
    print()
    
    try:
        # Run the main application
        subprocess.run([sys.executable, "main.py"])
    except KeyboardInterrupt:
        print("\n\nApplication stopped by user")
    except Exception as e:
        print(f"\n\nApplication error: {e}")

def main():
    """Main function."""
    print_header()
    
    # Check if we're in the right directory
    if not Path("main.py").exists():
        print("❌ Please run this script from the uav_project directory")
        return 1
    
    # Check requirements
    if not check_requirements():
        print("\n❌ Missing requirements. Please install them:")
        print("pip install -r requirements.txt")
        return 1
    
    # Run tests
    if not run_tests():
        print("\n❌ Tests failed. Please check the issues above.")
        return 1
    
    print("\n✅ All tests passed! The application is ready to run.")
    
    # Ask user if they want to run the application
    try:
        response = input("\nDo you want to start the application now? (y/n): ")
        if response.lower() in ['y', 'yes']:
            run_application()
        else:
            print("\nTo start the application manually, run: python main.py")
    except KeyboardInterrupt:
        print("\n\nExiting...")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())